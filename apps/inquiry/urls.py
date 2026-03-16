from django.urls import path

from . import views

app_name = 'inquiry'

urlpatterns = [
    path('', views.InquiryDashboardView.as_view(), name='dashboard'),
    path('list/', views.InquiryListView.as_view(), name='inquiry_list'),
    path('create/', views.InquiryCreateView.as_view(), name='inquiry_create'),
    path('<int:pk>/', views.InquiryDetailView.as_view(), name='inquiry_detail'),
    path('<int:pk>/edit/', views.InquiryUpdateView.as_view(), name='inquiry_update'),
    path('<int:pk>/reply/', views.InquiryReplyCreateView.as_view(), name='reply_create'),
    path('<int:pk>/generate/', views.LLMGenerateView.as_view(), name='llm_generate'),
    path('<int:pk>/generate-reply/', views.GenerateReplyView.as_view(), name='inquiry_generate_reply'),
    path('templates/', views.ReplyTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.ReplyTemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/edit/', views.ReplyTemplateUpdateView.as_view(), name='template_update'),
]
