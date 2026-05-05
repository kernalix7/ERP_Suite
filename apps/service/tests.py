from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.accounting.models import AccountReceivable
from apps.inventory.models import Product
from apps.sales.models import Customer, Partner

from .models import RepairRecord, ServiceRequest


class ServiceRequestTests(TestCase):
    """AS 요청 모델 테스트"""

    def setUp(self):
        self.product = Product.objects.create(
            code='PRD-001',
            name='테스트 제품',
            product_type=Product.ProductType.FINISHED,
        )
        self.customer = Customer.objects.create(
            code='CUST-SVC01', name='테스트 고객',
            phone='010-1234-5678',
        )

    def test_creation_with_required_fields(self):
        """필수 필드 포함 AS 요청 생성"""
        sr = ServiceRequest.objects.create(
            request_number='AS-2026-0001',
            customer=self.customer,
            product=self.product,
            request_type=ServiceRequest.RequestType.WARRANTY,
            symptom='전원이 켜지지 않음',
            received_date=date(2026, 3, 1),
        )
        self.assertEqual(sr.status, ServiceRequest.Status.RECEIVED)
        self.assertEqual(sr.request_type, 'WARRANTY')
        self.assertEqual(sr.customer, self.customer)
        self.assertEqual(sr.product, self.product)
        self.assertEqual(
            str(sr), f'AS-2026-0001 - {self.customer.name}'
        )

    def test_status_transitions(self):
        """RECEIVED → INSPECTING → REPAIRING → COMPLETED → RETURNED 상태 전환"""
        sr = ServiceRequest.objects.create(
            request_number='AS-2026-0002',
            customer=self.customer,
            product=self.product,
            symptom='화면 불량',
            received_date=date(2026, 3, 1),
        )
        expected_flow = [
            ServiceRequest.Status.RECEIVED,
            ServiceRequest.Status.INSPECTING,
            ServiceRequest.Status.REPAIRING,
            ServiceRequest.Status.COMPLETED,
            ServiceRequest.Status.RETURNED,
        ]
        self.assertEqual(sr.status, expected_flow[0])

        for next_status in expected_flow[1:]:
            sr.status = next_status
            sr.save()
            sr.refresh_from_db()
            self.assertEqual(sr.status, next_status)

        # 완료일 기록
        sr.completed_date = date(2026, 3, 10)
        sr.save()
        sr.refresh_from_db()
        self.assertEqual(sr.completed_date, date(2026, 3, 10))

    def test_soft_delete(self):
        """AS 요청 soft delete 처리"""
        sr = ServiceRequest.objects.create(
            request_number='AS-2026-0003',
            customer=self.customer,
            product=self.product,
            symptom='버튼 고장',
            received_date=date(2026, 3, 5),
        )
        self.assertTrue(sr.is_active)
        self.assertEqual(ServiceRequest.objects.count(), 1)

        sr.soft_delete()
        sr.refresh_from_db()
        self.assertFalse(sr.is_active)
        # ActiveManager 기본 쿼리셋에서 제외
        self.assertEqual(ServiceRequest.objects.count(), 0)
        # all_objects로는 조회 가능
        self.assertEqual(ServiceRequest.all_objects.count(), 1)


class RepairRecordTests(TestCase):
    """수리이력 모델 테스트"""

    def setUp(self):
        self.product = Product.objects.create(
            code='PRD-002',
            name='수리 대상 제품',
            product_type=Product.ProductType.FINISHED,
        )
        self.customer = Customer.objects.create(
            code='CUST-SVC02', name='수리 고객',
            phone='010-9999-8888',
        )
        self.technician = User.objects.create_user(
            username='tech1',
            password='testpass123',
            name='수리기사',
            role=User.Role.STAFF,
        )
        self.service_request = ServiceRequest.objects.create(
            request_number='AS-2026-0010',
            customer=self.customer,
            product=self.product,
            symptom='소음 발생',
            received_date=date(2026, 3, 1),
        )

    def test_repair_record_linked_to_service_request(self):
        """수리이력이 AS 요청에 연결"""
        repair = RepairRecord.objects.create(
            service_request=self.service_request,
            repair_date=date(2026, 3, 5),
            description='베어링 교체',
            parts_used='베어링 1개',
            cost=Decimal('50000'),
            technician=self.technician,
        )
        self.assertEqual(repair.service_request, self.service_request)
        self.assertEqual(self.service_request.repairs.count(), 1)
        self.assertEqual(
            str(repair), 'AS-2026-0010 - 2026-03-05'
        )

    def test_multiple_repairs_on_one_request(self):
        """하나의 AS 요청에 여러 수리이력"""
        RepairRecord.objects.create(
            service_request=self.service_request,
            repair_date=date(2026, 3, 5),
            description='1차 수리: 베어링 교체',
            cost=Decimal('50000'),
        )
        RepairRecord.objects.create(
            service_request=self.service_request,
            repair_date=date(2026, 3, 7),
            description='2차 수리: 모터 교체',
            cost=Decimal('150000'),
        )
        RepairRecord.objects.create(
            service_request=self.service_request,
            repair_date=date(2026, 3, 9),
            description='3차 수리: 최종 점검',
            cost=Decimal('0'),
        )
        self.assertEqual(self.service_request.repairs.count(), 3)

        total_cost = sum(r.cost for r in self.service_request.repairs.all())
        self.assertEqual(total_cost, Decimal('200000'))


