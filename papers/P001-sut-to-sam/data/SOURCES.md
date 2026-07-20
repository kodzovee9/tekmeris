# P001 Source Registry

Every raw file is recorded here with its provenance and SHA-256 hash before any use. Raw files are stored unmodified under `raw/` with their original filenames; all transformations create new artifacts elsewhere.

## S-001 — StatsSA Supply and Use Tables, 2018–2019

| Field | Value |
| --- | --- |
| Publisher | Statistics South Africa (Stats SA) |
| Title | Supply and Use Tables: revised 2018 and preliminary 2019 |
| Series | Report 04-04-03 |
| Reference period | Calendar years 2018 (revised), 2019 (preliminary) |
| Source page | https://www.statssa.gov.za/?page_id=1854&PPN=Report-04-04-03 |
| Access date | 2026-07-16 (manual download by founder; site blocks automated clients) |
| File | `raw/statssa/Supply and use tables 2018 - 2019.xlsx` (457 KB) |
| SHA-256 | `3cc319842ec7da64db3c90d9d92b540616afab2a5db08b822f3ea96a580a576b` |
| Contents | 6 sheets: Industry List, Product List, Supply Table 2018, Use Table 2018, Supply Table 2019, Use Table 2019 |
| License | Stats SA publications are publicly released statistics; reproduction customarily permitted with attribution — **verify exact copyright terms before public redistribution** |
| Use in P001 | Primary input: the official SUT core from which the SAM is constructed |
| Known limitations | 2019 tables are preliminary; Stats SA may have published revisions since. Must verify vintage matches the one used by the benchmark SAM (see S-003) by comparing control totals. |

## S-002 — StatsSA SUT report (documentation)

| Field | Value |
| --- | --- |
| Title | Supply and Use Tables 2019 report (PDF) |
| URL | https://www.statssa.gov.za/publications/Report-04-04-03/Report-04-04-032019.pdf |
| Access date | 2026-07-16 |
| File | `raw/statssa/Report-04-04-032019.pdf` (1.0 MB) |
| SHA-256 | `4163785fa0ff1c27d82562b7d100a89804513fc3fb4dc4b6987e6fa59208791c` |
| Use in P001 | Methodological documentation: valuation bases, margins, classifications |

## S-003 — UNU-WIDER 2019 South Africa SAM (benchmark) — OBTAINED

| Field | Value |
| --- | --- |
| Publisher | UNU-WIDER (SA-TIED programme) |
| Title | A 2019 Social Accounting Matrix for South Africa with occupational and capital stock detail |
| Authors | Dirk van Seventer, Rob Davies |
| Published | March 2023 (Technical Note 2023/1) |
| Data URL | https://www.wider.unu.edu/sites/default/files/Publications/Technical-note/tn2023-1-2019-SASAM-for-distribution.zip |
| Documentation | https://www.wider.unu.edu/sites/default/files/Publications/Technical-note/PDF/tn2023-1-2019-SAM-South-Africa-occupational-capital-stock-detail.pdf |
| License | © UNU-WIDER 2023; explicit redistribution terms not stated on the page — **treat as non-redistributable until confirmed**. File will be stored under `external/` (git-ignored); the replication package ships fetch instructions + hash, not the file. |
| Files | `external/tn2023-1-2019-SASAM-for-distribution.zip` (520 KB) and the workbook extracted from it, `external/tn2023-1-2019-SASAM-for-distribution.xlsx` (616 KB). Not redistributed; fetch from the Data URL above and verify against the hashes below. |
| SHA-256 (zip) | `515f98108a8951d02f9808903e319e7fee5e44f67b9b71839392e9c7966b2d99` |
| SHA-256 (xlsx) | `8a79715cc9d39194fc55afa8e7968f1f36d071a88bc4a067e033d5f7e17cc144` |
| Use in P001 | Validation benchmark: the published SAM built from the same official 2019 sources |
| Status | Obtained 2026-07-16; hashes recorded 2026-07-19 |

## S-004 — SARB Quarterly Bulletin national accounts (KBP series) — OBTAINED

| Field | Value |
| --- | --- |
| Publisher | South African Reserve Bank |
| Title | Quarterly Bulletin macroeconomic time series (annual KBP series), 2019 values as published 2022 |
| Access | Online statistical query at resbank.co.za (browser; free). The public web API endpoint responds but returned empty for KBP codes from this environment — verify interactively. |
| Required series | **69 annual series**, enumerated with descriptions in `derived/sarb_kbp_series.csv`, extracted from S-003's technical note, which maps every institutional macro-SAM cell to explicit KBP formulas |
| Use in P001 | Macro controls for the entire institutional block: factor income allocation, property income, transfers, direct taxes, savings, rest-of-world |
| Files | `raw/sarb/05KBP6 National Accounts December 2022.zip` (SHA-256 `776e2d19…8be60a22`), `raw/sarb/03Kbp4 Public Finance December 2022.zip` (`9cc9362c…b29275c`), `raw/sarb/04KBP5 Balance of Payments December 2022.zip` (`63c24469…a28090b4`) — bulk Quarterly Bulletin data files, December 2022 issue, downloaded 2026-07-16 via browser (the online statistical query backend currently returns empty for all KBP series; diagnosed and documented) |
| Coverage check | All 69 required codes present in the annual (J1) sheets with 2019 values. Vintage verified: KBP6007J (household consumption) = R3,588,896m and KBP6014J (imports) = R1,502,065m equal the benchmark SAM's corresponding cells exactly — this is the "SARB 2022" vintage the technical note cites. |
| Status | Obtained |

