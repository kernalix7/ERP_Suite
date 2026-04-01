from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from apps.accounting.models import AccountCode, Voucher, VoucherLine
from apps.asset.models import AssetCategory, DepreciationRecord, FixedAsset


class AssetCategoryTest(TestCase):
    """자산분류 모델 테스트"""

    def test_category_creation(self):
        """AssetCategory 생성 가능"""
        cat = AssetCategory.objects.create(
            name='비품',
            code='EQ',
            useful_life_years=5,
            depreciation_method='STRAIGHT',
        )
        self.assertEqual(cat.name, '비품')
        self.assertEqual(cat.code, 'EQ')
        self.assertEqual(cat.useful_life_years, 5)
        self.assertEqual(cat.depreciation_method, 'STRAIGHT')
        self.assertEqual(str(cat), '[EQ] 비품')


class FixedAssetTest(TestCase):
    """고정자산 모델 테스트"""

    def setUp(self):
        self.category = AssetCategory.objects.create(
            name='차량운반구',
            code='VH',
            useful_life_years=5,
            depreciation_method='STRAIGHT',
        )

    def test_asset_creation(self):
        """FixedAsset 생성 가능"""
        asset = FixedAsset.objects.create(
            asset_number='FA-001',
            name='업무용 승용차',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('30000000'),
            residual_value=Decimal('3000000'),
            useful_life_years=5,
            depreciation_method='STRAIGHT',
        )
        self.assertEqual(asset.asset_number, 'FA-001')
        self.assertEqual(asset.name, '업무용 승용차')
        self.assertEqual(asset.category, self.category)
        self.assertEqual(str(asset), '[FA-001] 업무용 승용차')

    def test_book_value_on_save(self):
        """save() 시 book_value = acquisition_cost - accumulated_depreciation"""
        asset = FixedAsset.objects.create(
            asset_number='FA-002',
            name='사무용 노트북',
            category=self.category,
            acquisition_date=date(2025, 1, 1),
            acquisition_cost=Decimal('2000000'),
            residual_value=Decimal('200000'),
            useful_life_years=4,
            accumulated_depreciation=Decimal('500000'),
        )
        self.assertEqual(
            asset.book_value,
            Decimal('2000000') - Decimal('500000'),
        )
        self.assertEqual(asset.book_value, Decimal('1500000'))

    def test_monthly_depreciation_straight_line(self):
        """정액법 월 감가상각비 계산"""
        asset = FixedAsset.objects.create(
            asset_number='FA-003',
            name='프린터',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('1200000'),
            residual_value=Decimal('0'),
            useful_life_years=5,
            depreciation_method='STRAIGHT',
        )
        # 정액법: (취득원가 - 잔존가치) / (내용연수 * 12)
        # (1200000 - 0) / (5 * 12) = 1200000 / 60 = 20000
        expected = int((Decimal('1200000') - Decimal('0')) / (5 * 12))
        self.assertEqual(asset.monthly_depreciation, expected)
        self.assertEqual(asset.monthly_depreciation, 20000)


class DepreciationRecordTest(TestCase):
    """감가상각 내역 모델 테스트"""

    def setUp(self):
        self.category = AssetCategory.objects.create(
            name='비품', code='EQ-DEP',
            useful_life_years=5,
        )
        self.asset = FixedAsset.objects.create(
            asset_number='FA-DEP-001',
            name='사무용 데스크',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('600000'),
            residual_value=Decimal('0'),
            useful_life_years=5,
        )

    def test_depreciation_record_creation(self):
        """DepreciationRecord 생성 가능"""
        record = DepreciationRecord.objects.create(
            asset=self.asset,
            year=2026,
            month=1,
            depreciation_amount=Decimal('10000'),
            accumulated_amount=Decimal('10000'),
            book_value_after=Decimal('590000'),
        )
        self.assertEqual(record.asset, self.asset)
        self.assertEqual(record.depreciation_amount, Decimal('10000'))
        self.assertEqual(str(record), 'FA-DEP-001 - 2026/1')

    def test_unique_asset_period(self):
        """동일 자산/년/월 중복 불가"""
        DepreciationRecord.objects.create(
            asset=self.asset,
            year=2026,
            month=3,
            depreciation_amount=Decimal('10000'),
            accumulated_amount=Decimal('30000'),
            book_value_after=Decimal('570000'),
        )
        with self.assertRaises(IntegrityError):
            DepreciationRecord.objects.create(
                asset=self.asset,
                year=2026,
                month=3,
                depreciation_amount=Decimal('10000'),
                accumulated_amount=Decimal('40000'),
                book_value_after=Decimal('560000'),
            )


