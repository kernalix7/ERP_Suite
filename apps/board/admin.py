from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Board, Post, Comment


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Board)
class BoardAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'slug', 'is_notice', 'permission_level', 'is_active')
    list_filter = ('is_notice', 'permission_level', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Post)
class PostAdmin(SimpleHistoryAdmin):
    list_display = ('title', 'board', 'author', 'is_pinned', 'view_count', 'created_at')
    list_filter = ('board', 'is_pinned', 'created_at')
    search_fields = ('title', 'content')
    inlines = [CommentInline]


@admin.register(Comment)
class CommentAdmin(SimpleHistoryAdmin):
    list_display = ('post', 'author', 'content_short', 'parent', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('content',)

    @admin.display(description='내용')
    def content_short(self, obj):
        return obj.content[:50]
