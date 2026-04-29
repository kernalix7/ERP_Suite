"""US electronic invoice adapter (stub) — federal e-invoice not mandated."""
from __future__ import annotations

from apps.localizations.base import ElectronicInvoiceAdapter


class USElectronicInvoiceAdapter(ElectronicInvoiceAdapter):
    """US e-invoice adapter (stub)."""

    def is_supported(self) -> bool:
        return False

    def submit_tax_invoice(self, invoice) -> dict:
        raise NotImplementedError('US e-invoice not yet implemented')
