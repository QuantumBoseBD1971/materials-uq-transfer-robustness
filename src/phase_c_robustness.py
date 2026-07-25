"""Phase-C robustness analysis for frozen materials reliability policies.

Adds element and composition-cluster shifts, group-bootstrap calibration
bounds, and a quantile-regression uncertainty score. OOD labels are used only
after policy thresholds are frozen.
"""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"

BASE_SEED = 20260724
N_REPEATS = 3
N_RF_MEMBERS = 5
N_BOOTSTRAPS = 200
MINIMUM_COVERAGE = 0.20
TASKS = {"expt_gap": 0.50, "log_kvrh": 0.15}


def parse_formula(formula: str) -> dict[str, float]:
    tokens = re.findall(r"[A-Z][a-z]?|\(|\)|\d+(?:\.\d+)?", formula)
    stack: list[dict[str, float]] = [{}]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "(":
            stack.append({})
        elif token == ")":
            group = stack.pop()
            multiplier = 1.0
            if i + 1 < len(tokens) and re.fullmatch(r"\d+(?:\.\d+)?", tokens[i + 1]):
                i += 1
                multiplier = float(tokens[i])
            for element, amount in group.items():
                stack[-1][element] = stack[-1].get(element, 0) + amount * multiplier
        elif re.fullmatch(r"[A-Z][a-z]?", token):
            amount = 1.0
            if i + 1 < len(tokens) and re.fullmatch(r"\d+(?:\.\d+)?", tokens[i + 1]):
                i += 1
                amount = float(tokens[i])
            stack[-1][token] = stack[-1].get(token, 0) + amount
        i += 1
    total = sum(stack[0].values())
    if len(stack) != 1 or total <= 0:
        raise ValueError(f"Could not parse formula: {formula}")
    return {el: amount / total for el, amount in stack[0].items()}


def make_features(formulas: pd.Series):
    parsed = [parse_formula(x) for x in formulas]
    elements = sorted({el for comp in parsed for el in comp})
    lookup = {el: i for i, el in enumerate(elements)}
    x = np.zeros((len(parsed), len(elements) + 2))
    for row, comp in enumerate(parsed):
        fractions = np.array(list(comp.values()))
        for el, fraction in comp.items():
            x[row, lookup[el]] = fraction
        x[row, -2] = len(comp)
        x[row, -1] = -(fractions * np.log(fractions)).sum()
    groups = [
        hashlib.sha256(np.round(row[:-2], 12).tobytes()).hexdigest()[:16] for row in x
    ]
    return x, parsed, groups


def grouped_calibration(frame, familiar_idx, seed):
    rng = np.random.default_rng(seed)
    groups = frame.loc[familiar_idx, "composition_group"].drop_duplicates().to_numpy()
    rng.shuffle(groups)
    n_cal = max(1, round(0.20 * len(groups)))
    cal_groups = set(groups[:n_cal])
    calibration = familiar_idx[
        frame.loc[familiar_idx, "composition_group"].isin(cal_groups).to_numpy()
    ]
    training = familiar_idx[
        ~frame.loc[familiar_idx, "composition_group"].isin(cal_groups).to_numpy()
    ]
    return training, calibration


def group_bootstrap_mae_ucb(errors, groups, rng):
    unique_groups = np.unique(groups)
    group_errors = {g: errors[groups == g] for g in unique_groups}
    means = np.empty(N_BOOTSTRAPS)
    for b in range(N_BOOTSTRAPS):
        sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        means[b] = np.concatenate([group_errors[g] for g in sampled]).mean()
    return float(np.quantile(means, 0.95))


def choose_threshold(scores, errors, groups, epsilon, seed):
    order = np.argsort(scores, kind="stable")
    candidates = np.unique(
        np.linspace(math.ceil(MINIMUM_COVERAGE * len(order)), len(order), 41).astype(int)
    )
    rng = np.random.default_rng(seed)
    valid = []
    for retained in candidates:
        chosen = order[:retained]
        ucb = group_bootstrap_mae_ucb(errors[chosen], groups[chosen], rng)
        if ucb <= epsilon:
            valid.append((retained, float(scores[order[retained - 1]]), ucb))
    return valid[-1] if valid else None


def rf_predictions(x_train, y_train, x_cal, x_ood, seed):
    rng = np.random.default_rng(seed)
    cal, ood = [], []
    for member in range(N_RF_MEMBERS):
        sample = rng.integers(0, len(y_train), len(y_train))
        model = RandomForestRegressor(
            n_estimators=80,
            min_samples_leaf=2,
            max_features=0.7,
            n_jobs=-1,
            random_state=seed + member,
        ).fit(x_train[sample], y_train[sample])
        cal.append(model.predict(x_cal))
        ood.append(model.predict(x_ood))
    cal, ood = np.vstack(cal), np.vstack(ood)
    return cal.mean(0), cal.std(0, ddof=1), ood.mean(0), ood.std(0, ddof=1)


def quantile_predictions(x_train, y_train, x_cal, x_ood, seed):
    models = {}
    for quantile in (0.1, 0.5, 0.9):
        models[quantile] = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=quantile,
            max_iter=80,
            max_leaf_nodes=31,
            l2_regularization=1.0,
            random_state=seed,
        ).fit(x_train, y_train)
    cal = {q: m.predict(x_cal) for q, m in models.items()}
    ood = {q: m.predict(x_ood) for q, m in models.items()}
    return cal[0.5], cal[0.9] - cal[0.1], ood[0.5], ood[0.9] - ood[0.1]


def nearest_distance(x_train, query):
    return NearestNeighbors(n_neighbors=1).fit(x_train).kneighbors(query)[0][:, 0]


