from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.document.models import (
    Contract, ContractMilestone, Document, DocumentApproval,
    DocumentCategory, DocumentVersion,
)

User = get_user_model()


class DocumentCategoryModelTest(TestCase):
    def test_create_category(self):
        cat = DocumentCategory.objects.create(
            name='법률문서', code='LEGAL', retention_years=10,
        )
        self.assertEqual(str(cat), '[LEGAL] 법률문서')
        self.assertEqual(cat.retention_years, 10)
        self.assertTrue(cat.is_active)

    def test_parent_category(self):
        parent = DocumentCategory.objects.create(name='계약', code='CONTRACT')
        child = DocumentCategory.objects.create(
            name='매입계약', code='CONTRACT-P', parent=parent,
        )
        self.assertEqual(child.parent, parent)


class DocumentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='docuser', password='testpass123', role='admin',
        )
        self.category = DocumentCategory.objects.create(
            name='일반', code='GEN',
        )

    def test_auto_number(self):
        doc = Document.objects.create(
            title='테스트 문서', category=self.category, owner=self.user,
        )
        self.assertTrue(doc.document_number.startswith('DOC-'))

    def test_default_status(self):
        doc = Document.objects.create(
            title='초안 문서', category=self.category, owner=self.user,
        )
        self.assertEqual(doc.status, Document.Status.DRAFT)

    def test_version_default(self):
        doc = Document.objects.create(
            title='버전 문서', category=self.category, owner=self.user,
        )
        self.assertEqual(doc.version, 1)


class DocumentVersionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='veruser', password='testpass123', role='admin',
        )
        cat = DocumentCategory.objects.create(name='일반', code='GEN')
        self.doc = Document.objects.create(title='버전 테스트', category=cat, owner=self.user)

    def test_create_version(self):
        ver = DocumentVersion.objects.create(
            document=self.doc, version_number=2,
            change_summary='수정본',
        )
        self.assertEqual(str(ver), '버전 테스트 v2')


class DocumentApprovalModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='apruser', password='testpass123', role='admin',
        )
        cat = DocumentCategory.objects.create(name='결재', code='APR')
        self.doc = Document.objects.create(title='결재 문서', category=cat, owner=self.user)

    def test_default_status(self):
        approval = DocumentApproval.objects.create(
            document=self.doc, approver=self.user,
        )
        self.assertEqual(approval.status, DocumentApproval.Status.PENDING)


class ContractModelTest(TestCase):
    def test_auto_number(self):
        contract = Contract.objects.create(
            title='테스트 계약',
            contract_type=Contract.ContractType.SALES,
            start_date=date.today(),
            value=Decimal('10000000'),
        )
        self.assertTrue(contract.contract_number.startswith('CT-'))

    def test_default_status(self):
        contract = Contract.objects.create(
            title='신규 계약',
            contract_type=Contract.ContractType.SERVICE,
            start_date=date.today(),
        )
        self.assertEqual(contract.status, Contract.Status.DRAFT)


class ContractMilestoneModelTest(TestCase):
    def test_create_milestone(self):
        contract = Contract.objects.create(
            title='마일스톤 계약',
            contract_type=Contract.ContractType.SERVICE,
            start_date=date.today(),
        )
        ms = ContractMilestone.objects.create(
            contract=contract,
            title='1차 납품',
            due_date=date.today() + timedelta(days=30),
            amount=Decimal('5000000'),
        )
        self.assertEqual(ms.status, ContractMilestone.Status.PENDING)
        self.assertIn('1차 납품', str(ms))


class DocumentViewAccessTest(TestCase):
    """문서 뷰 접근 권한 테스트 (비인증/비권한 거부 확인)"""

    def setUp(self):
        self.manager = User.objects.create_user(
            username='mgr_doc', password='testpass123', role='manager',
        )
        self.staff = User.objects.create_user(
            username='staff_doc', password='testpass123', role='staff',
        )

    def test_document_list_requires_login(self):
        resp = self.client.get('/document/documents/')
        self.assertEqual(resp.status_code, 302)

    def test_contract_create_requires_manager(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/document/contracts/create/')
        self.assertIn(resp.status_code, [302, 403])

    def test_dashboard_requires_login(self):
        resp = self.client.get('/document/')
        self.assertEqual(resp.status_code, 302)


class DocumentApprovalOrderTest(TestCase):
    """문서 결재 순서 검증 테스트"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='approver1', password='testpass123', role='manager',
        )
        self.user2 = User.objects.create_user(
            username='approver2', password='testpass123', role='manager',
        )
        cat = DocumentCategory.objects.create(name='결재테스트', code='APR-T')
        self.doc = Document.objects.create(
            title='다단계 결재 문서', category=cat, owner=self.user1,
            status=Document.Status.REVIEW,
        )
        self.approval1 = DocumentApproval.objects.create(
            document=self.doc, approver=self.user1,
        )
        self.approval2 = DocumentApproval.objects.create(
            document=self.doc, approver=self.user2,
        )

    def test_cannot_approve_before_prior_step(self):
        self.client.force_login(self.user2)
        resp = self.client.post(
            f'/document/approvals/{self.approval2.pk}/approve/',
            {'comment': '승인'},
        )
        self.approval2.refresh_from_db()
        self.assertEqual(self.approval2.status, DocumentApproval.Status.PENDING)
