"""대한민국 캘린더 어댑터 — 공휴일 판단·영업일 계산."""
from __future__ import annotations

from datetime import date

from apps.localizations.base import CalendarAdapter


class KRCalendarAdapter(CalendarAdapter):
    """Holiday 모델에 위임하여 한국 공휴일·영업일을 계산한다."""

    def is_holiday(self, target: date) -> bool:
        from apps.core.models_holiday import Holiday
        return Holiday.is_holiday(target)

    def is_business_day(self, target: date) -> bool:
        from apps.core.models_holiday import Holiday
        return Holiday.is_business_day(target)

    def add_business_days(self, start: date, days: int) -> date:
        from apps.core.models_holiday import Holiday
        return Holiday.add_business_days(start, days)
