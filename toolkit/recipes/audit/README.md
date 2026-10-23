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
Parses the matrix (duplicated row or column codes are refused), reports
each account's receipts minus payments, detects the file's rounding grain,
and tests whether each imbalance is within what rounding alone can produce
(half a grain per nonzero cell in the account's row and column; cells
rounded to zero are not counted, so the bound can understate rounding).

**Rung 2 — macro controls (needs published national accounts).**
```bash
python audit_sam.py --sam matrix.csv --format matrix --code-col \
    --kinds kinds.csv --controls controls.csv --out audit.md
```
`kinds.csv` classifies every account into a canonical kind (activity,
commodity, factor, household, enterprise, government, tax-product,
tax-direct, savings, stocks, row, transaction-cost, other); build it from
the file's own documentation. `controls.csv` holds published aggregates
(GVA, product taxes, GDP, the expenditure components), with their source
recorded. Add `--strict` to stop on an unclassified account or on a
classification for an account the matrix lacks; without it those are
reported and left out of the aggregates. The aggregates depend on the
classification and on the audit's definitions (for example, private
consumption is commodity-to-household plus activity-to-household flows).

The deviations say where the SAM departs from the controls, not why.
Possible explanations to investigate, none of which the audit can confirm
on its own:
- a uniform shift across GVA, taxes, and GDP may reflect a different
  vintage of the national accounts;
- offsetting deviations across expenditure components may reflect a
  statistical discrepancy in the published accounts, which a balanced SAM
  cannot carry;
- a single large deviation may reflect a source, a concept difference (for
  example, home consumption routed household-to-activity), the
  classification, or an undocumented adjustment.

**Rung 3 — cell level (needs machine-readable primary sources).**
Cell-level auditing means rebuilding the matrix from the same sources
and comparing cell by cell; that is a construction exercise — see the
[build recipe](../build/) and the P001 South Africa pipeline
(`papers/P001-sut-to-sam/code/`, scripts 01–12), which is the complete
worked example including recovery of undocumented choices (grid searches
over source editions and formula signs) and pricing of non-public inputs.

For SAMs whose producers reconciled them by an estimation method (for
example cross-entropy), rebuilding cell by cell from the same sources need
not reproduce the published matrix, so rungs 1 and 2 are usually the
practical scope.

## Worked example: Kenya

`examples/kenya/` audits the IFPRI 2019 Nexus SAM (CC BY 4.0) against
KNBS Economic Survey 2020 controls. It is also used in the companion paper:

```bash
python audit_sam.py \
    --sam examples/kenya/002_IFPRI_SAM_KEN_2019_SAM.csv \
    --format matrix --code-col --strict \
    --kinds examples/kenya/kinds.csv --controls examples/kenya/controls.csv \
    --title "Kenya: IFPRI 2019 Nexus SAM vs KNBS Economic Survey 2020 controls" \
    --out examples/kenya/kenya_audit.md
```

Observed: the production side is 1.0% below the controls; investment and
imports are close; private consumption is 9.2% below, government
consumption 9.1% above, and exports 13.6% above. The companion paper
discusses possible explanations; the audit itself reports only the
deviations.

## File formats

- `--format long`: `row,col,value` CSV with a header.
- `--format matrix`: header row = column codes, first column = row codes;
  `--code-col` if a second code column follows the labels (IFPRI-style);
  rows/columns labelled "total" are skipped.

## The Kenya example is self-contained

`examples/kenya/` holds everything the Kenya audit needs: the distributed
IFPRI 2019 Nexus SAM for Kenya (`002_IFPRI_SAM_KEN_2019_SAM.csv`, published
on Harvard Dataverse, doi:10.7910/DVN/ALUXSI, under CC BY 4.0 and
redistributed here unmodified), the account classification (`kinds.csv`),
and the published controls (`controls.csv`), nine aggregates transcribed
from the Kenya National Bureau of Statistics' *Economic Survey 2020*.
`SOURCES.sha256` registers all three files. Cite the SAM as:
- Dataset: International Food Policy Research Institute (IFPRI). 2021.
  *2019 Social Accounting Matrix for Kenya*. Harvard Dataverse, version 1.0.
  doi:10.7910/DVN/ALUXSI.
- Data paper: Thurlow, J. 2021. *2019 Social Accounting Matrix for Kenya: A
  Nexus Project SAM*. Washington, DC: IFPRI. doi:10.2499/p15738coll2.134819.

From `toolkit/recipes/audit/`:

```
python audit_sam.py --sam examples/kenya/002_IFPRI_SAM_KEN_2019_SAM.csv \
    --code-col --kinds examples/kenya/kinds.csv \
    --controls examples/kenya/controls.csv --strict \
    --title "Kenya: IFPRI 2019 Nexus SAM vs KNBS Economic Survey 2020 controls" \
    --out kenya_audit.md
```

`--strict` passes: every account in the matrix is classified and no
classification names an account the matrix lacks.

## The Ghana example is self-contained

`examples/ghana/` audits the IFPRI 2019 SAM for Ghana against
World Development Indicators controls:

- **The SAM.** `IFPRI_SAM_GHA_2019_SAM.csv` is the distributed file, in
  millions of Ghanaian cedis, redistributed unmodified under CC BY 4.0. The
  citation its publishers require covers both the dataset and the data paper:
  - Dataset: Ghana Statistical Services (GSS); Institute for Statistical,
    Social, and Economic Research (ISSER); International Food Policy Research
    Institute (IFPRI). 2023. *2019 Social Accounting Matrix for Ghana*.
    Harvard Dataverse, version 1. doi:10.7910/DVN/AC7CKV.
  - Data paper: GSS; ISSER; IFPRI. 2023. *2019 Social Accounting Matrix for
    Ghana: A Nexus Project SAM*. Washington, DC: IFPRI.
    doi:10.2499/p15738coll2.136897.
- **The classification.** `kinds.csv` follows the Nexus template, the same as
  the Kenya example's.
- **The controls.** `controls.csv` holds Ghana's 2019 values from the World
  Bank's World Development Indicators (CC BY 4.0; series last updated
  2026-10-08), converted from cedis to millions of cedis. The series are:
  NY.GDP.FCST.CN, NY.TAX.NIND.CN, NY.GDP.MKTP.CN, NE.CON.PRVT.CN,
  NE.CON.GOVT.CN, NE.GDI.FTOT.CN, NE.GDI.STKB.CN, NE.EXP.GNFS.CN and
  NE.IMP.GNFS.CN.

From `toolkit/recipes/audit/`:

```
python audit_sam.py --sam examples/ghana/IFPRI_SAM_GHA_2019_SAM.csv \
    --code-col --kinds examples/ghana/kinds.csv \
    --controls examples/ghana/controls.csv --strict \
    --title "Ghana: IFPRI 2019 Nexus SAM vs World Development Indicators controls" \
    --out ghana_audit.md
```

The Kenya example is also used in the companion paper. The Ghana example
appears only here.
