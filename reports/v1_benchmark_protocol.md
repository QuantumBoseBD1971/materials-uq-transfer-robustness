# V1 Benchmark Protocol

**Working title:** When Should a Materials Model Abstain?  
**Protocol status:** Draft 0.3 during Phase-D analysis. Phase A–C are
outcome-visible development analyses and will not be represented as
preregistered confirmation. All subsequent changes must be logged.

## 1. Scientific question

Can a model-agnostic abstention policy calibrated only on familiar materials
maintain a predeclared absolute prediction-error tolerance after deployment to
unfamiliar material families?

This is a reliability-policy audit. It is not a new model competition, an
active-learning paper, or a claim that abstention is new.

## 2. Scope

### Included

- public, non-personal materials datasets;
- scalar regression from composition descriptors in Phase A;
- scientifically interpretable distribution shifts;
- post-hoc uncertainty and applicability-domain scores;
- thresholds chosen without OOD labels;
- repeated seeds and paired comparisons.

### Excluded from v1

- the author's PhD ideas, data, experiments, models, and unpublished work;
- employer data or code;
- interatomic potentials and molecular force/energy prediction;
- learned binary reliability classifiers;
- adaptation or recalibration using OOD labels;
- claims of conformal coverage guarantees under arbitrary shift;
- graph neural networks until the novelty gate is passed.

## 3. Selected datasets

| Role | Dataset | Size | Target | Origin | Current decision |
|---|---|---:|---|---|---|
| Experimental | Matbench `expt_gap` | 4,604 | Experimental band gap (eV) | Zhuo et al.; Matbench-curated distribution | Selected; Phase A completed |
| Computed | Matbench `log_kvrh` | 10,987 | DFT log10 bulk modulus | Materials Project-derived; Matbench-curated distribution | Selected; Phase A completed |

The selection deliberately contrasts a noisy experimental property with a
cleaner computed property. The dataset provenance record covers source version,
retrieval date, row identity, cleaning history, redistribution terms, target
units and raw-file checksums.

## 4. Data partitions

Every outer test set is locked before model fitting.

1. **Random:** interpolation reference, grouped by reduced composition so that
   equivalent formulae cannot cross partitions.
2. **Composition cluster:** cluster fixed composition descriptors; hold out
   entire clusters.
3. **Element holdout:** hold out eligible elements meeting minimum train and
   test support. The eligibility rule is written before outcomes are inspected.
4. **Family holdout:** define chemistry families using composition-only rules,
   then hold out complete families.

No OOD test label may influence hyperparameters, score construction, threshold
selection, or family definitions.

### Shift severity

For each test record compute its nearest-neighbour distance to the training set
in a standardized descriptor space. Report the test-set median, 90th percentile,
and fraction beyond the 99th percentile of training-to-training neighbour
distance. Repeat with an element-set novelty indicator.

Phase-C screening used four K-means composition clusters and the six most
supported eligible element holdouts per task. The confirmatory subset and
cluster seed must be frozen before its OOD outcomes are rerun.

## 5. Phase A models

- training-target mean;
- ridge regression;
- random forest;
- histogram gradient boosting;
- multilayer perceptron only if its validation stability is acceptable.

Use the same composition descriptor matrix and outer partitions for all
applicable models. Hyperparameter selection is nested inside the training
partition.

## 6. Reliability scores

All scores are oriented so that a larger value means less reliable.

- ensemble predictive standard deviation;
- conformal interval width;
- nearest-neighbour descriptor distance;
- normalized distance (distance divided by local training density);
- prespecified hybrid: rank-normalized ensemble uncertainty plus rank-normalized
  distance, with equal weights.

The hybrid's weights must not be tuned on OOD outcomes in v1.

## 7. Frozen operating policy

For dataset \(d\), predeclare a tolerable absolute error \(\epsilon_d\). On the
ID calibration set:

1. rank records from most to least reliable;
2. find the largest retained subset whose upper confidence bound for MAE is at
   or below \(\epsilon_d\);
3. record the corresponding score threshold and minimum acceptable coverage;
4. freeze both values;
5. apply them unchanged to every OOD test set.

