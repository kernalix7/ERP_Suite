from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import BOMRevision, Drawing, ECNItem, EngineeringChangeNotice, ProductVersion


@admin.register(ProductVersion)
class ProductVersionAdmin(SimpleHistoryAdmin):
    list_display = ('product', 'version_number', 'status', 'effective_date')
    list_filter = ('status',)
    raw_id_fields = ('product',)


@admin.register(BOMRevision)
class BOMRevisionAdmin(SimpleHistoryAdmin):
    list_display = ('bom', 'revision_number', 'status', 'approved_by', 'approved_at')
    list_filter = ('status',)
    raw_id_fields = ('bom', 'approved_by')


@admin.register(EngineeringChangeNotice)
class EngineeringChangeNoticeAdmin(SimpleHistoryAdmin):
    list_display = ('ecn_number', 'title', 'status', 'priority', 'requested_by', 'target_date')
    list_filter = ('status', 'priority')
    search_fields = ('ecn_number', 'title')
    raw_id_fields = ('requested_by', 'approved_by')


@admin.register(ECNItem)
class ECNItemAdmin(SimpleHistoryAdmin):
    list_display = ('ecn', 'change_type', 'product', 'description')
    list_filter = ('change_type',)
    raw_id_fields = ('ecn', 'product')


@admin.register(Drawing)
class DrawingAdmin(SimpleHistoryAdmin):
    list_display = ('drawing_number', 'product', 'version', 'revision', 'format')
    search_fields = ('drawing_number',)
    raw_id_fields = ('product', 'version')
