"""Extract the complete 209-account map for the benchmark SAM.

Combines three authoritative sources inside the S-003 workbook: activity
accounts from the Industry_List concordance targets, commodity accounts from
the Product_List targets, and everything else from the 'Other Accounts 10Occ
2019 SAM' dictionary sheet. Each code gets an explicit AccountKind - assigned
here, in one reviewable table, because prefix conventions in this SAM
actively lie (atx, cler, craf) and some capital-account descriptions in the
dictionary sheet look misaligned (mach='Network, Computer & Other IT
Equipment' while trnp='Machinery' and nitc='Transport Equipment'); kinds
below follow the dictionary sheet, with a flag column for the suspect trio.

Writes data/derived/sam_account_map.csv and asserts that the map covers the
SAM's accounts exactly - no unclassified accounts, no phantom entries.

Run from this directory, after 01:  python 04_extract_account_map.py
"""

import csv
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.concordance import Concordance  # noqa: E402
from edikit.data.sam import read_labeled_matrix  # noqa: E402
from edikit.model.accounts import AccountKind  # noqa: E402

DATA = Path(__file__).parents[1] / "data"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"

# Explicit kinds for every non-activity, non-commodity account (dictionary
# sheet order). Occupations and capital types are FACTOR accounts.
OTHER_ACCOUNT_KINDS: dict[str, AccountKind] = {
    "marg": AccountKind.MARGIN,
    "mang": AccountKind.FACTOR, "prof": AccountKind.FACTOR,
    "tech": AccountKind.FACTOR, "cler": AccountKind.FACTOR,
    "sale": AccountKind.FACTOR, "skag": AccountKind.FACTOR,
    "craf": AccountKind.FACTOR, "oper": AccountKind.FACTOR,
    "elmn": AccountKind.FACTOR, "doms": AccountKind.FACTOR,
    "land": AccountKind.FACTOR, "immo": AccountKind.FACTOR,
    "mach": AccountKind.FACTOR, "nitc": AccountKind.FACTOR,
    "trnp": AccountKind.FACTOR, "inta": AccountKind.FACTOR,
    "ent": AccountKind.ENTERPRISE,
    **{f"hhd{i}": AccountKind.HOUSEHOLD for i in range(1, 15)},
    "gvt": AccountKind.GOVERNMENT,
    "atx": AccountKind.TAX, "stx": AccountKind.TAX,
    "mtx": AccountKind.TAX, "dtx": AccountKind.TAX,
    "si": AccountKind.SAVINGS_INVESTMENT,
    "dstk": AccountKind.SAVINGS_INVESTMENT,
    "row": AccountKind.REST_OF_WORLD,
}
SUSPECT_DESCRIPTIONS = {"mach", "nitc", "trnp"}  # possible label misalignment in S-003


def main() -> None:
    iconc = Concordance.from_csv(str(DATA / "derived" / "concordance_industries.csv"))
    pconc = Concordance.from_csv(str(DATA / "derived" / "concordance_products.csv"))

    wb = openpyxl.load_workbook(SAM_XLSX, data_only=True, read_only=True)
    other_desc: dict[str, str] = {}
    for r in wb["Other Accounts 10Occ 2019 SAM"].iter_rows(values_only=True):
        code, desc = str(r[0] or "").strip(), str(r[1] or "").strip()
        if code and code != "Contents":
            other_desc[code] = desc

    entries: list[tuple[str, str, str, str, str]] = []
    for a in iconc.targets:
        entries.append((a, AccountKind.ACTIVITY.value, iconc.target_labels.get(a, ""),
                        "Industry_List", ""))
    for c in pconc.targets:
        entries.append((c, AccountKind.COMMODITY.value, pconc.target_labels.get(c, ""),
                        "Product_List", ""))
    for code, kind in OTHER_ACCOUNT_KINDS.items():
        if code not in other_desc:
            raise SystemExit(f"account {code} not found in dictionary sheet")
        flag = "description-suspect" if code in SUSPECT_DESCRIPTIONS else ""
        entries.append((code, kind.value, other_desc[code],
                        "Other Accounts 10Occ 2019 SAM", flag))

    # Coverage assertion against the actual matrix. The workbook carries one
    # column-only, all-zero balance-check column labeled 'error'; it is not an
    # account, so it is excluded here - with proof that it is in fact empty.
    sam = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    err_cells = [v for (r, c), v in sam.cells.items() if c == "error"]
    assert not err_cells, f"'error' check column is not empty: {err_cells[:3]}"
    mapped = {e[0] for e in entries}
    matrix_accounts = set(sam.col_accounts) - {"error"}
    missing = sorted(matrix_accounts - mapped)
    phantom = sorted(mapped - matrix_accounts)
    if missing or phantom:
        raise SystemExit(f"coverage failure - unmapped: {missing}; phantom: {phantom}")

    out = DATA / "derived" / "sam_account_map.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "kind", "description", "source_sheet", "flag"])
        w.writerows(entries)

    kinds: dict[str, int] = {}
    for _, k, *_ in entries:
        kinds[k] = kinds.get(k, 0) + 1
    print(f"{len(entries)} accounts mapped, full coverage verified:")
    for k, n in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"  {k:20s} {n}")


if __name__ == "__main__":
    main()
