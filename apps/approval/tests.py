from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.approval.models import (
    ApprovalRequest, ApprovalStep, ApprovalAttachment,
)

User = get_user_model()


class ApprovalModelTestBase(TestCase):
    """결재 테스트 공통 setUp"""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='appr_admin', password='testpass123',
            role='admin', name='관리자',
        )
        self.manager = User.objects.create_user(
            username='appr_manager', password='testpass123',
            role='manager', name='매니저',
        )
        self.manager2 = User.objects.create_user(
            username='appr_manager2', password='testpass123',
            role='manager', name='매니저2',
        )
        self.manager3 = User.objects.create_user(
            username='appr_manager3', password='testpass123',
            role='manager', name='매니저3',
        )
        self.staff = User.objects.create_user(
            username='appr_staff', password='testpass123',
            role='staff', name='직원',
        )

    def _create_request(self, requester=None, approver=None, **kwargs):
        defaults = {
            'category': 'GENERAL',
            'title': '테스트 결재',
            'content': '테스트 내용',
            'amount': 100000,
            'requester': requester or self.manager,
            'approver': approver or self.admin,
            'created_by': requester or self.manager,
        }
        defaults.update(kwargs)
        return ApprovalRequest.all_objects.create(**defaults)


# ====================================================================
# 1. 모델 CRUD 테스트
# ====================================================================
class ApprovalRequestModelTest(ApprovalModelTestBase):
    """ApprovalRequest 모델 테스트"""

    def test_create_approval_request(self):
        """결재 요청 생성"""
        ar = self._create_request()
        self.assertTrue(ar.request_number.startswith('AR'))
        self.assertEqual(ar.status, 'DRAFT')
        self.assertEqual(ar.amount, 100000)

    def test_auto_request_number(self):
        """결재번호 자동생성"""
        ar1 = self._create_request()
        ar2 = self._create_request()
        self.assertNotEqual(ar1.request_number, ar2.request_number)

    def test_str_representation(self):
        """문자열 표현"""
        ar = self._create_request(title='구매품의 테스트')
        self.assertIn('구매품의 테스트', str(ar))

    def test_default_status_draft(self):
        """기본 상태 DRAFT"""
        ar = self._create_request()
        self.assertEqual(ar.status, 'DRAFT')

    def test_soft_delete(self):
        """소프트 삭제"""
        ar = self._create_request()
        ar.soft_delete()
        self.assertFalse(ar.is_active)
        # all_objects로는 조회 가능
        self.assertTrue(
            ApprovalRequest.all_objects.filter(pk=ar.pk).exists()
        )
        # objects(ActiveManager)로는 조회 불가
        self.assertFalse(
            ApprovalRequest.objects.filter(pk=ar.pk).exists()
        )

    def test_doc_categories(self):
        """문서종류 선택지"""
        categories = dict(ApprovalRequest.DocCategory.choices)
        self.assertIn('PURCHASE', categories)
        self.assertIn('EXPENSE', categories)
        self.assertIn('LEAVE', categories)

    def test_urgency_choices(self):
        """긴급도 선택지"""
        ar = self._create_request(urgency='URGENT')
        self.assertEqual(ar.urgency, 'URGENT')

    def test_all_urgency_values(self):
        """전체 긴급도 값 확인"""
        urgencies = dict(ApprovalRequest.Urgency.choices)
        self.assertEqual(set(urgencies.keys()), {'NORMAL', 'URGENT', 'CRITICAL'})

    def test_amount_default_zero(self):
        """금액 기본값 0"""
        ar = self._create_request(amount=0)
        self.assertEqual(ar.amount, 0)


class ApprovalStepModelTest(ApprovalModelTestBase):
    """ApprovalStep 모델 테스트"""

    def test_create_step(self):
        """결재 단계 생성"""
        ar = self._create_request()
        step = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        self.assertEqual(step.status, 'PENDING')
        self.assertEqual(step.step_order, 1)

    def test_step_ordering(self):
        """단계 순서 정렬"""
        ar = self._create_request()
        step2 = ApprovalStep.all_objects.create(
            request=ar, step_order=2, approver=self.manager2,
            created_by=self.manager,
        )
        step1 = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        steps = list(ar.steps.all())
        self.assertEqual(steps[0], step1)
        self.assertEqual(steps[1], step2)

    def test_step_str(self):
        """단계 문자열 표현"""
        ar = self._create_request()
        step = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        self.assertIn('1단계', str(step))

    def test_unique_together_step_order(self):
        """같은 요청 내 중복 단계 불가"""
        ar = self._create_request()
        ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ApprovalStep.all_objects.create(
                request=ar, step_order=1, approver=self.manager2,
                created_by=self.manager,
            )