class ServiceRequestSignalTests(TestCase):
    """AS 완료 시 유상수리 AR 자동 생성 시그널 테스트"""

    def setUp(self):
        self.product = Product.objects.create(
            code='PRD-SIG-001',
            name='시그널 테스트 제품',
            product_type=Product.ProductType.FINISHED,
        )
        self.customer = Customer.objects.create(
            code='CUST-SIG01', name='시그널고객',
            phone='010-5555-6666',
        )
        self.partner = Partner.objects.create(
            code='PTN-SIG-001',
            name='시그널고객',
            partner_type=Partner.PartnerType.CUSTOMER,
        )

    def test_completed_paid_repair_creates_ar(self):
        """유상수리 완료 시 AR 자동 생성"""
        sr = ServiceRequest.objects.create(
            request_number='AS-SIG-001',
            customer=self.customer,
            product=self.product,
            request_type=ServiceRequest.RequestType.PAID,
            symptom='화면 깨짐',
            received_date=date(2026, 3, 1),
            is_warranty=False,
        )
        RepairRecord.objects.create(
            service_request=sr,
            repair_date=date(2026, 3, 5),
            description='LCD 교체',
            cost=Decimal('100000'),
        )
        sr.status = ServiceRequest.Status.COMPLETED
        sr.completed_date = date(2026, 3, 5)
        sr.save()

        ar = AccountReceivable.objects.filter(
            notes__contains='AS-SIG-001',
        ).first()
        self.assertIsNotNone(ar)
        self.assertEqual(int(ar.amount), 100000)
        self.assertEqual(ar.partner, self.partner)

    def test_warranty_repair_no_ar(self):
        """보증수리 완료 시 AR 미생성"""
        sr = ServiceRequest.objects.create(
            request_number='AS-SIG-002',
            customer=self.customer,
            product=self.product,
            request_type=ServiceRequest.RequestType.WARRANTY,
            symptom='작동 불량',
            received_date=date(2026, 3, 1),
            is_warranty=True,
        )
        RepairRecord.objects.create(
            service_request=sr,
            repair_date=date(2026, 3, 5),
            description='부품 교체',
            cost=Decimal('80000'),
        )
        sr.status = ServiceRequest.Status.COMPLETED
        sr.save()

        ar_count = AccountReceivable.objects.filter(
            notes__contains='AS-SIG-002',
        ).count()
        self.assertEqual(ar_count, 0)

    def test_no_partner_match_no_ar(self):
        """매칭 거래처 없으면 AR 미생성"""
        other_customer = Customer.objects.create(
            code='CUST-NOMATCH', name='매칭불가고객',
            phone='010-0000-0000',
        )
        sr = ServiceRequest.objects.create(
            request_number='AS-SIG-003',
            customer=other_customer,
            product=self.product,
            symptom='고장',
            received_date=date(2026, 3, 1),
            is_warranty=False,
        )
        RepairRecord.objects.create(
            service_request=sr,
            repair_date=date(2026, 3, 5),
            description='수리',
            cost=Decimal('50000'),
        )
        sr.status = ServiceRequest.Status.COMPLETED
        sr.save()

        ar_count = AccountReceivable.objects.filter(
            notes__contains='AS-SIG-003',
        ).count()
        self.assertEqual(ar_count, 0)

    def test_zero_cost_no_ar(self):
        """수리비용 0원이면 AR 미생성"""
        sr = ServiceRequest.objects.create(
            request_number='AS-SIG-004',
            customer=self.customer,
            product=self.product,
            symptom='점검',
            received_date=date(2026, 3, 1),
            is_warranty=False,
        )
        sr.status = ServiceRequest.Status.COMPLETED
        sr.save()

        ar_count = AccountReceivable.objects.filter(
            notes__contains='AS-SIG-004',
        ).count()
        self.assertEqual(ar_count, 0)

    def test_cancel_service_deletes_ar(self):
        """AS 취소 시 관련 AR soft delete"""
        sr = ServiceRequest.objects.create(
            request_number='AS-SIG-005',
            customer=self.customer,
            product=self.product,
            request_type=ServiceRequest.RequestType.PAID,
            symptom='화면 불량',
            received_date=date(2026, 3, 1),
            is_warranty=False,
        )
        RepairRecord.objects.create(
            service_request=sr,
            repair_date=date(2026, 3, 5),
            description='LCD 교체',
            cost=Decimal('200000'),
        )
        # COMPLETED → AR 생성
        sr.status = ServiceRequest.Status.COMPLETED
        sr.completed_date = date(2026, 3, 5)
        sr.save()

        ar = AccountReceivable.objects.filter(
            notes__contains='AS-SIG-005',
            is_active=True,
        ).first()
        self.assertIsNotNone(ar)

        # CANCELLED → AR soft delete
        sr.status = ServiceRequest.Status.CANCELLED
        sr.save()

        ar.refresh_from_db()
        self.assertFalse(ar.is_active)

    def test_cancel_service_without_ar_no_error(self):
        """AR 없는 AS 취소 시 에러 없음"""
        sr = ServiceRequest.objects.create(
            request_number='AS-SIG-006',
            customer=self.customer,
            product=self.product,
            symptom='점검만',
            received_date=date(2026, 3, 1),
            is_warranty=True,
        )
        sr.status = ServiceRequest.Status.COMPLETED
        sr.save()
        # 보증수리이므로 AR 없음
        sr.status = ServiceRequest.Status.CANCELLED
        sr.save()  # 에러 없이 통과해야 함


