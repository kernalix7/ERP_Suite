"""
마켓플레이스 API 클라이언트 (네이버 커머스 / 쿠팡)

각 마켓플레이스의 주문 조회 API를 호출하여 MarketplaceOrder로 동기화합니다.
실제 API 연동 시 각 플랫폼의 인증 방식에 맞게 토큰을 발급받아야 합니다.
"""
import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import bcrypt

import requests
from django.conf import settings
from django.utils import timezone

from apps.core.api_utils import create_retry_session, circuit_breakers

logger = logging.getLogger(__name__)


class NaverCommerceClient:
    """
    네이버 커머스 API 클라이언트
    API 문서: https://apicenter.commerce.naver.com/ko/basic/commerce-api
    """
    BASE_URL = 'https://api.commerce.naver.com/external'
    TOKEN_URL = 'https://api.commerce.naver.com/external/v1/oauth2/token'

    # 네이버 커머스API 택배사 코드 매핑
    DELIVERY_COMPANY_CODES = {
        'CJ대한통운': 'CJGLS',
        'CJ': 'CJGLS',
        '한진택배': 'HANJIN',
        '한진': 'HANJIN',
        '롯데택배': 'LOTTE',
        '롯데': 'LOTTE',
        '로젠택배': 'LOGEN',
        '로젠': 'LOGEN',
        '우체국택배': 'EPOST',
        '우체국': 'EPOST',
        '경동택배': 'KDEXP',
        '경동': 'KDEXP',
        '대신택배': 'DAESIN',
        '대신': 'DAESIN',
        '일양로지스': 'ILYANG',
        '일양': 'ILYANG',
        'GS Postbox': 'GSPOSTBOX',
        '합동택배': 'HDEXP',
        '합동': 'HDEXP',
        '건영택배': 'KUNYOUNG',
        '건영': 'KUNYOUNG',
        '천일택배': 'CHUNIL',
        '천일': 'CHUNIL',
        '한의사방택배': 'HANIPS',
        'SLX': 'SLX',
        'EMS': 'EMS',
        'DHL': 'DHL',
        'FedEx': 'FEDEX',
        'UPS': 'UPS',
        'TNT': 'TNT',
    }

    # 역방향 매핑 (코드 → 택배사명)
    DELIVERY_CODE_TO_NAME = {v: k for k, v in DELIVERY_COMPANY_CODES.items()}

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self._access_token = None
        self._token_expires_at = 0
        self._session = create_retry_session(timeout=30)
        self._cb = circuit_breakers['naver']

    def _get_access_token(self) -> str:
        """OAuth 토큰 발급 (BCrypt 서명 방식, 최대 3회 재시도)"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        if not self._cb.is_available:
            raise requests.RequestException('네이버 API 일시 차단 (서킷브레이커 OPEN)')

        timestamp = int(time.time() * 1000)
        password = f'{self.client_id}_{timestamp}'
        hashed = bcrypt.hashpw(
            password.encode('utf-8'),
            self.client_secret.encode('utf-8'),
        )
        sign = base64.b64encode(hashed).decode('utf-8')

        data = {
            'client_id': self.client_id,
            'timestamp': timestamp,
            'client_secret_sign': sign,
            'grant_type': 'client_credentials',
            'type': 'SELF',
        }

        last_error = None
        for attempt in range(3):
            try:
                resp = self._session.post(self.TOKEN_URL, data=data, timeout=10)
                if resp.status_code != 200:
                    logger.error(
                        '네이버 토큰 발급 실패 상세 (시도 %d/3) — status=%s, body=%s',
                        attempt + 1, resp.status_code, resp.text[:500],
                    )
                resp.raise_for_status()
                result = resp.json()
                self._access_token = result['access_token']
                self._token_expires_at = time.time() + result.get('expires_in', 3600) - 60
                self._cb.record_success()
                return self._access_token
            except requests.RequestException as e:
                last_error = e
                logger.warning('네이버 토큰 발급 실패 (시도 %d/3): %s', attempt + 1, e)
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))

        self._cb.record_failure()
        logger.error('네이버 토큰 발급 최종 실패 (3회 재시도 후): %s', last_error)
        raise last_error

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._get_access_token()}',
            'Content-Type': 'application/json',
        }

    def get_orders(self, from_date: datetime = None, to_date: datetime = None) -> list:
        """
        주문 목록 조회 — 네이버 API는 최대 1일 단위만 허용하므로
        기간이 길면 하루씩 나눠서 조회합니다.

        Returns:
            list[dict]: 주문 데이터 리스트
        """
        if not from_date:
            from_date = datetime.now() - timedelta(days=7)
        if not to_date:
            to_date = datetime.now()

        # 마이크로초 제거 — chunk 분할 시 잔여분 방지
        from_date = from_date.replace(microsecond=0)
        to_date = to_date.replace(microsecond=0)

        # 1일 단위로 분할 조회
        all_product_order_ids = []
        chunk_start = from_date
        while chunk_start < to_date:
            chunk_end = min(chunk_start + timedelta(days=1), to_date)
            ids = self._fetch_changed_order_ids(chunk_start, chunk_end)
            all_product_order_ids.extend(ids)
            chunk_start = chunk_end

        if not all_product_order_ids:
            return []

        return self._get_order_details(all_product_order_ids)

    def _fetch_changed_order_ids(self, from_date: datetime, to_date: datetime) -> list:
        """1일 이내 기간의 변경된 주문 ID 조회 (lastChangedStatuses)"""
        url = f'{self.BASE_URL}/v1/pay-order/seller/product-orders/last-changed-statuses'
        params = {
            'lastChangedFrom': from_date.strftime('%Y-%m-%dT%H:%M:%S.000+09:00'),
            'lastChangedTo': to_date.strftime('%Y-%m-%dT%H:%M:%S.000+09:00'),
        }

        if not self._cb.is_available:
            raise requests.RequestException('네이버 API 일시 차단 (서킷브레이커 OPEN)')

        try:
            resp = self._session.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            self._cb.record_success()
            data = resp.json().get('data', {})
            statuses = data.get('lastChangeStatuses', [])
            return [s.get('productOrderId') for s in statuses if s.get('productOrderId')]
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('네이버 주문 ID 조회 실패 (%s ~ %s): %s', from_date, to_date, e)
            return []

    def _get_order_details(self, product_order_ids: list) -> list:
        """주문 상세 조회"""
        url = f'{self.BASE_URL}/v1/pay-order/seller/product-orders/query'
        try:
            resp = self._session.post(
                url,
                headers=self._headers(),
                json={'productOrderIds': product_order_ids},
                timeout=30,
            )
            resp.raise_for_status()
            self._cb.record_success()
            return resp.json().get('data', [])
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('네이버 주문 상세 조회 실패: %s', e)
            return []

    def normalize_order(self, raw_order: dict) -> dict:
        """네이버 API 응답을 MarketplaceOrder 필드에 매핑"""
        order_info = raw_order.get('order', {})
        product_order = raw_order.get('productOrder', {})
        delivery = raw_order.get('delivery', {})

        status_map = {
            'PAYMENT_WAITING': 'NEW',
            'PAYED': 'NEW',
            'DELIVERING': 'SHIPPED',
            'DELIVERED': 'DELIVERED',
            'PURCHASE_DECIDED': 'DELIVERED',
            'EXCHANGED': 'RETURNED',
            'CANCELED': 'CANCELLED',
            'RETURNED': 'RETURNED',
            'CANCELED_BY_NOPAYMENT': 'CANCELLED',
        }

        return {
            'store_order_id': product_order.get('productOrderId', ''),
            'platform_order_id': order_info.get('orderId', ''),
            'platform_product_order_id': product_order.get('productOrderId', ''),
            'product_name': product_order.get('productName', ''),
            'option_name': product_order.get('optionContent', ''),
            'quantity': product_order.get('quantity', 1),
            'price': product_order.get('totalPaymentAmount', 0),
            'buyer_name': order_info.get('ordererName', ''),
            'buyer_phone': order_info.get('ordererTel', ''),
            'receiver_name': delivery.get('name', ''),
            'receiver_phone': delivery.get('tel1', ''),
            'receiver_address': (delivery.get('baseAddress', '') + '\n' + delivery.get('detailedAddress', '')).strip(),
            'status': status_map.get(product_order.get('productOrderStatus'), 'NEW'),
            'ordered_at': product_order.get('orderDate', ''),
            'delivery_company': self.DELIVERY_CODE_TO_NAME.get(
                delivery.get('deliveryCompanyCode', ''), '',
            ),
            'tracking_number': delivery.get('trackingNumber', ''),
        }

    def dispatch_shipment(self, product_order_ids: list[str]) -> dict:
        """발주확인 처리 (발송 전 필수 단계)

        Args:
            product_order_ids: 발주확인할 상품주문번호 리스트

        Returns:
            dict: API 응답 결과
        """
        url = f'{self.BASE_URL}/v1/pay-order/seller/product-orders/confirm'

        if not self._cb.is_available:
            raise requests.RequestException('네이버 API 일시 차단 (서킷브레이커 OPEN)')

        try:
            resp = self._session.post(
                url,
                headers=self._headers(),
                json={'productOrderIds': product_order_ids},
                timeout=30,
            )
            resp.raise_for_status()
            self._cb.record_success()
            result = resp.json()
            logger.info('네이버 발주확인 완료: %s', product_order_ids)
            return result
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('네이버 발주확인 실패: %s', e)
            raise

    def ship_order(self, product_order_id: str,
                   delivery_company: str, tracking_number: str) -> dict:
        """배송정보 등록 (발주확인 후 호출)

        Args:
            product_order_id: 상품주문번호
            delivery_company: 택배사명 (한글 또는 코드)
            tracking_number: 운송장번호

        Returns:
            dict: API 응답 결과
        """
        url = (
            f'{self.BASE_URL}/v1/pay-order/seller/product-orders'
            f'/{product_order_id}/ship'
        )

        # 택배사명 → 네이버 코드 변환
        company_code = self.DELIVERY_COMPANY_CODES.get(
            delivery_company, delivery_company,
        )

        if not self._cb.is_available:
            raise requests.RequestException('네이버 API 일시 차단 (서킷브레이커 OPEN)')

        try:
            resp = self._session.post(
                url,
                headers=self._headers(),
                json={
                    'deliveryMethod': 'DELIVERY',
                    'deliveryCompanyCode': company_code,
                    'trackingNumber': tracking_number,
                },
                timeout=30,
            )
            resp.raise_for_status()
            self._cb.record_success()
            result = resp.json()
            logger.info(
                '네이버 배송정보 등록 완료: %s (택배사: %s, 운송장: %s)',
                product_order_id, company_code, tracking_number,
            )
            return result
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error(
                '네이버 배송정보 등록 실패 (%s): %s', product_order_id, e,
            )
            raise


class CoupangClient:
    """
    쿠팡 Wing API 클라이언트
    API 문서: https://developers.coupangcorp.com/
    """
    BASE_URL = 'https://api-gateway.coupang.com'

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._session = create_retry_session(timeout=30)
        self._cb = circuit_breakers['coupang']

    def _generate_signature(self, method: str, path: str, query: str = '') -> dict:
        """HMAC-SHA256 서명 생성"""
        datetime_str = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        message = f'{datetime_str}{method}{path}{query}'
        signature = hmac.new(
            self.client_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        authorization = (
            f'CEA algorithm=HmacSHA256, access-key={self.client_id}, '
            f'signed-date={datetime_str}, signature={signature}'
        )
        return {
            'Authorization': authorization,
            'Content-Type': 'application/json;charset=UTF-8',
            'X-Requested-By': 'erp-suite',
        }

    def get_orders(self, from_date: datetime = None, to_date: datetime = None) -> list:
        """
        주문 목록 조회

        Returns:
            list[dict]: 주문 데이터 리스트
        """
        if not from_date:
            from_date = datetime.now() - timedelta(days=7)
        if not to_date:
            to_date = datetime.now()

        path = '/v2/providers/openapi/apis/api/v4/vendors/A00000001/ordersheets'
        query_params = {
            'createdAtFrom': from_date.strftime('%Y-%m-%d'),
            'createdAtTo': to_date.strftime('%Y-%m-%d'),
            'status': 'ACCEPT',
        }
        query_string = urlencode(query_params)

        if not self._cb.is_available:
            logger.warning('쿠팡 API 서킷브레이커 OPEN — 주문 조회 건너뜀')
            return []

        try:
            headers = self._generate_signature('GET', path, query_string)
            resp = self._session.get(
                f'{self.BASE_URL}{path}',
                headers=headers,
                params=query_params,
                timeout=30,
            )
            resp.raise_for_status()
            self._cb.record_success()
            return resp.json().get('data', [])
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('쿠팡 주문 조회 실패: %s', e)
            return []

    def normalize_order(self, raw_order: dict) -> dict:
        """쿠팡 API 응답을 MarketplaceOrder 필드에 매핑"""
        status_map = {
            'ACCEPT': 'NEW',
            'INSTRUCT': 'CONFIRMED',
            'DEPARTURE': 'SHIPPED',
            'DELIVERING': 'SHIPPED',
            'FINAL_DELIVERY': 'DELIVERED',
            'CANCEL': 'CANCELLED',
            'RETURN': 'RETURNED',
        }

        return {
            'store_order_id': str(raw_order.get('orderId', '')),
            'platform_order_id': str(raw_order.get('orderId', '')),
            'platform_product_order_id': str(raw_order.get('orderItemId', '')),
            'product_name': raw_order.get('sellerProductName', ''),
            'option_name': raw_order.get('sellerProductItemName', ''),
            'quantity': raw_order.get('shippingCount', 1),
            'price': raw_order.get('orderPrice', 0),
            'buyer_name': raw_order.get('orderer', {}).get('name', ''),
            'buyer_phone': raw_order.get('orderer', {}).get('email', ''),
            'receiver_name': raw_order.get('receiver', {}).get('name', ''),
            'receiver_phone': raw_order.get('receiver', {}).get('safeNumber', ''),
            'receiver_address': raw_order.get('receiver', {}).get('addr1', '') + ' ' + raw_order.get('receiver', {}).get('addr2', ''),
            'status': status_map.get(raw_order.get('status'), 'NEW'),
            'ordered_at': raw_order.get('orderedAt', ''),
            'delivery_company': raw_order.get('deliveryCompanyName', ''),
            'tracking_number': raw_order.get('invoiceNumber', ''),
        }

    def confirm_order(self, shipment_box_ids: list[int]) -> dict:
        """발주확인 처리

        Args:
            shipment_box_ids: 발주확인할 shipmentBoxId 리스트

        Returns:
            dict: API 응답 결과
        """
        path = '/v2/providers/openapi/apis/api/v4/vendors/A00000001/ordersheets/confirmation'
        query_string = ''

        if not self._cb.is_available:
            raise requests.RequestException('쿠팡 API 일시 차단 (서킷브레이커 OPEN)')

        try:
            headers = self._generate_signature('PUT', path, query_string)
            resp = self._session.put(
                f'{self.BASE_URL}{path}',
                headers=headers,
                json={'shipmentBoxIds': shipment_box_ids},
                timeout=30,
            )
            resp.raise_for_status()
            self._cb.record_success()
            result = resp.json()
            logger.info('쿠팡 발주확인 완료: %s', shipment_box_ids)
            return result
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('쿠팡 발주확인 실패: %s', e)
            raise

    def ship_order(self, shipment_box_id: int,
                   delivery_company: str, tracking_number: str) -> dict:
        """배송정보 등록

        Args:
            shipment_box_id: 출고 박스 ID
            delivery_company: 택배사명
            tracking_number: 운송장번호

        Returns:
            dict: API 응답 결과
        """
        path = '/v2/providers/openapi/apis/api/v4/vendors/A00000001/ordersheets/invoices'
        query_string = ''

        if not self._cb.is_available:
            raise requests.RequestException('쿠팡 API 일시 차단 (서킷브레이커 OPEN)')

        try:
            headers = self._generate_signature('POST', path, query_string)
            resp = self._session.post(
                f'{self.BASE_URL}{path}',
                headers=headers,
                json=[{
                    'shipmentBoxId': shipment_box_id,
                    'deliveryCompanyCode': delivery_company,
                    'invoiceNumber': tracking_number,
                }],
                timeout=30,
            )
            resp.raise_for_status()
            self._cb.record_success()
            result = resp.json()
            logger.info(
                '쿠팡 배송정보 등록 완료: box=%s (택배사: %s, 운송장: %s)',
                shipment_box_id, delivery_company, tracking_number,
            )
            return result
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error(
                '쿠팡 배송정보 등록 실패 (box=%s): %s', shipment_box_id, e,
            )
            raise


def get_client(config=None):
    """
    MarketplaceConfig 또는 SystemConfig에서 API 클라이언트를 반환합니다.

    config가 None이면 SystemConfig(관리자 설정)에서 자동으로 읽습니다.
    """
    if config is not None:
        shop_name_lower = config.shop_name.lower()
        if '네이버' in shop_name_lower or 'naver' in shop_name_lower:
            return NaverCommerceClient(config.client_id, config.client_secret)
        elif '쿠팡' in shop_name_lower or 'coupang' in shop_name_lower:
            return CoupangClient(config.client_id, config.client_secret)
        else:
            logger.warning('지원하지 않는 마켓플레이스: %s', config.shop_name)
            return None

    # SystemConfig(관리자 설정)에서 읽기
    return _get_client_from_system_config()


def get_all_clients():
    """SystemConfig에서 설정된 모든 마켓플레이스 클라이언트 반환"""
    return _get_client_from_system_config(all_clients=True)


def _get_client_from_system_config(all_clients=False):
    """관리자 설정(SystemConfig)에서 API 클라이언트 생성"""
    from apps.core.system_config import SystemConfig

    clients = []

    naver_id = SystemConfig.get_value('MARKETPLACE', 'naver_client_id')
    naver_secret = SystemConfig.get_value('MARKETPLACE', 'naver_client_secret')
    if naver_id and naver_secret:
        clients.append(NaverCommerceClient(naver_id, naver_secret))

    coupang_key = SystemConfig.get_value('MARKETPLACE', 'coupang_access_key')
    coupang_secret = SystemConfig.get_value('MARKETPLACE', 'coupang_secret_key')
    if coupang_key and coupang_secret:
        clients.append(CoupangClient(coupang_key, coupang_secret))

    if all_clients:
        return clients
    # 첫 번째 유효한 클라이언트 반환
    return clients[0] if clients else None
