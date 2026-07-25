# Phase-E Geometry-Augmented Bulk-Modulus Sensitivity

**Run date:** 24 July 2026  
**Purpose:** test whether the Phase-D bulk-modulus reliability result is merely
an artefact of composition-only inputs.

## Design

The deduplicated `matbench_log_kvrh` dataset contained 10,827 unique
formula–target records. The primary composition descriptors were augmented
with lattice lengths, lattice angles, unit-cell volume, site count, volume per
site, lattice-length anisotropy and mean angular deviation from 90 degrees.

The sensitivity analysis reused:

- the nine locked bulk-modulus shifts;
- the primary 0.15 log10-unit MAE target;
- the first five grouped repetitions;
- the same calibration confidence-bound rule;
- RF ensemble disagreement, descriptor distance and the equal-rank hybrid.

It is a basic geometry-descriptor test, not a crystal-graph benchmark.

## Main paired result

| Representation | Attempted | Constructed | Operational failures | Failure rate | Median OOD coverage | Median retained OOD MAE |
|---|---:|---:|---:|---:|---:|---:|
| Composition only | 135 | 131 | 68 | 51.9% | 100% | 0.150 |
| Composition + geometry | 135 | 135 | 60 | 44.4% | 100% | 0.131 |

The holdout-cluster bootstrap 95% interval for the geometry-augmented
operational-failure rate was 11.1%–77.8%. Geometry reduced retained OOD MAE by
0.0225 log10 units on average in paired transfers.

## Shift heterogeneity

- Cluster holdouts improved: failures decreased from 41/45 to 30/45 and median
  retained MAE decreased from 0.227 to 0.187.
- Element holdouts did not improve operationally: failures increased from
  27/90 to 30/90, although median retained MAE decreased from 0.131 to 0.124.
- Among 131 pairs where both representations constructed a policy, 15 failures
  became successes and three successes became failures.

## Interpretation

Basic unit-cell geometry improves average bulk-modulus prediction and some
composition-cluster transfers, but it does not uniformly protect the frozen
absolute-risk threshold. The main conclusion is therefore not explained solely
by omission of simple structural descriptors. A graph model remains an
important future extension.
