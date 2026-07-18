"""Assemble P001's own 2019 South Africa SAM (v0.1) from public data only.

This is the paper's centerpiece: a complete 209-account SAM built from the
registered public sources - StatsSA SUT (production, final demand), SARB KBP
series (institutional cells, public-replication scenario), AFS (capital
split), LMD (occupation split), LCS (household groups) - with every rule
explicit and every departure from the benchmark's undocumented choices
disclosed in the V1_RULES list below.

Outputs: the SAM as a tidy CSV (row, col, value), per-account balance
diagnostics, and a cell-level comparison against the benchmark by block.

V1 disclosed simplifications (each is a numbered, revisitable rule):
 R1 mtx by commodity: total = KBP4590J (public proxy for the unpublished
    customs data), allocated across commodities by import shares.
 R2 stx by commodity: SUT product-tax column minus R1's mtx.
 R3 capital-type shares for the six activities absent from the AFS
    (aagri, aeduc, afins, ainsp, anobs, apuba): economy-wide average shares.
 R4 household consumption pattern: each commodity's household total is split
    across the 14 groups by total-expenditure shares (uniform Engel pattern;
    the LCS item-level expenditure file is not in the archive we hold).
 R5 occupation-to-household wage distribution: the aggregate LCS wage-income
    group shares are applied to every occupation (the benchmark expands by
    education; the LCS education detail is deferred to v0.2).
 R6 other household-facing cells (from ent/gvt/row; to dtx/si/row): split by
    LCS wage-income group shares (income-side) as a disclosed proxy.
 R7 capital-income distribution to institutions is uniform across the six
    capital types (this one is the benchmark's own documented rule).

Run from this directory, after 01, 04, 07, 08:  python 10_assemble_sam.py
"""

import csv
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.concordance import Concordance  # noqa: E402
from edikit.data.kbp import read_kbp_zips  # noqa: E402
from edikit.data.sam import read_labeled_matrix  # noqa: E402
from edikit.data.sut import read_supply_table, read_use_table  # noqa: E402

DATA = Path(__file__).parents[1] / "data"
OUT = Path(__file__).parents[1] / "outputs"
SUT_XLSX = DATA / "raw" / "statssa" / "Supply and use tables 2018 - 2019.xlsx"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"
LCS_ZIP = DATA / "external" / "lcs-2014-2015-v1-csv.zip"
YEAR = 2019

OCCS = ["mang", "prof", "tech", "cler", "sale", "skag", "craf", "oper", "elmn", "doms"]
CAPS = ["land", "immo", "nitc", "trnp", "mach", "inta"]
HHDS = [f"hhd{i}" for i in range(1, 15)]


def load_shares(path: str, key_cols: tuple[str, str], val_col: str) -> dict:
    out = {}
    with open(OUT / path, newline="") as f:
        for r in csv.DictReader(f):
            out[(r[key_cols[0]], r[key_cols[1]])] = float(r[val_col])
    return out


def household_group_shares() -> dict[str, list[float]]:
    """Weighted group shares of total expenditure and of wage income,
    using household-expenditure deciles (identified in 09)."""
    rows = []
    with zipfile.ZipFile(LCS_ZIP) as z, z.open("csv/lcs-2014-2015-households-v1.csv") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace")):
            try:
                rows.append((float(r["expenditure"]), float(r["hholds_wgt"]), r["UQNO"]))
            except ValueError:
                continue
    rows.sort()
    total_w = sum(w for _, w, _ in rows)
    cuts = [0.1 * i for i in range(1, 10)] + [0.92, 0.94, 0.96, 0.98]
    assign, cum, ci = {}, 0.0, 0
    for v, w, u in rows:
        cum += w
        while ci < len(cuts) and cum / total_w > cuts[ci] + 1e-12:
            ci += 1
        assign[u] = ci
    exp = [0.0] * 14
    for v, w, u in rows:
        exp[assign[u]] += v * w
    wage = [0.0] * 14
    with zipfile.ZipFile(LCS_ZIP) as z, z.open("csv/lcs-2014-2015-personincome-v1.csv") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace")):
            if r["Coicop"].strip() == "50110000" and r["UQNO"] in assign:
                try:
                    wage[assign[r["UQNO"]]] += float(r["Valueannualized_adj_weighted"])
                except ValueError:
                    pass
    return {"expenditure": [v / sum(exp) for v in exp],
            "wage": [v / sum(wage) for v in wage]}


