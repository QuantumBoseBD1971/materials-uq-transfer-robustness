"""Phase-B repeated evaluation of frozen abstention policies.

The OOD labels are used only after each score threshold has been selected and
frozen on the familiar-material calibration partition.
"""

from __future__ import annotations

import hashlib
import math
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"

BASE_SEED = 20260724
N_SEEDS = 10
N_ENSEMBLE_MEMBERS = 5
TREES_PER_MEMBER = 80
MINIMUM_COVERAGE = 0.20
UCB_LEVEL = 0.95
N_BOOTSTRAPS = 300
TASKS = {"expt_gap": 0.50, "log_kvrh": 0.15}


def parse_formula(formula: str) -> dict[str, float]:
    """Parse the reduced formulae emitted by pymatgen in the Phase-A files."""
    tokens = re.findall(r"[A-Z][a-z]?|\(|\)|\d+(?:\.\d+)?", formula)
    stack: list[dict[str, float]] = [{}]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "(":
            stack.append({})
        elif token == ")":
            group = stack.pop()
            multiplier = 1.0
            if index + 1 < len(tokens) and re.fullmatch(r"\d+(?:\.\d+)?", tokens[index + 1]):
                index += 1
                multiplier = float(tokens[index])
            for element, amount in group.items():
                stack[-1][element] = stack[-1].get(element, 0.0) + amount * multiplier
        elif re.fullmatch(r"[A-Z][a-z]?", token):
            amount = 1.0
            if index + 1 < len(tokens) and re.fullmatch(r"\d+(?:\.\d+)?", tokens[index + 1]):
                index += 1
                amount = float(tokens[index])
            stack[-1][token] = stack[-1].get(token, 0.0) + amount
        index += 1
    if len(stack) != 1 or not stack[0]:
        raise ValueError(f"Could not parse formula: {formula}")
    total = sum(stack[0].values())
    return {element: amount / total for element, amount in stack[0].items()}


def composition_matrix(formulas: pd.Series) -> np.ndarray:
    parsed = [parse_formula(x) for x in formulas]
    elements = sorted({el for comp in parsed for el in comp})
    lookup = {el: i for i, el in enumerate(elements)}
    matrix = np.zeros((len(parsed), len(elements) + 2), dtype=float)
    for row, comp in enumerate(parsed):
        fractions = np.array(list(comp.values()))
        for el, amount in comp.items():
            matrix[row, lookup[el]] = amount
        matrix[row, -2] = len(comp)
        matrix[row, -1] = -(fractions * np.log(fractions)).sum()
    return matrix


def grouped_split(frame: pd.DataFrame, holdout: str, seed: int):
    """Split familiar canonical compositions as groups to prevent leakage."""
    rng = np.random.default_rng(seed)
    ood = frame.index[frame["family"].eq(holdout)].to_numpy()
    familiar = frame.loc[frame["family"].ne(holdout)]
    groups = familiar["composition_group"].drop_duplicates().to_numpy()
    rng.shuffle(groups)
    n_cal_groups = max(1, round(0.20 * len(groups)))
    cal_groups = set(groups[:n_cal_groups])
    calibration = familiar.index[familiar["composition_group"].isin(cal_groups)].to_numpy()
    training = familiar.index[~familiar["composition_group"].isin(cal_groups)].to_numpy()
    assert not set(frame.loc[training, "composition_group"]) & set(
        frame.loc[calibration, "composition_group"]
    )
    return training, calibration, ood


def fit_bootstrap_ensemble(x: np.ndarray, y: np.ndarray, seed: int):
    rng = np.random.default_rng(seed)
    models = []
    for member in range(N_ENSEMBLE_MEMBERS):
        sample = rng.integers(0, len(y), len(y))
        model = RandomForestRegressor(
            n_estimators=TREES_PER_MEMBER,
            min_samples_leaf=2,
            max_features=0.7,
            n_jobs=-1,
            random_state=seed + member,
        )
        model.fit(x[sample], y[sample])
        models.append(model)
    return models


def ensemble_predict(models, x: np.ndarray):
    predictions = np.vstack([model.predict(x) for model in models])
    return predictions.mean(axis=0), predictions.std(axis=0, ddof=1)


def nearest_distance(train: np.ndarray, query: np.ndarray):
    model = NearestNeighbors(n_neighbors=1).fit(train)
    return model.kneighbors(query, return_distance=True)[0][:, 0]


def calibration_ecdf(reference: np.ndarray, values: np.ndarray):
    ordered = np.sort(reference)
    return np.searchsorted(ordered, values, side="right") / len(ordered)


def bootstrap_mae_ucb(errors: np.ndarray, rng: np.random.Generator):
    if not len(errors):
        return np.nan
    samples = rng.choice(errors, size=(N_BOOTSTRAPS, len(errors)), replace=True)
    return float(np.quantile(samples.mean(axis=1), UCB_LEVEL))


def select_frozen_threshold(scores: np.ndarray, errors: np.ndarray, seed: int):
    """Choose maximum coverage whose bootstrap MAE UCB meets the risk limit."""
    order = np.argsort(scores, kind="stable")
    candidates = np.unique(
        np.linspace(math.ceil(MINIMUM_COVERAGE * len(order)), len(order), 41).astype(int)
    )
    rng = np.random.default_rng(seed)
    eligible = []
    for retained in candidates:
        chosen = order[:retained]
        ucb = bootstrap_mae_ucb(errors[chosen], rng)
        eligible.append((retained, float(scores[order[retained - 1]]), ucb))
    return eligible


