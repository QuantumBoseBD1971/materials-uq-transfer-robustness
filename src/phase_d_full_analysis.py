"""Locked full robustness analysis for frozen materials reliability policies.

This analysis extends the outcome-visible Phase-C screen without changing its
shift definitions. It adds ten repeated grouped splits, tolerance sensitivity,
random/oracle/unfiltered controls, shift-severity diagnostics, and row-level
outputs for grouped bootstrap inference.
"""

from __future__ import annotations

import hashlib
import math
import os
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
N_REPEATS = 10
N_RF_MEMBERS = 5
TREES_PER_MEMBER = 50
N_CAL_BOOTSTRAPS = 300
MINIMUM_COVERAGE = 0.20
PRIMARY_EPSILON = {"expt_gap": 0.50, "log_kvrh": 0.15}
TOLERANCES = {
    "expt_gap": (0.30, 0.40, 0.50, 0.60, 0.70),
    "log_kvrh": (0.10, 0.125, 0.15, 0.175, 0.20),
}
WORKER_ID = int(os.environ.get("PHASE_D_WORKER_ID", "0"))
N_WORKERS = int(os.environ.get("PHASE_D_N_WORKERS", "1"))


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
                stack[-1][element] = stack[-1].get(element, 0.0) + amount * multiplier
        elif re.fullmatch(r"[A-Z][a-z]?", token):
            amount = 1.0
            if i + 1 < len(tokens) and re.fullmatch(r"\d+(?:\.\d+)?", tokens[i + 1]):
                i += 1
                amount = float(tokens[i])
            stack[-1][token] = stack[-1].get(token, 0.0) + amount
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
        fractions = np.asarray(list(comp.values()))
        for el, fraction in comp.items():
            x[row, lookup[el]] = fraction
        x[row, -2] = len(comp)
        x[row, -1] = -(fractions * np.log(fractions)).sum()
    groups = [
        hashlib.sha256(np.round(row[:-2], 12).tobytes()).hexdigest()[:16] for row in x
    ]
    return x, parsed, groups


def locked_shifts(frame, features, parsed):
    """Reproduce the Phase-C shift definitions without consulting outcomes."""
    shifts = []
    counts: dict[str, int] = {}
    for comp in parsed:
        for element in comp:
            counts[element] = counts.get(element, 0) + 1
    eligible = sorted(
        (el for el, count in counts.items() if 250 <= count <= 0.35 * len(frame)),
        key=lambda el: counts[el],
        reverse=True,
    )[:6]
    for element in eligible:
        ood = np.asarray([i for i, comp in enumerate(parsed) if element in comp])
        familiar = np.asarray([i for i, comp in enumerate(parsed) if element not in comp])
        if len(ood) >= 250 and len(familiar) >= 1000:
            shifts.append(("element", element, familiar, ood))

    scaled = StandardScaler().fit_transform(features)
    labels = KMeans(n_clusters=4, n_init=10, random_state=BASE_SEED).fit_predict(scaled)
    for cluster in range(4):
        ood = np.flatnonzero(labels == cluster)
        familiar = np.flatnonzero(labels != cluster)
        if len(ood) >= 250 and len(familiar) >= 1000:
            shifts.append(("cluster", f"C{cluster}", familiar, ood))
    return shifts


def grouped_calibration(frame, familiar, seed):
    rng = np.random.default_rng(seed)
    groups = frame.loc[familiar, "composition_group"].drop_duplicates().to_numpy()
    rng.shuffle(groups)
    n_cal = max(1, round(0.20 * len(groups)))
    cal_groups = set(groups[:n_cal])
    calibration = familiar[
        frame.loc[familiar, "composition_group"].isin(cal_groups).to_numpy()
    ]
    training = familiar[
        ~frame.loc[familiar, "composition_group"].isin(cal_groups).to_numpy()
    ]
    assert not set(frame.loc[training, "composition_group"]) & set(
        frame.loc[calibration, "composition_group"]
    )
    return training, calibration


def group_bootstrap_mae_ucb(errors, groups, rng):
    unique = np.unique(groups)
    by_group = {group: errors[groups == group] for group in unique}
    means = np.empty(N_CAL_BOOTSTRAPS)
    for b in range(N_CAL_BOOTSTRAPS):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        means[b] = np.concatenate([by_group[group] for group in sampled]).mean()
    return float(np.quantile(means, 0.95))


def threshold_candidates(scores, errors, groups, seed):
    order = np.argsort(scores, kind="stable")
    candidates = np.unique(
        np.linspace(math.ceil(MINIMUM_COVERAGE * len(order)), len(order), 41).astype(int)
    )
    rng = np.random.default_rng(seed)
    candidates_with_bounds = []
    for retained in candidates:
        chosen = order[:retained]
        ucb = group_bootstrap_mae_ucb(errors[chosen], groups[chosen], rng)
        candidates_with_bounds.append(
            (retained, float(scores[order[retained - 1]]), ucb)
        )
    return candidates_with_bounds


