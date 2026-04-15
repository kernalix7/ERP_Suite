"""Security views: 2FA setup/verify, password expiry, IP whitelist, active sessions."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.contrib.sessions.backends.db import SessionStore
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView

from apps.core.mixins import AdminRequiredMixin
from .forms import INPUT_CLASS, TwoFactorSetupForm, TwoFactorVerifyForm, IPWhitelistForm
from .models import IPWhitelist, PasswordHistory, TOTPDevice, UserSession
from .totp import generate_backup_codes, generate_secret, get_totp_uri, verify_totp


# ═══════════════════════════════════════════════════
# 2FA Setup / Verify / Backup Codes
# ═══════════════════════════════════════════════════

class TwoFactorSetupView(LoginRequiredMixin, TemplateView):
    """2FA 설정 — QR코드 URL 표시 + 6자리 코드 검증"""
    template_name = 'accounts/two_factor_setup.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        device, created = TOTPDevice.all_objects.get_or_create(
            user=self.request.user,
            defaults={'secret_key': generate_secret(), 'is_active': True},
        )
        if not created and not device.is_active:
            device.is_active = True
            device.secret_key = generate_secret()
            device.is_verified = False
            device.backup_codes = []
            device.save()
        if not device.is_verified:
            ctx['totp_uri'] = get_totp_uri(device.secret_key, self.request.user.username)
            ctx['secret_key'] = device.secret_key
        ctx['device'] = device
        ctx['form'] = TwoFactorSetupForm()
        return ctx

    def post(self, request, *args, **kwargs):
        form = TwoFactorSetupForm(request.POST)
        if not form.is_valid():
            return self.get(request, *args, **kwargs)

        code = form.cleaned_data['code']
        try:
            device = request.user.totp_device
        except TOTPDevice.DoesNotExist:
            messages.error(request, '2FA 장치가 설정되지 않았습니다.')
            return redirect('accounts:two_factor_setup')

        if verify_totp(device.secret_key, code):
            device.is_verified = True
            device.backup_codes = generate_backup_codes()
            device.save(update_fields=['is_verified', 'backup_codes', 'updated_at'])
            request.session['2fa_verified'] = True
            messages.success(request, '2단계 인증이 활성화되었습니다.')
            return redirect('accounts:two_factor_backup_codes')
        else:
            messages.error(request, '인증 코드가 올바르지 않습니다. 다시 시도하세요.')
            return redirect('accounts:two_factor_setup')


class TwoFactorVerifyView(LoginRequiredMixin, TemplateView):
    """2FA 검증 — 로그인 후 6자리 코드 입력"""
    template_name = 'accounts/two_factor_verify.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = TwoFactorVerifyForm()
        return ctx

    def post(self, request, *args, **kwargs):
        form = TwoFactorVerifyForm(request.POST)
        if not form.is_valid():
            ctx = self.get_context_data()
            ctx['form'] = form
            return self.render_to_response(ctx)

        code = form.cleaned_data['code']
        try:
            device = request.user.totp_device
        except TOTPDevice.DoesNotExist:
            messages.error(request, '2FA가 설정되지 않았습니다.')
            return redirect('accounts:login')

        if verify_totp(device.secret_key, code):
            request.session['2fa_verified'] = True
            messages.success(request, '2단계 인증이 완료되었습니다.')
            return redirect(settings.LOGIN_REDIRECT_URL)

        # Try backup code
        if device.verify_backup_code(code):
            request.session['2fa_verified'] = True
            messages.success(request, '백업코드로 인증되었습니다. 백업코드를 재발급하세요.')
            return redirect(settings.LOGIN_REDIRECT_URL)

        messages.error(request, '인증 코드가 올바르지 않습니다.')
        return redirect('accounts:two_factor_verify')


class TwoFactorBackupCodesView(LoginRequiredMixin, TemplateView):
    """백업코드 표시"""
    template_name = 'accounts/backup_codes.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            device = self.request.user.totp_device
            ctx['backup_codes'] = device.backup_codes
        except TOTPDevice.DoesNotExist:
            ctx['backup_codes'] = []
        return ctx


class TwoFactorDisableView(LoginRequiredMixin, View):
    """2FA 비활성화"""

    def post(self, request):
        try:
            device = request.user.totp_device
            device.is_verified = False
            device.is_active = False
            device.backup_codes = []
            device.save(update_fields=['is_verified', 'is_active', 'backup_codes', 'updated_at'])
            if '2fa_verified' in request.session:
                del request.session['2fa_verified']
            messages.success(request, '2단계 인증이 비활성화되었습니다.')
        except TOTPDevice.DoesNotExist:
            messages.info(request, '2단계 인증이 설정되어 있지 않습니다.')
        return redirect('accounts:profile')


class TwoFactorRegenerateBackupView(LoginRequiredMixin, View):
    """백업코드 재발급"""

    def post(self, request):
        try:
            device = request.user.totp_device
            device.backup_codes = generate_backup_codes()
            device.save(update_fields=['backup_codes', 'updated_at'])
            messages.success(request, '백업코드가 재발급되었습니다.')
            return redirect('accounts:two_factor_backup_codes')
        except TOTPDevice.DoesNotExist:
            messages.error(request, '2FA가 설정되지 않았습니다.')
            return redirect('accounts:two_factor_setup')


# ═══════════════════════════════════════════════════
# Password Expiry
# ═══════════════════════════════════════════════════

class PasswordExpiredView(LoginRequiredMixin, PasswordChangeView):
    """비밀번호 만료 — 강제 변경"""
    template_name = 'accounts/password_expired.html'
    success_url = reverse_lazy('core:dashboard')

    def get_form_class(self):
        from .forms import PasswordChangeCustomForm
        return PasswordChangeCustomForm

    def form_valid(self, form):
        response = super().form_valid(form)
        # Record password history
        PasswordHistory.objects.create(
            user=self.request.user,
            password_hash=make_password(form.cleaned_data['new_password1']),
        )
        messages.success(self.request, '비밀번호가 변경되었습니다.')
        return response


# ═══════════════════════════════════════════════════
# IP Whitelist Management
# ═══════════════════════════════════════════════════

class IPWhitelistListView(AdminRequiredMixin, ListView):
    """IP 화이트리스트 목록"""
    model = IPWhitelist
    template_name = 'accounts/ip_whitelist_list.html'
    context_object_name = 'whitelist'
    paginate_by = 20

    def get_queryset(self):
        return IPWhitelist.objects.filter(is_active=True).order_by('scope', 'ip_address')


class IPWhitelistCreateView(AdminRequiredMixin, CreateView):
    """IP 화이트리스트 추가"""
    model = IPWhitelist
    form_class = IPWhitelistForm
    template_name = 'accounts/ip_whitelist_form.html'
    success_url = reverse_lazy('accounts:ip_whitelist_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'IP 화이트리스트가 추가되었습니다.')
        return super().form_valid(form)


class IPWhitelistDeleteView(AdminRequiredMixin, View):
    """IP 화이트리스트 삭제 (soft delete)"""

    def post(self, request, pk):
        entry = get_object_or_404(IPWhitelist, pk=pk, is_active=True)
        entry.is_active = False
        entry.save(update_fields=['is_active', 'updated_at'])
        messages.success(request, f'IP {entry.ip_address} 이(가) 제거되었습니다.')
        return HttpResponseRedirect(reverse_lazy('accounts:ip_whitelist_list'))


# ═══════════════════════════════════════════════════
# Active Sessions
# ═══════════════════════════════════════════════════

class ActiveSessionsView(LoginRequiredMixin, ListView):
    """활성 세션 목록"""
    model = UserSession
    template_name = 'accounts/active_sessions.html'
    context_object_name = 'sessions'
    paginate_by = 20

    def get_queryset(self):
        return UserSession.objects.filter(
            user=self.request.user, is_active=True,
        ).order_by('-last_activity')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_session_key'] = self.request.session.session_key
        return ctx


class TerminateSessionView(LoginRequiredMixin, View):
    """특정 세션 강제 종료"""

    def post(self, request, pk):
        session_obj = get_object_or_404(
            UserSession, pk=pk, user=request.user, is_active=True,
        )
        # Do not allow terminating current session via this view
        if session_obj.session_key == request.session.session_key:
            messages.warning(request, '현재 세션은 여기서 종료할 수 없습니다. 로그아웃을 사용하세요.')
            return redirect('accounts:active_sessions')

        # Delete the actual Django session
        try:
            store = SessionStore(session_key=session_obj.session_key)
            store.delete()
        except Exception:
            pass
        session_obj.is_active = False
        session_obj.save(update_fields=['is_active', 'updated_at'])
        messages.success(request, '세션이 종료되었습니다.')
        return redirect('accounts:active_sessions')


class TerminateAllSessionsView(LoginRequiredMixin, View):
    """현재 세션 제외 모든 세션 종료"""

    def post(self, request):
        current_key = request.session.session_key
        sessions = UserSession.objects.filter(
            user=request.user, is_active=True,
        ).exclude(session_key=current_key)
        for s in sessions:
            try:
                store = SessionStore(session_key=s.session_key)
                store.delete()
            except Exception:
                pass
            s.is_active = False
            s.save(update_fields=['is_active', 'updated_at'])
        messages.success(request, '다른 모든 세션이 종료되었습니다.')
        return redirect('accounts:active_sessions')
