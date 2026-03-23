"""감사 증적 관리 (Audit Trail) — ISMS 증적 / 회계 증빙 / 시스템 감사"""
import logging
import re
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import models
from django.utils import timezone
from django.views.generic import ListView, TemplateView
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel

User = get_user_model()
logger = logging.getLogger('audit')


# ─────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────

class AuditAccessLog(models.Model):
    """감사 증적 열람 기록 — 누가 어떤 감사 데이터를 언제 열람했는지"""

    class Section(models.TextChoices):
        DASHBOARD = 'DASHBOARD', '감사 대시보드'
        ACCESS_LOG = 'ACCESS_LOG', '시스템 접근 로그'
        DATA_CHANGE = 'DATA_CHANGE', '데이터 변경 이력'
        LOGIN_HISTORY = 'LOGIN_HISTORY', '로그인/보안 이벤트'
        AUDIT_LOG = 'AUDIT_LOG', '감사 열람 기록'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='열람자',
        on_delete=models.PROTECT,
        related_name='audit_access_logs',
    )
    section = models.CharField('열람 섹션', max_length=30, choices=Section.choices)
    ip_address = models.GenericIPAddressField('IP 주소', null=True, blank=True)
    user_agent = models.TextField('User-Agent', blank=True)
    query_params = models.TextField('조회 조건', blank=True)
    accessed_at = models.DateTimeField('열람일시', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = '감사 열람 기록'
        verbose_name_plural = '감사 열람 기록'
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['user', 'accessed_at'], name='idx_auditlog_user_date'),
            models.Index(fields=['section'], name='idx_auditlog_section'),
        ]

    def __str__(self):
        return f'{self.user} → {self.get_section_display()} ({self.accessed_at:%Y-%m-%d %H:%M})'


# ─────────────────────────────────────────────
# Mixin
# ─────────────────────────────────────────────

class AuditRequiredMixin(LoginRequiredMixin):
    """감사권한(is_auditor) 확인 + 열람 기록 자동 저장"""

    audit_section = ''  # 하위 클래스에서 지정

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_auditor:
            raise PermissionDenied('감사 증적 열람 권한이 없습니다. 관리자에게 감사권한을 요청하세요.')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self._log_audit_access(request)
        return super().get(request, *args, **kwargs)

    def _log_audit_access(self, request):
        AuditAccessLog.objects.create(
            user=request.user,
            section=self.audit_section,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            query_params=request.GET.urlencode()[:500],
        )
        logger.info(
            'AUDIT_ACCESS user=%s section=%s ip=%s',
            request.user.username,
            self.audit_section,
            self._get_client_ip(request),
        )

    @staticmethod
    def _get_client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# ─────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────

class AuditDashboardView(AuditRequiredMixin, TemplateView):
    """감사 증적 대시보드"""
    template_name = 'audit/dashboard.html'
    audit_section = AuditAccessLog.Section.DASHBOARD

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)

        # 오늘 접근 로그 수 (파일 기반)
        ctx['today_access_count'] = self._count_today_access(today)

        # 최근 7일 데이터 변경 건수
        ctx['week_changes'] = self._count_recent_changes(week_ago)

        # 로그인 실패 (axes)
        try:
            from axes.models import AccessAttempt
            ctx['failed_logins_today'] = AccessAttempt.objects.filter(
                attempt_time__date=today,
            ).count()
            ctx['locked_accounts'] = AccessAttempt.objects.filter(
                attempt_time__gte=now - timedelta(hours=1),
                failures_since_start__gte=settings.AXES_FAILURE_LIMIT,
            ).values('username').distinct().count()
        except Exception:
            ctx['failed_logins_today'] = 0
            ctx['locked_accounts'] = 0

        # 감사 열람 기록 최근 5건
        ctx['recent_audit_access'] = AuditAccessLog.objects.select_related(
            'user'
        ).order_by('-accessed_at')[:5]

        # 감사권한 보유자 수
        ctx['auditor_count'] = User.objects.filter(is_auditor=True, is_active=True).count()

        return ctx

    @staticmethod
    def _count_today_access(today):
        log_path = Path(settings.BASE_DIR) / 'local' / 'erp.log'
        if not log_path.exists():
            return 0
        today_str = today.strftime('%Y-%m-%d')
        count = 0
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if today_str in line and 'access' in line.lower():
                        count += 1
        except OSError:
            pass
        return count

    @staticmethod
    def _count_recent_changes(since):
        """simple_history 테이블에서 최근 변경 건수 집계"""
        from django.apps import apps
        total = 0
        for model in apps.get_models():
            if hasattr(model, 'history'):
                try:
                    total += model.history.filter(history_date__gte=since).count()
                except Exception:
                    pass
        return total


