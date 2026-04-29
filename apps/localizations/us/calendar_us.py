"""US calendar adapter (stub) — weekend handling only, federal holidays not seeded."""
from __future__ import annotations

from datetime import date, timedelta

from apps.localizations.base import CalendarAdapter


class USCalendarAdapter(CalendarAdapter):
    """US calendar adapter (stub — weekend only)."""

    def is_holiday(self, target: date) -> bool:
        return False

    def is_business_day(self, target: date) -> bool:
        return target.weekday() < 5

    def add_business_days(self, start: date, days: int) -> date:
        cur = start
        added = 0
        while added < days:
            cur = cur + timedelta(days=1)
            if self.is_business_day(cur):
                added += 1
        return cur