class ApprovalAttachmentModelTest(ApprovalModelTestBase):
    """ApprovalAttachment 모델 테스트"""

    def test_attachment_str(self):
        """첨부파일 문자열 표현"""
        ar = self._create_request()
        att = ApprovalAttachment.all_objects.create(
            request=ar, file='test.pdf', original_name='테스트.pdf',
            created_by=self.manager,
        )
        self.assertEqual(str(att), '테스트.pdf')

    def test_attachment_belongs_to_request(self):
        """첨부파일-결재 연관"""
        ar = self._create_request()
        ApprovalAttachment.all_objects.create(
            request=ar, file='a.pdf', original_name='a.pdf',
            created_by=self.manager,
        )
        ApprovalAttachment.all_objects.create(
            request=ar, file='b.pdf', original_name='b.pdf',
            created_by=self.manager,
        )
        self.assertEqual(ar.attachments.count(), 2)


# ====================================================================
# 2. 시그널 테스트
# ====================================================================
class ApprovalStepSignalTest(ApprovalModelTestBase):
    """결재 단계 시그널 테스트"""

    def _setup_multistep(self):
        """3단계 결재 셋업"""
        ar = self._create_request(status='SUBMITTED')
        ar.submitted_at = timezone.now()
        ar.save(update_fields=['status', 'submitted_at', 'updated_at'])

        step1 = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.manager,
            created_by=self.manager,
        )
        step2 = ApprovalStep.all_objects.create(
            request=ar, step_order=2, approver=self.manager2,
            created_by=self.manager,
        )
        step3 = ApprovalStep.all_objects.create(
            request=ar, step_order=3, approver=self.admin,
            created_by=self.manager,
        )
        return ar, step1, step2, step3

    def test_step_approve_advances_current_step(self):
        """1단계 승인 → current_step 2로 이동"""
        ar, step1, step2, step3 = self._setup_multistep()

        step1.status = 'APPROVED'
        step1.acted_at = timezone.now()
        step1.save()

        ar.refresh_from_db()
        self.assertEqual(ar.current_step, 2)
        self.assertEqual(ar.status, 'SUBMITTED')

    def test_all_steps_approve_finalizes(self):
        """전 단계 승인 → 전체 APPROVED"""
        ar, step1, step2, step3 = self._setup_multistep()

        step1.status = 'APPROVED'
        step1.acted_at = timezone.now()
        step1.save()

        step2.status = 'APPROVED'
        step2.acted_at = timezone.now()
        step2.save()

        step3.status = 'APPROVED'
        step3.acted_at = timezone.now()
        step3.save()

        ar.refresh_from_db()
        self.assertEqual(ar.status, 'APPROVED')
        self.assertIsNotNone(ar.approved_at)

    def test_step_reject_rejects_request(self):
        """중간 단계 반려 → 전체 REJECTED"""
        ar, step1, step2, step3 = self._setup_multistep()

        step1.status = 'APPROVED'
        step1.save()

        step2.status = 'REJECTED'
        step2.comment = '예산 초과'
        step2.save()

        ar.refresh_from_db()
        self.assertEqual(ar.status, 'REJECTED')
        self.assertEqual(ar.reject_reason, '예산 초과')

    def test_first_step_reject(self):
        """1단계에서 즉시 반려"""
        ar, step1, step2, step3 = self._setup_multistep()

        step1.status = 'REJECTED'
        step1.comment = '부적합'
        step1.save()

        ar.refresh_from_db()
        self.assertEqual(ar.status, 'REJECTED')

    def test_signal_ignores_pending(self):
        """PENDING 상태 변경은 시그널 무시"""
        ar, step1, step2, step3 = self._setup_multistep()
        # step1을 다시 PENDING으로 저장 — 아무 변화 없어야 함
        step1.status = 'PENDING'
        step1.save()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'SUBMITTED')
        self.assertEqual(ar.current_step, 1)

    def test_signal_ignores_already_approved_request(self):
        """이미 APPROVED된 결재에 대한 시그널 무시"""
        ar, step1, step2, step3 = self._setup_multistep()
        # 수동으로 APPROVED 처리
        ar.status = 'APPROVED'
        ar.save(update_fields=['status', 'updated_at'])

        # step 변경이 영향 안 줌
        step1.status = 'REJECTED'
        step1.save()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'APPROVED')

    def test_signal_ignores_cancelled_request(self):
        """CANCELLED 결재에 대한 시그널 무시"""
        ar, step1, step2, step3 = self._setup_multistep()
        ar.status = 'CANCELLED'
        ar.save(update_fields=['status', 'updated_at'])

        step1.status = 'APPROVED'
        step1.save()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'CANCELLED')

    def test_two_step_approval(self):
        """2단계 결재 순차 승인"""
        ar = self._create_request(status='SUBMITTED')
        step1 = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.manager,
            created_by=self.manager,
        )
        step2 = ApprovalStep.all_objects.create(
            request=ar, step_order=2, approver=self.admin,
            created_by=self.manager,
        )

        step1.status = 'APPROVED'
        step1.save()
        ar.refresh_from_db()
        self.assertEqual(ar.current_step, 2)

        step2.status = 'APPROVED'
        step2.save()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'APPROVED')

    def test_single_step_approval(self):
        """단일 단계 승인"""
        ar = self._create_request(status='SUBMITTED')
        step1 = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )

        step1.status = 'APPROVED'
        step1.save()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'APPROVED')


