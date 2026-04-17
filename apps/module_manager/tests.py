from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase, RequestFactory

from apps.module_manager.base import BaseFeatureModule
from apps.module_manager.models import InstalledModule
from apps.module_manager.registry import ModuleRegistry, module_registry
from apps.module_manager.signal_utils import module_signal_handler

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
        self.assertTrue(module_enabled({}, 'tag.test'))
        self.assertFalse(module_enabled({}, 'tag.nonexistent'))

    def test_module_enabled_inactive(self):
        from apps.module_manager.templatetags.module_tags import module_enabled
        InstalledModule.all_objects.create(
            module_id='tag.inactive', name='비활성',
            category='SYSTEM', is_enabled=True, is_active=False,
        )
        self.assertFalse(module_enabled({}, 'tag.inactive'))


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


class ModuleSignalHandlerTest(TestCase):
    def test_handler_runs_when_enabled(self):
        InstalledModule.objects.create(
            module_id='sig.enabled', name='Enabled',
            category='SYSTEM', is_enabled=True,
        )
        call_log = []

        @module_signal_handler('sig.enabled')
        def handler(sender, **kwargs):
            call_log.append(True)

        handler(sender=None)
        self.assertEqual(len(call_log), 1)

    def test_handler_skipped_when_disabled(self):
        InstalledModule.objects.create(
            module_id='sig.disabled', name='Disabled',
            category='SYSTEM', is_enabled=False,
        )
        call_log = []

        @module_signal_handler('sig.disabled')
        def handler(sender, **kwargs):
            call_log.append(True)

        result = handler(sender=None)
        self.assertEqual(len(call_log), 0)
        self.assertIsNone(result)

    def test_handler_has_module_metadata(self):
        @module_signal_handler('sig.meta')
        def handler(sender, **kwargs):
            pass

        self.assertTrue(handler._is_module_gated)
        self.assertEqual(handler._module_id, 'sig.meta')


class RegistryCacheTest(TestCase):
    def setUp(self):
        self.registry = ModuleRegistry()

    def test_cache_returns_consistent_results(self):
        InstalledModule.objects.create(
            module_id='cache.test', name='Cache',
            category='SYSTEM', is_enabled=True,
        )
        self.assertTrue(self.registry.is_enabled('cache.test'))
        # Second call should use cache
        self.assertTrue(self.registry.is_enabled('cache.test'))

    def test_invalidate_single(self):
        InstalledModule.objects.create(
            module_id='cache.inv', name='Inv',
            category='SYSTEM', is_enabled=True,
        )
        self.assertTrue(self.registry.is_enabled('cache.inv'))
        self.registry.invalidate_cache('cache.inv')
        # After invalidation, next call queries DB again
        self.assertTrue(self.registry.is_enabled('cache.inv'))

    def test_invalidate_all(self):
        InstalledModule.objects.create(
            module_id='cache.all1', name='All1',
            category='SYSTEM', is_enabled=True,
        )
        InstalledModule.objects.create(
            module_id='cache.all2', name='All2',
            category='SYSTEM', is_enabled=True,
        )
        self.registry.is_enabled('cache.all1')
        self.registry.is_enabled('cache.all2')
        self.registry.invalidate_cache()
        self.assertEqual(len(self.registry._enabled_cache), 0)


class ModuleIncludeURLTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_url', password='testpass123', role='admin',
        )
        self.client.force_login(self.admin)

    def test_enabled_module_url_accessible(self):
        InstalledModule.objects.update_or_create(
            module_id='board',
            defaults={'name': '게시판', 'category': 'GROUPWARE', 'is_enabled': True},
        )
        resp = self.client.get('/board/')
        self.assertNotEqual(resp.status_code, 404)

    def test_disabled_module_url_returns_404(self):
        InstalledModule.objects.update_or_create(
            module_id='board',
            defaults={'name': '게시판', 'category': 'GROUPWARE', 'is_enabled': False},
        )
        resp = self.client.get('/board/')
        self.assertEqual(resp.status_code, 404)


class SeedMigrationTest(TestCase):
    def test_seed_modules_exist(self):
        """Verify seed migration created all 23 module records."""
        import importlib
        mod = importlib.import_module(
            'apps.module_manager.migrations.0003_seed_independent_modules',
        )
        expected_ids = {m['module_id'] for m in mod.MODULES}
        actual_ids = set(
            InstalledModule.objects.values_list('module_id', flat=True)
        )
        self.assertTrue(
            expected_ids.issubset(actual_ids),
            f'Missing modules: {expected_ids - actual_ids}',
        )

    def test_seed_modules_enabled_by_default(self):
        import importlib
        mod = importlib.import_module(
            'apps.module_manager.migrations.0003_seed_independent_modules',
        )
        expected_ids = [m['module_id'] for m in mod.MODULES]
        disabled = InstalledModule.objects.filter(
            module_id__in=expected_ids, is_enabled=False,
        ).values_list('module_id', flat=True)
        self.assertEqual(
            list(disabled), [],
            f'Expected all seed modules enabled, but disabled: {list(disabled)}',
        )


class ModuleDependencyCheckViewTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_depcheck', password='testpass123', role='admin',
        )
        self.client.force_login(self.admin)

    def test_check_disable_no_dependents(self):
        m = InstalledModule.objects.create(
            module_id='dep.solo', name='독립 모듈', category='SYSTEM', is_enabled=True,
        )
        resp = self.client.get(
            f'/modules/{m.pk}/dependency-check/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['action'], 'disable')
        self.assertEqual(data['dependents'], [])

    def test_check_disable_with_dependents(self):
        parent = InstalledModule.objects.create(
            module_id='dep.parent2', name='부모', category='SYSTEM', is_enabled=True,
        )
        InstalledModule.objects.create(
            module_id='dep.child2', name='자식', category='SYSTEM',
            is_enabled=True, dependencies=['dep.parent2'],
        )
        resp = self.client.get(
            f'/modules/{parent.pk}/dependency-check/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['action'], 'disable')
        self.assertEqual(len(data['dependents']), 1)
        self.assertEqual(data['dependents'][0]['module_id'], 'dep.child2')

    def test_check_enable_missing_dependency(self):
        m = InstalledModule.objects.create(
            module_id='dep.needsparent', name='의존자', category='SYSTEM',
            is_enabled=False, dependencies=['dep.missing'],
        )
        resp = self.client.get(
            f'/modules/{m.pk}/dependency-check/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['action'], 'enable')
        self.assertEqual(len(data['dependencies']), 1)

    def test_check_enable_satisfied_dependency(self):
        InstalledModule.objects.create(
            module_id='dep.satisfied_parent', name='충족부모', category='SYSTEM',
            is_enabled=True,
        )
        m = InstalledModule.objects.create(
            module_id='dep.satisfied_child', name='충족자식', category='SYSTEM',
            is_enabled=False, dependencies=['dep.satisfied_parent'],
        )
        resp = self.client.get(
            f'/modules/{m.pk}/dependency-check/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['action'], 'enable')
        self.assertEqual(data['dependencies'], [])


class SidebarVisibilityTest(TestCase):
    """Test that sidebar items are hidden/shown based on module status."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_sidebar', password='testpass123', role='admin',
        )
        self.client.force_login(self.admin)
        # Clear singleton registry cache to ensure test isolation
        module_registry.invalidate_cache()

    def test_enabled_module_shows_in_sidebar(self):
        InstalledModule.objects.update_or_create(
            module_id='board',
            defaults={'is_enabled': True, 'is_active': True},
        )
        # Use the module list page (always accessible, renders base.html sidebar)
        resp = self.client.get('/modules/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '/board/')

    def test_disabled_module_hidden_from_sidebar(self):
        InstalledModule.objects.update_or_create(
            module_id='board',
            defaults={'is_enabled': False},
        )
        resp = self.client.get('/modules/')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # The sidebar link should not be present for disabled modules
        self.assertNotIn('href="/board/"', content)


class ModuleToggleIntegrationTest(TestCase):
    """End-to-end: toggle module off then verify URL returns 404."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_toggle_e2e', password='testpass123', role='admin',
        )
        self.client.force_login(self.admin)
        module_registry.invalidate_cache()

    def test_toggle_off_blocks_url(self):
        m = InstalledModule.objects.get(module_id='board')
        self.assertTrue(m.is_enabled)
        # Access should work while enabled
        resp = self.client.get('/board/')
        self.assertNotEqual(resp.status_code, 404)
        # Toggle off via view
        self.client.post(f'/modules/{m.pk}/toggle/')
        m.refresh_from_db()
        self.assertFalse(m.is_enabled)
        # Now URL should return 404
        resp = self.client.get('/board/')
        self.assertEqual(resp.status_code, 404)

    def test_toggle_on_restores_url(self):
        m = InstalledModule.objects.get(module_id='board')
        m.is_enabled = False
        m.save()
        # URL should be blocked
        resp = self.client.get('/board/')
        self.assertEqual(resp.status_code, 404)
        # Toggle on
        self.client.post(f'/modules/{m.pk}/toggle/')
        m.refresh_from_db()
        self.assertTrue(m.is_enabled)
        # URL should work again
        resp = self.client.get('/board/')
        self.assertNotEqual(resp.status_code, 404)
