"""Audit a published SAM from its distributed file and public controls.

The audit ladder matches what the public record supports (the
"replicability spectrum" of the P001 working paper):

 1. Structure: parse the matrix, verify every account's receipts equal
    its payments, detect the file's rounding grain, and summarise the
    account structure. Needs only the distributed SAM.
 2. Macro controls: compute the SAM's implied national aggregates and
    compare them with published national-accounts figures. Needs a
    classification of accounts into canonical kinds and a controls file.
 3. Cell level: rebuild the matrix from primary sources. That is a
    construction exercise, not a comparison - see the build recipe and
    the P001 South Africa pipeline.

Two input layouts are supported: long form (row,col,value CSV) and
matrix form (first column = row labels, header = column labels; a
leading code column and total rows/columns are tolerated and skipped).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# canonical account kinds for the aggregate computations
KINDS = {"activity", "commodity", "factor", "household", "enterprise",
         "government", "tax-product", "tax-direct", "savings", "stocks",
         "row", "transaction-cost", "other"}


def read_long_csv(path: str | Path) -> dict[tuple[str, str], float]:
    """row,col,value CSV (header row required)."""
    cells: dict[tuple[str, str], float] = {}
    with open(path, encoding="utf-8-sig") as f:
        for rec in csv.DictReader(f):
            keys = list(rec)
            v = float(rec[keys[2]])
            if v:
                cells[(rec[keys[0]].strip(), rec[keys[1]].strip())] = v
    return cells


def read_matrix_csv(path: str | Path,
                    code_col: bool = False) -> dict[tuple[str, str], float]:
    """Square matrix CSV: header = column codes, first column = row codes
    (with an optional second code column, as in IFPRI distributions);
    rows/columns labelled 'total' are skipped."""
    rows = list(csv.reader(open(path, encoding="utf-8-sig")))
    skip = 2 if code_col else 1
    col_codes = [c.strip() for c in rows[0][skip:]]
    cells: dict[tuple[str, str], float] = {}
    for r in rows[1:]:
        code = r[skip - 1].strip()
        if not code or code.lower() == "total" or r[0].strip().lower() == "total":
            continue
        for j, v in enumerate(r[skip:]):
            v = v.strip().replace(",", "")
            if v and col_codes[j].lower() != "total":
                try:
                    x = float(v)
                except ValueError:
                    continue
                if x:
                    cells[(code, col_codes[j])] = x
    return cells


def read_kinds(path: str | Path) -> dict[str, str]:
    """account,kind CSV; kinds must be canonical (see KINDS)."""
    kinds: dict[str, str] = {}
    with open(path, encoding="utf-8-sig") as f:
        for rec in csv.DictReader(f):
            keys = list(rec)
            k = rec[keys[1]].strip()
            assert k in KINDS, f"unknown kind '{k}' (allowed: {sorted(KINDS)})"
            kinds[rec[keys[0]].strip()] = k
    return kinds


@dataclass
class AuditResult:
    accounts: list[str]
    n_cells: int
    gaps: dict[str, float]              # account -> rowsum - colsum
    grain: float                        # detected rounding grain of values
    kinds: dict[str, str] = field(default_factory=dict)
    aggregates: dict[str, float] = field(default_factory=dict)
    controls: dict[str, float] = field(default_factory=dict)
    coverage_gap: list[str] = field(default_factory=list)

    @property
    def max_gap(self) -> tuple[str, float]:
        a = max(self.gaps, key=lambda x: abs(self.gaps[x]))
        return a, self.gaps[a]


def _detect_grain(values: list[float]) -> float:
    for g in (1000.0, 100.0, 10.0, 1.0, 0.1, 0.01):
        if all(abs(v / g - round(v / g)) < 1e-9 for v in values):
            return g
    return 0.0


def audit(cells: dict[tuple[str, str], float],
          kinds: dict[str, str] | None = None,
          controls: dict[str, float] | None = None) -> AuditResult:
    rowsum: dict[str, float] = {}
    colsum: dict[str, float] = {}
    for (r, c), v in cells.items():
        rowsum[r] = rowsum.get(r, 0.0) + v
        colsum[c] = colsum.get(c, 0.0) + v
    accounts = sorted(set(rowsum) | set(colsum))
    res = AuditResult(
        accounts=accounts, n_cells=len(cells),
        gaps={a: rowsum.get(a, 0.0) - colsum.get(a, 0.0) for a in accounts},
        grain=_detect_grain(list(cells.values())),
        kinds=dict(kinds or {}), controls=dict(controls or {}))
    if not kinds:
        return res

    res.coverage_gap = [a for a in accounts if a not in kinds]
    of = {k: {a for a, x in kinds.items() if x == k} for k in KINDS}

    def flow(rk: str, ck: str) -> float:
        return sum(v for (r, c), v in cells.items()
                   if r in of[rk] and c in of[ck])

    gva = flow("factor", "activity")
    ptx = flow("tax-product", "commodity") + flow("tax-product", "household")
    res.aggregates = {
        "GVA (factor payments by activities)": gva,
        "Taxes on products": ptx,
        "GDP at market prices": gva + ptx,
        # marketed purchases plus direct household-to-activity flows
        # (home consumption, as in Nexus-style SAMs)
        "Private consumption":
            flow("commodity", "household") + flow("activity", "household"),
        "Government consumption": flow("commodity", "government"),
        "Gross fixed capital formation": flow("commodity", "savings"),
        "Changes in inventories": flow("commodity", "stocks"),
        "Exports": flow("commodity", "row"),
        "Imports": flow("row", "commodity"),
    }
    return res


def write_report(res: AuditResult, path: str | Path,
                 title: str = "SAM structural audit") -> None:
    with open(path, "w") as f:
        f.write(f"# {title}\n\nGenerated {date.today()} by "
                f"edikit.pipeline.audit.\n\n## Structure\n\n")
        a, g = res.max_gap
        within = sum(1 for v in res.gaps.values() if abs(v) <= res.grain / 2
                     or abs(v) <= 1e-6)
        f.write(f"- Accounts: {len(res.accounts)}; nonzero cells: "
                f"{res.n_cells:,}\n")
        f.write(f"- Rounding grain of the distributed values: "
                f"{res.grain:g}\n" if res.grain else
                "- Values are not on a uniform rounding grain\n")
        f.write(f"- Balance: max |receipts - payments| = {abs(g):,.4f} "
                f"({a}); accounts balanced within half the rounding grain: "
                f"{within}/{len(res.accounts)}\n")
        if res.grain >= 1.0 and abs(g) > 0:
            f.write("- Note: a rounded distribution of a balanced matrix "
                    "is itself unbalanced; imbalances up to a few grains "
                    "are a property of the file, not the estimate\n")
        if res.kinds:
            f.write("\n## Macro aggregates\n\n")
            if res.coverage_gap:
                f.write(f"- WARNING: {len(res.coverage_gap)} accounts have "
                        f"no kind and are excluded from aggregates: "
                        f"{', '.join(res.coverage_gap[:10])}\n\n")
            if res.controls:
                f.write("| Aggregate | SAM | Control | Dev. % |\n"
                        "|---|---|---|---|\n")
                for k, v in res.aggregates.items():
                    c = res.controls.get(k)
                    dev = f"{(v - c) / abs(c) * 100:+.1f}" if c else "-"
                    cs = f"{c:,.1f}" if c is not None else "-"
                    f.write(f"| {k} | {v:,.1f} | {cs} | {dev} |\n")
                f.write("\nA balanced SAM cannot carry a statistical "
                        "discrepancy: if the published accounts do, the "
                        "reconciliation reallocated it, and the deviation "
                        "pattern above indicates the aggregates through "
                        "which it was absorbed (aggregate data cannot "
                        "identify the allocation uniquely).\n")
            else:
                for k, v in res.aggregates.items():
                    f.write(f"- {k}: {v:,.1f}\n")
