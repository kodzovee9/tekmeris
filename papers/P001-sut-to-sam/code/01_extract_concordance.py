"""Extract the SUT->SAM industry and product concordances.

The mappings are published by the benchmark authors inside the UNU-WIDER 2019
SAM workbook (sheets Industry_List and Product_List, registered as S-003 in
../data/SOURCES.md). We extract them programmatically rather than construct
them by hand, and validate them numerically in 02_validate_supply_side.py.

Run from this directory:  python 01_extract_concordance.py
"""

import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.concordance import Concordance  # noqa: E402

DATA = Path(__file__).parents[1] / "data"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
PROVENANCE = "S-003 UNU-WIDER 2019 SA SAM workbook, sheets Industry_List/Product_List, extracted 2026-07-16"


def extract(sheet, source_col: int, target_col: int, label_col: int, name: str) -> Concordance:
    rows = list(sheet.iter_rows(values_only=True))
    mapping, labels = {}, {}
    for r in rows[2:]:
        src = str(r[source_col] or "").strip()
        tgt = str(r[target_col] or "").strip()
        if src and tgt:
            mapping[src] = tgt
            lab = str(r[label_col] or "").strip()
            if lab:
                labels[tgt] = lab
    return Concordance(name=name, mapping=mapping, provenance=PROVENANCE, target_labels=labels)


def main() -> None:
    wb = openpyxl.load_workbook(SAM_XLSX, data_only=True, read_only=True)

    # Industry_List: col C (idx 2) = SUT industry number, col G (idx 6) = SAM code,
    # col H (idx 7) = SAM label. Columns J-L repeat a lookup table; ignored.
    ind = extract(wb["Industry_List"], 2, 6, 7, "sut124-to-sam61-industries")
    # Product_List: col C (idx 2) = SUT product number, col G (idx 6) = SAM commodity label.
    prod = extract(wb["Product_List"], 2, 6, 6, "sut-products-to-sam-commodities")

    derived = DATA / "derived"
    derived.mkdir(exist_ok=True)
    ind.to_csv(str(derived / "concordance_industries.csv"))
    prod.to_csv(str(derived / "concordance_products.csv"))

    print(f"industries: {len(ind.mapping)} sources -> {len(ind.targets)} SAM activity accounts")
    print(f"products:   {len(prod.mapping)} sources -> {len(prod.targets)} SAM commodity accounts")


if __name__ == "__main__":
    main()
