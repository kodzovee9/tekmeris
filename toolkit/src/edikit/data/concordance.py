"""Many-to-one classification concordances with validation and aggregation."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field


@dataclass
class Concordance:
    """Maps each source code to exactly one target code.

    `name` identifies the mapping; `provenance` records where it came from
    (source file, sheet, extraction date) so aggregated results stay traceable.
    """

    name: str
    mapping: dict[str, str]
    provenance: str = ""
    target_labels: dict[str, str] = field(default_factory=dict)

    @property
    def targets(self) -> list[str]:
        seen: dict[str, None] = {}
        for t in self.mapping.values():
            seen.setdefault(t)
        return list(seen)

    def validate(self, expected_sources: list[str]) -> list[str]:
        """Return problems as human-readable strings; empty list means valid."""
        problems = []
        missing = [s for s in expected_sources if s not in self.mapping]
        extra = [s for s in self.mapping if s not in set(expected_sources)]
        if missing:
            problems.append(f"{self.name}: unmapped source codes: {', '.join(missing)}")
        if extra:
            problems.append(f"{self.name}: mapping has unknown sources: {', '.join(extra)}")
        return problems

    def aggregate(self, values: dict[str, float]) -> dict[str, float]:
        """Sum source-coded values into target codes. Unmapped keys raise."""
        out: dict[str, float] = {}
        for src, v in values.items():
            tgt = self.mapping[src]
            out[tgt] = out.get(tgt, 0.0) + v
        return out

    def to_csv(self, path: str) -> None:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["source", "target", "target_label"])
            for src, tgt in self.mapping.items():
                w.writerow([src, tgt, self.target_labels.get(tgt, "")])

    @classmethod
    def from_csv(cls, path: str, name: str = "", provenance: str = "") -> "Concordance":
        mapping: dict[str, str] = {}
        labels: dict[str, str] = {}
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                mapping[row["source"]] = row["target"]
                if row.get("target_label"):
                    labels[row["target"]] = row["target_label"]
        return cls(name=name or path, mapping=mapping, provenance=provenance, target_labels=labels)
