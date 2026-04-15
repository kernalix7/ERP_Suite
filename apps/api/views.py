from rest_framework import viewsets

from apps.inventory.models import Product, Category, Warehouse, StockMovement, SerialNumber
from apps.sales.models import Partner, Customer, Order, OrderItem, ShippingCarrier, PriceRule
from apps.production.models import BOM, BOMItem, ProductionPlan, WorkOrder
from apps.accounting.models import (
    TaxInvoice, Voucher, AccountReceivable, AccountPayable, Budget,
)
from apps.approval.models import ApprovalRequest, ApprovalStep
from apps.hr.models import EmployeeProfile, Payroll
from apps.service.models import ServiceRequest
from apps.inquiry.models import Inquiry
from apps.asset.models import (
    AssetCategory, FixedAsset, AssetTransfer,
    Certification, LeaseContract, AssetAudit,
)
from apps.marketplace.models import MarketplaceOrder
from apps.purchase.models import PurchaseOrder

from apps.api.serializers import (
    ProductSerializer, CategorySerializer, WarehouseSerializer,
    StockMovementSerializer, SerialNumberSerializer,
    PartnerSerializer, CustomerSerializer,
    OrderSerializer, OrderItemSerializer, BOMSerializer, BOMItemSerializer,
    ProductionPlanSerializer, WorkOrderSerializer, TaxInvoiceSerializer,
    ApprovalRequestSerializer, ApprovalStepSerializer,
    EmployeeProfileSerializer, PayrollSerializer,
    ServiceRequestSerializer, InquirySerializer,
    FixedAssetSerializer, AssetCategorySerializer, AssetTransferSerializer,
    CertificationSerializer, LeaseContractSerializer, AssetAuditSerializer,
    MarketplaceOrderSerializer,
    VoucherSerializer, AccountReceivableSerializer,
    AccountPayableSerializer, BudgetSerializer,
    PurchaseOrderSerializer, ShippingCarrierSerializer,
    PriceRuleSerializer,
)
from apps.api.permissions import IsManagerOrReadOnly


class BaseModelViewSet(viewsets.ModelViewSet):
    """ViewSet that auto-sets created_by on create and filters inactive records."""

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(qs.model, 'is_active'):
            qs = qs.filter(is_active=True)
        if not qs.query.order_by:
            qs = qs.order_by('-pk')
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        instance.soft_delete()


