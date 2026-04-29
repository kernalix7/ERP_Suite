"""KR 전자세금계산서 어댑터 — 홈택스/바로빌 연동 위임.

기존 ``apps.accounting.integrations.hometax_adapter`` 의 BarobillAdapter /
StubHometaxAdapter / get_hometax_adapter() 를 LocalizationAdapter 인터페이스로
래핑한다. 신규 도메인 코드는 본 어댑터를 통해 호출하여 다국가 분기를 준비.

근거:
- 부가가치세법 제32조 — 전자세금계산서 발급 의무
- 국세청 홈택스 e-세로 표준
"""
from __future__ import annotations

import logging

from apps.localizations.base import ElectronicInvoiceAdapter

logger = logging.getLogger(__name__)


class KRElectronicInvoiceAdapter(ElectronicInvoiceAdapter):
    """대한민국 전자세금계산서 어댑터 — 홈택스/바로빌 위임 래퍼."""

    def is_supported(self) -> bool:
        return True

    def _backend(self):
        # 지연 import — 앱 로드 순서 의존성 제거.
        from apps.accounting.integrations import get_hometax_adapter
        return get_hometax_adapter()

    def submit_tax_invoice(self, invoice) -> dict:
        result = self._backend().submit_tax_invoice(invoice)
        return self._serialize(result)

    def cancel_tax_invoice(self, invoice, reason: str = '') -> dict:
        result = self._backend().cancel_tax_invoice(invoice, reason=reason)
        return self._serialize(result)

    def submit_cash_receipt(self, receipt) -> dict:
        result = self._backend().submit_cash_receipt(receipt)
        return self._serialize(result)

    def cancel_cash_receipt(self, receipt, reason: str = '') -> dict:
        result = self._backend().cancel_cash_receipt(receipt, reason=reason)
        return self._serialize(result)

    @staticmethod
    def _serialize(result) -> dict:
        """HometaxResult dataclass → dict (어댑터 인터페이스 일관성)."""
        return {
            'success': bool(getattr(result, 'success', False)),
            'approval_number': getattr(result, 'approval_number', '') or '',
            'message': getattr(result, 'message', '') or '',
            'raw_response': getattr(result, 'raw_response', None),
        }
