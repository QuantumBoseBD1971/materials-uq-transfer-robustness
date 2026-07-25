# Research Analysis and Dataset Audit

**Audit date:** 24 July 2026  
**Project:** Frozen uncertainty-based error-control transfer across materials chemistry shifts  
**Author:** Mohammed Munir Uddin  
**ORCID:** 0009-0003-0147-2202

## 1. Audit conclusion

The primary analysis reported in the current manuscript is complete and its
headline values reproduce from the preserved result tables. The package
contains the raw source snapshots, processed dataset tables, split manifests,
row-level Phase-D predictions, analysis scripts, aggregate tables, figures and
the Overleaf manuscript.

This conclusion is deliberately narrower than saying that every item in the
early benchmark protocol was completed. The final paper focuses on element and
composition-cluster shifts, four deployable reliability policies, two
materials-property tasks, tolerance sensitivity, controls, grouped bootstrap
inference and a basic geometry sensitivity test. Some secondary analyses
listed during early planning were not included in the final study and are
recorded in Section 8.

## 2. Datasets actually used

### 2.1 Experimental band gap

| Item | Audited value |
|---|---|
| Matbench task | `matbench_expt_gap` |
| Raw file | `matbench_expt_gap.json.gz` |
| Raw rows | 4,604 |
| Input field | `composition` |
| Target field | `gap expt` |
| Target used in analysis | Experimental band gap, eV |
| Unique formula-target pairs used | 4,604 |
| Exact formula-target duplicates removed locally | 0 |
| Unique formulae | 4,604 |
| Raw SHA-256 | `783e7d1461eb83b00b2f2942da4b95fda5e58a0d1ae26b581c24cf8a82ca75b2` |

The Matbench task is derived from the compilation of Zhuo, Mansouri Tehrani
and Brgoch. Matbench had already curated the source data by composition,
removed compositions with a reported spread greater than 0.1 eV and retained
a representative value for the remaining compositions. It is therefore an
experimental-label task, but it does not preserve the full repeated-measurement
variation of the source compilation.

### 2.2 Computed bulk modulus

| Item | Audited value |
|---|---|
| Matbench task | `matbench_log_kvrh` |
| Raw file | `matbench_log_kvrh.json.gz` |
| Raw rows | 10,987 |
| Input field | `structure` |
| Target field | `log10(K_VRH)` |
| Target used in analysis | Base-10 logarithm of DFT VRH bulk modulus |
| Unique formula-target pairs used | 10,827 |
| Exact formula-target duplicates removed locally | 160 |
| Unique formulae before local deduplication | 9,723 |
| Formulae retaining more than one distinct target | 761 |
| Maximum distinct targets for one formula | 17 |
| Raw SHA-256 | `44b113ddb7e23aa18731a62c74afa7e5aa654199e0db5f951c8248a00955c9cd` |

The target is Materials Project-derived and was distributed through Matbench.
For the final analysis, one copy of every exact formula-target duplicate was
retained. Records having the same formula but genuinely different targets were
not collapsed. They were assigned the same composition group so they could not
cross training, calibration and test partitions within a run.

## 3. Features used

### 3.1 Primary Phase-D representation

Both tasks used:

- one fractional-composition feature for every element observed across the
  task;
- number of elements in the composition;
- compositional entropy.

The model did not use atom coordinates, bonds, graph representations or
external elemental-property tables in the primary analysis.

### 3.2 Phase-E geometry sensitivity

The bulk-modulus sensitivity analysis appended:

- lattice lengths \(a,b,c\);
- lattice angles \(\alpha,\beta,\gamma\);
- unit-cell volume;
- number of sites;
- volume per site;
- maximum-to-minimum lattice-length ratio;
- mean absolute lattice-angle deviation from 90 degrees.

These fields came directly from the structure objects in the same
`matbench_log_kvrh` snapshot. This is a low-dimensional structural sensitivity
test, not a crystal-graph model.

## 4. Final analysis design

- Final property tasks: two.
- Final shift types: complete element holdout and fixed
  composition-cluster holdout.
- Eligible holdouts: 19 total.
  - Experimental band gap: O, Se, S, Te, Cu, Ga and clusters C0-C3.
  - Computed bulk modulus: O, Li, Al, Si, Mg, Cu and clusters C1-C3.
- Primary Phase-D repetitions: ten grouped training/calibration splits.
- Familiar-data calibration allocation: 20% of familiar composition groups.
- Primary point model: five independently bootstrapped random-forest members,
  each with 50 trees.
- Deployable scores: RF ensemble standard deviation, quantile-regression
  interval width, nearest-training descriptor distance and an equal-rank
  uncertainty-distance hybrid.
- Controls: random ranking and realised-error oracle ranking.
- Threshold rule: largest candidate coverage from 20%-100% whose one-sided
  95th-percentile grouped-bootstrap calibration MAE bound was no greater than
  the selected tolerance.
- Primary tolerances: 0.50 eV for band gap and 0.15 log10 units for bulk
  modulus.
