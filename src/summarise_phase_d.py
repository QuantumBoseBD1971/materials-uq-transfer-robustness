"""Summarise Phase-D results and create manuscript figures/tables."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
PROCESSED = ROOT / "data" / "processed"
DEPLOYABLE = [
    "rf_ensemble_std",
    "quantile_width",
    "descriptor_distance",
    "rf_distance_hybrid",
]
LABELS = {
    "rf_ensemble_std": "RF ensemble",
    "quantile_width": "Quantile width",
    "descriptor_distance": "Descriptor distance",
    "rf_distance_hybrid": "Hybrid",
    "random_ranking": "Random",
    "oracle_error": "Oracle",
}
TASK_LABELS = {
    "expt_gap": "Experimental band gap",
    "log_kvrh": "Computed bulk modulus",
}


def combine_parts():
    for stem, directory, suffix in (
        ("phase_d_results", RESULTS, ".csv"),
        ("phase_d_predictions", RESULTS, ".csv.gz"),
        ("phase_d_split_manifest", PROCESSED, ".csv.gz"),
    ):
        parts = sorted(directory.glob(f"{stem}_part*{suffix}"))
        if not parts:
            continue
        combined = pd.concat([pd.read_csv(path) for path in parts], ignore_index=True)
        output = directory / f"{stem}{suffix}"
        combined.to_csv(output, index=False, compression="gzip" if suffix.endswith("gz") else None)


def clustered_rate_ci(frame, column, n_boot=3000, seed=20260724):
    """Bootstrap complete holdout blocks, preserving repeats and policies."""
    rng = np.random.default_rng(seed)
    blocks = [
        block[column].astype(float).to_numpy()
        for _, block in frame.groupby(["task", "shift_type", "holdout"], sort=True)
    ]
    estimate = float(np.concatenate(blocks).mean())
    draws = np.empty(n_boot)
    for i in range(n_boot):
        sampled = rng.integers(0, len(blocks), len(blocks))
        draws[i] = np.concatenate([blocks[j] for j in sampled]).mean()
    return estimate, float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def transfer_group_bootstrap(predictions, results, n_boot=200, seed=20260724):
    rng = np.random.default_rng(seed)
    output = []
    primary = results[
        results["primary_tolerance"]
        & results["policy"].isin(DEPLOYABLE)
        & results["policy_constructed"]
    ]
    for key, result in primary.groupby(
        ["task", "shift_type", "holdout", "repeat", "policy"], sort=True
    ):
        task, shift_type, holdout, repeat, policy = key
        row = result.iloc[0]
        subset = predictions[
            (predictions["task"] == task)
            & (predictions["shift_type"] == shift_type)
            & (predictions["holdout"] == holdout)
            & (predictions["repeat"] == repeat)
        ].copy()
        accept_col = f"accept_{policy}"
        retained = subset[subset[accept_col].astype(bool)].copy()
        if retained.empty:
            continue
        error_col = "absolute_error"
        if policy == "quantile_width":
            retained["quantile_absolute_error"] = (
                retained["target"] - retained["quantile_prediction"]
            ).abs()
            error_col = "quantile_absolute_error"
        groups = [
            group[error_col].to_numpy()
            for _, group in retained.groupby("composition_group", sort=False)
        ]
        draws = np.empty(n_boot)
        for i in range(n_boot):
            sampled = rng.integers(0, len(groups), len(groups))
            draws[i] = np.concatenate([groups[j] for j in sampled]).mean()
        output.append(
            {
                "task": task,
                "shift_type": shift_type,
                "holdout": holdout,
                "repeat": repeat,
                "policy": policy,
                "epsilon": row["epsilon"],
                "retained_mae": retained[error_col].mean(),
                "mae_ci_low": np.quantile(draws, 0.025),
                "mae_ci_high": np.quantile(draws, 0.975),
                "violation_ci_low": np.quantile(draws, 0.025) - row["epsilon"],
                "violation_ci_high": np.quantile(draws, 0.975) - row["epsilon"],
                "n_retained": len(retained),
                "n_groups_retained": len(groups),
            }
        )
    return pd.DataFrame(output)


def aggregate_tables(results):
    primary = results[results["primary_tolerance"]].copy()
    primary["risk_evaluable"] = primary["ood_retained_mae"].notna()
    deployable = primary[primary["policy"].isin(DEPLOYABLE)]
    rows = []
    for keys, group in deployable.groupby(["task", "shift_type", "policy"], sort=True):
        constructed = group[group["policy_constructed"]]
        evaluable = constructed[constructed["risk_evaluable"]]
        rows.append(
            {
                "task": keys[0],
                "shift_type": keys[1],
                "policy": keys[2],
                "attempted": len(group),
                "constructed": int(group["policy_constructed"].sum()),
                "risk_evaluable": len(evaluable),
                "risk_breaches": int(evaluable["risk_breach"].sum()),
                "operational_failures": int(constructed["operational_failure"].sum()),
                "operational_failure_rate": constructed["operational_failure"].mean(),
                "median_ood_coverage": constructed["ood_coverage"].median(),
                "median_risk_violation": evaluable["risk_violation"].median(),
                "median_spearman": evaluable["ood_spearman"].median(),
                "median_excess_aurc": evaluable["ood_excess_aurc"].median(),
            }
        )
    aggregate = pd.DataFrame(rows)
    aggregate.to_csv(RESULTS / "phase_d_primary_aggregate.csv", index=False)

    sensitivity = (
        results[
            results["policy"].isin(DEPLOYABLE) & results["policy_constructed"]
        ]
        .groupby(["task", "epsilon", "policy"], as_index=False)
        .agg(
            constructed=("policy_constructed", "size"),
            operational_failure_rate=("operational_failure", "mean"),
            median_coverage=("ood_coverage", "median"),
            median_violation=("risk_violation", "median"),
        )
    )
    sensitivity.to_csv(RESULTS / "phase_d_tolerance_sensitivity.csv", index=False)

    controls = (
        primary[primary["policy"].isin(["random_ranking", "oracle_error"] + DEPLOYABLE)]
        .groupby(["task", "shift_type", "policy"], as_index=False)
        .agg(
            median_aurc=("ood_aurc", "median"),
            median_excess_aurc=("ood_excess_aurc", "median"),
            median_spearman=("ood_spearman", "median"),
            median_coverage=("ood_coverage", "median"),
        )
    )
    controls.to_csv(RESULTS / "phase_d_control_comparison.csv", index=False)
    return aggregate, sensitivity, controls


def make_figures(aggregate, sensitivity, results):
    FIGURES.mkdir(exist_ok=True)
    colors = {
        "rf_ensemble_std": "#31688E",
        "quantile_width": "#35B779",
        "descriptor_distance": "#FDE725",
        "rf_distance_hybrid": "#443A83",
    }

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
    for axis, task in zip(axes, TASK_LABELS, strict=True):
        subset = aggregate[aggregate["task"] == task]
        labels = ["Element", "Cluster"]
        x = np.arange(2)
        width = 0.19
        for i, policy in enumerate(DEPLOYABLE):
            values = [
                subset[
                    (subset["shift_type"] == shift.lower()) & (subset["policy"] == policy)
                ]["operational_failure_rate"].iloc[0]
                for shift in labels
            ]
            axis.bar(
                x + (i - 1.5) * width,
                np.asarray(values) * 100,
                width,
                color=colors[policy],
                label=LABELS[policy],
            )
        axis.set_title(TASK_LABELS[task])
        axis.set_xticks(x, labels)
        axis.set_ylim(0, 105)
        axis.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Operational failure rate (%)")
    axes[1].legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES / "phase_d_operational_failures.png", dpi=300)
    fig.savefig(FIGURES / "phase_d_operational_failures.svg")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    for axis, task in zip(axes, TASK_LABELS, strict=True):
        subset = sensitivity[sensitivity["task"] == task]
        for policy in DEPLOYABLE:
            line = subset[subset["policy"] == policy].sort_values("epsilon")
            axis.plot(
                line["epsilon"],
                line["operational_failure_rate"] * 100,
                marker="o",
                color=colors[policy],
                label=LABELS[policy],
            )
        axis.set_title(TASK_LABELS[task])
        axis.set_xlabel("Operating error tolerance")
        axis.set_ylim(0, 105)
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Operational failure rate (%)")
    axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "phase_d_tolerance_sensitivity.png", dpi=300)
    fig.savefig(FIGURES / "phase_d_tolerance_sensitivity.svg")
    plt.close(fig)

    primary = results[
        results["primary_tolerance"]
        & results["policy"].isin(DEPLOYABLE)
        & results["policy_constructed"]
        & results["risk_violation"].notna()
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    for axis, task in zip(axes, TASK_LABELS, strict=True):
        subset = primary[primary["task"] == task]
        for policy in DEPLOYABLE:
            points = subset[subset["policy"] == policy]
            axis.scatter(
                points["fraction_beyond_train_p99"],
                points["risk_violation"],
                s=18,
                alpha=0.55,
                color=colors[policy],
                label=LABELS[policy],
            )
        axis.axhline(0, color="black", lw=1)
        axis.set_title(TASK_LABELS[task])
        axis.set_xlabel("OOD fraction beyond training 99th percentile")
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("Retained MAE minus tolerance")
    axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "phase_d_shift_severity.png", dpi=300)
    fig.savefig(FIGURES / "phase_d_shift_severity.svg")
    plt.close(fig)


def write_report(results, aggregate, transfer_ci):
    primary = results[
        results["primary_tolerance"] & results["policy"].isin(DEPLOYABLE)
    ]
    constructed = primary[primary["policy_constructed"]]
    evaluable = constructed[constructed["ood_retained_mae"].notna()]
    rate, low, high = clustered_rate_ci(constructed, "operational_failure")
    robust_breaches = int((transfer_ci["violation_ci_low"] > 0).sum())
    text = f"""# Phase-D Full Robustness Analysis

