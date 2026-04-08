from abc import ABC
from decimal import Decimal


class BaseStoreModule(ABC):
    module_id: str = ''
    module_name: str = ''
    has_api: bool = False

    # --- 공통 ---

    def get_api_client(self, config: dict):
        return None

    def get_required_config_keys(self) -> list[dict]:
        return []

    @property
    def vat_included(self) -> bool:
        return False

    # --- 1) 고객 불러오기 ---

    def fetch_customers(self, client, from_date=None, to_date=None) -> list[dict]:
        raise NotImplementedError

    def normalize_customer(self, raw_customer: dict) -> dict:
        raise NotImplementedError

    # --- 2) 견적(주문) 불러오기 ---

    def fetch_orders(self, client, from_date=None, to_date=None) -> list[dict]:
        raise NotImplementedError

    def normalize_order(self, raw_order: dict) -> dict:
        raise NotImplementedError

    def map_status(self, platform_status: str) -> str:
        return platform_status

    def match_product(self, product_name: str, option_name: str = ''):
        from apps.inventory.models import Product
        return Product.objects.filter(name=product_name, is_active=True).first()

    # --- 3) 운송장 불러오기 ---

    def fetch_shipments(self, client, from_date=None, to_date=None) -> list[dict]:
        raise NotImplementedError

    def normalize_shipment(self, raw_shipment: dict) -> dict:
        raise NotImplementedError

    # --- 4) 정산 불러오기 ---

    def fetch_settlements(self, client, from_date=None, to_date=None) -> list[dict]:
        raise NotImplementedError

    def normalize_settlement(self, raw_settlement: dict) -> dict:
        raise NotImplementedError

    def calculate_commission(self, order, partner) -> Decimal:
        """기본: CommissionRate 테이블 기반 계산"""
        total = Decimal('0')
        for item in order.items.filter(is_active=True):
            item_amount = int(item.amount) if item.amount else 0
            total += partner.calculate_commission(item_amount, product=item.product)
        return total

    def get_settlement_bank_account(self, order, partner):
        """기본: order.bank_account -> 기본계좌"""
        if order and order.bank_account:
            return order.bank_account
        from apps.accounting.models import BankAccount
        return BankAccount.objects.filter(is_active=True, is_default=True).first()