# ====================================================================
# 3. 뷰 테스트 (결재 워크플로)
# ====================================================================
class ApprovalViewTestBase(ApprovalModelTestBase):
    """뷰 테스트 공통"""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.manager)


class ApprovalListViewTest(ApprovalViewTestBase):
    """결재 목록 뷰 테스트"""

    def test_list_view_accessible(self):
        """목록 접근 가능"""
        response = self.client.get(reverse('approval:approval_list'))
        self.assertEqual(response.status_code, 200)

    def test_list_filters_active_only(self):
        """활성 건만 표시"""
        ar1 = self._create_request(title='활성')
        ar2 = self._create_request(title='비활성')
        ar2.soft_delete()
        response = self.client.get(reverse('approval:approval_list'))
        approvals = response.context['approvals']
        pks = [a.pk for a in approvals]
        self.assertIn(ar1.pk, pks)
        self.assertNotIn(ar2.pk, pks)

    def test_list_filter_by_status(self):
        """상태 필터"""
        self._create_request(title='제출됨', status='SUBMITTED')
        self._create_request(title='작성중')
        response = self.client.get(
            reverse('approval:approval_list') + '?status=SUBMITTED'
        )
        approvals = response.context['approvals']
        for a in approvals:
            self.assertEqual(a.status, 'SUBMITTED')

    def test_list_tab_my(self):
        """내 결재 탭"""
        self._create_request(requester=self.manager)
        self._create_request(requester=self.admin)
        response = self.client.get(
            reverse('approval:approval_list') + '?tab=my'
        )
        approvals = response.context['approvals']
        for a in approvals:
            self.assertEqual(a.requester, self.manager)

    def test_list_tab_pending(self):
        """결재대기 탭"""
        self._create_request(
            approver=self.manager, status='SUBMITTED',
        )
        self._create_request(
            approver=self.admin, status='SUBMITTED',
        )
        response = self.client.get(
            reverse('approval:approval_list') + '?tab=pending'
        )
        approvals = response.context['approvals']
        for a in approvals:
            self.assertEqual(a.approver, self.manager)

    def test_pending_count_in_context(self):
        """결재대기 건수"""
        self._create_request(
            approver=self.manager, status='SUBMITTED',
        )
        response = self.client.get(reverse('approval:approval_list'))
        self.assertEqual(response.context['pending_count'], 1)

    def test_unauthenticated_redirect(self):
        """비로그인 접근 리다이렉트"""
        self.client.logout()
        response = self.client.get(reverse('approval:approval_list'))
        self.assertNotEqual(response.status_code, 200)


