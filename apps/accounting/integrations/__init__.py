"""외부 재무 API 통합 어댑터 모듈 (홈택스/바로빌 등).

현재 구조:
- hometax_adapter.py — 전자세금계산서·현금영수증 국세청 연동 어댑터
  - `HometaxAdapter` (추상 베이스)
  - `StubHometaxAdapter` (개발/테스트용 — 항상 성공 응답)
  - `BarobillAdapter` (운영용 — 바로빌 API 연동, 실제 API 키 주입 필요)

사용법:
    from apps.accounting.integrations import get_hometax_adapter
    adapter = get_hometax_adapter()
    result = adapter.submit_tax_invoice(invoice)
"""
from .hometax_adapter import (
    HometaxAdapter,
    StubHometaxAdapter,
    BarobillAdapter,
    HometaxResult,
    get_hometax_adapter,
)

__all__ = [
    'HometaxAdapter', 'StubHometaxAdapter', 'BarobillAdapter',
    'HometaxResult', 'get_hometax_adapter',
]