def main() -> None:
    iconc = Concordance.from_csv(str(DATA / "derived" / "concordance_industries.csv"))
    pconc = Concordance.from_csv(str(DATA / "derived" / "concordance_products.csv"))
    supply = read_supply_table(str(SUT_XLSX), YEAR)
    use = read_use_table(str(SUT_XLSX), YEAR)
    kbp = read_kbp_zips(sorted(str(p) for p in (DATA / "raw" / "sarb").glob("*.zip")))

    def K(code: str) -> float:
        return kbp.get(code, YEAR)

    sam: dict[tuple[str, str], float] = {}

    def add(r: str, c: str, v: float) -> None:
        if abs(v) > 1e-9:
            sam[(r, c)] = sam.get((r, c), 0.0) + v

    # ---- production block from the SUT ----
    for (p, i), v in use.intermediate.items():
        add(pconc.mapping[p], iconc.mapping[i], v)                     # c x a
    for (p, i), v in supply.matrix.items():
        add(iconc.mapping[i], pconc.mapping[p], v)                     # a x c (make)
    lab, cap, atx_a = {}, {}, {}
    for i in use.industries:
        a = iconc.mapping[i]
        lab[a] = lab.get(a, 0.0) + use.value_added.get(("D1", i), 0.0)
        cap[a] = cap.get(a, 0.0) + use.value_added.get(("B2/3", i), 0.0)
        atx_a[a] = atx_a.get(a, 0.0) + use.value_added.get(("D2/3", i), 0.0)

    occ_sh = load_shares("occupation_split.csv", ("activity", "occupation"), "lmd_share")
    for a, tot in lab.items():
        for o in OCCS:
            add(o, a, tot * occ_sh.get((a, o), 0.0))

    cap_sh = load_shares("capital_split.csv", ("activity", "type"), "afs_share")
    covered = {a for (a, _) in cap_sh}
    econ_tot = {t: sum(cap_sh.get((a, t), 0.0) * cap[a] for a in covered if a in cap)
                for t in CAPS}
    econ_sum = sum(econ_tot.values())
    avg_sh = {t: econ_tot[t] / econ_sum for t in CAPS}                 # R3
    for a, tot in cap.items():
        sh = {t: cap_sh.get((a, t), 0.0) for t in CAPS} if a in covered else avg_sh
        for t in CAPS:
            add(t, a, tot * sh[t])
    for a, v in atx_a.items():
        add("atx", a, v)
    add("gvt", "atx", sum(atx_a.values()))

    # ---- commodity accounts: margins, taxes, imports, final demand ----
    prod_by_comm: dict[str, dict[str, float]] = {}
    for p in supply.products:
        c = pconc.mapping[p.code]
        d = prod_by_comm.setdefault(c, {"marg": 0.0, "tax": 0.0, "basic": 0.0, "dom": 0.0})
        d["marg"] += supply.margins.get(p.code, 0.0)
        d["tax"] += supply.taxes_less_subsidies.get(p.code, 0.0)
        d["basic"] += supply.total_supply_basic.get(p.code, 0.0)
    for (p, i), v in supply.matrix.items():
        prod_by_comm[pconc.mapping[p]]["dom"] += v
    imports = {c: max(d["basic"] - d["dom"], 0.0) for c, d in prod_by_comm.items()}
    imp_tot = sum(imports.values())
    mtx_total = K("KBP4590J")                                          # R1
    for c, d in prod_by_comm.items():
        if d["marg"] > 0:
            add("marg", c, d["marg"])
        elif d["marg"] < 0:
            add(c, "marg", -d["marg"])
        mtx_c = mtx_total * imports[c] / imp_tot                       # R1
        add("mtx", c, mtx_c)
        add("stx", c, d["tax"] - mtx_c)                                # R2
        add(c, "row", 0.0)  # placeholder ordering; exports added below
        if imports[c] > 0:
            add("row", c, imports[c])
    add("gvt", "stx", sum(d["tax"] for d in prod_by_comm.values()) - mtx_total)
    add("gvt", "mtx", mtx_total)

    hh_sh = household_group_shares()
    exp_sh, wage_sh = hh_sh["expenditure"], hh_sh["wage"]
    fd_by_comm: dict[tuple[str, str], float] = {}
    for (p, cat), v in use.final_demand.items():
        fd_by_comm[(pconc.mapping[p], cat)] = fd_by_comm.get((pconc.mapping[p], cat), 0.0) + v
    for (c, cat), v in fd_by_comm.items():
        if cat == "Exports":
            add(c, "row", v)
        elif cat == "Households":
            for k, g in enumerate(HHDS):
                add(c, g, v * exp_sh[k])                               # R4
        elif cat == "General government":
            add(c, "gvt", v)
        elif cat == "Fixed capital formation":
            add(c, "si", v)
        elif cat in ("Changes in inventories", "Residual"):
            add(c, "dstk", v)
    add("dstk", "si", sum(v for (c, cat), v in fd_by_comm.items()
                          if cat in ("Changes in inventories", "Residual")))

    # ---- institutional block from KBP formulas (public-replication) ----
    lab_total = sum(lab.values())
    hh_lab = K("KBP6240J")                                             # ix
    row_lab = lab_total + K("KBP6208J") - hh_lab                       # x residual
    for j, o in enumerate(OCCS):
        o_tot = sum(sam.get((o, a), 0.0) for a in lab) + \
                K("KBP6208J") * (sum(sam.get((o, a), 0.0) for a in lab) / lab_total)
        add(o, "row", K("KBP6208J") * (sum(sam.get((o, a2), 0.0) for a2 in lab) / lab_total))
        hh_part = hh_lab * (o_tot / (lab_total + K("KBP6208J")))
        for k, g in enumerate(HHDS):
            add(g, o, hh_part * wage_sh[k])                            # R5
        add("row", o, o_tot - hh_part)                                 # x, per occupation

    cap_total = sum(cap.values())
    ent_cap = K("KBP6706J") + K("KBP6746J") + K("KBP6904J") - K("KBP6901J")   # xi
    hh_cap = K("KBP6826J")                                             # xii
    gvt_cap = K("KBP6786J")                                            # xiii
    row_cap = cap_total + K("KBP6904J") - ent_cap - hh_cap - gvt_cap   # xiv residual
    for t in CAPS:
        t_tot = sum(sam.get((t, a), 0.0) for a in cap) + \
                K("KBP6904J") * (sum(sam.get((t, a), 0.0) for a in cap) / cap_total)
        add(t, "row", K("KBP6904J") * (sum(sam.get((t, a2), 0.0) for a2 in cap) / cap_total))
        u = t_tot / (cap_total + K("KBP6904J"))                        # R7 uniform
        add("ent", t, ent_cap * u)
        for k, g in enumerate(HHDS):
            add(g, t, hh_cap * u * wage_sh[k])                         # R6
        add("gvt", t, gvt_cap * u)
        add("row", t, row_cap * u)

    add("ent", "ent", -K("KBP6707J") + K("KBP6710J") - K("KBP6747J")
        + K("KBP6752J") + K("KBP6716J"))                               # xv (recovered)
    hh_ent = (K("KBP6721J") + K("KBP6762J") + K("KBP6827J")
              + K("KBP6838J") + K("KBP6845J"))                         # xvi
    for k, g in enumerate(HHDS):
        add(g, "ent", hh_ent * wage_sh[k])                             # R6
    add("gvt", "ent", K("KBP6718J") + K("KBP6759J") + K("KBP6787J"))   # xvii
    add("dtx", "ent", K("KBP6717J") + K("KBP6758J"))                   # xviii
    add("si", "ent", K("KBP6724J") + K("KBP6725J") + K("KBP6764J") + K("KBP6765J"))
    add("row", "ent", K("KBP6918J") + K("KBP6919J"))                   # xx

    per_group = lambda total: [(g, total * wage_sh[k]) for k, g in enumerate(HHDS)]
    for g, v in per_group(K("KBP6832J") + K("KBP6842J")):              # xxii
        add("ent", g, v)
    for g, v in per_group(K("KBP6797J") + K("KBP6840J")):              # xxiii
        add("gvt", g, v)
    for g, v in per_group(K("KBP6245J")):                              # xxiv
        add("dtx", g, v)
    for g, v in per_group(K("KBP6846J") + K("KBP6848J")):              # xxv
        add("si", g, v)
    for g, v in per_group(K("KBP6909J")):                              # xxvi
        add("row", g, v)
    for g, v in per_group(K("KBP6801J") + K("KBP6836J")):              # xxix
        add(g, "gvt", v)
    for g, v in per_group(K("KBP6912J")):                              # xliv
        add(g, "row", v)

    add("ent", "gvt", K("KBP6715J") + K("KBP6791J"))                   # xxviii
    add("gvt", "gvt", K("KBP6794J") + K("KBP6798J"))                   # xxx
    add("si", "gvt", K("KBP6803J"))                                    # xxxi
    add("row", "gvt", K("KBP6908J"))                                   # xxxii
    add("gvt", "dtx", K("KBP6717J") + K("KBP6758J") + K("KBP6245J"))   # xxxvi
    add("ent", "row", K("KBP6934J") + K("KBP6935J"))                   # xliii
    add("gvt", "row", K("KBP6911J"))                                   # xlv
    add("si", "row", K("KBP6913J"))                                    # xlvi

    # ---- diagnostics ----
    accounts = sorted({r for (r, _) in sam} | {c for (_, c) in sam})
    rowsum = {a: 0.0 for a in accounts}
    colsum = {a: 0.0 for a in accounts}
    for (r, c), v in sam.items():
        rowsum[r] += v
        colsum[c] += v
    imbal = {a: rowsum[a] - colsum[a] for a in accounts}
    worst = sorted(imbal.items(), key=lambda x: -abs(x[1]))[:12]
    gdp_scale = sum(lab.values()) + sum(cap.values())

    bench = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    ours_keys, bench_keys = set(sam), set(bench.cells)
    common = ours_keys & bench_keys
    devs = sorted(abs(sam[k] - bench.cells[k]) for k in common)
    exact = sum(1 for k in common if abs(sam[k] - bench.cells[k]) <= 0.5)

    OUT.mkdir(exist_ok=True)
    with open(OUT / "p001_sam_v01.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row", "col", "value_Rm"])
        for (r, c), v in sorted(sam.items()):
            w.writerow([r, c, f"{v:.3f}"])

    with open(OUT / "assembly_report.md", "w") as f:
        f.write(f"# P001 SAM v0.1 assembly report\n\nGenerated by "
                f"code/10_assemble_sam.py. Public inputs only; disclosed rules R1-R7 "
                f"in the script header.\n\n")
        f.write(f"- Accounts: {len(accounts)}; nonzero cells: {len(sam):,}\n")
        f.write(f"- Cells in common with benchmark: {len(common):,} of ours "
                f"{len(ours_keys):,} / benchmark {len(bench_keys):,}\n")
        f.write(f"- Common cells equal within R0.5m: {exact:,} "
                f"({exact/len(common)*100:.1f}%); median |diff| R{devs[len(devs)//2]:,.2f}m\n")
        f.write(f"- Account imbalances (row minus column), share of VA "
                f"R{gdp_scale:,.0f}m:\n\n")
        f.write("| Account | Imbalance (Rm) | % of VA |\n|---|---|---|\n")
        for a, v in worst:
            f.write(f"| {a} | {v:+,.0f} | {v/gdp_scale*100:+.3f}% |\n")
        f.write(f"\nMax |imbalance|: R{max(abs(v) for v in imbal.values()):,.0f}m. "
                f"Residual imbalances stem from rules R1-R6 and the documented "
                f"benchmark discrepancies (596 adjustment, mtx proxy); v0.2 closes "
                f"them with the balancing module.\n")

    print(f"accounts {len(accounts)}; cells {len(sam):,}; common {len(common):,}; "
          f"exact(<=R0.5m) {exact:,} ({exact/len(common)*100:.1f}%)")
    print(f"max |imbalance| R{max(abs(v) for v in imbal.values()):,.0f}m "
          f"({max(abs(v) for v in imbal.values())/gdp_scale*100:.3f}% of VA)")
    for a, v in worst[:6]:
        print(f"  {a:6s} {v:+14,.0f}")


if __name__ == "__main__":
    main()