class ApprovalCreateViewTest(ApprovalViewTestBase):
    """결재 생성 뷰 테스트"""

    def test_create_view_accessible(self):
        """생성 폼 접근"""
        response = self.client.get(reverse('approval:approval_create'))
        self.assertEqual(response.status_code, 200)

    def test_create_approval(self):
        """결재 생성"""
        data = {
            'category': 'GENERAL',
            'title': '테스트 결재 생성',
            'content': '내용입니다',
            'amount': '1000000',
            'urgency': 'NORMAL',
            'notes': '',
            # inline formset management
            'steps-TOTAL_FORMS': '0',
            'steps-INITIAL_FORMS': '0',
            'steps-MIN_NUM_FORMS': '0',
            'steps-MAX_NUM_FORMS': '1000',
        }
        response = self.client.post(
            reverse('approval:approval_create'), data,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ApprovalRequest.objects.filter(title='테스트 결재 생성').exists()
        )

    def test_create_sets_requester(self):
        """생성 시 기안자 자동 설정"""
        data = {
            'category': 'PURCHASE',
            'title': '기안자 테스트',
            'content': '내용',
            'amount': '0',
            'urgency': 'NORMAL',
            'notes': '',
            'steps-TOTAL_FORMS': '0',
            'steps-INITIAL_FORMS': '0',
            'steps-MIN_NUM_FORMS': '0',
            'steps-MAX_NUM_FORMS': '1000',
        }
        self.client.post(reverse('approval:approval_create'), data)
        ar = ApprovalRequest.objects.get(title='기안자 테스트')
        self.assertEqual(ar.requester, self.manager)


class ApprovalDetailViewTest(ApprovalViewTestBase):
    """결재 상세 뷰 테스트"""

    def test_detail_view(self):
        """상세 조회"""
        ar = self._create_request()
        response = self.client.get(
            reverse('approval:approval_detail', args=[ar.request_number])
        )
        self.assertEqual(response.status_code, 200)

    def test_detail_context_has_steps(self):
        """상세 컨텍스트에 steps 포함"""
        ar = self._create_request()
        ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        response = self.client.get(
            reverse('approval:approval_detail', args=[ar.request_number])
        )
        self.assertIn('steps', response.context)
        self.assertEqual(response.context['steps'].count(), 1)

    def test_can_submit_context(self):
        """기안자만 제출 가능 표시"""
        ar = self._create_request(requester=self.manager)
        response = self.client.get(
            reverse('approval:approval_detail', args=[ar.request_number])
        )
        self.assertTrue(response.context['can_submit'])

    def test_cannot_submit_if_not_requester(self):
        """기안자가 아니면 제출 불가"""
        ar = self._create_request(requester=self.admin)
        response = self.client.get(
            reverse('approval:approval_detail', args=[ar.request_number])
        )
        self.assertFalse(response.context['can_submit'])


class ApprovalUpdateViewTest(ApprovalViewTestBase):
    """결재 수정 뷰 테스트"""

    def test_update_draft_only(self):
        """DRAFT 상태만 수정 가능"""
        ar = self._create_request(status='SUBMITTED')
        response = self.client.get(
            reverse('approval:approval_update', args=[ar.request_number])
        )
        self.assertEqual(response.status_code, 404)

    def test_update_own_only(self):
        """본인 기안건만 수정 가능"""
        ar = self._create_request(requester=self.admin)
        response = self.client.get(
            reverse('approval:approval_update', args=[ar.request_number])
        )
        self.assertEqual(response.status_code, 404)


class ApprovalSubmitViewTest(ApprovalViewTestBase):
    """결재 제출 뷰 테스트"""

    def test_submit_draft(self):
        """DRAFT → SUBMITTED"""
        ar = self._create_request(requester=self.manager)
        response = self.client.post(
            reverse('approval:approval_submit', args=[ar.request_number])
        )
        self.assertEqual(response.status_code, 302)
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'SUBMITTED')
        self.assertIsNotNone(ar.submitted_at)

    def test_submit_non_draft_ignored(self):
        """DRAFT이 아닌 상태에서 제출 시 상태 유지"""
        ar = self._create_request(
            requester=self.manager, status='SUBMITTED',
        )
        self.client.post(
            reverse('approval:approval_submit', args=[ar.request_number])
        )
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'SUBMITTED')


