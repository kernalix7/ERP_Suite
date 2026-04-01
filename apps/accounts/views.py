from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, FormView, DetailView, View

from apps.core.mixins import AdminRequiredMixin
from .forms import (
    LoginForm, UserCreateForm, UserUpdateForm,
    PasswordChangeCustomForm, ProfileForm, AdminSetPasswordForm,
    PermissionRequestForm, PermissionGroupForm,
)
from .models import (
    User, PermissionGroup, PermissionGroupPermission,
    PermissionGroupMembership, UserPermission, ModulePermission,
)
from .permissions import MODULE_CHOICES, ACTION_CHOICES


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        messages.success(self.request, f'{form.get_user().name or form.get_user().username}님, 환영합니다.')
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('accounts:login')


# ── 본인 프로필 ──

class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, '프로필이 수정되었습니다.')
        return super().form_valid(form)


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = PasswordChangeCustomForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('core:dashboard')

    def form_valid(self, form):
        messages.success(self.request, '비밀번호가 변경되었습니다.')
        return super().form_valid(form)


# ── 관리자 사용자 관리 ──

class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.filter(is_active=True).prefetch_related(
            models.Prefetch(
                'permission_memberships',
                queryset=PermissionGroupMembership.objects.filter(
                    is_active=True,
                ).select_related('group'),
                to_attr='_active_memberships',
            ),
        ).order_by('name')
        q = self.request.GET.get('q', '').strip()
        role = self.request.GET.get('role', '')
        if q:
            qs = qs.filter(
                models.Q(username__icontains=q)
                | models.Q(name__icontains=q)
                | models.Q(email__icontains=q)
                | models.Q(phone__icontains=q)
            )
        if role:
            qs = qs.filter(role=role)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['filter_role'] = self.request.GET.get('role', '')
        ctx['role_choices'] = User.Role.choices
        # perm_groups 속성 주입 (prefetch 결과 활용)
        for u in ctx['users']:
            u.perm_groups = [m.group for m in getattr(u, '_active_memberships', [])]
        return ctx


class UserCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')


class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')


