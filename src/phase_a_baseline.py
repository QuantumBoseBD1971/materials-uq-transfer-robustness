"""Phase-A feasibility benchmark for frozen materials-model abstention policies."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pymatgen.core import Composition, Structure
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
SEED = 20260724


def load_json_gz(name: str) -> dict:
    with gzip.open(RAW / name, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def structure_formula(payload: dict) -> str:
    return Structure.from_dict(payload).composition.reduced_formula


def load_task(task: str) -> pd.DataFrame:
    if task == "expt_gap":
        raw = load_json_gz("matbench_expt_gap.json.gz")
        rows = [(formula, target) for formula, target in raw["data"]]
        target_name = "gap_eV"
    elif task == "log_kvrh":
        raw = load_json_gz("matbench_log_kvrh.json.gz")
        rows = [(structure_formula(structure), target) for structure, target in raw["data"]]
        target_name = "log10_K_VRH"
    else:
        raise ValueError(task)
    frame = pd.DataFrame(rows, columns=["formula", "target"])
    frame["task"] = task
    frame["target_name"] = target_name
    return frame


def composition_features(formula: str) -> tuple[dict[str, float], int, float]:
    comp = Composition(formula).fractional_composition
    fractions = {str(el): float(amount) for el, amount in comp.items()}
    values = np.array(list(fractions.values()))
    entropy = float(-(values * np.log(values)).sum())
    return fractions, len(fractions), entropy


def chemistry_family(elements: set[str]) -> str:
    # Mutually exclusive, prespecified broad chemistry labels.
    if "O" in elements:
        return "oxide"
    if elements & {"F", "Cl", "Br", "I"}:
        return "halide"
    if elements & {"S", "Se", "Te"}:
        return "chalcogenide"
    if elements & {"N", "P", "As", "Sb", "Bi"}:
        return "pnictide"
    return "other"


def featurize(frame: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    parsed = [composition_features(x) for x in frame["formula"]]
    elements = sorted({el for fractions, _, _ in parsed for el in fractions})
    matrix = np.zeros((len(frame), len(elements) + 2), dtype=float)
    lookup = {el: index for index, el in enumerate(elements)}
    families = []
    for row, (fractions, count, entropy) in enumerate(parsed):
        for el, fraction in fractions.items():
            matrix[row, lookup[el]] = fraction
        matrix[row, -2:] = count, entropy
        families.append(chemistry_family(set(fractions)))
    output = frame.copy()
    output["family"] = families
    output["row_id"] = [
        hashlib.sha256(f"{task}|{formula}|{target:.12g}".encode()).hexdigest()[:16]
        for task, formula, target in output[["task", "formula", "target"]].itertuples(index=False)
    ]
    return output, matrix


def split_indices(families: np.ndarray, holdout: str, seed: int):
    rng = np.random.default_rng(seed)
    ood = np.flatnonzero(families == holdout)
    familiar = np.flatnonzero(families != holdout)
    rng.shuffle(familiar)
    n_cal = max(200, round(0.2 * len(familiar)))
    return familiar[n_cal:], familiar[:n_cal], ood


def rf_uncertainty(model: RandomForestRegressor, features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    predictions = np.vstack([tree.predict(features) for tree in model.estimators_])
    return predictions.mean(axis=0), predictions.std(axis=0)


def distance_score(train: np.ndarray, query: np.ndarray) -> np.ndarray:
    nearest = NearestNeighbors(n_neighbors=1).fit(train)
    return nearest.kneighbors(query, return_distance=True)[0][:, 0]


def frozen_threshold(score: np.ndarray, errors: np.ndarray, epsilon: float, minimum_coverage=0.2):
    order = np.argsort(score)
    cumulative_mae = np.cumsum(errors[order]) / np.arange(1, len(order) + 1)
    eligible = np.flatnonzero(
        (cumulative_mae <= epsilon)
        & (np.arange(1, len(order) + 1) >= math.ceil(minimum_coverage * len(order)))
    )
    if not len(eligible):
        return None, 0.0, np.nan
    last = eligible[-1]
    return float(score[order[last]]), float((last + 1) / len(order)), float(cumulative_mae[last])


def evaluate_policy(
    score_cal: np.ndarray,
    error_cal: np.ndarray,
    score_ood: np.ndarray,
    error_ood: np.ndarray,
    epsilon: float,
) -> dict:
    threshold, calibration_coverage, calibration_mae = frozen_threshold(score_cal, error_cal, epsilon)
    if threshold is None:
        return {
            "policy_constructed": False,
            "threshold": np.nan,
            "calibration_coverage": 0.0,
            "calibration_mae": np.nan,
            "ood_coverage": 0.0,
            "ood_retained_mae": np.nan,
            "risk_violation": np.nan,
        }
    accepted = score_ood <= threshold
    ood_mae = float(error_ood[accepted].mean()) if accepted.any() else np.nan
    return {
        "policy_constructed": True,
        "threshold": threshold,
        "calibration_coverage": calibration_coverage,
        "calibration_mae": calibration_mae,
        "ood_coverage": float(accepted.mean()),
        "ood_retained_mae": ood_mae,
        "risk_violation": ood_mae - epsilon if np.isfinite(ood_mae) else np.nan,
    }


def run_task(task: str, epsilon: float) -> tuple[list[dict], pd.DataFrame]:
    frame, features = featurize(load_task(task))
    family_counts = frame["family"].value_counts()
    eligible = family_counts[family_counts >= 250].index.tolist()
    rows: list[dict] = []
    manifests = []

    for fold, holdout in enumerate(eligible):
        train_idx, cal_idx, ood_idx = split_indices(frame["family"].to_numpy(), holdout, SEED + fold)
        scaler = StandardScaler().fit(features[train_idx])
        x_train, x_cal, x_ood = (
            scaler.transform(features[idx]) for idx in (train_idx, cal_idx, ood_idx)
        )
        y_train, y_cal, y_ood = (
            frame["target"].to_numpy()[idx] for idx in (train_idx, cal_idx, ood_idx)
        )

        ridge = Ridge(alpha=1.0).fit(x_train, y_train)
        ridge_ood = ridge.predict(x_ood)
        rows.append(
            {
                "task": task,
                "holdout_family": holdout,
                "model": "ridge",
                "policy": "none",
                "n_train": len(train_idx),
                "n_calibration": len(cal_idx),
                "n_ood": len(ood_idx),
                "epsilon": epsilon,
                "ood_mae_all": mean_absolute_error(y_ood, ridge_ood),
                "ood_rmse_all": root_mean_squared_error(y_ood, ridge_ood),
            }
        )

        forest = RandomForestRegressor(
            n_estimators=300,
            min_samples_leaf=2,
            max_features=0.7,
            n_jobs=-1,
            random_state=SEED,
        ).fit(x_train, y_train)
        pred_cal, uncertainty_cal = rf_uncertainty(forest, x_cal)
        pred_ood, uncertainty_ood = rf_uncertainty(forest, x_ood)
        error_cal, error_ood = np.abs(y_cal - pred_cal), np.abs(y_ood - pred_ood)
        distance_cal = distance_score(x_train, x_cal)
        distance_ood = distance_score(x_train, x_ood)

        # Rank-normalized hybrid, with calibration distribution frozen.
        def calibration_ecdf(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
            ordered = np.sort(reference)
            return np.searchsorted(ordered, values, side="right") / len(ordered)

        scores = {
            "ensemble_std": (uncertainty_cal, uncertainty_ood),
            "descriptor_distance": (distance_cal, distance_ood),
            "equal_rank_hybrid": (
                0.5 * calibration_ecdf(uncertainty_cal, uncertainty_cal)
                + 0.5 * calibration_ecdf(distance_cal, distance_cal),
                0.5 * calibration_ecdf(uncertainty_cal, uncertainty_ood)
                + 0.5 * calibration_ecdf(distance_cal, distance_ood),
            ),
        }
        for policy, (score_cal, score_ood) in scores.items():
            result = evaluate_policy(score_cal, error_cal, score_ood, error_ood, epsilon)
            rows.append(
                {
                    "task": task,
                    "holdout_family": holdout,
                    "model": "random_forest",
                    "policy": policy,
                    "n_train": len(train_idx),
                    "n_calibration": len(cal_idx),
                    "n_ood": len(ood_idx),
                    "epsilon": epsilon,
                    "ood_mae_all": float(error_ood.mean()),
                    "ood_rmse_all": root_mean_squared_error(y_ood, pred_ood),
                    **result,
                }
            )

        for label, indices in (("train", train_idx), ("calibration", cal_idx), ("ood", ood_idx)):
            part = frame.iloc[indices][["row_id", "formula", "target", "family"]].copy()
            part["task"] = task
            part["holdout_family"] = holdout
            part["partition"] = label
            manifests.append(part)

    processed = frame[["row_id", "task", "formula", "target_name", "target", "family"]]
    processed.to_csv(PROCESSED / f"{task}_phase_a.csv", index=False)
    return rows, pd.concat(manifests, ignore_index=True)


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    all_rows, all_manifests = [], []
    for task, epsilon in (("expt_gap", 0.5), ("log_kvrh", 0.15)):
        rows, manifest = run_task(task, epsilon)
        all_rows.extend(rows)
        all_manifests.append(manifest)
    results = pd.DataFrame(all_rows)
    results.to_csv(RESULTS / "phase_a_results.csv", index=False)
    pd.concat(all_manifests, ignore_index=True).to_csv(
        PROCESSED / "phase_a_split_manifest.csv", index=False
    )
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
