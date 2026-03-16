from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Event


@admin.register(Event)
class EventAdmin(SimpleHistoryAdmin):
    list_display = ('title', 'event_type', 'start_datetime', 'end_datetime', 'all_day', 'creator', 'is_active')
    list_filter = ('event_type', 'all_day', 'is_recurring', 'start_datetime')
    search_fields = ('title', 'description', 'location')
    filter_horizontal = ('attendees',)
