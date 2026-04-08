from decimal import Decimal

from django.test import TestCase

from apps.store_modules.base import BaseStoreModule
from apps.store_modules.models import StoreModuleConfig
from apps.store_modules.registry import registry


class RegistryTests(TestCase):
    """ModuleRegistry 테스트"""

    def test_registry_has_modules(self):
        """3개 모듈이 등록되어 있어야 한다."""
        modules = registry.all()
        self.assertIn('naver_smartstore', modules)
        self.assertIn('coupang', modules)
        self.assertIn('direct_sale', modules)
        self.assertEqual(len(modules), 3)

    def test_registry_choices(self):
        """choices()가 올바른 형식을 반환해야 한다."""
        choices = registry.choices()
        # 첫 항목은 빈 선택지
        self.assertEqual(choices[0], ('', '-- 선택 --'))
        # module_id, module_name 튜플
        ids = [c[0] for c in choices[1:]]
        self.assertIn('naver_smartstore', ids)
        self.assertIn('coupang', ids)
        self.assertIn('direct_sale', ids)

    def test_get_instance(self):
        """module_id로 인스턴스를 조회할 수 있어야 한다."""
        naver = registry.get_instance('naver_smartstore')
        self.assertIsNotNone(naver)
        self.assertIsInstance(naver, BaseStoreModule)
        self.assertEqual(naver.module_id, 'naver_smartstore')
        self.assertEqual(naver.module_name, '네이버 스마트스토어')
        self.assertTrue(naver.has_api)

    def test_get_instance_coupang(self):
        """쿠팡 모듈 인스턴스 조회"""
        coupang = registry.get_instance('coupang')
        self.assertIsNotNone(coupang)
        self.assertEqual(coupang.module_id, 'coupang')
        self.assertTrue(coupang.has_api)

    def test_get_instance_direct_sale(self):
        """직접판매 모듈 인스턴스 조회"""
        direct = registry.get_instance('direct_sale')
        self.assertIsNotNone(direct)
        self.assertEqual(direct.module_id, 'direct_sale')
        self.assertFalse(direct.has_api)

    def test_get_instance_unknown(self):
        """존재하지 않는 module_id는 None을 반환해야 한다."""
        result = registry.get_instance('nonexistent_module')
        self.assertIsNone(result)


class ModulePropertyTests(TestCase):
    """모듈별 속성 테스트"""

    def test_naver_vat_included(self):
        """네이버 스마트스토어는 VAT 포함이다."""
        naver = registry.get_instance('naver_smartstore')
        self.assertTrue(naver.vat_included)

    def test_coupang_vat_not_included(self):
        """쿠팡은 기본 VAT 미포함이다."""
        coupang = registry.get_instance('coupang')
        self.assertFalse(coupang.vat_included)

    def test_direct_sale_no_commission(self):
        """직접판매 수수료는 0이다."""
        direct = registry.get_instance('direct_sale')
        result = direct.calculate_commission(None, None)
        self.assertEqual(result, Decimal('0'))

    def test_direct_sale_fetch_returns_empty(self):
        """직접판매 모듈의 fetch 메서드는 빈 리스트를 반환한다."""
        direct = registry.get_instance('direct_sale')
        self.assertEqual(direct.fetch_orders(None), [])
        self.assertEqual(direct.fetch_customers(None), [])
        self.assertEqual(direct.fetch_shipments(None), [])
        self.assertEqual(direct.fetch_settlements(None), [])

    def test_direct_sale_normalize_returns_empty(self):
        """직접판매 모듈의 normalize 메서드는 빈 dict를 반환한다."""
        direct = registry.get_instance('direct_sale')
        self.assertEqual(direct.normalize_order({}), {})
        self.assertEqual(direct.normalize_customer({}), {})
        self.assertEqual(direct.normalize_shipment({}), {})
        self.assertEqual(direct.normalize_settlement({}), {})

    def test_naver_status_map(self):
        """네이버 상태 매핑이 올바르게 작동해야 한다."""
        naver = registry.get_instance('naver_smartstore')
        self.assertEqual(naver.map_status('PAYMENT_WAITING'), 'NEW')
        self.assertEqual(naver.map_status('PAYED'), 'CONFIRMED')
        self.assertEqual(naver.map_status('DELIVERING'), 'SHIPPED')
        self.assertEqual(naver.map_status('DELIVERED'), 'DELIVERED')
        self.assertEqual(naver.map_status('PURCHASE_DECIDED'), 'DELIVERED')
        self.assertEqual(naver.map_status('CANCELED'), 'CANCELLED')
        self.assertEqual(naver.map_status('CANCELED_BY_NOPAYMENT'), 'CANCELLED')
        self.assertEqual(naver.map_status('RETURNED'), 'RETURNED')
        self.assertEqual(naver.map_status('EXCHANGED'), 'RETURNED')
        # 알 수 없는 상태는 그대로 반환
        self.assertEqual(naver.map_status('UNKNOWN'), 'UNKNOWN')

    def test_coupang_status_map(self):
        """쿠팡 상태 매핑이 올바르게 작동해야 한다."""
        coupang = registry.get_instance('coupang')
        self.assertEqual(coupang.map_status('ACCEPT'), 'NEW')
        self.assertEqual(coupang.map_status('INSTRUCT'), 'CONFIRMED')
        self.assertEqual(coupang.map_status('DEPARTURE'), 'SHIPPED')
        self.assertEqual(coupang.map_status('DELIVERING'), 'SHIPPED')
        self.assertEqual(coupang.map_status('FINAL_DELIVERY'), 'DELIVERED')
        self.assertEqual(coupang.map_status('CANCEL'), 'CANCELLED')
        self.assertEqual(coupang.map_status('RETURN'), 'RETURNED')
        self.assertEqual(coupang.map_status('EXCHANGE'), 'RETURNED')

    def test_naver_required_config_keys(self):
        """네이버 모듈은 client_id, client_secret 설정을 요구한다."""
        naver = registry.get_instance('naver_smartstore')
        keys = naver.get_required_config_keys()
        key_names = [k['key'] for k in keys]
        self.assertIn('client_id', key_names)
        self.assertIn('client_secret', key_names)

    def test_coupang_required_config_keys(self):
        """쿠팡 모듈은 access_key, secret_key 설정을 요구한다."""
        coupang = registry.get_instance('coupang')
        keys = coupang.get_required_config_keys()
        key_names = [k['key'] for k in keys]
        self.assertIn('access_key', key_names)
        self.assertIn('secret_key', key_names)


