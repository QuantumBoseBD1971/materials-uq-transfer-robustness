# Phase-A Feasibility Report

**Run date:** 24 July 2026  
**Interpretation status:** Exploratory feasibility result, not manuscript evidence.

## Question tested

If a random-forest uncertainty threshold is selected solely on familiar
materials so that accepted calibration predictions meet a fixed MAE tolerance,
does that threshold still meet the same tolerance on a completely held-out
chemistry family?

The policy was not recalibrated using held-out labels.

## Data and design

- 4,604 experimental band-gap records; tolerance 0.50 eV.
- 10,987 computed log10 bulk-modulus records; tolerance 0.15 log10 units.
- broad mutually exclusive oxide, halide, chalcogenide, pnictide and other
  families;
- only holdout families with at least 250 records;
- composition fractions plus two simple stoichiometric features;
- ridge and random-forest baselines;
- random-forest tree disagreement, nearest-training-composition distance, and
  an equal-rank hybrid policy.

There were nine dataset–family holdouts and 27 policy-transfer tests.

## Initial result

The frozen operating policy violated its target OOD risk in **23 of 27 tests**.

| Task | Policy | Holdouts violating risk / total | Median risk violation | Median retained OOD coverage |
|---|---|---:|---:|---:|
| Experimental gap | Ensemble disagreement | 4 / 4 | +0.207 eV | 99.8% |
| Experimental gap | Descriptor distance | 4 / 4 | +0.645 eV | 92.0% |
| Experimental gap | Equal-rank hybrid | 3 / 4 | +0.207 eV | 99.9% |
| Computed log bulk modulus | Ensemble disagreement | 4 / 5 | +0.115 | 100.0% |
| Computed log bulk modulus | Descriptor distance | 4 / 5 | +0.107 | 97.0% |
| Computed log bulk modulus | Equal-rank hybrid | 4 / 5 | +0.099 | 96.4% |

The clearest failure was the held-out oxide family for experimental band gap.
The ensemble rule retained 99.6% of unfamiliar oxides but produced an accepted
MAE of 1.474 eV against the frozen 0.50 eV limit.

For computed bulk modulus, the held-out halide family was similarly problematic:
the best of the three tested policies still retained 91.7% and produced an MAE
of 0.389, exceeding the 0.15 limit by 0.239.

The hybrid succeeded for the experimental `other` holdout, retaining 17.7% at
0.206 eV MAE. It also narrowly succeeded for computed pnictides, retaining
96.4% at 0.144. This prevents an over-broad claim that threshold transfer always
fails.

## What this means

The central phenomenon is present strongly enough to justify continuing:
calibration on familiar materials frequently approved almost the entire
calibration set, yet the same frozen score threshold failed to recognise large
errors after a chemistry-family shift.

This is more specific than simply observing that OOD MAE is worse. It shows a
failure of a deployment rule that appeared acceptable before the shift.

## What this does not establish

- One deterministic split per family is insufficient for inference.
- Broad rule-based families are useful stress tests but do not yet constitute a
  complete scientific taxonomy.
- Tree-level random-forest disagreement is not a full independent ensemble.
- Composition-only inputs omit crystal geometry, especially important for
  elastic properties.
- The empirical calibration rule does not yet use a confidence bound on risk.
- The fixed tolerances need stronger scientific justification and sensitivity
  analysis.
- No claim of novelty or general failure should be made from this run alone.

## Next registered experiment

1. repeat each holdout with at least 10 training/calibration seeds;
2. select the threshold using an upper bootstrap confidence bound for
   calibration MAE;
3. add risk–coverage curves, AURC, ranking correlation and interval coverage;
4. add element-holdout and composition-cluster shifts;
5. use independent bootstrap ensembles;
6. compare composition-only with structure-aware features for bulk modulus;
7. retain OOD labels as evaluation-only data throughout;
8. rerun the novelty search immediately before protocol registration.

## Raw-file checksums

- `matbench_expt_gap.json.gz`:
  `783e7d1461eb83b00b2f2942da4b95fda5e58a0d1ae26b581c24cf8a82ca75b2`
- `matbench_log_kvrh.json.gz`:
  `44b113ddb7e23aa18731a62c74afa7e5aa654199e0db5f951c8248a00955c9cd`
