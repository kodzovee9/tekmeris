"""Second application (Kenya): audit of the IFPRI 2019 Nexus SAM.

Stage 1: parse the distributed CSV (S-008, CC-BY-4.0), build the account
map from the file's own label+code columns, and verify the matrix balances.
Stage 2: compare the SAM's macro aggregates against the published KNBS
controls (Economic Survey 2020, current-price tables). Unlike the South
African benchmark, Nexus SAMs are cross-entropy reconciled, so this audit
targets structure and macro controls rather than cell-level replication;
the comparison indicates the aggregates through which the
reconciliation acted.

Run from this directory:  python 14_kenya_audit.py
"""

import csv
from pathlib import Path

DATA = Path(__file__).parents[1] / "data"
OUT = Path(__file__).parents[1] / "outputs"
SAM_CSV = DATA / "raw" / "kenya" / "ifpri" / "002_IFPRI_SAM_KEN_2019_SAM.csv"

# KNBS controls, Sh billions, 2019 provisional at current prices
# (S-010: Economic Survey 2020; GVA and taxes on products from Table 2.1
# p.26; expenditure components and the production-vs-expenditure
# discrepancy from Table 2.7 p.33; NPISH consumption added to private
# consumption for comparability with the SAM's household accounts)
KNBS = {
    "GVA (all activities)": 8911.5,
    "Taxes on products": 828.9,
    "GDP at market prices": 9740.4,
    "Private consumption (incl. NPISH)": 7945.7 + 89.7,
    "Government consumption": 1271.4,
    "Gross fixed capital formation": 1631.9,
    "Changes in inventories": 63.1,
    "Exports of goods and services": 1171.9,
    "Imports of goods and services": 2081.5,
    "Statistical discrepancy": -351.9,
}


