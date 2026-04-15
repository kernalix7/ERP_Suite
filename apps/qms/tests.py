from datetime import date
from unittest.mock import patch

from django.test import TestCase

from apps.inventory.models import Product
from apps.production.models import QualityInspection
from apps.qms.models import AuditFinding, CAPA, InternalAudit, ISODocument, NonConformance


class NonConformanceTest(TestCase):
    def test_auto_number(self):
        nc = NonConformance.objects.create(
            title='치수 불량', description='가공품 치수 초과',
        )
        self.assertTrue(nc.nc_number.startswith('NC-'))

    def test_default_status(self):
        nc = NonConformance.objects.create(
            title='테스트', description='테스트',
        )
        self.assertEqual(nc.status, 'OPEN')
        self.assertEqual(nc.source, 'INTERNAL')
        self.assertEqual(nc.severity, 'MINOR')


class CAPATest(TestCase):
    def test_auto_number(self):
        capa = CAPA.objects.create(
            type='CORRECTIVE', description='금형 교체',
        )
        self.assertTrue(capa.capa_number.startswith('CAPA-'))

    def test_with_nc(self):
        nc = NonConformance.objects.create(
            title='치수 불량', description='테스트',
        )
        capa = CAPA.objects.create(
            nc=nc, type='CORRECTIVE', description='금형 교체',
        )
        self.assertEqual(capa.nc, nc)


class InternalAuditTest(TestCase):
    def test_auto_number(self):
        audit = InternalAudit.objects.create(
            title='공정감사', audit_type='PROCESS',
        )
        self.assertTrue(audit.audit_number.startswith('AUD-'))

    def test_default_status(self):
        audit = InternalAudit.objects.create(
            title='시스템감사', audit_type='SYSTEM',
        )
        self.assertEqual(audit.status, 'PLANNED')


class ISODocumentTest(TestCase):
    def test_doc_creation(self):
        doc = ISODocument.objects.create(
            document_number='QMS-P-001',
            title='품질매뉴얼',
            category='절차서',
        )
        self.assertEqual(str(doc), '[QMS-P-001] 품질매뉴얼')
        self.assertEqual(doc.status, 'DRAFT')

    def test_unique_number(self):
        ISODocument.objects.create(
            document_number='QMS-P-002', title='테스트',
        )
        with self.assertRaises(Exception):
            ISODocument.objects.create(
                document_number='QMS-P-002', title='중복',
            )


# ── Signal Tests ─────────────────────────────────────────────

class InspectionFailSignalTest(TestCase):
    """검수 FAIL → NonConformance 자동 생성"""

    def setUp(self):
        self.product = Product.objects.create(name='QMS테스트제품', code='QMS-T-001')

    def test_fail_creates_nc(self):
        qi = QualityInspection.objects.create(
            inspection_type='PRODUCTION',
            product=self.product,
            inspected_quantity=100,
            pass_quantity=80,
            fail_quantity=20,
            inspection_date=date.today(),
            result='FAIL',
            defect_description='표면 흠집',
        )
        nc = NonConformance.objects.filter(notes=f'QI-{qi.pk}', is_active=True).first()
        self.assertIsNotNone(nc)
        self.assertEqual(nc.severity, 'MAJOR')
        self.assertEqual(nc.product, self.product)
        self.assertIn('표면 흠집', nc.description)

    def test_fail_no_duplicate_nc(self):
        qi = QualityInspection.objects.create(
            inspection_type='PRODUCTION',
            product=self.product,
            inspected_quantity=100,
            fail_quantity=20,
            inspection_date=date.today(),
            result='FAIL',
        )
        # save again — should not create duplicate
        qi.save()
        nc_count = NonConformance.objects.filter(
            notes=f'QI-{qi.pk}', is_active=True,
        ).count()
        self.assertEqual(nc_count, 1)


