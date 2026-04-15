from rest_framework import serializers

from apps.inventory.models import Product, Category, Warehouse, StockMovement, SerialNumber
from apps.sales.models import Partner, Customer, CustomerPurchase, Order, OrderItem, Shipment, ShippingCarrier, PriceRule
from apps.production.models import BOM, BOMItem, ProductionPlan, WorkOrder
from apps.accounting.models import (
    TaxInvoice, Voucher, VoucherLine, AccountReceivable, AccountPayable, Budget,
)
from apps.approval.models import ApprovalRequest, ApprovalStep
from apps.hr.models import EmployeeProfile, Payroll
from apps.service.models import ServiceRequest
from apps.inquiry.models import Inquiry
from apps.asset.models import (
    AssetCategory as AssetCategoryModel, FixedAsset, AssetTransfer,
    Certification, LeaseContract, AssetAudit,
)
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


class SerialNumberSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True, default=None)

    class Meta:
        model = SerialNumber
        fields = [
            'id', 'serial', 'product', 'product_name',
            'status', 'warehouse', 'warehouse_name',
            'production_date',
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


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategoryModel
        fields = [
            'id', 'code', 'name', 'useful_life_years', 'depreciation_method',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class AssetTransferSerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source='asset.name', read_only=True, default=None)

    class Meta:
        model = AssetTransfer
        fields = [
            'id', 'asset', 'asset_name', 'transfer_date',
            'from_department', 'to_department',
            'from_person', 'to_person',
            'from_location', 'to_location', 'reason',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = [
            'id', 'product', 'asset', 'cert_type', 'cert_number',
            'cert_name', 'issuer', 'issue_date', 'expiry_date',
            'cost', 'is_capitalized',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class LeaseContractSerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source='asset.name', read_only=True, default=None)

    class Meta:
        model = LeaseContract
        fields = [
            'id', 'contract_number', 'asset', 'asset_name',
            'lessor', 'lease_type', 'start_date', 'end_date',
            'monthly_payment', 'deposit', 'total_amount', 'auto_voucher',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['contract_number', 'total_amount', 'created_at', 'updated_at']


class AssetAuditSerializer(serializers.ModelSerializer):
    auditor_name = serializers.CharField(source='auditor.name', read_only=True, default=None)

    class Meta:
        model = AssetAudit
        fields = [
            'id', 'audit_date', 'auditor', 'auditor_name', 'department',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


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


# === WMS ===

from apps.wms.models import WarehouseZone, PickOrder, PutAwayTask


class WarehouseZoneSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = WarehouseZone
        fields = [
            'id', 'warehouse', 'warehouse_name', 'name', 'code',
            'zone_type', 'description',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PickOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickOrder
        fields = [
            'id', 'pick_number', 'order', 'status', 'priority',
            'assigned_to',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['pick_number', 'created_at', 'updated_at']


class PutAwayTaskSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = PutAwayTask
        fields = [
            'id', 'goods_receipt', 'product', 'product_name',
            'quantity', 'suggested_bin', 'actual_bin',
            'status', 'assigned_to',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === CMMS ===

from apps.cmms.models import Equipment, MaintenanceWorkOrder


class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        fields = [
            'id', 'name', 'code', 'category', 'location',
            'manufacturer', 'model_number', 'serial_number',
            'purchase_date', 'purchase_cost', 'status', 'department',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class MaintenanceWorkOrderSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)

    class Meta:
        model = MaintenanceWorkOrder
        fields = [
            'id', 'wo_number', 'schedule', 'equipment', 'equipment_name',
            'status', 'priority', 'description',
            'started_at', 'completed_at', 'cost',
            'findings', 'parts_used', 'assigned_to',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['wo_number', 'created_at', 'updated_at']


# === PLM ===

from apps.plm.models import EngineeringChangeNotice, Drawing


class EngineeringChangeNoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EngineeringChangeNotice
        fields = [
            'id', 'ecn_number', 'title', 'description',
            'priority', 'status',
            'requested_by', 'approved_by', 'target_date',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['ecn_number', 'created_at', 'updated_at']


class DrawingSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Drawing
        fields = [
            'id', 'product', 'product_name', 'version',
            'file', 'drawing_number', 'revision',
            'description', 'format',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === QMS ===

from apps.qms.models import NonConformance, CAPA, InternalAudit


class NonConformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NonConformance
        fields = [
            'id', 'nc_number', 'title', 'description',
            'source', 'severity', 'product', 'detected_by',
            'status', 'root_cause', 'corrective_action',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['nc_number', 'created_at', 'updated_at']


class CAPASerializer(serializers.ModelSerializer):
    class Meta:
        model = CAPA
        fields = [
            'id', 'capa_number', 'nc', 'type',
            'description', 'assigned_to', 'due_date',
            'status', 'effectiveness_check',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['capa_number', 'created_at', 'updated_at']


class InternalAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternalAudit
        fields = [
            'id', 'audit_number', 'title', 'audit_type',
            'scope', 'auditor', 'audit_date',
            'status', 'findings', 'conclusion',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['audit_number', 'created_at', 'updated_at']


# === Forecast ===

from apps.forecast.models import DemandForecast, SOPMeeting


class DemandForecastSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = DemandForecast
        fields = [
            'id', 'product', 'product_name',
            'period_start', 'period_end',
            'forecast_method', 'forecast_qty',
            'actual_qty', 'accuracy_pct',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class SOPMeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SOPMeeting
        fields = [
            'id', 'title', 'meeting_date', 'period',
            'status', 'minutes', 'decisions',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === Helpdesk ===

from apps.helpdesk.models import Ticket, SLA


class TicketSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)

    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_number', 'title', 'description',
            'category', 'category_name', 'priority', 'status',
            'reporter', 'assigned_to',
            'sla', 'sla_response_due', 'sla_resolution_due', 'sla_breached',
            'channel',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['ticket_number', 'created_at', 'updated_at']


class SLASerializer(serializers.ModelSerializer):
    class Meta:
        model = SLA
        fields = [
            'id', 'name', 'response_time_hours',
            'resolution_time_hours', 'escalation_time_hours',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === Portal ===

from apps.portal.models import PortalUser, PortalDocument


class PortalUserSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True)

    class Meta:
        model = PortalUser
        fields = [
            'id', 'user', 'partner', 'partner_name',
            'portal_type', 'is_verified', 'last_portal_login',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PortalDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortalDocument
        fields = [
            'id', 'portal_user', 'document_type', 'title', 'file',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === Logistics ===

from apps.logistics.models import Vehicle, DeliveryRoute


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'id', 'name', 'plate_number', 'vehicle_type',
            'capacity_kg', 'capacity_cbm', 'status', 'driver',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class DeliveryRouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRoute
        fields = [
            'id', 'route_number', 'name', 'date',
            'vehicle', 'driver', 'status',
            'total_distance_km', 'total_cost',
            'departure_time', 'return_time',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['route_number', 'created_at', 'updated_at']


# === EDI ===

from apps.edi.models import EDIPartner, EDITransaction


class EDIPartnerSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True)

    class Meta:
        model = EDIPartner
        fields = [
            'id', 'partner', 'partner_name', 'edi_id', 'protocol',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class EDITransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EDITransaction
        fields = [
            'id', 'transaction_id', 'partner', 'document_type',
            'direction', 'status', 'processed_at', 'error_message',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['transaction_id', 'created_at', 'updated_at']


# === Subscription ===

from apps.subscription.models import SubscriptionPlan, Subscription, BillingRecord


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'code', 'description',
            'billing_cycle', 'price', 'currency', 'features',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class SubscriptionSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'subscription_number', 'partner', 'partner_name',
            'plan', 'plan_name', 'status',
            'start_date', 'end_date', 'next_billing_date',
            'auto_renew', 'cancel_reason',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['subscription_number', 'created_at', 'updated_at']


class BillingRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingRecord
        fields = [
            'id', 'subscription', 'billing_date',
            'amount', 'tax_amount', 'total', 'status',
            'invoice', 'order',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['total', 'created_at', 'updated_at']


# === Document ===

from apps.document.models import Document, Contract


class DocumentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'document_number', 'title', 'category', 'category_name',
            'content_file', 'file_type', 'version',
            'status', 'owner', 'department', 'access_level',
            'tags', 'expiry_date',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['document_number', 'created_at', 'updated_at']


class ContractSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True, default=None)

    class Meta:
        model = Contract
        fields = [
            'id', 'contract_number', 'title', 'contract_type',
            'partner', 'partner_name',
            'start_date', 'end_date', 'value',
            'status', 'auto_renew', 'renewal_notice_days',
            'signed_date', 'signed_by',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['contract_number', 'created_at', 'updated_at']


# === Expense ===

from apps.expense.models import ExpenseClaim, ExpenseCategory as ExpenseCategoryModel


class ExpenseClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseClaim
        fields = [
            'id', 'claim_number', 'employee', 'title',
            'status', 'submitted_date',
            'approved_by', 'approved_date',
            'total_amount', 'paid_date', 'rejection_reason',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['claim_number', 'total_amount', 'created_at', 'updated_at']


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategoryModel
        fields = [
            'id', 'name', 'code', 'account_code',
            'parent', 'policy',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === ESG ===

from apps.esg.models import CarbonEmission, SafetyIncident, ComplianceRequirement


class CarbonEmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonEmission
        fields = [
            'id', 'source', 'scope', 'emission_type',
            'amount_kg', 'period', 'facility', 'calculation_method',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class SafetyIncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SafetyIncident
        fields = [
            'id', 'incident_number', 'date', 'location',
            'severity', 'description', 'injured_count',
            'root_cause', 'corrective_action',
            'status', 'reported_by',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['incident_number', 'created_at', 'updated_at']


class ComplianceRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceRequirement
        fields = [
            'id', 'name', 'regulation', 'description',
            'responsible', 'due_date', 'status',
            'last_review',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === LMS ===

from apps.lms.models import Course, CourseEnrollment


class CourseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'course_number', 'title', 'category', 'category_name',
            'instructor', 'description', 'level', 'status',
            'duration_hours', 'pass_score', 'is_mandatory',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['course_number', 'created_at', 'updated_at']


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseEnrollment
        fields = [
            'id', 'course', 'learner', 'status',
            'enrolled_at', 'completed_at',
            'progress_pct', 'final_score',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['enrolled_at', 'created_at', 'updated_at']


# === Wiki ===

from apps.wiki.models import WikiArticle, WikiSpace


class WikiSpaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WikiSpace
        fields = [
            'id', 'name', 'code', 'description',
            'is_public', 'owner',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class WikiArticleSerializer(serializers.ModelSerializer):
    space_name = serializers.CharField(source='space.name', read_only=True)

    class Meta:
        model = WikiArticle
        fields = [
            'id', 'article_number', 'space', 'space_name',
            'category', 'title', 'slug', 'status',
            'author', 'tags', 'view_count', 'is_pinned',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['article_number', 'view_count', 'created_at', 'updated_at']


# === Project ===

from apps.project.models import (
    Project as ProjectModel, Task as TaskModel, Milestone,
)


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectModel
        fields = [
            'id', 'project_number', 'name', 'category',
            'status', 'priority', 'manager', 'department',
            'description', 'start_date', 'due_date', 'completed_date',
            'budget', 'progress_pct',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['project_number', 'created_at', 'updated_at']


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskModel
        fields = [
            'id', 'project', 'milestone', 'parent_task',
            'title', 'description', 'status', 'priority',
            'assignee', 'reporter',
            'start_date', 'due_date', 'completed_date',
            'estimated_hours', 'actual_hours',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class MilestoneSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = Milestone
        fields = [
            'id', 'project', 'project_name',
            'title', 'description',
            'due_date', 'completed_date', 'status',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === Visitor ===

from apps.visitor.models import VisitRequest, VisitLog


class VisitRequestSerializer(serializers.ModelSerializer):
    visitor_name = serializers.CharField(source='visitor.name', read_only=True)

    class Meta:
        model = VisitRequest
        fields = [
            'id', 'visit_number', 'visitor', 'visitor_name',
            'host', 'purpose', 'department',
            'scheduled_at', 'expected_duration_minutes',
            'status', 'rejection_reason',
            'approved_by', 'approved_at', 'visitor_count',
            'description',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['visit_number', 'created_at', 'updated_at']


class VisitLogSerializer(serializers.ModelSerializer):
    visitor_name = serializers.CharField(source='visitor.name', read_only=True)

    class Meta:
        model = VisitLog
        fields = [
            'id', 'visit_request', 'visitor', 'visitor_name',
            'check_in_at', 'check_out_at', 'badge_number',
            'receptionist', 'remarks',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === Attendance ===

from apps.attendance.models import AttendanceRecord, LeaveRequest


class AttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'user', 'date', 'check_in', 'check_out',
            'status', 'overtime_hours',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'user', 'leave_type',
            'start_date', 'end_date', 'days', 'reason',
            'status', 'approved_by', 'approved_at',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# === Board ===

from apps.board.models import Board as BoardModel, Post


class BoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardModel
        fields = [
            'id', 'name', 'slug', 'description',
            'is_notice', 'permission_level',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PostSerializer(serializers.ModelSerializer):
    board_name = serializers.CharField(source='board.name', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'board', 'board_name', 'title',
            'content', 'author', 'is_pinned', 'view_count',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['view_count', 'created_at', 'updated_at']


# === Calendar ===

from apps.calendar_app.models import Event


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'description',
            'start_datetime', 'end_datetime', 'all_day',
            'event_type', 'color', 'location',
            'creator', 'is_recurring',
            'is_active', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
