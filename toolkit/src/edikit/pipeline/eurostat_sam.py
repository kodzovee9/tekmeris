"""Benchmark-free macro-SAM generation for any ESA-transmitting country.

The Eurostat dissemination API serves harmonised supply-use tables
(naio_10_cp15/16) and non-financial sector accounts (nasa_10_nf_tr) for
every country in the ESA 2010 transmission programme. Because the item
codes are harmonised, one generation routine covers them all: fetch(),
generate(), and the report writers below turn a country code and a year
into a validated macro SAM with every account residual reported.

Design rules (N1-N4, documented in the P001 working paper):
 N1 Inter-institutional flows are routed through instrument accounts
    (property income d4x, current taxes dtx, social contributions and
    benefits soc_c/soc_b, other transfers trf, pension adjustment d8,
    capital transfers d9) because Eurostat publishes sector totals
    paid/received, not who-to-whom counterparts.
 N2 Sectors: corporations = S11+S12; government = S13; households incl.
    NPISH = S14_S15; rest of world = S2.
 N3 Imports per product come from the supply table's P7 column; the
    identity TS_BP = domestic output + imports is kept as a cross-check.
 N4 The residents-abroad / cif-fob adjustment rows (OP_RES, OP_NRES,
    ADJ_P6, ADJ_P7) are routed to their exact cells on the RoW account.
 N5 Balancing (optional, balance()): negative cells flip to their
    positive transpose, account targets are the mean of receipts and
    payments, and RAS runs with every adjustment factor logged. The
    pre-balancing matrix with attributed residuals is the diagnostic
    product; the balanced matrix is the SAM.

Validation is entirely internal - the ESA identities of the tables and
the balance of the generated matrix - and residuals are reported, never
balanced away silently.
"""

from __future__ import annotations

import csv
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..data.eurostat import read_jsonstat
from ..model.balancing import BalanceResult, ras

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
DATASETS = {
    "supply": ("naio_10_cp15", {"unit": "MIO_EUR", "stk_flow": "TOTAL"}),
    "use": ("naio_10_cp16", {"unit": "MIO_EUR", "stk_flow": "TOTAL"}),
    "sectors": ("nasa_10_nf_tr", {"unit": "CP_MEUR"}),
}
FD_COLS = ["P3_S13", "P3_S14", "P3_S15", "P51G", "P52", "P53", "P6"]
SUPPLY_SPECIALS = {"TOTAL", "TS_PP", "TS_BP", "OTTM", "D21X31",
                   "P7", "P7_B0", "P7_D0", "P7_U2", "P7_U3"}
SECTORS = {"corp": ["S11", "S12"], "gvt": ["S13"], "hhd": ["S14_S15"]}
INSTRUMENTS = {"d4x": "D4", "dtx": "D5", "soc_c": "D61", "soc_b": "D62",
               "trf": "D7", "d8": "D8", "d9": "D9"}


def coverage(code: str):
    """NACE/CPA code -> (section letter, set of 2-digit divisions or None
    for a whole section). Handles 'C10-12', 'C31_32', 'J59_60', 'C11', 'D'."""
    body = code[4:] if code.startswith("CPA_") else code
    sec, rest = body[0], body[1:]
    if not rest or not any(ch.isdigit() for ch in rest):
        return sec, None            # whole section (D, O, P, U, ...)
    divs = set()
    for part in re.split(r"[_]", rest):
        m = re.match(r"(\d+)[A-Z]?(?:-(\d+))?$", part)
        if not m:
            return sec, None
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        divs.update(range(lo, hi + 1))
    return sec, divs


def partition(codes: list[str]) -> list[str]:
    """Finest non-overlapping tiling: drop any code whose coverage is
    strictly contained in another present code's coverage (Eurostat lists
    mix A64 aggregates like 'C10-12' with sub-details like 'C11')."""
    cov = {c: coverage(c) for c in codes}
    out = []
    for c in codes:
        sec, divs = cov[c]
        contained = False
        for d in codes:
            if d == c:
                continue
            dsec, ddivs = cov[d]
            if dsec != sec:
                continue
            if ddivs is None and divs is not None:
                contained = True      # a whole-section code also present
            elif ddivs is not None and divs is not None and divs < ddivs:
                contained = True
        if not contained:
            out.append(c)
    return out


