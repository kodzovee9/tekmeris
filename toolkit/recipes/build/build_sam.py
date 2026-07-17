#!/usr/bin/env python
"""Build a validated macro SAM for any ESA-transmitting country.

    python build_sam.py --country AT --year 2019

fetches the country's supply table, use table, and sector accounts from
the Eurostat dissemination API (three requests, reused if already on
disk), generates a macro SAM with no benchmark consulted, and writes:

    output/<COUNTRY>_<YEAR>_macro_sam.csv    the matrix (row, col, EURm)
    output/<COUNTRY>_<YEAR>_generation.md    the validation report

Every accounting-identity check and every account residual is in the
report; nothing is balanced away silently. See README.md for what the
checks mean and how to adapt the kit beyond the Eurostat universe.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from edikit.pipeline import eurostat_sam  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--country", required=True,
                    help="Eurostat geo code, e.g. NL, AT, PL, DE")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--data-dir", default="data",
                    help="where raw API responses are stored (default: data/)")
    ap.add_argument("--out-dir", default="output")
    args = ap.parse_args()

    print(f"fetching {args.country} {args.year} (cached files reused)...")
    paths = eurostat_sam.fetch(args.country, args.year, args.data_dir)
    res = eurostat_sam.generate(args.country, args.year, paths)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{args.country}_{args.year}"
    eurostat_sam.write_csv(res, out / f"{stem}_macro_sam.csv")
    eurostat_sam.write_report(res, out / f"{stem}_generation.md")
    bal, flipped = eurostat_sam.balance(res)
    with open(out / f"{stem}_macro_sam_balanced.csv", "w", newline="") as f:
        import csv
        w = csv.writer(f)
        w.writerow(["row", "col", "value_EURm", "ras_factor"])
        for (r, c), v in sorted(bal.matrix.items()):
            w.writerow([r, c, f"{v:.1f}", f"{bal.factors.get((r, c), 1.0):.6f}"])

    print(f"industries {len(res.inds)}; products {len(res.prods)}; "
          f"identity findings {len(res.findings)}; "
          f"commodity closure {res.n_closed}/{len(res.prods)}")
    print(f"macro SAM: {len(res.accounts)} accounts, "
          f"GDP(bp) EUR {res.gdp:,.0f}m")
    for a, v in sorted(res.imbalances.items(), key=lambda x: -abs(x[1]))[:6]:
        print(f"  {a:5s} {v:+12,.0f}  ({v / res.gdp * 100:+.2f}% GDP)")
    print(f"balanced: converged={bal.converged}; max |factor-1| "
          f"{bal.max_factor_deviation() * 100:.2f}%"
          + (f"; flipped {flipped}" if flipped else ""))
    print(f"written: {out / (stem + '_macro_sam.csv')}, "
          f"{out / (stem + '_generation.md')}")


if __name__ == "__main__":
    main()
