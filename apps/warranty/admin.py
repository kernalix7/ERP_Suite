from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import ProductRegistration


@admin.register(ProductRegistration)
class ProductRegistrationAdmin(SimpleHistoryAdmin):
    list_display = ('serial_number', 'product', 'customer_name', 'phone', 'purchase_date', 'is_verified')
    search_fields = ('serial_number', 'customer_name')
    list_filter = ('is_verified',)
