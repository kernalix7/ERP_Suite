from django.conf import settings
from django.db import models


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class BaseModel(models.Model):
    BUSINESS_KEY_FIELD = None  # 하위 모델이 오버라이드 (예: 'order_number')

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
        update_fields = ['is_active', 'updated_at']
        if self.BUSINESS_KEY_FIELD:
            field = self.BUSINESS_KEY_FIELD
            old_val = getattr(self, field)
            if old_val and not str(old_val).startswith('_DEL_'):
                setattr(self, field, f'_DEL_{self.pk}_{old_val}')
                update_fields.append(field)
        self.save(update_fields=update_fields)

    def restore(self):
        update_fields = ['is_active', 'updated_at']
        if self.BUSINESS_KEY_FIELD:
            field = self.BUSINESS_KEY_FIELD
            val = getattr(self, field)
            if val and str(val).startswith('_DEL_'):
                original = str(val).split('_', 3)[3]  # _DEL_{pk}_{original}
                if type(self).objects.filter(**{field: original}).exists():
                    raise ValueError(f'키값 "{original}"이 이미 사용 중입니다.')
                setattr(self, field, original)
                update_fields.append(field)
        self.is_active = True
        self.save(update_fields=update_fields)


# 별도 파일에 정의된 모델 import (migration에 포함)
from apps.core.notification import Notification  # noqa: E402, F401
from apps.core.attachment import Attachment  # noqa: E402, F401
from apps.core.audit import AuditAccessLog  # noqa: E402, F401
from apps.core.system_config import SystemConfig  # noqa: E402, F401
