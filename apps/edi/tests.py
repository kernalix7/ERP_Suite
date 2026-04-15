from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User
from apps.sales.models import Partner

from .models import (
    EDIDocumentType,
    EDIMapping,
    EDIPartner,
    EDISchedule,
    EDITransaction,
)


class EDIPartnerTests(TestCase):
    def setUp(self):
        self.partner = Partner.objects.create(
            code='PTN-EDI01', name='EDI 거래처', partner_type='SUPPLIER',
        )

    def test_create_edi_partner(self):
        ep = EDIPartner.objects.create(
            partner=self.partner,
            edi_id='EDI-001',
            protocol=EDIPartner.Protocol.SFTP,
            connection_settings={'host': '192.168.1.1', 'port': 22},
        )
        self.assertEqual(ep.protocol, 'SFTP')
        self.assertIn('EDI-001', str(ep))

    def test_soft_delete(self):
        ep = EDIPartner.objects.create(
            partner=self.partner, edi_id='EDI-DEL',
            protocol=EDIPartner.Protocol.API,
        )
        ep.soft_delete()
        self.assertFalse(EDIPartner.objects.filter(edi_id='EDI-DEL').exists())


class EDIDocumentTypeTests(TestCase):
    def test_create_doc_type(self):
        dt = EDIDocumentType.objects.create(
            code='PO850',
            name='발주서',
            direction=EDIDocumentType.Direction.OUTBOUND,
            format=EDIDocumentType.Format.XML,
        )
        self.assertEqual(str(dt), 'PO850 - 발주서')

    def test_inbound_type(self):
        dt = EDIDocumentType.objects.create(
            code='INV810',
            name='인보이스',
            direction=EDIDocumentType.Direction.INBOUND,
            format=EDIDocumentType.Format.JSON,
        )
        self.assertEqual(dt.direction, 'INBOUND')


class EDITransactionTests(TestCase):
    def setUp(self):
        self.partner = Partner.objects.create(
            code='PTN-EDITX', name='TX 거래처', partner_type='SUPPLIER',
        )
        self.edi_partner = EDIPartner.objects.create(
            partner=self.partner, edi_id='EDI-TX01',
            protocol=EDIPartner.Protocol.API,
        )
        self.doc_type = EDIDocumentType.objects.create(
            code='ORD850', name='주문서',
            direction=EDIDocumentType.Direction.OUTBOUND,
            format=EDIDocumentType.Format.XML,
        )

    def test_create_transaction_auto_id(self):
        tx = EDITransaction.objects.create(
            partner=self.edi_partner,
            document_type=self.doc_type,
            direction=EDITransaction.Direction.OUTBOUND,
            payload='<order>test</order>',
        )
        self.assertTrue(tx.transaction_id.startswith('EDI-'))
        self.assertEqual(tx.status, EDITransaction.Status.PENDING)

    def test_status_flow(self):
        tx = EDITransaction.objects.create(
            partner=self.edi_partner,
            document_type=self.doc_type,
            direction=EDITransaction.Direction.OUTBOUND,
        )
        tx.status = EDITransaction.Status.SENT
        tx.save()
        tx.refresh_from_db()
        self.assertEqual(tx.status, EDITransaction.Status.SENT)

        tx.status = EDITransaction.Status.PROCESSED
        tx.save()
        tx.refresh_from_db()
        self.assertEqual(tx.status, EDITransaction.Status.PROCESSED)

    def test_error_and_retry(self):
        tx = EDITransaction.objects.create(
            partner=self.edi_partner,
            document_type=self.doc_type,
            direction=EDITransaction.Direction.OUTBOUND,
            status=EDITransaction.Status.ERROR,
            error_message='Connection timeout',
        )
        self.assertEqual(tx.status, 'ERROR')
        tx.status = EDITransaction.Status.PENDING
        tx.error_message = ''
        tx.save()
        tx.refresh_from_db()
        self.assertEqual(tx.status, 'PENDING')
        self.assertEqual(tx.error_message, '')

    def test_soft_delete(self):
        tx = EDITransaction.objects.create(
            partner=self.edi_partner,
            document_type=self.doc_type,
            direction=EDITransaction.Direction.INBOUND,
        )
        tx.soft_delete()
        self.assertFalse(EDITransaction.objects.filter(pk=tx.pk).exists())
        self.assertTrue(EDITransaction.all_objects.filter(pk=tx.pk).exists())


class EDIMappingTests(TestCase):
    def test_create_mapping(self):
        dt = EDIDocumentType.objects.create(
            code='MAP01', name='매핑테스트',
            direction=EDIDocumentType.Direction.INBOUND,
            format=EDIDocumentType.Format.CSV,
        )
        mapping = EDIMapping.objects.create(
            document_type=dt,
            source_field='order_id',
            target_model='sales.Order',
            target_field='order_number',
            transformation='strip',
        )
        self.assertIn('->', str(mapping))


class EDIScheduleTests(TestCase):
    def test_create_schedule(self):
        partner = Partner.objects.create(
            code='PTN-SCH01', name='스케줄 거래처', partner_type='SUPPLIER',
        )
        edi_partner = EDIPartner.objects.create(
            partner=partner, edi_id='EDI-SCH01',
            protocol=EDIPartner.Protocol.FTP,
        )
        dt = EDIDocumentType.objects.create(
            code='SCH01', name='스케줄 문서',
            direction=EDIDocumentType.Direction.INBOUND,
            format=EDIDocumentType.Format.EDIFACT,
        )
        schedule = EDISchedule.objects.create(
            partner=edi_partner,
            document_type=dt,
            frequency=EDISchedule.Frequency.DAILY,
        )
        self.assertEqual(schedule.frequency, 'DAILY')
        self.assertIn('매일', str(schedule))


class EDIViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='edi_staff', password='testpass123', role='staff',
        )
        self.manager = User.objects.create_user(
            username='edi_manager', password='testpass123', role='manager',
        )

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('edi:dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_authenticated(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('edi:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_transaction_list_requires_login(self):
        resp = self.client.get(reverse('edi:transaction_list'))
        self.assertEqual(resp.status_code, 302)

    def test_transaction_list_authenticated(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('edi:transaction_list'))
        self.assertEqual(resp.status_code, 200)