def fetch(country: str, year: int, dest: str | Path,
          overwrite: bool = False) -> dict[str, Path]:
    """Download the three datasets for one country-year into dest/,
    named <dataset>_<COUNTRY>_<YEAR>.json; existing files are reused."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, (dataset, filters) in DATASETS.items():
        path = dest / f"{dataset}_{country}_{year}.json"
        paths[key] = path
        if path.exists() and not overwrite:
            continue
        query = "&".join(f"{k}={v}" for k, v in
                         {"format": "JSON", "freq": "A", **filters,
                          "geo": country, "time": year}.items())
        req = urllib.request.Request(f"{API}/{dataset}?{query}",
                                     headers={"User-Agent": "edikit"})
        try:
            import certifi
            import ssl
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:  # fall back to the platform trust store
            ctx = None
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            path.write_bytes(r.read())
    return paths


@dataclass
class MacroSAMResult:
    country: str
    year: int
    inds: list[str]
    prods: list[str]
    findings: list[str]            # output/VA identity violations
    cross_diffs: list[str]         # supply-vs-use output mismatches
    n3_check: float                # max |TS_BP - domestic - imports|
    n_closed: int                  # products whose commodity balance closes
    prod_resid: dict[str, float]
    sam: dict[tuple[str, str], float]
    imbalances: dict[str, float] = field(default_factory=dict)
    gdp: float = 0.0
    # aggregate -> leaf-detail share of the published total, where the two
    # differ: <1.0 means cells are suppressed/confidential in the source
    coverage: dict[str, float] = field(default_factory=dict)

    @property
    def accounts(self) -> list[str]:
        return sorted(self.imbalances)


def generate(country: str, year: int,
             paths: dict[str, Path]) -> MacroSAMResult:
    """Build the macro SAM from fetched files; no benchmark consulted."""
    sup = read_jsonstat(str(paths["supply"]))
    use = read_jsonstat(str(paths["use"]))
    nasa = read_jsonstat(str(paths["sectors"]))
    yr = str(year)

    scells = sup.slice(freq="A", unit="MIO_EUR", stk_flow="TOTAL",
                       geo=country, time=yr)
    ucells = use.slice(freq="A", unit="MIO_EUR", stk_flow="TOTAL",
                       geo=country, time=yr)

    # industry set from the SUPPLY table (no final-demand columns there),
    # leaf-filtered over the codes the country actually reports: some
    # countries list an aggregate and its sub-details but populate only one
    # level, so codes with entirely absent rows must not join the tiling
    # (explicit zeros count as reported; suppressed cells are absent)
    populated = {i for (i, _) in scells}
    inds = partition([i for i in sup.categories["ind_impv"]
                      if i not in SUPPLY_SPECIALS and i in populated])
    pop_prods = {p for (_, p) in scells}
    prods = partition([p for p in sup.categories["prd_amo"]
                       if p.startswith("CPA_") and p != "CPA_TOTAL"
                       and p in pop_prods])
    tot_ind = sum(scells.get(("TOTAL", p), 0.0) for p in prods)
    tiled = sum(scells.get((i, p), 0.0) for i in inds for p in prods)
    # overcounting means the partition double-counts - always a bug;
    # undercounting means suppressed/confidential cells - a property of
    # the source, recorded as coverage and reported
    assert tiled - tot_ind <= max(1.0, 1e-6 * tot_ind), \
        f"industry partition double-counts: {tiled:,.0f} vs {tot_ind:,.0f}"
    missing = [i for i in inds if i not in use.categories["ind_use"]]
    assert not missing, f"industries absent from use table: {missing}"
    uinds = inds

    coverage: dict[str, float] = {}

    def pub_or_leaf(name: str, published: float | None, leaf: float,
                    tol: float = 1.0) -> float:
        """Prefer the leaf-detail sum when it reproduces the published
        aggregate (exact accounting); otherwise trust the published cell
        and record the detail's coverage of it."""
        if published is None or abs(published - leaf) <= tol:
            return leaf
        if published:
            coverage[name] = leaf / published
        return published

    # --- supply side ---
    V = {(p, i): v for (i, p), v in scells.items() if p in prods and i in inds}
    ts_bp = {p: scells.get(("TS_BP", p), 0.0) for p in prods}
    ts_pp = {p: scells.get(("TS_PP", p), 0.0) for p in prods}
    dom_out = {p: sum(V.get((p, i), 0.0) for i in inds) for p in prods}
    imports = {p: scells.get(("P7", p), 0.0) for p in prods}
    taxes = {p: scells.get(("D21X31", p), 0.0) for p in prods}
    n3_check = max(abs(ts_bp[p] - dom_out[p] - imports[p]) for p in prods)

    # --- use side ---
    U = {(p, i): v for (i, p), v in ucells.items() if p in prods and i in uinds}
    fd = {(p, c): ucells.get((c, p), 0.0) for p in prods for c in FD_COLS}
    va = {(code, i): ucells.get((i, code), 0.0)
          for code in ("D1", "D29X39", "B2A3G", "B1G", "P1") for i in uinds}

    # --- internal identity checks (tolerance EUR 1m) ---
    findings = []
    for i in uinds:
        p2 = sum(U.get((p, i), 0.0) for p in prods)
        gap1 = va[("P1", i)] - p2 - va[("B1G", i)]
        gap2 = va[("B1G", i)] - (va[("D1", i)] + va[("D29X39", i)]
                                 + va[("B2A3G", i)])
        if abs(gap1) > 1.0:
            findings.append(f"output identity {i}: gap {gap1:,.1f}")
        if abs(gap2) > 1.0:
            findings.append(f"VA identity {i}: gap {gap2:,.1f}")
    sup_out = {i: sum(V.get((p, i), 0.0) for p in prods) for i in inds}
    cross = [i for i in inds if abs(sup_out[i] - va[("P1", i)]) > 1.0]
    # per-product intermediates from the published TOTAL industry column,
    # which is complete even when industry detail is suppressed
    inter_p = {p: ucells.get(("TOTAL", p),
                             sum(U.get((p, i), 0.0) for i in uinds))
               for p in prods}
    prod_resid = {p: ts_pp[p] - inter_p[p]
                  - sum(fd[(p, c)] for c in FD_COLS) for p in prods}
    n_closed = sum(1 for p in prods if abs(prod_resid[p]) <= 1.0)

    # --- macro SAM (EUR million) ---
    sam: dict[tuple[str, str], float] = {}

    def add(r, c, v):
        if abs(v) > 1e-9:
            sam[(r, c)] = sam.get((r, c), 0.0) + v

    # every aggregate prefers the exact leaf sum but falls back to the
    # published total cell when detail is suppressed (see pub_or_leaf)
    va_tot = {code: pub_or_leaf(f"value added ({code})",
                                ucells.get(("TOTAL", code)),
                                sum(va[(code, i)] for i in uinds))
              for code in ("D1", "B2A3G", "D29X39")}
    fd_tot = {c: pub_or_leaf(f"final demand ({c})",
                             ucells.get((c, "CPA_TOTAL")),
                             sum(fd[(p, c)] for p in prods))
              for c in FD_COLS}
    add("com", "act", pub_or_leaf("intermediate consumption",
                                  ucells.get(("TOTAL", "CPA_TOTAL")),
                                  sum(U.values())))
    add("act", "com", pub_or_leaf("gross output",
                                  scells.get(("TOTAL", "CPA_TOTAL")),
                                  sum(sup_out.values())))
    add("lab", "act", va_tot["D1"])
    add("cap", "act", va_tot["B2A3G"])
    add("atx", "act", va_tot["D29X39"])
    add("gvt", "atx", va_tot["D29X39"])
    add("row", "com", pub_or_leaf("imports (P7)",
                                  scells.get(("P7", "CPA_TOTAL")),
                                  sum(imports.values())))
    add("ptx", "com", pub_or_leaf("product taxes (D21X31)",
                                  scells.get(("D21X31", "CPA_TOTAL")),
                                  sum(taxes.values())))
    add("gvt", "ptx", sam.get(("ptx", "com"), 0.0))
    # adjustment rows, addressed by their exact cells (N4); the published
    # CPA_TOTAL cells exclude them, so no double counting
    opres_hh = ucells.get(("P3_S14", "OP_RES"), 0.0)
    opnres_hh = ucells.get(("P3_S14", "OP_NRES"), 0.0)  # negative by convention
    adj_p6 = ucells.get(("P6", "ADJ_P6"), 0.0)
    imp_adj = scells.get(("P7", "ADJ_P7"), 0.0)
    add("com", "hhd", fd_tot["P3_S14"] + fd_tot["P3_S15"]
        + opnres_hh)                       # non-residents' purchases -> exports
    add("row", "hhd", opres_hh)            # residents' direct purchases abroad
    add("com", "gvt", fd_tot["P3_S13"])
    add("com", "si", fd_tot["P51G"] + fd_tot["P52"] + fd_tot["P53"])
    add("com", "row", fd_tot["P6"] - opnres_hh + adj_p6)
    add("row", "com", imp_adj)             # cif/fob adjustment on imports

    def n(item, sector, direct):
        return nasa.value(freq="A", unit="CP_MEUR", direct=direct,
                          na_item=item, sector=sector, geo=country,
                          time=yr, default=0.0)

    # factors to sectors: nasa closes labour to the euro
    for name, secs in SECTORS.items():
        add(name, "cap", sum(n("B2A3G", s, "RECV") or n("B2A3G", s, "PAID")
                             for s in secs))
    add("hhd", "lab", n("D1", "S14_S15", "RECV"))
    add("lab", "row", n("D1", "S2", "PAID"))
    add("row", "lab", n("D1", "S2", "RECV"))
    cap_in = sam.get(("cap", "act"), 0.0)
    cap_out = sum(sam.get((name, "cap"), 0.0) for name in SECTORS)
    add("row", "cap", cap_in - cap_out)                            # residual

    # instrument accounts (N1)
    for acct, item in INSTRUMENTS.items():
        for name, secs in SECTORS.items():
            paid = sum(n(item, s, "PAID") for s in secs)
            recv = sum(n(item, s, "RECV") for s in secs)
            if paid:
                add(acct, name, paid)
            if recv:
                add(name, acct, recv)
        add(acct, "row", n(item, "S2", "PAID"))
        add("row", acct, n(item, "S2", "RECV"))

    # saving and accumulation: sectors save into si; the economy's net
    # lending B9 (S1) flows from si to the rest of the world
    for name, secs in SECTORS.items():
        add("si", name, sum(n("B8G", s, "RECV") or n("B8G", s, "PAID")
                            for s in secs))
    add("row", "si", n("B9", "S1", "PAID"))

    rowsum, colsum = {}, {}
    for (r, c), v in sam.items():
        rowsum[r] = rowsum.get(r, 0.0) + v
        colsum[c] = colsum.get(c, 0.0) + v
    accounts = sorted(set(rowsum) | set(colsum))
    res = MacroSAMResult(
        country=country, year=year, inds=inds, prods=prods,
        findings=findings, cross_diffs=cross, n3_check=n3_check,
        n_closed=n_closed, prod_resid=prod_resid, sam=sam,
        imbalances={a: rowsum.get(a, 0.0) - colsum.get(a, 0.0)
                    for a in accounts},
        gdp=(sam.get(("lab", "act"), 0.0) + sam.get(("cap", "act"), 0.0)
             + sam.get(("atx", "act"), 0.0)),
        coverage=coverage)
    return res