class InspectionConditionalSignalTest(TestCase):
    """검수 CONDITIONAL → Manager 알림"""

    def setUp(self):
        self.product = Product.objects.create(name='QMS테스트제품2', code='QMS-T-002')

    @patch('apps.qms.signals.create_notification')
    def test_conditional_sends_notification(self, mock_notify):
        QualityInspection.objects.create(
            inspection_type='INCOMING',
            product=self.product,
            inspected_quantity=50,
            inspection_date=date.today(),
            result='CONDITIONAL',
            conditional_notes='경미한 스크래치',
        )
        mock_notify.assert_called_once()
        args = mock_notify.call_args
        self.assertEqual(args[0][0], 'manager')
        self.assertIn('조건부합격', args[0][1])


class NCOpenCreateCAPASignalTest(TestCase):
    """부적합 OPEN → CAPA 자동 생성"""

    def test_nc_open_creates_capa(self):
        nc = NonConformance.objects.create(
            title='원자재 불량', description='입고 원자재 규격 초과',
            status='OPEN',
        )
        capa = CAPA.objects.filter(nc=nc, is_active=True).first()
        self.assertIsNotNone(capa)
        self.assertEqual(capa.type, 'CORRECTIVE')
        self.assertEqual(capa.status, 'OPEN')

    def test_nc_non_open_no_capa(self):
        nc = NonConformance.objects.create(
            title='이미 해결', description='테스트',
            status='RESOLVED',
        )
        capa_count = CAPA.objects.filter(nc=nc, is_active=True).count()
        self.assertEqual(capa_count, 0)


class CAPAClosedResolveNCSignalTest(TestCase):
    """CAPA CLOSED → NonConformance RESOLVED"""

    def test_capa_closed_resolves_nc(self):
        nc = NonConformance.objects.create(
            title='부적합', description='테스트', status='OPEN',
        )
        capa = CAPA.objects.filter(nc=nc, is_active=True).first()
        self.assertIsNotNone(capa)
        capa.status = 'CLOSED'
        capa.save()
        nc.refresh_from_db()
        self.assertEqual(nc.status, 'RESOLVED')

    def test_capa_in_progress_does_not_resolve_nc(self):
        nc = NonConformance.objects.create(
            title='부적합2', description='테스트', status='OPEN',
        )
        capa = CAPA.objects.filter(nc=nc, is_active=True).first()
        capa.status = 'IN_PROGRESS'
        capa.save()
        nc.refresh_from_db()
        self.assertEqual(nc.status, 'OPEN')


class AuditFindingNCRSignalTest(TestCase):
    """감사 발견사항 부적합 → NCR 자동 생성"""

    def setUp(self):
        self.audit = InternalAudit.objects.create(
            title='공정감사 Q2', audit_type='PROCESS',
        )

    def test_major_nc_creates_ncr_and_capa(self):
        """MAJOR_NC 발견사항 → NCR(MAJOR) + CAPA 자동 생성"""
        finding = AuditFinding.objects.create(
            audit=self.audit,
            finding_type='MAJOR_NC',
            description='중대 부적합 발견: 절차 미준수',
        )
        ncr = NonConformance.objects.filter(
            title__startswith='감사 부적합',
            is_active=True,
        ).first()
        self.assertIsNotNone(ncr)
        self.assertEqual(ncr.severity, 'MAJOR')
        self.assertEqual(ncr.source, 'INTERNAL')
        # CAPA도 자동 생성 확인
        capa = ncr.capas.filter(is_active=True).first()
        self.assertIsNotNone(capa)
        # AuditFinding.capa에 연결 확인
        finding.refresh_from_db()
        self.assertEqual(finding.capa, capa)

    def test_minor_nc_creates_ncr_minor(self):
        """MINOR_NC 발견사항 → NCR(MINOR) 자동 생성"""
        AuditFinding.objects.create(
            audit=self.audit,
            finding_type='MINOR_NC',
            description='경미 부적합: 문서 불비',
        )
        ncr = NonConformance.objects.filter(
            severity='MINOR',
            title__startswith='감사 부적합',
        ).first()
        self.assertIsNotNone(ncr)

    def test_observation_no_ncr(self):
        """OBSERVATION → NCR 미생성"""
        AuditFinding.objects.create(
            audit=self.audit,
            finding_type='OBSERVATION',
            description='관찰사항',
        )
        count = NonConformance.objects.filter(
            title__startswith='감사 부적합',
        ).count()
        self.assertEqual(count, 0)
