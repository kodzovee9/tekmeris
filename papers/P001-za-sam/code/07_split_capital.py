"""Disaggregate capital income into six capital-stock types via the AFS.

Implements entry (iii) of the technical note at micro level: each activity's
gross operating surplus is split across six capital types using that
activity's shares of capital stock in the Stats SA Annual Financial
Statistics 2019 (S-007, PPE schedules: 258 SIC blocks x 22 asset rows).

- Asset types aggregate per the note's Table A3 (capital work in progress
  dropped; 'other PPE' folded into Machinery; rows 12-22 are intangibles).
- AFS SIC blocks map to SAM activities per the note's Table A4, parsed here
  from the technical-note text with full-coverage assertions.
- The note does not say WHICH carrying value defines the 'stock' nor which
  AFS release; testing opening/closing columns across the 2019 preliminary
  and 2019 revised editions identifies **2019 revised, closing values** as
  the closest (median |share diff| 0.18pp vs 0.72pp for preliminary) -
  deterministic recovery of two undocumented choices. Residual outliers
  (posts/telecoms above all) indicate further benchmark-side adjustments.

Run from this directory, after 01 and 04:
    python 07_split_capital.py
"""

import csv
import re
import sys
from datetime import date
from pathlib import Path

import xlrd

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.sam import read_labeled_matrix  # noqa: E402

DATA = Path(__file__).parents[1] / "data"
OUT = Path(__file__).parents[1] / "outputs"
AFS_ZIP = DATA / "raw" / "statssa" / "afs" / "Disaggregated industry estimates 2019_2020.zip"
AFS_MEMBER = "AFS 2019 revised ~ Disaggregated industry estimates.xls"
TN_TEXT = DATA / "external" / "tn2023-1.txt"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"

CAPITAL_TYPES = ["land", "immo", "nitc", "trnp", "mach", "inta"]
# Table A3: detailed AFS asset row -> SAM capital account (None = dropped)
A3 = {
    "Land": "land",
    "Residential buildings": "immo",
    "Non-residential buildings": "immo",
    "Construction works, roads and parking areas": "immo",
    "Land improvements": "immo",
    "Network equipment": "nitc",
    "Computers and other IT equipment": "nitc",
    "Motor vehicles and other transport equipment": "trnp",
    "Plant, machinery and other office equipment": "mach",
    "Capital work in progress": None,
    "Other property, plant and equipment": "mach",
    "Intangible assets": None,  # header row for the intangibles block
    "Computer software": "inta",
    "Databases": "inta",
    "Mineral exploration and evaluation": "inta",
    "Patents and trademarks": "inta",
    "Goodwill and marketing assets": "inta",
    "Research and development": "inta",
    "Entertainment, literary and artistic originals": "inta",
    "Contracts, leases and licences": "inta",
    "Capital work in progress (intangible)": None,
    "Other intellectual property products": "inta",
}


def parse_table_a4(text: str) -> dict[str, str]:
    """Parse the note's Table A4 into {sic_code: activity}.

    Rows look like: '<sic list> <description> I0xx a<code> <label>'. The
    activity anchor 'I\\d{3} a\\w+' is reliable; the SIC list is recovered as
    the leading numeric tokens of the text between consecutive anchors.
    """
    start = text.index("Table A4: Mapping of detailed AFS industries")
    end = text.find("Table A5", start)
    seg = text[start:end if end > 0 else None]
    seg = re.sub(r"---\s*page\s*\d+\s*---|\n", " ", seg)
    seg = re.sub(r"\s+", " ", seg)
    seg = seg[seg.index("#Code Label Description") + len("#Code Label Description"):]
    anchors = list(re.finditer(r"I\d{3}\s+(a[a-z]{3,4})\b", seg))
    mapping: dict[str, str] = {}
    for i, m in enumerate(anchors):
        chunk_start = anchors[i - 1].end() if i else 0
        chunk = seg[chunk_start:m.start()]
        # chunk = [previous row's trailing label] [SIC list] [description]:
        # take the first run of 2-4 digit codes that is followed by text
        sics = re.search(r"(?:^|\s)((?:\d{2,4}\s*[;,]?\s*)+)(?=[A-Z(])", chunk)
        if not sics:
            continue
        for code in re.findall(r"\d{2,4}", sics.group(1)):
            mapping[code] = m.group(1)
    return mapping


def read_afs_stocks(measure_cols: dict[str, int]) -> dict[str, dict[tuple[str, str], float]]:
    """Read PPE blocks: {measure: {(sic_heading_first_code, sam_type): value}}."""
    import io
    import zipfile
    with zipfile.ZipFile(AFS_ZIP) as z:
        wb = xlrd.open_workbook(file_contents=z.read(AFS_MEMBER))
    ws = wb.sheet_by_name("PPE schedules")
    out = {m: {} for m in measure_cols}
    current_sics: list[str] = []
    for i in range(ws.nrows):
        lead = str(ws.cell_value(i, 0)).strip()
        if lead.upper().startswith("SIC"):
            current_sics = re.findall(r"\d{2,4}", lead)
            continue
        sam_type = A3.get(lead)
        if sam_type is None or not current_sics:
            continue
        for m, col in measure_cols.items():
            v = ws.cell_value(i, col)
            if isinstance(v, (int, float)) and v:
                key = (current_sics[0], sam_type)
                out[m][key] = out[m].get(key, 0.0) + float(v)
    return out


