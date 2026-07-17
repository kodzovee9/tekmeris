# Replicate recipe

Regenerate every number in the P001 working paper from the registered
sources. The replication package is `papers/P001-za-sam/`:

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

Run scripts in numeric order from `code/` (each states its inputs in its
docstring; 01–06 and 10–15 need only committed data). Every script
writes a validation report to `outputs/` — the reports, not the console,
are the record.