class CategoryViewSet(BaseModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name']


class ProductViewSet(BaseModelViewSet):
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code']
    filterset_fields = ['product_type', 'category']


class WarehouseViewSet(BaseModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code']


class StockMovementViewSet(BaseModelViewSet):
    queryset = StockMovement.objects.select_related('product', 'warehouse').all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['movement_number', 'reference']
    filterset_fields = ['movement_type', 'product', 'warehouse']


class SerialNumberViewSet(viewsets.ReadOnlyModelViewSet):
    """시리얼번호 읽기 전용 API"""
    queryset = SerialNumber.objects.select_related('product', 'warehouse').filter(is_active=True)
    serializer_class = SerialNumberSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['serial', 'product__name']
    filterset_fields = ['status', 'product', 'warehouse']


class PartnerViewSet(BaseModelViewSet):
    queryset = Partner.objects.all()
    serializer_class = PartnerSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code', 'business_number']
    filterset_fields = ['partner_type']


class CustomerViewSet(BaseModelViewSet):
    queryset = Customer.objects.prefetch_related('purchases__product').all()
    serializer_class = CustomerSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'phone', 'email']


class OrderViewSet(BaseModelViewSet):
    queryset = Order.objects.select_related('partner', 'customer').prefetch_related('items__product').all()
    serializer_class = OrderSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['order_number']
    filterset_fields = ['status', 'partner', 'customer']


class OrderItemViewSet(BaseModelViewSet):
    queryset = OrderItem.objects.select_related('product', 'order').all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['order', 'product']


class BOMViewSet(BaseModelViewSet):
    queryset = BOM.objects.select_related('product').prefetch_related('items__material').all()
    serializer_class = BOMSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['product__name']
    filterset_fields = ['product', 'is_default']


class BOMItemViewSet(BaseModelViewSet):
    queryset = BOMItem.objects.select_related('material', 'bom').all()
    serializer_class = BOMItemSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['bom', 'material']


class ProductionPlanViewSet(BaseModelViewSet):
    queryset = ProductionPlan.objects.select_related('product', 'bom').all()
    serializer_class = ProductionPlanSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['plan_number', 'product__name']
    filterset_fields = ['status', 'product']


class WorkOrderViewSet(BaseModelViewSet):
    queryset = WorkOrder.objects.select_related('production_plan', 'assigned_to').all()
    serializer_class = WorkOrderSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['order_number']
    filterset_fields = ['status', 'production_plan', 'assigned_to']


class TaxInvoiceViewSet(BaseModelViewSet):
    queryset = TaxInvoice.objects.select_related('partner', 'order').all()
    serializer_class = TaxInvoiceSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['invoice_number', 'description']
    filterset_fields = ['invoice_type', 'partner']


# === Approval ===

class ApprovalRequestViewSet(BaseModelViewSet):
    queryset = ApprovalRequest.objects.select_related(
        'requester', 'approver', 'cooperator', 'department',
    ).prefetch_related('steps__approver').all()
    serializer_class = ApprovalRequestSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['request_number', 'title']
    filterset_fields = ['status', 'category', 'urgency', 'requester']


class ApprovalStepViewSet(BaseModelViewSet):
    queryset = ApprovalStep.objects.select_related(
        'request', 'approver',
    ).all()
    serializer_class = ApprovalStepSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['request', 'status', 'approver']


# === HR ===

class EmployeeProfileViewSet(BaseModelViewSet):
    queryset = EmployeeProfile.objects.select_related(
        'user', 'department', 'position',
    ).all()
    serializer_class = EmployeeProfileSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['employee_number', 'user__name']
    filterset_fields = ['department', 'position', 'status', 'contract_type']


class PayrollViewSet(BaseModelViewSet):
    queryset = Payroll.objects.select_related(
        'employee__user',
    ).all()
    serializer_class = PayrollSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['employee', 'year', 'month', 'status']
    ordering_fields = ['year', 'month']


# === Service ===

class ServiceRequestViewSet(BaseModelViewSet):
    queryset = ServiceRequest.objects.select_related(
        'customer', 'product',
    ).all()
    serializer_class = ServiceRequestSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['request_number', 'symptom']
    filterset_fields = ['status', 'request_type', 'is_warranty']


# === Inquiry ===

class InquiryViewSet(BaseModelViewSet):
    queryset = Inquiry.objects.select_related(
        'channel', 'assigned_to',
    ).all()
    serializer_class = InquirySerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['subject', 'customer_name']
    filterset_fields = ['status', 'priority', 'channel']


# === Asset ===

class FixedAssetViewSet(BaseModelViewSet):
    queryset = FixedAsset.objects.select_related('category').all()
    serializer_class = FixedAssetSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['asset_number', 'name']
    filterset_fields = ['category', 'status', 'depreciation_method']


class AssetCategoryViewSet(BaseModelViewSet):
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code']


class AssetTransferViewSet(BaseModelViewSet):
    queryset = AssetTransfer.objects.select_related(
        'asset', 'from_department', 'to_department', 'from_person', 'to_person',
    ).all()
    serializer_class = AssetTransferSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['asset', 'transfer_date', 'from_department', 'to_department']


class CertificationViewSet(BaseModelViewSet):
    queryset = Certification.objects.select_related('product', 'asset').all()
    serializer_class = CertificationSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['cert_name', 'cert_number']
    filterset_fields = ['cert_type', 'product', 'asset', 'is_capitalized']


class LeaseContractViewSet(BaseModelViewSet):
    queryset = LeaseContract.objects.select_related('asset', 'lessor').all()
    serializer_class = LeaseContractSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['contract_number', 'asset__name']
    filterset_fields = ['lease_type', 'asset']


class AssetAuditViewSet(BaseModelViewSet):
    queryset = AssetAudit.objects.select_related('auditor', 'department').all()
    serializer_class = AssetAuditSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['audit_date', 'auditor', 'department']


# === Marketplace ===

class MarketplaceOrderViewSet(BaseModelViewSet):
    queryset = MarketplaceOrder.objects.select_related('erp_order').all()
    serializer_class = MarketplaceOrderSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['store_order_id', 'product_name', 'buyer_name']
    filterset_fields = ['status']


# === Accounting (additional) ===

class VoucherViewSet(BaseModelViewSet):
    queryset = Voucher.objects.select_related('approved_by').prefetch_related('lines').all()
    serializer_class = VoucherSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['voucher_number', 'description']
    filterset_fields = ['voucher_type', 'approval_status']


class AccountReceivableViewSet(BaseModelViewSet):
    queryset = AccountReceivable.objects.select_related('partner', 'order', 'invoice').all()
    serializer_class = AccountReceivableSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['partner', 'status']
    ordering_fields = ['due_date', 'amount']


class AccountPayableViewSet(BaseModelViewSet):
    queryset = AccountPayable.objects.select_related('partner', 'invoice').all()
    serializer_class = AccountPayableSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['partner', 'status']
    ordering_fields = ['due_date', 'amount']


class BudgetViewSet(BaseModelViewSet):
    queryset = Budget.objects.select_related('account').all()
    serializer_class = BudgetSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['account', 'year', 'month']
    ordering_fields = ['year', 'month']


# === Purchase ===

class PurchaseOrderViewSet(BaseModelViewSet):
    queryset = PurchaseOrder.objects.select_related('partner').all()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['po_number']
    filterset_fields = ['status', 'partner']


# === Shipping ===

class ShippingCarrierViewSet(BaseModelViewSet):
    queryset = ShippingCarrier.objects.all()
    serializer_class = ShippingCarrierSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['code', 'name']
    filterset_fields = ['is_default']


class PriceRuleViewSet(BaseModelViewSet):
    queryset = PriceRule.objects.all()
    serializer_class = PriceRuleSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['product__name', 'partner__name', 'customer__name']
    filterset_fields = ['product', 'partner', 'customer']


# === WMS ===

from apps.wms.models import WarehouseZone, PickOrder, PutAwayTask
from apps.api.serializers import (
    WarehouseZoneSerializer, PickOrderSerializer, PutAwayTaskSerializer,
)


class WarehouseZoneViewSet(BaseModelViewSet):
    queryset = WarehouseZone.objects.select_related('warehouse').all()
    serializer_class = WarehouseZoneSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code']
    filterset_fields = ['zone_type', 'warehouse']


class PickOrderViewSet(BaseModelViewSet):
    queryset = PickOrder.objects.select_related('order', 'assigned_to').all()
    serializer_class = PickOrderSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['pick_number']
    filterset_fields = ['status', 'priority', 'assigned_to']


class PutAwayTaskViewSet(BaseModelViewSet):
    queryset = PutAwayTask.objects.select_related(
        'product', 'suggested_bin', 'actual_bin', 'assigned_to',
    ).all()
    serializer_class = PutAwayTaskSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['status', 'assigned_to']


# === CMMS ===

from apps.cmms.models import Equipment, MaintenanceWorkOrder
from apps.api.serializers import EquipmentSerializer, MaintenanceWorkOrderSerializer


class EquipmentViewSet(BaseModelViewSet):
    queryset = Equipment.objects.select_related('department').all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code', 'serial_number']
    filterset_fields = ['status', 'department']


class MaintenanceWorkOrderViewSet(BaseModelViewSet):
    queryset = MaintenanceWorkOrder.objects.select_related(
        'equipment', 'schedule', 'assigned_to',
    ).all()
    serializer_class = MaintenanceWorkOrderSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['wo_number', 'equipment__name']
    filterset_fields = ['status', 'priority', 'equipment', 'assigned_to']


# === PLM ===

from apps.plm.models import EngineeringChangeNotice, Drawing
from apps.api.serializers import EngineeringChangeNoticeSerializer, DrawingSerializer


class EngineeringChangeNoticeViewSet(BaseModelViewSet):
    queryset = EngineeringChangeNotice.objects.select_related(
        'requested_by', 'approved_by',
    ).all()
    serializer_class = EngineeringChangeNoticeSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['ecn_number', 'title']
    filterset_fields = ['status', 'priority']


class DrawingViewSet(BaseModelViewSet):
    queryset = Drawing.objects.select_related('product', 'version').all()
    serializer_class = DrawingSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['drawing_number', 'product__name']
    filterset_fields = ['product']


# === QMS ===

from apps.qms.models import NonConformance, CAPA, InternalAudit
from apps.api.serializers import (
    NonConformanceSerializer, CAPASerializer, InternalAuditSerializer,
)


class NonConformanceViewSet(BaseModelViewSet):
    queryset = NonConformance.objects.select_related('product', 'detected_by').all()
    serializer_class = NonConformanceSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['nc_number', 'title']
    filterset_fields = ['status', 'source', 'severity']


class CAPAViewSet(BaseModelViewSet):
    queryset = CAPA.objects.select_related('nc', 'assigned_to').all()
    serializer_class = CAPASerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['capa_number']
    filterset_fields = ['status', 'type', 'assigned_to']


class InternalAuditViewSet(BaseModelViewSet):
    queryset = InternalAudit.objects.select_related('auditor').all()
    serializer_class = InternalAuditSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['audit_number', 'title']
    filterset_fields = ['status', 'audit_type']


# === Forecast ===

from apps.forecast.models import DemandForecast, SOPMeeting
from apps.api.serializers import DemandForecastSerializer, SOPMeetingSerializer


class DemandForecastViewSet(BaseModelViewSet):
    queryset = DemandForecast.objects.select_related('product').all()
    serializer_class = DemandForecastSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['product', 'forecast_method']
    ordering_fields = ['period_start', 'period_end']


class SOPMeetingViewSet(BaseModelViewSet):
    queryset = SOPMeeting.objects.all()
    serializer_class = SOPMeetingSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['title']
    filterset_fields = ['status']


# === Helpdesk ===

from apps.helpdesk.models import Ticket, SLA
from apps.api.serializers import TicketSerializer, SLASerializer


class TicketViewSet(BaseModelViewSet):
    queryset = Ticket.objects.select_related(
        'category', 'reporter', 'assigned_to', 'sla',
    ).all()
    serializer_class = TicketSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['ticket_number', 'title']
    filterset_fields = ['status', 'priority', 'channel', 'assigned_to', 'sla_breached']


class SLAViewSet(BaseModelViewSet):
    queryset = SLA.objects.all()
    serializer_class = SLASerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name']


# === Portal ===

from apps.portal.models import PortalUser, PortalDocument
from apps.api.serializers import PortalUserSerializer, PortalDocumentSerializer


class PortalUserViewSet(BaseModelViewSet):
    queryset = PortalUser.objects.select_related('user', 'partner').all()
    serializer_class = PortalUserSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['portal_type', 'is_verified']


class PortalDocumentViewSet(BaseModelViewSet):
    queryset = PortalDocument.objects.select_related('portal_user').all()
    serializer_class = PortalDocumentSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['document_type', 'portal_user']


# === Logistics ===

from apps.logistics.models import Vehicle, DeliveryRoute
from apps.api.serializers import VehicleSerializer, DeliveryRouteSerializer


class VehicleViewSet(BaseModelViewSet):
    queryset = Vehicle.objects.select_related('driver').all()
    serializer_class = VehicleSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'plate_number']
    filterset_fields = ['vehicle_type', 'status']


