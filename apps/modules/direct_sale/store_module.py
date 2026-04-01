from decimal import Decimal

from apps.store_modules.base import BaseStoreModule
from apps.store_modules.registry import registry


class DirectSaleModule(BaseStoreModule):
    module_id = 'direct_sale'
    module_name = '직접판매'
    has_api = False

    def calculate_commission(self, order, partner) -> Decimal:
        return Decimal('0')


registry.register(DirectSaleModule)
