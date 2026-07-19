"""Cross-producer SAM reconciliation at the coarsest common aggregation.

Two independent SAMs of the same country-year rarely share an account
scheme: an official statistics-office SAM (e.g. ANSD's 65-account Senegal
matrix) and a modelling SAM (e.g. an IFPRI Nexus SAM with ~200 accounts)
disaggregate activities, factors, households and taxes along different
lines and even book the same transaction in different places. The only
level at which they can be compared cell-for-cell is a small **macro-SAM**
of national-accounting aggregates that both must satisfy.

This module reduces any SAM to that common nine-account macro grid given a
classifier that maps its accounts onto the macro classes, derives the
standard national-accounts aggregates from the reduced matrix, and lays two
or more producers' results side by side. The reduction is deliberately
lossy in exactly the way the comparison requires: it collapses each
producer's private account structure to the concepts on which producers can
be held to disagree.

The macro classes:

* ``ACT`` activities, ``COM`` commodities  — the production core;
* ``LAB`` labour, ``CAP`` capital (incl. land and mixed income) — factors;
* ``HH`` households (incl. NPISH), ``ENT`` corporations, ``GOV`` government
  — domestic institutions;
* ``SAV`` the capital account (saving, investment and stock changes);
* ``ROW`` the rest of the world.

Taxes are booked to ``GOV`` (a statistics office routes them straight to
government; a Nexus SAM interposes explicit tax accounts — the same net
flow, one account layer apart), and trade/transport margins to ``COM``
(intra-commodity, so they net out at this level).
"""

from __future__ import annotations

import csv
import re
from collections.abc import Callable
from dataclasses import dataclass, field

MACRO_ORDER = ["ACT", "COM", "LAB", "CAP", "HH", "ENT", "GOV", "SAV", "ROW"]

Classify = Callable[[str], str | None]


def scale_to_billions(unit_text: str) -> tuple[float, str]:
    """Factor to rescale values stated in ``unit_text`` to billions, plus the
    matched unit word. 'millions' -> 1e-3, 'billions'/unknown -> 1.0. Used to
    put every producer on the same billions axis whatever unit its file
    declares (a readme line, or a 'Value (CFA MLN)' column header)."""
    t = unit_text.lower()
    if re.search(r"\bmln\b|million", t):
        return 1e-3, "millions"
    if re.search(r"\bbn\b|billion|milliard", t):
        return 1.0, "billions"
    return 1.0, unit_text.strip()


def nexus_classmap(code: str) -> str | None:
    """Map an IFPRI Nexus-template account code onto a macro class.

    The Nexus template uses a fixed vocabulary across countries: ``a*``
    activities, ``c*`` commodities, ``flab*`` labour, ``fcap``/``flnd``
    capital and land, ``hhd*`` households, ``ent`` corporations, ``gov``
    government, ``row`` the rest of the world, ``s-i`` and ``dstk`` the
    capital account, ``*tax`` tax accounts and ``trc`` the transaction-cost
    (margin) pool. Returns ``None`` for a code the template does not define.
    """
    c = code.strip().lower()
    if c.startswith("flab"):
        return "LAB"
    if c.startswith(("fcap", "fln", "flnd")) or (c.startswith("f") and len(c) > 1):
        return "CAP"                       # capital, land and other factors
    if c.startswith(("hhd", "hh")):
        return "HH"                        # households (NPISH folded in by Nexus)
    if c in ("ent", "entp", "corp"):
        return "ENT"
    if c in ("gov", "govt"):
        return "GOV"
    if c == "row":
        return "ROW"
    if c in ("s-i", "si", "inv", "cap") or c.startswith("dstk") or c == "stk":
        return "SAV"                       # saving, investment and stock changes
    if c.endswith("tax"):
        return "GOV"                       # dtax/mtax/stax/... -> government
    if c in ("trc", "tcost", "marg"):
        return "COM"                       # transaction-cost pool -> commodities
    if c.startswith("a"):
        return "ACT"
    if c.startswith("c"):
        return "COM"
    return None