**Run date:** 24 July 2026  
**Status:** locked extension of outcome-visible development analyses; not
preregistered confirmation.

## Design

The Phase-C shift definitions were held fixed. The analysis used ten grouped
training/calibration repetitions, five independently bootstrapped
random-forest members, quantile regression, descriptor distance, an equal-rank
hybrid, five operating tolerances per task, and random/oracle controls.
Equivalent compositions were kept within one partition.

## Primary operating targets

- experimental band gap: retained-set MAE <= 0.50 eV;
- computed log10 bulk modulus: retained-set MAE <= 0.15.

These are scenario-based operating targets, not universal scientific safety
limits. Conclusions were checked across five targets per task.

## Primary result

- attempted deployable transfers: {len(primary):,};
- policies constructible on familiar calibration data: {len(constructed):,};
- transfers accepting at least one OOD material: {len(evaluable):,};
- absolute-risk breaches: {int(evaluable['risk_breach'].sum()):,} of {len(evaluable):,}
  ({evaluable['risk_breach'].mean():.1%});
- operational failures (risk breach or OOD coverage below 20%):
  {int(constructed['operational_failure'].sum()):,} of {len(constructed):,}
  ({rate:.1%}; holdout-cluster bootstrap 95% interval {low:.1%}–{high:.1%});
