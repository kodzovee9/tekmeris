"""Disaggregate labour income into ten occupations via LMD microdata.

Implements entry (ii) of the technical note at micro level: each activity's
compensation of employees is split across ten occupations using wage bills
computed from the Labour Market Dynamics 2018 and 2019 microdata (S-005):

    wage bill(activity, occupation) = weighted employment x average wage,
    missing-wage cells get the national average wage of the occupation,
    percentage shares averaged over the two years.  (TN Section 2, item ii)

Mappings: LMD industry labels -> 124-level SUT industries via the note's
Table A2 (parsed from text, matched on normalized descriptions), then the
existing 124->61 concordance. Occupations use the LMD's derived 10-category
variable, which matches the SAM's occupation accounts exactly (including
domestic workers). The LMD files stack four quarters, so weighted employment
is Weight/4.

The microdata stay in data/external/ (not redistributable); this script
publishes only aggregated shares.

Run from this directory, after 01 and 04:
    python 08_split_occupations.py
"""

import csv
import io
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.concordance import Concordance  # noqa: E402
from edikit.data.sam import read_labeled_matrix  # noqa: E402

DATA = Path(__file__).parents[1] / "data"
OUT = Path(__file__).parents[1] / "outputs"
TN_TEXT = DATA / "external" / "tn2023-1.txt"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"
LMD = {2018: ("lmdsa-2018-v1.0-csv.zip", "lmdsa-2018-v1.0.csv"),
       2019: ("lmdsa-2019-v1.1.zip",
              "lmdsa-2019-v1.1/lmdsa-2019-v1.1-csv/lmdsa-2019-v1.1.csv")}

OCC_LABELS = {
    "Legislators; senior officials and managers": "mang",
    "Professionals": "prof",
    "Technical and associate professionals": "tech",
    "Clerks": "cler",
    "Service workers and shop and market sales workers": "sale",
    "Skilled agricultural and fishery workers": "skag",
    "Craft and related trades workers": "craf",
    "Plant and machine operators and assemblers": "oper",
    "Elementary Occupation": "elmn",
    "Domestic workers": "doms",
}
OCCS = list(OCC_LABELS.values())

# Labels absent from Table A2 (or too generic to match): explicit treatment.
# 'MINING OF METAL ORES' is the 2-digit SIC 24 label -> amore's SUT industry;
# the exterritorial/foreign-government/unspecified labels (<20 obs combined)
# have no Table A2 row and are dropped, as the benchmark evidently did.
LABEL_FALLBACKS = {"MINING OF METAL ORES": "I6"}
LABEL_DROPS = {"EXTERRITORIAL ORGANISATIONS", "REPRESENTATIVES OF FOREIGN GOVERNMENTS",
               "UNSPECIFIED", "62"}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse_table_a2(text: str) -> dict[str, str]:
    """{normalized LMD SIC description: SUT industry code 'I<n>'}."""
    start = text.index("Table A2: Mapping of LMD SIC")
    end = text.find("Table A3", start)
    seg = re.sub(r"---\s*page\s*\d+\s*---|\n", " ", text[start:end])
    seg = re.sub(r"\s+", " ", seg)
    anchors = list(re.finditer(r"\bi(\d{3})\b", seg))
    mapping: dict[str, str] = {}
    for i, m in enumerate(anchors):
        chunk = seg[anchors[i - 1].end() if i else 0:m.start()]
        # chunk tail = '<row n> <3-digit sic> <description>'; strip leading
        # remnants of the previous row's full description up to that pattern
        row = re.search(r"(?:^|\s)\d{1,3}\s+(\d{2,3})\s+(.*)$", chunk)
        if not row:
            continue
        desc = row.group(2)
        mapping[norm(desc)] = f"I{int(m.group(1))}"
    return mapping


