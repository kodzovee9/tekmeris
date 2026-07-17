# Country coverage, 2019

Generated 2026-07-17 by recipes/build/sweep.py: 20 of 37 candidate countries generate and balance with clean diagnostics; 7 generate and balance but carry diagnostics needing review; 2 generate but cannot be balanced from one-sided sector accounts.

| Country | Outcome | Detail |
|---|---|---|
| AT | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 0.6% GDP; balanced max |f-1| 5.5%; detail suppressed (100% worst aggregate) |
| BE | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 0.7% GDP; balanced max |f-1| 8.5% |
| BG | fail | ValueError: BG 2019: no supply-table data returned (the dataset does not cover this country-year) |
| CY | ok | 63 industries; 0 identity findings; closure 63/65; worst residual 1.9% GDP; balanced max |f-1| 17.1%; detail suppressed (100% worst aggregate) |
| CZ | review | 65 industries; 0 identity findings; closure 65/65; worst residual 16.8% GDP; balanced max |f-1| 2047.4% |
| DE | review | 63 industries; 0 identity findings; closure 33/65; worst residual 19.1% GDP; balanced max |f-1| 38805.3%; detail suppressed (76% worst aggregate) |
| DK | review | 65 industries; 47 identity findings; closure 48/65; worst residual 36.0% GDP; balanced max |f-1| 36324.8%; detail suppressed (96% worst aggregate) |
| EE | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 2.2% GDP; balanced max |f-1| 27.5% |
| EL | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 1.5% GDP; balanced max |f-1| 20.9% |
| ES | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 0.4% GDP; balanced max |f-1| 3.8% |
| FI | ok | 64 industries; 0 identity findings; closure 25/64; worst residual 2.7% GDP; balanced max |f-1| 15.6% |
| FR | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 2.1% GDP; balanced max |f-1| 31.3%; detail suppressed (100% worst aggregate) |
| HR | ok | 64 industries; 0 identity findings; closure 64/64; worst residual 2.7% GDP; balanced max |f-1| 18.4% |
| HU | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 1.6% GDP; balanced max |f-1| 27.1% |
| IE | review | 49 industries; 48 identity findings; closure 49/49; worst residual 11.5% GDP; balanced max |f-1| 279.4%; detail suppressed (50% worst aggregate) |
| IT | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 1.0% GDP; balanced max |f-1| 6.7%; detail suppressed (100% worst aggregate) |
| LT | ok | 63 industries; 52 identity findings; closure 63/63; worst residual 1.2% GDP; balanced max |f-1| 11.5%; detail suppressed (78% worst aggregate) |
| LU | ok | 35 industries; 2 identity findings; closure 65/65; worst residual 4.5% GDP; balanced max |f-1| 46.2%; detail suppressed (72% worst aggregate) |
| LV | review | 64 industries; 0 identity findings; closure 65/65; worst residual 5.5% GDP; balanced max |f-1| 26.0% |
| MT | ok | 49 industries; 0 identity findings; closure 49/65; worst residual 2.8% GDP; balanced max |f-1| 9.9%; detail suppressed (73% worst aggregate) |
| NL | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 1.5% GDP; balanced max |f-1| 2.8% |
| PL | ok | 60 industries; 58 identity findings; closure 60/60; worst residual 1.1% GDP; balanced max |f-1| 11.9%; detail suppressed (93% worst aggregate) |
| PT | review | 65 industries; 0 identity findings; closure 65/65; worst residual 18.8% GDP; balanced max |f-1| 3203.2%; detail suppressed (100% worst aggregate) |
| RO | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 2.2% GDP; balanced max |f-1| 19.8% |
| SE | review | 65 industries; 58 identity findings; closure 65/65; worst residual 20.0% GDP; balanced max |f-1| 1985.6% |
| SI | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 0.9% GDP; balanced max |f-1| 10.6%; detail suppressed (100% worst aggregate) |
| SK | ok | 65 industries; 0 identity findings; closure 65/65; worst residual 0.8% GDP; balanced max |f-1| 8.3%; detail suppressed (100% worst aggregate) |
| NO | ok | 63 industries; 0 identity findings; closure 65/65; worst residual 0.3% GDP; balanced max |f-1| 0.8%; detail suppressed (97% worst aggregate) |
| IS | fail | ValueError: IS 2019: no supply-table data returned (the dataset does not cover this country-year) |
| CH | fail | ValueError: CH 2019: no supply-table data returned (the dataset does not cover this country-year) |
| UK | fail | ValueError: UK 2019: no supply-table data returned (the dataset does not cover this country-year) |
| RS | fail | ValueError: column 'dtx' has a positive target but an empty seed column |
| MK | partial | generates (64 industries, 0 findings, worst residual 76.0% GDP); balancing infeasible - ValueError: row 'si' has a positive target but an empty seed row |
| TR | fail | ValueError: TR 2019: no supply-table data returned (the dataset does not cover this country-year) |
| BA | fail | ValueError: BA 2019: no supply-table data returned (the dataset does not cover this country-year) |
| ME | fail | ValueError: ME 2019: no supply-table data returned (the dataset does not cover this country-year) |
| AL | partial | generates (65 industries, 55 findings, worst residual 41.0% GDP); balancing infeasible - ValueError: row 'soc_b' has a positive target but an empty seed row |

Failures are properties of source availability for the requested year (missing datasets, vintages, or units), recorded here rather than hidden; rerun the sweep to regenerate this table.
