from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class InstalledModule(BaseModel):
    CATEGORY_CHOICES = [
        ('COMPLIANCE', '법규/컴플라이언스'),
        ('PRODUCTION', '생산'),
        ('PURCHASE', '구매'),
        ('SALES', '영업/CRM'),
        ('ACCOUNTING', '회계/재무'),
        ('HR', '인사/급여'),
        ('GROUPWARE', '그룹웨어'),
        ('SYSTEM', '시스템'),
    ]

    module_id = models.CharField('모듈 ID', max_length=100, unique=True)
    name = models.CharField('모듈명', max_length=200)
    description = models.TextField('설명', blank=True)
    category = models.CharField('카테고리', max_length=50, choices=CATEGORY_CHOICES)
    country_code = models.CharField(
        '국가코드', max_length=10, blank=True, default='',
        help_text='ISO 3166-1 코드. 빈 값은 범용 모듈.',
    )
    is_enabled = models.BooleanField('활성화', default=False)
    settings = models.JSONField('설정', default=dict, blank=True)
    version = models.CharField('버전', max_length=20, default='1.0.0')
    icon = models.CharField('아이콘', max_length=50, blank=True)
    dependencies = models.JSONField('의존성', default=list, blank=True)
    sort_order = models.IntegerField('정렬순서', default=0)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '설치된 모듈'
        verbose_name_plural = '설치된 모듈'
        ordering = ['sort_order', 'category', 'name']

    def __str__(self):
        return f'{self.name} ({self.module_id})'
