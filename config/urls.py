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
    """Health check endpoint for load balancers / k8s probes."""
    checks = {'status': 'ok'}
    try:
        connection.ensure_connection()
        checks['database'] = 'ok'
    except Exception:
        checks['database'] = 'error'
        checks['status'] = 'degraded'
    try:
        from django.core.cache import cache
        cache.set('_health', '1', 10)
        if cache.get('_health') == '1':
            checks['cache'] = 'ok'
        else:
            checks['cache'] = 'error'
            checks['status'] = 'degraded'
    except Exception:
        checks['cache'] = 'unavailable'
    status_code = 200 if checks['status'] == 'ok' else 503
    return JsonResponse(checks, status=status_code)


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
    path('', include('apps.core.urls')),
    # API
    path('api/', include('apps.api.urls')),
    path('api-auth/', include('rest_framework.urls')),
    # API Documentation (Swagger/ReDoc)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    # Monitoring
    path('', include('django_prometheus.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