class WarrantySerialAutoVerificationTest(TestCase):
    """시리얼번호 기반 보증 자동 검증 테스트"""

    def setUp(self):
        from datetime import timedelta
        from apps.warranty.models import ProductRegistration
        from apps.inventory.models import SerialNumber

        self.user = User.objects.create_user(
            username='warranty_serial_user', password='testpass123',
            role='manager',
        )
        self.product = Product.objects.create(
            code='PRD-WS-001', name='보증검증제품',
            product_type=Product.ProductType.FINISHED,
            unit_price=50000, cost_price=30000,
        )
        self.other_product = Product.objects.create(
            code='PRD-WS-002', name='다른제품',
            product_type=Product.ProductType.FINISHED,
            unit_price=30000,
        )
        self.customer = Customer.objects.create(
            code='CUST-WS01', name='보증고객',
            phone='010-1111-2222',
        )

        # 유효한 보증 정품등록
        self.valid_reg = ProductRegistration.objects.create(
            serial_number='SN-VALID-001',
            product=self.product,
            customer=self.customer,
            customer_name='보증고객',
            phone='010-1111-2222',
            purchase_date=date.today() - timedelta(days=30),
            warranty_start=date.today() - timedelta(days=30),
            warranty_end=date.today() + timedelta(days=335),
            is_verified=True,
        )

        # 만료된 보증 정품등록
        self.expired_reg = ProductRegistration.objects.create(
            serial_number='SN-EXPIRED-001',
            product=self.product,
            customer=self.customer,
            customer_name='보증고객',
            phone='010-1111-2222',
            purchase_date=date.today() - timedelta(days=400),
            warranty_start=date.today() - timedelta(days=400),
            warranty_end=date.today() - timedelta(days=35),
        )

        # 재고 시리얼번호
        self.inv_serial = SerialNumber.objects.create(
            serial='SN-VALID-001',
            product=self.product,
            status=SerialNumber.Status.SHIPPED,
        )

    def test_valid_serial_sets_warranty(self):
        """유효한 시리얼번호로 AS 접수 시 is_warranty=True"""
        sr = ServiceRequest(
            request_number='AS-WS-001',
            customer=self.customer,
            product=self.other_product,  # 다른 제품으로 설정
            serial_number='SN-VALID-001',
            symptom='전원 불량',
            received_date=date.today(),
        )
        # form_valid 로직을 직접 테스트
        from apps.warranty.models import ProductRegistration
        reg = ProductRegistration.objects.filter(
            serial_number=sr.serial_number, is_active=True,
        ).first()
        if reg and reg.is_warranty_valid:
            sr.is_warranty = True
            sr.request_type = 'WARRANTY'

        from apps.inventory.models import SerialNumber
        inv_sn = SerialNumber.objects.filter(
            serial=sr.serial_number, is_active=True,
        ).select_related('product').first()
        if inv_sn:
            sr.product = inv_sn.product

        sr.save()
        sr.refresh_from_db()
        self.assertTrue(sr.is_warranty)
        self.assertEqual(sr.request_type, 'WARRANTY')
        # 제품이 시리얼 기반으로 자동 매칭됨
        self.assertEqual(sr.product, self.product)

    def test_expired_serial_no_warranty(self):
        """만료된 시리얼번호로 AS 접수 시 is_warranty=False"""
        sr = ServiceRequest(
            request_number='AS-WS-002',
            customer=self.customer,
            product=self.product,
            serial_number='SN-EXPIRED-001',
            symptom='화면 불량',
            received_date=date.today(),
        )
        from apps.warranty.models import ProductRegistration
        reg = ProductRegistration.objects.filter(
            serial_number=sr.serial_number, is_active=True,
        ).first()
        if reg and reg.is_warranty_valid:
            sr.is_warranty = True

        sr.save()
        sr.refresh_from_db()
        self.assertFalse(sr.is_warranty)

    def test_unknown_serial_no_error(self):
        """미등록 시리얼번호로 AS 접수 시 에러 없음"""
        sr = ServiceRequest.objects.create(
            request_number='AS-WS-003',
            customer=self.customer,
            product=self.product,
            serial_number='SN-UNKNOWN-999',
            symptom='작동 불량',
            received_date=date.today(),
        )
        self.assertFalse(sr.is_warranty)
        self.assertEqual(sr.product, self.product)