class DeliveryRouteViewSet(BaseModelViewSet):
    queryset = DeliveryRoute.objects.select_related('vehicle', 'driver').all()
    serializer_class = DeliveryRouteSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['route_number', 'name']
    filterset_fields = ['status', 'date', 'vehicle', 'driver']


# === EDI ===

from apps.edi.models import EDIPartner as EDIPartnerModel, EDITransaction
from apps.api.serializers import EDIPartnerSerializer, EDITransactionSerializer


class EDIPartnerViewSet(BaseModelViewSet):
    queryset = EDIPartnerModel.objects.select_related('partner').all()
    serializer_class = EDIPartnerSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['edi_id', 'partner__name']
    filterset_fields = ['protocol']


class EDITransactionViewSet(BaseModelViewSet):
    queryset = EDITransaction.objects.select_related('partner', 'document_type').all()
    serializer_class = EDITransactionSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['transaction_id']
    filterset_fields = ['status', 'direction', 'partner']


# === Subscription ===

from apps.subscription.models import SubscriptionPlan, Subscription, BillingRecord
from apps.api.serializers import (
    SubscriptionPlanSerializer, SubscriptionSerializer, BillingRecordSerializer,
)


class SubscriptionPlanViewSet(BaseModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code']
    filterset_fields = ['billing_cycle']


class SubscriptionViewSet(BaseModelViewSet):
    queryset = Subscription.objects.select_related('partner', 'plan').all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['subscription_number', 'partner__name']
    filterset_fields = ['status', 'plan', 'auto_renew']


class BillingRecordViewSet(BaseModelViewSet):
    queryset = BillingRecord.objects.select_related('subscription', 'invoice').all()
    serializer_class = BillingRecordSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['status', 'subscription']
    ordering_fields = ['billing_date']


# === Document ===

from apps.document.models import Document as DocumentModel, Contract
from apps.api.serializers import DocumentSerializer, ContractSerializer


class DocumentViewSet(BaseModelViewSet):
    queryset = DocumentModel.objects.select_related('category', 'owner', 'department').all()
    serializer_class = DocumentSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['document_number', 'title']
    filterset_fields = ['status', 'category', 'access_level']


class ContractViewSet(BaseModelViewSet):
    queryset = Contract.objects.select_related('partner', 'signed_by').all()
    serializer_class = ContractSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['contract_number', 'title']
    filterset_fields = ['contract_type', 'status', 'partner']


# === Expense ===

from apps.expense.models import (
    ExpenseClaim,
    ExpenseCategory as ExpenseCategoryModel,
)
from apps.api.serializers import ExpenseClaimSerializer, ExpenseCategorySerializer


class ExpenseClaimViewSet(BaseModelViewSet):
    queryset = ExpenseClaim.objects.select_related('employee', 'approved_by').all()
    serializer_class = ExpenseClaimSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['claim_number', 'title']
    filterset_fields = ['status', 'employee']


class ExpenseCategoryViewSet(BaseModelViewSet):
    queryset = ExpenseCategoryModel.objects.select_related('account_code', 'parent', 'policy').all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code']


# === ESG ===

from apps.esg.models import CarbonEmission, SafetyIncident, ComplianceRequirement
from apps.api.serializers import (
    CarbonEmissionSerializer, SafetyIncidentSerializer,
    ComplianceRequirementSerializer,
)


class CarbonEmissionViewSet(BaseModelViewSet):
    queryset = CarbonEmission.objects.all()
    serializer_class = CarbonEmissionSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['source', 'facility']
    filterset_fields = ['scope', 'period']


class SafetyIncidentViewSet(BaseModelViewSet):
    queryset = SafetyIncident.objects.select_related('reported_by').all()
    serializer_class = SafetyIncidentSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['incident_number', 'location']
    filterset_fields = ['severity', 'status']


class ComplianceRequirementViewSet(BaseModelViewSet):
    queryset = ComplianceRequirement.objects.select_related('responsible').all()
    serializer_class = ComplianceRequirementSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'regulation']
    filterset_fields = ['status']


