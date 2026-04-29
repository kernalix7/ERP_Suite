"""일본 캘린더 어댑터 (스텁) — 주말만 보정, 공휴일 데이터 미구현."""
from __future__ import annotations

from datetime import date, timedelta

from apps.localizations.base import CalendarAdapter


class JPCalendarAdapter(CalendarAdapter):
    """일본 영업일 어댑터 (스텁 — 주말만 보정)."""

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
