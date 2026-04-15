from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.inventory.models import Product
from apps.plm.models import (
    BOMRevision,
    Drawing,
    EngineeringChangeNotice,
    ProductVersion,
)
from apps.production.models import BOM


class ProductVersionTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='테스트제품', code='PLM-001')

    def test_version_creation(self):
        ver = ProductVersion.objects.create(
            product=self.product, version_number='1.0', status='DRAFT',
        )
        self.assertEqual(str(ver), '[PLM-001] 테스트제품 v1.0')
        self.assertEqual(ver.status, 'DRAFT')

    def test_unique_version(self):
        ProductVersion.objects.create(
            product=self.product, version_number='1.0',
        )
        with self.assertRaises(Exception):
            ProductVersion.objects.create(
                product=self.product, version_number='1.0',
            )


class ECNTest(TestCase):
    def test_auto_number(self):
        ecn = EngineeringChangeNotice.objects.create(
            title='재질 변경', description='알루미늄 → 스테인리스',
        )
        self.assertTrue(ecn.ecn_number.startswith('ECN-'))

    def test_default_status(self):
        ecn = EngineeringChangeNotice.objects.create(
            title='테스트', description='테스트',
        )
        self.assertEqual(ecn.status, 'DRAFT')


class DrawingTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='테스트제품', code='DRW-001')

    def test_drawing_creation(self):
        drawing = Drawing.objects.create(
            product=self.product,
            drawing_number='DWG-2026-001',
            revision='A',
        )
        self.assertEqual(str(drawing), 'DWG-2026-001 Rev.A')


# ── Signal Tests ─────────────────────────────────────────────

class ECNApprovedBOMRevisionSignalTest(TestCase):
    """ECN APPROVED → BOMRevision 자동 생성"""

    def setUp(self):
        self.product = Product.objects.create(
            name='ECN테스트제품', code='ECN-T-001', product_type='FINISHED',
        )
        self.bom = BOM.objects.create(product=self.product, version='1.0')

    def test_ecn_approved_creates_bom_revision(self):
        ecn = EngineeringChangeNotice.objects.create(
            title='재질 변경', description='테스트', status='DRAFT',
        )
        ecn.affected_products.add(self.product)
        ecn.status = 'APPROVED'
        ecn.save()
        rev = BOMRevision.objects.filter(bom=self.bom, is_active=True).first()
        self.assertIsNotNone(rev)
        self.assertEqual(rev.revision_number, '1')
        self.assertIn('ECN', rev.change_reason)

    def test_ecn_draft_no_revision(self):
        ecn = EngineeringChangeNotice.objects.create(
            title='초안', description='테스트', status='DRAFT',
        )
        ecn.affected_products.add(self.product)
        rev_count = BOMRevision.objects.filter(bom=self.bom, is_active=True).count()
        self.assertEqual(rev_count, 0)


class ProductVersionActivateSignalTest(TestCase):
    """ProductVersion is_active=True → 같은 제품 다른 버전 비활성화"""

    def setUp(self):
        self.product = Product.objects.create(name='버전테스트', code='VER-T-001')

    def test_activate_deactivates_others(self):
        v1 = ProductVersion.objects.create(
            product=self.product, version_number='1.0',
        )
        v2 = ProductVersion.objects.create(
            product=self.product, version_number='2.0',
        )
        v1.refresh_from_db()
        self.assertFalse(v1.is_active)
        self.assertTrue(v2.is_active)

    def test_different_product_not_affected(self):
        product2 = Product.objects.create(name='다른제품', code='VER-T-002')
        v1 = ProductVersion.objects.create(
            product=self.product, version_number='1.0',
        )
        v2 = ProductVersion.objects.create(
            product=product2, version_number='1.0',
        )
        v1.refresh_from_db()
        self.assertTrue(v1.is_active)
        self.assertTrue(v2.is_active)


class DrawingRevisionAutoIncrementSignalTest(TestCase):
    """Drawing 파일 변경 시 revision 자동 증가"""

    def setUp(self):
        self.product = Product.objects.create(name='도면테스트', code='DRW-T-001')

    def test_file_change_increments_alpha_revision(self):
        drawing = Drawing.objects.create(
            product=self.product,
            drawing_number='DWG-SIG-001',
            revision='A',
            file=SimpleUploadedFile('test_v1.pdf', b'version1'),
        )
        self.assertEqual(drawing.revision, 'A')
        drawing.file = SimpleUploadedFile('test_v2.pdf', b'version2')
        drawing.save()
        drawing.refresh_from_db()
        self.assertEqual(drawing.revision, 'B')

    def test_file_change_increments_numeric_revision(self):
        drawing = Drawing.objects.create(
            product=self.product,
            drawing_number='DWG-SIG-002',
            revision='1',
            file=SimpleUploadedFile('num_v1.pdf', b'version1'),
        )
        drawing.file = SimpleUploadedFile('num_v2.pdf', b'version2')
        drawing.save()
        drawing.refresh_from_db()
        self.assertEqual(drawing.revision, '2')