## S-005 — Stats SA Labour Market Dynamics 2018 & 2019 — OBTAINED

| Field | Value |
| --- | --- |
| Publisher | Statistics South Africa (reports P0211-based; microdata via DataFirst, UCT) |
| Use in P001 | Disaggregation of wage earnings by industry x occupation (10 occupations) |
| Access | Microdata via DataFirst (founder registered 2026-07-16) |
| Files | `external/lmdsa-2018-v1.0-csv.zip` (LMD 2018 v1.0 CSV, SHA-256 `c18e20d1…c664ee2`) and `external/lmdsa-2019-v1.1.zip` (LMD 2019 v1.1, SHA-256 `2df63362…5af342e0`, 168 MB CSV inside) — both git-ignored: DataFirst terms prohibit redistribution; replication package ships scripts + aggregated shares only |
| Status | Both years obtained — **S-005 complete. Data audit closed: every source family used by the benchmark is in hand.** |

## S-006 — Stats SA Living Conditions Survey 2014/15 (P0310) — OBTAINED

| Field | Value |
| --- | --- |
| Publisher | Statistics South Africa; microdata via DataFirst (UCT) |
| Use in P001 | Household disaggregation into 14 expenditure groups (deciles; top decile split into five 2% bands); distribution of factor income and outlays to households |
| Access | Microdata via DataFirst (founder registered 2026-07-16) |
| Files | `external/lcs-2014-2015-v1-csv.zip` (LCS 2014/15 v1 CSV, SHA-256 `9de5ade4208cd36103edbbf36bc649dcff4b3a1b92095ff980527116ac500cf9`, git-ignored: DataFirst terms prohibit redistribution — replication package ships scripts + aggregated decile shares only) |
| Status | Obtained |

## S-007 — Stats SA Annual Financial Statistics 2019 (P0021) — OBTAINED

