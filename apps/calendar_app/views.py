from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import View
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, TemplateView,
)

from .models import Event
from .forms import EventForm


class CalendarView(LoginRequiredMixin, TemplateView):
    template_name = 'calendar_app/calendar.html'


class EventListView(LoginRequiredMixin, ListView):
    model = Event
    template_name = 'calendar_app/event_list.html'
    context_object_name = 'events'
    paginate_by = 20

    def get_queryset(self):
        return (
            Event.objects.filter(is_active=True, end_datetime__gte=timezone.now())
            .select_related('creator')
            .order_by('start_datetime')
        )


class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'calendar_app/event_form.html'

    def form_valid(self, form):
        form.instance.creator = self.request.user
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('calendar_app:calendar_view')


class EventUpdateView(LoginRequiredMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'calendar_app/event_form.html'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.creator != request.user and not request.user.is_admin_role:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('calendar_app:calendar_view')


class EventDeleteView(LoginRequiredMixin, DeleteView):
    model = Event
    template_name = 'calendar_app/event_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.creator != request.user and not request.user.is_admin_role:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('calendar_app:calendar_view')

    def form_valid(self, form):
        """Soft delete instead of hard delete."""
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.soft_delete()
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(success_url)


class EventAPIView(LoginRequiredMixin, View):
    """JSON endpoint for FullCalendar AJAX requests."""

    @staticmethod
    def _parse_aware(value, use_end_of_day=False):
        """날짜/시간 문자열을 timezone-aware datetime으로 변환"""
        from datetime import datetime as dt_cls, time
        from django.utils.dateparse import parse_datetime, parse_date
        # parse_date 우선: 날짜만 있는 문자열에 use_end_of_day 적용
        d = parse_date(value)
        if d:
            t = time(23, 59, 59) if use_end_of_day else time(0, 0, 0)
            return timezone.make_aware(dt_cls.combine(d, t))
        result = parse_datetime(value)
        if result and timezone.is_naive(result):
            result = timezone.make_aware(result)
        return result

    def get(self, request):
        start = request.GET.get('start')
        end = request.GET.get('end')

        qs = Event.objects.filter(is_active=True).select_related('creator')
        if start:
            start_dt = self._parse_aware(start)
            if start_dt:
                qs = qs.filter(end_datetime__gte=start_dt)
        if end:
            end_dt = self._parse_aware(end, use_end_of_day=True)
            if end_dt:
                qs = qs.filter(start_datetime__lte=end_dt)

        events = []
        for event in qs:
            events.append({
                'id': event.pk,
                'title': event.title,
                'start': event.start_datetime.isoformat(),
                'end': event.end_datetime.isoformat(),
                'allDay': event.all_day,
                'color': event.color,
                'url': reverse('calendar_app:event_update', kwargs={'pk': event.pk}),
                'extendedProps': {
                    'event_type': event.get_event_type_display(),
                    'location': event.location,
                    'creator': str(event.creator),
                    'description': event.description,
                },
            })
        return JsonResponse(events, safe=False)
