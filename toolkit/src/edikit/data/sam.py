"""Reader for labeled square SAM matrices in Excel sheets.

Layout convention (as used in the UNU-WIDER South Africa SAM workbooks):
one header row of column account labels, one label column of row account
labels, numeric cells in between, and an optional trailing totals row/column
labeled "total".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import openpyxl

_TOTALS_LABEL = re.compile(r"^(col|row)?\s*tot(al)?s?$", re.IGNORECASE)


def is_totals_label(label: str) -> bool:
    return bool(_TOTALS_LABEL.match(label.strip()))


@dataclass
class LabeledMatrix:
    row_accounts: list[str]
    col_accounts: list[str]
    # cells[(row_account, col_account)] -> value; zeros omitted
    cells: dict[tuple[str, str], float] = field(default_factory=dict)
    embedded_col_totals: dict[str, float] = field(default_factory=dict)
    embedded_row_totals: dict[str, float] = field(default_factory=dict)

    def col_sums(self) -> dict[str, float]:
        out = {c: 0.0 for c in self.col_accounts}
        for (_, c), v in self.cells.items():
            out[c] += v
        return out

    def row_sums(self) -> dict[str, float]:
        out = {r: 0.0 for r in self.row_accounts}
        for (r, _), v in self.cells.items():
            out[r] += v
        return out

    def accounts_with_prefix(self, prefix: str) -> list[str]:
        return [c for c in self.col_accounts if c.startswith(prefix)]


def read_labeled_matrix(path: str, sheet_name: str) -> LabeledMatrix:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    rows = list(wb[sheet_name].iter_rows(values_only=True))

    # find the header row: the first row with >= 3 non-empty string labels
    header_idx = None
    for i, r in enumerate(rows):
        labels = [c for c in r[1:] if isinstance(c, str) and c.strip()]
        if len(labels) >= 3:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"{sheet_name}: no header row of column labels found")

    header = rows[header_idx]
    col_map: dict[int, str] = {}
    for j, h in enumerate(header):
        if j == 0:
            continue
        lab = str(h or "").strip()
        if lab:
            col_map[j] = lab

    m = LabeledMatrix(row_accounts=[], col_accounts=list(col_map.values()))
    for r in rows[header_idx + 1 :]:
        lab = str(r[0] or "").strip()
        if not lab:
            continue
        if is_totals_label(lab):
            for j, c in col_map.items():
                v = r[j]
                if isinstance(v, (int, float)):
                    m.embedded_col_totals[c] = float(v)
            continue
        m.row_accounts.append(lab)
        for j, c in col_map.items():
            if is_totals_label(c):
                v = r[j]
                if isinstance(v, (int, float)):
                    m.embedded_row_totals[lab] = float(v)
                continue
            v = r[j]
            if isinstance(v, (int, float)) and v != 0:
                m.cells[(lab, c)] = float(v)

    m.col_accounts = [c for c in m.col_accounts if not is_totals_label(c)]
    return m
