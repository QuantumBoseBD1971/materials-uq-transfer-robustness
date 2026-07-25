# Phase-C Robustness Screening Report

**Run date:** 24 July 2026  
**Status:** robustness screening; not preregistered confirmatory evidence.

## Design

Phase C tested whether Phase B's result survives two alternative definitions
of unfamiliar chemistry: complete element holdouts and unsupervised
composition-cluster holdouts. It also added a histogram-gradient-boosting
quantile-width score and changed the calibration risk bound to resample
canonical composition groups rather than individual rows.

The screen used three seeds, up to six supported element holdouts per task,
four composition clusters per task, five bootstrapped random forests, and a
one-sided 95% group-bootstrap MAE bound. OOD labels remained unavailable
until every threshold was frozen.

## Overall result

Of 228 attempted rules, 207 were constructible
on familiar calibration data. Among 206 transfers with at least
one accepted OOD prediction, **144 (69.9%)** breached
the absolute risk limit. Counting either a risk breach or transferred coverage
below 20% as operational failure, **148 of 207
(71.5%)** failed.

## Aggregate table

| Task | Shift | Policy | Constructed / attempted | Risk breaches / evaluable | Coverage failures | Operational failures | Median violation | Median coverage |
|---|---|---|---:|---:|---:|---:|
| Experimental gap | cluster | Distance | 6 / 12 | 5 / 5 | 1 | 6 | +1.674 | 0.0% |
| Experimental gap | cluster | Quantile width | 11 / 12 | 8 / 11 | 3 | 9 | +0.842 | 73.1% |
| Experimental gap | cluster | RF–distance hybrid | 12 / 12 | 10 / 12 | 6 | 12 | +0.502 | 34.7% |
| Experimental gap | cluster | RF ensemble | 12 / 12 | 11 / 12 | 0 | 11 | +0.505 | 99.9% |
| Experimental gap | element | Distance | 10 / 18 | 10 / 10 | 5 | 10 | +0.265 | 5.5% |
| Experimental gap | element | Quantile width | 18 / 18 | 18 / 18 | 0 | 18 | +0.816 | 89.0% |
| Experimental gap | element | RF–distance hybrid | 18 / 18 | 18 / 18 | 0 | 18 | +0.356 | 99.3% |
| Experimental gap | element | RF ensemble | 18 / 18 | 18 / 18 | 0 | 18 | +0.343 | 99.2% |
| Computed bulk modulus | cluster | Distance | 6 / 9 | 3 / 6 | 0 | 3 | +0.042 | 62.3% |
| Computed bulk modulus | cluster | Quantile width | 8 / 9 | 6 / 8 | 1 | 6 | +0.102 | 100.0% |
| Computed bulk modulus | cluster | RF–distance hybrid | 7 / 9 | 4 / 7 | 1 | 4 | +0.073 | 91.8% |
| Computed bulk modulus | cluster | RF ensemble | 9 / 9 | 6 / 9 | 1 | 6 | +0.112 | 100.0% |
| Computed bulk modulus | element | Distance | 18 / 18 | 7 / 18 | 0 | 7 | -0.015 | 100.0% |
| Computed bulk modulus | element | Quantile width | 18 / 18 | 6 / 18 | 0 | 6 | -0.020 | 100.0% |
| Computed bulk modulus | element | RF–distance hybrid | 18 / 18 | 7 / 18 | 0 | 7 | -0.015 | 100.0% |
| Computed bulk modulus | element | RF ensemble | 18 / 18 | 7 / 18 | 0 | 7 | -0.015 | 100.0% |

## Interpretation

The Phase-B conclusion is not confined to hand-written material-family rules
or one uncertainty estimator. Failures persist under held-out elements,
data-driven composition clusters, and quantile interval width. Distance-based
rules can reduce coverage sharply; zero acceptance is operational failure,
not evidence that the risk target transferred successfully.

## Limits and next gate

- This was an outcome-visible screening run and cannot serve as final inference.
- Cluster identity is representation-dependent and must be locked before confirmation.
- Element tests overlap because materials may contain several eligible elements.
- Tolerances still require independent scientific justification.
- Bulk-modulus prediction remains composition-only.
- Confirmatory analysis needs fixed holdouts, more seeds, paired group-bootstrap intervals,
  random and oracle controls, and sensitivity curves across risk tolerances.
