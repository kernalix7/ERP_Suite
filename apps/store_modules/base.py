from abc import ABC
from decimal import Decimal


class BaseStoreModule(ABC):
    module_id: str = ''
    module_name: str = ''
    has_api: bool = False

    def get_api_client(self, config: dict):
        return None

    def fetch_orders(self, client, from_date=None, to_date=None) -> list[dict]:
        return []

    def normalize_order(self, raw_order: dict) -> dict:
        return raw_order

    def map_status(self, platform_status: str) -> str:
        return platform_status

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

    def match_product(self, product_name: str, option_name: str = ''):
        from apps.inventory.models import Product
        return Product.objects.filter(name=product_name, is_active=True).first()

    @property
    def vat_included(self) -> bool:
        return False

    def get_required_config_keys(self) -> list[dict]:
        return []