If no ID operating point meets the tolerance and minimum coverage, record
policy construction failure rather than relaxing the rule after inspection.

Sensitivity analyses may use several tolerances, but one tolerance per dataset
must be labelled primary before OOD evaluation.

## 8. Outcomes

### Primary

\[
\Delta_{\mathrm{risk}} =
\operatorname{MAE}_{\mathrm{retained,OOD}}-\epsilon_d
\]

A positive value is a target-risk violation.

### Secondary

- retained coverage;
- transfer gap between OOD retained MAE and ID calibration retained MAE;
- catastrophic-error frequency among retained predictions;
- empirical interval coverage and mean interval width;
- Spearman correlation between score and absolute error;
- AURC and excess AURC;
- false abstention rate among predictions with realised error
  \(\leq\epsilon_d\).

Report bootstrap confidence intervals with resampling units grouped by reduced
composition. Use paired resamples when comparing policies on the same test set.
Treat transferred coverage below the predeclared minimum as an operational
failure distinct from a risk-limit breach. A zero-acceptance policy has
undefined retained risk and must never be counted as a safety success.

## 9. Negative and positive controls

- random reliability ranking;
- oracle ranking by realised absolute error (evaluation only);
- unfiltered model at 100% coverage;
- distance-only rule;
- uncertainty-only rule.

The oracle is an upper-bound diagnostic and must never be presented as a
deployable method.

## 10. Success and stop rules

Proceed to a graph model only if at least one result replicates across both
tasks:

- systematic target-risk violation under increasing shift;
- material disagreement between calibration and ranking;
- consistent benefit from the prespecified hybrid score;
- reversal of model ranking between MAE and policy-transfer performance.

If none replicates, stop model expansion and revise the question. Do not add
models merely to generate more tables.

## 11. Leakage checks

- canonicalize and reduce compositions before splitting;
- group exact composition duplicates; near-duplicate chemistry is not collapsed
  in v1 and must be reported as a limitation;
- fit descriptor scaling, imputers, clusters and conformal calibration only
  from permitted training/calibration data;
- hash and publish row-level split manifests;
- assert zero group overlap between train, calibration and test;
- log all exclusions with reason codes;
- never choose a “good-looking” family after viewing its model errors.

## 12. Planned outputs

1. literature and overlap matrix;
2. two dataset cards;
3. immutable split manifests;
4. configuration-driven baseline code;
5. results tables with paired uncertainty intervals;
6. failure-case atlas by chemistry family and shift severity;
7. manuscript and archived software release.

## 13. Open decisions before coding

- verify redistribution conditions for the Materials Project-derived Matbench
  snapshot;
- choose and justify \(\epsilon_d\) for each task without using OOD outcomes;
- define family rules and element eligibility thresholds;
- specify the descriptor package and pin its version;
- complete full-text extraction for MatUQ, Tang et al., Dale et al., and PROBE;
- register the protocol publicly only after the design is stable.

## 14. Development analysis log

- **Phase A:** single-split feasibility analysis; identified widespread family-shift failures.
- **Phase B:** 10-seed family holdouts, canonical-composition grouping,
  independently bootstrapped random forests and row-bootstrap calibration bounds.
- **Phase C:** three-seed screening with element and composition-cluster shifts,
  group-bootstrap calibration bounds and quantile-width uncertainty. This stage
  exposed the need to separate risk breach, inadequate transferred coverage and
  policy-construction failure.
- **Phase D pre-result quality control:** the computed bulk-modulus working table
  contained 160 repeated formula–target pairs (10,987 rows; 10,827 unique pairs).
  Exact pairs are deduplicated before the final analysis because the study uses
  composition-only inputs and repeated identical feature–label records would
  otherwise receive extra weight. Distinct targets for the same composition are
  retained and kept in a single partition. This check occurred before Phase-D
  results were available.
- **Phase D status:** locked extension with ten grouped repetitions, five
  tolerance scenarios, random/oracle controls, shift-severity diagnostics and
  row-level accept/reject records. It remains an outcome-visible robustness
  analysis, not a preregistered confirmation.