# === LMS ===

from apps.lms.models import Course as CourseModel, CourseEnrollment
from apps.api.serializers import CourseSerializer, CourseEnrollmentSerializer


class CourseViewSet(BaseModelViewSet):
    queryset = CourseModel.objects.select_related('category', 'instructor').all()
    serializer_class = CourseSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['course_number', 'title']
    filterset_fields = ['status', 'level', 'category', 'is_mandatory']


class CourseEnrollmentViewSet(BaseModelViewSet):
    queryset = CourseEnrollment.objects.select_related('course', 'learner').all()
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['status', 'course', 'learner']


# === Wiki ===

from apps.wiki.models import WikiArticle, WikiSpace
from apps.api.serializers import WikiArticleSerializer, WikiSpaceSerializer


class WikiSpaceViewSet(BaseModelViewSet):
    queryset = WikiSpace.objects.select_related('owner').all()
    serializer_class = WikiSpaceSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code']
    filterset_fields = ['is_public']


class WikiArticleViewSet(BaseModelViewSet):
    queryset = WikiArticle.objects.select_related(
        'space', 'category', 'author',
    ).all()
    serializer_class = WikiArticleSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['article_number', 'title']
    filterset_fields = ['status', 'space', 'category', 'is_pinned']


# === Project ===

from apps.project.models import (
    Project as ProjectModel, Task as TaskModel, Milestone,
)
from apps.api.serializers import ProjectSerializer, TaskSerializer, MilestoneSerializer