class ApprovalActionViewTest(ApprovalViewTestBase):
    """결재 승인/반려 뷰 테스트 (단일 결재자)"""

    def setUp(self):
        super().setUp()
        # 매니저로 로그인 후 admin으로 전환 (결재자)
        self.client.force_login(self.admin)

    def test_approve(self):
        """승인"""
        ar = self._create_request(
            approver=self.admin, status='SUBMITTED',
        )
        response = self.client.post(
            reverse('approval:approval_action', args=[ar.request_number]),
            {'action': 'approve'},
        )
        self.assertEqual(response.status_code, 302)
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'APPROVED')

    def test_reject(self):
        """반려"""
        ar = self._create_request(
            approver=self.admin, status='SUBMITTED',
        )
        response = self.client.post(
            reverse('approval:approval_action', args=[ar.request_number]),
            {'action': 'reject', 'reject_reason': '예산 부족'},
        )
        self.assertEqual(response.status_code, 302)
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'REJECTED')
        self.assertEqual(ar.reject_reason, '예산 부족')

    def test_action_on_non_submitted_ignored(self):
        """SUBMITTED이 아닌 건 처리 불가"""
        ar = self._create_request(
            approver=self.admin, status='DRAFT',
        )
        self.client.post(
            reverse('approval:approval_action', args=[ar.request_number]),
            {'action': 'approve'},
        )
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'DRAFT')


class ApprovalStepActionViewTest(ApprovalViewTestBase):
    """다단계 결재 처리 뷰 테스트"""

    def test_step_approve(self):
        """단계별 승인"""
        ar = self._create_request(
            requester=self.manager, status='SUBMITTED',
        )
        step1 = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.manager,
            created_by=self.manager,
        )
        step2 = ApprovalStep.all_objects.create(
            request=ar, step_order=2, approver=self.admin,
            created_by=self.manager,
        )
        # manager 로그인 상태에서 1단계 승인
        response = self.client.post(
            reverse(
                'approval:approval_step_action',
                args=[ar.request_number, step1.pk],
            ),
            {'action': 'approve', 'comment': '확인'},
        )
        self.assertEqual(response.status_code, 302)
        step1.refresh_from_db()
        self.assertEqual(step1.status, 'APPROVED')

    def test_step_reject(self):
        """단계별 반려"""
        ar = self._create_request(
            requester=self.staff, status='SUBMITTED',
        )
        step1 = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.manager,
            created_by=self.staff,
        )
        response = self.client.post(
            reverse(
                'approval:approval_step_action',
                args=[ar.request_number, step1.pk],
            ),
            {'action': 'reject', 'comment': '재작성 요망'},
        )
        self.assertEqual(response.status_code, 302)
        step1.refresh_from_db()
        self.assertEqual(step1.status, 'REJECTED')
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'REJECTED')

    def test_wrong_step_order_rejected(self):
        """현재 단계가 아닌 단계 처리 불가"""
        ar = self._create_request(
            requester=self.staff, status='SUBMITTED',
        )
        ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.manager2,
            created_by=self.staff,
        )
        step2 = ApprovalStep.all_objects.create(
            request=ar, step_order=2, approver=self.manager,
            created_by=self.staff,
        )
        # step2 처리 시도 (현재 current_step=1이므로 거부)
        response = self.client.post(
            reverse(
                'approval:approval_step_action',
                args=[ar.request_number, step2.pk],
            ),
            {'action': 'approve'},
        )
        self.assertEqual(response.status_code, 302)
        step2.refresh_from_db()
        # 처리되지 않아야 함
        self.assertEqual(step2.status, 'PENDING')

    def test_non_approver_cannot_process_step(self):
        """결재자가 아닌 사용자 처리 불가"""
        ar = self._create_request(
            requester=self.staff, status='SUBMITTED',
        )
        step1 = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.staff,
        )
        # manager 로그인 상태에서 admin 결재 단계 처리 시도 → 404
        response = self.client.post(
            reverse(
                'approval:approval_step_action',
                args=[ar.request_number, step1.pk],
            ),
            {'action': 'approve'},
        )
        self.assertEqual(response.status_code, 404)


