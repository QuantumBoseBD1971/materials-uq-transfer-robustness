# Frozen uncertainty controls across materials chemistry shifts

Version 1.0.0 of the reproducibility materials accompanying:

> Mohammed Munir Uddin, “Evaluating the Transfer of Frozen
> Uncertainty-Based Error Controls Across Materials Chemistry Shifts”

## Scope

This archive contains the analysis code, deterministic split manifests,
aggregate and transfer-level result tables, figures, and audit documentation
for the manuscript. It does **not** contain the original Matbench source
records or row-level predictions that reproduce source target values.

The study evaluates whether acceptance thresholds selected using only
familiar-material calibration data preserve an absolute retained-set mean
absolute error target after element and composition-cluster distribution
shifts. The primary analysis uses experimental band gap and computed
log10 bulk modulus tasks from Matbench. A sensitivity analysis augments the
bulk-modulus representation with basic unit-cell geometry.

## Obtain the source data

Run:

```bash
python src/fetch_matbench.py
```

The script downloads the two official Matbench v0.1 task files and verifies
their SHA-256 checksums:

- `matbench_expt_gap.json.gz`:
  `783e7d1461eb83b00b2f2942da4b95fda5e58a0d1ae26b581c24cf8a82ca75b2`
- `matbench_log_kvrh.json.gz`:
  `44b113ddb7e23aa18731a62c74afa7e5aa654199e0db5f951c8248a00955c9cd`

## Environment

The analysis was run with Python 3.12.13. Create a clean environment and
install the pinned dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Reproduction order

The scripts use fixed seeds and read/write paths relative to the archive root:

```bash
python src/phase_a_baseline.py
python src/phase_b_benchmark.py
python src/summarise_phase_b.py
python src/phase_c_robustness.py
python src/summarise_phase_c.py
python src/phase_d_full_analysis.py
python src/summarise_phase_d.py
python src/phase_e_geometry_sensitivity.py
python src/summarise_phase_e.py
```

Phase D is computationally expensive. Its environment variables
`PHASE_D_WORKER_ID` and `PHASE_D_N_WORKERS` support independent worker
partitions; Phase E provides the analogous `PHASE_E_*` variables. Combine
worker outputs before running the corresponding summary script.

## Contents

- `src/`: data retrieval, analysis, and summary scripts;
- `data/processed/`: deterministic split manifests only;
- `results/`: transfer-level and aggregate outputs without source records or
  row-level source targets;
- `figures/`: paper figures;
- `reports/`: protocol, provenance, phase reports, and final audit;
- `manuscript/`: manuscript PDF and journal submission support files.

## Data and licensing

The source datasets are third-party Matbench data and are not redistributed in
this archive. Users should retrieve them from Matbench and comply with the
applicable Matbench, Figshare, and Materials Project terms.

Code in `src/` is released under the MIT License. Original documentation,
figures, and result tables produced for this study are released under
CC BY 4.0. See `LICENSE.md`.

## Archived release

Version 1.0.0 is permanently archived on Zenodo:

[https://doi.org/10.5281/zenodo.21545109](https://doi.org/10.5281/zenodo.21545109)

## Citation

Please cite the archived release using:

Mohammed Munir Uddin. *Frozen uncertainty controls across materials chemistry shifts*. Version 1.0.0. Zenodo, 2026. https://doi.org/10.5281/zenodo.21545109

Machine-readable citation metadata is available in `CITATION.cff`.

## Contact

Mohammed Munir Uddin  
ORCID: https://orcid.org/0009-0003-0147-2202  
Email: muniruddin514@outlook.com
