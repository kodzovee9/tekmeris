# Toolkit

`edikit` — a Python package for reproducible construction and auditing of
national social accounting matrices from official statistics. Modules
exist only when a paper needed them — nothing is built speculatively.

## Implemented modules

| Module | Role |
| --- | --- |
| `edikit.data` | readers for one publisher's layout each (Stats SA SUT workbooks, ANSD supply-use tables, SAM workbooks, SARB bulk files, Eurostat JSON-stat), with `check_*` functions that report identity findings; concordances; `provenance` (verify files against a SHA-256 manifest) |
| `edikit.model` | account taxonomy with explicit classification (`classify_by_prefix` raises on an unmatched code); RAS and GRAS (negative-tolerant) balancing that returns every cell's adjustment factor |
| `edikit.report` | Excel workbooks whose totals and balance checks are live formulas |
| `edikit.pipeline` | macro-SAM generation (`eurostat_sam`, for covered ESA country-years; see [recipes/build/COVERAGE.md](https://github.com/kodzovee9/tekmeris/blob/main/toolkit/recipes/build/COVERAGE.md)), auditing (`audit`), and two-producer comparison (`reconcile`) |

Which conditions stop execution and which are recorded is set out in the
edikit metapaper (Table 1).

## Roadmap stubs (empty packages, not yet implemented)

`edikit.forecast` (vintage logging, later P006), `edikit.benchmark`
(P002 — rankings with uncertainty bands), `edikit.decide` (P005+ —
scenario comparison). They gain content only when a paper needs them.

## Recipes

`recipes/` holds the three user-facing entry points, one per use case,
all thin scripts over the same library (see `recipes/README.md`):

- `recipes/replicate/` documents how the companion paper's scripts
  reproduce its numbers. Some need restricted inputs that each user obtains.
- `recipes/audit/` audits a published SAM: structure first, then macro
  controls (`python audit_sam.py --sam matrix.csv ...`). Ghana and Kenya are
  the worked examples.
- `recipes/build/` generates a balanced macro SAM for covered ESA
  country-years in one command (`python build_sam.py --country DK --year
  2019`; see `recipes/build/COVERAGE.md`). Five worked examples ship with
  their inputs.

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
