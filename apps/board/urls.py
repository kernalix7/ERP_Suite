from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'board'

urlpatterns = [
    path('', views.BoardListView.as_view(), name='board_list'),
    path('<slug:slug>/', views.PostListView.as_view(), name='post_list'),
    path('<slug:slug>/create/', views.PostCreateView.as_view(), name='post_create'),
    path('post/<int:pk>/', views.PostDetailView.as_view(), name='post_detail'),
    path('post/<int:pk>/edit/', views.PostUpdateView.as_view(), name='post_update'),
    path('post/<int:pk>/delete/', views.PostDeleteView.as_view(), name='post_delete'),
    path('post/<int:pk>/comment/', views.CommentCreateView.as_view(), name='comment_create'),
    # Excel 내보내기
    path('posts/excel/', excel_views.PostExcelView.as_view(), name='post_excel'),
]
