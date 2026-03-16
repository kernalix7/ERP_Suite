from django import forms

from apps.inventory.forms import BaseForm
from .models import Event


class EventForm(BaseForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'start_datetime', 'end_datetime',
            'all_day', 'event_type', 'color', 'location', 'attendees',
            'is_recurring', 'notes',
        ]
        widgets = {
            'start_datetime': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-input'}
            ),
            'end_datetime': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-input'}
            ),
            'color': forms.TextInput(
                attrs={'type': 'color', 'class': 'form-input h-10 w-16 p-1'}
            ),
            'attendees': forms.SelectMultiple(
                attrs={'class': 'form-input', 'size': '5'}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_datetime')
        end = cleaned.get('end_datetime')
        if start and end and end < start:
            raise forms.ValidationError('종료일시는 시작일시 이후여야 합니다.')
        return cleaned
