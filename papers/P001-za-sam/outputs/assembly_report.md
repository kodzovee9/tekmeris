# P001 SAM v0.1 assembly report

Generated 2026-07-16 by code/10_assemble_sam.py. Public inputs only; disclosed rules R1-R7 in the script header.

- Accounts: 209; nonzero cells: 6,779
- Cells in common with benchmark: 6,732 of ours 6,779 / benchmark 6,737
- Common cells equal within R0.5m: 4,205 (62.5%); median |diff| R0.00m
- Account imbalances (row minus column), share of VA R4,938,506m:

| Account | Imbalance (Rm) | % of VA |
|---|---|---|
| hhd9 | +99,987 | +2.025% |
| hhd14 | -93,223 | -1.888% |
| hhd13 | -59,541 | -1.206% |
| hhd8 | +47,873 | +0.969% |
| hhd10 | +29,406 | +0.595% |
| hhd5 | -8,679 | -0.176% |
| hhd4 | -6,807 | -0.138% |
| hhd2 | -6,664 | -0.135% |
| hhd12 | +6,368 | +0.129% |
| hhd1 | -6,311 | -0.128% |
| hhd3 | -5,326 | -0.108% |
| hhd7 | +2,559 | +0.052% |

Max |imbalance|: R99,987m. Residual imbalances stem from rules R1-R6 and the documented benchmark discrepancies (596 adjustment, mtx proxy); v0.2 closes them with the balancing module.
