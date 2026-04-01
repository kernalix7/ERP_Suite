from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'inquiry'

urlpatterns = [
    path('', views.InquiryDashboardView.as_view(), name='dashboard'),
    path('list/', views.InquiryListView.as_view(), name='inquiry_list'),
    path('create/', views.InquiryCreateView.as_view(), name='inquiry_create'),
    path('templates/', views.ReplyTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.ReplyTemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/edit/', views.ReplyTemplateUpdateView.as_view(), name='template_update'),
    path('channels/', views.InquiryChannelListView.as_view(), name='channel_list'),
    path('channels/create/', views.InquiryChannelCreateView.as_view(), name='channel_create'),
    path('channels/<int:pk>/edit/', views.InquiryChannelUpdateView.as_view(), name='channel_update'),
    path('excel/', excel_views.InquiryExcelView.as_view(), name='inquiry_excel'),
    path('<str:slug>/', views.InquiryDetailView.as_view(), name='inquiry_detail'),
    path('<str:slug>/edit/', views.InquiryUpdateView.as_view(), name='inquiry_update'),
    path('<str:slug>/reply/', views.InquiryReplyCreateView.as_view(), name='reply_create'),
    path('<str:slug>/generate/', views.LLMGenerateView.as_view(), name='llm_generate'),
    path('<str:slug>/generate-reply/', views.GenerateReplyView.as_view(), name='inquiry_generate_reply'),
]
