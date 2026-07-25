"""Create Phase-C aggregate tables, report, and figure."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

data = pd.read_csv(RESULTS / "phase_c_results.csv")
constructed = data[data["policy_constructed"]].copy()
constructed["risk_evaluable"] = constructed["risk_violation"].notna()
constructed["risk_breach"] = constructed["risk_violation"] > 0
constructed["coverage_failure"] = constructed["ood_coverage"] < 0.20
constructed["operational_failure"] = (
    constructed["coverage_failure"] | constructed["risk_breach"]
)

aggregate = (
    data.groupby(["task", "shift_type", "policy"], as_index=False)
    .agg(
        attempted=("policy_constructed", "size"),
        constructed=("policy_constructed", "sum"),
        median_coverage=("ood_coverage", "median"),
        median_risk_violation=("risk_violation", "median"),
        median_spearman=("ood_spearman", "median"),
    )
)
violations = (
    constructed.groupby(["task", "shift_type", "policy"], as_index=False)
    .agg(
        risk_evaluable=("risk_evaluable", "sum"),
        risk_breaches=("risk_breach", "sum"),
        coverage_failures=("coverage_failure", "sum"),
        operational_failures=("operational_failure", "sum"),
    )
)
aggregate = aggregate.merge(violations, how="left")
aggregate.to_csv(RESULTS / "phase_c_aggregate.csv", index=False)

holdout = (
    constructed.groupby(["task", "shift_type", "holdout", "policy"], as_index=False)
    .agg(
        risk_evaluable=("risk_evaluable", "sum"),
        risk_breaches=("risk_breach", "sum"),
        coverage_failures=("coverage_failure", "sum"),
        operational_failures=("operational_failure", "sum"),
        repeats=("operational_failure", "size"),
        median_risk_violation=("risk_violation", "median"),
        median_coverage=("ood_coverage", "median"),
        median_shift_distance=("shift_median_distance", "median"),
    )
)
holdout.to_csv(RESULTS / "phase_c_holdout_summary.csv", index=False)

plot = (
    constructed.groupby(["shift_type", "policy"], as_index=False)["operational_failure"]
    .mean()
    .pivot(index="policy", columns="shift_type", values="operational_failure")
    .mul(100)
)
FIGURES.mkdir(exist_ok=True)
ax = plot.plot(kind="barh", figsize=(9, 5.5), width=0.72)
ax.set_xlabel("Constructed policies failing risk or 20% coverage criterion (%)")
ax.set_ylabel("")
ax.set_xlim(0, 105)
ax.grid(axis="x", alpha=0.25)
ax.legend(title="Shift")
plt.tight_layout()
plt.savefig(FIGURES / "phase_c_violation_rates.png", dpi=220)
plt.savefig(FIGURES / "phase_c_violation_rates.svg")
plt.close()

total_attempted = len(data)
total_constructed = len(constructed)
total_evaluable = int(constructed["risk_evaluable"].sum())
total_breached = int(constructed["risk_breach"].sum())
total_operational = int(constructed["operational_failure"].sum())
breach_rate = 100 * total_breached / total_evaluable
operational_rate = 100 * total_operational / total_constructed

lines = [
    "# Phase-C Robustness Screening Report",
    "",
    "**Run date:** 24 July 2026  ",
    "**Status:** robustness screening; not preregistered confirmatory evidence.",
    "",
    "## Design",
    "",
    "Phase C tested whether Phase B's result survives two alternative definitions",
    "of unfamiliar chemistry: complete element holdouts and unsupervised",
    "composition-cluster holdouts. It also added a histogram-gradient-boosting",
    "quantile-width score and changed the calibration risk bound to resample",
    "canonical composition groups rather than individual rows.",
    "",
    "The screen used three seeds, up to six supported element holdouts per task,",
    "four composition clusters per task, five bootstrapped random forests, and a",
    "one-sided 95% group-bootstrap MAE bound. OOD labels remained unavailable",
    "until every threshold was frozen.",
    "",
    "## Overall result",
    "",
    f"Of {total_attempted} attempted rules, {total_constructed} were constructible",
    f"on familiar calibration data. Among {total_evaluable} transfers with at least",
    f"one accepted OOD prediction, **{total_breached} ({breach_rate:.1f}%)** breached",
    f"the absolute risk limit. Counting either a risk breach or transferred coverage",
    f"below 20% as operational failure, **{total_operational} of {total_constructed}",
    f"({operational_rate:.1f}%)** failed.",
    "",
    "## Aggregate table",
    "",
    "| Task | Shift | Policy | Constructed / attempted | Risk breaches / evaluable | Coverage failures | Operational failures | Median violation | Median coverage |",
    "|---|---|---|---:|---:|---:|---:|",
]
labels = {
    "expt_gap": "Experimental gap",
    "log_kvrh": "Computed bulk modulus",
    "rf_ensemble_std": "RF ensemble",
    "quantile_width": "Quantile width",
    "descriptor_distance": "Distance",
    "rf_distance_hybrid": "RF–distance hybrid",
}
for row in aggregate.itertuples():
    lines.append(
        f"| {labels[row.task]} | {row.shift_type} | {labels[row.policy]} | "
        f"{int(row.constructed)} / {int(row.attempted)} | "
        f"{int(row.risk_breaches or 0)} / {int(row.risk_evaluable or 0)} | "
        f"{int(row.coverage_failures or 0)} | {int(row.operational_failures or 0)} | "
        f"{row.median_risk_violation:+.3f} | {row.median_coverage:.1%} |"
    )
lines += [
    "",
    "## Interpretation",
    "",
    "The Phase-B conclusion is not confined to hand-written material-family rules",
    "or one uncertainty estimator. Failures persist under held-out elements,",
    "data-driven composition clusters, and quantile interval width. Distance-based",
    "rules can reduce coverage sharply; zero acceptance is operational failure,",
    "not evidence that the risk target transferred successfully.",
    "",
    "## Limits and next gate",
    "",
    "- This was an outcome-visible screening run and cannot serve as final inference.",
    "- Cluster identity is representation-dependent and must be locked before confirmation.",
    "- Element tests overlap because materials may contain several eligible elements.",
    "- Tolerances still require independent scientific justification.",
    "- Bulk-modulus prediction remains composition-only.",
    "- Confirmatory analysis needs fixed holdouts, more seeds, paired group-bootstrap intervals,",
    "  random and oracle controls, and sensitivity curves across risk tolerances.",
]
(ROOT / "phase_c_robustness_report.md").write_text("\n".join(lines) + "\n")
