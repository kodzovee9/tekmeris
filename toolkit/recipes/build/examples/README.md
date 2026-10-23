# Worked examples: macro SAMs for five countries, 2019

The edikit metapaper reports the BE, DK, FR and ES runs. The NL run is the
one used in the companion paper. Everything needed to rerun all five is here,
and no network access is required.

| Run | Data vintage | What it shows |
|---|---|---|
| NL | July 2026 | Used in the companion paper, not in the metapaper. Its inputs are pinned to the vintage that paper used. |
| BE | October 2026 | Passes every core check. |
| DK | October 2026 | Passes every core check. The two Eurostat datasets agree, so the capital-factor closing entry is negligible. |
| FR | October 2026 | Passes every core check. The datasets differ by 0.9% on gross value added, and the report sets that difference beside the residuals it bears on. |
| ES | October 2026 | A failure the generator detects. This vintage publishes no general-government sector accounts for Spain, so the report lists the missing items and balancing does not converge. |

## Inputs (`inputs/`)

Fifteen Eurostat dissemination-API responses, three per country:

| Dataset | Content |
|---|---|
| `naio_10_cp15` | supply table at basic prices, with the transformation to purchasers' prices |
| `naio_10_cp16` | use table at purchasers' prices |
| `nasa_10_nf_tr` | non-financial transactions by institutional sector |

They are cached as `fetch()` saved them. Eurostat permits reuse with
attribution (source: Eurostat), so they are redistributed here unmodified.
Each report records its datasets' vintage stamps. `inputs/SOURCES.sha256`
registers every file, in `sha256sum` format:

```
shasum -a 256 -c SOURCES.sha256          # standard tools, no Python
```

## Rerunning

From `toolkit/recipes/build/`:

```
python build_sam.py --country DK --year 2019 --data-dir examples/inputs --out-dir out
```

Because the inputs are cached, `fetch()` reuses them instead of calling the API,
and the outputs reproduce `output/` byte for byte. `--targets receipts` or
`--targets payments` shows how the balancing target moves the balanced matrix.
`--decimals` sets the CSV rounding.

Fetching the same country today may give different results. Eurostat revises
these datasets, and the coverage table (`../COVERAGE.md`) records the vintages
it was built from.

## Reading a report

Each report in `output/` includes:
- every identity finding;
- any sector-account items the source does not publish;
- the aggregates both datasets measure, side by side, with their vintages;
- for each account residual, the items computed from the inputs that bear on
  it, and what they leave unexplained;
- the capital-factor closing entry;
- the cells flipped before balancing;
- how far balancing moves GDP.

The balanced CSV's `note` column marks closing entries and flipped cells.

These runs show that the generator executes as documented and that its output
is accounting-consistent. They do not show that a balanced macro SAM is the
right matrix for a particular model.