def wage_bills(year: int, a2: dict[str, str], iconc: Concordance,
               unmatched: set[str]) -> dict[tuple[str, str], float]:
    """{(activity, occupation): wage bill} for one LMD year."""
    zip_name, member = LMD[year]
    emp: dict[tuple[str, str], float] = {}
    wage_sum: dict[tuple[str, str], float] = {}
    wage_w: dict[tuple[str, str], float] = {}
    occ_wage_sum: dict[str, float] = {}
    occ_wage_w: dict[str, float] = {}
    a2_norms = list(a2.items())

    def act_of(label: str) -> str | None:
        if label.strip() in LABEL_DROPS:
            return None
        if label.strip() in LABEL_FALLBACKS:
            return iconc.mapping.get(LABEL_FALLBACKS[label.strip()])
        n = norm(label)
        if n in a2:
            icode = a2[n]
        else:
            hits = [v for k, v in a2_norms if k.startswith(n) or n.startswith(k)]
            if len(set(hits)) != 1:
                unmatched.add(label)
                return None
            icode = hits[0]
        return iconc.mapping.get(icode)

    with zipfile.ZipFile(DATA / "external" / zip_name) as z, z.open(member) as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace")):
            if row["Status"] != "Employed":
                continue
            occ = OCC_LABELS.get(row["occup"])
            act = act_of(row["Q43INDUSTRY"])
            if occ is None or act is None:
                continue
            try:
                w = float(row["Weight"]) / 4.0  # four stacked quarters
            except ValueError:
                continue
            key = (act, occ)
            emp[key] = emp.get(key, 0.0) + w
            v = row["Q54a_monthly"].strip()
            if v and v not in ("NA", "."):
                try:
                    wage = float(v)
                except ValueError:
                    wage = None
                if wage and wage > 0:
                    wage_sum[key] = wage_sum.get(key, 0.0) + w * wage
                    wage_w[key] = wage_w.get(key, 0.0) + w
                    occ_wage_sum[occ] = occ_wage_sum.get(occ, 0.0) + w * wage
                    occ_wage_w[occ] = occ_wage_w.get(occ, 0.0) + w

    nat_wage = {o: occ_wage_sum[o] / occ_wage_w[o] for o in occ_wage_sum}
    bills: dict[tuple[str, str], float] = {}
    for key, e in emp.items():
        _, occ = key
        avg = (wage_sum[key] / wage_w[key]) if wage_w.get(key) else nat_wage.get(occ)
        if avg:
            bills[key] = e * avg
    return bills


def main() -> None:
    tn = open(TN_TEXT, encoding="utf-8", errors="replace").read()
    a2 = parse_table_a2(tn)
    iconc = Concordance.from_csv(str(DATA / "derived" / "concordance_industries.csv"))
    print(f"Table A2 parsed: {len(a2)} LMD industry descriptions")

    unmatched: set[str] = set()
    shares_by_year = {}
    for year in (2018, 2019):
        bills = wage_bills(year, a2, iconc, unmatched)
        shares: dict[tuple[str, str], float] = {}
        for a in {k[0] for k in bills}:
            tot = sum(bills.get((a, o), 0.0) for o in OCCS)
            if tot > 0:
                for o in OCCS:
                    shares[(a, o)] = bills.get((a, o), 0.0) / tot
        shares_by_year[year] = shares
        print(f"{year}: activities with wage bills: {len({k[0] for k in bills})}")

    both = set(shares_by_year[2018]) | set(shares_by_year[2019])
    lmd_shares = {k: (shares_by_year[2018].get(k, 0.0) + shares_by_year[2019].get(k, 0.0)) / 2
                  for k in both}

    # benchmark occupation block
    sam = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    bench = {(c, r): v for (r, c), v in sam.cells.items()
             if r in OCCS and c.startswith("a") and c != "atx"}
    lab_tot = {}
    for (a, _), v in bench.items():
        lab_tot[a] = lab_tot.get(a, 0.0) + v

    rows, devs = [], []
    for a in sorted(lab_tot):
        if not any((a, o) in lmd_shares for o in OCCS):
            continue
        for o in OCCS:
            ours = lmd_shares.get((a, o), 0.0)
            b = bench.get((a, o), 0.0) / lab_tot[a]
            devs.append(abs(ours - b))
            rows.append({"activity": a, "occupation": o, "lmd_share": ours,
                         "bench_share": b, "diff_pp": (ours - b) * 100})
    devs.sort()

    OUT.mkdir(exist_ok=True)
    with open(OUT / "occupation_split.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["activity", "occupation", "lmd_share",
                                          "bench_share", "diff_pp"])
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.5f}" if isinstance(v, float) else v)
                        for k, v in r.items()})

    n = len(devs)
    summary = (f"n={n}  median {devs[n//2]*100:.4f}pp  mean {sum(devs)/n*100:.4f}pp  "
               f"max {devs[-1]*100:.2f}pp  within 1pp {sum(1 for d in devs if d <= 0.01)/n*100:.1f}%")
    with open(OUT / "occupation_split.md", "w") as f:
        f.write(f"# Occupation disaggregation report\n\nGenerated by "
                f"code/08_split_occupations.py.\n\n")
        f.write(f"- Table A2: {len(a2)} descriptions parsed; unmatched LMD labels: "
                f"{len(unmatched)}\n")
        for u in sorted(unmatched)[:15]:
            f.write(f"  - {u}\n")
        f.write(f"- Share agreement vs benchmark (10 occupations x "
                f"{len({r['activity'] for r in rows})} activities): {summary}\n\n")
        f.write("Full table: occupation_split.csv. Only aggregated shares are "
                "published; LMD microdata are not redistributed.\n")
    print(summary)
    print(f"unmatched labels: {len(unmatched)}")


if __name__ == "__main__":
    main()
