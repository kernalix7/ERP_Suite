from django.db import models
from simple_history.admin import SimpleHistoryAdmin  # noqa: F401
from simple_history.models import HistoricalRecords

from apps.core.fields import EncryptedCharField
from apps.core.models import BaseModel


class StoreModuleConfig(BaseModel):
    VALUE_TYPE_CHOICES = [
        ('text', '텍스트'),
        ('password', '비밀번호'),
        ('number', '숫자'),
        ('url', 'URL'),
        ('boolean', '예/아니오'),
    ]

    module_id = models.CharField('모듈 ID', max_length=50)
    key = models.CharField('설정 키', max_length=100)
    value = EncryptedCharField('설정 값', max_length=1000, blank=True)
    display_name = models.CharField('표시명', max_length=200)
    is_secret = models.BooleanField('비밀값 여부', default=False)
    value_type = models.CharField(
        '값 유형', max_length=20, choices=VALUE_TYPE_CHOICES, default='text'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '스토어 모듈 설정'
        verbose_name_plural = '스토어 모듈 설정'
        unique_together = [('module_id', 'key')]
        ordering = ['module_id', 'key']

    def __str__(self):
        return f'{self.module_id} - {self.display_name}'

    @classmethod
    def get_value(cls, module_id, key, default=''):
        try:
            config = cls.objects.get(module_id=module_id, key=key)
            return config.value or default
        except cls.DoesNotExist:
            return default

    @classmethod
    def get_all_values(cls, module_id) -> dict:
        configs = cls.objects.filter(module_id=module_id)
        return {c.key: c.value for c in configs}

    @classmethod
    def initialize_for_module(cls, module_instance):
        required_keys = module_instance.get_required_config_keys()
        for key_info in required_keys:
            cls.objects.get_or_create(
                module_id=module_instance.module_id,
                key=key_info['key'],
                defaults={
                    'display_name': key_info.get('display_name', key_info['key']),
                    'is_secret': key_info.get('is_secret', False),
                    'value_type': key_info.get('value_type', 'text'),
                    'value': key_info.get('default', ''),
                },
            )