| Field | Value |
| --- | --- |
| Publisher | Statistics South Africa |
| Use in P001 | Disaggregation of gross operating surplus into six capital-stock types (the accounts with suspect code/description alignment in the SAM: immo, mach, nitc, trnp, inta, land) |
| Access | Public report + data files on statssa.gov.za |
| Files | `raw/statssa/P00212019.pdf` (report); `raw/statssa/afs/` — three data zips (2026-07-16): Disaggregated industry estimates 2018–2019 (contains the **PPE schedules**: carrying values, additions, disposals by asset type x SIC industry — the capital-stock source behind the SAM's six capital accounts), Time series estimates, and Estimates by business size |
| Status | Fully obtained. Addendum 2026-07-16: `raw/statssa/afs/Disaggregated industry estimates 2019_2020.zip` (SHA-256 `4be9ad19…08a054a`) added — contains **AFS 2019 revised**, identified numerically as the vintage behind the benchmark's capital split (median share deviation 0.18pp vs 0.72pp for the 2019 preliminary edition). |

## S-003 documentation — technical note (OBTAINED)

`external/tn2023-1.pdf` (SHA-256 `07be2dfea79f3431e16548c398dcd96f83444fc8862c44a2d6ede5f3586b792a`; 42 pages) with extracted text `external/tn2023-1.txt`. Beyond the source map above, it records two facts material to P001's replication claim:

1. **A known non-public input**: the split of import duties (mtx) from other product taxes (stx) uses *unpublished data supplied by Stats SA*. Full public replication of that split is impossible; P001 must treat it as an expert-judgment cell with a public proxy (e.g., SARS/Treasury tax statistics) and disclose the difference.
2. **Cross-validation**: the technical note's Table 2 macro SAM equals the kind-level macro-SAM computed independently by `code/05_validate_institutional_block.py` from the distributed workbook (outputs/macro_sam_by_kind.csv), cell for cell in R-billions.

## Second application: Kenya (paper v3)

## S-008 — IFPRI 2019 Nexus SAM for Kenya — OBTAINED

| Field | Value |
| --- | --- |
| Publisher | IFPRI (Nexus Project); Thurlow (2021) |
| Data | Harvard Dataverse doi:10.7910/DVN/ALUXSI — obtained 2026-07-17: `raw/kenya/ifpri/` (readme; SAM CSV, SHA-256 `a949a1e6…b08cc3`; population). Structural audit passed: 108 accounts in 11 label-groups matching the data paper; **all 2,086 published values are integers (Sh billions)** — the distributed matrix is a rounded presentation, so its own balance holds only to rounding (max gap Sh 5bn ≈ 0.06% of GDP), a fact for the replicability-profile section |
| License | CC-BY-4.0 (redistributable, unlike S-003) |
| Documentation | Data paper obtained: `raw/kenya/kenya_sam_datapaper.pdf` (33 pp., SHA-256 `see commit`), CC-BY |
| Method note | Nexus SAMs are **cross-entropy reconciled** (Robinson et al. 2001): exact cell-level replication is not expected by construction; the Kenya application audits macro-control replication and documents CE as a distinct replicability profile |
| Sources per Table 9 | 2009 SUT (KNBS 2014); 2009-rebased GDP series + Economic Survey 2020 tables (KNBS 2020); government finance (Economic Survey 2019); IMF BPM6 BoP; World Bank WDI; FAOSTAT; COMTRADE; UNCTAD TRAINS; KIHBS 2015/16 |

## S-009 — KNBS 2009 SUT — OBTAINED (CONDENSED); DETAILED VERSION HELD BY KNBS

**Corrected 2026-07-17** (initial conclusion "not publicly distributed" was too strong; condensed publication located with external search assistance). The 2009 SUT, produced during the 2014 GDP rebasing, has a three-tier public record, all in `raw/kenya/knbs/`:

1. **Condensed SUT published in print**: Economic Survey 2014, chapter 17 (pp. 266–279), Tables 17.8 (supply) and 17.9 (use) at broad product-group level; full ES 2014 (322 pp., SHA-256 `6d…` per commit) and a 14-page chapter extract (SHA-256 `e12fe005…b394`). Text-extractable; provides public supply-side control totals (output, imports, margins, product taxes by product group).
2. **Methodology**: the two rebasing reports (Revision & Rebasing; Sources & Methods — the latter states the revision classified 86 industries and 153 products).
3. **The detailed balanced SUT (151 products × 81 industries) is compiled but not distributed** — ES 2014 ¶17.22 verbatim: "A detailed balanced SUT consisting of 151 products by 81 industries has been compiled and the results are available at KNBS."

Replicability finding, refined: Kenya's SUT is public only at condensed level; the detailed table used by the Nexus SAM is available on request, not distributed. Between South Africa (full SUT as Excel) and a no-publication regime, Kenya sits in the middle tier — print-condensed with detail on request.

## S-010 — KNBS Economic Survey 2020 + 2019 — OBTAINED

`raw/kenya/knbs/2020-Economic-Survey.pdf` (SHA-256 `aa52bbb8…873a8a2b`) and `2019-Economic-Survey.pdf`, obtained 2026-07-17. Rebased GDP series (Tables 2.1–2.7, 2.12a), sector detail (7.17, 8.8, 10.3), government accounts (5.3–5.4). Used in `code/14_kenya_audit.py` stage 2: 2019 current-price controls transcribed from Table 2.1 (p. 26: GVA, taxes on products, GDP mp) and Table 2.7 (p. 33: expenditure components and the KSh −352bn production-vs-expenditure discrepancy).

## Third application: Netherlands (paper v3)

## S-011 — Eurostat NL 2019: supply-use tables and sector accounts — OBTAINED

| Field | Value |
| --- | --- |
| Publisher | Eurostat (ESA 2010 transmission programme); free reuse with attribution |
| Acquisition | **100% programmatic** via the Eurostat dissemination API (statistics/1.0), 2026-07-17 — no browser, no manual step; fetch commands recorded in the audit script |
| Files | `raw/netherlands/naio_10_cp15_NL_2019.json` (supply table at basic prices incl. transformation, 114 industries x 111 products, 5,237 values); `naio_10_cp16_NL_2019.json` (use table at purchasers' prices, 121 use columns incl. P3_S13/S14/S15, P51G, P52, P53, P6, x 120 rows incl. the full VA block B1G/D1/D29X39/B2A3G, 6,106 values); `nasa_10_nf_tr_NL_2019.json` (non-financial transactions, 132 ESA items x 14 institutional sectors x paid/received, 1,290 values) |
| SHA-256 | `raw/netherlands/naio_10_cp15_NL_2019.json` `cefd02794843d898f85b2e87c492d7798f62b7fea91a9f84f9ffbb2c7340ba1f`; `naio_10_cp16_NL_2019.json` `f0bdbb317792fd7da61a6141bc523e52287063acd4a061ed6a3b1c429b58810a`; `nasa_10_nf_tr_NL_2019.json` `aaa52b563491bb3606e58a9a6b8de36b8589499010218d5d013482c537dbbafc` (recorded 2026-07-19; these files are committed, so the hashes are verifiable directly from the package) |
| Purpose | Third application: benchmark-free SAM generation — tests the toolkit as a generator (no benchmark to crib concordances or formulas from), with acquisition cost effectively zero |
| Notes | Imports per product derivable from TS_BP minus domestic output (DOM/IMP stk_flow splits not populated for NL); margins column OTTM; adjustment rows (OP_RES, ADJ_P6/P7) present and to be handled explicitly |

## Folder policy

- `raw/` — committed to the repository (currently private): official public statistics, unmodified.
- `external/` — **not** committed (`.gitignore`): third-party files with unconfirmed redistribution rights; registered here by URL + hash instead.
- Before this repository is ever made public, re-check every license above; anything unclear moves to `external/`.
