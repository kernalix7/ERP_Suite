from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class PortalUser(BaseModel):
    """포털 사용자 (고객 또는 공급처)"""

    class PortalType(models.TextChoices):
        CUSTOMER = 'CUSTOMER', '고객'
        SUPPLIER = 'SUPPLIER', '공급처'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='사용자',
        on_delete=models.PROTECT, related_name='portal_profile',
    )
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='portal_users',
    )
    portal_type = models.CharField(
        '포털 유형', max_length=10,
        choices=PortalType.choices, default=PortalType.CUSTOMER,
    )
    is_verified = models.BooleanField('인증 여부', default=False)
    last_portal_login = models.DateTimeField('최근 포털 로그인', null=True, blank=True)
    permissions = models.JSONField('권한 설정', default=dict, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '포털 사용자'
        verbose_name_plural = '포털 사용자'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} ({self.partner.name})'


class PortalNotification(BaseModel):
    """포털 알림"""
    portal_user = models.ForeignKey(
        PortalUser, verbose_name='포털 사용자',
        on_delete=models.PROTECT, related_name='notifications',
    )
    title = models.CharField('제목', max_length=200)
    message = models.TextField('내용')
    is_read = models.BooleanField('읽음', default=False)
    link = models.CharField('링크', max_length=500, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '포털 알림'
        verbose_name_plural = '포털 알림'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.portal_user} - {self.title}'


class PortalDocument(BaseModel):
    """포털 문서"""

    class DocumentType(models.TextChoices):
        INVOICE = 'INVOICE', '세금계산서'
        PO = 'PO', '발주서'
        DELIVERY = 'DELIVERY', '배송확인서'
        CONTRACT = 'CONTRACT', '계약서'

    portal_user = models.ForeignKey(
        PortalUser, verbose_name='포털 사용자',
        on_delete=models.PROTECT, related_name='documents',
    )
    document_type = models.CharField(
        '문서 유형', max_length=10,
        choices=DocumentType.choices,
    )
    title = models.CharField('제목', max_length=200)
    file = models.FileField('파일', upload_to='portal/documents/%Y/%m/')
    related_content_type = models.ForeignKey(
        ContentType, verbose_name='관련 모델',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    related_object_id = models.PositiveIntegerField('관련 객체 ID', null=True, blank=True)
    related_object = GenericForeignKey('related_content_type', 'related_object_id')

    history = HistoricalRecords()

    class Meta:
        verbose_name = '포털 문서'
        verbose_name_plural = '포털 문서'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.get_document_type_display()})'
