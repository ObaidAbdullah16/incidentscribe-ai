"""Hard spend caps for model calls, stored in DynamoDB.

Two counters (today and this month) in micro-dollars. Before a call, the
worst-case cost is checked against both caps; after the call, the real cost is
added atomically. When a cap would be crossed, the pipeline still answers using
the free deterministic fallback - users get a summary, the bill stays flat.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class BudgetDecision:
    allowed: bool
    spent_today: float
    spent_month: float
    reason: str = ""


class Budget:
    def __init__(self, table: Any, daily_cap_usd: float, monthly_cap_usd: float, now: dt.datetime | None = None):
        self.table = table
        self.daily_cap = daily_cap_usd
        self.monthly_cap = monthly_cap_usd
        self._now = now

    def _keys(self) -> tuple[str, str]:
        now = self._now or dt.datetime.now(dt.UTC)
        return f"day#{now:%Y-%m-%d}", f"month#{now:%Y-%m}"

    def _get(self, key: str) -> float:
        item = self.table.get_item(Key={"pk": key}).get("Item") or {}
        return int(item.get("spend_micro_usd", 0)) / 1e6

    def check(self, estimate_usd: float) -> BudgetDecision:
        day, month = self._keys()
        today, this_month = self._get(day), self._get(month)
        if today + estimate_usd > self.daily_cap:
            return BudgetDecision(False, today, this_month, f"daily AI budget of ${self.daily_cap:.2f} reached")
        if this_month + estimate_usd > self.monthly_cap:
            return BudgetDecision(False, today, this_month, f"monthly AI budget of ${self.monthly_cap:.2f} reached")
        return BudgetDecision(True, today, this_month)

    def record(self, cost_usd: float) -> None:
        micro = Decimal(int(round(cost_usd * 1e6)))
        now = self._now or dt.datetime.now(dt.UTC)
        for key, ttl_days in zip(self._keys(), (40, 400), strict=True):
            self.table.update_item(
                Key={"pk": key},
                UpdateExpression="ADD spend_micro_usd :c, calls :one SET expires_at = :ttl",
                ExpressionAttributeValues={":c": micro, ":one": Decimal(1),
                                           ":ttl": Decimal(int((now + dt.timedelta(days=ttl_days)).timestamp()))},
            )
