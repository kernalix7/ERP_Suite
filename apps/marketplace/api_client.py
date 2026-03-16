"""
마켓플레이스 API 클라이언트 (네이버 커머스 / 쿠팡)

각 마켓플레이스의 주문 조회 API를 호출하여 MarketplaceOrder로 동기화합니다.
실제 API 연동 시 각 플랫폼의 인증 방식에 맞게 토큰을 발급받아야 합니다.
"""
import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class NaverCommerceClient:
    """
    네이버 커머스 API 클라이언트
    API 문서: https://apicenter.commerce.naver.com/ko/basic/commerce-api
    """
    BASE_URL = 'https://api.commerce.naver.com/external'
    TOKEN_URL = 'https://api.commerce.naver.com/external/v1/oauth2/token'

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = None
        self._token_expires_at = 0

    def _get_access_token(self) -> str:
        """OAuth 토큰 발급 (BCRYPT 서명 방식)"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        timestamp = int(time.time() * 1000)
        password = f'{self.client_id}_{timestamp}'
        sign = hmac.new(
            self.client_secret.encode('utf-8'),
            password.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        data = {
            'client_id': self.client_id,
            'timestamp': timestamp,
            'client_secret_sign': sign,
            'grant_type': 'client_credentials',
            'type': 'SELF',
        }

        try:
            resp = requests.post(self.TOKEN_URL, data=data, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            self._access_token = result['access_token']
            self._token_expires_at = time.time() + result.get('expires_in', 3600) - 60
            return self._access_token
        except requests.RequestException as e:
            logger.error('네이버 토큰 발급 실패: %s', e)
            raise

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._get_access_token()}',
            'Content-Type': 'application/json',
        }

    def get_orders(self, from_date: datetime = None, to_date: datetime = None) -> list:
        """
        주문 목록 조회 (최근 주문 기준)

        Returns:
            list[dict]: 주문 데이터 리스트
        """
        if not from_date:
            from_date = datetime.now() - timedelta(days=1)
        if not to_date:
            to_date = datetime.now()

        url = f'{self.BASE_URL}/v1/pay-order/seller/product-orders/last-changed-statuses'
        params = {
            'lastChangedFrom': from_date.strftime('%Y-%m-%dT%H:%M:%S.000+09:00'),
            'lastChangedTo': to_date.strftime('%Y-%m-%dT%H:%M:%S.000+09:00'),
        }

        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            product_order_ids = [
                item['productOrderId']
                for item in data.get('data', {}).get('lastChangeStatuses', [])
            ]
            if not product_order_ids:
                return []
            return self._get_order_details(product_order_ids)
        except requests.RequestException as e:
            logger.error('네이버 주문 조회 실패: %s', e)
            return []

    def _get_order_details(self, product_order_ids: list) -> list:
        """주문 상세 조회"""
        url = f'{self.BASE_URL}/v1/pay-order/seller/product-orders/query'
        try:
            resp = requests.post(
                url,
                headers=self._headers(),
                json={'productOrderIds': product_order_ids},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get('data', [])
        except requests.RequestException as e:
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

        try:
            headers = self._generate_signature('GET', path, query_string)
            resp = requests.get(
                f'{self.BASE_URL}{path}',
                headers=headers,
                params=query_params,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get('data', [])
        except requests.RequestException as e:
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


def get_client(config):
    """
    MarketplaceConfig에서 적절한 API 클라이언트를 반환합니다.

    Args:
        config: MarketplaceConfig instance

    Returns:
        NaverCommerceClient or CoupangClient
    """
    shop_name_lower = config.shop_name.lower()
    if '네이버' in shop_name_lower or 'naver' in shop_name_lower:
        return NaverCommerceClient(config.client_id, config.client_secret)
    elif '쿠팡' in shop_name_lower or 'coupang' in shop_name_lower:
        return CoupangClient(config.client_id, config.client_secret)
    else:
        logger.warning('지원하지 않는 마켓플레이스: %s', config.shop_name)
        return None
