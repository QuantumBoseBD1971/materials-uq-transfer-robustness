# Phase-D Full Robustness Analysis

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

- attempted deployable transfers: 760;
- policies constructible on familiar calibration data: 701;
- transfers accepting at least one OOD material: 695;
- absolute-risk breaches: 514 of 695
  (74.0%);
- operational failures (risk breach or OOD coverage below 20%):
  532 of 701
  (75.9%; holdout-cluster bootstrap 95% interval 55.4%–93.2%);
- transfers whose composition-group bootstrap interval lay wholly above the
  target: 460 of 695.

## Interpretation boundary

The study shows that a policy satisfying an ID calibration-risk bound often
does not retain the same absolute error target after chemistry shift. It does
not show that every UQ method, model class, representation, or materials task
must fail. The oracle control is nondeployable and is used only to determine
whether useful low-error subsets exist in principle.
