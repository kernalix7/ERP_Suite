from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.db import models
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, FormView

from apps.core.mixins import AdminRequiredMixin
from .forms import (
    LoginForm, UserCreateForm, UserUpdateForm,
    PasswordChangeCustomForm, ProfileForm, AdminSetPasswordForm,
)
from .models import User


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
        qs = User.objects.filter(is_active=True).order_by('name')
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
