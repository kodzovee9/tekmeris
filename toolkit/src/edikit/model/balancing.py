"""Matrix balancing: RAS (biproportional adjustment) with full diagnostics.

Adjusts a non-negative seed matrix to match prescribed row and column totals
while staying as close as possible (in the biproportional sense) to the seed
structure. Every call returns diagnostics - iterations, convergence, and the
distribution of adjustment factors - because an adjustment that cannot be
inspected is an adjustment that cannot be trusted.

GRAS (for matrices with negative entries) and cross-entropy variants are
deliberate future extensions; this module refuses negative seeds rather than
silently mishandling them.
"""

from __future__ import annotations

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
