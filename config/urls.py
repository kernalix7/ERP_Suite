from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
)


def health_check(request):
    """Health check endpoint for load balancers / k8s probes.

    Returns minimal 200/503 response. Detailed component status is hidden
    to prevent information leakage about internal infrastructure.
    """
    healthy = True
    try:
        connection.ensure_connection()
    except Exception:
        healthy = False
    try:
        from django.core.cache import cache
        cache.set('_health', '1', 10)
        if cache.get('_health') != '1':
            healthy = False
    except Exception:
        pass  # cache unavailability is non-critical
    status_code = 200 if healthy else 503
    return JsonResponse({'status': 'ok' if healthy else 'error'}, status=status_code)


urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('mgmt-console-x/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('production/', include('apps.production.urls')),
    path('sales/', include('apps.sales.urls')),
    path('service/', include('apps.service.urls')),
    path('accounting/', include('apps.accounting.urls')),
    path('approval/', include('apps.approval.urls')),
    path('investment/', include('apps.investment.urls')),
    path('warranty/', include('apps.warranty.urls')),
    path('marketplace/', include('apps.marketplace.urls')),
    path('inquiry/', include('apps.inquiry.urls')),
    path('purchase/', include('apps.purchase.urls')),
    path('attendance/', include('apps.attendance.urls')),
    path('board/', include('apps.board.urls')),
    path('calendar/', include('apps.calendar_app.urls')),
    path('hr/', include('apps.hr.urls')),
    path('messenger/', include('apps.messenger.urls')),
    path('ad/', include('apps.ad.urls')),
    path('advertising/', include('apps.advertising.urls')),
    path('asset/', include('apps.asset.urls')),
    path('modules/', include('apps.module_manager.urls')),
    # Phase 15: 신규 앱 URL
    path('lms/', include('apps.lms.urls')),
    path('wiki/', include('apps.wiki.urls')),
    path('project/', include('apps.project.urls')),
    path('visitor/', include('apps.visitor.urls')),
    path('wms/', include('apps.wms.urls')),
    path('cmms/', include('apps.cmms.urls')),
    path('plm/', include('apps.plm.urls')),
    path('qms/', include('apps.qms.urls')),
    path('forecast/', include('apps.forecast.urls')),
    path('helpdesk/', include('apps.helpdesk.urls')),
    path('portal/', include('apps.portal.urls')),
    path('logistics/', include('apps.logistics.urls')),
    path('edi/', include('apps.edi.urls')),
    path('subscription/', include('apps.subscription.urls')),
    path('document/', include('apps.document.urls')),
    path('expense/', include('apps.expense.urls')),
    path('esg/', include('apps.esg.urls')),
    path('bi/', include('apps.bi.urls')),
    path('rpa/', include('apps.rpa.urls')),
    path('', include('apps.core.urls')),
    # API
    path('api/', include('apps.api.urls')),
    path('api-auth/', include('rest_framework.urls')),
    # API Documentation (Swagger/ReDoc) — DEBUG only, see below
    # Monitoring
    path('', include('django_prometheus.urls')),
]

if settings.DEBUG:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