def rf_predictions(x_train, y_train, x_cal, x_ood, seed):
    rng = np.random.default_rng(seed)
    cal, ood = [], []
    for member in range(N_RF_MEMBERS):
        sample = rng.integers(0, len(y_train), len(y_train))
        model = RandomForestRegressor(
            n_estimators=TREES_PER_MEMBER,
            min_samples_leaf=2,
            max_features=0.7,
            n_jobs=1,
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
            max_iter=50,
            max_leaf_nodes=31,
            l2_regularization=1.0,
            random_state=seed,
        ).fit(x_train, y_train)
    cal = {q: model.predict(x_cal) for q, model in models.items()}
    ood = {q: model.predict(x_ood) for q, model in models.items()}
    return cal[0.5], cal[0.9] - cal[0.1], ood[0.5], ood[0.9] - ood[0.1]


def nearest_distance(x_train, query):
    return NearestNeighbors(n_neighbors=1).fit(x_train).kneighbors(query)[0][:, 0]


def ecdf(reference, values):
    ordered = np.sort(reference)
    return np.searchsorted(ordered, values, side="right") / len(ordered)


def risk_curve_metrics(scores, errors):
    order = np.argsort(scores, kind="stable")
    coverage = np.arange(1, len(order) + 1) / len(order)
    risk = np.cumsum(errors[order]) / np.arange(1, len(order) + 1)
    aurc = float(np.trapezoid(risk, coverage))
    oracle_order = np.argsort(errors, kind="stable")
    oracle_risk = np.cumsum(errors[oracle_order]) / np.arange(1, len(errors) + 1)
    oracle_aurc = float(np.trapezoid(oracle_risk, coverage))
    return aurc, aurc - oracle_aurc


def append_result(
    rows,
    *,
    task,
    shift_type,
    holdout,
    repeat,
    policy,
    epsilon,
    score_cal,
    score_ood,
    error_cal,
    error_ood,
    cal_groups,
    seed,
    severity,
    candidates,
):
    valid = [candidate for candidate in candidates if candidate[2] <= epsilon]
    selected = valid[-1] if valid else None
    if selected:
        retained, threshold, ucb = selected
        accepted = score_ood <= threshold
    else:
        retained, threshold, ucb = 0, np.nan, np.nan
        accepted = np.zeros(len(error_ood), dtype=bool)
    retained_mae = float(error_ood[accepted].mean()) if accepted.any() else np.nan
    aurc, excess_aurc = risk_curve_metrics(score_ood, error_ood)
    rows.append(
        {
            "task": task,
            "shift_type": shift_type,
            "holdout": holdout,
            "repeat": repeat,
            "seed": seed,
            "policy": policy,
            "epsilon": epsilon,
            "primary_tolerance": epsilon == PRIMARY_EPSILON[task],
            "policy_constructed": selected is not None,
            "calibration_coverage": retained / len(error_cal),
            "calibration_ucb95": ucb,
            "ood_coverage": float(accepted.mean()),
            "ood_retained_mae": retained_mae,
            "risk_violation": retained_mae - epsilon,
            "risk_breach": bool(retained_mae > epsilon) if accepted.any() else np.nan,
            "coverage_failure": bool(selected and accepted.mean() < MINIMUM_COVERAGE),
            "operational_failure": bool(
                selected and (not accepted.any() or accepted.mean() < MINIMUM_COVERAGE
                              or retained_mae > epsilon)
            ),
            "ood_spearman": float(spearmanr(score_ood, error_ood).statistic),
            "ood_aurc": aurc,
            "ood_excess_aurc": excess_aurc,
            **severity,
        }
    )
    return selected, accepted