class AccessLogView(AuditRequiredMixin, TemplateView):
    """시스템 접근 로그 — erp.log 파싱"""
    template_name = 'audit/access_log.html'
    audit_section = AuditAccessLog.Section.ACCESS_LOG

    LOG_PATTERN = re.compile(
        r'\[(?P<ts>[^\]]+)\]\s+INFO\s+access\s+'
        r'(?P<user>\S+)\s+(?P<method>\S+)\s+(?P<path>\S+)\s+'
        r'(?P<status>\d+)\s+(?P<duration>\d+)ms'
    )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        log_path = Path(settings.BASE_DIR) / 'local' / 'erp.log'
        entries = []

        filter_user = self.request.GET.get('user', '')
        filter_path = self.request.GET.get('path', '')
        filter_status = self.request.GET.get('status', '')

        if log_path.exists():
            try:
                lines = log_path.read_text(
                    encoding='utf-8', errors='replace'
                ).splitlines()
                for line in reversed(lines):
                    m = self.LOG_PATTERN.match(line)
                    if not m:
                        continue
                    entry = m.groupdict()
                    if filter_user and filter_user not in entry['user']:
                        continue
                    if filter_path and filter_path not in entry['path']:
                        continue
                    if filter_status and entry['status'] != filter_status:
                        continue
                    entries.append(entry)
                    if len(entries) >= 500:
                        break
            except OSError:
                pass

        paginator = Paginator(entries, 50)
        page = self.request.GET.get('page', 1)
        ctx['page_obj'] = paginator.get_page(page)
        ctx['filter_user'] = filter_user
        ctx['filter_path'] = filter_path
        ctx['filter_status'] = filter_status
        ctx['total_entries'] = len(entries)
        return ctx


