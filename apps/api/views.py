from rest_framework import viewsets

from apps.inventory.models import Product, Category, Warehouse, StockMovement
from apps.sales.models import Partner, Customer, Order, OrderItem
from apps.production.models import BOM, BOMItem, ProductionPlan, WorkOrder
from apps.accounting.models import TaxInvoice

from apps.api.serializers import (
    ProductSerializer, CategorySerializer, WarehouseSerializer,
    StockMovementSerializer, PartnerSerializer, CustomerSerializer,
    OrderSerializer, OrderItemSerializer, BOMSerializer, BOMItemSerializer,
    ProductionPlanSerializer, WorkOrderSerializer, TaxInvoiceSerializer,
)
from apps.api.permissions import IsManagerOrReadOnly


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name']


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code']
    filterset_fields = ['product_type', 'category']


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code']


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related('product', 'warehouse').all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['movement_number', 'reference']
    filterset_fields = ['movement_type', 'product', 'warehouse']


class PartnerViewSet(viewsets.ModelViewSet):
    queryset = Partner.objects.all()
    serializer_class = PartnerSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'code', 'business_number']
    filterset_fields = ['partner_type']


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('product').all()
    serializer_class = CustomerSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['name', 'phone', 'email']


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related('partner', 'customer').prefetch_related('items__product').all()
    serializer_class = OrderSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['order_number']
    filterset_fields = ['status', 'partner', 'customer']


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.select_related('product', 'order').all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['order', 'product']


class BOMViewSet(viewsets.ModelViewSet):
    queryset = BOM.objects.select_related('product').prefetch_related('items__material').all()
    serializer_class = BOMSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['product__name']
    filterset_fields = ['product', 'is_default']


class BOMItemViewSet(viewsets.ModelViewSet):
    queryset = BOMItem.objects.select_related('material', 'bom').all()
    serializer_class = BOMItemSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ['bom', 'material']


class ProductionPlanViewSet(viewsets.ModelViewSet):
    queryset = ProductionPlan.objects.select_related('product', 'bom').all()
    serializer_class = ProductionPlanSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['plan_number', 'product__name']
    filterset_fields = ['status', 'product']


class WorkOrderViewSet(viewsets.ModelViewSet):
    queryset = WorkOrder.objects.select_related('production_plan', 'assigned_to').all()
    serializer_class = WorkOrderSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['order_number']
    filterset_fields = ['status', 'production_plan', 'assigned_to']


class TaxInvoiceViewSet(viewsets.ModelViewSet):
    queryset = TaxInvoice.objects.select_related('partner', 'order').all()
    serializer_class = TaxInvoiceSerializer
    permission_classes = [IsManagerOrReadOnly]
    search_fields = ['invoice_number', 'description']
    filterset_fields = ['invoice_type', 'partner']
