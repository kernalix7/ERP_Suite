from django.urls import path
from . import views
from apps.core.excel_views import WikiArticleExcelView

app_name = 'wiki'

urlpatterns = [
    path('export/articles/', WikiArticleExcelView.as_view(), name='article_excel'),
    # Space
    path('', views.WikiSpaceListView.as_view(), name='space_list'),
    path('spaces/create/', views.WikiSpaceCreateView.as_view(), name='space_create'),
    path('spaces/<str:code>/categories/', views.WikiCategoryTreeView.as_view(), name='category_tree'),

    # Articles
    path('articles/', views.WikiArticleListView.as_view(), name='article_list'),
    path('articles/create/', views.WikiArticleCreateView.as_view(), name='article_create'),
    path('articles/search/', views.WikiArticleSearchView.as_view(), name='article_search'),
    path('articles/recent/', views.RecentChangesView.as_view(), name='recent_changes'),
    path('articles/popular/', views.PopularArticlesView.as_view(), name='popular_articles'),
    path('articles/mine/', views.MyArticlesView.as_view(), name='my_articles'),

    # Categories
    path('categories/', views.WikiCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.WikiCategoryCreateView.as_view(), name='category_create'),

    # Article detail/edit/history
    path('articles/<slug:slug>/', views.WikiArticleDetailView.as_view(), name='article_detail'),
    path('articles/<slug:slug>/edit/', views.WikiArticleUpdateView.as_view(), name='article_update'),
    path('articles/<slug:slug>/history/', views.ArticleRevisionListView.as_view(), name='article_history'),

    # Revisions
    path('revisions/<int:pk>/', views.ArticleRevisionDetailView.as_view(), name='revision_detail'),

    # Comments
    path('articles/<int:article_pk>/comments/', views.ArticleCommentCreateView.as_view(), name='comment_create'),
]
