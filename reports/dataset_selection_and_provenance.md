# Dataset Selection and Provenance — Phase A

**Decision date:** 24 July 2026  
**Status:** Feasibility selection; retain only if the baseline and licence audit pass.

## Selected tasks

| Role | Dataset | Rows | Target | Why selected |
|---|---|---:|---|---|
| Experimental | `matbench_expt_gap` | 4,604 | Experimental band gap (eV) | Composition-only task, material experimental noise, manageable size, and MIT-licensed source deposit |
| Computed | `matbench_log_kvrh` | 10,987 | DFT log10 VRH bulk modulus | Contrasts computed labels with the experimental task while remaining small enough for repeated independent runs |

The original broad plan used formation energy and superconducting critical
temperature. That pairing was changed because formation energy has 132,752
structures and is unnecessarily costly for the feasibility stage, while the
SuperCon provenance and redistribution position require further checking.

## Retrieval

- Official Matbench static JSON distributions:
  - `https://ml.materialsproject.org/projects/matbench_expt_gap.json.gz`
  - `https://ml.materialsproject.org/projects/matbench_log_kvrh.json.gz`
- Retrieval date: 24 July 2026.
- Raw files are retained byte-for-byte; processed tables are derived separately.

## Provenance notes

### Experimental band gap

Matbench describes this task as data retrieved from Zhuo et al.'s supplementary
information. It was deduplicated by composition. Compositions whose reported
band gaps spanned more than 0.1 eV were removed; a remaining composition was
assigned the reported value closest to that composition's mean. The original
Figshare deposit contains 6,354 records and is marked MIT; the Matbench task
contains 4,604 curated records.

This curation suppresses part of the real repeated-measurement variation.
Therefore, the task is "experimental" but not a complete representation of
experimental aleatoric uncertainty.

### Computed bulk modulus

Matbench describes this as Materials Project data retrieved on 2 April 2019.
The target is log10 of the Voigt–Reuss–Hill average bulk modulus. Entries with
formation energy or energy above hull above 150 meV, negative elastic moduli,
invalid Voigt/Reuss/VRH ordering, or noble gases were removed.

## Phase-A feature boundary

The first feasibility run intentionally uses composition fractions, number of
elements, and compositional entropy for both tasks. It does not yet use crystal
geometry. This makes model inputs comparable, cheap, and auditable, although it
places a deliberate ceiling on the computed-property model's accuracy.

## Prespecified family hierarchy

Families are mutually exclusive and assigned in this order:

1. oxide — contains O;
2. halide — contains F, Cl, Br, or I;
3. chalcogenide — contains S, Se, or Te;
4. pnictide — contains N, P, As, Sb, or Bi;
5. other.

Only families with at least 250 records are used as an OOD holdout in Phase A.
The hierarchy and minimum count were fixed before model errors were inspected.

## Primary feasibility tolerances

- experimental gap: accepted-set MAE no greater than 0.50 eV;
- log10 bulk modulus: accepted-set MAE no greater than 0.15 log10 units.

These are engineering feasibility thresholds, fixed before OOD outcomes were
examined. They are not yet asserted as universal scientific safety limits.
Sensitivity analysis and domain justification are required for the paper.

## Required citations

- Dunn et al., *Benchmarking materials property prediction methods: the
  Matbench test set and Automatminer reference algorithm*, npj Computational
  Materials 6, 138 (2020), DOI: 10.1038/s41524-020-00406-3.
- Zhuo, Mansouri Tehrani and Brgoch, *Predicting the Band Gaps of Inorganic
  Solids by Machine Learning*, J. Phys. Chem. Lett. 9, 1668–1673 (2018),
  DOI: 10.1021/acs.jpclett.8b00124.

## Licence gate

The experimental source deposit explicitly shows an MIT licence. The Matbench
code repository is MIT licensed. Before public redistribution, confirm whether
the Materials Project-derived raw bulk-modulus records may be redistributed
inside our release or whether the repository should instead publish retrieval
scripts and checksums only.
