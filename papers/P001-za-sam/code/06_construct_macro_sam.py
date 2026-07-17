"""Construct the 2019 macro SAM from SARB data and validate against the benchmark.

This is the first *constructive* step of P001: every institutional cell of the
macro SAM is computed from the SARB Quarterly Bulletin series (S-004) using
the formulas transcribed from the benchmark's technical note
(derived/macro_sam_formulas.csv), then compared with the same cell aggregated
from the distributed benchmark SAM (S-003).

Macro accounts: activities, commodities, labour (10 occupations), capital
(6 types), enterprises, households (14 groups), government, atx, stx, mtx,
dtx, dstk, si, row. The benchmark's margin account transacts only with
commodities (verified here), so it consolidates away exactly, as in the
technical note's Table 2.

Two formula entries are special: mtx-from-commodities rests on unpublished
Stats SA customs data (computed here as the benchmark value, flagged), and
two RoW cells are defined as residuals in the note itself.

Run from this directory, after 01 and 04:
    python 06_construct_macro_sam.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.kbp import evaluate_formula, read_kbp_zips  # noqa: E402
from edikit.data.sam import read_labeled_matrix  # noqa: E402

DATA = Path(__file__).parents[1] / "data"
OUT = Path(__file__).parents[1] / "outputs"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"
SARB_ZIPS = sorted(str(p) for p in (DATA / "raw" / "sarb").glob("*.zip"))
YEAR = 2019

OCCUPATIONS = {"mang", "prof", "tech", "cler", "sale", "skag", "craf", "oper",
               "elmn", "doms"}
CAPITAL = {"land", "immo", "nitc", "trnp", "mach", "inta"}


def macro_group(code: str, kinds: dict[str, str]) -> str | None:
    """Map a benchmark account code to its Table-2 macro account."""
    if code in OCCUPATIONS:
        return "labour"
    if code in CAPITAL:
        return "capital"
    if code == "marg":
        return None  # consolidated away (transacts only with commodities)
    kind = kinds[code]
    return {
        "activity": "activities", "commodity": "commodities",
        "enterprise": "enterprises", "household": "households",
        "government": "government", "rest_of_world": "row",
        "tax": code,                       # atx / stx / mtx / dtx stay separate
        "savings_investment": code,        # si / dstk stay separate
    }[kind]


def main() -> None:
    # 1. Load KBP data and check the margin-consolidation premise
    kbp = read_kbp_zips(SARB_ZIPS)
    sam = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    kinds = {}
    with open(DATA / "derived" / "sam_account_map.csv", newline="") as f:
        for r in csv.DictReader(f):
            kinds[r["code"]] = r["kind"]

    marg_partners = {c for (r, c), v in sam.cells.items() if r == "marg"} | \
                    {r for (r, c), v in sam.cells.items() if c == "marg"}
    assert all(kinds[p] == "commodity" for p in marg_partners), \
        f"margin account transacts beyond commodities: {marg_partners}"

    # 2. Aggregate the benchmark to macro accounts
    bench: dict[tuple[str, str], float] = {}
    for (r, c), v in sam.cells.items():
        gr, gc = macro_group(r, kinds), macro_group(c, kinds)
        if gr and gc and gr != gc or (gr and gc and gr == gc and gr in
                                      ("enterprises", "government", "households")):
            bench[(gr, gc)] = bench.get((gr, gc), 0.0) + v

    # 3. Compute each formula cell from KBP data (R millions)
    computed: dict[str, float] = {}
    rows_spec = list(csv.DictReader(open(DATA / "derived" / "macro_sam_formulas.csv")))
    by_entry: dict[str, dict] = {r["entry"]: r for r in rows_spec}

    def signed_sum(expr: str, resolve) -> float:
        total, sign, token = 0.0, 1, ""
        for ch in expr.replace(" ", "") + "+":
            if ch in "+-":
                if token:
                    total += sign * resolve(token)
                token, sign = "", (1 if ch == "+" else -1)
            else:
                token += ch
        return total

    def value(entry: str, cache: dict, unpublished: dict) -> float:
        """Resolve one entry; tokens may be KBP codes or other entry ids.

        `unpublished` maps UNPUBLISHED entries to the value to use - the
        benchmark cell (as-built) or a public proxy (replication scenario).
        """
        if entry in cache:
            return cache[entry]
        r = by_entry[entry]
        f = r["formula"]
        if f == "UNPUBLISHED":
            v = unpublished[entry]
        else:
            expr = f.split(":", 1)[1] if f.startswith("RESIDUAL:") else f
            v = signed_sum(expr, lambda tok: kbp.get(tok, YEAR)
                           if tok.startswith("KBP") else value(tok, cache, unpublished))
        cache[entry] = v
        return v

    unpub_entries = [r["entry"] for r in rows_spec if r["formula"] == "UNPUBLISHED"]
    as_built = {e: bench.get((by_entry[e]["row_account"], by_entry[e]["col_account"]), 0.0)
                for e in unpub_entries}
    proxy = {e: kbp.get("KBP4590J", YEAR) for e in unpub_entries}  # public proxy for vii

    cache_built: dict = {}
    cache_proxy: dict = {}
    results = []
    for r in rows_spec:
        v = value(r["entry"], cache_built, as_built)
        vp = value(r["entry"], cache_proxy, proxy)
        b = bench.get((r["row_account"], r["col_account"]), 0.0)
        dev = (v - b) / b * 100 if b else (0.0 if abs(v) < 0.5 else float("inf"))
        pdev = (vp - b) / b * 100 if b else (0.0 if abs(vp) < 0.5 else float("inf"))
        results.append({**r, "computed_Rm": v, "benchmark_Rm": b, "dev_pct": dev,
                        "proxy_dev_pct": pdev,
                        "flag": ("unpublished-input" if r["formula"] == "UNPUBLISHED"
                                 else "residual" if r["formula"].startswith("RESIDUAL")
                                 else "")})

    # 4. Coverage: benchmark macro cells not covered by any formula
    covered = {(r["row_account"], r["col_account"]) for r in rows_spec}
    uncovered = {k: v for k, v in bench.items() if k not in covered and abs(v) > 0.5}

    OUT.mkdir(exist_ok=True)
    with open(OUT / "macro_sam_construction.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["entry", "row_account", "col_account",
                                          "formula", "computed_Rm", "benchmark_Rm",
                                          "dev_pct", "proxy_dev_pct", "flag",
                                          "tn_value_rbn", "note"])
        w.writeheader()
        for r in results:
            w.writerow({k: (f"{v:.3f}" if isinstance(v, float) else v)
                        for k, v in r.items() if k in w.fieldnames})

    devs = [abs(r["dev_pct"]) for r in results if r["flag"] != "unpublished-input"]
    proxy_affected = [r for r in results
                      if abs(r["proxy_dev_pct"] - r["dev_pct"]) > 0.001]
    exact = sum(1 for d in devs if d <= 0.01)
    within1 = sum(1 for d in devs if d <= 1.0)
    worst = sorted((r for r in results if r["flag"] != "unpublished-input"),
                   key=lambda r: -abs(r["dev_pct"]))[:10]

    with open(OUT / "macro_sam_construction.md", "w") as f:
        f.write(f"# Macro-SAM construction report\n\nGenerated {date.today()} by "
                f"code/06_construct_macro_sam.py.\n\n")
        f.write(f"Every institutional cell computed from SARB KBP series "
                f"(December 2022 vintage) using the technical note's formulas, "
                f"compared with the benchmark aggregated to Table-2 macro accounts "
                f"(margin account verified to consolidate away exactly).\n\n")
        f.write(f"- Cells: {len(results)} ({len(devs)} KBP-computable, 1 unpublished-input, "
                f"2 residual-defined)\n")
        f.write(f"- Exact (<=0.01%): {exact}/{len(devs)}; within 1%: {within1}/{len(devs)}; "
                f"median |dev| {sorted(devs)[len(devs)//2]:.4f}%; max |dev| "
                f"{max(devs):.4f}%\n")
        f.write(f"- Benchmark macro cells not covered by any formula: "
                f"{ {k: round(v,1) for k, v in uncovered.items()} if uncovered else 'none'}\n\n")
        f.write("## Largest deviations\n\n")
        f.write("| Entry | Cell | Formula | Computed (Rm) | Benchmark (Rm) | Dev % |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in worst:
            f.write(f"| {r['entry']} | ({r['row_account']},{r['col_account']}) | "
                    f"{r['formula'][:34]} | {r['computed_Rm']:,.0f} | "
                    f"{r['benchmark_Rm']:,.0f} | {r['dev_pct']:+.4f} |\n")
        f.write("\n## Cost of the unpublished input (public-replication scenario)\n\n")
        f.write("Replacing the unpublished customs figure with the public proxy "
                "KBP4590J changes these cells:\n\n")
        for r in proxy_affected:
            f.write(f"- {r['entry']} ({r['row_account']},{r['col_account']}): "
                    f"as-built {r['dev_pct']:+.3f}% -> proxy {r['proxy_dev_pct']:+.3f}%\n")
        f.write("\nFull table: macro_sam_construction.csv.\n")

    print(f"cells: {len(results)}; exact: {exact}/{len(devs)}; within 1%: "
          f"{within1}/{len(devs)}; max |dev|: {max(devs):.4f}%")
    print(f"uncovered benchmark cells: {len(uncovered)}")
    for k, v in list(uncovered.items())[:8]:
        print(f"  {k}: R{v:,.0f}m")


if __name__ == "__main__":
    main()
