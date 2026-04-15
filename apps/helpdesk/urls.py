from django.urls import path

from . import views

app_name = 'helpdesk'

urlpatterns = [
    # Dashboard
    path('', views.HelpdeskDashboardView.as_view(), name='dashboard'),

    # Tickets
    path('tickets/', views.TicketListView.as_view(), name='ticket_list'),
    path('tickets/my/', views.MyTicketListView.as_view(), name='my_tickets'),
    path('tickets/create/', views.TicketCreateView.as_view(), name='ticket_create'),
    path('tickets/<str:ticket_number>/', views.TicketDetailView.as_view(), name='ticket_detail'),
    path('tickets/<str:ticket_number>/edit/', views.TicketUpdateView.as_view(), name='ticket_update'),
    path('tickets/<str:ticket_number>/assign/', views.TicketAssignView.as_view(), name='ticket_assign'),
    path('tickets/<str:ticket_number>/resolve/', views.TicketResolveView.as_view(), name='ticket_resolve'),
    path('tickets/<str:ticket_number>/close/', views.TicketCloseView.as_view(), name='ticket_close'),
    path('tickets/<str:ticket_number>/comment/', views.TicketCommentCreateView.as_view(), name='ticket_comment'),

    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_update'),

    # SLA
    path('sla/', views.SLAListView.as_view(), name='sla_list'),
    path('sla/create/', views.SLACreateView.as_view(), name='sla_create'),
    path('sla/<int:pk>/edit/', views.SLAUpdateView.as_view(), name='sla_update'),
]