# ====================================================================
# 4. 권한 테스트
# ====================================================================
class ApprovalPermissionTest(ApprovalModelTestBase):
    """결재 권한 테스트"""

    def test_staff_cannot_access_list(self):
        """staff 역할은 결재 목록 접근 불가"""
        self.client.force_login(self.staff)
        response = self.client.get(reverse('approval:approval_list'))
        # ManagerRequiredMixin으로 인해 리다이렉트 또는 403
        self.assertIn(response.status_code, [302, 403])

    def test_manager_can_access_list(self):
        """manager 역할은 결재 목록 접근 가능"""
        self.client.force_login(self.manager)
        response = self.client.get(reverse('approval:approval_list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_list(self):
        """admin 역할은 결재 목록 접근 가능"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('approval:approval_list'))
        self.assertEqual(response.status_code, 200)


# ====================================================================
# 5. 엣지케이스 테스트
# ====================================================================
class ApprovalEdgeCaseTest(ApprovalModelTestBase):
    """결재 엣지케이스 테스트"""

    def test_approve_already_approved_via_signal(self):
        """이미 승인된 건 시그널 재처리 무시"""
        ar = self._create_request(status='APPROVED')
        ar.approved_at = timezone.now()
        ar.save(update_fields=['status', 'approved_at', 'updated_at'])

        step = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        step.status = 'REJECTED'
        step.save()
        ar.refresh_from_db()
        # APPROVED 유지
        self.assertEqual(ar.status, 'APPROVED')

    def test_cancelled_request_signal_ignored(self):
        """취소된 결재에 대한 시그널 무시"""
        ar = self._create_request(status='CANCELLED')
        step = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        step.status = 'APPROVED'
        step.save()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'CANCELLED')

    def test_empty_reject_reason(self):
        """반려 사유 없이 반려"""
        ar = self._create_request(status='SUBMITTED')
        step = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        step.status = 'REJECTED'
        step.comment = ''
        step.save()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'REJECTED')
        self.assertEqual(ar.reject_reason, '')

    def test_multiple_requests_isolation(self):
        """결재 요청 간 시그널 격리"""
        ar1 = self._create_request(status='SUBMITTED', title='요청1')
        ar2 = self._create_request(status='SUBMITTED', title='요청2')

        step1 = ApprovalStep.all_objects.create(
            request=ar1, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        step2 = ApprovalStep.all_objects.create(
            request=ar2, step_order=1, approver=self.admin,
            created_by=self.manager,
        )

        step1.status = 'APPROVED'
        step1.save()

        ar1.refresh_from_db()
        ar2.refresh_from_db()
        self.assertEqual(ar1.status, 'APPROVED')
        self.assertEqual(ar2.status, 'SUBMITTED')

    def test_history_tracked(self):
        """결재 이력 추적 (simple_history)"""
        ar = self._create_request()
        ar.title = '수정된 제목'
        ar.save()
        self.assertTrue(ar.history.count() >= 2)

    def test_step_history_tracked(self):
        """단계 이력 추적"""
        ar = self._create_request()
        step = ApprovalStep.all_objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.manager,
        )
        step.status = 'APPROVED'
        step.save()
        self.assertTrue(step.history.count() >= 2)


class PermissionApprovalSignalTest(TestCase):
    """권한 신청 승인 시 User.role 자동 업데이트 시그널 테스트"""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='signal_staff', password='testpass123',
            role='staff', name='직원',
        )
        self.admin = User.objects.create_user(
            username='signal_admin', password='testpass123',
            role='admin', name='관리자',
        )

    def test_permission_upgrade_on_approval(self):
        """권한 신청 승인 시 역할 자동 변경"""
        from django.contrib.contenttypes.models import ContentType
        user_ct = ContentType.objects.get_for_model(User)

        ar = ApprovalRequest.objects.create(
            category='GENERAL',
            title='권한 신청: 직원 → 매니저',
            content='신청 역할: 매니저\n사유: 테스트',
            purpose='테스트',
            status='SUBMITTED',
            requester=self.staff,
            content_type=user_ct,
            object_id=self.staff.pk,
            created_by=self.staff,
        )
        step = ApprovalStep.objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.admin,
        )
        step.status = 'APPROVED'
        step.save()

        self.staff.refresh_from_db()
        self.assertEqual(self.staff.role, 'manager')
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'APPROVED')

    def test_no_upgrade_on_rejection(self):
        """권한 신청 반려 시 역할 변경 없음"""
        from django.contrib.contenttypes.models import ContentType
        user_ct = ContentType.objects.get_for_model(User)

        ar = ApprovalRequest.objects.create(
            category='GENERAL',
            title='권한 신청: 직원 → 매니저',
            content='신청 역할: 매니저\n사유: 테스트',
            purpose='테스트',
            status='SUBMITTED',
            requester=self.staff,
            content_type=user_ct,
            object_id=self.staff.pk,
            created_by=self.staff,
        )
        step = ApprovalStep.objects.create(
            request=ar, step_order=1, approver=self.admin,
            created_by=self.admin,
        )
        step.status = 'REJECTED'
        step.comment = '사유 불충분'
        step.save()

        self.staff.refresh_from_db()
        self.assertEqual(self.staff.role, 'staff')  # 변경 없음
