"""
국세청 홈택스 전자세금계산서 API 클라이언트

홈택스 전자세금계산서 API 규격에 따라 발행/조회/취소를 처리합니다.
SystemConfig에서 인증정보를 로드하며, XML(SOAP) 형식으로 통신합니다.
"""
import logging
import uuid
from datetime import datetime
from xml.etree import ElementTree as ET

import requests
from defusedxml import ElementTree as SafeET
from django.utils import timezone

from apps.core.api_utils import create_retry_session, circuit_breakers

logger = logging.getLogger(__name__)

# 홈택스 API 서버
NTS_ENDPOINTS = {
    'test': 'https://demoapi.hometax.go.kr',
    'production': 'https://api.hometax.go.kr',
}


class NTSAPIError(Exception):
    """국세청 API 호출 에러"""

    def __init__(self, message, code=None, response_data=None):
        self.code = code
        self.response_data = response_data or {}
        super().__init__(message)


class NTSClient:
    """
    국세청 홈택스 전자세금계산서 API 클라이언트

    SystemConfig에서 인증정보를 로드하여 사용합니다.
    - NTS / business_number: 사업자등록번호
    - NTS / cert_path: 공인인증서 경로
    - NTS / api_key: API 키
    - NTS / api_secret: API 시크릿
    - NTS / environment: test / production
    """

    SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
    NTS_NS = 'urn:kr:or:kec:standard:Tax:ReusableAggregateBusinessInformationEntitySchemaModule:1:0'

    def __init__(self):
        self._config = {}
        self._access_token = None
        self._token_expires_at = 0
        self._session = create_retry_session(timeout=30)
        self._cb = circuit_breakers['nts']

    def _load_config(self):
        """SystemConfig에서 NTS 설정 로드"""
        from apps.core.system_config import SystemConfig

        keys = ['business_number', 'cert_path', 'api_key', 'api_secret', 'environment']
        for key in keys:
            self._config[key] = SystemConfig.get_value('NTS', key)

        if not self._config.get('api_key'):
            raise NTSAPIError('국세청 API 키가 설정되지 않았습니다.')

        if not self._config.get('business_number'):
            raise NTSAPIError('사업자등록번호가 설정되지 않았습니다.')

    @property
    def base_url(self):
        env = self._config.get('environment', 'test')
        return NTS_ENDPOINTS.get(env, NTS_ENDPOINTS['test'])

    def _authenticate(self):
        """API 인증 토큰 발급"""
        import time

        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        if not self._cb.is_available:
            raise NTSAPIError('국세청 API 일시 차단 (서킷브레이커 OPEN)')

        url = f'{self.base_url}/auth/token'
        data = {
            'api_key': self._config['api_key'],
            'api_secret': self._config['api_secret'],
            'cert_path': self._config.get('cert_path', ''),
        }

        try:
            resp = self._session.post(url, json=data, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            self._access_token = result.get('access_token', '')
            self._token_expires_at = time.time() + result.get('expires_in', 3600) - 60
            self._cb.record_success()
            logger.info('국세청 API 인증 성공')
            return self._access_token
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('국세청 API 인증 실패: %s', e)
            raise NTSAPIError(f'인증 실패: {e}')

    def _headers(self):
        return {
            'Authorization': f'Bearer {self._authenticate()}',
            'Content-Type': 'application/xml; charset=utf-8',
        }

    def _build_xml(self, tax_invoice):
        """TaxInvoice를 표준전자세금계산서 XML로 변환"""
        envelope = ET.Element('Envelope', xmlns=self.SOAP_NS)
        body = ET.SubElement(envelope, 'Body')
        tax_invoice_doc = ET.SubElement(body, 'TaxInvoice', xmlns=self.NTS_NS)

        # 교환 정보
        exchange_doc = ET.SubElement(tax_invoice_doc, 'ExchangedDocument')
        ET.SubElement(exchange_doc, 'ID').text = tax_invoice.issue_id or str(uuid.uuid4())
        ET.SubElement(exchange_doc, 'IssueDateTime').text = (
            tax_invoice.issue_date.strftime('%Y%m%d')
        )

        # 공급자 정보
        invoicer = ET.SubElement(tax_invoice_doc, 'InvoicerParty')
        ET.SubElement(invoicer, 'ID').text = self._config.get('business_number', '')

        # 공급받는자 정보
        invoicee = ET.SubElement(tax_invoice_doc, 'InvoiceeParty')
        if tax_invoice.partner:
            ET.SubElement(invoicee, 'ID').text = getattr(
                tax_invoice.partner, 'business_number', ''
            ) or ''
            ET.SubElement(invoicee, 'Name').text = str(tax_invoice.partner)

        # 금액 정보
        amount_doc = ET.SubElement(tax_invoice_doc, 'SpecifiedMonetarySummation')
        ET.SubElement(amount_doc, 'ChargeTotalAmount').text = str(tax_invoice.supply_amount)
        ET.SubElement(amount_doc, 'TaxTotalAmount').text = str(tax_invoice.tax_amount)
        ET.SubElement(amount_doc, 'GrandTotalAmount').text = str(tax_invoice.total_amount)

        return ET.tostring(envelope, encoding='unicode', xml_declaration=True)

    def issue(self, tax_invoice):
        """
        전자세금계산서 발행

        Args:
            tax_invoice: TaxInvoice 모델 인스턴스

        Returns:
            dict: {'issue_id': str, 'confirmation_number': str, 'status': str}

        Raises:
            NTSAPIError: API 호출 실패 시
        """
        self._load_config()

        if not tax_invoice.issue_id:
            tax_invoice.issue_id = str(uuid.uuid4())

        if not self._cb.is_available:
            raise NTSAPIError('국세청 API 일시 차단 (서킷브레이커 OPEN)')

        xml_data = self._build_xml(tax_invoice)
        url = f'{self.base_url}/etax/v1/invoice/issue'

        try:
            resp = self._session.post(
                url, headers=self._headers(), data=xml_data, timeout=60,
            )
            resp.raise_for_status()
            self._cb.record_success()

            result = self._parse_response(resp.text)
            logger.info(
                '전자세금계산서 발행 성공: %s (승인번호: %s)',
                tax_invoice.invoice_number, result.get('confirmation_number', ''),
            )
            return {
                'issue_id': tax_invoice.issue_id,
                'confirmation_number': result.get('confirmation_number', ''),
                'status': 'ISSUED',
                'raw_response': result,
            }
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('전자세금계산서 발행 실패: %s — %s', tax_invoice.invoice_number, e)
            raise NTSAPIError(
                f'발행 실패: {e}',
                response_data={'invoice_number': tax_invoice.invoice_number},
            )

    def query(self, tax_invoice):
        """
        전자세금계산서 상태 조회

        Args:
            tax_invoice: TaxInvoice 모델 인스턴스 (issue_id 필수)

        Returns:
            dict: {'status': str, 'confirmation_number': str, ...}

        Raises:
            NTSAPIError: API 호출 실패 시
        """
        self._load_config()

        if not tax_invoice.issue_id:
            raise NTSAPIError('발행ID가 없어 상태 조회가 불가합니다.')

        if not self._cb.is_available:
            raise NTSAPIError('국세청 API 일시 차단 (서킷브레이커 OPEN)')

        url = f'{self.base_url}/etax/v1/invoice/status'
        params = {
            'issueId': tax_invoice.issue_id,
            'businessNumber': self._config['business_number'],
        }

        try:
            resp = self._session.get(
                url, headers=self._headers(), params=params, timeout=30,
            )
            resp.raise_for_status()
            self._cb.record_success()

            result = self._parse_response(resp.text)
            logger.info(
                '전자세금계산서 상태 조회: %s → %s',
                tax_invoice.invoice_number, result.get('status', 'UNKNOWN'),
            )
            return result
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('전자세금계산서 상태 조회 실패: %s — %s', tax_invoice.invoice_number, e)
            raise NTSAPIError(f'상태 조회 실패: {e}')

    def cancel(self, tax_invoice, reason=''):
        """
        전자세금계산서 취소 (수정세금계산서 발행)

        Args:
            tax_invoice: TaxInvoice 모델 인스턴스
            reason: 취소 사유

        Returns:
            dict: {'status': str, 'cancel_id': str, ...}

        Raises:
            NTSAPIError: API 호출 실패 시
        """
        self._load_config()

        if not tax_invoice.issue_id:
            raise NTSAPIError('발행ID가 없어 취소가 불가합니다.')

        if tax_invoice.electronic_status not in ('ISSUED', 'SENT', 'ACCEPTED'):
            raise NTSAPIError(
                f'현재 상태({tax_invoice.get_electronic_status_display()})에서는 취소할 수 없습니다.',
            )

        if not self._cb.is_available:
            raise NTSAPIError('국세청 API 일시 차단 (서킷브레이커 OPEN)')

        url = f'{self.base_url}/etax/v1/invoice/cancel'
        data = {
            'issueId': tax_invoice.issue_id,
            'businessNumber': self._config['business_number'],
            'cancelReason': reason,
        }

        try:
            resp = self._session.post(
                url, headers=self._headers(), json=data, timeout=60,
            )
            resp.raise_for_status()
            self._cb.record_success()

            result = self._parse_response(resp.text)
            logger.info(
                '전자세금계산서 취소 성공: %s (사유: %s)',
                tax_invoice.invoice_number, reason,
            )
            return {
                'status': 'CANCELLED',
                'cancel_id': result.get('cancel_id', ''),
                'raw_response': result,
            }
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('전자세금계산서 취소 실패: %s — %s', tax_invoice.invoice_number, e)
            raise NTSAPIError(f'취소 실패: {e}')

    def check_status(self, issue_id):
        """
        발행ID로 상태 직접 조회 (TaxInvoice 객체 없이)

        Args:
            issue_id: 전자세금계산서 발행 고유ID

        Returns:
            dict: 상태 정보
        """
        self._load_config()

        if not self._cb.is_available:
            raise NTSAPIError('국세청 API 일시 차단 (서킷브레이커 OPEN)')

        url = f'{self.base_url}/etax/v1/invoice/status'
        params = {
            'issueId': issue_id,
            'businessNumber': self._config['business_number'],
        }

        try:
            resp = self._session.get(
                url, headers=self._headers(), params=params, timeout=30,
            )
            resp.raise_for_status()
            self._cb.record_success()
            return self._parse_response(resp.text)
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('전자세금계산서 상태 조회 실패: %s — %s', issue_id, e)
            raise NTSAPIError(f'상태 조회 실패: {e}')

    def _parse_response(self, response_text):
        """XML 응답 파싱 (defusedxml 사용 — XXE 방지)"""
        try:
            root = SafeET.fromstring(response_text)
            result = {}
            # SOAP Body 내 응답 파싱
            body = root.find(f'{{{self.SOAP_NS}}}Body')
            if body is None:
                # JSON 응답 fallback
                import json
                try:
                    return json.loads(response_text)
                except (json.JSONDecodeError, ValueError):
                    return {'raw': response_text}

            for elem in body.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if elem.text and elem.text.strip():
                    result[tag] = elem.text.strip()

            # 상태 매핑
            status_code = result.get('ResultCode', '')
            status_map = {
                '00': 'ACCEPTED',
                '01': 'SENT',
                '10': 'ISSUED',
                '20': 'REJECTED',
                '30': 'CANCELLED',
            }
            result['status'] = status_map.get(status_code, result.get('status', 'UNKNOWN'))
            result['confirmation_number'] = result.get('NTSConfirmNumber', '')

            return result
        except ET.ParseError:
            logger.warning('국세청 응답 XML 파싱 실패, 원문 반환')
            return {'raw': response_text}
