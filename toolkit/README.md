# Toolkit

The shared Python package (`edikit`, a working name) that accumulates across papers. Modules exist only when a paper needed them — nothing is built speculatively.

## Module map (mirrors the five dimensions)

| Module | Tag | First expected contributor |
| --- | --- | --- |
| `edikit.data` | data | P001 — source registry, ingestion, concordances, provenance |
| `edikit.model` | model | P001/P002/P003 — SAM assembly, balancing (RAS/GRAS/cross-entropy), multipliers, IO updating |
| `edikit.forecast` | forecast | vintage logging (standing task), later P006 |
| `edikit.benchmark` | benchmark | P002 — rankings with uncertainty bands |
| `edikit.decide` | decide | P005+ — scenario comparison, trade-off reporting |
| `edikit.report` | cross-cutting | P001 — transparent Excel workbook generation, validation reports |
| `edikit.pipeline` | cross-cutting | end-to-end generators; `eurostat_sam` builds a validated macro SAM for any ESA-transmitting country |

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
