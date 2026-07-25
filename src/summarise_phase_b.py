"""Create manuscript-facing Phase-B summary tables and figures."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"


def main():
    FIGURES.mkdir(exist_ok=True)
    data = pd.read_csv(RESULTS / "phase_b_results.csv")
    constructed = data.loc[data["policy_constructed"]].copy()
    aggregate = (
        data.groupby(["task", "policy"])
        .agg(
            attempts=("policy_constructed", "size"),
            constructed=("policy_constructed", "sum"),
            violations=("risk_violation", lambda x: (x > 0).sum()),
            median_risk_violation=("risk_violation", "median"),
            median_ood_coverage=("ood_coverage", "median"),
            median_ood_spearman=("ood_spearman", "median"),
        )
        .reset_index()
    )
    aggregate["violation_rate_given_constructed"] = (
        aggregate["violations"] / aggregate["constructed"]
    )
    aggregate.to_csv(RESULTS / "phase_b_aggregate.csv", index=False)

    family = (
        data.groupby(["task", "holdout_family", "policy"])
        .agg(
            attempts=("policy_constructed", "size"),
            constructed=("policy_constructed", "sum"),
            violations=("risk_violation", lambda x: (x > 0).sum()),
            median_risk_violation=("risk_violation", "median"),
            median_ood_coverage=("ood_coverage", "median"),
        )
        .reset_index()
    )
    family.to_csv(RESULTS / "phase_b_family_summary.csv", index=False)

    labels = {
        "ensemble_std": "Ensemble uncertainty",
        "descriptor_distance": "Descriptor distance",
        "equal_rank_hybrid": "Hybrid",
    }
    order = list(labels)
    plot = (
        constructed.groupby(["task", "policy"])["risk_violation"]
        .agg(["median", lambda x: np.quantile(x, 0.25), lambda x: np.quantile(x, 0.75)])
        .rename(columns={"<lambda_0>": "q25", "<lambda_1>": "q75"})
        .reset_index()
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for ax, task, unit in zip(
        axes,
        ["expt_gap", "log_kvrh"],
        ["Risk violation (eV)", "Risk violation (log10 K units)"],
    ):
        part = plot.loc[plot["task"].eq(task)].set_index("policy").reindex(order)
        x = np.arange(len(order))
        ax.bar(
            x,
            part["median"],
            yerr=[part["median"] - part["q25"], part["q75"] - part["median"]],
            capsize=4,
        )
        ax.axhline(0, color="black", linewidth=1)
        ax.set_xticks(x, [labels[p] for p in order], rotation=20, ha="right")
        ax.set_ylabel(unit)
        ax.set_title("Experimental band gap" if task == "expt_gap" else "Computed bulk modulus")
    fig.suptitle("Frozen policy risk violations across family shifts")
    fig.savefig(FIGURES / "phase_b_risk_violations.png", dpi=220)
    fig.savefig(FIGURES / "phase_b_risk_violations.svg")


if __name__ == "__main__":
    main()
