from django.conf import settings
from django.db import models


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class BaseModel(models.Model):
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='생성자',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    is_active = models.BooleanField('활성', default=True)
    notes = models.TextField('비고', blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])


# 별도 파일에 정의된 모델 import (migration에 포함)
from apps.core.notification import Notification  # noqa: E402, F401
from apps.core.attachment import Attachment  # noqa: E402, F401
from apps.core.audit import AuditAccessLog  # noqa: E402, F401
