from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory

from apps.module_manager.base import BaseFeatureModule
from apps.module_manager.models import InstalledModule
from apps.module_manager.registry import ModuleRegistry

User = get_user_model()


class InstalledModuleModelTest(TestCase):
    def test_create_module(self):
        m = InstalledModule.objects.create(
            module_id='test.module',
            name='테스트 모듈',
            category='SYSTEM',
        )
        self.assertEqual(str(m), '테스트 모듈 (test.module)')
        self.assertFalse(m.is_enabled)
        self.assertTrue(m.is_active)

    def test_module_unique_id(self):
        InstalledModule.objects.create(
            module_id='test.unique', name='모듈1', category='SYSTEM',
        )
        with self.assertRaises(Exception):
            InstalledModule.objects.create(
                module_id='test.unique', name='모듈2', category='SYSTEM',
            )

    def test_enable_disable(self):
        m = InstalledModule.objects.create(
            module_id='test.toggle', name='토글 모듈', category='SYSTEM',
        )
        self.assertFalse(m.is_enabled)
        m.is_enabled = True
        m.save()
        m.refresh_from_db()
        self.assertTrue(m.is_enabled)

    def test_default_ordering(self):
        InstalledModule.objects.create(
            module_id='z.module', name='Z 모듈', category='SYSTEM', sort_order=2,
        )
        InstalledModule.objects.create(
            module_id='a.module', name='A 모듈', category='HR', sort_order=1,
        )
        modules = list(InstalledModule.objects.values_list('module_id', flat=True))
        self.assertEqual(modules[0], 'a.module')
        self.assertEqual(modules[1], 'z.module')


class ModuleRegistryTest(TestCase):
    def setUp(self):
        self.registry = ModuleRegistry()
        self.registry._modules = {}

    def test_register_and_get(self):
        class DummyModule(BaseFeatureModule):
            module_id = 'test.dummy'
            name = '더미'
            category = 'SYSTEM'

            def get_urls(self):
                return []

            def get_sidebar_items(self):
                return []

        self.registry.register(DummyModule)
        self.assertIsNotNone(self.registry.get_module('test.dummy'))
        self.assertIsNone(self.registry.get_module('nonexistent'))

    def test_get_all(self):
        class Mod1(BaseFeatureModule):
            module_id = 'test.mod1'
            name = '모듈1'
            category = 'SYSTEM'
            def get_urls(self): return []
            def get_sidebar_items(self): return []

        class Mod2(BaseFeatureModule):
            module_id = 'test.mod2'
            name = '모듈2'
            category = 'HR'
            def get_urls(self): return []
            def get_sidebar_items(self): return []

        self.registry.register(Mod1)
        self.registry.register(Mod2)
        self.assertEqual(len(self.registry.get_all()), 2)

    def test_get_enabled(self):
        class EnabledMod(BaseFeatureModule):
            module_id = 'test.enabled'
            name = '활성 모듈'
            category = 'SYSTEM'
            def get_urls(self): return []
            def get_sidebar_items(self): return []

        self.registry.register(EnabledMod)
        InstalledModule.objects.create(
            module_id='test.enabled', name='활성 모듈',
            category='SYSTEM', is_enabled=True,
        )
        enabled = self.registry.get_enabled()
        self.assertIn('test.enabled', enabled)

    def test_is_enabled(self):
        InstalledModule.objects.create(
            module_id='test.check', name='체크', category='SYSTEM', is_enabled=True,
        )
        self.assertTrue(self.registry.is_enabled('test.check'))
        self.assertFalse(self.registry.is_enabled('nonexistent'))


class ModuleTemplateTagTest(TestCase):
    def test_module_enabled_tag(self):
        from apps.module_manager.templatetags.module_tags import module_enabled
        InstalledModule.objects.create(
            module_id='tag.test', name='태그 테스트',
            category='SYSTEM', is_enabled=True,
        )
        self.assertTrue(module_enabled('tag.test'))
        self.assertFalse(module_enabled('tag.nonexistent'))

    def test_module_enabled_inactive(self):
        from apps.module_manager.templatetags.module_tags import module_enabled
        InstalledModule.all_objects.create(
            module_id='tag.inactive', name='비활성',
            category='SYSTEM', is_enabled=True, is_active=False,
        )
        self.assertFalse(module_enabled('tag.inactive'))


class ModuleToggleViewTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_test', password='testpass123', role='admin',
        )
        self.client.force_login(self.admin)

    def test_toggle_enable(self):
        m = InstalledModule.objects.create(
            module_id='view.toggle', name='토글 뷰', category='SYSTEM',
        )
        resp = self.client.post(f'/modules/{m.pk}/toggle/')
        m.refresh_from_db()
        self.assertTrue(m.is_enabled)
        self.assertEqual(resp.status_code, 302)

    def test_toggle_disable_with_dependent(self):
        parent = InstalledModule.objects.create(
            module_id='view.parent', name='부모', category='SYSTEM', is_enabled=True,
        )
        InstalledModule.objects.create(
            module_id='view.child', name='자식', category='SYSTEM',
            is_enabled=True, dependencies=['view.parent'],
        )
        resp = self.client.post(f'/modules/{parent.pk}/toggle/')
        parent.refresh_from_db()
        self.assertTrue(parent.is_enabled)  # should NOT have been disabled

    def test_enable_missing_dependency(self):
        m = InstalledModule.objects.create(
            module_id='view.dep', name='의존', category='SYSTEM',
            dependencies=['nonexistent.dep'],
        )
        resp = self.client.post(f'/modules/{m.pk}/toggle/')
        m.refresh_from_db()
        self.assertFalse(m.is_enabled)  # should NOT have been enabled


class ModuleRequiredMixinTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_mixin', password='testpass123', role='admin',
        )
        self.client.force_login(self.admin)

    def test_access_allowed_when_enabled(self):
        InstalledModule.objects.create(
            module_id='mixin.test', name='Mixin Test',
            category='SYSTEM', is_enabled=True,
        )
        # ModuleListView doesn't use ModuleRequiredMixin, so test via decorator
        from django.test import RequestFactory
        from django.http import HttpResponse
        from apps.module_manager.decorators import module_required

        @module_required('mixin.test')
        def dummy_view(request):
            return HttpResponse('ok')

        factory = RequestFactory()
        req = factory.get('/')
        req.user = self.admin
        resp = dummy_view(req)
        self.assertEqual(resp.status_code, 200)

    def test_access_blocked_when_disabled(self):
        InstalledModule.objects.create(
            module_id='mixin.blocked', name='Blocked',
            category='SYSTEM', is_enabled=False,
        )
        from django.test import RequestFactory
        from django.http import Http404
        from apps.module_manager.decorators import module_required

        @module_required('mixin.blocked')
        def dummy_view(request):
            return HttpResponse('ok')

        factory = RequestFactory()
        req = factory.get('/')
        req.user = self.admin
        with self.assertRaises(Http404):
            dummy_view(req)

    def test_access_blocked_when_module_not_exists(self):
        from django.test import RequestFactory
        from django.http import Http404
        from apps.module_manager.decorators import module_required

        @module_required('nonexistent.module')
        def dummy_view(request):
            return HttpResponse('ok')

        factory = RequestFactory()
        req = factory.get('/')
        req.user = self.admin
        with self.assertRaises(Http404):
            dummy_view(req)
