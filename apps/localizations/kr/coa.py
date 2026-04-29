"""KR 계정과목 어댑터 — K-GAAP 9단계 손익계산서.

근거:
- 일반기업회계기준(K-GAAP) 제2장 — 재무제표 표시
- 9단계 손익계산서: 매출 → 매출원가 → 매출총이익 → 판관비 → 영업이익 →
  영업외수익 → 영업외비용 → 법인세차감전이익 → 당기순이익

기존 AccountCode 모델의 PLBucket(SALES/COGS/SGA/NONOP_REVENUE/NONOP_EXPENSE/
INCOME_TAX)을 9단계로 매핑한다. 손익계산서 빌더(views/reports)가 본 어댑터의
income_statement_steps()를 호출하면 다국가 분기 가능.
"""
from __future__ import annotations

from apps.localizations.base import ChartOfAccountsAdapter


# K-GAAP 9단계 손익계산서 — 표시 순서대로
# (step_no, label, kind, source_buckets)
#   kind = 'sum' (계정 합산) | 'derived' (단계 간 계산)
#   source_buckets = AccountCode.PLBucket 값 리스트 ('sum'일 때만)
KGAAP_INCOME_STATEMENT_STEPS: list[dict] = [
    {'step': 1, 'label': '매출액',           'kind': 'sum',     'buckets': ['SALES']},
    {'step': 2, 'label': '매출원가',         'kind': 'sum',     'buckets': ['COGS']},
    {'step': 3, 'label': '매출총이익',       'kind': 'derived', 'formula': 'step1 - step2'},
    {'step': 4, 'label': '판매비와관리비',   'kind': 'sum',     'buckets': ['SGA']},
    {'step': 5, 'label': '영업이익',         'kind': 'derived', 'formula': 'step3 - step4'},
    {'step': 6, 'label': '영업외수익',       'kind': 'sum',     'buckets': ['NONOP_REVENUE']},
    {'step': 7, 'label': '영업외비용',       'kind': 'sum',     'buckets': ['NONOP_EXPENSE']},
    {'step': 8, 'label': '법인세차감전순이익', 'kind': 'derived', 'formula': 'step5 + step6 - step7'},
    {'step': 9, 'label': '당기순이익',       'kind': 'derived', 'formula': 'step8 - income_tax', 'tax_bucket': 'INCOME_TAX'},
]


class KRChartOfAccountsAdapter(ChartOfAccountsAdapter):
    """대한민국 K-GAAP 계정과목 어댑터."""

    def standard_name(self) -> str:
        return 'K-GAAP'

    def income_statement_format(self) -> str:
        return '9-step'

    def income_statement_steps(self) -> list[dict]:
        """K-GAAP 9단계 손익계산서 구조 — 손익계산서 빌더가 사용."""
        return [dict(s) for s in KGAAP_INCOME_STATEMENT_STEPS]

    def pl_bucket_choices(self) -> list[tuple[str, str]]:
        """AccountCode.PLBucket 와 동기화된 (key, label) 리스트.

        UI/리포트에서 다국가 라벨링이 필요할 때 사용.
        """
        return [
            ('SALES', '매출'),
            ('COGS', '매출원가'),
            ('SGA', '판매비와관리비'),
            ('NONOP_REVENUE', '영업외수익'),
            ('NONOP_EXPENSE', '영업외비용'),
            ('INCOME_TAX', '법인세'),
        ]
