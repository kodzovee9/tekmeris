"""Matrix balancing: RAS and GRAS (biproportional adjustment) with full
diagnostics.

Adjusts a seed matrix to match prescribed row and column totals while staying
as close as possible (in the biproportional sense) to the seed structure.
``ras`` handles non-negative seeds; ``gras`` (Junius & Oosterhaven 2003)
generalises it to seeds with negative entries — as a real social accounting
matrix has (margin self-supply, cif/fob adjustments, disinvestment) — keeping
the sign of every cell. Every call returns diagnostics — iterations,
convergence, and the distribution of adjustment factors — because an
adjustment that cannot be inspected is an adjustment that cannot be trusted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

Matrix = dict[tuple[str, str], float]


@dataclass
class BalanceResult:
    matrix: Matrix
    iterations: int
    converged: bool
    max_row_gap: float
    max_col_gap: float
    # multiplicative adjustment per cell vs the seed (only cells with seed > 0)
    factors: dict[tuple[str, str], float] = field(default_factory=dict)

    def max_factor_deviation(self) -> float:
        """Largest |factor - 1| across cells: how far balancing bent the seed."""
        return max((abs(f - 1.0) for f in self.factors.values()), default=0.0)


def ras(seed: Matrix, row_targets: dict[str, float], col_targets: dict[str, float],
        max_iter: int = 500, tol: float = 1e-9) -> BalanceResult:
    """Classic RAS. Requires a non-negative seed, positive targets consistent
    in total (sum of row targets == sum of column targets within tolerance),
    and a seed that connects every row/column with a positive target."""
    if any(v < 0 for v in seed.values()):
        raise ValueError("RAS requires a non-negative seed; use GRAS for negatives")
    tot_r, tot_c = sum(row_targets.values()), sum(col_targets.values())
    if abs(tot_r - tot_c) > max(1e-6, 1e-9 * abs(tot_r)):
        raise ValueError(f"row targets sum {tot_r!r} != column targets sum {tot_c!r}")

    m = {k: v for k, v in seed.items() if v > 0}
    for r, t in row_targets.items():
        if t > 0 and not any(rr == r for (rr, _) in m):
            raise ValueError(f"row {r!r} has a positive target but an empty seed row")
    for c, t in col_targets.items():
        if t > 0 and not any(cc == c for (_, cc) in m):
            raise ValueError(f"column {c!r} has a positive target but an empty seed column")

    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        rowsum: dict[str, float] = {}
        for (r, _), v in m.items():
            rowsum[r] = rowsum.get(r, 0.0) + v
        for (r, c) in list(m):
            if rowsum[r] > 0 and r in row_targets:
                m[(r, c)] *= row_targets[r] / rowsum[r]
        colsum: dict[str, float] = {}
        for (_, c), v in m.items():
            colsum[c] = colsum.get(c, 0.0) + v
        for (r, c) in list(m):
            if colsum[c] > 0 and c in col_targets:
                m[(r, c)] *= col_targets[c] / colsum[c]

        rowsum = {}
        colsum = {}
        for (r, c), v in m.items():
            rowsum[r] = rowsum.get(r, 0.0) + v
            colsum[c] = colsum.get(c, 0.0) + v
        rgap = max((abs(rowsum.get(r, 0.0) - t) for r, t in row_targets.items()),
                   default=0.0)
        cgap = max((abs(colsum.get(c, 0.0) - t) for c, t in col_targets.items()),
                   default=0.0)
        scale = max(tot_r, 1.0)
        if rgap <= tol * scale and cgap <= tol * scale:
            converged = True
            break

    factors = {k: m[k] / seed[k] for k in m if seed.get(k, 0.0) > 0}
    return BalanceResult(matrix=m, iterations=it, converged=converged,
                         max_row_gap=rgap, max_col_gap=cgap, factors=factors)


def _line_mult(target: float, pos: float, neg: float) -> float:
    """Positive multiplier m solving  m*pos - neg/m = target  (the per-line
    GRAS update). ``pos`` is the seed line's positive mass weighted by the
    other dimension's current multipliers, ``neg`` its negative mass weighted
    by their inverses."""
    if pos > 1e-15:
        return (target + math.sqrt(target * target + 4.0 * pos * neg)) / (2.0 * pos)
    if neg > 1e-15:                     # line has only negative seed entries
        return -neg / target if target < -1e-15 else 1.0
    return 1.0                          # empty line — leave untouched


def gras(seed: Matrix, row_targets: dict[str, float], col_targets: dict[str, float],
         max_iter: int = 500, tol: float = 1e-9) -> BalanceResult:
    """Generalized RAS (Junius & Oosterhaven 2003). Adjusts a seed that may
    contain negative entries to match the row/column targets, preserving the
    sign of every seed cell and staying biproportionally close. Reduces to RAS
    when the seed is non-negative. Cells absent from the seed stay zero (the
    zero structure is not invented), so a target line must carry some seed
    mass; the totals must agree in aggregate."""
    tot_r, tot_c = sum(row_targets.values()), sum(col_targets.values())
    if abs(tot_r - tot_c) > max(1e-6, 1e-9 * abs(tot_r)):
        raise ValueError(f"row targets sum {tot_r!r} != column targets sum {tot_c!r}")

    # split the seed into positive (P) and absolute-negative (N) parts
    P = {k: v for k, v in seed.items() if v > 0}
    N = {k: -v for k, v in seed.items() if v < 0}
    keys = set(P) | set(N)
    by_row: dict[str, list[tuple[str, str]]] = {}
    by_col: dict[str, list[tuple[str, str]]] = {}
    for k in keys:
        by_row.setdefault(k[0], []).append(k)
        by_col.setdefault(k[1], []).append(k)

    r = {i: 1.0 for i in row_targets}
    s = {j: 1.0 for j in col_targets}
    scale = max(abs(tot_r), 1.0)
    converged, it, rgap, cgap, prev = False, 0, 0.0, 0.0, float("inf")
    for it in range(1, max_iter + 1):
        for i, t in row_targets.items():
            pos = sum(P[k] * s[k[1]] for k in by_row.get(i, ()) if k in P)
            neg = sum(N[k] / s[k[1]] for k in by_row.get(i, ()) if k in N)
            r[i] = _line_mult(t, pos, neg)
        for j, t in col_targets.items():
            pos = sum(P[k] * r[k[0]] for k in by_col.get(j, ()) if k in P)
            neg = sum(N[k] / r[k[0]] for k in by_col.get(j, ()) if k in N)
            s[j] = _line_mult(t, pos, neg)

        rowsum: dict[str, float] = {}
        colsum: dict[str, float] = {}
        for k in keys:
            x = P.get(k, 0.0) * r[k[0]] * s[k[1]] - N.get(k, 0.0) / (r[k[0]] * s[k[1]])
            rowsum[k[0]] = rowsum.get(k[0], 0.0) + x
            colsum[k[1]] = colsum.get(k[1], 0.0) + x
        rgap = max((abs(rowsum.get(i, 0.0) - t) for i, t in row_targets.items()),
                   default=0.0)
        cgap = max((abs(colsum.get(j, 0.0) - t) for j, t in col_targets.items()),
                   default=0.0)
        gap = max(rgap, cgap)
        if gap <= tol * scale:
            converged = True
            break
        if prev - gap <= tol * scale:      # fixed point: no further improvement
            break                          # (best solution the seed structure allows)
        prev = gap

    m = {k: P.get(k, 0.0) * r[k[0]] * s[k[1]] - N.get(k, 0.0) / (r[k[0]] * s[k[1]])
         for k in keys}
    factors = {k: m[k] / seed[k] for k in keys if seed.get(k, 0.0) != 0}
    return BalanceResult(matrix=m, iterations=it, converged=converged,
                         max_row_gap=rgap, max_col_gap=cgap, factors=factors)
