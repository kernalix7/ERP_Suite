from django import forms
from apps.core.forms import BaseForm
from .models import WikiSpace, WikiCategory, WikiArticle, ArticleComment, ArticleAttachment


class WikiSpaceForm(BaseForm):
    class Meta:
        model = WikiSpace
        fields = ['name', 'code', 'description', 'is_public', 'owner', 'notes']


class WikiCategoryForm(BaseForm):
    class Meta:
        model = WikiCategory
        fields = ['space', 'name', 'slug', 'parent', 'sort_order', 'notes']

    def __init__(self, *args, space=None, **kwargs):
        super().__init__(*args, **kwargs)
        if space:
            self.fields['parent'].queryset = WikiCategory.objects.filter(
                space=space, is_active=True,
            )


class WikiArticleForm(BaseForm):
    class Meta:
        model = WikiArticle
        fields = [
            'space', 'category', 'title', 'slug', 'content',
            'status', 'is_pinned', 'tags', 'notes',
        ]
        widgets = {
            'content': forms.Textarea(attrs={'rows': 20, 'class': 'form-input font-mono'}),
        }


class ArticleCommentForm(BaseForm):
    class Meta:
        model = ArticleComment
        fields = ['content', 'parent']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'class': 'form-input'}),
        }


class ArticleAttachmentForm(BaseForm):
    class Meta:
        model = ArticleAttachment
        fields = ['article', 'file', 'file_name']


class ArticleSearchForm(forms.Form):
    q = forms.CharField(
        label='검색어', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '제목 또는 본문 검색...'}),
    )
    space = forms.ModelChoiceField(
        label='공간', queryset=None,
        required=False, empty_label='전체 공간',
    )
    tag = forms.CharField(
        label='태그', max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '태그 검색'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['space'].queryset = WikiSpace.objects.filter(is_active=True)