def risk_curve(scores: np.ndarray, errors: np.ndarray):
    order = np.argsort(scores, kind="stable")
    coverage = np.arange(1, len(order) + 1) / len(order)
    risk = np.cumsum(errors[order]) / np.arange(1, len(order) + 1)
    aurc = float(np.trapezoid(risk, coverage))
    return coverage, risk, aurc


def run():
    warnings.filterwarnings(
        "ignore",
        message="`sklearn.utils.parallel.delayed` should be used*",
        category=UserWarning,
    )
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary_rows, curve_rows, split_rows = [], [], []

    for task, epsilon in TASKS.items():
        frame = pd.read_csv(PROCESSED / f"{task}_phase_a.csv").reset_index(drop=True)
        features = composition_matrix(frame["formula"])
        frame["composition_group"] = [
            hashlib.sha256(np.round(row[:-2], 12).tobytes()).hexdigest()[:16]
            for row in features
        ]
        eligible = frame["family"].value_counts().loc[lambda x: x >= 250].index

        for holdout in eligible:
            for repeat in range(N_SEEDS):
                seed = BASE_SEED + repeat
                train, calibration, ood = grouped_split(frame, holdout, seed)
                split_hash = hashlib.sha256(
                    "|".join(sorted(frame.loc[ood, "row_id"])).encode()
                ).hexdigest()[:16]
                scaler = StandardScaler().fit(features[train])
                x_train, x_cal, x_ood = [
                    scaler.transform(features[idx]) for idx in (train, calibration, ood)
                ]
                y_train, y_cal, y_ood = [
                    frame.loc[idx, "target"].to_numpy() for idx in (train, calibration, ood)
                ]
                models = fit_bootstrap_ensemble(x_train, y_train, seed)
                pred_cal, std_cal = ensemble_predict(models, x_cal)
                pred_ood, std_ood = ensemble_predict(models, x_ood)
                error_cal = np.abs(y_cal - pred_cal)
                error_ood = np.abs(y_ood - pred_ood)
                distance_cal = nearest_distance(x_train, x_cal)
                distance_ood = nearest_distance(x_train, x_ood)
                scores = {
                    "ensemble_std": (std_cal, std_ood),
                    "descriptor_distance": (distance_cal, distance_ood),
                    "equal_rank_hybrid": (
                        0.5 * calibration_ecdf(std_cal, std_cal)
                        + 0.5 * calibration_ecdf(distance_cal, distance_cal),
                        0.5 * calibration_ecdf(std_cal, std_ood)
                        + 0.5 * calibration_ecdf(distance_cal, distance_ood),
                    ),
                }

                for policy, (score_cal, score_ood) in scores.items():
                    candidate_rows = select_frozen_threshold(
                        score_cal, error_cal, seed + sum(map(ord, policy))
                    )
                    valid = [x for x in candidate_rows if x[2] <= epsilon]
                    selected = valid[-1] if valid else None
                    if selected:
                        retained, threshold, calibration_ucb = selected
                        accepted = score_ood <= threshold
                    else:
                        retained, threshold, calibration_ucb = 0, np.nan, np.nan
                        accepted = np.zeros(len(ood), dtype=bool)
                    retained_mae = (
                        float(error_ood[accepted].mean()) if accepted.any() else np.nan
                    )
                    _, _, cal_aurc = risk_curve(score_cal, error_cal)
                    ood_cov_curve, ood_risk_curve, ood_aurc = risk_curve(score_ood, error_ood)
                    rank_corr = spearmanr(score_ood, error_ood).statistic
                    summary_rows.append(
                        {
                            "task": task,
                            "holdout_family": holdout,
                            "repeat": repeat,
                            "seed": seed,
                            "split_hash": split_hash,
                            "policy": policy,
                            "epsilon": epsilon,
                            "n_train": len(train),
                            "n_calibration": len(calibration),
                            "n_ood": len(ood),
                            "policy_constructed": selected is not None,
                            "threshold": threshold,
                            "calibration_coverage": retained / len(calibration),
                            "calibration_mae": (
                                float(error_cal[np.argsort(score_cal)[:retained]].mean())
                                if retained
                                else np.nan
                            ),
                            "calibration_mae_ucb95": calibration_ucb,
                            "ood_mae_all": float(error_ood.mean()),
                            "ood_coverage": float(accepted.mean()),
                            "ood_retained_mae": retained_mae,
                            "risk_violation": retained_mae - epsilon,
                            "ood_spearman": rank_corr,
                            "calibration_aurc": cal_aurc,
                            "ood_aurc": ood_aurc,
                        }
                    )
                    for point in np.linspace(0.1, 1.0, 10):
                        ix = max(0, math.ceil(point * len(ood_cov_curve)) - 1)
                        curve_rows.append(
                            {
                                "task": task,
                                "holdout_family": holdout,
                                "repeat": repeat,
                                "policy": policy,
                                "coverage": float(ood_cov_curve[ix]),
                                "ood_risk": float(ood_risk_curve[ix]),
                            }
                        )

                for partition, indices in (
                    ("train", train),
                    ("calibration", calibration),
                    ("ood", ood),
                ):
                    for row_id in frame.loc[indices, "row_id"]:
                        split_rows.append(
                            {
                                "task": task,
                                "holdout_family": holdout,
                                "repeat": repeat,
                                "seed": seed,
                                "row_id": row_id,
                                "partition": partition,
                            }
                        )

    pd.DataFrame(summary_rows).to_csv(RESULTS / "phase_b_results.csv", index=False)
    pd.DataFrame(curve_rows).to_csv(RESULTS / "phase_b_risk_coverage.csv", index=False)
    pd.DataFrame(split_rows).to_csv(
        PROCESSED / "phase_b_split_manifest.csv.gz", index=False, compression="gzip"
    )


if __name__ == "__main__":
    run()