def run():
    RESULTS.mkdir(exist_ok=True)
    rows, predictions, manifests = [], [], []
    for task in PRIMARY_EPSILON:
        frame = pd.read_csv(PROCESSED / f"{task}_phase_a.csv").reset_index(drop=True)
        frame = frame.drop_duplicates(subset=["formula", "target"], keep="first").reset_index(
            drop=True
        )
        assert frame["row_id"].is_unique
        features, parsed, groups = make_features(frame["formula"])
        frame["composition_group"] = groups
        for shift_type, holdout, familiar, ood in locked_shifts(frame, features, parsed):
            for repeat in range(N_REPEATS):
                if repeat % N_WORKERS != WORKER_ID:
                    continue
                seed = BASE_SEED + repeat
                train, cal = grouped_calibration(frame, familiar, seed)
                scaler = StandardScaler().fit(features[train])
                x_train, x_cal, x_ood = [
                    scaler.transform(features[idx]) for idx in (train, cal, ood)
                ]
                y_train, y_cal, y_ood = [
                    frame.loc[idx, "target"].to_numpy() for idx in (train, cal, ood)
                ]
                rf_cal, rf_u_cal, rf_ood, rf_u_ood = rf_predictions(
                    x_train, y_train, x_cal, x_ood, seed
                )
                q_cal, q_u_cal, q_ood, q_u_ood = quantile_predictions(
                    x_train, y_train, x_cal, x_ood, seed
                )
                d_cal = nearest_distance(x_train, x_cal)
                d_ood = nearest_distance(x_train, x_ood)
                train_nn = NearestNeighbors(n_neighbors=2).fit(x_train).kneighbors(x_train)[0][:, 1]
                novelty_cut = float(np.quantile(train_nn, 0.99))
                training_elements = set().union(*(set(parsed[index]) for index in train))
                severity = {
                    "shift_median_distance": float(np.median(d_ood)),
                    "shift_p90_distance": float(np.quantile(d_ood, 0.90)),
                    "fraction_beyond_train_p99": float(np.mean(d_ood > novelty_cut)),
                    "element_novelty_fraction": float(
                        np.mean(
                            [bool(set(parsed[index]) - training_elements) for index in ood]
                        )
                    ),
                }
                rng = np.random.default_rng(seed + 991)
                random_cal, random_ood = rng.random(len(cal)), rng.random(len(ood))
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
                    "random_ranking": (rf_cal, random_cal, rf_ood, random_ood),
                    "oracle_error": (
                        rf_cal,
                        np.abs(y_cal - rf_cal),
                        rf_ood,
                        np.abs(y_ood - rf_ood),
                    ),
                }
                cal_groups = frame.loc[cal, "composition_group"].to_numpy()
                primary_decisions = {}
                for policy, (pred_cal, score_cal, pred_ood, score_ood) in policies.items():
                    error_cal = np.abs(y_cal - pred_cal)
                    error_ood = np.abs(y_ood - pred_ood)
                    candidates = threshold_candidates(
                        score_cal,
                        error_cal,
                        cal_groups,
                        seed + sum(map(ord, policy)),
                    )
                    for epsilon in TOLERANCES[task]:
                        selected, accepted = append_result(
                            rows,
                            task=task,
                            shift_type=shift_type,
                            holdout=holdout,
                            repeat=repeat,
                            policy=policy,
                            epsilon=epsilon,
                            score_cal=score_cal,
                            score_ood=score_ood,
                            error_cal=error_cal,
                            error_ood=error_ood,
                            cal_groups=cal_groups,
                            seed=seed,
                            severity=severity,
                            candidates=candidates,
                        )
                        if epsilon == PRIMARY_EPSILON[task]:
                            primary_decisions[policy] = {
                                "threshold": selected[1] if selected else np.nan,
                                "accepted": accepted,
                                "score": score_ood,
                            }
                for idx, truth, pred, unc, dist in zip(
                    range(len(ood)), y_ood, rf_ood, rf_u_ood, d_ood, strict=True
                ):
                    row_index = ood[idx]
                    predictions.append(
                        {
                            "task": task,
                            "shift_type": shift_type,
                            "holdout": holdout,
                            "repeat": repeat,
                            "seed": seed,
                            "row_id": frame.loc[row_index, "row_id"],
                            "composition_group": frame.loc[
                                row_index, "composition_group"
                            ],
                            "target": truth,
                            "prediction": pred,
                            "absolute_error": abs(truth - pred),
                            "ensemble_std": unc,
                            "quantile_prediction": q_ood[idx],
                            "quantile_width": q_u_ood[idx],
                            "descriptor_distance": dist,
                            "hybrid_score": policies["rf_distance_hybrid"][3][idx],
                            "accept_rf_ensemble_std": primary_decisions[
                                "rf_ensemble_std"
                            ]["accepted"][idx],
                            "accept_quantile_width": primary_decisions[
                                "quantile_width"
                            ]["accepted"][idx],
                            "accept_descriptor_distance": primary_decisions[
                                "descriptor_distance"
                            ]["accepted"][idx],
                            "accept_rf_distance_hybrid": primary_decisions[
                                "rf_distance_hybrid"
                            ]["accepted"][idx],
                        }
                    )
                for partition, indices in (("train", train), ("calibration", cal), ("ood", ood)):
                    manifests.extend(
                        {
                            "task": task,
                            "shift_type": shift_type,
                            "holdout": holdout,
                            "repeat": repeat,
                            "seed": seed,
                            "row_id": row_id,
                            "partition": partition,
                        }
                        for row_id in frame.loc[indices, "row_id"]
                    )
                print(task, shift_type, holdout, repeat, flush=True)
    suffix = f"_part{WORKER_ID}" if N_WORKERS > 1 else ""
    pd.DataFrame(rows).to_csv(RESULTS / f"phase_d_results{suffix}.csv", index=False)
    pd.DataFrame(predictions).to_csv(
        RESULTS / f"phase_d_predictions{suffix}.csv.gz", index=False, compression="gzip"
    )
    pd.DataFrame(manifests).to_csv(
        PROCESSED / f"phase_d_split_manifest{suffix}.csv.gz",
        index=False,
        compression="gzip",
    )


if __name__ == "__main__":
    run()
