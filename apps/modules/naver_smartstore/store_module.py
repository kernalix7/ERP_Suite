from decimal import Decimal

from apps.store_modules.base import BaseStoreModule
from apps.store_modules.registry import registry


class NaverSmartStoreModule(BaseStoreModule):
    module_id = 'naver_smartstore'
    module_name = '네이버 스마트스토어'
    has_api = True

    DEFAULT_COMMISSION_RATE = Decimal('5.5')

    STATUS_MAP = {
        'PAYMENT_WAITING': 'NEW',
        'PAYED': 'CONFIRMED',
        'DELIVERING': 'SHIPPED',
        'DELIVERED': 'DELIVERED',
        'PURCHASE_DECIDED': 'DELIVERED',
        'CANCELED': 'CANCELLED',
        'CANCELED_BY_NOPAYMENT': 'CANCELLED',
        'RETURNED': 'RETURNED',
        'EXCHANGED': 'RETURNED',
    }

    def get_api_client(self, config: dict = None):
        from apps.marketplace.api_client import NaverCommerceClient
        if config:
            return NaverCommerceClient(
                config.get('client_id', ''),
                config.get('client_secret', ''),
            )
        from apps.store_modules.models import StoreModuleConfig
        client_id = StoreModuleConfig.get_value('naver_smartstore', 'client_id')
        client_secret = StoreModuleConfig.get_value('naver_smartstore', 'client_secret')
        return NaverCommerceClient(client_id, client_secret)

    @property
    def vat_included(self) -> bool:
        return True

    def get_required_config_keys(self) -> list[dict]:
        return [
            {
                'key': 'client_id',
                'display_name': '네이버 커머스 Client ID',
                'value_type': 'password',
                'is_secret': True,
            },
            {
                'key': 'client_secret',
                'display_name': '네이버 커머스 Client Secret',
                'value_type': 'password',
                'is_secret': True,
            },
        ]

    # --- 1) 고객 ---

    def fetch_customers(self, client, from_date=None, to_date=None) -> list[dict]:
        orders = self.fetch_orders(client, from_date, to_date)
        seen, customers = set(), []
        for raw in orders:
            order_info = raw.get('order', {})
            buyer_name = order_info.get('ordererName', '')
            if buyer_name and buyer_name not in seen:
                seen.add(buyer_name)
                customers.append(raw)
        return customers

    def normalize_customer(self, raw_customer: dict) -> dict:
        order_info = raw_customer.get('order', {})
        delivery = raw_customer.get('delivery', {})
        return {
            'name': order_info.get('ordererName', ''),
            'phone': order_info.get('ordererTel', ''),
            'address': (
                delivery.get('baseAddress', '') + ' '
                + delivery.get('detailedAddress', '')
            ).strip(),
            'zipcode': delivery.get('zipCode', ''),
        }

    # --- 2) 견적(주문) ---

    def fetch_orders(self, client, from_date=None, to_date=None) -> list[dict]:
        return client.get_orders(from_date=from_date, to_date=to_date)

    def normalize_order(self, raw_order: dict) -> dict:
        order_info = raw_order.get('order', {})
        product_order = raw_order.get('productOrder', {})
        delivery = raw_order.get('delivery', {})

        from apps.marketplace.api_client import NaverCommerceClient

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
            'receiver_address': (
                delivery.get('baseAddress', '') + ' '
                + delivery.get('detailedAddress', '')
            ).strip(),
            'receiver_zipcode': delivery.get('zipCode', ''),
            'status': self.map_status(
                product_order.get('productOrderStatus', ''),
            ),
            'ordered_at': product_order.get('orderDate', ''),
            'delivery_company': NaverCommerceClient.DELIVERY_CODE_TO_NAME.get(
                delivery.get('deliveryCompanyCode', ''), '',
            ),
            'tracking_number': delivery.get('trackingNumber', ''),
        }

    def map_status(self, platform_status: str) -> str:
        return self.STATUS_MAP.get(platform_status, platform_status)

    def match_product(self, product_name: str, option_name: str = ''):
        from apps.inventory.models import Product
        from apps.marketplace.models import ProductMapping

        mapping = ProductMapping.objects.filter(
            store_product_name=product_name,
            store_option_name=option_name or '',
            is_active=True,
        ).select_related('product').first()
        if mapping:
            return mapping.product

        product = Product.objects.filter(
            name=product_name, is_active=True,
        ).first()
        if product:
            return product

        product = Product.objects.filter(
            name__icontains=product_name, is_active=True,
        ).first()
        if product:
            return product

        if option_name:
            product = Product.objects.filter(
                name__icontains=option_name, is_active=True,
            ).first()
            if product:
                return product

        return None

    def calculate_commission(self, order, partner) -> Decimal:
        if partner:
            try:
                return super().calculate_commission(order, partner)
            except (AttributeError, TypeError):
                pass
        if order and hasattr(order, 'total_amount') and order.total_amount:
            return (
                Decimal(str(order.total_amount))
                * self.DEFAULT_COMMISSION_RATE
                / Decimal('100')
            )
        return Decimal('0')

    # --- 5) 역동기화 (ERP → 마켓) ---

    def push_shipment(self, client, platform_order_id, delivery_company, tracking_number):
        import logging
        logger = logging.getLogger(__name__)
        try:
            # 1) 발주확인
            client.dispatch_shipment([platform_order_id])
            # 2) 배송정보 등록
            client.ship_order(platform_order_id, delivery_company, tracking_number)
            return {'success': True, 'message': f'네이버 배송등록 완료: {platform_order_id}'}
        except Exception as e:
            logger.error('네이버 배송등록 실패 (%s): %s', platform_order_id, e)
            return {'success': False, 'message': str(e)}

    def push_return(self, client, platform_order_id, reason=''):
        import logging
        logger = logging.getLogger(__name__)
        # 네이버 반품 접수 API는 별도 엔드포인트 — 현재 미구현 (수동 처리 안내)
        logger.info('네이버 반품은 셀러센터에서 수동 처리 필요: %s', platform_order_id)
        return {
            'success': False,
            'message': f'네이버 반품은 셀러센터에서 수동 처리가 필요합니다 ({platform_order_id})',
        }

    # --- 3) 운송장 ---

    def fetch_shipments(self, client, from_date=None, to_date=None) -> list[dict]:
        orders = self.fetch_orders(client, from_date, to_date)
        return [
            o for o in orders
            if o.get('delivery', {}).get('trackingNumber')
        ]

    def normalize_shipment(self, raw_shipment: dict) -> dict:
        from apps.marketplace.api_client import NaverCommerceClient
        delivery = raw_shipment.get('delivery', {})
        product_order = raw_shipment.get('productOrder', {})
        return {
            'tracking_number': delivery.get('trackingNumber', ''),
            'delivery_company': NaverCommerceClient.DELIVERY_CODE_TO_NAME.get(
                delivery.get('deliveryCompanyCode', ''), '',
            ),
            'product_order_id': product_order.get('productOrderId', ''),
            'status': self.map_status(
                product_order.get('productOrderStatus', ''),
            ),
        }

    # --- 4) 정산 ---

    def fetch_settlements(self, client, from_date=None, to_date=None) -> list[dict]:
        orders = self.fetch_orders(client, from_date, to_date)
        return [
            o for o in orders
            if o.get('productOrder', {}).get('productOrderStatus')
            in ('PURCHASE_DECIDED', 'DELIVERED')
        ]

    def normalize_settlement(self, raw_settlement: dict) -> dict:
        product_order = raw_settlement.get('productOrder', {})
        commission = product_order.get('commissionAmount', 0)
        settlement_amount = product_order.get('totalPaymentAmount', 0)
        return {
            'product_order_id': product_order.get('productOrderId', ''),
            'settlement_amount': settlement_amount,
            'commission': commission,
            'net_amount': settlement_amount - commission,
            'status': self.map_status(
                product_order.get('productOrderStatus', ''),
            ),
        }


registry.register(NaverSmartStoreModule)
