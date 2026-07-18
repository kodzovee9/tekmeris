# Toolkit

`edikit` — a Python package for reproducible construction and auditing of
national social accounting matrices from official statistics. Modules
exist only when a paper needed them — nothing is built speculatively.

## Implemented modules

| Module | Role |
| --- | --- |
| `edikit.data` | source readers with accounting-identity checks on ingestion (SUT workbooks, SAM matrices, central-bank series, Eurostat JSON-stat, concordances) |
| `edikit.model` | account taxonomy with coverage assertions; RAS balancing with per-cell factor diagnostics |
| `edikit.report` | Excel workbooks whose totals and balance checks are live formulas |
| `edikit.pipeline` | end-to-end generation (`eurostat_sam`, for covered ESA country-years — see [recipes/build/COVERAGE.md](recipes/build/COVERAGE.md)) and auditing (`audit`) |

## Roadmap stubs (empty packages, not yet implemented)

`edikit.forecast` (vintage logging, later P006), `edikit.benchmark`
(P002 — rankings with uncertainty bands), `edikit.decide` (P005+ —
scenario comparison). They gain content only when a paper needs them.

## Recipes

`recipes/` holds the three user-facing entry points, one per use case,
all thin scripts over the same library (see `recipes/README.md`):

- `recipes/replicate/` — regenerate every number in the P001 paper.
- `recipes/audit/` — audit a published SAM: structure, then macro
  controls (`python audit_sam.py --sam matrix.csv ...`); Kenya is the
  committed worked example.
- `recipes/build/` — generate a validated macro SAM for any
  ESA-transmitting country in one command
  (`python build_sam.py --country AT --year 2019`), with the adaptation
  guide for countries outside the Eurostat universe.

## Rules

- Logic lives here; paper folders keep only thin wrapper scripts and configuration.
- Every module ships with tests (accounting identities are test cases, not comments).
- Public API changes get a line in the changelog once anything external depends on this.

## Development

```
cd toolkit
pip install -e ".[dev]"
pytest
```
