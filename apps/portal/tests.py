from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User
from apps.sales.models import Partner

from .models import PortalDocument, PortalNotification, PortalUser


class PortalUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='portal_customer', password='testpass123',
        )
        self.partner = Partner.objects.create(
            code='PTN-P001', name='테스트 고객사',
            partner_type='CUSTOMER',
        )

    def test_create_portal_user(self):
        pu = PortalUser.objects.create(
            user=self.user,
            partner=self.partner,
            portal_type=PortalUser.PortalType.CUSTOMER,
            is_verified=True,
        )
        self.assertEqual(pu.portal_type, 'CUSTOMER')
        self.assertTrue(pu.is_verified)
        self.assertIn(self.partner.name, str(pu))

    def test_supplier_portal_user(self):
        supplier_user = User.objects.create_user(
            username='portal_supplier', password='testpass123',
        )
        supplier = Partner.objects.create(
            code='PTN-P002', name='테스트 공급처',
            partner_type='SUPPLIER',
        )
        pu = PortalUser.objects.create(
            user=supplier_user,
            partner=supplier,
            portal_type=PortalUser.PortalType.SUPPLIER,
        )
        self.assertEqual(pu.portal_type, 'SUPPLIER')
        self.assertFalse(pu.is_verified)

    def test_soft_delete(self):
        pu = PortalUser.objects.create(
            user=self.user, partner=self.partner,
            portal_type=PortalUser.PortalType.CUSTOMER,
        )
        pu.soft_delete()
        self.assertFalse(PortalUser.objects.filter(pk=pu.pk).exists())
        self.assertTrue(PortalUser.all_objects.filter(pk=pu.pk).exists())


class PortalNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='notif_user', password='testpass123')
        self.partner = Partner.objects.create(code='PTN-N01', name='알림고객', partner_type='CUSTOMER')
        self.portal_user = PortalUser.objects.create(
            user=self.user, partner=self.partner,
            portal_type=PortalUser.PortalType.CUSTOMER, is_verified=True,
        )

    def test_create_notification(self):
        notif = PortalNotification.objects.create(
            portal_user=self.portal_user,
            title='주문 확인',
            message='주문이 확인되었습니다.',
            link='/portal/orders/1/',
        )
        self.assertFalse(notif.is_read)
        self.assertIn('주문 확인', str(notif))

    def test_read_notification(self):
        notif = PortalNotification.objects.create(
            portal_user=self.portal_user,
            title='배송 완료',
            message='배송이 완료되었습니다.',
        )
        notif.is_read = True
        notif.save()
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)


class PortalDocumentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='doc_user', password='testpass123')
        self.partner = Partner.objects.create(code='PTN-D01', name='문서고객', partner_type='CUSTOMER')
        self.portal_user = PortalUser.objects.create(
            user=self.user, partner=self.partner,
            portal_type=PortalUser.PortalType.CUSTOMER, is_verified=True,
        )

    def test_create_document(self):
        doc = PortalDocument.objects.create(
            portal_user=self.portal_user,
            document_type=PortalDocument.DocumentType.INVOICE,
            title='2026년 3월 세금계산서',
        )
        self.assertEqual(doc.document_type, 'INVOICE')
        self.assertIn('세금계산서', str(doc))


class PortalViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.partner = Partner.objects.create(
            code='PTN-V01', name='뷰테스트', partner_type='CUSTOMER',
        )
        self.user = User.objects.create_user(
            username='portal_view_user', password='testpass123',
        )
        self.portal_user = PortalUser.objects.create(
            user=self.user, partner=self.partner,
            portal_type=PortalUser.PortalType.CUSTOMER, is_verified=True,
        )
        self.manager = User.objects.create_user(
            username='portal_mgr', password='testpass123', role='manager',
        )

    def test_dashboard_requires_auth(self):
        resp = self.client.get(reverse('portal:dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_portal_user(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('portal:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_logout_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('portal:logout'))
        self.assertEqual(resp.status_code, 405)

    def test_logout_post(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('portal:logout'))
        self.assertEqual(resp.status_code, 302)

    def test_admin_user_list_requires_manager(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('portal:admin_user_list'))
        self.assertEqual(resp.status_code, 403)

    def test_admin_user_list_manager_ok(self):
        self.client.force_login(self.manager)
        resp = self.client.get(reverse('portal:admin_user_list'))
        self.assertEqual(resp.status_code, 200)