def jrc_classmap(code: str) -> str | None:
    """Map a JRC DataM SAM account code onto a macro class.

    The JRC African-SAM template (Mainar Causapé et al.) uses: ``a_*`` and
    ``ahf_*`` activities (the latter regional household-farm producers),
    ``c_*`` marketed and ``ch*`` self-consumed commodities, ``fl_*`` labour by
    skill and region with ``fl_irr``/``fl_nir`` land and ``flivst`` livestock
    as capital-type factors, ``fcp_*`` capital, ``flb_RW*`` rest-of-world
    labour, ``hh_*`` households, ``ent`` corporations, ``govt`` government with
    ``*tax`` tax accounts, ``inv_*``/``i_s`` the capital account, ``trcost``
    the margin pool, and ``row``/``hrow`` the rest of the world. Returns
    ``None`` for a code outside the template."""
    c = code.strip()
    if c.startswith("a_") or c.startswith("ahf"):
        return "ACT"
    if c.startswith("c_") or c.startswith("ch") or c == "trcost":
        return "COM"                       # marketed, self-consumed, and margins
    if c.startswith("flb") or re.search("SemSk|Skill|UnSkl", c):
        return "LAB"                       # labour by skill class (incl. RoW)
    if c.startswith("fcp") or c in ("fl_irr", "fl_nir", "flivst"):
        return "CAP"                       # capital, land and livestock factors
    if c.startswith("hh_"):
        return "HH"
    if c == "ent":
        return "ENT"
    if c == "govt" or c.endswith("tax"):
        return "GOV"                       # dir/ind/imp/sal/fact taxes -> government
    if c == "i_s" or c.startswith("inv"):
        return "SAV"                       # saving and investment accounts
    if c in ("row", "hrow"):
        return "ROW"                       # incl. the rest-of-world household
    return None


def read_jrc_sam(path: str) -> tuple[dict[tuple[str, str], float], str]:
    """Read a JRC DataM SAM (long form: Spending Agent, Receiving Agent,
    Value). The receiving agent is the row (income), the spending agent the
    column (expenditure). Returns the cells and the unit word parsed from the
    value column header (e.g. 'CFA MLN')."""
    cells: dict[tuple[str, str], float] = {}
    unit = ""
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        vcol = next((h for h in (reader.fieldnames or []) if h.startswith("Value")), "Value")
        m = re.search(r"\(([^)]*)\)", vcol)
        unit = m.group(1) if m else ""
        for r in reader:
            row = r["Receiving Agent (Code)"].strip()
            col = r["Spending Agent (Code)"].strip()
            v = float(r[vcol]) if r[vcol] not in (None, "") else 0.0
            if v:
                cells[(row, col)] = cells.get((row, col), 0.0) + v
    return cells, unit


def macro_reduce(cells: dict[tuple[str, str], float],
                 classify: Classify) -> tuple[dict[tuple[str, str], float], set[str]]:
    """Aggregate a SAM to the macro grid. Returns the reduced matrix and the
    set of account codes the classifier did not recognise (so an incomplete
    classification is visible, never silently dropped)."""
    out: dict[tuple[str, str], float] = {}
    unclassified: set[str] = set()
    for (r, c), v in cells.items():
        rk, ck = classify(r), classify(c)
        if rk is None:
            unclassified.add(r)
        if ck is None:
            unclassified.add(c)
        if rk and ck:
            out[(rk, ck)] = out.get((rk, ck), 0.0) + v
    return out, unclassified


def national_accounts(m: dict[tuple[str, str], float]) -> dict[str, float]:
    """Derive the standard national aggregates from a macro-SAM, twice over:
    from the income/production side and from the expenditure side. A balanced
    SAM makes the two GDP figures agree; the gap between them is a check on
    the reduction, not a property of the economy.

    Private consumption includes the direct activity->household flow: a Nexus
    SAM books home (own-account) consumption there, while an office SAM routes
    all household consumption through commodities. Counting both makes the
    aggregate comparable across the two conventions."""
    f = lambda r, c: m.get((r, c), 0.0)  # noqa: E731
    va = f("LAB", "ACT") + f("CAP", "ACT")          # value added at factor cost
    tax_prod = f("GOV", "ACT")                       # net taxes on production
    tax_products = f("GOV", "COM")                   # net taxes on products
    gdp_income = va + tax_prod + tax_products
    hh = f("COM", "HH") + f("ACT", "HH")             # incl. home consumption
    gov = f("COM", "GOV")
    capital = f("COM", "SAV")                        # GFCF + inventory change
    exports, imports = f("COM", "ROW"), f("ROW", "COM")
    gdp_exp = hh + gov + capital + exports - imports
    return {
        "Value added (factor cost)": va,
        "Net taxes on production": tax_prod,
        "Net taxes on products": tax_products,
        "GDP (income side)": gdp_income,
        "Household consumption": hh,
        "Government consumption": gov,
        "Capital formation": capital,
        "Exports": exports,
        "Imports": imports,
        "GDP (expenditure side)": gdp_exp,
    }


def macro_gaps(m: dict[tuple[str, str], float]) -> dict[str, float]:
    """Each macro account's receipts minus payments (should be ~0 in a
    balanced matrix; a residual localises where a reduction failed to
    conserve a flow)."""
    rs: dict[str, float] = {}
    cs: dict[str, float] = {}
    for (r, c), v in m.items():
        rs[r] = rs.get(r, 0.0) + v
        cs[c] = cs.get(c, 0.0) + v
    return {a: rs.get(a, 0.0) - cs.get(a, 0.0) for a in MACRO_ORDER}


