from django.urls import path

from . import views

app_name = 'module_manager'

urlpatterns = [
    path('', views.ModuleListView.as_view(), name='module_list'),
    path('<int:pk>/toggle/', views.ModuleToggleView.as_view(), name='module_toggle'),
    path('<int:pk>/settings/', views.ModuleSettingsView.as_view(), name='module_settings'),
]
