from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Board(BaseModel):
    """게시판 분류"""

    class PermissionLevel(models.TextChoices):
        ANYONE = 'anyone', '전체'
        STAFF = 'staff', '직원'
        MANAGER = 'manager', '매니저'
        ADMIN = 'admin', '관리자'

    name = models.CharField('게시판명', max_length=50)
    slug = models.SlugField('슬러그', unique=True)
    description = models.TextField('설명', blank=True)
    is_notice = models.BooleanField('공지사항 게시판', default=False)
    permission_level = models.CharField(
        '글쓰기 권한',
        max_length=20,
        choices=PermissionLevel.choices,
        default=PermissionLevel.STAFF,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '게시판'
        verbose_name_plural = '게시판'
        ordering = ['name']

    def __str__(self):
        return self.name


class Post(BaseModel):
    """게시글"""

    board = models.ForeignKey(
        Board,
        verbose_name='게시판',
        on_delete=models.PROTECT,
        related_name='posts',
    )
    title = models.CharField('제목', max_length=200)
    content = models.TextField('내용')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='작성자',
        on_delete=models.PROTECT,
        related_name='board_posts',
    )
    is_pinned = models.BooleanField('상단 고정', default=False)
    view_count = models.PositiveIntegerField('조회수', default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '게시글'
        verbose_name_plural = '게시글'
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['board', 'is_active'], name='idx_post_board_active'),
        ]

    def __str__(self):
        return self.title


class Comment(BaseModel):
    """댓글"""

    post = models.ForeignKey(
        Post,
        verbose_name='게시글',
        on_delete=models.CASCADE,
        related_name='comments',
    )
    content = models.TextField('내용')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='작성자',
        on_delete=models.PROTECT,
        related_name='board_comments',
    )
    parent = models.ForeignKey(
        'self',
        verbose_name='상위 댓글',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '댓글'
        verbose_name_plural = '댓글'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post'], name='idx_comment_post'),
        ]

    def __str__(self):
        return f'{self.author} - {self.content[:30]}'
