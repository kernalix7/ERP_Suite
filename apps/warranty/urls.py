from django.urls import path
from . import views

app_name = 'warranty'

urlpatterns = [
    path('', views.RegistrationListView.as_view(), name='registration_list'),
    path('create/', views.RegistrationCreateView.as_view(), name='registration_create'),
    path('<int:pk>/', views.RegistrationDetailView.as_view(), name='registration_detail'),
    path('<int:pk>/edit/', views.RegistrationUpdateView.as_view(), name='registration_update'),
    path('check/', views.SerialCheckView.as_view(), name='serial_check'),
    path('verify/', views.WarrantyVerifyView.as_view(), name='warranty_verify'),
]