class AdminPasswordResetView(AdminRequiredMixin, FormView):
    """관리자가 다른 사용자 비밀번호를 재설정"""
    template_name = 'accounts/admin_password_reset.html'
    form_class = AdminSetPasswordForm
    success_url = reverse_lazy('accounts:user_list')

    def get_target_user(self):
        return get_object_or_404(User, pk=self.kwargs['pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.get_target_user()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['target_user'] = self.get_target_user()
        return ctx

    def form_valid(self, form):
        form.save()
        target = self.get_target_user()
        messages.success(self.request, f'{target.name or target.username}의 비밀번호가 재설정되었습니다.')
        return super().form_valid(form)


class PermissionRequestView(LoginRequiredMixin, FormView):
    """권한 신청 — ApprovalRequest 생성"""
    template_name = 'accounts/permission_request.html'
    form_class = PermissionRequestForm
    success_url = reverse_lazy('accounts:permission_request')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_role'] = self.request.user.get_role_display()

        # 기존 권한 신청 이력
        from apps.approval.models import ApprovalRequest
        user_ct = ContentType.objects.get_for_model(User)
        ctx['request_history'] = (
            ApprovalRequest.objects
            .filter(
                content_type=user_ct,
                object_id=self.request.user.pk,
                category='GENERAL',
            )
            .order_by('-created_at')[:10]
        )
        return ctx

    def form_valid(self, form):
        user = self.request.user

        # 관리자는 신청 불가
        if user.role == 'admin':
            messages.warning(self.request, '이미 관리자 권한을 보유하고 있습니다.')
            return self.form_invalid(form)

        requested_role = form.cleaned_data['requested_role']
        reason = form.cleaned_data['reason']

        # 동일/하위 역할 신청 방지
        role_order = {'staff': 0, 'manager': 1, 'admin': 2}
        if role_order.get(requested_role, 0) <= role_order.get(user.role, 0):
            messages.warning(self.request, '현재 역할보다 상위 역할만 신청할 수 있습니다.')
            return self.form_invalid(form)

        from apps.approval.models import ApprovalRequest
        user_ct = ContentType.objects.get_for_model(User)

        # 이미 진행중인 신청이 있으면 차단
        pending = ApprovalRequest.objects.filter(
            content_type=user_ct,
            object_id=user.pk,
            status__in=['DRAFT', 'SUBMITTED'],
        ).exists()
        if pending:
            messages.warning(self.request, '이미 진행 중인 권한 신청이 있습니다.')
            return self.form_invalid(form)

        role_display = dict(User.Role.choices).get(requested_role, requested_role)
        ApprovalRequest.objects.create(
            category='GENERAL',
            title=f'권한 신청: {user.get_role_display()} → {role_display}',
            content=f'신청 역할: {role_display}\n사유: {reason}',
            purpose=reason,
            amount=0,
            status='SUBMITTED',
            requester=user,
            content_type=user_ct,
            object_id=user.pk,
        )
        messages.success(self.request, f'{role_display} 권한 신청이 접수되었습니다.')
        return super().form_valid(form)


# ── 권한 그룹 관리 ──

class PermissionGroupListView(AdminRequiredMixin, ListView):
    model = PermissionGroup
    template_name = 'accounts/permission_group_list.html'
    context_object_name = 'groups'

    def get_queryset(self):
        return (
            PermissionGroup.objects.filter(is_active=True)
            .annotate(
                member_count=models.Count(
                    'memberships',
                    filter=models.Q(memberships__is_active=True),
                ),
                perm_count=models.Count(
                    'group_permissions',
                    filter=models.Q(group_permissions__is_active=True),
                ),
            )
            .order_by('-priority', 'name')
        )


class PermissionGroupCreateView(AdminRequiredMixin, CreateView):
    model = PermissionGroup
    form_class = PermissionGroupForm
    template_name = 'accounts/permission_group_form.html'
    success_url = reverse_lazy('accounts:permission_group_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['modules'] = MODULE_CHOICES
        ctx['actions'] = ACTION_CHOICES
        ctx['assigned_perms'] = set()
        ctx['members'] = []
        ctx['all_users'] = User.objects.filter(is_active=True).order_by('name')
        return ctx

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        self._save_permissions(self.object)
        self._save_members(self.object)
        messages.success(self.request, f'권한 그룹 "{self.object.name}"이(가) 생성되었습니다.')
        return response

    def _save_permissions(self, group):
        selected = self.request.POST.getlist('permissions')
        valid_codenames = {
            f'{m}.{a}' for m, _ in MODULE_CHOICES for a, _ in ACTION_CHOICES
        }
        selected = [c for c in selected if c in valid_codenames]
        all_perms = ModulePermission.objects.filter(
            codename__in=selected, is_active=True,
        )
        for perm in all_perms:
            PermissionGroupPermission.all_objects.update_or_create(
                group=group, permission=perm,
                defaults={'is_active': True},
            )

    def _save_members(self, group):
        user_ids = self.request.POST.getlist('members')
        valid_user_ids = set(
            User.objects.filter(is_active=True).values_list('pk', flat=True)
        )
        for uid in user_ids:
            try:
                uid_int = int(uid)
            except (ValueError, TypeError):
                continue
            if uid_int not in valid_user_ids:
                continue
            PermissionGroupMembership.all_objects.update_or_create(
                user_id=uid_int, group=group,
                defaults={'assigned_by': self.request.user, 'is_active': True},
            )


class PermissionGroupUpdateView(AdminRequiredMixin, UpdateView):
    model = PermissionGroup
    form_class = PermissionGroupForm
    template_name = 'accounts/permission_group_form.html'
    success_url = reverse_lazy('accounts:permission_group_list')

    def get_queryset(self):
        return PermissionGroup.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['modules'] = MODULE_CHOICES
        ctx['actions'] = ACTION_CHOICES
        ctx['assigned_perms'] = set(
            PermissionGroupPermission.objects
            .filter(group=self.object, is_active=True)
            .values_list('permission__codename', flat=True)
        )
        ctx['members'] = list(
            PermissionGroupMembership.objects
            .filter(group=self.object, is_active=True)
            .values_list('user_id', flat=True)
        )
        ctx['all_users'] = User.objects.filter(is_active=True).order_by('name')
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            self._sync_permissions(self.object)
            self._sync_members(self.object)
        from apps.accounts.permission_utils import invalidate_group_perm_cache
        invalidate_group_perm_cache(self.object.pk)
        messages.success(self.request, f'권한 그룹 "{self.object.name}"이(가) 수정되었습니다.')
        return response

    def _sync_permissions(self, group):
        selected_raw = set(self.request.POST.getlist('permissions'))
        valid_codenames = {
            f'{m}.{a}' for m, _ in MODULE_CHOICES for a, _ in ACTION_CHOICES
        }
        selected = selected_raw & valid_codenames
        # all_objects: soft delete된 레코드도 포함하여 unique 충돌 방지
        existing = dict(
            PermissionGroupPermission.all_objects
            .filter(group=group)
            .values_list('permission__codename', 'pk')
        )
        # 삭제 (soft delete)
        for codename, pk in existing.items():
            if codename not in selected:
                PermissionGroupPermission.all_objects.filter(pk=pk).update(is_active=False)
        # 추가 또는 재활성화
        for codename in selected:
            if codename not in existing:
                perm = ModulePermission.objects.filter(codename=codename, is_active=True).first()
                if perm:
                    PermissionGroupPermission.all_objects.update_or_create(
                        group=group, permission=perm,
                        defaults={'is_active': True},
                    )
            else:
                # 재활성화
                PermissionGroupPermission.all_objects.filter(pk=existing[codename]).update(is_active=True)

    def _sync_members(self, group):
        selected_ids = set()
        for uid in self.request.POST.getlist('members'):
            try:
                selected_ids.add(int(uid))
            except (ValueError, TypeError):
                continue
        valid_user_ids = set(
            User.objects.filter(is_active=True).values_list('pk', flat=True)
        )
        selected_ids &= valid_user_ids
        # all_objects: soft delete된 레코드도 포함하여 unique 충돌 방지
        existing = dict(
            PermissionGroupMembership.all_objects
            .filter(group=group)
            .values_list('user_id', 'pk')
        )
        for uid, pk in existing.items():
            if uid not in selected_ids:
                PermissionGroupMembership.all_objects.filter(pk=pk).update(is_active=False)
        for uid in selected_ids:
            if uid not in existing:
                PermissionGroupMembership.all_objects.update_or_create(
                    user_id=uid, group=group,
                    defaults={'assigned_by': self.request.user, 'is_active': True},
                )
            else:
                PermissionGroupMembership.all_objects.filter(pk=existing[uid]).update(is_active=True)


# ── 사용자별 권한 관리 ──

class UserPermissionView(AdminRequiredMixin, DetailView):
    """사용자별 권한 그룹 + 직접 권한 관리"""
    model = User
    template_name = 'accounts/user_permissions.html'
    context_object_name = 'target_user'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        target = self.object
        ctx['modules'] = MODULE_CHOICES
        ctx['actions'] = ACTION_CHOICES
        ctx['all_groups'] = PermissionGroup.objects.filter(is_active=True).order_by('-priority', 'name')
        ctx['user_group_ids'] = set(
            PermissionGroupMembership.objects
            .filter(user=target, is_active=True)
            .values_list('group_id', flat=True)
        )
        # 직접 권한: {codename: grant}
        ctx['direct_perms'] = dict(
            UserPermission.objects
            .filter(user=target, is_active=True)
            .values_list('permission__codename', 'grant')
        )
        # 그룹으로부터 받은 권한 (표시용)
        ctx['group_perms'] = set(
            ModulePermission.objects
            .filter(
                is_active=True,
                group_assignments__group__memberships__user=target,
                group_assignments__group__memberships__is_active=True,
                group_assignments__group__is_active=True,
                group_assignments__is_active=True,
            )
            .values_list('codename', flat=True)
        )
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        target = self.object

        valid_codenames = {
            f'{m}.{a}' for m, _ in MODULE_CHOICES for a, _ in ACTION_CHOICES
        }

        with transaction.atomic():
            # 그룹 멤버십 동기화
            selected_group_ids = set()
            for gid in request.POST.getlist('groups'):
                try:
                    selected_group_ids.add(int(gid))
                except (ValueError, TypeError):
                    continue
            # 존재하는 활성 그룹만 허용
            valid_group_ids = set(
                PermissionGroup.objects.filter(
                    is_active=True, pk__in=selected_group_ids,
                ).values_list('pk', flat=True)
            )
            selected_group_ids &= valid_group_ids

            # all_objects: soft delete된 레코드도 포함하여 unique 충돌 방지
            existing_memberships = dict(
                PermissionGroupMembership.all_objects
                .filter(user=target)
                .values_list('group_id', 'pk')
            )
            for gid, pk in existing_memberships.items():
                if gid not in selected_group_ids:
                    PermissionGroupMembership.all_objects.filter(pk=pk).update(is_active=False)
            for gid in selected_group_ids:
                if gid not in existing_memberships:
                    PermissionGroupMembership.all_objects.update_or_create(
                        user=target, group_id=gid,
                        defaults={'assigned_by': request.user, 'is_active': True},
                    )
                else:
                    PermissionGroupMembership.all_objects.filter(pk=existing_memberships[gid]).update(is_active=True)

            # 직접 권한 동기화 — codename 형식 검증
            grant_perms = set(request.POST.getlist('grant_perms')) & valid_codenames
            deny_perms = set(request.POST.getlist('deny_perms')) & valid_codenames
            # grant와 deny가 동시에 지정된 codename은 deny 우선
            grant_perms -= deny_perms

            # 기존 직접 권한 비활성화 후 재설정 (all_objects로 soft delete 포함)
            UserPermission.all_objects.filter(user=target).update(is_active=False)
            for codename in grant_perms:
                perm = ModulePermission.objects.filter(codename=codename, is_active=True).first()
                if perm:
                    UserPermission.all_objects.update_or_create(
                        user=target, permission=perm,
                        defaults={'grant': True, 'is_active': True, 'assigned_by': request.user},
                    )
            for codename in deny_perms:
                perm = ModulePermission.objects.filter(codename=codename, is_active=True).first()
                if perm:
                    UserPermission.all_objects.update_or_create(
                        user=target, permission=perm,
                        defaults={'grant': False, 'is_active': True, 'assigned_by': request.user},
                    )

        # update()는 시그널을 트리거하지 않으므로 명시적 캐시 무효화
        from apps.accounts.permission_utils import invalidate_user_perm_cache
        invalidate_user_perm_cache(target.pk)

        messages.success(request, f'{target.name or target.username}의 권한이 수정되었습니다.')
        return HttpResponseRedirect(
            reverse_lazy('accounts:user_permissions', kwargs={'pk': target.pk})
        )


# ── 권한 그룹 삭제 (soft delete) ──

class PermissionGroupDeleteView(AdminRequiredMixin, View):
    """권한 그룹 soft delete — 멤버십과 그룹-권한 매핑도 함께 비활성화"""

    def post(self, request, pk):
        group = get_object_or_404(PermissionGroup, pk=pk, is_active=True)
        # 캐시 무효화를 위해 멤버 ID를 미리 수집
        member_ids = list(
            PermissionGroupMembership.objects
            .filter(group=group, is_active=True)
            .values_list('user_id', flat=True)
        )
        with transaction.atomic():
            PermissionGroupPermission.objects.filter(group=group).update(is_active=False)
            PermissionGroupMembership.objects.filter(group=group).update(is_active=False)
            group.is_active = False
            group.save(update_fields=['is_active'])
        # update()는 시그널을 트리거하지 않으므로 멤버 캐시 명시적 무효화
        from apps.accounts.permission_utils import invalidate_user_perm_cache
        for uid in member_ids:
            invalidate_user_perm_cache(uid)
        messages.success(request, f'권한 그룹 "{group.name}"이(가) 삭제되었습니다.')
        return HttpResponseRedirect(reverse_lazy('accounts:permission_group_list'))
