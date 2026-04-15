from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from apps.api.views import (
    ProductViewSet, CategoryViewSet, WarehouseViewSet,
    StockMovementViewSet, SerialNumberViewSet,
    PartnerViewSet, CustomerViewSet,
    OrderViewSet, OrderItemViewSet, BOMViewSet, BOMItemViewSet,
    ProductionPlanViewSet, WorkOrderViewSet, TaxInvoiceViewSet,
    ApprovalRequestViewSet, ApprovalStepViewSet,
    EmployeeProfileViewSet, PayrollViewSet,
    ServiceRequestViewSet, InquiryViewSet,
    FixedAssetViewSet, AssetCategoryViewSet, AssetTransferViewSet,
    CertificationViewSet, LeaseContractViewSet, AssetAuditViewSet,
    MarketplaceOrderViewSet,
    VoucherViewSet, AccountReceivableViewSet,
    AccountPayableViewSet, BudgetViewSet,
    PurchaseOrderViewSet, ShippingCarrierViewSet,
    PriceRuleViewSet,
    # WMS
    WarehouseZoneViewSet, PickOrderViewSet, PutAwayTaskViewSet,
    # CMMS
    EquipmentViewSet, MaintenanceWorkOrderViewSet,
    # PLM
    EngineeringChangeNoticeViewSet, DrawingViewSet,
    # QMS
    NonConformanceViewSet, CAPAViewSet, InternalAuditViewSet,
    # Forecast
    DemandForecastViewSet, SOPMeetingViewSet,
    # Helpdesk
    TicketViewSet, SLAViewSet,
    # Portal
    PortalUserViewSet, PortalDocumentViewSet,
    # Logistics
    VehicleViewSet, DeliveryRouteViewSet,
    # EDI
    EDIPartnerViewSet, EDITransactionViewSet,
    # Subscription
    SubscriptionPlanViewSet, SubscriptionViewSet, BillingRecordViewSet,
    # Document
    DocumentViewSet, ContractViewSet,
    # Expense
    ExpenseClaimViewSet, ExpenseCategoryViewSet,
    # ESG
    CarbonEmissionViewSet, SafetyIncidentViewSet, ComplianceRequirementViewSet,
    # LMS
    CourseViewSet, CourseEnrollmentViewSet,
    # Wiki
    WikiSpaceViewSet, WikiArticleViewSet,
    # Project
    ProjectViewSet, ProjectTaskViewSet, MilestoneViewSet,
    # Visitor
    VisitRequestViewSet, VisitLogViewSet,
    # Attendance
    AttendanceRecordViewSet, LeaveRequestViewSet,
    # Board
    BoardViewSet, PostViewSet,
    # Calendar
    EventViewSet,
)

router = DefaultRouter()
# Existing (13)
router.register('products', ProductViewSet)
router.register('categories', CategoryViewSet)
router.register('warehouses', WarehouseViewSet)
router.register('stock-movements', StockMovementViewSet)
router.register('serial-numbers', SerialNumberViewSet)
router.register('partners', PartnerViewSet)
router.register('customers', CustomerViewSet)
router.register('orders', OrderViewSet)
router.register('order-items', OrderItemViewSet)
router.register('boms', BOMViewSet)
router.register('bom-items', BOMItemViewSet)
router.register('production-plans', ProductionPlanViewSet)
router.register('work-orders', WorkOrderViewSet)
router.register('tax-invoices', TaxInvoiceViewSet)
# New (+12 = 25 total)
router.register('approval-requests', ApprovalRequestViewSet)
router.register('approval-steps', ApprovalStepViewSet)
router.register('employees', EmployeeProfileViewSet)
router.register('payrolls', PayrollViewSet)
router.register('service-requests', ServiceRequestViewSet)
router.register('inquiries', InquiryViewSet)
router.register('fixed-assets', FixedAssetViewSet)
router.register('asset-categories', AssetCategoryViewSet)
router.register('asset-transfers', AssetTransferViewSet)
router.register('certifications', CertificationViewSet)
router.register('lease-contracts', LeaseContractViewSet)
router.register('asset-audits', AssetAuditViewSet)
router.register('marketplace-orders', MarketplaceOrderViewSet)
router.register('vouchers', VoucherViewSet)
router.register('accounts-receivable', AccountReceivableViewSet)
router.register('accounts-payable', AccountPayableViewSet)
router.register('budgets', BudgetViewSet)
router.register('purchase-orders', PurchaseOrderViewSet)
router.register('shipping-carriers', ShippingCarrierViewSet)
router.register('price-rules', PriceRuleViewSet)
# WMS
router.register('wms-zones', WarehouseZoneViewSet)
router.register('wms-pick-orders', PickOrderViewSet)
router.register('wms-putaway-tasks', PutAwayTaskViewSet)
# CMMS
router.register('equipment', EquipmentViewSet)
router.register('maintenance-work-orders', MaintenanceWorkOrderViewSet)
# PLM
router.register('ecns', EngineeringChangeNoticeViewSet)
router.register('drawings', DrawingViewSet)
# QMS
router.register('non-conformances', NonConformanceViewSet)
router.register('capas', CAPAViewSet)
router.register('internal-audits', InternalAuditViewSet)
# Forecast
router.register('demand-forecasts', DemandForecastViewSet)
router.register('sop-meetings', SOPMeetingViewSet)
# Helpdesk
router.register('tickets', TicketViewSet)
router.register('slas', SLAViewSet)
# Portal
router.register('portal-users', PortalUserViewSet)
router.register('portal-documents', PortalDocumentViewSet)
# Logistics
router.register('vehicles', VehicleViewSet)
router.register('delivery-routes', DeliveryRouteViewSet)
# EDI
router.register('edi-partners', EDIPartnerViewSet)
router.register('edi-transactions', EDITransactionViewSet)
# Subscription
router.register('subscription-plans', SubscriptionPlanViewSet)
router.register('subscriptions', SubscriptionViewSet)
router.register('billing-records', BillingRecordViewSet)
# Document
router.register('documents', DocumentViewSet)
router.register('contracts', ContractViewSet)
# Expense
router.register('expense-claims', ExpenseClaimViewSet)
router.register('expense-categories', ExpenseCategoryViewSet)
# ESG
router.register('carbon-emissions', CarbonEmissionViewSet)
router.register('safety-incidents', SafetyIncidentViewSet)
router.register('compliance-requirements', ComplianceRequirementViewSet)
# LMS
router.register('courses', CourseViewSet)
router.register('course-enrollments', CourseEnrollmentViewSet)
# Wiki
router.register('wiki-spaces', WikiSpaceViewSet)
router.register('wiki-articles', WikiArticleViewSet)
# Project
router.register('projects', ProjectViewSet)
router.register('project-tasks', ProjectTaskViewSet)
router.register('milestones', MilestoneViewSet)
# Visitor
router.register('visit-requests', VisitRequestViewSet)
router.register('visit-logs', VisitLogViewSet)
# Attendance
router.register('attendance-records', AttendanceRecordViewSet)
router.register('leave-requests', LeaveRequestViewSet)
# Board
router.register('boards', BoardViewSet)
router.register('posts', PostViewSet)
# Calendar
router.register('events', EventViewSet)

urlpatterns = router.urls + [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]
