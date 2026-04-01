from rest_framework import viewsets

from apps.inventory.models import Product, Category, Warehouse, StockMovement
from apps.sales.models import Partner, Customer, Order, OrderItem, ShippingCarrier, PriceRule
from apps.production.models import BOM, BOMItem, ProductionPlan, WorkOrder
from apps.accounting.models import (
    TaxInvoice, Voucher, AccountReceivable, AccountPayable, Budget,
)
from apps.approval.models import ApprovalRequest, ApprovalStep
from apps.hr.models import EmployeeProfile, Payroll
from apps.service.models import ServiceRequest
from apps.inquiry.models import Inquiry
from apps.asset.models import FixedAsset
from apps.marketplace.models import MarketplaceOrder
from apps.purchase.models import PurchaseOrder

from apps.api.serializers import (
    ProductSerializer, CategorySerializer, WarehouseSerializer,
    StockMovementSerializer, PartnerSerializer, CustomerSerializer,
    OrderSerializer, OrderItemSerializer, BOMSerializer, BOMItemSerializer,
    ProductionPlanSerializer, WorkOrderSerializer, TaxInvoiceSerializer,
    ApprovalRequestSerializer, ApprovalStepSerializer,
    EmployeeProfileSerializer, PayrollSerializer,
    ServiceRequestSerializer, InquirySerializer,
    FixedAssetSerializer, MarketplaceOrderSerializer,
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
