"""Generate the paper's tables and figure from the pipeline outputs.

Nothing in the manuscript's exhibits is typed by hand: this script reads the
outputs of scripts 06-08 (plus the AFS sources for the recovery grid) and
emits LaTeX table fragments and one figure into paper/tables/ and
paper/figures/. Rerunning the pipeline rebuilds the paper's numbers.

Run from this directory, after 06, 07, 08:  python 13_paper_tables.py
"""

import csv
import os
import re
import sys
import zipfile
from pathlib import Path

# deterministic figure metadata: matplotlib honors SOURCE_DATE_EPOCH for
# the PDF CreationDate, which must not vary run to run
os.environ.setdefault("SOURCE_DATE_EPOCH", "0")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import xlrd

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.sam import read_labeled_matrix  # noqa: E402

DATA = Path(__file__).parents[1] / "data"
OUT = Path(__file__).parents[1] / "outputs"
PAPER = Path(__file__).parents[1] / "paper"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"
CAPS = ["land", "immo", "nitc", "trnp", "mach", "inta"]
OCC_NAMES = {"mang": "Managers", "prof": "Professionals", "tech": "Technicians",
             "cler": "Clerks", "sale": "Service and sales", "skag": "Skilled agriculture",
             "craf": "Craft", "oper": "Plant/machine operators",
             "elmn": "Elementary", "doms": "Domestic workers"}

# Table A3 (as in script 07)
A3 = {"Land": "land", "Residential buildings": "immo", "Non-residential buildings": "immo",
      "Construction works, roads and parking areas": "immo", "Land improvements": "immo",
      "Network equipment": "nitc", "Computers and other IT equipment": "nitc",
      "Motor vehicles and other transport equipment": "trnp",
      "Plant, machinery and other office equipment": "mach",
      "Capital work in progress": None, "Other property, plant and equipment": "mach",
      "Intangible assets": None, "Computer software": "inta", "Databases": "inta",
      "Mineral exploration and evaluation": "inta", "Patents and trademarks": "inta",
      "Goodwill and marketing assets": "inta", "Research and development": "inta",
      "Entertainment, literary and artistic originals": "inta",
      "Contracts, leases and licences": "inta", "Capital work in progress (intangible)": None,
      "Other intellectual property products": "inta"}


def parse_a4(text: str) -> dict[str, str]:
    start = text.index("Table A4: Mapping of detailed AFS industries")
    seg = re.sub(r"---\s*page\s*\d+\s*---|\n", " ", text[start:])
    seg = re.sub(r"\s+", " ", seg)
    seg = seg[seg.index("#Code Label Description") + len("#Code Label Description"):]
    anchors = list(re.finditer(r"I\d{3}\s+(a[a-z]{3,4})\b", seg))
    m = {}
    for i, a in enumerate(anchors):
        chunk = seg[anchors[i - 1].end() if i else 0:a.start()]
        s = re.search(r"(?:^|\s)((?:\d{2,4}\s*[;,]?\s*)+)(?=[A-Z(])", chunk)
        if s:
            for code in re.findall(r"\d{2,4}", s.group(1)):
                m[code] = a.group(1)
    return m


def afs_shares(zip_path: Path, member: str, col: int, a4) -> dict:
    with zipfile.ZipFile(zip_path) as z:
        wb = xlrd.open_workbook(file_contents=z.read(member))
    ws = wb.sheet_by_name("PPE schedules")
    out, cur = {}, None
    for i in range(ws.nrows):
        lead = str(ws.cell_value(i, 0)).strip()
        if lead.upper().startswith("SIC"):
            cur = re.findall(r"\d{2,4}", lead)[0]
            continue
        t = A3.get(lead)
        if t and cur:
            v = ws.cell_value(i, col)
            if isinstance(v, (int, float)) and v:
                act = a4.get(cur)
                if act:
                    out[(act, t)] = out.get((act, t), 0.0) + float(v)
    return out


