# Phase-B Repeated Evaluation Report

**Run date:** 24 July 2026  
**Status:** Confirmatory-development checkpoint; not yet a preregistered final result.

## Design improvement over Phase A

Phase B repeated every chemistry-family holdout with 10 training/calibration
seeds. Equivalent numeric compositions were kept within a single partition.
Each uncertainty estimate came from five independently bootstrapped random
forests (80 trees each). A policy could be deployed only if the upper 95th
percentile bootstrap bound for familiar-material calibration MAE met the
predeclared tolerance at a minimum of 20% coverage.

The selected score threshold was then frozen and applied to the held-out
chemistry family without using its labels.

## Main result

Across 270 attempted operating-policy transfers, 244 policies passed the
familiar-material construction rule. Of those deployable policies, **221
(90.6%) violated the same risk limit after transfer to an unfamiliar chemistry
family**.

| Task | Policy | Constructed / attempted | OOD violations / constructed | Median risk violation | Median OOD coverage |
|---|---|---:|---:|---:|---:|
| Experimental band gap | Ensemble uncertainty | 40 / 40 | 40 / 40 | +0.256 eV | 99.5% |
| Experimental band gap | Descriptor distance | 23 / 40 | 15 / 23 | +0.986 eV | 0.0% across all attempts* |
| Experimental band gap | Hybrid | 40 / 40 | 30 / 40 | +0.231 eV | 65.1% |
| Computed bulk modulus | Ensemble uncertainty | 50 / 50 | 50 / 50 | +0.096 log10 units | 97.2% |
| Computed bulk modulus | Descriptor distance | 41 / 50 | 40 / 41 | +0.097 log10 units | 97.9% |
| Computed bulk modulus | Hybrid | 50 / 50 | 46 / 50 | +0.094 log10 units | 86.0% |

\*The distance rule often could not be constructed or accepted almost no OOD
records. Construction failure and zero coverage are distinct from successful
risk control and must not be counted as safety successes.

## Strongest finding

Ensemble uncertainty passed the conservative familiar-material calibration
rule in every repeat, yet violated the transferred risk limit in **all 90 of 90
family-shift tests**. Median OOD coverage remained very high, indicating that
the policy usually failed by accepting unfamiliar predictions rather than by
becoming conservatively unusable.

The hybrid was materially more selective and succeeded on all 10 experimental
`other`-family repeats, but still violated the risk target in 76 of 90
constructed transfers. This supports a nuanced conclusion: adding descriptor
distance can help in some shifts, but does not make frozen transfer dependable
in general.

## Interpretation

The result is stronger than a simple increase in OOD prediction error. Every
tested operating point was chosen under an explicit familiar-material risk
constraint. The repeated failures show that calibration evidence did not
transfer with the frozen decision rule.

Uncertainty ranking was only moderately informative. Median Spearman
uncertainty–error correlation was approximately 0.41 for experimental band gap
and 0.20 for computed bulk modulus. A score can therefore have positive ranking
ability while still failing an absolute deployment-risk requirement.

## Remaining limitations and next gate

- Chemistry families remain broad rule-based stress tests.
- The two tolerances require domain justification independent of observed OOD
  outcomes.
- Bootstrap rows are not yet grouped by composition inside the risk-bound
  calculation.
- The bulk-modulus model is composition-only and omits crystal structure.
- Only one predictive model family supplies deployable UQ in Phase B.
- Multiple family tests are descriptive; no multiplicity-adjusted inferential
  claim is made.
- Final evidence requires preregistration before further outcome-driven design
  changes.

The next methodological gate should add composition-group bootstrap bounds,
element-holdout and composition-cluster shifts, a gradient-boosting quantile
baseline, and structure-aware bulk-modulus descriptors. The current result is
strong enough to justify that expansion.
