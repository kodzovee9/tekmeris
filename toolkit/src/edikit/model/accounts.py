"""Canonical SAM account taxonomy.

Every SAM the toolkit touches is described in these terms, whatever the source
workbook calls its accounts. Kind assignment always comes from an explicit,
reviewable mapping (e.g. prefix rules declared in paper config), never from
guessing inside library code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AccountKind(str, Enum):
    ACTIVITY = "activity"
    COMMODITY = "commodity"
    FACTOR = "factor"
    ENTERPRISE = "enterprise"
    HOUSEHOLD = "household"
    GOVERNMENT = "government"
    TAX = "tax"
    MARGIN = "margin"
    SAVINGS_INVESTMENT = "savings_investment"
    REST_OF_WORLD = "rest_of_world"
    OTHER = "other"


@dataclass(frozen=True)
class Account:
    code: str
    kind: AccountKind
    description: str = ""
    source: str = ""  # where this account definition came from


@dataclass
class AccountSet:
    accounts: list[Account]

    def by_kind(self, kind: AccountKind) -> list[Account]:
        return [a for a in self.accounts if a.kind == kind]

    def codes(self, kind: AccountKind | None = None) -> list[str]:
        return [a.code for a in self.accounts if kind is None or a.kind == kind]


def classify_by_prefix(
    codes: list[str], prefix_rules: dict[str, AccountKind], source: str = ""
) -> AccountSet:
    """Assign kinds from an explicit prefix->kind table (longest prefix wins).

    Raises on any unmatched code: unclassified accounts must be resolved by a
    human adding a rule, not silently bucketed.
    """
    accounts = []
    ordered = sorted(prefix_rules, key=len, reverse=True)
    for code in codes:
        for p in ordered:
            if code.startswith(p):
                accounts.append(Account(code=code, kind=prefix_rules[p], source=source))
                break
        else:
            raise ValueError(f"no prefix rule matches account code {code!r}")
    return AccountSet(accounts)
