# Supply-side validation report

Generated 2026-07-16 by code/02_validate_supply_side.py.

## Internal consistency of the official supply table (S-001)

- Products: 108; industries: 124
- Row identity (purchasers' = basic + taxes + margins) and column-total checks: **0 findings** at R0.5m tolerance

## Benchmark SAM integrity (S-003)

- Accounts: 210; balance check (|column sum - row sum|): max R0.000m -> balanced
- 'a*' block classified by explicit rules: 61 activities; excluded as non-activity: atx

## Concordance (S-003 Industry_List)

- 124 SUT industries -> 61 SAM activity accounts; validation problems: 0

## SUT output vs benchmark SAM activity totals

- Matched accounts: 61; unmatched: none
- Aggregate over matched: SUT R11,036,678m vs SAM R11,036,678m (+0.0000%)
- Within 1%: 61/61; median |dev| 0.0000%; max |dev| 0.0000%

### Largest deviations

| Account | Label | SUT (Rm) | SAM (Rm) | Dev % |
|---|---|---|---|---|
| aglss | Glass | 10,158 | 10,158 | -0.0000 |
| aomnf | Manufacturing n.e.c, recycling | 55,010 | 55,010 | -0.0000 |
| aweav | Spinning, weaving and finishing of t | 27,971 | 27,971 | +0.0000 |
| arubb | Rubber | 21,057 | 21,057 | -0.0000 |
| aelcg | Electricity, gas, steam and hot wate | 274,785 | 274,785 | -0.0000 |
| amach | Machinery and equipment | 138,678 | 138,678 | -0.0000 |
| abchm | Nuclear fuel, basic chemicals | 107,759 | 107,759 | -0.0000 |
| amorg | Activities of membership organisatio | 18,633 | 18,633 | +0.0000 |
| awtrd | Wholesale trade, commission trade | 468,973 | 468,973 | -0.0000 |
| afish | Fishing | 20,116 | 20,116 | -0.0000 |

Full table: supply_validation.csv.
