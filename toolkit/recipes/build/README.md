# Build recipe

Build a validated macro social accounting matrix from public data with one
command — no benchmark SAM, no spreadsheet, no manual download.

```bash
python build_sam.py --country AT --year 2019
```

That fetches Austria's 2019 supply table, use table, and non-financial
sector accounts from the Eurostat dissemination API (three requests,
~200KB, cached in `data/`), generates an 18-account macro SAM, and writes
two files to `output/`:

- `AT_2019_macro_sam.csv` — the matrix in long form (row, col, EUR million)
- `AT_2019_generation.md` — the validation report

It works for any country and year in the ESA 2010 transmission programme
(the EU members plus several others — roughly 30 countries, most years
from 2010 on). Requires Python 3.10+; no packages beyond the standard
library and `edikit` (this repository, no install needed — the script
finds it relatively). If the download fails with an SSL certificate
error (common with macOS framework Python), `pip install certifi` and
rerun.

Countries whose tables carry suppressed (confidential) cells — Poland,
for example — still work: the macro SAM anchors to the published totals,
and the report quantifies exactly how much detail is withheld and which
identity checks that suppression touches.

## What you get, and what the checks mean

The generation is *benchmark-free*: nothing is copied from any published
SAM. Correctness therefore rests on the accounting identities the pipeline
enforces, all reported in `*_generation.md`:

1. **Supply-use identities** — output and value-added identities for every
   industry, the import identity, and the supply-demand balance of every
   product, each at a EUR 1m tolerance. For a well-maintained statistical
   system these close exactly; any finding is listed.
2. **Account residuals** — every account's row total minus column total,
   in EUR and as a share of GDP. The production, tax, capital, and
   instrument accounts close exactly by construction; the institutional
   accounts (households, corporations, government, labour, rest of world,
   savings-investment) typically carry residuals of a fraction of a
   percent of GDP that attach to known ESA boundary items (the
   domestic-vs-national concept in compensation, mixed-income attribution,
   capital-account detail). They are **reported, not balanced away** — if
   you need an exactly balanced matrix, apply the RAS routine in
   `edikit.model.balancing`, which logs the adjustment factor of every
   cell it touches.

The design rules behind the account structure (N1–N4: instrument accounts
for inter-institutional flows, sector definitions, the import identity as
cross-check, explicit routing of the residents-abroad and cif/fob
adjustment rows) are documented in `edikit/pipeline/eurostat_sam.py` and
in the accompanying working paper.

## Adapting beyond Eurostat

For a country outside the ESA transmission programme, the API stage is
replaced by your country's published files; everything downstream reuses
the same toolkit machinery. The working paper's South Africa pipeline
(`papers/P001-za-sam/code/`, scripts 01–12) is the worked example of the
full pattern:

1. **Register your sources** — every raw file with vintage, URL, and
   SHA-256 hash (see `papers/P001-za-sam/data/SOURCES.md` for the format).
2. **Read and verify the SUT** — `edikit.data.sut` shows the pattern for
   an Excel-published supply-use table: recompute embedded totals, enforce
   the output/VA/supply identities before using a single number.
3. **Classify explicitly** — never by code prefix or label; build one
   reviewable account-classification table with a coverage assertion
   (`edikit.model.accounts`). The paper documents what happens otherwise.
4. **Institutional cells as formulas** — transcribe your national-accounts
   sources into a machine-readable formula table (one row per SAM cell)
   rather than hand-copying numbers; see the South African KBP formula
   table for the pattern.
5. **Balance with a log** — `edikit.model.balancing` (RAS with per-cell
   factor diagnostics), and publish the factors with the matrix.

The one rule that carries the whole kit: **every choice a reader cannot
see is a choice they cannot check.** Register sources, enforce identities,
report residuals.

## Extending the macro SAM

The macro SAM is deliberately the common denominator. Disaggregation —
industries and products (the API serves the full 65×65 core), household
groups from a budget survey, occupational labour from a labour-force
survey — follows the South African scripts 07–11 pattern: survey-based
share systems applied under numbered, disclosed rules, then a logged
balancing step.
