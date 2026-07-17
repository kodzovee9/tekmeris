# AT 2019: benchmark-free macro-SAM generation

Generated 2026-07-17 by edikit.pipeline.eurostat_sam from the Eurostat dissemination API; no benchmark consulted.

## Internal validation of the Eurostat SUT

- Industries: 65; products: 65
- Output and VA identities: 0 findings at EUR 1m tolerance
- Supply-vs-use output cross-check: 0 industries differ (>EUR 1m)
- Import identity cross-check (TS_BP = domestic + imports): max gap EUR 0.1m
- Commodity balance closure: 65/65 products within EUR 1m; largest residual EUR 0m
- Suppressed detail (macro cells use the published totals; the leaf detail covers):
  - intermediate consumption: 100.0%
- Note: identity findings above may reflect the same suppression (an identity cannot close over cells the source withholds), not errors in the published data.

## Generated macro SAM (18 accounts, EUR million)

- GDP at basic prices (generated): EUR 354,893m
- Account balance residuals (row minus column):

| Account | Residual (EURm) | % of GDP |
|---|---|---|
| act | +1 | +0.000% |
| atx | +0 | +0.000% |
| cap | +0 | +0.000% |
| com | -1 | -0.000% |
| corp | +1,013 | +0.285% |
| d4x | -2 | -0.001% |
| d8 | +0 | +0.000% |
| d9 | +0 | +0.000% |
| dtx | +0 | +0.000% |
| gvt | -1,360 | -0.383% |
| hhd | -1,985 | -0.559% |
| lab | +170 | +0.048% |
| ptx | +0 | +0.000% |
| row | +1,377 | +0.388% |
| si | +788 | +0.222% |
| soc_b | -1 | -0.000% |
| soc_c | -1 | -0.000% |
| trf | +1 | +0.000% |

Residuals are reported, not hidden; they typically attach to ESA boundary items (domestic-vs-national concept in compensation, mixed-income attribution, capital-account detail). Inspect any account above a few percent of GDP before use.