class ProjectViewSet(BaseModelViewSet):
    queryset = ProjectModel.objects.select_related(
        'category', 'manager', 'department',
    ).all()
    serializer_class = ProjectSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['project_number', 'name']
    filterset_fields = ['status', 'priority', 'manager', 'department']


class ProjectTaskViewSet(BaseModelViewSet):
    queryset = TaskModel.objects.select_related(
        'project', 'milestone', 'assignee', 'reporter',
    ).all()
    serializer_class = TaskSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['title']
    filterset_fields = ['status', 'priority', 'project', 'assignee', 'milestone']


class MilestoneViewSet(BaseModelViewSet):
    queryset = Milestone.objects.select_related('project').all()
    serializer_class = MilestoneSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['title']
    filterset_fields = ['status', 'project']


# === Visitor ===

from apps.visitor.models import VisitRequest, VisitLog
from apps.api.serializers import VisitRequestSerializer, VisitLogSerializer


class VisitRequestViewSet(BaseModelViewSet):
    queryset = VisitRequest.objects.select_related(
        'visitor', 'host', 'purpose', 'department', 'approved_by',
    ).all()
    serializer_class = VisitRequestSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['visit_number', 'visitor__name']
    filterset_fields = ['status', 'host', 'purpose']


class VisitLogViewSet(BaseModelViewSet):
    queryset = VisitLog.objects.select_related(
        'visitor', 'visit_request', 'receptionist',
    ).all()
    serializer_class = VisitLogSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['visitor']


