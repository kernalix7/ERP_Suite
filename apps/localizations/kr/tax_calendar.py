"""KR 세무 신고기한 어댑터.

근거:
- 부가가치세법 제49조 — 분기 확정신고: 분기 종료 후 25일 이내
- 소득세법 제128조 — 원천징수 납부: 징수일 다음달 10일까지
- 법인세법 제60조 — 법인세 신고: 사업연도 종료일이 속하는 달의 말일부터 3개월 이내
- 국세기본법 제5조 제1항 — 기한이 토·일·공휴일·근로자의날인 경우 다음날로 만료

영업일 보정은 KRCalendarAdapter(다른 팀 담당)가 등록되면 활용. 부재 시
주말 보정만 수행 (graceful degradation).
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from apps.localizations.base import TaxCalendarAdapter


def _next_business_day(target: date) -> date:
    """주말이면 다음 월요일로 연기. 공휴일은 KRCalendarAdapter 등록 시 추가 적용."""
    try:
        from apps.localizations.kr.calendar_kr import KRCalendarAdapter  # noqa
        cal = KRCalendarAdapter()
        cur = target
        while not cal.is_business_day(cur):
            cur = cur + timedelta(days=1)
        return cur
    except Exception:
        # CalendarAdapter 미구현 단계 — 주말만 보정
        cur = target
        while cur.weekday() >= 5:  # 5=Sat, 6=Sun
            cur = cur + timedelta(days=1)
        return cur


class KRTaxCalendarAdapter(TaxCalendarAdapter):
    """대한민국 세무 신고기한 어댑터."""

    def vat_filing_due(self, year: int, quarter: int) -> date:
        """부가세 분기 신고기한 — 분기 종료월 다음달 25일.

        Q1(1~3월) → 4/25, Q2(4~6월) → 7/25, Q3(7~9월) → 10/25, Q4(10~12월) → 익년 1/25.
        """
        if quarter not in (1, 2, 3, 4):
            raise ValueError(f'quarter must be 1~4, got {quarter}')
        end_month = quarter * 3  # 3, 6, 9, 12
        # 종료월 다음달 25일
        if end_month == 12:
            due = date(year + 1, 1, 25)
        else:
            due = date(year, end_month + 1, 25)
        return _next_business_day(due)

    def withholding_filing_due(self, year: int, month: int) -> date:
        """원천세 신고·납부기한 — 지급월 다음달 10일.

        12월 지급분 → 익년 1/10.
        반기 납부특례(상시 20인 이하)는 별도 — 본 메서드는 일반 월별 기준.
        """
        if month not in range(1, 13):
            raise ValueError(f'month must be 1~12, got {month}')
        if month == 12:
            due = date(year + 1, 1, 10)
        else:
            due = date(year, month + 1, 10)
        return _next_business_day(due)

    def corporate_tax_filing_due(self, year: int) -> date:
        """법인세 신고기한 — 사업연도 종료월 말일 + 3개월.

        12월 결산 법인 기준 → 익년 3/31. 사업연도 변형은 별도 인자 추가 시 확장.
        """
        # 12월 결산 가정 — 종료일 = year-12-31, 신고기한 = (year+1)-3-{말일}
        target_year = year + 1
        target_month = 3
        last_day = calendar.monthrange(target_year, target_month)[1]
        due = date(target_year, target_month, last_day)
        return _next_business_day(due)
