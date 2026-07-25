"""Summarise the paired geometry-augmented bulk-modulus sensitivity analysis."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

POLICY_MAP = {
    "geometry_rf_ensemble_std": "rf_ensemble_std",
    "geometry_descriptor_distance": "descriptor_distance",
    "geometry_rf_distance_hybrid": "rf_distance_hybrid",
}


def proportion_ci(values, rng, n_boot=10_000):
    """Holdout-cluster bootstrap interval for a binary outcome."""
    block_rates = (
        values.groupby(["shift_type", "holdout"])["operational_failure"]
        .mean()
        .to_numpy()
    )
    sampled = rng.choice(
        block_rates, size=(n_boot, len(block_rates)), replace=True
    ).mean(axis=1)
    return np.quantile(sampled, [0.025, 0.975])


def main():
    geometry = pd.concat(
        [
            pd.read_csv(RESULTS / "phase_e_geometry_results_part0.csv"),
            pd.read_csv(RESULTS / "phase_e_geometry_results_part1.csv"),
        ],
        ignore_index=True,
    ).sort_values(["shift_type", "holdout", "repeat", "policy"])
    geometry.to_csv(RESULTS / "phase_e_geometry_results.csv", index=False)

    baseline = pd.read_csv(RESULTS / "phase_d_results.csv")
    baseline = baseline[
        (baseline["task"] == "log_kvrh")
        & (baseline["epsilon"] == 0.15)
        & (baseline["repeat"] < 5)
        & (baseline["policy"].isin(POLICY_MAP.values()))
    ].copy()

    paired = geometry.copy()
    paired["baseline_policy"] = paired["policy"].map(POLICY_MAP)
    paired = paired.merge(
        baseline,
        left_on=["task", "shift_type", "holdout", "repeat", "baseline_policy"],
        right_on=["task", "shift_type", "holdout", "repeat", "policy"],
        suffixes=("_geometry", "_composition"),
        validate="one_to_one",
    )
    for metric in [
        "policy_constructed",
        "ood_coverage",
        "ood_retained_mae",
        "risk_violation",
        "operational_failure",
    ]:
        paired[f"delta_{metric}"] = (
            paired[f"{metric}_geometry"].astype(float)
            - paired[f"{metric}_composition"].astype(float)
        )
    paired.to_csv(RESULTS / "phase_e_paired_comparison.csv", index=False)

    rows = []
    rng = np.random.default_rng(20260724)
    for representation, frame in [
        ("composition_only", baseline),
        ("composition_plus_geometry", geometry),
    ]:
        constructed = frame[frame["policy_constructed"].astype(bool)]
        evaluable = constructed[constructed["ood_retained_mae"].notna()]
        lo, hi = proportion_ci(constructed, rng)
        rows.append(
            {
                "representation": representation,
                "attempted": len(frame),
                "constructed": len(constructed),
                "evaluable": len(evaluable),
                "risk_breaches": int(evaluable["risk_breach"].fillna(False).sum()),
                "risk_breach_rate": evaluable["risk_breach"].mean(),
                "operational_failures": int(constructed["operational_failure"].sum()),
                "operational_failure_rate": constructed[
                    "operational_failure"
                ].mean(),
                "operational_failure_ci95_low": lo,
                "operational_failure_ci95_high": hi,
                "median_ood_coverage": constructed["ood_coverage"].median(),
                "median_ood_retained_mae": evaluable["ood_retained_mae"].median(),
            }
        )
    summary = pd.DataFrame(rows)
    summary.to_csv(RESULTS / "phase_e_summary.csv", index=False)

    policy_summary = (
        geometry.groupby("policy", as_index=False)
        .agg(
            attempted=("policy_constructed", "size"),
            constructed=("policy_constructed", "sum"),
            operational_failure_rate=("operational_failure", "mean"),
            median_ood_coverage=("ood_coverage", "median"),
            median_ood_retained_mae=("ood_retained_mae", "median"),
        )
    )
    policy_summary.to_csv(RESULTS / "phase_e_policy_summary.csv", index=False)

    plot = pd.DataFrame(
        {
            "Composition only": baseline.groupby("shift_type")[
                "operational_failure"
            ].mean(),
            "Composition + geometry": geometry.groupby("shift_type")[
                "operational_failure"
            ].mean(),
        }
    )
    ax = plot.plot(kind="bar", figsize=(7.2, 4.6), color=["#6B7280", "#2563EB"])
    ax.set_ylabel("Operational failure rate")
    ax.set_xlabel("Shift type")
    ax.set_ylim(0, 1)
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    plt.xticks(rotation=0)
    plt.tight_layout()
    FIGURES.mkdir(exist_ok=True)
    plt.savefig(FIGURES / "phase_e_geometry_comparison.png", dpi=300)
    plt.savefig(FIGURES / "phase_e_geometry_comparison.pdf")
    plt.close()

    print(summary.to_string(index=False))
    print("\nPaired mean changes (geometry minus composition):")
    print(
        paired[
            [
                "delta_ood_coverage",
                "delta_ood_retained_mae",
                "delta_operational_failure",
            ]
        ]
        .mean()
        .to_string()
    )


if __name__ == "__main__":
    main()
