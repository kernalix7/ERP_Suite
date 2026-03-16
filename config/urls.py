from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
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
    path('', include('apps.core.urls')),
    # API
    path('api/', include('apps.api.urls')),
    path('api-auth/', include('rest_framework.urls')),
    # Monitoring
    path('', include('django_prometheus.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
