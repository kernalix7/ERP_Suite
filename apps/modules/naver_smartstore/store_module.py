from apps.store_modules.base import BaseStoreModule
from apps.store_modules.registry import registry


class NaverSmartStoreModule(BaseStoreModule):
    module_id = 'naver_smartstore'
    module_name = '네이버 스마트스토어'
    has_api = True

    STATUS_MAP = {
        'PAYED': 'NEW',
        'DELIVERING': 'SHIPPED',
        'DELIVERED': 'DELIVERED',
        'PURCHASE_DECIDED': 'DELIVERED',
        'CANCELED': 'CANCELLED',
        'RETURNED': 'RETURNED',
        'EXCHANGED': 'RETURNED',
    }

    def get_api_client(self, config: dict):
        from apps.marketplace.api_client import NaverCommerceClient
        return NaverCommerceClient(
            config.get('client_id', ''),
            config.get('client_secret', ''),
        )

    def fetch_orders(self, client, from_date=None, to_date=None) -> list[dict]:
        return client.get_orders(from_date=from_date, to_date=to_date)

    def normalize_order(self, raw_order: dict) -> dict:
        from apps.marketplace.api_client import NaverCommerceClient
        client = NaverCommerceClient('', '')
        return client.normalize_order(raw_order)

    def map_status(self, platform_status: str) -> str:
        return self.STATUS_MAP.get(platform_status, platform_status)

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


registry.register(NaverSmartStoreModule)
