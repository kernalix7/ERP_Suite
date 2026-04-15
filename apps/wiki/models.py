from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords
from apps.core.models import BaseModel


class WikiSpace(BaseModel):
    """위키 공간 (Space) — 팀/부서 단위 지식베이스 구분"""
    name = models.CharField('공간명', max_length=100)
    code = models.CharField('코드', max_length=20, unique=True)
    description = models.TextField('설명', blank=True)
    is_public = models.BooleanField('공개 여부', default=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='소유자',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_wiki_spaces',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '위키공간'
        verbose_name_plural = '위키공간'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class WikiCategory(BaseModel):
    """위키 카테고리 (Space 내 분류 트리)"""
    space = models.ForeignKey(
        WikiSpace, verbose_name='공간',
        on_delete=models.PROTECT, related_name='categories',
    )
    name = models.CharField('카테고리명', max_length=100)
    slug = models.SlugField('슬러그', max_length=100)
    parent = models.ForeignKey(
        'self', verbose_name='상위카테고리',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
    )
    sort_order = models.PositiveIntegerField('정렬순서', default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '위키카테고리'
        verbose_name_plural = '위키카테고리'
        unique_together = ('space', 'slug')
        ordering = ['space', 'sort_order', 'name']

    def __str__(self):
        return f'{self.space.code} / {self.name}'


class WikiArticle(BaseModel):
    """위키 문서"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        PUBLISHED = 'PUBLISHED', '게시'
        ARCHIVED = 'ARCHIVED', '보관'

    article_number = models.CharField('문서번호', max_length=20, unique=True, blank=True)
    space = models.ForeignKey(
        WikiSpace, verbose_name='공간',
        on_delete=models.PROTECT, related_name='articles',
    )
    category = models.ForeignKey(
        WikiCategory, verbose_name='카테고리',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='articles',
    )
    title = models.CharField('제목', max_length=300)
    slug = models.SlugField('슬러그', max_length=300, unique=True)
    content = models.TextField('본문')
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.DRAFT)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='작성자',
        on_delete=models.PROTECT, related_name='wiki_articles',
    )
    tags = models.JSONField('태그', default=list, blank=True)
    view_count = models.PositiveIntegerField('조회수', default=0)
    is_pinned = models.BooleanField('고정', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '위키문서'
        verbose_name_plural = '위키문서'
        ordering = ['-updated_at']

    def __str__(self):
        return f'[{self.article_number}] {self.title}'

    def save(self, *args, **kwargs):
        if not self.article_number:
            from apps.core.utils import generate_document_number
            self.article_number = generate_document_number(WikiArticle, 'article_number', 'WIKI')
        super().save(*args, **kwargs)


class ArticleRevision(BaseModel):
    """문서 개정 이력"""
    article = models.ForeignKey(
        WikiArticle, verbose_name='문서',
        on_delete=models.PROTECT, related_name='revisions',
    )
    revision_number = models.PositiveIntegerField('개정번호')
    content = models.TextField('본문 스냅샷')
    change_summary = models.CharField('변경요약', max_length=500, blank=True)
    revised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='편집자',
        on_delete=models.PROTECT, related_name='article_revisions',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '문서개정이력'
        verbose_name_plural = '문서개정이력'
        unique_together = ('article', 'revision_number')
        ordering = ['-revision_number']

    def __str__(self):
        return f'{self.article.title} v{self.revision_number}'


class ArticleComment(BaseModel):
    """문서 댓글 (중첩 지원)"""
    article = models.ForeignKey(
        WikiArticle, verbose_name='문서',
        on_delete=models.PROTECT, related_name='comments',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='작성자',
        on_delete=models.PROTECT, related_name='article_comments',
    )
    content = models.TextField('내용')
    parent = models.ForeignKey(
        'self', verbose_name='상위댓글',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='replies',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '문서댓글'
        verbose_name_plural = '문서댓글'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.article.title} - {self.author.username} 댓글'


class ArticleAttachment(BaseModel):
    """문서 첨부파일"""
    article = models.ForeignKey(
        WikiArticle, verbose_name='문서',
        on_delete=models.PROTECT, related_name='attachments',
    )
    file = models.FileField('파일', upload_to='wiki/attachments/')
    file_name = models.CharField('파일명', max_length=300)
    file_size = models.PositiveIntegerField('파일크기(bytes)', default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='업로더',
        on_delete=models.SET_NULL, null=True,
        related_name='article_attachments',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '문서첨부파일'
        verbose_name_plural = '문서첨부파일'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.article.title} - {self.file_name}'
