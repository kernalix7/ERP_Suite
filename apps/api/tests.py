from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.inventory.models import Product, Category
from apps.sales.models import Partner

User = get_user_model()


class JWTAuthenticationTest(TestCase):
    """JWT 인증 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='apiuser', password='testpass123',
            role='staff', name='API유저',
        )

    def test_obtain_token(self):
        """JWT 토큰 발급"""
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'apiuser',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_obtain_token_invalid_credentials(self):
        """잘못된 자격증명으로 토큰 발급 실패"""
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'apiuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        """JWT 토큰 갱신"""
        obtain_response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'apiuser',
            'password': 'testpass123',
        })
        refresh_token = obtain_response.data['refresh']
        refresh_response = self.client.post(reverse('token_refresh'), {
            'refresh': refresh_token,
        })
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_response.data)

    def test_access_api_with_token(self):
        """JWT 토큰으로 API 접근"""
        obtain_response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'apiuser',
            'password': 'testpass123',
        })
        token = obtain_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_write_api_without_token_rejected(self):
        """토큰 없이 API 쓰기 접근 불가"""
        unauthenticated_client = APIClient(enforce_csrf_checks=True)
        response = unauthenticated_client.post(
            '/api/products/',
            {'code': 'X', 'name': 'X', 'product_type': 'RAW',
             'unit_price': 1, 'cost_price': 1},
            format='json',
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED,
             status.HTTP_403_FORBIDDEN],
        )


class IsManagerOrReadOnlyPermissionTest(TestCase):
    """IsManagerOrReadOnly 권한 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='api_admin', password='testpass123', role='admin',
        )
        self.manager = User.objects.create_user(
            username='api_manager', password='testpass123', role='manager',
        )
        self.staff = User.objects.create_user(
            username='api_staff', password='testpass123', role='staff',
        )
        self.category = Category.objects.create(
            code='CAT-TEST', name='테스트카테고리', created_by=self.admin,
        )

    def _get_token(self, username):
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': username,
            'password': 'testpass123',
        })
        return response.data['access']

    def test_staff_can_read(self):
        """staff는 읽기 가능"""
        token = self._get_token('api_staff')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_cannot_write(self):
        """staff는 쓰기 불가"""
        token = self._get_token('api_staff')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/categories/', {
            'name': '새카테고리',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_write(self):
        """manager는 쓰기 가능"""
        token = self._get_token('api_manager')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/categories/', {
            'code': 'CAT-MGR', 'name': '매니저카테고리',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_can_write(self):
        """admin은 쓰기 가능"""
        token = self._get_token('api_admin')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/categories/', {
            'code': 'CAT-ADM', 'name': '관리자카테고리',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_manager_can_update(self):
        """manager는 수정 가능"""
        token = self._get_token('api_manager')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.patch(
            f'/api/categories/{self.category.pk}/',
            {'name': '수정된카테고리'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_cannot_delete(self):
        """staff는 삭제 불가"""
        token = self._get_token('api_staff')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete(
            f'/api/categories/{self.category.pk}/',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_delete(self):
        """manager 삭제 시 soft delete 수행"""
        token = self._get_token('api_manager')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete(
            f'/api/categories/{self.category.pk}/',
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_active)


class ProductAPITest(TestCase):
    """Product API 엔드포인트 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='prod_api_mgr', password='testpass123', role='manager',
        )
        self.product = Product.objects.create(
            code='API-PRD-001', name='API 테스트 제품',
            product_type='FINISHED', unit_price=10000, cost_price=5000,
            created_by=self.manager,
        )
        # Authenticate
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'prod_api_mgr', 'password': 'testpass123',
        })
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}',
        )

    def test_product_list(self):
        """제품 목록 조회"""
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_product_detail(self):
        """제품 상세 조회"""
        response = self.client.get(f'/api/products/{self.product.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'API-PRD-001')
        self.assertEqual(response.data['name'], 'API 테스트 제품')

    def test_product_create(self):
        """제품 생성"""
        response = self.client.post('/api/products/', {
            'code': 'API-PRD-002',
            'name': 'API 생성 제품',
            'product_type': 'RAW',
            'unit_price': 5000,
            'cost_price': 3000,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Product.objects.filter(code='API-PRD-002').exists())

    def test_product_update(self):
        """제품 수정"""
        response = self.client.patch(
            f'/api/products/{self.product.pk}/',
            {'name': '수정된 제품명'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, '수정된 제품명')

    def test_product_serializer_fields(self):
        """제품 시리얼라이저 필드 확인"""
        response = self.client.get(f'/api/products/{self.product.pk}/')
        data = response.data
        self.assertIn('id', data)
        self.assertIn('code', data)
        self.assertIn('name', data)
        self.assertIn('product_type', data)
        self.assertIn('current_stock', data)
        self.assertIn('unit_price', data)
        self.assertIn('cost_price', data)


class PartnerAPITest(TestCase):
    """Partner API 엔드포인트 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='partner_api_mgr', password='testpass123', role='manager',
        )
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'partner_api_mgr', 'password': 'testpass123',
        })
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}',
        )

    def test_partner_list(self):
        """거래처 목록 조회"""
        response = self.client.get('/api/partners/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_partner_create(self):
        """거래처 생성"""
        response = self.client.post('/api/partners/', {
            'code': 'P-API-001',
            'name': 'API 거래처',
            'partner_type': 'CUSTOMER',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Partner.objects.filter(code='P-API-001').exists())


class OrderAPITest(TestCase):
    """Order API 엔드포인트 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='order_api_mgr', password='testpass123', role='manager',
        )
        self.partner = Partner.objects.create(
            code='ORD-API-P001', name='API주문거래처',
            partner_type='CUSTOMER', created_by=self.manager,
        )
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'order_api_mgr', 'password': 'testpass123',
        })
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}',
        )

    def test_order_list(self):
        """주문 목록 조회"""
        response = self.client.get('/api/orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_order_create(self):
        """주문 생성"""
        response = self.client.post('/api/orders/', {
            'order_number': 'ORD-API-001',
            'partner': self.partner.pk,
            'order_date': '2026-03-17',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_order_status_read_only(self):
        """주문 status 필드는 API로 직접 변경 불가"""
        from apps.sales.models import Order
        order = Order.objects.create(
            order_number='ORD-API-RO', partner=self.partner,
            order_date='2026-03-17', created_by=self.manager,
        )
        response = self.client.patch(
            f'/api/orders/{order.pk}/',
            {'status': 'CONFIRMED'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, 'DRAFT')


# ====================================================================
# New ViewSet Tests
# ====================================================================

class _AuthenticatedAPITestBase(TestCase):
    """Authenticated API test base with manager JWT token"""

    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='new_api_mgr', password='testpass123', role='manager',
            name='API매니저',
        )
        self.staff = User.objects.create_user(
            username='new_api_staff', password='testpass123', role='staff',
            name='API스탭',
        )
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'new_api_mgr', 'password': 'testpass123',
        })
        self.token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')


class ApprovalRequestAPITest(_AuthenticatedAPITestBase):
    """ApprovalRequest API 테스트"""

    def test_list(self):
        """결재 목록 조회"""
        response = self.client.get('/api/approval-requests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        """결재 생성"""
        response = self.client.post('/api/approval-requests/', {
            'category': 'GENERAL',
            'title': 'API 결재 테스트',
            'content': 'API에서 생성',
            'amount': 50000,
            'requester': self.manager.pk,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('request_number', response.data)

    def test_detail(self):
        """결재 상세 조회"""
        from apps.approval.models import ApprovalRequest
        ar = ApprovalRequest.all_objects.create(
            category='PURCHASE', title='상세테스트', content='내용',
            requester=self.manager, created_by=self.manager,
        )
        response = self.client.get(f'/api/approval-requests/{ar.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], '상세테스트')
        self.assertIn('steps', response.data)

    def test_request_number_read_only(self):
        """request_number는 읽기전용"""
        from apps.approval.models import ApprovalRequest
        ar = ApprovalRequest.all_objects.create(
            category='GENERAL', title='RO테스트', content='내용',
            requester=self.manager, created_by=self.manager,
        )
        original_num = ar.request_number
        response = self.client.patch(
            f'/api/approval-requests/{ar.pk}/',
            {'request_number': 'AR-HACK'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ar.refresh_from_db()
        self.assertEqual(ar.request_number, original_num)

    def test_staff_read_only(self):
        """staff는 읽기만 가능"""
        staff_response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'new_api_staff', 'password': 'testpass123',
        })
        staff_client = APIClient()
        staff_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {staff_response.data["access"]}',
        )
        response = staff_client.get('/api/approval-requests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = staff_client.post('/api/approval-requests/', {
            'category': 'GENERAL', 'title': 'X', 'content': 'X',
            'requester': self.staff.pk,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ApprovalStepAPITest(_AuthenticatedAPITestBase):
    """ApprovalStep API 테스트"""

    def test_list(self):
        response = self.client.get('/api/approval-steps/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_step(self):
        from apps.approval.models import ApprovalRequest
        ar = ApprovalRequest.all_objects.create(
            category='GENERAL', title='단계테스트', content='내용',
            requester=self.manager, created_by=self.manager,
        )
        response = self.client.post('/api/approval-steps/', {
            'request': ar.pk,
            'step_order': 1,
            'approver': self.manager.pk,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class EmployeeProfileAPITest(_AuthenticatedAPITestBase):
    """EmployeeProfile API 테스트"""

    def test_list(self):
        response = self.client.get('/api/employees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PayrollAPITest(_AuthenticatedAPITestBase):
    """Payroll API 테스트"""

    def test_list(self):
        response = self.client.get('/api/payrolls/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ServiceRequestAPITest(_AuthenticatedAPITestBase):
    """ServiceRequest API 테스트"""

    def test_list(self):
        response = self.client.get('/api/service-requests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class InquiryAPITest(_AuthenticatedAPITestBase):
    """Inquiry API 테스트"""

    def test_list(self):
        response = self.client.get('/api/inquiries/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class FixedAssetAPITest(_AuthenticatedAPITestBase):
    """FixedAsset API 테스트"""

    def test_list(self):
        response = self.client.get('/api/fixed-assets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class MarketplaceOrderAPITest(_AuthenticatedAPITestBase):
    """MarketplaceOrder API 테스트"""

    def test_list(self):
        response = self.client.get('/api/marketplace-orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class VoucherAPITest(_AuthenticatedAPITestBase):
    """Voucher API 테스트"""

    def test_list(self):
        response = self.client.get('/api/vouchers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AccountReceivableAPITest(_AuthenticatedAPITestBase):
    """AccountReceivable API 테스트"""

    def test_list(self):
        response = self.client.get('/api/accounts-receivable/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AccountPayableAPITest(_AuthenticatedAPITestBase):
    """AccountPayable API 테스트"""

    def test_list(self):
        response = self.client.get('/api/accounts-payable/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BudgetAPITest(_AuthenticatedAPITestBase):
    """Budget API 테스트"""

    def test_list(self):
        response = self.client.get('/api/budgets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PurchaseOrderAPITest(_AuthenticatedAPITestBase):
    """PurchaseOrder API 테스트"""

    def test_list(self):
        response = self.client.get('/api/purchase-orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        partner = Partner.objects.create(
            code='PO-API-P001', name='발주API거래처',
            partner_type='SUPPLIER', created_by=self.manager,
        )
        response = self.client.post('/api/purchase-orders/', {
            'partner': partner.pk,
            'order_date': '2026-03-24',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_soft_delete(self):
        """API 삭제 시 soft delete"""
        from apps.purchase.models import PurchaseOrder as PO
        partner = Partner.objects.create(
            code='PO-API-DEL', name='삭제테스트거래처',
            partner_type='SUPPLIER', created_by=self.manager,
        )
        po = PO.all_objects.create(
            partner=partner, order_date='2026-03-24',
            created_by=self.manager,
        )
        response = self.client.delete(f'/api/purchase-orders/{po.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        po.refresh_from_db()
        self.assertFalse(po.is_active)


class NewViewSetCountTest(_AuthenticatedAPITestBase):
    """API ViewSet 총 개수 확인"""

    def test_total_viewset_count(self):
        """API 엔드포인트 25개 이상 등록 확인"""
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # DefaultRouter root returns all registered endpoints
        self.assertGreaterEqual(len(response.data), 25)
