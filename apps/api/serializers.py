from rest_framework import serializers

from apps.inventory.models import Product, Category, Warehouse, StockMovement
from apps.sales.models import Partner, Customer, CustomerPurchase, Order, OrderItem, Shipment, ShippingCarrier, PriceRule
from apps.production.models import BOM, BOMItem, ProductionPlan, WorkOrder
from apps.accounting.models import (
    TaxInvoice, Voucher, VoucherLine, AccountReceivable, AccountPayable, Budget,
)
from apps.approval.models import ApprovalRequest, ApprovalStep
from apps.hr.models import EmployeeProfile, Payroll
from apps.service.models import ServiceRequest
from apps.inquiry.models import Inquiry
from apps.asset.models import FixedAsset
from apps.marketplace.models import MarketplaceOrder
from apps.purchase.models import PurchaseOrder


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id', 'code', 'name', 'parent',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)

    class Meta:
        model = Product
        fields = [
            'id', 'code', 'name', 'product_type', 'category', 'category_name',
            'unit', 'unit_price', 'cost_price', 'safety_stock', 'current_stock',
            'specification',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['current_stock', 'created_at', 'updated_at']


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            'id', 'code', 'name', 'location',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'movement_number', 'movement_type',
            'product', 'product_name', 'warehouse', 'warehouse_name',
            'quantity', 'unit_price', 'movement_date', 'reference',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = [
            'id', 'code', 'name', 'partner_type', 'business_number',
            'representative', 'contact_name', 'phone', 'email', 'address',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class CustomerPurchaseSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = CustomerPurchase
        fields = [
            'id', 'product', 'product_name',
            'serial_number', 'purchase_date', 'warranty_end',
        ]


class CustomerSerializer(serializers.ModelSerializer):
    purchases = CustomerPurchaseSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'code', 'name', 'phone', 'email', 'address',
            'purchases',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'product', 'product_name',
            'quantity', 'unit_price', 'amount', 'tax_amount', 'total_with_tax',
        ]
        read_only_fields = ['amount', 'tax_amount', 'total_with_tax']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    partner_name = serializers.CharField(source='partner.name', read_only=True, default=None)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default=None)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'order_type', 'partner', 'partner_name',
            'customer', 'customer_name', 'assigned_to',
            'order_date', 'delivery_date', 'status',
            'total_amount', 'tax_total', 'grand_total',
            'shipping_address', 'shipping_method', 'tracking_number',
            'items',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['total_amount', 'tax_total', 'grand_total', 'status', 'created_at', 'updated_at']


class ShipmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = Shipment
        fields = [
            'id', 'order', 'order_number', 'shipment_number',
            'shipping_type', 'carrier', 'tracking_number',
            'status', 'shipped_date', 'delivered_date',
            'receiver_name', 'receiver_phone', 'receiver_address',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class BOMItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)

    class Meta:
        model = BOMItem
        fields = [
            'id', 'bom', 'material', 'material_name',
            'quantity', 'loss_rate',
        ]


