from decimal import Decimal

from apps.store_modules.base import BaseStoreModule
from apps.store_modules.registry import registry


class DirectSaleModule(BaseStoreModule):
    module_id = 'direct_sale'
    module_name = '직접판매'
    has_api = False

    def calculate_commission(self, order, partner) -> Decimal:
        return Decimal('0')

    # API 없는 직접판매 — 모든 fetch 메서드는 빈 리스트 반환
    def fetch_customers(self, client, from_date=None, to_date=None) -> list[dict]:
        return []

    def normalize_customer(self, raw_customer: dict) -> dict:
        return {}

    def fetch_orders(self, client, from_date=None, to_date=None) -> list[dict]:
        return []

    def normalize_order(self, raw_order: dict) -> dict:
        return {}

    def fetch_shipments(self, client, from_date=None, to_date=None) -> list[dict]:
        return []

    def normalize_shipment(self, raw_shipment: dict) -> dict:
        return {}

    def fetch_settlements(self, client, from_date=None, to_date=None) -> list[dict]:
        return []

    def normalize_settlement(self, raw_settlement: dict) -> dict:
        return {}


registry.register(DirectSaleModule)