def balance(res: MacroSAMResult, targets: str = "mean",
            ) -> tuple[BalanceResult, list[tuple[str, str]]]:
    """Balance the generated matrix by RAS with every adjustment logged.

    Negative cells are first flipped to their transpose as positive flows
    (a payment of -v from a to b is a payment of +v from b to a; every
    account's receipts-minus-payments residual and every institution's
    net position are invariant under the flip) and the flipped cells are
    returned. Each account's single target is, per `targets`, the
    arithmetic mean of its receipts and payments (the symmetric default,
    design rule N5), its receipts ("receipts"), or its payments
    ("payments"); any choice of one target per account makes the row- and
    column-target totals agree by construction. The alternatives exist
    for sensitivity analysis; scaling to a common total keeps the
    variants comparable cell by cell."""
    seed: dict[tuple[str, str], float] = {}
    flipped: list[tuple[str, str]] = []
    for (r, c), v in res.sam.items():
        if v < 0:
            flipped.append((r, c))
            seed[(c, r)] = seed.get((c, r), 0.0) - v
        else:
            seed[(r, c)] = seed.get((r, c), 0.0) + v
    rowsum: dict[str, float] = {}
    colsum: dict[str, float] = {}
    for (r, c), v in seed.items():
        rowsum[r] = rowsum.get(r, 0.0) + v
        colsum[c] = colsum.get(c, 0.0) + v
    accounts = set(rowsum) | set(colsum)
    mean = {a: (rowsum.get(a, 0.0) + colsum.get(a, 0.0)) / 2.0
            for a in accounts}
    if targets == "mean":
        t = mean
    else:
        base = rowsum if targets == "receipts" else colsum
        # scale to the mean variant's total so alternatives stay
        # comparable cell by cell
        scale = sum(mean.values()) / sum(base.get(a, 0.0) for a in accounts)
        t = {a: base.get(a, 0.0) * scale for a in accounts}
    return ras(seed, t, dict(t)), flipped


