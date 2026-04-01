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

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self._access_token = None
        self._token_expires_at = 0
        self._session = create_retry_session(timeout=30)
        self._cb = circuit_breakers['naver']

    def _get_access_token(self) -> str:
        """OAuth 토큰 발급 (BCrypt 서명 방식)"""
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

        try:
            resp = self._session.post(self.TOKEN_URL, data=data, timeout=10)
            if resp.status_code != 200:
                logger.error(
                    '네이버 토큰 발급 실패 상세 — status=%s, body=%s',
                    resp.status_code, resp.text[:500],
                )
            resp.raise_for_status()
            result = resp.json()
            self._access_token = result['access_token']
            self._token_expires_at = time.time() + result.get('expires_in', 3600) - 60
            self._cb.record_success()
            return self._access_token
        except requests.RequestException as e:
            self._cb.record_failure()
            logger.error('네이버 토큰 발급 실패: %s', e)
            raise

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
            from_date = datetime.now() - timedelta(days=1)
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
            'PAYED': 'NEW',
            'DELIVERING': 'SHIPPED',
            'DELIVERED': 'DELIVERED',
            'PURCHASE_DECIDED': 'DELIVERED',
            'CANCELED': 'CANCELLED',
            'RETURNED': 'RETURNED',
            'EXCHANGED': 'RETURNED',
        }

        return {
            'store_order_id': product_order.get('productOrderId', ''),
            'product_name': product_order.get('productName', ''),
            'option_name': product_order.get('optionContent', ''),
            'quantity': product_order.get('quantity', 1),
            'price': product_order.get('totalPaymentAmount', 0),
            'buyer_name': order_info.get('ordererName', ''),
            'buyer_phone': order_info.get('ordererTel', ''),
            'receiver_name': delivery.get('name', ''),
            'receiver_phone': delivery.get('tel1', ''),
            'receiver_address': delivery.get('baseAddress', '') + ' ' + delivery.get('detailedAddress', ''),
            'status': status_map.get(product_order.get('productOrderStatus'), 'NEW'),
            'ordered_at': product_order.get('orderDate', ''),
        }


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
            from_date = datetime.now() - timedelta(days=1)
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
        }


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
