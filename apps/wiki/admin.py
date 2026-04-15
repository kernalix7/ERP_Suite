from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import WikiSpace, WikiCategory, WikiArticle, ArticleRevision, ArticleComment, ArticleAttachment


@admin.register(WikiSpace)
class WikiSpaceAdmin(SimpleHistoryAdmin):
    list_display = ['code', 'name', 'is_public', 'owner', 'is_active']
    list_filter = ['is_public', 'is_active']
    search_fields = ['code', 'name']


@admin.register(WikiCategory)
class WikiCategoryAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'space', 'slug', 'parent', 'sort_order', 'is_active']
    list_filter = ['space', 'is_active']
    search_fields = ['name', 'slug']


@admin.register(WikiArticle)
class WikiArticleAdmin(SimpleHistoryAdmin):
    list_display = ['article_number', 'title', 'space', 'status', 'author', 'view_count', 'is_pinned', 'is_active']
    list_filter = ['status', 'space', 'is_pinned', 'is_active']
    search_fields = ['article_number', 'title', 'content']
    raw_id_fields = ['author', 'space', 'category']


@admin.register(ArticleRevision)
class ArticleRevisionAdmin(SimpleHistoryAdmin):
    list_display = ['article', 'revision_number', 'revised_by', 'change_summary', 'created_at']
    list_filter = ['is_active']
    search_fields = ['article__title', 'change_summary']


@admin.register(ArticleComment)
class ArticleCommentAdmin(SimpleHistoryAdmin):
    list_display = ['article', 'author', 'parent', 'created_at', 'is_active']
    list_filter = ['is_active']


@admin.register(ArticleAttachment)
class ArticleAttachmentAdmin(SimpleHistoryAdmin):
    list_display = ['article', 'file_name', 'file_size', 'uploaded_by', 'is_active']
    list_filter = ['is_active']
