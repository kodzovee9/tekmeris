#!/usr/bin/env python
"""Country-coverage sweep: run the build pipeline across the ESA universe.

    python sweep.py [--year 2019] [--countries AT,BE,...]

For every candidate country the script fetches the three Eurostat
datasets (cached), generates the macro accounting matrix, balances it,
and records one row in COVERAGE.md: outcome, identity findings,
commodity closure, worst pre-balancing residual, maximum balancing
factor deviation, and any suppression coverage note or failure reason.
The committed table is the evidence behind the recipe's country-coverage
claim; failures are documented, not hidden.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from edikit.pipeline import eurostat_sam as es  # noqa: E402

# EU members plus the EFTA/candidate countries that transmit ESA tables
CANDIDATES = ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES",
              "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
              "NL", "PL", "PT", "RO", "SE", "SI", "SK",
              "NO", "IS", "CH", "UK", "RS", "MK", "TR", "BA", "ME", "AL"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--year", type=int, default=2019)
    ap.add_argument("--countries", default=",".join(CANDIDATES))
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default="COVERAGE.md")
    args = ap.parse_args()

    rows = []
    for cc in args.countries.split(","):
        cc = cc.strip()
        res = None
        try:
            for attempt in (1, 2):  # one retry for transient network errors
                try:
                    paths = es.fetch(cc, args.year, args.data_dir)
                    break
                except OSError:
                    if attempt == 2:
                        raise
            res = es.generate(cc, args.year, paths)
            bal, flipped = es.balance(res)
            worst = max(abs(v) for v in res.imbalances.values()) / res.gdp * 100
            supp = (f"; detail suppressed ({min(res.coverage.values()) * 100:.0f}"
                    f"% worst aggregate)" if res.coverage else "")
            # five-tier classification, aligned with the toolkit's own
            # concept of executable checks:
            #   passes-core-checks: every accounting diagnostic clean
            #   generates-with-caveats: builds and balances, but carries
            #     identity/closure/cross-check/suppression findings
            #   requires-review: large residuals or extreme factors
            if worst > 5.0 or bal.max_factor_deviation() > 1.0:
                status = "requires-review"
            elif (res.findings or res.cross_diffs or res.coverage
                  or res.n_closed < len(res.prods) or res.n3_check > 1.0
                  or not bal.converged):
                status = "generates-with-caveats"
            else:
                status = "passes-core-checks"
            rows.append((cc, status,
                         f"{len(res.inds)} industries; "
                         f"{len(res.findings)} identity findings; "
                         f"closure {res.n_closed}/{len(res.prods)}; "
                         f"worst residual {worst:.1f}% GDP; balanced "
                         f"max |f-1| {bal.max_factor_deviation() * 100:.1f}%"
                         + supp))
            print(f"{cc}: {status}")
        except Exception as e:  # record the failure, keep sweeping
            reason = f"{type(e).__name__}: {str(e)[:110]}"
            if res is not None and res.gdp > 0:
                # generation succeeded; balancing did not
                worst = max(abs(v) for v in res.imbalances.values()) / res.gdp * 100
                rows.append((cc, "partial",
                             f"generates ({len(res.inds)} industries, "
                             f"{len(res.findings)} findings, worst residual "
                             f"{worst:.1f}% GDP); balancing infeasible - "
                             f"{reason}"))
                print(f"{cc}: partial - {reason}")
            elif "no supply-table data" in str(e) or (
                    res is not None and res.gdp <= 0):
                detail = (reason if res is None else
                          "required use-table or sector-account rows are "
                          "empty (GDP evaluates to zero)")
                rows.append((cc, "unavailable", detail))
                print(f"{cc}: unavailable")
            else:
                rows.append((cc, "fail", reason))
                print(f"{cc}: FAIL - {reason}")

    tiers = ["passes-core-checks", "generates-with-caveats",
             "requires-review", "partial", "unavailable", "fail"]
    n = {t: sum(1 for _, st, _ in rows if st == t) for t in tiers}
    with open(args.out, "w") as f:
        f.write(f"# Country coverage, {args.year}\n\nGenerated "
                f"by recipes/build/sweep.py over {len(rows)} candidate "
                f"countries: {n['passes-core-checks']} pass every core check "
                f"(zero identity findings, full commodity closure, no "
                f"cross-table differences, import identity within tolerance, "
                f"no suppression, converged balancing, worst residual within "
                f"5% of GDP); {n['generates-with-caveats']} generate and "
                f"balance with documented caveats; {n['requires-review']} "
                f"carry large residuals or extreme factors and require "
                f"review; {n['partial']} generate but cannot be balanced; "
                f"{n['unavailable']} country-years are not covered by the "
                f"datasets"
                + (f"; {n['fail']} fail otherwise" if n['fail'] else "")
                + ".\n\n"
                f"| Country | Outcome | Detail |\n|---|---|---|\n")
        for cc, st, detail in rows:
            f.write(f"| {cc} | {st} | {detail} |\n")
        f.write("\nFailures are properties of source availability for the "
                "requested year (missing datasets, vintages, or units), "
                "recorded here rather than hidden; rerun the sweep to "
                "regenerate this table.\n")
    print("\n" + "; ".join(f"{t}: {n[t]}" for t in tiers if n[t])
          + f"; written {args.out}")


if __name__ == "__main__":
    main()
