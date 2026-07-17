"""Balance SAM v0.1 -> v0.2: RAS on the household income block.

v0.1's imbalances sit entirely in the 14 household groups: proxy income
shares (rules R5/R6) do not match each group's outlays. The well-posed fix
is biproportional: hold every payer's total transfer to households fixed
(these are documented macro cells) and each group's total outlays fixed
(consumption and payment cells stay untouched), then RAS the 14 x 27
household income block so each group's income equals its outlays.

The report also answers a question the paper cares about: does balancing
move the income block TOWARD the benchmark's (item-share-based) values?

Run from this directory, after 10:  python 11_balance_sam.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.sam import read_labeled_matrix  # noqa: E402
from edikit.model.balancing import ras  # noqa: E402

OUT = Path(__file__).parents[1] / "outputs"
DATA = Path(__file__).parents[1] / "data"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"
HHDS = [f"hhd{i}" for i in range(1, 15)]


def load_sam(path) -> dict[tuple[str, str], float]:
    sam = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            sam[(r["row"], r["col"])] = float(r["value_Rm"])
    return sam


def imbalances(sam) -> dict[str, float]:
    rowsum, colsum = {}, {}
    for (r, c), v in sam.items():
        rowsum[r] = rowsum.get(r, 0.0) + v
        colsum[c] = colsum.get(c, 0.0) + v
    return {a: rowsum.get(a, 0.0) - colsum.get(a, 0.0)
            for a in set(rowsum) | set(colsum)}


def main() -> None:
    sam = load_sam(OUT / "p001_sam_v01.csv")
    imb0 = imbalances(sam)

    # household income block and its targets
    block = {(r, c): v for (r, c), v in sam.items() if r in HHDS}
    payers = sorted({c for (_, c) in block})
    col_targets = {}
    for (_, c), v in block.items():
        col_targets[c] = col_targets.get(c, 0.0) + v
    outlays = {g: sum(v for (r, c), v in sam.items() if c == g) for g in HHDS}

    tot_income, tot_outlay = sum(col_targets.values()), sum(outlays.values())
    agg_gap_pct = (tot_income - tot_outlay) / tot_outlay * 100
    # tiny aggregate gap (documented macro deviations): scale row targets
    row_targets = {g: v * tot_income / tot_outlay for g, v in outlays.items()}

    res = ras(block, row_targets, col_targets)
    assert res.converged, "RAS failed to converge"

    sam2 = {k: v for k, v in sam.items() if k[0] not in HHDS}
    sam2.update(res.matrix)
    imb1 = imbalances(sam2)

    # does balancing move the block toward the benchmark?
    bench = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    def block_dev(m):
        devs = [abs(m.get((g, p), 0.0) - bench.cells.get((g, p), 0.0))
                for g in HHDS for p in payers]
        return sum(devs) / len(devs)
    dev_before, dev_after = block_dev(block), block_dev(res.matrix)

    with open(OUT / "p001_sam_v02.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row", "col", "value_Rm"])
        for (r, c), v in sorted(sam2.items()):
            w.writerow([r, c, f"{v:.3f}"])

    facs = sorted(res.factors.values())
    hh_imb0 = max(abs(imb0[g]) for g in HHDS)
    hh_imb1 = max(abs(imb1.get(g, 0.0)) for g in HHDS)
    rest1 = max(abs(v) for a, v in imb1.items() if a not in HHDS)

    with open(OUT / "balance_report.md", "w") as f:
        f.write(f"# SAM v0.2 balancing report\n\nGenerated {date.today()} by "
                f"code/11_balance_sam.py.\n\n")
        f.write(f"- Household income block: {len(block)} cells, 14 groups x "
                f"{len(payers)} payers; aggregate income/outlay gap before "
                f"balancing: {agg_gap_pct:+.4f}% (row targets scaled accordingly)\n")
        f.write(f"- RAS: converged in {res.iterations} iterations; max residual "
                f"gap R{max(res.max_row_gap, res.max_col_gap):,.6f}m\n")
        f.write(f"- Household imbalance: max R{hh_imb0:,.0f}m before -> "
                f"R{hh_imb1:,.3f}m after\n")
        f.write(f"- Largest remaining imbalance outside households: R{rest1:,.0f}m\n")
        f.write(f"- Adjustment factors: median {facs[len(facs)//2]:.3f}, "
                f"range [{facs[0]:.3f}, {facs[-1]:.3f}]\n")
        f.write(f"- Mean |cell difference| vs benchmark household block: "
                f"R{dev_before:,.1f}m before -> R{dev_after:,.1f}m after "
                f"({'toward' if dev_after < dev_before else 'away from'} the "
                f"benchmark)\n")
    print(f"RAS converged in {res.iterations} iters; hh imbalance "
          f"R{hh_imb0:,.0f}m -> R{hh_imb1:,.3f}m; other max R{rest1:,.0f}m")
    print(f"factors median {facs[len(facs)//2]:.3f} range [{facs[0]:.3f}, {facs[-1]:.3f}]")
    print(f"benchmark distance: R{dev_before:,.1f}m -> R{dev_after:,.1f}m")


if __name__ == "__main__":
    main()
