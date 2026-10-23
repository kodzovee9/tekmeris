"""Benchmark-free macro-SAM generation for ESA-transmitting countries.

The Eurostat dissemination API serves harmonised supply-use tables
(naio_10_cp15/16) and non-financial sector accounts (nasa_10_nf_tr) for
countries in the ESA 2010 transmission programme (coverage varies by
country-year; the build recipe's COVERAGE.md records a full sweep).
Because the item codes are harmonised, one routine serves them: fetch(),
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
from pathlib import Path

from ..data.eurostat import read_jsonstat
from ..model.balancing import BalanceResult, ras

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
# How far the leaf-industry sum may exceed the published TOTAL before the
# partition is treated as double counting. Not zero, because some sources'
# own detail exceeds their published total (Denmark 2019, +1.7% in an
# earlier release). A double count of a section smaller than this would pass
# undetected; the manuscript states the tolerance for that reason.
TILING_TOLERANCE = 0.05

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
            elif (ddivs is not None and divs is not None and divs == ddivs
                  and len(c) > len(d)):
                # equal coverage at two granularities (e.g. L68 alongside
                # L68A/L68B): keep the coarser code, drop the suffixed one
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
    # closing entries: cells whose value is a residual that makes an account
    # close, not an observed flow. Recorded so every report can state them;
    # an unreported plug would contradict "adjustment is never silent".
    plugs: dict[tuple[str, str], float] = field(default_factory=dict)
    # vintage stamp of each input dataset ("updated" in the JSON-stat file)
    vintages: dict[str, str] = field(default_factory=dict)
    # the same aggregate as measured by the supply-use tables and by the
    # sector accounts: label -> (SUT value, sector-account value)
    cross_source: dict[str, tuple[float, float]] = field(default_factory=dict)
    # items computed from the inputs that bear on an account's residual:
    # account -> [(description, value)]. Descriptive, not causal: the report
    # flags an item as matching only when it equals the residual within 1m.
    residual_items: dict[str, list[tuple[str, float]]] = field(
        default_factory=dict)
    # (item, sector) pairs the generator needed but the source publishes on
    # neither side; each was used as zero
    missing_inputs: list[str] = field(default_factory=list)

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
    if not inds or not prods:
        raise ValueError(f"{country} {year}: no supply-table data returned "
                         f"(the dataset does not cover this country-year)")
    tot_ind = sum(scells.get(("TOTAL", p), 0.0) for p in prods)
    tiled = sum(scells.get((i, p), 0.0) for i in inds for p in prods)
    # gross overcounting means the partition double-counts - a bug;
    # small excesses occur where a source's own detail disagrees with its
    # published TOTAL column (Denmark 2019, +1.7% in an earlier release), and
    # undercounts mean suppressed cells - both are source properties, recorded as
    # coverage diagnostics, and the macro cells anchor to published totals
    # Explicit raises rather than `assert`: Python strips asserts under -O,
    # and a check the interpreter can silently drop is not a check.
    if tiled - tot_ind > max(TILING_TOLERANCE * tot_ind, 1.0):
        raise ValueError(
            f"{country} {year}: industry partition double-counts: leaf sum "
            f"{tiled:,.0f} exceeds the published total {tot_ind:,.0f} by more "
            f"than {TILING_TOLERANCE:.0%}")
    missing = [i for i in inds if i not in use.categories["ind_use"]]
    if missing:
        raise ValueError(f"{country} {year}: industries absent from use "
                         f"table: {missing}")
    uinds = inds

    coverage: dict[str, float] = {}
    if abs(tiled - tot_ind) > max(1.0, 1e-6 * tot_ind):
        coverage["industry detail vs published supply total"] = tiled / tot_ind

    def pub_or_leaf(name: str, published: float | None, leaf: float) -> float:
        """Prefer the leaf-detail sum when it reproduces the published
        aggregate (within EUR 1m or 0.001 per cent, whichever is larger);
        otherwise trust the published cell and record the detail's
        coverage of it."""
        if published is None or abs(published - leaf) <= max(
                1.0, 1e-5 * abs(published)):
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

    # A value the source does not publish is used as zero, because a SAM
    # cell must hold a number. Many sectors legitimately publish only one
    # side of a flow (corporations pay but do not receive social benefits),
    # so an item is recorded as missing only when a sector has no value on
    # either side - the case that can collapse an account unexplained.
    absent: set[tuple[str, str]] = set()
    present: set[tuple[str, str]] = set()

    def n(item, sector, direct):
        v = nasa.value(freq="A", unit="CP_MEUR", direct=direct,
                       na_item=item, sector=sector, geo=country, time=yr)
        if v is None:
            absent.add((item, sector))
            return 0.0
        present.add((item, sector))
        return v

    # factors to sectors: nasa closes labour to the euro
    for name, secs in SECTORS.items():
        add(name, "cap", sum(n("B2A3G", s, "RECV") or n("B2A3G", s, "PAID")
                             for s in secs))
    add("hhd", "lab", n("D1", "S14_S15", "RECV"))
    add("lab", "row", n("D1", "S2", "PAID"))
    add("row", "lab", n("D1", "S2", "RECV"))
    # Capital-account closure. cap receives gross operating surplus and mixed
    # income from the supply-use tables (cap <- act); the sector accounts
    # distribute B2A3G to the domestic sectors (cap -> sectors). The two
    # sources measure the same aggregate differently, and the difference is
    # booked against the rest of the world so the account closes. It is a
    # measurement discrepancy between sources, not an observed flow, so it is
    # recorded as a plug and stated in every report.
    cap_in = sam.get(("cap", "act"), 0.0)
    cap_out = sum(sam.get((name, "cap"), 0.0) for name in SECTORS)
    plugs = {("row", "cap"): cap_in - cap_out}
    add("row", "cap", cap_in - cap_out)

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

    # --- cross-source diagnostics (reported, never used to adjust) ---
    def either(item, sector):
        return n(item, sector, "PAID") or n(item, sector, "RECV")

    sa_gva = n("P1", "S1", "RECV") - n("P2", "S1", "PAID")
    sa_d1 = n("D1", "S1", "PAID")
    sa_b2 = sum(n("B2A3G", s, "RECV") or n("B2A3G", s, "PAID")
                for secs in SECTORS.values() for s in secs)
    sa_p3 = n("P3", "S14_S15", "PAID")
    sut_p3 = fd_tot["P3_S14"] + fd_tot["P3_S15"]
    cross_source = {
        "Gross value added at basic prices": (
            va_tot["D1"] + va_tot["B2A3G"] + va_tot["D29X39"], sa_gva),
        "Compensation of employees (D1), resident producers": (
            va_tot["D1"], sa_d1),
        "Gross operating surplus and mixed income (B2A3G)": (
            va_tot["B2A3G"], sa_b2),
        "Household final consumption (P3)": (sut_p3, sa_p3),
    }
    net_d9 = {name: sum(n("D9", s, "RECV") - n("D9", s, "PAID")
                        for s in secs) for name, secs in SECTORS.items()}
    residual_items = {
        name: [("net capital transfers received (D9), routed through the "
                "institution's account while si receives saving (B8G) "
                "before capital transfers", net_d9[name])]
        for name in SECTORS}
    residual_items["gvt"].append((
        "taxes on production and imports received, less subsidies paid, by "
        "the rest of the world (S2, mainly EU institutions); the generator "
        "credits all such taxes to domestic government",
        n("D2", "S2", "RECV") - n("D3", "S2", "PAID")))
    residual_items["hhd"].append((
        "household consumption, sector accounts less supply-use tables",
        sa_p3 - sut_p3))
    residual_items["si"] = [(
        "acquisitions less disposals of non-produced assets (NP), not "
        "represented", either("NP", "S1"))]
    residual_items["lab"] = [(
        "compensation of employees, supply-use tables less sector accounts",
        va_tot["D1"] - sa_d1)]
    residual_items["row"] = [(
        "closing entry (row,cap)", plugs[("row", "cap")])]
    vintages = {"supply": sup.updated, "use": use.updated,
                "sectors": nasa.updated}

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
        coverage=coverage, plugs=plugs, vintages=vintages,
        cross_source=cross_source, residual_items=residual_items,
        missing_inputs=sorted(f"{i} {sec}" for i, sec in absent - present))
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
    return ras(seed, t, dict(t), max_iter=20000), flipped


def write_balanced_csv(bal: BalanceResult, path: str | Path,
                       decimals: int = 1,
                       flipped: list[tuple[str, str]] | None = None,
                       plugs: dict[tuple[str, str], float] | None = None,
                       ) -> None:
    """Balanced matrix with every cell's RAS factor.

    Values are rounded to `decimals` places of EUR million (default 0.1m),
    so the written matrix balances only to that rounding even though the
    balanced matrix in memory closes to the solver's tolerance. Pass a
    larger `decimals` for a higher-precision export. Long form, one row
    per cell.

    Pass `flipped` (from balance()) and `plugs` (res.plugs) to add a note
    column marking cells that are not observed flows: closing entries, and
    cells flipped from a negative before RAS. A flipped closing entry is
    marked at its new position. Without them the format is unchanged."""
    notes: dict[tuple[str, str], str] = {}
    flips = set(flipped or [])
    for (r, c) in plugs or {}:
        pos = (c, r) if (r, c) in flips else (r, c)
        notes[pos] = ("closing entry, flipped from "
                      f"({r},{c})" if pos != (r, c) else "closing entry")
    for (r, c) in flips:
        notes.setdefault((c, r), f"flipped from ({r},{c})")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        head = ["row", "col", "value_EURm", "ras_factor"]
        w.writerow(head + ["note"] if notes else head)
        for (r, c), v in sorted(bal.matrix.items()):
            row = [r, c, f"{v:.{decimals}f}",
                   f"{bal.factors.get((r, c), 1.0):.6f}"]
            w.writerow(row + [notes.get((r, c), "")] if notes else row)


def write_report(res: MacroSAMResult, path: str | Path,
                 balance: BalanceResult | None = None,
                 flipped: list[tuple[str, str]] | None = None,
                 targets: str = "mean") -> None:
    """Generic markdown validation report for one generated macro SAM;
    pass `balance` (and `flipped`, and the `targets` rule given to
    balance()) to append the balancing diagnostics."""
    # newline="\n": the same bytes on every platform, so a report can be
    # compared byte-for-byte across operating systems like the CSVs can.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {res.country} {res.year}: benchmark-free macro-SAM "
                f"generation\n\nGenerated by "
                f"edikit.pipeline.eurostat_sam from the Eurostat "
                f"dissemination API; no benchmark consulted.\n\n")
        f.write(f"## Internal validation of the Eurostat SUT\n\n"
                f"- Industries: {len(res.inds)}; products: {len(res.prods)}\n"
                f"- Output and VA identities: {len(res.findings)} findings "
                f"at EUR 1m tolerance\n")
        for x in res.findings:
            f.write(f"  - {x}\n")
        if res.missing_inputs:
            f.write(f"- Sector-account values not published on either side "
                    f"(used as zero; any account they feed is unreliable): "
                    f"{', '.join(res.missing_inputs)}\n")
        f.write(f"- Supply-vs-use output cross-check: "
                f"{len(res.cross_diffs)} industries differ (>EUR 1m)\n")
        f.write(f"- Import identity cross-check (TS_BP = domestic + imports): "
                f"max gap EUR {res.n3_check:,.1f}m\n")
        f.write(f"- Commodity balance closure: {res.n_closed}/{len(res.prods)} "
                f"products within EUR 1m; largest residual EUR "
                f"{max(abs(v) for v in res.prod_resid.values()):,.0f}m\n")
        if res.coverage:
            f.write("- Leaf detail vs published totals (macro cells use "
                    "the published totals; below 100% = suppressed cells, "
                    "above 100% = the source's own detail exceeds its "
                    "published total):\n")
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
        if res.cross_source:
            f.write("\n## Cross-source consistency\n\n"
                    "The supply-use tables and the sector accounts measure "
                    "some aggregates twice. Differences between them are "
                    "properties of the inputs, not of the generator. "
                    "Dataset vintages (\"updated\" stamps): "
                    + "; ".join(f"{k} {v or 'not stated'}"
                                for k, v in res.vintages.items())
                    + ".\n\n| Aggregate | Supply-use tables | Sector "
                    "accounts | Difference | % |\n|---|---|---|---|---|\n")
            for name, (a, b) in res.cross_source.items():
                pct = f"{(b - a) / a * 100:+.2f}%" if a else "-"
                f.write(f"| {name} | {a:,.1f} | {b:,.1f} | {b - a:+,.1f} | "
                        f"{pct} |\n")
        if res.residual_items:
            f.write("\n## Items bearing on each residual\n\n"
                    "Each item is computed from the inputs. An item marked "
                    "= matches the residual within EUR 1m; otherwise the "
                    "items are shown with what they leave unexplained. This "
                    "describes the residuals; it does not establish their "
                    "causes.\n\n| Account | Residual | Item | Value |\n"
                    "|---|---|---|---|\n")
            for acc, items in res.residual_items.items():
                r = res.imbalances.get(acc, 0.0)
                for desc, v in items:
                    mark = " =" if abs(r - v) <= 1.0 else ""
                    f.write(f"| {acc} | {r:+,.1f} | {desc} | "
                            f"{v:+,.1f}{mark} |\n")
                if len(items) > 1:
                    tot = sum(v for _, v in items)
                    f.write(f"| {acc} | | sum of items (unexplained "
                            f"{r - tot:+,.1f}) | {tot:+,.1f} |\n")
                elif abs(r - items[0][1]) > 1.0:
                    f.write(f"| {acc} | | unexplained | "
                            f"{r - items[0][1]:+,.1f} |\n")
        f.write("\nInspect any residual above a few percent of GDP before "
                "using the matrix, starting with the items above.\n")
        if res.plugs:
            f.write("\n## Closing entries\n\n"
                    "These cells are residuals that make an account close, "
                    "not observed flows:\n\n")
            for (r, c), v in sorted(res.plugs.items()):
                f.write(f"- ({r},{c}) = EUR {v:+,.1f}m "
                        f"({v / res.gdp * 100:+.3f}% of GDP)\n")
            if ("row", "cap") in res.plugs:
                f.write("- (row,cap) closes the capital factor account "
                        "(cap): gross operating surplus and mixed income from "
                        "the supply-use tables, less the amount the sector "
                        "accounts distribute to domestic sectors. It measures "
                        "the discrepancy between the two sources (see "
                        "Cross-source consistency) and is booked against the "
                        "rest of the world, so it also appears in the row "
                        "residual. If negative, balancing flips it to "
                        "(cap,row), where it reads as factor income from "
                        "abroad; the balanced CSV's note column marks it.\n")
        if balance is not None:
            f.write("\n## Balanced macro SAM\n\n")
            if flipped:
                f.write("- Negative cells flipped to their positive "
                        "transpose before balancing: "
                        + ", ".join(f"({r},{c})" for r, c in flipped) + "\n")
            rule = {"mean": "mean(receipts, payments)",
                    "receipts": "receipts", "payments": "payments"}[targets]
            f.write(f"- RAS against account targets = {rule}: "
                    f"converged={balance.converged} in "
                    f"{balance.iterations} iterations; max residual EUR "
                    f"{max(balance.max_row_gap, balance.max_col_gap):.3f}m\n")
            fs = sorted(balance.factors.values())
            f.write(f"- Adjustment factors: {len(fs)} cells in "
                    f"[{fs[0]:.4f}, {fs[-1]:.4f}] (max |f-1| = "
                    f"{balance.max_factor_deviation() * 100:.2f}%); every "
                    f"factor ships in the balanced CSV\n")
            m = balance.matrix
            gdp_bal = (m.get(("lab", "act"), 0.0) + m.get(("cap", "act"), 0.0)
                       + m.get(("atx", "act"), 0.0))
            f.write(f"- GDP at basic prices after balancing: EUR "
                    f"{gdp_bal:,.1f}m ({(gdp_bal / res.gdp - 1) * 100:+.3f}% "
                    f"vs. generated); balancing moves aggregates, so use the "
                    f"balanced matrix only where that shift is acceptable\n")


def write_csv(res: MacroSAMResult, path: str | Path,
              decimals: int = 1) -> None:
    """Generated (unbalanced) matrix, values rounded to `decimals` places
    of EUR million (default 0.1m)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row", "col", "value_EURm"])
        for (r, c), v in sorted(res.sam.items()):
            w.writerow([r, c, f"{v:.{decimals}f}"])