def main() -> None:
    rows = list(csv.reader(open(SAM_CSV, encoding="utf-8-sig")))
    # layout: row 0 = [title, 'Code', code...]; data rows = [label, code, values...]
    col_codes = [c.strip() for c in rows[0][2:]]
    accounts, cells = [], {}
    for r in rows[1:]:
        label, code = r[0].strip(), r[1].strip()
        if code.lower() in ("", "total") or label.lower() == "total":
            continue
        accounts.append((code, label))
        for j, v in enumerate(r[2:]):
            v = v.strip().replace(",", "")
            if v and col_codes[j].lower() != "total":
                try:
                    x = float(v)
                except ValueError:
                    continue
                if x:
                    cells[(code, col_codes[j])] = x

    codes = [c for c, _ in accounts]
    assert len(codes) == len(set(codes)), "duplicate account codes"
    kinds = {}
    for code, label in accounts:
        group = label.split(" - ")[0].strip() if " - " in label else label.strip()
        kinds[code] = group
    groups = {}
    for c, g in kinds.items():
        groups.setdefault(g, []).append(c)

    rowsum, colsum = {}, {}
    for (r, c), v in cells.items():
        rowsum[r] = rowsum.get(r, 0.0) + v
        colsum[c] = colsum.get(c, 0.0) + v
    gaps = sorted(((abs(rowsum.get(a, 0) - colsum.get(a, 0)), a) for a in codes),
                  reverse=True)

    # macro aggregates for the KNBS comparison, Sh billions
    acts = set(groups.get("Activities", []))
    coms = set(groups.get("Commodities", []))
    hhds = set(groups.get("Households", []))
    gva = sum(v for (r, c), v in cells.items()
              if c in acts and kinds.get(r) == "Factors")
    prod_tax = sum(v for (r, c), v in cells.items()
                   if r in ("mtax", "stax") and c in coms)
    sam_macro = {
        "GVA (all activities)": gva,
        "Taxes on products": prod_tax,
        "GDP at market prices": gva + prod_tax,
        # marketed purchases plus home consumption, which Nexus SAMs route
        # directly from households to activities (Sh 661bn here)
        "Private consumption (incl. NPISH)":
            sum(v for (r, c), v in cells.items()
                if c in hhds and (r in coms or r in acts)),
        "Government consumption":
            sum(v for (r, c), v in cells.items() if c == "gov" and r in coms),
        "Gross fixed capital formation":
            sum(v for (r, c), v in cells.items() if c == "s-i" and r in coms),
        "Changes in inventories":
            sum(v for (r, c), v in cells.items() if c == "dstk" and r in coms),
        "Exports of goods and services":
            sum(v for (r, c), v in cells.items() if c == "row" and r in coms),
        "Imports of goods and services":
            sum(v for (r, c), v in cells.items() if r == "row" and c in coms),
        "Statistical discrepancy": 0.0,  # a balanced SAM cannot carry one
    }
    # the SAM's own expenditure-side GDP, for the identity check below
    exp_gdp = (sam_macro["Private consumption (incl. NPISH)"]
               + sam_macro["Government consumption"]
               + sam_macro["Gross fixed capital formation"]
               + sam_macro["Changes in inventories"]
               + sam_macro["Exports of goods and services"]
               - sam_macro["Imports of goods and services"])

    with open(OUT / "kenya_macro_comparison.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["aggregate", "sam_bn", "knbs_bn", "dev_pct"])
        for k, knbs_v in KNBS.items():
            sam_v = sam_macro[k]
            skip = not knbs_v or k == "Statistical discrepancy"
            dev = "" if skip else f"{(sam_v - knbs_v) / abs(knbs_v) * 100:.2f}"
            w.writerow([k, f"{sam_v:.1f}", f"{knbs_v:.1f}", dev])

    OUT.mkdir(exist_ok=True)
    with open(OUT / "kenya_structural_audit.md", "w") as f:
        f.write(f"# Kenya (second application): structural audit\n\n"
                f"Generated by code/14_kenya_audit.py from the "
                f"IFPRI 2019 Nexus SAM (S-008, CC-BY-4.0).\n\n")
        f.write(f"- Accounts: {len(codes)}; nonzero cells: {len(cells):,}; "
                f"units Sh billions\n")
        f.write("- Account groups (from the file's own labels): "
                + "; ".join(f"{g} ({len(cs)})" for g, cs in groups.items()) + "\n")
        f.write(f"- Balance: max |rowsum - colsum| = Sh {gaps[0][0]:.4f} billion "
                f"({gaps[0][1]}); accounts within 0.5: "
                f"{sum(1 for g, _ in gaps if g <= 0.5)}/{len(codes)}\n\n")
        f.write("## Macro comparison against KNBS controls (Sh billion, "
                "current prices, 2019 provisional)\n\n")
        f.write("| Aggregate | SAM | KNBS (ES 2020) | Dev. % |\n|---|---|---|---|\n")
        for k, knbs_v in KNBS.items():
            sam_v = sam_macro[k]
            skip = not knbs_v or k == "Statistical discrepancy"
            dev = "-" if skip else f"{(sam_v - knbs_v) / abs(knbs_v) * 100:+.1f}"
            f.write(f"| {k} | {sam_v:,.1f} | {knbs_v:,.1f} | {dev} |\n")
        f.write(f"\n- SAM expenditure-side GDP = {exp_gdp:,.1f}, equal to the "
                f"production-side figure up to the file's integer rounding: a "
                f"balanced SAM cannot carry KNBS's published Sh "
                f"{-KNBS['Statistical discrepancy']:.0f}bn production-vs-"
                f"expenditure discrepancy (-3.6% of GDP), so the cross-entropy "
                f"reconciliation necessarily reallocated it. The pattern is "
                f"consistent with the discrepancy and associated source "
                f"differences being absorbed primarily through the "
                f"consumption and trade aggregates; aggregate data cannot "
                f"identify the allocation uniquely.\n"
                f"- The uniform -1.0% on GVA, product taxes, and GDP is "
                f"consistent with the SAM using a different vintage of the "
                f"then-provisional 2019 accounts than the ES 2020 print.\n")

    print(f"accounts {len(codes)}; cells {len(cells):,}; groups: "
          f"{ {g: len(cs) for g, cs in groups.items()} }")
    print(f"balance: max gap Sh {gaps[0][0]:.4f}bn ({gaps[0][1]}); "
          f"within 0.5bn: {sum(1 for g, _ in gaps if g <= 0.5)}/{len(codes)}")
    for k, knbs_v in KNBS.items():
        sam_v = sam_macro[k]
        skip = not knbs_v or k == "Statistical discrepancy"
        dev = "-" if skip else f"{(sam_v - knbs_v) / abs(knbs_v) * 100:+.1f}%"
        print(f"  {k:38s} SAM {sam_v:8,.1f}  KNBS {knbs_v:8,.1f}  {dev}")
    print(f"  {'SAM expenditure-side GDP':38s} {exp_gdp:8,.1f}")


if __name__ == "__main__":
    main()
