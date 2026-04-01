from apps.store_modules.base import BaseStoreModule
from apps.store_modules.registry import registry


class CoupangModule(BaseStoreModule):
    module_id = 'coupang'
    module_name = '쿠팡'
    has_api = True

    STATUS_MAP = {
        'ACCEPT': 'NEW',
        'INSTRUCT': 'CONFIRMED',
        'DEPARTURE': 'SHIPPED',
        'DELIVERING': 'SHIPPED',
        'FINAL_DELIVERY': 'DELIVERED',
        'CANCEL': 'CANCELLED',
        'RETURN': 'RETURNED',
    }

    def get_api_client(self, config: dict):
        from apps.marketplace.api_client import CoupangClient
        return CoupangClient(
            config.get('access_key', ''),
            config.get('secret_key', ''),
        )

    def fetch_orders(self, client, from_date=None, to_date=None) -> list[dict]:
        return client.get_orders(from_date=from_date, to_date=to_date)

    def normalize_order(self, raw_order: dict) -> dict:
        from apps.marketplace.api_client import CoupangClient
        client = CoupangClient('', '')
        return client.normalize_order(raw_order)

    def map_status(self, platform_status: str) -> str:
        return self.STATUS_MAP.get(platform_status, platform_status)

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


registry.register(CoupangModule)
