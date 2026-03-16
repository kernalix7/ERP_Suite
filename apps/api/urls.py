from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from apps.api.views import (
    ProductViewSet, CategoryViewSet, WarehouseViewSet,
    StockMovementViewSet, PartnerViewSet, CustomerViewSet,
    OrderViewSet, OrderItemViewSet, BOMViewSet, BOMItemViewSet,
    ProductionPlanViewSet, WorkOrderViewSet, TaxInvoiceViewSet,
)

router = DefaultRouter()
router.register('products', ProductViewSet)
router.register('categories', CategoryViewSet)
router.register('warehouses', WarehouseViewSet)
router.register('stock-movements', StockMovementViewSet)
router.register('partners', PartnerViewSet)
router.register('customers', CustomerViewSet)
router.register('orders', OrderViewSet)
router.register('order-items', OrderItemViewSet)
router.register('boms', BOMViewSet)
router.register('bom-items', BOMItemViewSet)
router.register('production-plans', ProductionPlanViewSet)
router.register('work-orders', WorkOrderViewSet)
router.register('tax-invoices', TaxInvoiceViewSet)

urlpatterns = router.urls + [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]