class DataChangeLogView(AuditRequiredMixin, TemplateView):
    """데이터 변경 이력 — simple_history 통합 조회"""
    template_name = 'audit/data_change_log.html'
    audit_section = AuditAccessLog.Section.DATA_CHANGE

    TRACKED_MODELS = [
        ('accounts', 'User', '사용자'),
        ('inventory', 'Product', '제품'),
        ('inventory', 'StockMovement', '입출고'),
        ('sales', 'Order', '주문'),
        ('sales', 'Quotation', '견적'),
        ('sales', 'Partner', '거래처'),
        ('purchase', 'PurchaseOrder', '발주'),
        ('production', 'ProductionPlan', '생산계획'),
        ('production', 'WorkOrder', '작업지시'),
        ('accounting', 'Voucher', '전표'),
        ('accounting', 'TaxInvoice', '세금계산서'),
        ('accounting', 'Payment', '입출금'),
        ('approval', 'ApprovalRequest', '결재'),
        ('hr', 'EmployeeProfile', '직원정보'),
        ('attendance', 'LeaveRequest', '휴가신청'),
        ('investment', 'Investment', '투자'),
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.apps import apps

        filter_model = self.request.GET.get('model', '')
        filter_user = self.request.GET.get('user', '')
        filter_type = self.request.GET.get('type', '')  # +, ~, -

        entries = []
        for app_label, model_name, display in self.TRACKED_MODELS:
            if filter_model and model_name != filter_model:
                continue
            try:
                model = apps.get_model(app_label, model_name)
                if not hasattr(model, 'history'):
                    continue
                qs = model.history.select_related('history_user').order_by('-history_date')
                if filter_user:
                    qs = qs.filter(history_user__username__icontains=filter_user)
                if filter_type:
                    qs = qs.filter(history_type=filter_type)
                for record in qs[:100]:
                    entries.append({
                        'model_name': display,
                        'model_key': model_name,
                        'object_id': record.history_object.pk if hasattr(record, 'history_object') else record.pk,
                        'object_repr': str(record.instance) if hasattr(record, 'instance') else str(record.pk),
                        'history_type': record.history_type,
                        'history_type_display': {'+': '생성', '~': '수정', '-': '삭제'}.get(record.history_type, '?'),
                        'history_user': str(record.history_user) if record.history_user else '(시스템)',
                        'history_date': record.history_date,
                    })
            except Exception:
                continue

        entries.sort(key=lambda x: x['history_date'], reverse=True)
        entries = entries[:500]

        paginator = Paginator(entries, 50)
        page = self.request.GET.get('page', 1)
        ctx['page_obj'] = paginator.get_page(page)
        ctx['tracked_models'] = self.TRACKED_MODELS
        ctx['filter_model'] = filter_model
        ctx['filter_user'] = filter_user
        ctx['filter_type'] = filter_type
        ctx['total_entries'] = len(entries)
        return ctx


class LoginHistoryView(AuditRequiredMixin, TemplateView):
    """로그인/보안 이벤트 — django-axes"""
    template_name = 'audit/login_history.html'
    audit_section = AuditAccessLog.Section.LOGIN_HISTORY

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filter_user = self.request.GET.get('user', '')
        filter_result = self.request.GET.get('result', '')  # success, fail

        entries = []
        try:
            from axes.models import AccessAttempt, AccessLog
            # 실패 기록
            if filter_result != 'success':
                qs = AccessAttempt.objects.order_by('-attempt_time')
                if filter_user:
                    qs = qs.filter(username__icontains=filter_user)
                for a in qs[:300]:
                    entries.append({
                        'username': a.username,
                        'ip_address': a.ip_address,
                        'user_agent': a.user_agent[:80] if a.user_agent else '',
                        'timestamp': a.attempt_time,
                        'result': 'FAIL',
                        'failures': a.failures_since_start,
                    })

            # 성공 기록
            if filter_result != 'fail':
                qs = AccessLog.objects.order_by('-attempt_time')
                if filter_user:
                    qs = qs.filter(username__icontains=filter_user)
                for a in qs[:300]:
                    entries.append({
                        'username': a.username,
                        'ip_address': a.ip_address,
                        'user_agent': a.user_agent[:80] if a.user_agent else '',
                        'timestamp': a.attempt_time,
                        'result': 'OK',
                        'failures': 0,
                    })
        except Exception:
            pass

        entries.sort(key=lambda x: x['timestamp'], reverse=True)
        entries = entries[:500]

        paginator = Paginator(entries, 50)
        page = self.request.GET.get('page', 1)
        ctx['page_obj'] = paginator.get_page(page)
        ctx['filter_user'] = filter_user
        ctx['filter_result'] = filter_result
        ctx['total_entries'] = len(entries)
        return ctx


class AuditAccessLogView(AuditRequiredMixin, ListView):
    """감사 열람 기록 (메타 감사) — 누가 이 시스템을 열람했는지"""
    template_name = 'audit/audit_access_log.html'
    audit_section = AuditAccessLog.Section.AUDIT_LOG
    model = AuditAccessLog
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        qs = AuditAccessLog.objects.select_related('user').order_by('-accessed_at')
        filter_user = self.request.GET.get('user', '')
        filter_section = self.request.GET.get('section', '')
        if filter_user:
            qs = qs.filter(user__username__icontains=filter_user)
        if filter_section:
            qs = qs.filter(section=filter_section)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_user'] = self.request.GET.get('user', '')
        ctx['filter_section'] = self.request.GET.get('section', '')
        ctx['section_choices'] = AuditAccessLog.Section.choices
        return ctx
