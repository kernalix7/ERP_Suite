"""KR 세제 어댑터 — VAT(부가가치세) + 원천세율 + 외환손익 PostingProfile.

근거:
- 부가가치세법 제30조 — 일반세율 10%
- 소득세법 시행령 제184조·제202조의5 — 원천징수 세율
- 법인세법 제73조 — 내국법인 원천징수
- 영세율(0%) / 면세 거래는 vat_rate()와 별개로 거래 단위에서 분기 처리

원천세율은 지방소득세(소득세의 10%) 자동 가산을 포함한 합산 세율 기준.

외환손익 계정코드:
- 기본값(K-GAAP): 외환차익 470, 외환차손 925
- 사용자가 SystemConfig('TAX', 'fx_gain_account_code'/'fx_loss_account_code')로
  오버라이드 가능 — 어댑터 메서드는 SystemConfig 우선, 미설정 시 default 반환.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from apps.localizations.base import TaxAdapter

logger = logging.getLogger(__name__)


# 외환손익 계정코드 default — K-GAAP 일반 코드체계 기준
KR_FX_GAIN_DEFAULT_CODE = '470'   # 외환차익 (영업외수익)
KR_FX_LOSS_DEFAULT_CODE = '925'   # 외환차손 (영업외비용)


# 원천세 합산 세율 — (소득세/법인세) + (지방소득세 = 본세 × 10%)
# Key 는 WithholdingTax/HR 도메인에서 공통 사용하기 위한 안정 식별자.
KR_WITHHOLDING_RATES: dict[str, Decimal] = {
    'BUSINESS_INCOME': Decimal('0.033'),      # 사업소득(프리랜서) 3% + 0.3% = 3.3%
    'OTHER_INCOME': Decimal('0.088'),         # 기타소득(필요경비 60% 공제 후) 8% + 0.8% = 8.8% (실효 4.4%까지 산출)
    'INTEREST_INCOME': Decimal('0.154'),      # 이자소득 14% + 1.4% = 15.4%
    'DIVIDEND_INCOME': Decimal('0.154'),      # 배당소득 14% + 1.4% = 15.4%
    'DAILY_WAGE': Decimal('0.060'),           # 일용근로소득 6% (지방세 포함)
    'CORPORATE_INTEREST': Decimal('0.154'),   # 법인 이자/배당 14% + 1.4%
    'NON_RESIDENT': Decimal('0.220'),         # 비거주자 일반 20% + 2% = 22% (조세조약 별도)
    'RETIREMENT_INCOME': Decimal('0.000'),    # 퇴직소득 — 별도 정산(원천 0% 명목, 정산세 별도)
}


# 외환손익 자동 전표 PostingProfile — 환차익/환차손 계정 매핑 시 어댑터 호출.
# 실 계정코드는 AccountCode 마스터에 KR 시드로 등록되며, 어댑터는 계정 분류 키만 노출.
KR_FX_POSTING_PROFILE = {
    'fx_gain_account_key': 'FX_GAIN',         # 외환차익 (영업외수익 — 9-step 손익계산서 8단계)
    'fx_loss_account_key': 'FX_LOSS',         # 외환차손 (영업외비용 — 9-step 손익계산서 9단계)
    'fx_gain_unrealized_key': 'FX_GAIN_UNREALIZED',   # 외화환산이익 (결산시점 평가)
    'fx_loss_unrealized_key': 'FX_LOSS_UNREALIZED',   # 외화환산손실
}


class KRTaxAdapter(TaxAdapter):
    """대한민국 세제 어댑터."""

    def vat_rate(self) -> Decimal:
        return Decimal('0.10')

    def withholding_rates(self) -> dict[str, Decimal]:
        return dict(KR_WITHHOLDING_RATES)

    def withholding_rate(self, tax_key: str) -> Decimal:
        """세목 키로 단일 세율 조회. 미등록 키는 0.0 반환."""
        return KR_WITHHOLDING_RATES.get(tax_key, Decimal('0'))

    def fx_posting_profile(self) -> dict[str, str]:
        """외환손익 자동 전표용 PostingProfile (계정 분류 키 매핑)."""
        return dict(KR_FX_POSTING_PROFILE)

    def fx_gain_code(self) -> str:
        """외환차익 계정코드 — SystemConfig('TAX','fx_gain_account_code') 우선,
        미설정 시 K-GAAP 기본 '470' 반환.

        SystemConfig 조회 실패(앱 미로드/마이그레이션 미적용 등)시에도 graceful
        하게 default 반환하여 시그널이 죽지 않도록 한다.
        """
        try:
            from apps.core.models import SystemConfig
            v = SystemConfig.get_value('TAX', 'fx_gain_account_code', '')
            if v:
                return str(v)
        except Exception:
            logger.debug('SystemConfig fx_gain_account_code 조회 실패 — default 사용')
        return KR_FX_GAIN_DEFAULT_CODE

    def fx_loss_code(self) -> str:
        """외환차손 계정코드 — SystemConfig 우선, 미설정 시 K-GAAP 기본 '925' 반환."""
        try:
            from apps.core.models import SystemConfig
            v = SystemConfig.get_value('TAX', 'fx_loss_account_code', '')
            if v:
                return str(v)
        except Exception:
            logger.debug('SystemConfig fx_loss_account_code 조회 실패 — default 사용')
        return KR_FX_LOSS_DEFAULT_CODE
