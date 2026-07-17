# Audit recipe

Audit a published SAM as far as its public record allows. The recipe is
a ladder — each rung needs more public data than the last, and the
honest deliverable at every rung includes naming the rung you could not
reach and why.

## The ladder

**Rung 1 — structure (needs only the distributed SAM).**
```bash
python audit_sam.py --sam matrix.csv --format matrix --out audit.md
```
Parses the matrix, verifies every account's receipts equal its payments,
detects the file's rounding grain, and reports the account structure.
Two findings are common at this rung alone: distributed files rounded to
a grain that unbalances the matrix (rounding a balanced matrix
unbalances it), and account labels that contradict account contents.

**Rung 2 — macro controls (needs published national accounts).**
```bash
python audit_sam.py --sam matrix.csv --format matrix --code-col \
    --kinds kinds.csv --controls controls.csv --out audit.md
```
`kinds.csv` classifies every account into a canonical kind (activity,
commodity, factor, household, enterprise, government, tax-product,
tax-direct, savings, stocks, row, transaction-cost, other) — build it
from the file's own documentation, never from code prefixes. `controls.csv`
holds published aggregates (GVA, product taxes, GDP, the expenditure
components) transcribed from your statistical office's tables, with the
source table and page recorded in a comment or commit message.

How to read the deviations:
- *A uniform shift across GVA, taxes, and GDP* is the signature of a
  vintage difference (the SAM used an earlier release of then-provisional
  accounts), not a methodological choice.
- *Offsetting deviations across expenditure components* usually locate a
  reallocated statistical discrepancy: a balanced SAM cannot carry one,
  so if the published accounts have a production-vs-expenditure gap, the
  SAM's reconciliation put it somewhere — the comparison shows where.
- *A single large deviation* is a lead: trace it to a source, a
  concept difference (e.g. home consumption routed household-to-activity),
  or an undocumented adjustment.

**Rung 3 — cell level (needs machine-readable primary sources).**
Cell-level auditing means rebuilding the matrix from the same sources
and comparing cell by cell; that is a construction exercise — see the
[build recipe](../build/) and the P001 South Africa pipeline
(`papers/P001-za-sam/code/`, scripts 01–12), which is the complete
worked example including recovery of undocumented choices (grid searches
over source editions and formula signs) and pricing of non-public inputs.

Note for cross-entropy-reconciled SAMs (e.g. IFPRI Nexus): cell-level
replication is not the relevant test even with the sources in hand — the
matrix is a model output. Rungs 1–2 are the honest scope, plus
documenting the reconciliation's inputs.

## Worked example: Kenya

`examples/kenya/` audits the IFPRI 2019 Nexus SAM (CC-BY-4.0, committed
under `papers/P001-za-sam/data/raw/kenya/`) against KNBS Economic Survey
2020 controls:

```bash
python audit_sam.py \
    --sam ../../../papers/P001-za-sam/data/raw/kenya/ifpri/002_IFPRI_SAM_KEN_2019_SAM.csv \
    --format matrix --code-col \
    --kinds examples/kenya/kinds.csv --controls examples/kenya/controls.csv \
    --out examples/kenya/kenya_audit.md
```

Findings (Section 6.1 of the working paper): production side a uniform
−1.0% (vintage signature); investment and imports essentially exact; and
consumption −9.2%, government +9.1%, exports +13.6% — the visible
reallocation of KNBS's own Sh −352bn statistical discrepancy.

## File formats

- `--format long`: `row,col,value` CSV with a header.
- `--format matrix`: header row = column codes, first column = row codes;
  `--code-col` if a second code column follows the labels (IFPRI-style);
  rows/columns labelled "total" are skipped.
