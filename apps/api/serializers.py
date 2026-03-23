from rest_framework import serializers

from apps.inventory.models import Product, Category, Warehouse, StockMovement
from apps.sales.models import Partner, Customer, CustomerPurchase, Order, OrderItem, Shipment
from apps.production.models import BOM, BOMItem, ProductionPlan, WorkOrder
from apps.accounting.models import TaxInvoice


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'parent',
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
            'id', 'name', 'phone', 'email', 'address',
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
        read_only_fields = ['total_amount', 'tax_total', 'grand_total', 'created_at', 'updated_at']


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
