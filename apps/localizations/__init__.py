"""국가별 로컬라이제이션 패키지 — Country Pack.

ERP의 한국 종속 로직(K-GAAP·국세청·홈택스·한국 공휴일 등)을 추상화하여
미래 다국가 진출 시 새 국가 어댑터만 구현하면 자동 분기되도록 한다.

구조:
- base.py — LocalizationAdapter 추상 베이스 (모든 국가가 구현해야 할 인터페이스)
- registry.py — country code(ISO-3166 alpha-2) → adapter instance 매핑
- kr/ — 한국 (KR) 구현 (현재 prod 기본)
- us/, jp/ 등 — 미래 추가

사용 예시:
    from apps.localizations import get_adapter
    kr = get_adapter('KR')
    vat_rate = kr.tax.vat_rate()        # 0.10
    is_holiday = kr.calendar.is_holiday(date(2026, 1, 1))  # True
    valid = kr.identifier.validate_business_number('123-45-67890')

활성 국가 설정:
    SystemConfig.set_value('GENERAL', 'active_country', 'KR') 또는
    settings.ACTIVE_COUNTRY = 'KR' (default)
"""
from decimal import Decimal

from .registry import (
    get_adapter,
    get_active_adapter,
    get_registered_codes,
    register_adapter,
)


def get_vat_rate() -> Decimal:
    """현재 활성 국가의 기본 부가세율. 어댑터 미로드 시 KR 기본값(0.10) 반환.

    OrderItem.save() / QuotationItem.save() / POItem.save() 등 세이브 훅에서
    다국가 분기를 위해 본 헬퍼를 호출. 어댑터 import 실패해도 시스템이 계속
    동작하도록 graceful fallback.
    """
    try:
        return get_active_adapter().tax.vat_rate()
    except Exception:
        return Decimal('0.10')


def get_vat_multiplier() -> Decimal:
    """공급가액 → 합계금액 환산 배수 (1 + vat_rate). VAT-inclusive 역산용."""
    return Decimal('1') + get_vat_rate()


__all__ = [
    'get_adapter',
    'get_active_adapter',
    'get_registered_codes',
    'register_adapter',
    'get_vat_rate',
    'get_vat_multiplier',
]
