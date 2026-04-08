from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from apps.accounting.models import AccountCode, Voucher, VoucherLine
from apps.asset.models import (
    AssetAudit, AssetAuditItem, AssetCategory, AssetTransfer,
    Certification, DepreciationRecord, FixedAsset, LeaseContract, Location,
)


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


class AssetTransferSignalTest(TestCase):
    """자산 이관 시그널 테스트"""

    def setUp(self):
        from apps.hr.models import Department
        self.category = AssetCategory.objects.create(
            name='비품', code='EQ-TR', useful_life_years=5,
        )
        self.dept_a = Department.objects.create(name='영업부', code='SALES')
        self.dept_b = Department.objects.create(name='개발부', code='DEV')
        self.asset = FixedAsset.objects.create(
            asset_number='FA-TR-001',
            name='이관 테스트 자산',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('1000000'),
            useful_life_years=5,
            department=self.dept_a,
            location='본사 3층',
        )

    def test_transfer_updates_asset_department(self):
        """AssetTransfer 생성 → FixedAsset 부서/위치 자동 갱신"""
        AssetTransfer.objects.create(
            asset=self.asset,
            transfer_date=date(2026, 4, 1),
            from_department=self.dept_a,
            to_department=self.dept_b,
            from_location='본사 3층',
            to_location='본사 5층',
            reason='조직 개편',
        )
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.department, self.dept_b)
        self.assertEqual(self.asset.location, '본사 5층')

    def test_transfer_str(self):
        """AssetTransfer 문자열 표현"""
        transfer = AssetTransfer.objects.create(
            asset=self.asset,
            transfer_date=date(2026, 4, 1),
            from_department=self.dept_a,
            to_department=self.dept_b,
        )
        self.assertIn('FA-TR-001', str(transfer))
        self.assertIn('이관', str(transfer))

    def test_multiple_transfers_track_history(self):
        """연속 이관 → 최종 부서 반영"""
        from apps.hr.models import Department
        dept_c = Department.objects.create(name='경영지원부', code='ADMIN')

        AssetTransfer.objects.create(
            asset=self.asset,
            transfer_date=date(2026, 3, 1),
            from_department=self.dept_a,
            to_department=self.dept_b,
            to_location='본사 5층',
        )
        AssetTransfer.objects.create(
            asset=self.asset,
            transfer_date=date(2026, 6, 1),
            from_department=self.dept_b,
            to_department=dept_c,
            to_location='별관 2층',
        )
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.department, dept_c)
        self.assertEqual(self.asset.location, '별관 2층')
        self.assertEqual(self.asset.transfers.count(), 2)


class CertificationTest(TestCase):
    """인증 모델 + 자본화 시그널 테스트"""

    def setUp(self):
        self.category = AssetCategory.objects.create(
            name='비품', code='EQ-CERT', useful_life_years=5,
        )
        self.asset = FixedAsset.objects.create(
            asset_number='FA-CERT-001',
            name='계측 장비',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('5000000'),
            useful_life_years=5,
        )
        # 자본화 전표용 계정과목
        AccountCode.objects.create(code='160', name='무형자산', account_type='ASSET')
        AccountCode.objects.create(code='101', name='보통예금', account_type='ASSET')

    def test_certification_creation(self):
        """Certification 생성 가능"""
        cert = Certification.objects.create(
            cert_type='KC',
            cert_name='KC인증 취득',
            issuer='한국인증원',
            issue_date=date(2026, 3, 1),
            expiry_date=date(2027, 2, 28),
            cost=Decimal('300000'),
        )
        self.assertEqual(cert.cert_type, 'KC')
        self.assertIn('KC인증', str(cert))

    def test_capitalize_creates_intangible_asset(self):
        """is_capitalized=True, asset 없음 → FixedAsset(INTANGIBLE) 자동 생성"""
        before_asset_count = FixedAsset.objects.count()
        cert = Certification.objects.create(
            cert_type='ISO',
            cert_name='ISO 9001 인증',
            issuer='국제인증기관',
            issue_date=date(2026, 1, 1),
            expiry_date=date(2029, 1, 1),
            cost=Decimal('5000000'),
            is_capitalized=True,
        )
        self.assertEqual(FixedAsset.objects.count(), before_asset_count + 1)
        cert.refresh_from_db()
        self.assertIsNotNone(cert.asset)
        self.assertEqual(cert.asset.asset_type, FixedAsset.AssetType.INTANGIBLE)
        self.assertEqual(cert.asset.acquisition_cost, Decimal('5000000'))
        self.assertEqual(cert.asset.useful_life_years, 3)  # ~1095 days // 365

    def test_capitalize_creates_voucher(self):
        """is_capitalized=True → 전표 생성 (차변:무형자산160, 대변:현금101)"""
        before_count = Voucher.objects.count()
        Certification.objects.create(
            cert_type='CE',
            cert_name='CE 마킹',
            issue_date=date(2026, 6, 1),
            expiry_date=date(2028, 6, 1),
            cost=Decimal('2000000'),
            is_capitalized=True,
        )
        self.assertEqual(Voucher.objects.count(), before_count + 1)
        voucher = Voucher.objects.latest('pk')
        self.assertIn('자본화', voucher.description)
        self.assertTrue(voucher.is_balanced)

    def test_no_capitalize_no_asset_created(self):
        """is_capitalized=False → 무형자산 생성 안 함"""
        before_count = FixedAsset.objects.count()
        Certification.objects.create(
            cert_type='KC',
            cert_name='KC인증',
            issue_date=date(2026, 6, 1),
            cost=Decimal('100000'),
            is_capitalized=False,
        )
        self.assertEqual(FixedAsset.objects.count(), before_count)

    def test_capitalize_with_existing_asset_no_creation(self):
        """is_capitalized=True지만 asset이 이미 있으면 새로 만들지 않음"""
        before_count = FixedAsset.objects.count()
        Certification.objects.create(
            cert_type='ISO',
            cert_name='ISO 연결',
            asset=self.asset,
            issue_date=date(2026, 6, 1),
            cost=Decimal('500000'),
            is_capitalized=True,
        )
        self.assertEqual(FixedAsset.objects.count(), before_count)


