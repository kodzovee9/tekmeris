#!/usr/bin/env python
"""Audit a published SAM: structure always; macro controls when supplied.

    python audit_sam.py --sam matrix.csv --format matrix --code-col \
        --kinds kinds.csv --controls controls.csv --out audit.md

Stage 1 (only --sam needed): parse the matrix, verify every account
balances, detect the file's rounding grain, and report the structure.

Stage 2 (--kinds, optionally --controls): classify accounts into
canonical kinds (activity, commodity, factor, household, enterprise,
government, tax-product, tax-direct, savings, stocks, row,
transaction-cost, other), compute the SAM's implied national aggregates,
and compare them with published controls. See README.md for how to
choose controls and read the deviations; examples/kenya/ is a complete
worked example against the IFPRI 2019 Nexus SAM.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from edikit.pipeline import audit as A  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sam", required=True, help="the distributed SAM (CSV)")
    ap.add_argument("--format", choices=("long", "matrix"), default="matrix")
    ap.add_argument("--code-col", action="store_true",
                    help="matrix format: a code column follows the labels")
    ap.add_argument("--kinds", help="account,kind CSV for macro aggregates")
    ap.add_argument("--controls", help="aggregate,value CSV of published "
                                       "national-accounts controls")
    ap.add_argument("--out", default="audit.md")
    ap.add_argument("--title", default="SAM structural audit")
    args = ap.parse_args()

    cells = (A.read_long_csv(args.sam) if args.format == "long"
             else A.read_matrix_csv(args.sam, code_col=args.code_col))
    kinds = A.read_kinds(args.kinds) if args.kinds else None
    controls = None
    if args.controls:
        with open(args.controls, encoding="utf-8-sig") as f:
            recs = list(csv.DictReader(f))
        keys = list(recs[0])
        controls = {r[keys[0]].strip(): float(r[keys[1]]) for r in recs}

    res = A.audit(cells, kinds=kinds, controls=controls)
    A.write_report(res, args.out, title=args.title)

    a, g = res.max_gap
    print(f"accounts {len(res.accounts)}; cells {res.n_cells:,}; "
          f"grain {res.grain:g}; max gap {abs(g):,.4f} ({a})")
    for k, v in res.aggregates.items():
        c = res.controls.get(k)
        dev = f"  vs control {c:,.1f} ({(v - c) / abs(c) * 100:+.1f}%)" if c else ""
        print(f"  {k}: {v:,.1f}{dev}")
    print(f"written: {args.out}")


if __name__ == "__main__":
    main()
