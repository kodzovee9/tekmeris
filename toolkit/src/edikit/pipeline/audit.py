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
from pathlib import Path

# canonical account kinds for the aggregate computations
KINDS = {"activity", "commodity", "factor", "household", "enterprise",
         "government", "tax-product", "tax-direct", "savings", "stocks",
         "row", "transaction-cost", "other"}


def read_long_csv(path: str | Path) -> dict[tuple[str, str], float]:
    """row,col,value CSV (header row required)."""
    cells: dict[tuple[str, str], float] = {}
    seen: set[tuple[str, str]] = set()
    with open(path, encoding="utf-8-sig") as f:
        for rec in csv.DictReader(f):
            keys = list(rec)
            v = float(rec[keys[2]])
            key = (rec[keys[0]].strip(), rec[keys[1]].strip())
            if key in seen:
                # a repeated cell would otherwise overwrite the earlier
                # value silently - data loss nobody would see
                raise ValueError(f"{path}: cell {key} appears more than once")
            seen.add(key)
            if v:
                cells[key] = v
    return cells


def read_matrix_csv(path: str | Path,
                    code_col: bool = False) -> dict[tuple[str, str], float]:
    """Square matrix CSV: header = column codes, first column = row codes
    (with an optional second code column, as in IFPRI distributions);
    rows/columns labelled 'total' are skipped."""
    rows = list(csv.reader(open(path, encoding="utf-8-sig")))
    skip = 2 if code_col else 1
    col_codes = [c.strip() for c in rows[0][skip:]]
    dup_cols = sorted({c for c in col_codes
                       if c and c.lower() != "total" and col_codes.count(c) > 1})
    if dup_cols:
        raise ValueError(f"{path}: column codes appear more than once: "
                         f"{dup_cols}")
    cells: dict[tuple[str, str], float] = {}
    seen_rows: set[str] = set()
    for r in rows[1:]:
        code = r[skip - 1].strip()
        if not code or code.lower() == "total" or r[0].strip().lower() == "total":
            continue
        if code in seen_rows:
            raise ValueError(f"{path}: row code {code!r} appears more than "
                             f"once")
        seen_rows.add(code)
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
            if k not in KINDS:
                raise ValueError(f"{path}: unknown kind {k!r} for account "
                                 f"{rec[keys[0]].strip()!r} "
                                 f"(allowed: {sorted(KINDS)})")
            acct = rec[keys[0]].strip()
            if acct in kinds:
                raise ValueError(f"{path}: account {acct!r} is classified "
                                 f"more than once")
            kinds[acct] = k
    return kinds


def read_controls(path: str | Path) -> dict[str, float]:
    """aggregate,value CSV of published national-accounts controls."""
    controls: dict[str, float] = {}
    with open(path, encoding="utf-8-sig") as f:
        for rec in csv.DictReader(f):
            keys = list(rec)
            name = rec[keys[0]].strip()
            if name in controls:
                raise ValueError(f"{path}: control {name!r} appears more "
                                 f"than once")
            controls[name] = float(rec[keys[1]])
    return controls


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
    # kinds given for accounts the matrix does not contain (typos, or a
    # classification table written for a different version of the SAM)
    phantom: list[str] = field(default_factory=list)
    # largest imbalance rounding alone can produce in each account: half a
    # grain per nonzero cell in the account's row and column. An imbalance
    # beyond it is a property of the matrix, not of its rounding.
    rounding_bound: dict[str, float] = field(default_factory=dict)

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
          controls: dict[str, float] | None = None,
          strict: bool = False) -> AuditResult:
    """Structural audit, plus macro aggregates when `kinds` is given.

    By default an account with no kind is reported (WARNING in the report)
    and left out of the aggregates, so a partial classification still gives
    a partial audit. With strict=True any unclassified account, or any kind
    given for an account the matrix does not contain, raises instead: use it
    when the aggregates will be relied on.
    """
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
    if res.grain:
        ncell: dict[str, int] = {}
        for (r, c) in cells:
            if r == c:      # a diagonal cell cancels in receipts - payments
                continue
            ncell[r] = ncell.get(r, 0) + 1
            ncell[c] = ncell.get(c, 0) + 1
        res.rounding_bound = {a: 0.5 * res.grain * ncell.get(a, 0)
                              for a in accounts}
    if not kinds:
        return res

    res.coverage_gap = [a for a in accounts if a not in kinds]
    res.phantom = sorted(a for a in kinds if a not in set(accounts))
    if strict and (res.coverage_gap or res.phantom):
        raise ValueError(
            f"classification incomplete: {len(res.coverage_gap)} accounts "
            f"without a kind {res.coverage_gap[:10]}, {len(res.phantom)} "
            f"kinds for accounts not in the matrix {res.phantom[:10]}")
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
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {title}\n\nGenerated by "
                f"edikit.pipeline.audit.\n\n## Structure\n\n")
        a, g = res.max_gap
        # Without a uniform grain, count against the four decimals printed.
        tol, label = ((res.grain / 2, "within half the rounding grain")
                      if res.grain else (5e-5, "to the four decimals shown"))
        within = sum(1 for v in res.gaps.values() if abs(v) <= tol)
        f.write(f"- Accounts: {len(res.accounts)}; nonzero cells: "
                f"{res.n_cells:,}\n")
        f.write(f"- Rounding grain of the distributed values: "
                f"{res.grain:g}\n" if res.grain else
                "- Values are not on a uniform rounding grain\n")
        f.write(f"- Balance: max |receipts - payments| = {abs(g):,.4f} "
                f"({a}); accounts balanced {label}: "
                f"{within}/{len(res.accounts)}\n")
        if res.rounding_bound and abs(g) > 0:
            beyond = sorted(a for a, v in res.gaps.items()
                            if abs(v) > res.rounding_bound[a] + 1e-9)
            f.write(f"- Rounding test: each value is off by at most half a "
                    f"grain, so rounding alone can unbalance an account by at "
                    f"most half a grain per nonzero cell in its row and "
                    f"column. Accounts whose imbalance exceeds that bound: "
                    f"{len(beyond)}/{len(res.accounts)}"
                    + (f" ({', '.join(beyond)})" if beyond else "") + "\n")
        if res.kinds:
            f.write("\n## Macro aggregates\n\n")
            if res.coverage_gap:
                f.write(f"- WARNING: {len(res.coverage_gap)} accounts have "
                        f"no kind and are excluded from aggregates: "
                        f"{', '.join(res.coverage_gap)}\n\n")
            if res.phantom:
                f.write(f"- WARNING: {len(res.phantom)} accounts are "
                        f"classified but absent from the matrix: "
                        f"{', '.join(res.phantom)}\n\n")
            if res.controls:
                f.write("| Aggregate | SAM | Control | Dev. % |\n"
                        "|---|---|---|---|\n")
                for k, v in res.aggregates.items():
                    c = res.controls.get(k)
                    dev = f"{(v - c) / abs(c) * 100:+.1f}" if c else "-"
                    cs = f"{c:,.1f}" if c is not None else "-"
                    f.write(f"| {k} | {v:,.1f} | {cs} | {dev} |\n")
                # Report what is observed and stop there: the deviations
                # say where the SAM departs from the controls, not why.
                f.write("\nThe deviations show where the SAM departs from "
                        "the published controls, not why. If the published "
                        "accounts carry a statistical discrepancy, a "
                        "balanced SAM cannot reproduce every control, but "
                        "aggregate data alone cannot say which aggregates "
                        "absorbed it or whether other causes contribute.\n")
            else:
                for k, v in res.aggregates.items():
                    f.write(f"- {k}: {v:,.1f}\n")