@dataclass
class Producer:
    """One producer's SAM reduced to the macro grid and rescaled to a common
    unit. ``scale`` multiplies the source values onto that unit (e.g. 1e-3 to
    take ANSD's CFA millions to CFA billions)."""

    name: str
    macro_sam: dict[tuple[str, str], float]
    unit: str = ""
    scale: float = 1.0
    unclassified: set[str] = field(default_factory=set)

    def scaled(self) -> dict[tuple[str, str], float]:
        return {k: v * self.scale for k, v in self.macro_sam.items()}

    def accounts_na(self) -> dict[str, float]:
        return {k: v * self.scale for k, v in national_accounts(self.macro_sam).items()}


def write_reconciliation(path, producers: list[Producer], *, title: str,
                         year: int, unit: str, notes: list[str] | None = None,
                         mapping_rules: list[str] | None = None) -> None:
    """Write the reconciliation report: national aggregates and the full
    macro-SAM for each producer side by side, with pairwise divergences when
    exactly two producers are compared."""
    na = {p.name: p.accounts_na() for p in producers}
    keys = list(national_accounts({}).keys())
    with open(path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write("Generated by `edikit.pipeline.reconcile`. Each producer's SAM "
                "is reduced to a common nine-account macro grid (activities, "
                "commodities, labour, capital, households, corporations, "
                "government, capital account, rest of world) and its national "
                f"aggregates derived. All figures {unit}.\n\n")

        names = [p.name for p in producers]
        f.write("## National aggregates\n\n")
        header = ["Aggregate", *names] + (["Diff", "Dev. %"] if len(producers) == 2 else [])
        f.write("| " + " | ".join(header) + " |\n")
        f.write("|" + "---|" * len(header) + "\n")
        for k in keys:
            row = f"| {k} | " + " | ".join(f"{na[n][k]:,.0f}" for n in names)
            if len(producers) == 2:
                a, b = na[names[0]][k], na[names[1]][k]
                dev = f"{(b - a) / abs(a) * 100:+.1f}" if a else "-"
                row += f" | {b - a:+,.0f} | {dev} |"
            else:
                row += " |"
            f.write(row + "\n")

        # composition: expenditure components as a share of GDP. When two
        # producers are built on different national-accounts vintages the
        # level gap (a rebasing) can dwarf any structural disagreement; the
        # shares strip the level out and show where they really differ.
        if len(producers) == 2:
            comp = ["Household consumption", "Government consumption",
                    "Capital formation", "Exports", "Imports"]
            f.write("\n## Composition (share of GDP)\n\n")
            f.write(f"| Component | {names[0]} | {names[1]} | Δ pp |\n"
                    "|---|---|---|---|\n")
            for k in comp:
                sa = na[names[0]][k] / na[names[0]]["GDP (expenditure side)"] * 100
                sb = na[names[1]][k] / na[names[1]]["GDP (expenditure side)"] * 100
                f.write(f"| {k} | {sa:.1f}% | {sb:.1f}% | {sb - sa:+.1f} |\n")

        for p in producers:
            f.write(f"\n## Macro-SAM — {p.name} ({unit})\n\n")
            m = p.scaled()
            present = [a for a in MACRO_ORDER
                       if any((a, c) in m for c in MACRO_ORDER)
                       or any((r, a) in m for r in MACRO_ORDER)]
            f.write("| row \\ col | " + " | ".join(present) + " |\n")
            f.write("|" + "---|" * (len(present) + 1) + "\n")
            for r in present:
                cells = " | ".join(
                    (f"{m[(r, c)]:,.0f}" if (r, c) in m else "") for c in present)
                f.write(f"| **{r}** | {cells} |\n")
            g = macro_gaps(p.macro_sam)
            worst = max(g, key=lambda a: abs(g[a]))
            f.write(f"\nBalance: max |receipts − payments| = "
                    f"{abs(g[worst]) * p.scale:,.1f} ({worst}).\n")
            if p.unclassified:
                f.write(f"\n**Unclassified accounts** ({len(p.unclassified)}): "
                        f"{', '.join(sorted(p.unclassified))}\n")

        if mapping_rules:
            f.write("\n## Mapping rules\n\n")
            for i, r in enumerate(mapping_rules, 1):
                f.write(f"{i}. {r}\n")
        if notes:
            f.write("\n## Notes\n\n")
            for n in notes:
                f.write(f"- {n}\n")
