# Build recipe

Generate a balanced macro social accounting matrix from Eurostat data with
one command. No benchmark SAM, spreadsheet or manual download is needed.

```bash
python build_sam.py --country DK --year 2019
```

The command fetches Denmark's 2019 supply table, use table and non-financial
sector accounts from the Eurostat dissemination API (three requests of about
200 KB, cached in `data/`). It then generates an 18-account macro accounting
matrix, balances it, and writes three files to `output/`:

- `DK_2019_macro_sam.csv` is the matrix before balancing, in long form (row,
  col, EUR million).
- `DK_2019_macro_sam_balanced.csv` is the balanced matrix with the RAS
  adjustment factor of every cell. A `note` column marks closing entries and
  cells flipped from a negative.
- `DK_2019_generation.md` is the validation report.

Options:

| Option | Effect |
|---|---|
| `--targets {mean,receipts,payments}` | Sets the balancing target per account (default `mean`). |
| `--decimals N` | Sets the CSV rounding, in decimal places of EUR million (default 1). |

The workflow covers country-years in the ESA 2010 transmission programme
with the required Eurostat tables. [COVERAGE.md](COVERAGE.md) records a sweep
of 37 candidate countries for 2019 and the data vintages it used. Eurostat
revises these datasets, so outcomes can change on later data; regenerate the
table with `python sweep.py`. `examples/` holds five runs with their inputs,
which reproduce offline.

Requires Python 3.11+ and edikit. If the download fails with an SSL
certificate error (common with macOS framework Python), run
`pip install certifi` and try again.

## What the report shows

The generation is *benchmark-free*: nothing is copied from any published
SAM. The report records what the checks found. Recording a finding does not
fix it, and accounting consistency does not make the matrix economically
right for a given model.

1. **Supply-use identities.** For every industry, the output and
   value-added identities; the import identity; and the supply-demand balance
   of every product, each at a EUR 1m tolerance. Every finding is listed.
   Where cells are suppressed, findings can reflect the suppression rather
   than errors.
2. **Unpublished inputs.** Sector-account items the source publishes on
   neither side are used as zero and listed. Any account they feed is
   unreliable.
3. **Cross-source consistency.** Several aggregates are measured by both the
   supply-use tables and the sector accounts: gross value added,
   compensation, operating surplus and household consumption. The report shows
   both measurements and the vintage of each dataset.
4. **Account residuals.** Every account's receipts minus payments, with the
   items computed from the inputs that bear on each residual:
   - cross-source gaps;
   - net capital transfers, which the account design leaves in the
     institutions' accounts;
   - taxes collected by the rest of the world;
   - non-produced assets.

   The report also shows what those items leave unexplained.
5. **The closing entry.** The capital factor account is closed by a residual
   booked against the rest of the world. That residual measures the
   difference between the two datasets' operating-surplus figures, and it
   also appears in the rest-of-world residual.
6. **Balancing.** The report gives convergence, flipped cells, the range of
   adjustment factors, and GDP before and after balancing.

The design rules behind the account structure are documented in
`edikit/pipeline/eurostat_sam.py`. They cover instrument accounts for
inter-institutional flows, sector definitions, the import identity as a
cross-check, and the routing of the residents-abroad and cif/fob
adjustment rows.

## Beyond Eurostat

Outside a harmonized statistical system, building a SAM is a different and
larger job. It needs readers for the national sources, mappings from their
classifications to SAM accounts, rules for allocating flows the sources do
not report, and decisions about conflicting sources. edikit supplies the
parts that transfer: explicit classification, concordances, balancing with a
per-cell log, source verification, and live-formula workbooks. The economic
decisions remain the analyst's.

The companion paper's South Africa scripts (`papers/P001-sut-to-sam/code/`)
are one worked instance of those decisions. They show the shape of the work,
not settings to change for another country. For example:

- sources registered in `SOURCES.md`, with a `SOURCES.sha256` manifest that
  `edikit.data.provenance.verify_sources` checks;
- a reader for one publisher's SUT layout (`edikit.data.sut`), whose
  `check_*` functions report identity findings;
- one reviewable account-classification table, applied with
  `edikit.model.accounts.classify_by_prefix`, which raises on an unmatched
  code;
- institutional cells transcribed as formulas rather than copied numbers;
- balancing with the factor of every cell published.

## Extending the macro SAM

The macro SAM is a common denominator, not a SAM ready for a particular
model. Disaggregating it by industry and product (the API serves the full
65-industry core), by household group from a budget survey, or by occupation
from a labor-force survey requires survey-based allocation rules and a
further balancing step.
