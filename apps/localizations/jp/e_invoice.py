"""JP 전자세금계산서 어댑터 (스텁) — 適格請求書 / Peppol 향후 구현."""
from __future__ import annotations

from apps.localizations.base import ElectronicInvoiceAdapter


class JPElectronicInvoiceAdapter(ElectronicInvoiceAdapter):
    """일본 전자청구서 어댑터 (스텁)."""

    def is_supported(self) -> bool:
        return False

    def submit_tax_invoice(self, invoice) -> dict:
        raise NotImplementedError('JP e-invoice not yet implemented')