class LeaseContractTest(TestCase):
    """리스 계약 모델 테스트"""

    def setUp(self):
        self.category = AssetCategory.objects.create(
            name='차량', code='VH-LS', useful_life_years=5,
        )
        self.asset = FixedAsset.objects.create(
            asset_number='FA-LS-001',
            name='업무용 승용차',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('30000000'),
            useful_life_years=5,
        )

    def test_lease_creation(self):
        """LeaseContract 생성 + 자동 계약번호"""
        contract = LeaseContract.objects.create(
            asset=self.asset,
            lease_type='OPERATING',
            start_date=date(2026, 1, 1),
            end_date=date(2028, 12, 31),
            monthly_payment=Decimal('500000'),
            deposit=Decimal('5000000'),
        )
        self.assertTrue(contract.contract_number.startswith('LS'))
        self.assertEqual(str(contract), f'[{contract.contract_number}] 업무용 승용차')

    def test_total_amount_auto_calculated(self):
        """total_amount = monthly_payment x 개월수 자동 계산"""
        contract = LeaseContract.objects.create(
            asset=self.asset,
            lease_type='FINANCE',
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            monthly_payment=Decimal('500000'),
        )
        # 12개월 (2026-01 ~ 2027-01)
        self.assertEqual(contract.total_amount, Decimal('6000000'))

    def test_remaining_months_expired(self):
        """만료된 계약 → remaining_months = 0"""
        contract = LeaseContract.objects.create(
            asset=self.asset,
            lease_type='OPERATING',
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
            monthly_payment=Decimal('100000'),
        )
        self.assertEqual(contract.remaining_months, 0)


class AssetAuditTest(TestCase):
    """자산 실사 모델 테스트"""

    def setUp(self):
        from apps.hr.models import Department
        from apps.accounts.models import User
        self.category = AssetCategory.objects.create(
            name='비품', code='EQ-AUD', useful_life_years=5,
        )
        self.dept = Department.objects.create(name='영업부', code='SALES-AUD')
        self.auditor = User.objects.create_user(
            username='auditor1', password='test1234',
        )
        self.asset1 = FixedAsset.objects.create(
            asset_number='FA-AUD-001',
            name='실사 자산 1',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('1000000'),
            useful_life_years=5,
            department=self.dept,
        )
        self.asset2 = FixedAsset.objects.create(
            asset_number='FA-AUD-002',
            name='실사 자산 2',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('2000000'),
            useful_life_years=5,
            department=self.dept,
        )

    def test_audit_creation(self):
        """AssetAudit 생성 가능"""
        audit = AssetAudit.objects.create(
            audit_date=date(2026, 3, 31),
            auditor=self.auditor,
            department=self.dept,
        )
        self.assertEqual(str(audit), '실사 2026-03-31 (영업부)')

    def test_audit_item_creation(self):
        """AssetAuditItem 생성 가능"""
        audit = AssetAudit.objects.create(
            audit_date=date(2026, 3, 31),
            auditor=self.auditor,
        )
        item = AssetAuditItem.objects.create(
            audit=audit,
            asset=self.asset1,
            status='FOUND',
            actual_location='본사 3층',
            condition='GOOD',
        )
        self.assertEqual(item.status, 'FOUND')
        self.assertIn('FA-AUD-001', str(item))

    def test_audit_item_unique_constraint(self):
        """동일 실사에서 같은 자산 중복 불가"""
        audit = AssetAudit.objects.create(
            audit_date=date(2026, 3, 31),
            auditor=self.auditor,
        )
        AssetAuditItem.objects.create(audit=audit, asset=self.asset1)
        with self.assertRaises(IntegrityError):
            AssetAuditItem.objects.create(audit=audit, asset=self.asset1)

    def test_audit_item_status_choices(self):
        """실사상태 4가지 + 상태 4가지"""
        audit = AssetAudit.objects.create(
            audit_date=date(2026, 4, 1),
            auditor=self.auditor,
        )
        for status_val in ['FOUND', 'MISSING', 'DAMAGED', 'LOCATION_MISMATCH']:
            item = AssetAuditItem(
                audit=audit,
                asset=self.asset1 if status_val == 'FOUND' else self.asset2,
                status=status_val,
            )
            item.full_clean()  # should not raise


