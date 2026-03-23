from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

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