class ServiceRequestAccessControlTests(TestCase):
    """ServiceRequest List/Detail 뷰 사용자 역할별 격리 검증."""

    def setUp(self):
        self.product = Product.objects.create(
            code='PRD-AC1', name='AC 테스트 제품',
            product_type=Product.ProductType.FINISHED,
        )
        self.customer = Customer.objects.create(
            code='CUST-AC1', name='AC 고객', phone='010-0000-0001',
        )
        self.staff_a = User.objects.create_user(
            username='staff_a', password='pw', role='staff',
        )
        self.staff_b = User.objects.create_user(
            username='staff_b', password='pw', role='staff',
        )
        self.manager = User.objects.create_user(
            username='svc_manager', password='pw', role='manager',
        )
        self.req_a = ServiceRequest.objects.create(
            request_number='AS-AC-001',
            customer=self.customer, product=self.product,
            symptom='증상 A', received_date=date.today(),
            created_by=self.staff_a,
        )
        self.req_b = ServiceRequest.objects.create(
            request_number='AS-AC-002',
            customer=self.customer, product=self.product,
            symptom='증상 B', received_date=date.today(),
            created_by=self.staff_b,
        )

    def test_staff_cannot_see_others_service_request(self):
        """staff B 가 staff A 접수 detail → 404"""
        self.client.force_login(self.staff_b)
        resp = self.client.get(f'/service/requests/{self.req_a.request_number}/')
        self.assertEqual(resp.status_code, 404)

    def test_creator_staff_sees_own_request(self):
        """본인 접수 detail → 200"""
        self.client.force_login(self.staff_a)
        resp = self.client.get(f'/service/requests/{self.req_a.request_number}/')
        self.assertEqual(resp.status_code, 200)

    def test_manager_sees_all_service_requests(self):
        """manager 모든 detail → 200"""
        self.client.force_login(self.manager)
        for r in (self.req_a, self.req_b):
            resp = self.client.get(f'/service/requests/{r.request_number}/')
            self.assertEqual(resp.status_code, 200)

    def test_list_filters_by_creator_for_staff(self):
        """staff ListView 본인 것만 노출"""
        self.client.force_login(self.staff_a)
        resp = self.client.get('/service/requests/')
        self.assertEqual(resp.status_code, 200)
        nums = [r.request_number for r in resp.context['requests']]
        self.assertIn(self.req_a.request_number, nums)
        self.assertNotIn(self.req_b.request_number, nums)

    def test_list_returns_all_for_manager(self):
        """manager ListView 전체 노출"""
        self.client.force_login(self.manager)
        resp = self.client.get('/service/requests/')
        self.assertEqual(resp.status_code, 200)
        nums = [r.request_number for r in resp.context['requests']]
        self.assertIn(self.req_a.request_number, nums)
        self.assertIn(self.req_b.request_number, nums)
