"""홈택스/바로빌 API 어댑터 — 전자세금계산서·현금영수증 제출.

**실제 운영 연결 시 준비사항:**
- 사업자 공동인증서(서명용 공인인증서) PFX/DER 파일
- 바로빌 CorpNum + CertKey + SecretKey (환경변수)
- 홈택스 세무대리인 지정 또는 자사 발행 권한

**현재 상태:** 인터페이스 완성 + Stub 구현. 운영키 주입 시 즉시 동작 가능.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class HometaxResult:
    """국세청 제출 결과 공통 DTO."""
    success: bool
    approval_number: str = ''
    message: str = ''
    raw_response: Optional[dict] = None

    @classmethod
    def ok(cls, approval_number: str, raw=None) -> 'HometaxResult':
        return cls(success=True, approval_number=approval_number, raw_response=raw)

    @classmethod
    def fail(cls, message: str, raw=None) -> 'HometaxResult':
        return cls(success=False, message=message, raw_response=raw)


class HometaxAdapter:
    """추상 베이스 — 구현체가 submit_tax_invoice / submit_cash_receipt 제공."""

    def submit_tax_invoice(self, invoice) -> HometaxResult:
        raise NotImplementedError

    def cancel_tax_invoice(self, invoice, reason: str = '') -> HometaxResult:
        raise NotImplementedError

    def submit_cash_receipt(self, receipt) -> HometaxResult:
        raise NotImplementedError

    def cancel_cash_receipt(self, receipt, reason: str = '') -> HometaxResult:
        raise NotImplementedError


class StubHometaxAdapter(HometaxAdapter):
    """개발/테스트용 — 항상 성공 응답. 실제 전송 안 함."""

    def submit_tax_invoice(self, invoice) -> HometaxResult:
        logger.info('[STUB] submit_tax_invoice %s', getattr(invoice, 'invoice_number', '?'))
        return HometaxResult.ok(
            approval_number=f'STUB-TI-{invoice.pk}',
            raw={'stub': True, 'invoice_number': invoice.invoice_number},
        )

    def cancel_tax_invoice(self, invoice, reason: str = '') -> HometaxResult:
        logger.info('[STUB] cancel_tax_invoice %s', getattr(invoice, 'invoice_number', '?'))
        return HometaxResult.ok(
            approval_number=f'STUB-TI-CANCEL-{invoice.pk}',
            raw={'stub': True, 'reason': reason},
        )

    def submit_cash_receipt(self, receipt) -> HometaxResult:
        logger.info('[STUB] submit_cash_receipt %s', getattr(receipt, 'receipt_number', '?'))
        return HometaxResult.ok(
            approval_number=f'STUB-CR-{receipt.pk}',
            raw={'stub': True, 'receipt_number': receipt.receipt_number},
        )

    def cancel_cash_receipt(self, receipt, reason: str = '') -> HometaxResult:
        logger.info('[STUB] cancel_cash_receipt %s', getattr(receipt, 'receipt_number', '?'))
        return HometaxResult.ok(
            approval_number=f'STUB-CR-CANCEL-{receipt.pk}',
            raw={'stub': True, 'reason': reason},
        )


class BarobillAdapter(HometaxAdapter):
    """운영용 — 바로빌 API 연동.

    **필요한 환경변수:**
    - BAROBILL_CORP_NUM: 사업자등록번호 (10자리)
    - BAROBILL_CERT_KEY: 바로빌 CertKey
    - BAROBILL_SECRET_KEY: 바로빌 SecretKey
    - BAROBILL_API_URL: 기본 'https://ws.baroservice.com'

    환경변수 미설정 시 StubHometaxAdapter 로 fallback (운영 환경에서는 명시 에러).
    """

    def __init__(self):
        self.corp_num = getattr(settings, 'BAROBILL_CORP_NUM', '') or ''
        self.cert_key = getattr(settings, 'BAROBILL_CERT_KEY', '') or ''
        self.secret_key = getattr(settings, 'BAROBILL_SECRET_KEY', '') or ''
        self.api_url = getattr(
            settings, 'BAROBILL_API_URL', 'https://ws.baroservice.com',
        )
        if not (self.corp_num and self.cert_key and self.secret_key):
            logger.warning(
                'BarobillAdapter: 키 미설정 — 모든 호출이 HometaxResult.fail 반환. '
                '환경변수 BAROBILL_CORP_NUM/CERT_KEY/SECRET_KEY 주입 필요.',
            )
            self._configured = False
        else:
            self._configured = True

    def _guard(self) -> Optional[HometaxResult]:
        if not self._configured:
            return HometaxResult.fail(
                'BarobillAdapter 미구성 — 환경변수 누락. '
                '실제 연동 전까지 StubHometaxAdapter 사용.',
            )
        return None

    def submit_tax_invoice(self, invoice) -> HometaxResult:
        guard = self._guard()
        if guard is not None:
            return guard
        # TODO: 실제 바로빌 SOAP/REST 호출 구현.
        # 현재는 인터페이스만 — 운영키 준비 후 구현체 추가.
        return HometaxResult.fail(
            'BarobillAdapter.submit_tax_invoice 미구현 (인터페이스만 완성).',
        )

    def cancel_tax_invoice(self, invoice, reason: str = '') -> HometaxResult:
        guard = self._guard()
        if guard is not None:
            return guard
        return HometaxResult.fail(
            'BarobillAdapter.cancel_tax_invoice 미구현 (인터페이스만 완성).',
        )

    def submit_cash_receipt(self, receipt) -> HometaxResult:
        guard = self._guard()
        if guard is not None:
            return guard
        return HometaxResult.fail(
            'BarobillAdapter.submit_cash_receipt 미구현 (인터페이스만 완성).',
        )

    def cancel_cash_receipt(self, receipt, reason: str = '') -> HometaxResult:
        guard = self._guard()
        if guard is not None:
            return guard
        return HometaxResult.fail(
            'BarobillAdapter.cancel_cash_receipt 미구현 (인터페이스만 완성).',
        )


def get_hometax_adapter() -> HometaxAdapter:
    """환경별 어댑터 선택.

    - settings.HOMETAX_ADAPTER == 'barobill' → BarobillAdapter
    - 그 외(dev/test) → StubHometaxAdapter
    """
    adapter_name = getattr(settings, 'HOMETAX_ADAPTER', 'stub').lower()
    if adapter_name == 'barobill':
        return BarobillAdapter()
    return StubHometaxAdapter()
