from apps.core.forms import BaseForm
from .models import BinLocation, PickOrder, PickOrderItem, PutAwayTask, WarehouseZone, WavePlan


class WarehouseZoneForm(BaseForm):
    class Meta:
        model = WarehouseZone
        fields = ['warehouse', 'name', 'code', 'zone_type', 'description', 'notes']


class BinLocationForm(BaseForm):
    class Meta:
        model = BinLocation
        fields = ['zone', 'code', 'row', 'column', 'level', 'max_weight', 'notes']


class PickOrderForm(BaseForm):
    class Meta:
        model = PickOrder
        fields = ['order', 'priority', 'assigned_to', 'notes']


class PickOrderItemForm(BaseForm):
    class Meta:
        model = PickOrderItem
        fields = ['product', 'bin_location', 'quantity']


class PutAwayTaskForm(BaseForm):
    class Meta:
        model = PutAwayTask
        fields = ['goods_receipt', 'product', 'quantity', 'suggested_bin', 'assigned_to', 'notes']


class WavePlanForm(BaseForm):
    class Meta:
        model = WavePlan
        fields = ['name', 'pick_orders', 'notes']