class LocationTest(TestCase):
    """자산 위치 모델 테스트"""

    def test_location_creation(self):
        """Location 생성 가능"""
        loc = Location.objects.create(
            name='본사 3층 개발실',
            code='HQ-3F-DEV',
            building='본사',
            floor='3',
            room='개발실',
        )
        self.assertEqual(loc.name, '본사 3층 개발실')
        self.assertEqual(loc.code, 'HQ-3F-DEV')
        self.assertEqual(str(loc), '[HQ-3F-DEV] 본사 3층 개발실')

    def test_location_code_unique(self):
        """위치코드 중복 불가"""
        Location.objects.create(name='위치A', code='LOC-001')
        with self.assertRaises(IntegrityError):
            Location.objects.create(name='위치B', code='LOC-001')

    def test_full_path_property(self):
        """full_path: 건물 > 위치명 > 층 > 호실"""
        loc = Location.objects.create(
            name='서버실',
            code='HQ-B1-SRV',
            building='본사',
            floor='B1',
            room='A구역',
        )
        self.assertEqual(loc.full_path, '본사 > 서버실 > B1층 > A구역')

    def test_full_path_minimal(self):
        """building/floor/room 없으면 name만"""
        loc = Location.objects.create(name='외부창고', code='EXT-WH')
        self.assertEqual(loc.full_path, '외부창고')

    def test_parent_relationship(self):
        """상위위치 참조"""
        parent = Location.objects.create(name='본사', code='HQ')
        child = Location.objects.create(name='3층', code='HQ-3F', parent=parent)
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())

    def test_asset_managed_location(self):
        """FixedAsset에 managed_location FK 연결"""
        loc = Location.objects.create(name='본사 1층', code='HQ-1F')
        cat = AssetCategory.objects.create(name='비품', code='EQ-LOC', useful_life_years=5)
        asset = FixedAsset.objects.create(
            asset_number='FA-LOC-001',
            name='위치 테스트 자산',
            category=cat,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('1000000'),
            useful_life_years=5,
            managed_location=loc,
        )
        self.assertEqual(asset.managed_location, loc)
        self.assertIn(asset, loc.assets.all())

    def test_transfer_managed_location_fields(self):
        """AssetTransfer에 from/to_managed_location FK"""
        from apps.hr.models import Department
        loc_a = Location.objects.create(name='A동', code='LOC-A')
        loc_b = Location.objects.create(name='B동', code='LOC-B')
        cat = AssetCategory.objects.create(name='비품', code='EQ-TL', useful_life_years=5)
        dept = Department.objects.create(name='개발부', code='DEV-TL')
        asset = FixedAsset.objects.create(
            asset_number='FA-TL-001',
            name='이관위치 테스트',
            category=cat,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('500000'),
            useful_life_years=5,
            managed_location=loc_a,
            department=dept,
        )
        transfer = AssetTransfer.objects.create(
            asset=asset,
            transfer_date=date(2026, 4, 1),
            from_department=dept,
            to_department=dept,
            from_managed_location=loc_a,
            to_managed_location=loc_b,
        )
        self.assertEqual(transfer.from_managed_location, loc_a)
        self.assertEqual(transfer.to_managed_location, loc_b)


class DepartmentSummaryViewTest(TestCase):
    """부서별 자산 현황 뷰 테스트"""

    def setUp(self):
        from apps.accounts.models import User
        from apps.hr.models import Department
        self.user = User.objects.create_user(
            username='mgr_dept', password='test1234', role='manager',
        )
        self.dept = Department.objects.create(name='영업부', code='SALES-DS')
        self.category = AssetCategory.objects.create(
            name='비품', code='EQ-DS', useful_life_years=5,
        )
        FixedAsset.objects.create(
            asset_number='FA-DS-001',
            name='부서별 테스트 자산',
            category=self.category,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=Decimal('2000000'),
            useful_life_years=5,
            department=self.dept,
        )

    def test_department_summary_accessible(self):
        """부서별 현황 페이지 접근 가능"""
        self.client.force_login(self.user)
        response = self.client.get('/asset/department-summary/')
        self.assertEqual(response.status_code, 200)

    def test_department_summary_context(self):
        """부서별 현황 컨텍스트 데이터"""
        self.client.force_login(self.user)
        response = self.client.get('/asset/department-summary/')
        self.assertIn('dept_data', response.context)
        self.assertIn('total_count', response.context)
        self.assertGreaterEqual(response.context['total_count'], 1)

    def test_department_summary_chart_json(self):
        """차트용 JSON 데이터 존재"""
        self.client.force_login(self.user)
        response = self.client.get('/asset/department-summary/')
        self.assertIn('dept_labels_json', response.context)
        self.assertIn('category_labels_json', response.context)
        self.assertIn('status_labels_json', response.context)
        self.assertIn('location_labels_json', response.context)
