from decimal import Decimal

from apps.store_modules.base import BaseStoreModule
from apps.store_modules.registry import registry


class CoupangModule(BaseStoreModule):
    module_id = 'coupang'
    module_name = '쿠팡'
    has_api = True

    DEFAULT_COMMISSION_RATE = Decimal('10.8')

    STATUS_MAP = {
        'ACCEPT': 'NEW',
        'INSTRUCT': 'CONFIRMED',
        'DEPARTURE': 'SHIPPED',
        'DELIVERING': 'SHIPPED',
        'FINAL_DELIVERY': 'DELIVERED',
        'CANCEL': 'CANCELLED',
        'RETURN': 'RETURNED',
        'EXCHANGE': 'RETURNED',
    }

    def get_api_client(self, config: dict = None):
        from apps.marketplace.api_client import CoupangClient
        if config:
            return CoupangClient(
                config.get('access_key', ''),
                config.get('secret_key', ''),
            )
        from apps.store_modules.models import StoreModuleConfig
        access_key = StoreModuleConfig.get_value('coupang', 'access_key')
        secret_key = StoreModuleConfig.get_value('coupang', 'secret_key')
        return CoupangClient(access_key, secret_key)

    def get_required_config_keys(self) -> list[dict]:
        return [
            {
                'key': 'access_key',
                'display_name': '쿠팡 Access Key',
                'value_type': 'password',
                'is_secret': True,
            },
            {
                'key': 'secret_key',
                'display_name': '쿠팡 Secret Key',
                'value_type': 'password',
                'is_secret': True,
            },
        ]

    # --- 1) 고객 ---

    def fetch_customers(self, client, from_date=None, to_date=None) -> list[dict]:
        orders = self.fetch_orders(client, from_date, to_date)
        seen, customers = set(), []
        for raw in orders:
            buyer_name = raw.get('orderer', {}).get('name', '')
            if buyer_name and buyer_name not in seen:
                seen.add(buyer_name)
                customers.append(raw)
        return customers

    def normalize_customer(self, raw_customer: dict) -> dict:
        orderer = raw_customer.get('orderer', {})
        receiver = raw_customer.get('receiver', {})
        return {
            'name': orderer.get('name', ''),
            'phone': receiver.get('safeNumber', ''),
            'address': (
                receiver.get('addr1', '') + ' '
                + receiver.get('addr2', '')
            ).strip(),
            'zipcode': receiver.get('postCode', ''),
        }

    # --- 2) 견적(주문) ---

    def fetch_orders(self, client, from_date=None, to_date=None) -> list[dict]:
        return client.get_orders(from_date=from_date, to_date=to_date)

    def normalize_order(self, raw_order: dict) -> dict:
        receiver = raw_order.get('receiver', {})
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
            'receiver_name': receiver.get('name', ''),
            'receiver_phone': receiver.get('safeNumber', ''),
            'receiver_address': (
                receiver.get('addr1', '') + ' '
                + receiver.get('addr2', '')
            ).strip(),
            'receiver_zipcode': receiver.get('postCode', ''),
            'status': self.map_status(raw_order.get('status', '')),
            'ordered_at': raw_order.get('orderedAt', ''),
            'delivery_company': raw_order.get('deliveryCompanyName', ''),
            'tracking_number': raw_order.get('invoiceNumber', ''),
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
            shipment_box_id = int(platform_order_id)
            client.ship_order(shipment_box_id, delivery_company, tracking_number)
            return {'success': True, 'message': f'쿠팡 배송등록 완료: {platform_order_id}'}
        except (ValueError, TypeError):
            return {'success': False, 'message': f'유효하지 않은 주문번호: {platform_order_id}'}
        except Exception as e:
            logger.error('쿠팡 배송등록 실패 (%s): %s', platform_order_id, e)
            return {'success': False, 'message': str(e)}

    def push_return(self, client, platform_order_id, reason=''):
        import logging
        logger = logging.getLogger(__name__)
        # 쿠팡 반품 접수 API — 현재 미구현 (수동 처리 안내)
        logger.info('쿠팡 반품은 Wing에서 수동 처리 필요: %s', platform_order_id)
        return {
            'success': False,
            'message': f'쿠팡 반품은 Wing에서 수동 처리가 필요합니다 ({platform_order_id})',
        }

    # --- 3) 운송장 ---

    def fetch_shipments(self, client, from_date=None, to_date=None) -> list[dict]:
        orders = self.fetch_orders(client, from_date, to_date)
        return [o for o in orders if o.get('invoiceNumber')]

    def normalize_shipment(self, raw_shipment: dict) -> dict:
        return {
            'tracking_number': raw_shipment.get('invoiceNumber', ''),
            'delivery_company': raw_shipment.get('deliveryCompanyName', ''),
            'product_order_id': str(raw_shipment.get('orderItemId', '')),
            'status': self.map_status(raw_shipment.get('status', '')),
        }

    # --- 4) 정산 ---

    def fetch_settlements(self, client, from_date=None, to_date=None) -> list[dict]:
        orders = self.fetch_orders(client, from_date, to_date)
        return [
            o for o in orders
            if o.get('status') in ('FINAL_DELIVERY',)
        ]

    def normalize_settlement(self, raw_settlement: dict) -> dict:
        settlement_amount = raw_settlement.get('orderPrice', 0)
        commission = raw_settlement.get('commissionAmount', 0)
        return {
            'product_order_id': str(raw_settlement.get('orderItemId', '')),
            'settlement_amount': settlement_amount,
            'commission': commission,
            'net_amount': settlement_amount - commission,
            'status': self.map_status(raw_settlement.get('status', '')),
        }


registry.register(CoupangModule)