- Sensitivity tolerances: 0.30-0.70 eV and 0.10-0.20 log10 units.
- OOD retained-MAE intervals: 200 composition-group bootstrap resamples.
- Headline operational-failure interval: 3,000 resamples of complete
  task-shift-holdout blocks.

## 5. Reproduced headline results

Direct recalculation from `results/phase_d_results.csv` confirms:

| Quantity | Reproduced value |
|---|---:|
| Primary deployable-policy transfers attempted | 760 |
| Policies constructible on familiar calibration data | 701 |
| Constructed policies accepting at least one OOD material | 695 |
| Risk breaches among evaluable transfers | 514/695 (74.0%) |
| Operational failures among constructed policies | 532/701 (75.9%) |
| Experimental-band-gap operational failures | 343/350 |
| Bulk-modulus operational failures | 189/351 |

The Phase-D split manifest contains 1,434,830 partition assignments. No
training/calibration, training/OOD or calibration/OOD row-identifier overlap
was detected within any task-shift-holdout-repeat block.

The Phase-E result table also reproduces:

| Representation | Constructed | Operational failures | Failure rate | Median retained OOD MAE |
|---|---:|---:|---:|---:|
| Composition only | 131/135 | 68 | 51.9% | 0.150 |
| Composition plus geometry | 135/135 | 60 | 44.4% | 0.131 |

## 6. Software environment observed during audit

| Package | Version |
|---|---:|
| Python packages / runtime | Python-based analysis |
| NumPy | 2.3.5 |
| pandas | 2.2.3 |
| scikit-learn | 1.8.0 |
| SciPy | 1.17.0 |

The release should preserve a fully pinned environment file rather than only
minimum-version ranges. The Python interpreter version and platform should
also be captured when the final public repository is created.

## 7. What is complete

- Raw source snapshots and checksums are present.
- Final processed row counts and duplicate treatment are traceable.
- Element and cluster holdouts are fixed and named.
- Ten repeated grouped Phase-D splits are present.
- Leakage checks pass at the recorded row-identifier level.
- Four deployable reliability policies and two diagnostic controls are present.
- Five operating tolerances per task are present.
- Risk breach and low-coverage failure are distinguished.
- Row-level Phase-D predictions and primary accept/reject decisions are
  preserved.
- Grouped-bootstrap transfer intervals and holdout-cluster uncertainty are
  present.
- Basic geometry-augmented sensitivity analysis is complete.
- Manuscript headline values match the final CSV outputs.

## 8. What was planned earlier but is not part of the completed paper analysis

The early protocol mentioned several outputs that the narrowed final paper does
not report:

- a final random/interpolation outer-split benchmark;
- final family-holdout results alongside element and cluster shifts;
- catastrophic-error frequency;
- empirical quantile-interval coverage and mean interval width;
- false-abstention rate among predictions whose realised error was within the
  tolerance;
- a full chemistry failure-case atlas;
- a crystal-graph model;
- a publicly preregistered, untouched external confirmation dataset.

These omissions do not make the current paper internally incomplete because
the manuscript does not claim to provide them. They do mean that the correct
statement is:

> The analysis required for the current, narrowly framed paper is complete;
> the study is an outcome-visible robustness analysis rather than a
> preregistered external confirmation.

## 9. Remaining issues before journal submission or thesis reuse

1. Resolve and document the redistribution terms for the Materials
   Project-derived raw bulk-modulus snapshot. Publishing retrieval
   instructions and checksums instead of the raw file may be safest.
2. Create a pinned reproducibility environment containing the exact Python and
   package versions.
3. Insert the eventual GitHub release URL and Zenodo DOI.
4. Give the scenario tolerances an explicit application-based rationale, or
   continue to label them clearly as illustrative operating tolerances.
5. Preserve the wide holdout-cluster interval and avoid treating the 760
   transfers as independent experiments.
6. If reused in a thesis, describe this as independent computational research
   based exclusively on public Matbench data. Do not imply that it uses the
   author's experimental PhD data. Its inclusion should match the thesis scope
   and supervisory/university requirements.

## 10. Recommended thesis dataset statement

> The computational study used two public Matbench v0.1 regression tasks:
> `matbench_expt_gap`, containing 4,604 composition-level experimental band-gap
> observations, and `matbench_log_kvrh`, containing 10,987
> structure-property records for DFT-derived log10 VRH bulk modulus. A
> pre-analysis duplicate audit of the latter identified 160 exact
> formula-target repetitions; retaining one copy of each produced 10,827
> unique formula-target observations. Distinct target values associated with
> the same composition were retained but grouped to prevent composition
> leakage between training, calibration and test partitions. The primary
> representation used elemental fractions, element count and compositional
> entropy. A paired sensitivity analysis additionally used basic unit-cell
> geometry from the bulk-modulus structures.

This paragraph should be adapted to the final thesis chapter and accompanied
by the Matbench and Zhuo et al. citations and the final software/data
availability record.