- transfers whose composition-group bootstrap interval lay wholly above the
  target: {robust_breaches:,} of {len(transfer_ci):,}.

## Interpretation boundary

The study shows that a policy satisfying an ID calibration-risk bound often
does not retain the same absolute error target after chemistry shift. It does
not show that every UQ method, model class, representation, or materials task
must fail. The oracle control is nondeployable and is used only to determine
whether useful low-error subsets exist in principle.
"""
    (ROOT / "phase_d_full_analysis_report.md").write_text(text)


def main():
    combine_parts()
    results = pd.read_csv(RESULTS / "phase_d_results.csv")
    predictions = pd.read_csv(RESULTS / "phase_d_predictions.csv.gz")
    for column in (
        "primary_tolerance",
        "policy_constructed",
        "risk_breach",
        "coverage_failure",
        "operational_failure",
    ):
        if column in results:
            results[column] = results[column].astype("boolean")
    aggregate, sensitivity, _ = aggregate_tables(results)
    transfer_ci = transfer_group_bootstrap(predictions, results)
    transfer_ci.to_csv(RESULTS / "phase_d_transfer_bootstrap_ci.csv", index=False)
    make_figures(aggregate, sensitivity, results)
    write_report(results, aggregate, transfer_ci)


if __name__ == "__main__":
    main()