class DepreciationSignalTest(TestCase):
    """감가상각 시그널 테스트"""

    def setUp(self):
        self.category = AssetCategory.objects.create(
            name='비품', code='EQ-SIG',
            useful_life_years=5,
        )
        self.asset = FixedAsset.objects.create(
            asset_number='FA-SIG-001',
            name='테스트 자산',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('1200000'),
            residual_value=Decimal('0'),
            useful_life_years=5,
        )
        # 시그널 테스트용 계정과목
        self.acct_820 = AccountCode.objects.create(
            code='820', name='감가상각비',
            account_type='EXPENSE',
        )
        self.acct_159 = AccountCode.objects.create(
            code='159', name='감가상각누계액',
            account_type='ASSET',
        )

    def test_depreciation_updates_asset_atomically(self):
        """DepreciationRecord 생성 → FixedAsset F() 원자적 갱신"""
        DepreciationRecord.objects.create(
            asset=self.asset,
            year=2026, month=1,
            depreciation_amount=Decimal('20000'),
            accumulated_amount=Decimal('20000'),
            book_value_after=Decimal('1180000'),
        )
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.accumulated_depreciation, Decimal('20000'))
        self.assertEqual(self.asset.book_value, Decimal('1180000'))

    def test_depreciation_creates_voucher(self):
        """DepreciationRecord 생성 → 자동전표(차변:감가상각비, 대변:누계액)"""
        before_count = Voucher.objects.count()
        DepreciationRecord.objects.create(
            asset=self.asset,
            year=2026, month=2,
            depreciation_amount=Decimal('20000'),
            accumulated_amount=Decimal('20000'),
            book_value_after=Decimal('1180000'),
        )
        self.assertEqual(Voucher.objects.count(), before_count + 1)
        voucher = Voucher.objects.latest('pk')
        self.assertIn('감가상각', voucher.description)
        lines = voucher.lines.all()
        self.assertEqual(lines.count(), 2)
        debit_line = lines.get(debit__gt=0)
        credit_line = lines.get(credit__gt=0)
        self.assertEqual(debit_line.account, self.acct_820)
        self.assertEqual(debit_line.debit, Decimal('20000'))
        self.assertEqual(credit_line.account, self.acct_159)
        self.assertEqual(credit_line.credit, Decimal('20000'))

    def test_depreciation_no_voucher_without_accounts(self):
        """계정과목 없으면 전표 미생성 (에러 없이 진행)"""
        self.acct_820.delete()
        before_count = Voucher.objects.count()
        DepreciationRecord.objects.create(
            asset=self.asset,
            year=2026, month=3,
            depreciation_amount=Decimal('20000'),
            accumulated_amount=Decimal('20000'),
            book_value_after=Decimal('1180000'),
        )
        # 전표는 생성되지 않지만, 자산 갱신은 여전히 수행됨
        self.assertEqual(Voucher.objects.count(), before_count)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.accumulated_depreciation, Decimal('20000'))

    def test_consecutive_depreciation(self):
        """연속 감가상각 → 누적 반영"""
        DepreciationRecord.objects.create(
            asset=self.asset,
            year=2026, month=1,
            depreciation_amount=Decimal('20000'),
            accumulated_amount=Decimal('20000'),
            book_value_after=Decimal('1180000'),
        )
        DepreciationRecord.objects.create(
            asset=self.asset,
            year=2026, month=2,
            depreciation_amount=Decimal('20000'),
            accumulated_amount=Decimal('40000'),
            book_value_after=Decimal('1160000'),
        )
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.accumulated_depreciation, Decimal('40000'))
        self.assertEqual(self.asset.book_value, Decimal('1160000'))


class AssetDisposalSignalTest(TestCase):
    """자산 처분 시그널 테스트"""

    def setUp(self):
        self.category = AssetCategory.objects.create(
            name='비품', code='EQ-DISP',
            useful_life_years=5,
        )
        self.asset = FixedAsset.objects.create(
            asset_number='FA-DISP-001',
            name='처분 테스트 자산',
            category=self.category,
            acquisition_date=date(2024, 1, 1),
            acquisition_cost=Decimal('1000000'),
            residual_value=Decimal('100000'),
            useful_life_years=5,
            accumulated_depreciation=Decimal('600000'),
        )
        # 계정과목 생성
        AccountCode.objects.create(code='159', name='감가상각누계액', account_type='ASSET')
        AccountCode.objects.create(code='150', name='유형자산', account_type='ASSET')
        AccountCode.objects.create(code='101', name='보통예금', account_type='ASSET')
        AccountCode.objects.create(code='901', name='유형자산처분이익', account_type='REVENUE')
        AccountCode.objects.create(code='951', name='유형자산처분손실', account_type='EXPENSE')

    def test_disposal_with_gain(self):
        """처분이익 발생 시 전표 자동 생성"""
        before_count = Voucher.objects.count()
        # book_value = 1000000 - 600000 = 400000, disposal = 500000 → 이익 100000
        self.asset.status = FixedAsset.Status.DISPOSED
        self.asset.disposal_date = date(2026, 3, 1)
        self.asset.disposal_amount = Decimal('500000')
        self.asset.disposal_reason = '교체'
        self.asset.save()

        self.assertEqual(Voucher.objects.count(), before_count + 1)
        voucher = Voucher.objects.latest('pk')
        self.assertIn('처분', voucher.description)
        # 차변합 = 대변합 (복식부기)
        self.assertTrue(voucher.is_balanced)

    def test_disposal_with_loss(self):
        """처분손실 발생 시 전표 자동 생성"""
        before_count = Voucher.objects.count()
        # book_value = 400000, disposal = 200000 → 손실 200000
        self.asset.status = FixedAsset.Status.DISPOSED
        self.asset.disposal_date = date(2026, 3, 1)
        self.asset.disposal_amount = Decimal('200000')
        self.asset.save()

        self.assertEqual(Voucher.objects.count(), before_count + 1)
        voucher = Voucher.objects.latest('pk')
        self.assertTrue(voucher.is_balanced)

    def test_scrap_zero_disposal(self):
        """폐기(처분금액 0) 시 전표 생성"""
        before_count = Voucher.objects.count()
        self.asset.status = FixedAsset.Status.SCRAPPED
        self.asset.disposal_date = date(2026, 3, 1)
        self.asset.disposal_amount = Decimal('0')
        self.asset.save()

        self.assertEqual(Voucher.objects.count(), before_count + 1)
        voucher = Voucher.objects.latest('pk')
        self.assertTrue(voucher.is_balanced)

    def test_no_voucher_on_status_unchanged(self):
        """상태 변경 없으면 전표 미생성"""
        before_count = Voucher.objects.count()
        self.asset.name = '이름 변경만'
        self.asset.save()
        self.assertEqual(Voucher.objects.count(), before_count)
