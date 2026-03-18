from django import forms

from apps.core.forms import BaseForm
from .models import Post, Comment


class PostForm(BaseForm):
    class Meta:
        model = Post
        fields = ['board', 'title', 'content', 'is_pinned', 'notes']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # 매니저 이상만 상단 고정 가능
        if self.user and self.user.role not in ('admin', 'manager'):
            self.fields.pop('is_pinned', None)


class CommentForm(BaseForm):
    class Meta:
        model = Comment
        fields = ['content', 'parent']
        widgets = {
            'parent': forms.HiddenInput(),
        }