# === Attendance ===

from apps.attendance.models import AttendanceRecord, LeaveRequest
from apps.api.serializers import AttendanceRecordSerializer, LeaveRequestSerializer


class AttendanceRecordViewSet(BaseModelViewSet):
    queryset = AttendanceRecord.objects.select_related('user').all()
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['user', 'date', 'status']
    ordering_fields = ['date']


class LeaveRequestViewSet(BaseModelViewSet):
    queryset = LeaveRequest.objects.select_related('user', 'approved_by').all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['user', 'leave_type', 'status']
    ordering_fields = ['start_date']


# === Board ===

from apps.board.models import Board as BoardModel, Post
from apps.api.serializers import BoardSerializer, PostSerializer


class BoardViewSet(BaseModelViewSet):
    queryset = BoardModel.objects.all()
    serializer_class = BoardSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name']
    filterset_fields = ['is_notice']


class PostViewSet(BaseModelViewSet):
    queryset = Post.objects.select_related('board', 'author').all()
    serializer_class = PostSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['title']
    filterset_fields = ['board', 'author', 'is_pinned']


# === Calendar ===

from apps.calendar_app.models import Event
from apps.api.serializers import EventSerializer


class EventViewSet(BaseModelViewSet):
    queryset = Event.objects.select_related('creator').all()
    serializer_class = EventSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['title', 'location']
    filterset_fields = ['event_type', 'creator', 'all_day']
