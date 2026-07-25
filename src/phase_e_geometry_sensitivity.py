"""Geometry-augmented sensitivity analysis for computed bulk modulus.

This is not a full crystal-graph model. It tests whether Phase-D conclusions
are merely an artefact of omitting basic unit-cell geometry from the computed
bulk-modulus model.
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from phase_d_full_analysis import (
    BASE_SEED,
    MINIMUM_COVERAGE,
    PRIMARY_EPSILON,
    ecdf,
    grouped_calibration,
    locked_shifts,
    make_features,
    rf_predictions,
    threshold_candidates,
)

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
RAW = ROOT / "data" / "raw" / "matbench_log_kvrh.json.gz"
N_REPEATS = 5
WORKER_ID = int(os.environ.get("PHASE_E_WORKER_ID", "0"))
N_WORKERS = int(os.environ.get("PHASE_E_N_WORKERS", "1"))


def raw_geometry_features():
    with gzip.open(RAW, "rt") as handle:
        payload = json.load(handle)
    targets, features = [], []
    for structure, target in payload["data"]:
        lattice = structure["lattice"]
        lengths = np.asarray([lattice["a"], lattice["b"], lattice["c"]], dtype=float)
        angles = np.asarray(
            [lattice["alpha"], lattice["beta"], lattice["gamma"]], dtype=float
        )
        volume = float(lattice["volume"])
        n_sites = len(structure["sites"])
        features.append(
            [
                *lengths,
                *angles,
                volume,
                n_sites,
                volume / n_sites,
                lengths.max() / lengths.min(),
                np.abs(angles - 90.0).mean(),
            ]
        )
        targets.append(target)
    return np.asarray(features), np.asarray(targets)


def nearest_distance(x_train, query):
    return NearestNeighbors(n_neighbors=1).fit(x_train).kneighbors(query)[0][:, 0]


def run():
    original = pd.read_csv(PROCESSED / "log_kvrh_phase_a.csv").reset_index(drop=True)
    geometry, raw_targets = raw_geometry_features()
    assert len(original) == len(geometry)
    assert np.allclose(original["target"].to_numpy(), raw_targets)
    keep = ~original.duplicated(subset=["formula", "target"], keep="first")
    frame = original.loc[keep].reset_index(drop=True)
    geometry = geometry[keep.to_numpy()]
    composition, parsed, groups = make_features(frame["formula"])
    frame["composition_group"] = groups
    combined = np.column_stack([composition, geometry])
    epsilon = PRIMARY_EPSILON["log_kvrh"]
    rows = []
    for shift_type, holdout, familiar, ood in locked_shifts(frame, composition, parsed):
        for repeat in range(N_REPEATS):
            if repeat % N_WORKERS != WORKER_ID:
                continue
            seed = BASE_SEED + repeat
            train, cal = grouped_calibration(frame, familiar, seed)
            scaler = StandardScaler().fit(combined[train])
            x_train, x_cal, x_ood = [
                scaler.transform(combined[idx]) for idx in (train, cal, ood)
            ]
            y_train, y_cal, y_ood = [
                frame.loc[idx, "target"].to_numpy() for idx in (train, cal, ood)
            ]
            pred_cal, unc_cal, pred_ood, unc_ood = rf_predictions(
                x_train, y_train, x_cal, x_ood, seed
            )
            distance_cal = nearest_distance(x_train, x_cal)
            distance_ood = nearest_distance(x_train, x_ood)
            policies = {
                "geometry_rf_ensemble_std": (unc_cal, unc_ood),
                "geometry_descriptor_distance": (distance_cal, distance_ood),
                "geometry_rf_distance_hybrid": (
                    0.5 * ecdf(unc_cal, unc_cal) + 0.5 * ecdf(distance_cal, distance_cal),
                    0.5 * ecdf(unc_cal, unc_ood) + 0.5 * ecdf(distance_cal, distance_ood),
                ),
            }
            error_cal = np.abs(y_cal - pred_cal)
            error_ood = np.abs(y_ood - pred_ood)
            cal_groups = frame.loc[cal, "composition_group"].to_numpy()
            for policy, (score_cal, score_ood) in policies.items():
                candidates = threshold_candidates(
                    score_cal,
                    error_cal,
                    cal_groups,
                    seed + sum(map(ord, policy)),
                )
                valid = [candidate for candidate in candidates if candidate[2] <= epsilon]
                selected = valid[-1] if valid else None
                if selected:
                    retained, threshold, ucb = selected
                    accepted = score_ood <= threshold
                else:
                    retained, threshold, ucb = 0, np.nan, np.nan
                    accepted = np.zeros(len(ood), dtype=bool)
                retained_mae = error_ood[accepted].mean() if accepted.any() else np.nan
                rows.append(
                    {
                        "task": "log_kvrh",
                        "shift_type": shift_type,
                        "holdout": holdout,
                        "repeat": repeat,
                        "policy": policy,
                        "epsilon": epsilon,
                        "policy_constructed": selected is not None,
                        "calibration_coverage": retained / len(cal),
                        "calibration_ucb95": ucb,
                        "ood_coverage": accepted.mean(),
                        "ood_retained_mae": retained_mae,
                        "risk_violation": retained_mae - epsilon,
                        "risk_breach": bool(retained_mae > epsilon)
                        if accepted.any()
                        else np.nan,
                        "coverage_failure": bool(
                            selected and accepted.mean() < MINIMUM_COVERAGE
                        ),
                        "operational_failure": bool(
                            selected
                            and (
                                not accepted.any()
                                or accepted.mean() < MINIMUM_COVERAGE
                                or retained_mae > epsilon
                            )
                        ),
                    }
                )
            print(shift_type, holdout, repeat, flush=True)
    suffix = f"_part{WORKER_ID}" if N_WORKERS > 1 else ""
    pd.DataFrame(rows).to_csv(
        RESULTS / f"phase_e_geometry_results{suffix}.csv", index=False
    )


if __name__ == "__main__":
    run()