def ecdf(reference, values):
    ordered = np.sort(reference)
    return np.searchsorted(ordered, values, side="right") / len(ordered)


def make_shifts(frame, features, parsed, seed):
    shifts = []
    counts = {}
    for comp in parsed:
        for el in comp:
            counts[el] = counts.get(el, 0) + 1
    eligible = sorted(
        (el for el, count in counts.items() if 250 <= count <= 0.35 * len(frame)),
        key=lambda el: counts[el],
        reverse=True,
    )[:6]
    for el in eligible:
        ood = np.array([i for i, comp in enumerate(parsed) if el in comp], dtype=int)
        familiar = np.array([i for i, comp in enumerate(parsed) if el not in comp], dtype=int)
        if len(ood) >= 250 and len(familiar) >= 1000:
            shifts.append(("element", el, familiar, ood))

    scaled = StandardScaler().fit_transform(features)
    clusters = KMeans(n_clusters=4, n_init=10, random_state=seed).fit_predict(scaled)
    for cluster in range(4):
        ood = np.flatnonzero(clusters == cluster)
        familiar = np.flatnonzero(clusters != cluster)
        if len(ood) >= 250 and len(familiar) >= 1000:
            shifts.append(("cluster", f"C{cluster}", familiar, ood))
    return shifts


def run():
    RESULTS.mkdir(exist_ok=True)
    rows, manifests = [], []
    for task, epsilon in TASKS.items():
        frame = pd.read_csv(PROCESSED / f"{task}_phase_a.csv").reset_index(drop=True)
        features, parsed, groups = make_features(frame["formula"])
        frame["composition_group"] = groups
        shifts = make_shifts(frame, features, parsed, BASE_SEED)
        for shift_type, holdout, familiar, ood in shifts:
            for repeat in range(N_REPEATS):
                seed = BASE_SEED + repeat
                train, cal = grouped_calibration(frame, familiar, seed)
                scaler = StandardScaler().fit(features[train])
                x_train, x_cal, x_ood = (
                    scaler.transform(features[train]),
                    scaler.transform(features[cal]),
                    scaler.transform(features[ood]),
                )
                y_train = frame.loc[train, "target"].to_numpy()
                y_cal = frame.loc[cal, "target"].to_numpy()
                y_ood = frame.loc[ood, "target"].to_numpy()
                rf_cal, rf_u_cal, rf_ood, rf_u_ood = rf_predictions(
                    x_train, y_train, x_cal, x_ood, seed
                )
                q_cal, q_u_cal, q_ood, q_u_ood = quantile_predictions(
                    x_train, y_train, x_cal, x_ood, seed
                )
                d_cal, d_ood = nearest_distance(x_train, x_cal), nearest_distance(
                    x_train, x_ood
                )
                policies = {
                    "rf_ensemble_std": (rf_cal, rf_u_cal, rf_ood, rf_u_ood),
                    "quantile_width": (q_cal, q_u_cal, q_ood, q_u_ood),
                    "descriptor_distance": (rf_cal, d_cal, rf_ood, d_ood),
                    "rf_distance_hybrid": (
                        rf_cal,
                        0.5 * ecdf(rf_u_cal, rf_u_cal) + 0.5 * ecdf(d_cal, d_cal),
                        rf_ood,
                        0.5 * ecdf(rf_u_cal, rf_u_ood) + 0.5 * ecdf(d_cal, d_ood),
                    ),
                }
                cal_groups = frame.loc[cal, "composition_group"].to_numpy()
                for policy, (pred_cal, score_cal, pred_ood, score_ood) in policies.items():
                    error_cal = np.abs(y_cal - pred_cal)
                    error_ood = np.abs(y_ood - pred_ood)
                    selected = choose_threshold(
                        score_cal, error_cal, cal_groups, epsilon, seed + sum(map(ord, policy))
                    )
                    if selected:
                        retained, threshold, ucb = selected
                        accepted = score_ood <= threshold
                    else:
                        retained, threshold, ucb = 0, np.nan, np.nan
                        accepted = np.zeros(len(ood), dtype=bool)
                    retained_mae = error_ood[accepted].mean() if accepted.any() else np.nan
                    rows.append(
                        {
                            "task": task,
                            "shift_type": shift_type,
                            "holdout": holdout,
                            "repeat": repeat,
                            "policy": policy,
                            "epsilon": epsilon,
                            "n_train": len(train),
                            "n_calibration": len(cal),
                            "n_ood": len(ood),
                            "policy_constructed": selected is not None,
                            "calibration_coverage": retained / len(cal),
                            "calibration_ucb95": ucb,
                            "ood_coverage": accepted.mean(),
                            "ood_retained_mae": retained_mae,
                            "risk_violation": retained_mae - epsilon,
                            "ood_spearman": spearmanr(score_ood, error_ood).statistic,
                            "shift_median_distance": float(np.median(d_ood)),
                            "threshold": threshold,
                        }
                    )
                for partition, idx in (("train", train), ("calibration", cal), ("ood", ood)):
                    manifests.extend(
                        {
                            "task": task,
                            "shift_type": shift_type,
                            "holdout": holdout,
                            "repeat": repeat,
                            "row_id": row_id,
                            "partition": partition,
                        }
                        for row_id in frame.loc[idx, "row_id"]
                    )
    pd.DataFrame(rows).to_csv(RESULTS / "phase_c_results.csv", index=False)
    pd.DataFrame(manifests).to_csv(
        PROCESSED / "phase_c_split_manifest.csv.gz", index=False, compression="gzip"
    )


if __name__ == "__main__":
    run()