class StoreModuleConfigModelTests(TestCase):
    """StoreModuleConfig 모델 CRUD 테스트"""

    def test_create_config(self):
        """설정 생성"""
        config = StoreModuleConfig.objects.create(
            module_id='naver_smartstore',
            key='client_id',
            value='test_client_id',
            display_name='테스트 Client ID',
        )
        self.assertEqual(config.module_id, 'naver_smartstore')
        self.assertEqual(config.key, 'client_id')
        self.assertTrue(config.is_active)

    def test_get_value(self):
        """get_value 클래스메서드"""
        StoreModuleConfig.objects.create(
            module_id='coupang',
            key='access_key',
            value='test_key_123',
            display_name='Access Key',
        )
        val = StoreModuleConfig.get_value('coupang', 'access_key')
        self.assertEqual(val, 'test_key_123')

    def test_get_value_default(self):
        """존재하지 않는 키는 기본값을 반환한다."""
        val = StoreModuleConfig.get_value('nonexistent', 'key', default='fallback')
        self.assertEqual(val, 'fallback')

    def test_get_all_values(self):
        """get_all_values 클래스메서드"""
        StoreModuleConfig.objects.create(
            module_id='test_module', key='key1', value='val1', display_name='Key 1',
        )
        StoreModuleConfig.objects.create(
            module_id='test_module', key='key2', value='val2', display_name='Key 2',
        )
        vals = StoreModuleConfig.get_all_values('test_module')
        self.assertEqual(vals, {'key1': 'val1', 'key2': 'val2'})

    def test_unique_together(self):
        """같은 module_id + key 조합은 중복 불가"""
        StoreModuleConfig.objects.create(
            module_id='test_mod', key='dup_key', value='v1', display_name='D1',
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            StoreModuleConfig.objects.create(
                module_id='test_mod', key='dup_key', value='v2', display_name='D2',
            )

    def test_soft_delete(self):
        """soft delete 동작 확인"""
        config = StoreModuleConfig.objects.create(
            module_id='test_sd', key='k1', value='v1', display_name='SD Test',
        )
        config.soft_delete()
        self.assertFalse(
            StoreModuleConfig.objects.filter(pk=config.pk).exists()
        )
        self.assertTrue(
            StoreModuleConfig.all_objects.filter(pk=config.pk).exists()
        )

    def test_initialize_for_module(self):
        """initialize_for_module로 필수 설정이 생성되어야 한다."""
        naver = registry.get_instance('naver_smartstore')
        StoreModuleConfig.initialize_for_module(naver)
        configs = StoreModuleConfig.objects.filter(module_id='naver_smartstore')
        keys = list(configs.values_list('key', flat=True))
        self.assertIn('client_id', keys)
        self.assertIn('client_secret', keys)
