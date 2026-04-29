from django.urls import path

from . import views

app_name = 'localizations'

urlpatterns = [
    path('countries/', views.CountryListView.as_view(), name='country_list'),
]
