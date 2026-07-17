"""Use-side validation: intermediate consumption and value added vs the benchmark.

Pipeline: read the StatsSA 2019 use table (S-001), verify its internal
identities (supply = intermediate + final demand per product; output =
intermediate + B1 per industry; B1 = D1 + D2/3 + B2/3) and the cross-table
ties to the supply table. Then aggregate to the SAM's 61 activities and
compare with the benchmark's activity-column decomposition:

    activity column total = intermediates (c* rows) + atx (production taxes)
                            + factor payments (everything else)

so implied SAM value added = column total - intermediates - atx, which is
compared against SUT value added at factor cost (B1 minus D2/3, since the
SAM's factor payments exclude production taxes, which sit in atx). No
factor-account classification is needed for this comparison - a deliberate
choice until the technical note's account map is formally encoded.

Run from this directory, after 01 and 02:
    python 03_validate_use_side.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.concordance import Concordance  # noqa: E402
from edikit.data.sam import read_labeled_matrix  # noqa: E402
from edikit.data.sut import (  # noqa: E402
    check_use_table,
    cross_check_supply_use,
    read_supply_table,
    read_use_table,
)

DATA = Path(__file__).parents[1] / "data"
OUT = Path(__file__).parents[1] / "outputs"
SUT_XLSX = DATA / "raw" / "statssa" / "Supply and use tables 2018 - 2019.xlsx"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"
PRODUCTION_TAX_ACCOUNT = "atx"
# c-prefixed accounts that are NOT commodities: occupation factors whose
# columns pay households (verified in this script's diagnostic history)
NON_COMMODITY_C_ACCOUNTS = {"cler", "craf"}


def main() -> None:
    # 1. Read both tables; internal + cross-table checks
    supply = read_supply_table(str(SUT_XLSX), 2019)
    use = read_use_table(str(SUT_XLSX), 2019)
    findings = check_use_table(use, tolerance=0.5)
    cross = cross_check_supply_use(supply, use, tolerance=0.5)

    # 2. Aggregate SUT intermediate and value added to 61 activities
    conc = Concordance.from_csv(str(DATA / "derived" / "concordance_industries.csv"),
                                name="sut124-to-sam61-industries")
    sut_inter_61 = conc.aggregate(use.intermediate_by_industry())
    b1 = use.value_added_by_industry("B1")
    d23 = use.value_added_by_industry("D2/3")
    sut_va_61 = conc.aggregate({i: b1[i] - d23[i] for i in use.industries})

    # 3. Benchmark SAM activity-column decomposition
    sam = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    activities = sorted(sut_inter_61)
    sam_rows_by_col: dict[str, dict[str, float]] = {a: {} for a in activities}
    for (r, c), v in sam.cells.items():
        if c in sam_rows_by_col:
            sam_rows_by_col[c][r] = v
    comparison = []
    for a in activities:
        col = sam_rows_by_col[a]
        inter = sum(v for r, v in col.items()
                    if r.startswith("c") and r not in NON_COMMODITY_C_ACCOUNTS)
        atax = col.get(PRODUCTION_TAX_ACCOUNT, 0.0)
        total = sam.embedded_col_totals.get(a, 0.0)
        implied_va = total - inter - atax
        comparison.append({
            "account": a,
            "label": conc.target_labels.get(a, ""),
            "sut_intermediate": sut_inter_61[a],
            "sam_intermediate": inter,
            "inter_dev_pct": (inter - sut_inter_61[a]) / sut_inter_61[a] * 100
                             if sut_inter_61[a] else 0.0,
            "sut_va": sut_va_61[a],
            "sam_implied_va": implied_va,
            "va_dev_pct": (implied_va - sut_va_61[a]) / sut_va_61[a] * 100
                          if sut_va_61[a] else 0.0,
            "sam_production_tax": atax,
        })

    OUT.mkdir(exist_ok=True)
    with open(OUT / "use_validation.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(comparison[0].keys()))
        w.writeheader()
        for row in comparison:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v)
                        for k, v in row.items()})

    inter_devs = [abs(r["inter_dev_pct"]) for r in comparison]
    va_devs = [abs(r["va_dev_pct"]) for r in comparison]
    worst_inter = sorted(comparison, key=lambda r: -abs(r["inter_dev_pct"]))[:8]
    worst_va = sorted(comparison, key=lambda r: -abs(r["va_dev_pct"]))[:8]

    with open(OUT / "use_validation.md", "w") as f:
        f.write(f"# Use-side validation report\n\nGenerated {date.today()} "
                f"by code/03_validate_use_side.py.\n\n")
        f.write("## Internal consistency of the official use table (S-001)\n\n")
        f.write(f"- Products: {len(use.products)}; industries: {len(use.industries)}; "
                f"final-demand categories: {', '.join(use.fd_categories)}\n")
        f.write(f"- Identity checks (supply = intermediate + final demand; output = "
                f"intermediate + B1; B1 = D1 + D2/3 + B2/3; embedded totals): "
                f"**{len(findings)} findings** at R0.5m tolerance\n")
        for x in findings[:20]:
            f.write(f"  - {x.check} / {x.subject}: {x.detail}\n")
        f.write(f"- Cross-table checks vs supply table: **{len(cross)} findings**\n")
        for x in cross[:20]:
            f.write(f"  - {x.check} / {x.subject}: {x.detail}\n")
        f.write("\n## SUT vs benchmark SAM, per activity (61 accounts)\n\n")
        f.write("SAM activity columns are decomposed as intermediates (c* rows, "
                "excluding the mislabeled occupation accounts cler/craf) + production "
                "taxes (atx) + factor payments; implied VA = column total - "
                "intermediates - atx.\n\n")
        f.write(f"- Intermediate consumption: within 1%: "
                f"{sum(1 for d in inter_devs if d <= 1.0)}/61; "
                f"median |dev| {sorted(inter_devs)[30]:.4f}%; max |dev| {max(inter_devs):.4f}%\n")
        f.write(f"- Value added: within 1%: {sum(1 for d in va_devs if d <= 1.0)}/61; "
                f"median |dev| {sorted(va_devs)[30]:.4f}%; max |dev| {max(va_devs):.4f}%\n")
        f.write(f"- Production taxes routed through '{PRODUCTION_TAX_ACCOUNT}': "
                f"R{sum(r['sam_production_tax'] for r in comparison):,.0f}m total\n\n")
        f.write("### Largest intermediate-consumption deviations\n\n")
        f.write("| Account | Label | SUT (Rm) | SAM (Rm) | Dev % |\n|---|---|---|---|---|\n")
        for r in worst_inter:
            f.write(f"| {r['account']} | {r['label'][:32]} | {r['sut_intermediate']:,.0f} "
                    f"| {r['sam_intermediate']:,.0f} | {r['inter_dev_pct']:+.4f} |\n")
        f.write("\n### Largest value-added deviations\n\n")
        f.write("| Account | Label | SUT VA at factor cost (Rm) | SAM implied VA (Rm) | Dev % |\n|---|---|---|---|---|\n")
        for r in worst_va:
            f.write(f"| {r['account']} | {r['label'][:32]} | {r['sut_va']:,.0f} "
                    f"| {r['sam_implied_va']:,.0f} | {r['va_dev_pct']:+.4f} |\n")
        f.write("\nFull table: use_validation.csv.\n")

    print(f"internal findings: {len(findings)}; cross-table findings: {len(cross)}")
    print(f"intermediate: within 1%: {sum(1 for d in inter_devs if d <= 1.0)}/61; "
          f"max |dev| {max(inter_devs):.4f}%")
    print(f"value added:  within 1%: {sum(1 for d in va_devs if d <= 1.0)}/61; "
          f"max |dev| {max(va_devs):.4f}%")


if __name__ == "__main__":
    main()
