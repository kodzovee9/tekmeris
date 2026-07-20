# Replicate recipe

Regenerate every number in the P001 working paper from the registered
sources. The replication package is `papers/P001-sut-to-sam/`:

- `data/SOURCES.md` — the source registry (publisher, vintage, URL,
  SHA-256 for every input). Public raw files are committed under
  `data/raw/`; access-restricted microdata (DataFirst) and
  redistribution-unclear files are registered by URL + hash and live in
  git-ignored `data/external/` — fetch them per the registry before
  running the scripts that need them.
- `code/01–13` — South Africa: SUT validation, concordances, the
  institutional block from SARB formulas, the capital/occupation/household
  share systems, assembly under rules R1–R7, RAS balancing, workbook
  generation, and the paper's tables and figure.
- `code/14` — Kenya: structural audit and KNBS macro-controls comparison.
- `code/15` — Netherlands: benchmark-free macro-SAM generation.
- `paper/` — the LaTeX manuscript; exhibits regenerate from `code/13`.

## Install

```bash
pip install -e "./toolkit[dev,replicate]"
```

`edikit` itself needs only `openpyxl`. The `replicate` extra adds two
packages that the P001 scripts use but the library does not: `xlrd`
(script 07 reads the Stats SA Annual Financial Statistics, which are
legacy `.xls`) and `matplotlib` (script 13 draws the paper's figure).
Without it those two scripts stop with `ModuleNotFoundError`; the other
thirteen are unaffected.

Run scripts in numeric order from `code/` (each states its inputs in its
docstring). Every script writes a validation report to `outputs/` — the
reports, not the console, are the record.

Most scripts need inputs that cannot be redistributed here. From a clean
clone, with no fetched data, three run to completion (12, 14, 15) and the
rest stop on a registered source: nine on the UNU-WIDER benchmark and one
(script 10) on the SARB series values, whose codes are listed in
`data/derived/sarb_kbp_series.csv` but whose observations come from the
Quarterly Bulletin files registered as S-004. That is expected behaviour,
not breakage; `data/raw/NOT-REDISTRIBUTED.md` states where each fetched
file belongs.