class BOMSerializer(serializers.ModelSerializer):
    items = BOMItemSerializer(many=True, read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = BOM
        fields = [
            'id', 'product', 'product_name', 'version', 'is_default',
            'items',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProductionPlanSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ProductionPlan
        fields = [
            'id', 'plan_number', 'product', 'product_name',
            'bom', 'planned_quantity', 'planned_start', 'planned_end',
            'status', 'estimated_cost', 'actual_cost',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class WorkOrderSerializer(serializers.ModelSerializer):
    production_plan_number = serializers.CharField(
        source='production_plan.plan_number', read_only=True,
    )

    class Meta:
        model = WorkOrder
        fields = [
            'id', 'order_number', 'production_plan', 'production_plan_number',
            'assigned_to', 'quantity', 'status',
            'started_at', 'completed_at',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaxInvoiceSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True)

    class Meta:
        model = TaxInvoice
        fields = [
            'id', 'invoice_number', 'invoice_type',
            'partner', 'partner_name', 'order',
            'issue_date', 'supply_amount', 'tax_amount', 'total_amount',
            'description',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === Approval ===

class ApprovalStepSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source='approver.name', read_only=True, default=None)

    class Meta:
        model = ApprovalStep
        fields = [
            'id', 'request', 'step_order', 'approver', 'approver_name',
            'status', 'comment', 'acted_at',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['acted_at', 'created_at', 'updated_at']


class ApprovalRequestSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(source='requester.name', read_only=True, default=None)
    approver_name = serializers.CharField(source='approver.name', read_only=True, default=None)
    steps = ApprovalStepSerializer(many=True, read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = [
            'id', 'request_number', 'category', 'urgency',
            'title', 'department', 'purpose', 'content', 'amount',
            'expected_date', 'status',
            'requester', 'requester_name', 'approver', 'approver_name',
            'cooperator', 'submitted_at', 'approved_at',
            'reject_reason', 'current_step',
            'steps',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'request_number', 'submitted_at', 'approved_at',
            'created_at', 'updated_at',
        ]


# === HR ===

class EmployeeProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True, default=None)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    position_name = serializers.CharField(source='position.name', read_only=True, default=None)

    class Meta:
        model = EmployeeProfile
        fields = [
            'id', 'user', 'user_name', 'employee_number',
            'department', 'department_name', 'position', 'position_name',
            'hire_date', 'contract_type', 'status',
            'base_salary',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PayrollSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source='employee.user.name', read_only=True, default=None,
    )

    class Meta:
        model = Payroll
        fields = [
            'id', 'employee', 'employee_name',
            'year', 'month', 'base_salary',
            'overtime_pay', 'bonus', 'allowances', 'gross_pay',
            'national_pension', 'health_insurance', 'long_term_care',
            'employment_insurance', 'income_tax', 'local_income_tax',
            'total_deductions', 'net_pay',
            'status', 'paid_date',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'gross_pay', 'total_deductions', 'net_pay',
            'created_at', 'updated_at',
        ]


# === Service ===

class ServiceRequestSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True, default=None)
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = ServiceRequest
        fields = [
            'id', 'request_number', 'customer', 'customer_name',
            'product', 'product_name', 'serial_number',
            'request_type', 'status', 'symptom',
            'received_date', 'completed_date', 'is_warranty',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['request_number', 'created_at', 'updated_at']


# === Inquiry ===

class InquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inquiry
        fields = [
            'id', 'inquiry_number', 'channel', 'customer_name', 'customer_contact',
            'subject', 'content', 'status', 'priority',
            'received_date', 'assigned_to',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === Asset ===

class FixedAssetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)

    class Meta:
        model = FixedAsset
        fields = [
            'id', 'asset_number', 'name', 'category', 'category_name',
            'acquisition_date', 'acquisition_cost',
            'residual_value', 'useful_life_years', 'depreciation_method',
            'accumulated_depreciation', 'book_value',
            'department', 'location', 'responsible_person',
            'status', 'disposal_date', 'disposal_amount',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'accumulated_depreciation', 'book_value',
            'created_at', 'updated_at',
        ]


# === Marketplace ===

class MarketplaceOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplaceOrder
        fields = [
            'id', 'store_order_id', 'product_name', 'option_name',
            'quantity', 'price',
            'buyer_name', 'receiver_name', 'receiver_address',
            'status', 'ordered_at', 'erp_order', 'synced_at',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['synced_at', 'created_at', 'updated_at']


# === Accounting (additional) ===

class VoucherLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherLine
        fields = [
            'id', 'voucher', 'account', 'debit', 'credit',
            'description',
        ]


class VoucherSerializer(serializers.ModelSerializer):
    lines = VoucherLineSerializer(many=True, read_only=True)

    class Meta:
        model = Voucher
        fields = [
            'id', 'voucher_number', 'voucher_type', 'voucher_date',
            'description', 'approval_status', 'approved_by',
            'lines',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['voucher_number', 'created_at', 'updated_at']


class AccountReceivableSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True, default=None)

    class Meta:
        model = AccountReceivable
        fields = [
            'id', 'partner', 'partner_name', 'order', 'invoice',
            'amount', 'paid_amount', 'due_date', 'status',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['paid_amount', 'created_at', 'updated_at']


class AccountPayableSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True, default=None)

    class Meta:
        model = AccountPayable
        fields = [
            'id', 'partner', 'partner_name', 'invoice',
            'amount', 'paid_amount', 'due_date', 'status',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['paid_amount', 'created_at', 'updated_at']


class BudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Budget
        fields = [
            'id', 'account', 'year', 'month',
            'budget_amount', 'description',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === Purchase ===

class PurchaseOrderSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True, default=None)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'po_number', 'partner', 'partner_name',
            'order_date', 'expected_date', 'status',
            'total_amount', 'tax_total', 'grand_total',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'po_number', 'total_amount', 'tax_total', 'grand_total',
            'created_at', 'updated_at',
        ]


# === Shipping ===

class ShippingCarrierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingCarrier
        fields = [
            'id', 'code', 'name', 'tracking_url_template',
            'api_endpoint', 'is_default',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PriceRuleSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    partner_name = serializers.CharField(source='partner.name', read_only=True, default=None)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default=None)

    class Meta:
        model = PriceRule
        fields = [
            'id', 'product', 'product_name', 'partner', 'partner_name',
            'customer', 'customer_name', 'min_quantity', 'unit_price',
            'discount_rate', 'valid_from', 'valid_to', 'priority',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
