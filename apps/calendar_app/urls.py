from django.urls import path

from . import views

app_name = 'calendar_app'

urlpatterns = [
    path('', views.CalendarView.as_view(), name='calendar_view'),
    path('events/', views.EventListView.as_view(), name='event_list'),
    path('events/create/', views.EventCreateView.as_view(), name='event_create'),
    path('events/<int:pk>/edit/', views.EventUpdateView.as_view(), name='event_update'),
    path('events/<int:pk>/delete/', views.EventDeleteView.as_view(), name='event_delete'),
    path('api/events/', views.EventAPIView.as_view(), name='event_api'),
]