def write_report(res: MacroSAMResult, path: str | Path) -> None:
    """Generic markdown validation report for one generated macro SAM."""
    with open(path, "w") as f:
        f.write(f"# {res.country} {res.year}: benchmark-free macro-SAM "
                f"generation\n\nGenerated {date.today()} by "
                f"edikit.pipeline.eurostat_sam from the Eurostat "
                f"dissemination API; no benchmark consulted.\n\n")
        f.write(f"## Internal validation of the Eurostat SUT\n\n"
                f"- Industries: {len(res.inds)}; products: {len(res.prods)}\n"
                f"- Output and VA identities: {len(res.findings)} findings "
                f"at EUR 1m tolerance\n")
        for x in res.findings[:12]:
            f.write(f"  - {x}\n")
        f.write(f"- Supply-vs-use output cross-check: "
                f"{len(res.cross_diffs)} industries differ (>EUR 1m)\n")
        f.write(f"- Import identity cross-check (TS_BP = domestic + imports): "
                f"max gap EUR {res.n3_check:,.1f}m\n")
        f.write(f"- Commodity balance closure: {res.n_closed}/{len(res.prods)} "
                f"products within EUR 1m; largest residual EUR "
                f"{max(abs(v) for v in res.prod_resid.values()):,.0f}m\n")
        if res.coverage:
            f.write("- Suppressed detail (macro cells use the published "
                    "totals; the leaf detail covers):\n")
            for name, cov in sorted(res.coverage.items()):
                f.write(f"  - {name}: {cov * 100:.1f}%\n")
            f.write("- Note: identity findings above may reflect the same "
                    "suppression (an identity cannot close over cells the "
                    "source withholds), not errors in the published data.\n")
        f.write("\n")
        f.write(f"## Generated macro SAM ({len(res.accounts)} accounts, "
                f"EUR million)\n\n"
                f"- GDP at basic prices (generated): EUR {res.gdp:,.0f}m\n"
                f"- Account balance residuals (row minus column):\n\n")
        f.write("| Account | Residual (EURm) | % of GDP |\n|---|---|---|\n")
        for a in res.accounts:
            v = res.imbalances[a]
            f.write(f"| {a} | {v:+,.0f} | {v / res.gdp * 100:+.3f}% |\n")
        f.write("\nResiduals are reported, not hidden; they typically attach "
                "to ESA boundary items (domestic-vs-national concept in "
                "compensation, mixed-income attribution, capital-account "
                "detail). Inspect any account above a few percent of GDP "
                "before use.\n")


def write_csv(res: MacroSAMResult, path: str | Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row", "col", "value_EURm"])
        for (r, c), v in sorted(res.sam.items()):
            w.writerow([r, c, f"{v:.1f}"])
