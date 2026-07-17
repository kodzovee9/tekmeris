"""Reader for Eurostat dissemination-API responses (JSON-stat 2.0).

The statistics/1.0 endpoint returns JSON-stat: dimension order in `id`,
sizes in `size`, category codes with linear positions under
`dimension/<dim>/category/index`, and values in a sparse map from linear
index to number. This reader decodes that into {(cat1, cat2, ...): value}
keyed by category codes, plus label lookups - enough to drive SUT ingestion
and sector-accounts work for any country and year the API serves.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class EurostatTable:
    label: str
    dims: list[str]
    categories: dict[str, list[str]]           # dim -> codes in position order
    labels: dict[str, dict[str, str]]          # dim -> code -> label
    values: dict[tuple[str, ...], float] = field(default_factory=dict)

    def slice(self, **fixed: str) -> dict[tuple[str, ...], float]:
        """Cells matching the fixed dim=code constraints, keyed by the
        remaining dimensions' codes (in dim order)."""
        free = [i for i, d in enumerate(self.dims) if d not in fixed]
        out: dict[tuple[str, ...], float] = {}
        for key, v in self.values.items():
            if all(key[self.dims.index(d)] == c for d, c in fixed.items()):
                out[tuple(key[i] for i in free)] = v
        return out

    def value(self, default: float | None = None, **coords: str) -> float | None:
        key = tuple(coords[d] for d in self.dims)
        return self.values.get(key, default)


def read_jsonstat(path: str) -> EurostatTable:
    d = json.load(open(path, encoding="utf-8"))
    if "error" in d and "value" not in d:
        raise ValueError(f"{path}: API error payload: {str(d['error'])[:200]}")
    dims = list(d["id"])
    sizes = list(d["size"])
    categories: dict[str, list[str]] = {}
    labels: dict[str, dict[str, str]] = {}
    for dim in dims:
        cat = d["dimension"][dim]["category"]
        order = sorted(cat["index"], key=lambda c: cat["index"][c])
        categories[dim] = order
        labels[dim] = dict(cat.get("label", {}))
    table = EurostatTable(label=d.get("label", ""), dims=dims,
                          categories=categories, labels=labels)
    for lin_str, v in d["value"].items():
        if v is None:
            continue
        lin = int(lin_str)
        key = []
        for size, dim in zip(reversed(sizes), reversed(dims)):
            key.append(categories[dim][lin % size])
            lin //= size
        table.values[tuple(reversed(key))] = float(v)
    return table
