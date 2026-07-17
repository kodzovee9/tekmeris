"""Institutional-block validation: final demand and the macro-SAM.

Two exercises, both powered by the complete account map from 04:

1. Final-demand reconciliation. The SUT use table's final-demand columns are
   compared per commodity with the SAM's institutional spending blocks:
   Households vs c x (hhd1..hhd14), General government vs c x gvt, Exports vs
   c x row, Fixed capital formation vs c x si, and Changes in inventories +
   Residual vs c x dstk (whose own dictionary entry is 'Change in
   stocks+resid').

2. The macro-SAM. The full 209x209 matrix is aggregated to account kinds
   (activity, commodity, factor, household, ...), giving a 10x10 picture of
   the economy's institutional structure - who pays whom, in R'million -
   that doubles as a readable summary of what the institutional block must
   reproduce when P001 constructs it from primary sources.

Run from this directory, after 01 and 04:
    python 05_validate_institutional_block.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.concordance import Concordance  # noqa: E402
from edikit.data.sam import read_labeled_matrix  # noqa: E402
from edikit.data.sut import read_use_table  # noqa: E402

DATA = Path(__file__).parents[1] / "data"
OUT = Path(__file__).parents[1] / "outputs"
SUT_XLSX = DATA / "raw" / "statssa" / "Supply and use tables 2018 - 2019.xlsx"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"

# SUT final-demand category -> SAM spender account codes
FD_MAP: dict[str, list[str]] = {
    "Households": [f"hhd{i}" for i in range(1, 15)],
    "General government": ["gvt"],
    "Exports": ["row"],
    "Fixed capital formation": ["si"],
    "Changes in inventories + Residual": ["dstk"],
}
KIND_ORDER = ["activity", "commodity", "margin", "factor", "enterprise",
              "household", "government", "tax", "savings_investment",
              "rest_of_world"]


def load_account_kinds() -> dict[str, str]:
    kinds = {}
    with open(DATA / "derived" / "sam_account_map.csv", newline="") as f:
        for row in csv.DictReader(f):
            kinds[row["code"]] = row["kind"]
    return kinds


def main() -> None:
    use = read_use_table(str(SUT_XLSX), 2019)
    pconc = Concordance.from_csv(str(DATA / "derived" / "concordance_products.csv"))
    sam = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    kinds = load_account_kinds()

    # --- 1. Final-demand reconciliation, per commodity ---
    sut_fd: dict[str, dict[str, float]] = {}
    for (pcode, cat), v in use.final_demand.items():
        key = ("Changes in inventories + Residual"
               if cat in ("Changes in inventories", "Residual") else cat)
        if key not in FD_MAP:
            continue
        sut_fd.setdefault(key, {})[pcode] = sut_fd.get(key, {}).get(pcode, 0.0) + v

    sam_fd: dict[str, dict[str, float]] = {cat: {} for cat in FD_MAP}
    for (r, c), v in sam.cells.items():
        if kinds.get(r) != "commodity":
            continue
        for cat, spenders in FD_MAP.items():
            if c in spenders:
                sam_fd[cat][r] = sam_fd[cat].get(r, 0.0) + v

    results = []
    for cat in FD_MAP:
        sut_by_comm = pconc.aggregate(sut_fd.get(cat, {}))
        sam_by_comm = sam_fd[cat]
        comms = set(sut_by_comm) | set(sam_by_comm)
        diffs = {cc: sam_by_comm.get(cc, 0.0) - sut_by_comm.get(cc, 0.0) for cc in comms}
        exact = sum(1 for d in diffs.values() if abs(d) < 0.5)
        tot_s, tot_b = sum(sut_by_comm.values()), sum(sam_by_comm.values())
        worst = sorted(diffs.items(), key=lambda x: -abs(x[1]))[:3]
        results.append((cat, tot_s, tot_b, exact, len(comms), worst))

    # --- 2. Macro-SAM by account kind ---
    macro: dict[tuple[str, str], float] = {}
    for (r, c), v in sam.cells.items():
        kr, kc = kinds.get(r), kinds.get(c)
        if kr and kc:
            macro[(kr, kc)] = macro.get((kr, kc), 0.0) + v

    with open(OUT / "macro_sam_by_kind.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["receives\\pays"] + KIND_ORDER)
        for kr in KIND_ORDER:
            w.writerow([kr] + [round(macro.get((kr, kc), 0.0), 1) for kc in KIND_ORDER])

    # --- Report ---
    OUT.mkdir(exist_ok=True)
    with open(OUT / "institutional_validation.md", "w") as f:
        f.write(f"# Institutional-block validation report\n\nGenerated {date.today()} "
                f"by code/05_validate_institutional_block.py.\n\n")
        f.write("## Final demand: SUT categories vs SAM institutional spending\n\n")
        f.write("| Category | SUT (Rm) | SAM (Rm) | Gap (Rm) | Commodities exact |\n")
        f.write("|---|---|---|---|---|\n")
        for cat, ts, tb, exact, n, _ in results:
            f.write(f"| {cat} | {ts:,.0f} | {tb:,.0f} | {tb - ts:+,.0f} | {exact}/{n} |\n")
        f.write("\n### Largest commodity-level gaps per category\n\n")
        for cat, _, _, exact, n, worst in results:
            if exact < n:
                items = ", ".join(f"{cc} {d:+,.0f}m" for cc, d in worst if abs(d) >= 0.5)
                f.write(f"- **{cat}**: {items}\n")
        f.write("\n## The macro-SAM (kind x kind, R'million)\n\n")
        f.write("Rows receive, columns pay. Full table: macro_sam_by_kind.csv.\n\n")
        f.write("| receives \\\\ pays | " + " | ".join(k[:9] for k in KIND_ORDER) + " |\n")
        f.write("|" + "---|" * (len(KIND_ORDER) + 1) + "\n")
        for kr in KIND_ORDER:
            cells = [f"{macro.get((kr, kc), 0.0):,.0f}" if macro.get((kr, kc)) else ""
                     for kc in KIND_ORDER]
            f.write(f"| {kr} | " + " | ".join(cells) + " |\n")
        f.write("\nReading guide: factor rows are paid by activities (value added) and "
                "pay households/enterprises (income distribution); government is paid "
                "by taxes and pays commodities (consumption) and households (transfers); "
                "savings_investment collects savings and pays commodities (investment).\n")

    for cat, ts, tb, exact, n, _ in results:
        print(f"{cat:36s} SUT {ts:14,.0f}  SAM {tb:14,.0f}  gap {tb-ts:+12,.0f}  exact {exact}/{n}")


if __name__ == "__main__":
    main()