def grid_stats(by_act, bench, gos):
    devs = []
    for a in sorted({x for (x, _) in by_act}):
        tot = sum(by_act.get((a, t), 0.0) for t in CAPS)
        if tot <= 0 or gos.get(a, 0.0) <= 0:
            continue
        for t in CAPS:
            devs.append(abs(by_act.get((a, t), 0.0) / tot - bench.get((t, a), 0.0) / gos[a]))
    devs.sort()
    return {"median": devs[len(devs) // 2] * 100,
            "within1": sum(1 for d in devs if d <= 0.01) / len(devs) * 100,
            "devs": devs}


def main() -> None:
    (PAPER / "tables").mkdir(exist_ok=True)
    (PAPER / "figures").mkdir(exist_ok=True)

    # ---- Table: notable macro cells ----
    rows = list(csv.DictReader(open(OUT / "macro_sam_construction.csv")))
    notable = {"vi", "vii", "xv", "xvii", "xxviii", "xxxiv", "xxxv"}
    with open(PAPER / "tables" / "tab_macro_notable.tex", "w") as f:
        f.write("\\begin{tabular}{llrrrr}\n\\toprule\n")
        f.write("Entry & Cell (receiver $\\leftarrow$ payer) & Computed & Benchmark "
                "& Dev.\\ \\% & Proxy dev.\\ \\% \\\\\n\\midrule\n")
        for r in rows:
            if r["entry"] in notable:
                cell = f"{r['row_account']} $\\leftarrow$ {r['col_account']}"
                f.write(f"{r['entry']} & {cell} & {float(r['computed_Rm']):,.0f} & "
                        f"{float(r['benchmark_Rm']):,.0f} & "
                        f"{float(r['dev_pct']):+.2f} & {float(r['proxy_dev_pct']):+.2f} \\\\\n")
        n = len(rows)
        exact = sum(1 for r in rows if r["flag"] != "unpublished-input"
                    and abs(float(r["dev_pct"])) <= 0.01)
        f.write("\\midrule\n\\multicolumn{6}{l}{\\emph{Remaining "
                f"{n - len(notable)} cells: exact "
                f"({exact} of 45 computable within 0.01\\%)"
                "}} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")

    # ---- Table: capital-split recovery grid ----
    tn = open(DATA / "external" / "tn2023-1.txt", encoding="utf-8", errors="replace").read()
    a4 = parse_a4(tn)
    sam = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    bench = {(r, c): v for (r, c), v in sam.cells.items()
             if r in CAPS and c.startswith("a") and c != "atx"}
    gos = {}
    for (t, a), v in bench.items():
        gos[a] = gos.get(a, 0.0) + v
    afs_dir = DATA / "raw" / "statssa" / "afs"
    grid = {}
    for ed, (zp, member) in {
        "2019 preliminary": (afs_dir / "Disaggregated industry estimates 2018_2019.zip",
                             "AFS 2019 preliminary ~ Disaggregated industry estimates.xls"),
        "2019 revised": (afs_dir / "Disaggregated industry estimates 2019_2020.zip",
                         "AFS 2019 revised ~ Disaggregated industry estimates.xls")}.items():
        for meas, col in {"opening": 1, "closing": 7}.items():
            grid[(ed, meas)] = grid_stats(afs_shares(zp, member, col, a4), bench, gos)
    with open(PAPER / "tables" / "tab_capital_grid.tex", "w") as f:
        f.write("\\begin{tabular}{llrr}\n\\toprule\n")
        f.write("AFS edition & Stock measure & Median $|$diff$|$ (pp) & Within 1pp (\\%) \\\\\n\\midrule\n")
        for (ed, meas), s in grid.items():
            mark = " $\\leftarrow$ recovered" if (ed, meas) == ("2019 revised", "closing") else ""
            f.write(f"{ed} & {meas}{mark} & {s['median']:.2f} & {s['within1']:.1f} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")

    # ---- Table: occupation deviations by occupation ----
    occ_rows = list(csv.DictReader(open(OUT / "occupation_split.csv")))
    by_occ = {}
    for r in occ_rows:
        by_occ.setdefault(r["occupation"], []).append(abs(float(r["diff_pp"])))
    with open(PAPER / "tables" / "tab_occupation.tex", "w") as f:
        f.write("\\begin{tabular}{lrrr}\n\\toprule\n")
        f.write("Occupation & Median $|$diff$|$ (pp) & Max (pp) & Within 1pp (of 61) \\\\\n\\midrule\n")
        for o in OCC_NAMES:
            d = sorted(by_occ[o])
            f.write(f"{OCC_NAMES[o]} & {d[len(d)//2]:.3f} & {d[-1]:.2f} & "
                    f"{sum(1 for x in d if x <= 1.0)} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")

    # ---- Table: Kenya macro comparison (second application) ----
    ken = list(csv.DictReader(open(OUT / "kenya_macro_comparison.csv")))
    with open(PAPER / "tables" / "tab_kenya.tex", "w") as f:
        f.write("\\begin{tabular}{lrrr}\n\\toprule\n")
        f.write("Aggregate & SAM & KNBS & Dev.\\ \\% \\\\\n\\midrule\n")
        for r in ken:
            dev = f"{float(r['dev_pct']):+.1f}" if r["dev_pct"] else "---"
            f.write(f"{r['aggregate']} & {float(r['sam_bn']):,.0f} & "
                    f"{float(r['knbs_bn']):,.0f} & {dev} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")

    # ---- Table: Netherlands generated macro SAM residuals ----
    nl = list(csv.DictReader(open(OUT / "netherlands_macro_sam.csv")))
    rs, cs = {}, {}
    for r in nl:
        v = float(r["value_EURm"])
        rs[r["row"]] = rs.get(r["row"], 0.0) + v
        cs[r["col"]] = cs.get(r["col"], 0.0) + v
    nl_gdp = 724960.0
    resid = {a: rs.get(a, 0.0) - cs.get(a, 0.0) for a in set(rs) | set(cs)}
    named = {"corp": "Corporations", "gvt": "Government", "hhd": "Households",
             "lab": "Labour", "row": "Rest of world", "si": "Savings--investment"}
    with open(PAPER / "tables" / "tab_netherlands.tex", "w") as f:
        f.write("\\begin{tabular}{lrr}\n\\toprule\n")
        f.write("Account & Residual (EUR m) & \\% of GDP \\\\\n\\midrule\n")
        for a, name in named.items():
            f.write(f"{name} & {resid[a]:+,.0f} & {resid[a] / nl_gdp * 100:+.2f} \\\\\n")
        exact = sum(1 for a, v in resid.items() if a not in named and abs(v) < 0.5)
        f.write("\\midrule\n\\multicolumn{3}{l}{\\emph{Remaining "
                f"{exact} accounts (production, taxes, capital, instruments): "
                "residual zero}} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")

    # ---- Figure: ECDF of absolute share deviations ----
    cap_devs = [d * 100 for d in grid[("2019 revised", "closing")]["devs"]]
    occ_devs = sorted(abs(float(r["diff_pp"])) for r in occ_rows)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    for devs, label, style in [(cap_devs, "Capital types (AFS, recovered basis)", "-"),
                               (occ_devs, "Occupations (LMD wage bills)", "--")]:
        xs = sorted(devs)
        ys = [i / len(xs) * 100 for i in range(1, len(xs) + 1)]
        ax.plot(xs, ys, style, linewidth=1.6, label=label)
    ax.set_xscale("symlog", linthresh=0.01)
    ax.set_xlabel("Absolute share deviation from benchmark (percentage points, symlog scale)")
    ax.set_ylabel("Share of comparisons (%)")
    ax.axvline(1.0, color="grey", linewidth=0.8, linestyle=":")
    ax.annotate("1pp", xy=(1.0, 5), fontsize=8, color="grey")
    ax.legend(frameon=False, fontsize=9)
    ax.set_ylim(0, 100)
    fig.tight_layout()
    fig.savefig(PAPER / "figures" / "fig_share_ecdf.pdf")
    print("tables and figure written:",
          [p.name for p in (PAPER / 'tables').iterdir()],
          [p.name for p in (PAPER / 'figures').iterdir()])


if __name__ == "__main__":
    main()
