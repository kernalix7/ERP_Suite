from django.urls import path

from . import views
from .audit import (
    AuditDashboardView, AccessLogView, DataChangeLogView,
    LoginHistoryView, AuditAccessLogView,
)
from .backup import BackupView, BackupDownloadView
from .trash import TrashListView, RestoreView
from .attachment_views import AttachmentUploadView, AttachmentDeleteView, AttachmentListView
from .report import DataReportView

app_name = 'core'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    # 데이터 입력 가이드
    path('report/', DataReportView.as_view(), name='data_report'),
    # 백업
    path('backup/', BackupView.as_view(), name='backup'),
    path('backup/download/', BackupDownloadView.as_view(), name='backup_download'),
    # 휴지통
    path('trash/', TrashListView.as_view(), name='trash'),
    path('trash/restore/<str:app_label>/<str:model_name>/<int:pk>/',
         RestoreView.as_view(), name='restore'),
    # 증빙 첨부
    path('attachments/', AttachmentListView.as_view(), name='attachment_list'),
    path('attachments/upload/<str:app_label>/<str:model_name>/<int:pk>/',
         AttachmentUploadView.as_view(), name='attachment_upload'),
    path('attachments/<int:pk>/delete/',
         AttachmentDeleteView.as_view(), name='attachment_delete'),
    # 감사 증적
    path('audit/', AuditDashboardView.as_view(), name='audit_dashboard'),
    path('audit/access-log/', AccessLogView.as_view(), name='audit_access_log'),
    path('audit/data-changes/', DataChangeLogView.as_view(), name='audit_data_changes'),
    path('audit/login-history/', LoginHistoryView.as_view(), name='audit_login_history'),
    path('audit/audit-log/', AuditAccessLogView.as_view(), name='audit_audit_log'),
]