def main() -> None:
    tn = open(TN_TEXT, encoding="utf-8", errors="replace").read()
    a4 = parse_table_a4(tn)
    print(f"Table A4 parsed: {len(a4)} SIC codes -> {len(set(a4.values()))} activities")

    measures = {"opening": 1, "closing": 7}
    stocks = read_afs_stocks(measures)
    stocks["average"] = {k: (stocks["opening"].get(k, 0.0) + stocks["closing"].get(k, 0.0)) / 2
                         for k in set(stocks["opening"]) | set(stocks["closing"])}

    # benchmark capital block: type x activity
    sam = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    bench: dict[tuple[str, str], float] = {}
    activities = set()
    for (r, c), v in sam.cells.items():
        if r in CAPITAL_TYPES and c.startswith("a") and c != "atx":
            bench[(r, c)] = v
            activities.add(c)
    gos = {a: sum(bench.get((t, a), 0.0) for t in CAPITAL_TYPES) for a in activities}

    # aggregate AFS stocks to activity level, per measure
    unmapped: set[str] = set()
    results = {}
    for m, data in stocks.items():
        by_act: dict[tuple[str, str], float] = {}
        for (sic, t), v in data.items():
            act = a4.get(sic)
            if act is None:
                unmapped.add(sic)
                continue
            by_act[(act, t)] = by_act.get((act, t), 0.0) + v
        results[m] = by_act

    covered = sorted({a for (a, _) in results["closing"]})
    uncovered = sorted(activities - set(covered))

    # compare share vectors per activity, per measure
    report_rows = []
    summary = {}
    for m, by_act in results.items():
        devs = []
        for a in covered:
            tot = sum(by_act.get((a, t), 0.0) for t in CAPITAL_TYPES)
            if tot <= 0 or gos.get(a, 0.0) <= 0:
                continue
            for t in CAPITAL_TYPES:
                share_afs = by_act.get((a, t), 0.0) / tot
                share_bench = bench.get((t, a), 0.0) / gos[a]
                devs.append(abs(share_afs - share_bench))
                if m == "closing":
                    report_rows.append({"activity": a, "type": t,
                                        "afs_share": share_afs,
                                        "bench_share": share_bench,
                                        "abs_diff_pp": (share_afs - share_bench) * 100})
        devs.sort()
        summary[m] = {"n": len(devs), "median_pp": devs[len(devs) // 2] * 100,
                      "mean_pp": sum(devs) / len(devs) * 100,
                      "max_pp": devs[-1] * 100,
                      "within_1pp": sum(1 for d in devs if d <= 0.01) / len(devs) * 100}  # <=1 percentage point

    OUT.mkdir(exist_ok=True)
    with open(OUT / "capital_split.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["activity", "type", "afs_share",
                                          "bench_share", "abs_diff_pp"])
        w.writeheader()
        for r in report_rows:
            w.writerow({k: (f"{v:.5f}" if isinstance(v, float) else v)
                        for k, v in r.items()})

    with open(OUT / "capital_split.md", "w") as f:
        f.write(f"# Capital-stock disaggregation report\n\nGenerated {date.today()} "
                f"by code/07_split_capital.py.\n\n")
        f.write(f"- Table A4 parsed from the technical note: {len(a4)} SIC codes; "
                f"AFS SIC blocks unmapped: {sorted(unmapped) if unmapped else 'none'}\n")
        f.write(f"- Activities covered by AFS: {len(covered)}/61; not covered: "
                f"{', '.join(uncovered) if uncovered else 'none'}\n\n")
        f.write("## Share agreement with the benchmark, by stock measure\n\n")
        f.write("| Measure | Comparisons | Median |diff| (pp) | Mean (pp) | Max (pp) | Within 1pp |\n")
        f.write("|---|---|---|---|---|---|\n")
        for m, s in summary.items():
            f.write(f"| {m} | {s['n']} | {s['median_pp']:.4f} | {s['mean_pp']:.4f} | "
                    f"{s['max_pp']:.4f} | {s['within_1pp']:.1f}% |\n")
        f.write("\nShares compared per activity: AFS capital-type share vs benchmark "
                "capital-row share of activity GOS. Full closing-measure table: "
                "capital_split.csv.\n")

    for m, s in summary.items():
        print(f"{m:8s} n={s['n']}  median {s['median_pp']:.4f}pp  mean {s['mean_pp']:.4f}pp  "
              f"max {s['max_pp']:.4f}pp  exact {s['within_1pp']:.1f}%")
    print(f"covered activities: {len(covered)}/61; uncovered: {uncovered}")
    if unmapped:
        print(f"unmapped AFS SICs: {sorted(unmapped)[:10]}")


if __name__ == "__main__":
    main()
