from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class EDIPartner(BaseModel):
    """EDI 거래처"""
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='edi_profiles',
    )
    edi_id = models.CharField('EDI ID', max_length=50, unique=True)

    class Protocol(models.TextChoices):
        FTP = 'FTP', 'FTP'
        SFTP = 'SFTP', 'SFTP'
        AS2 = 'AS2', 'AS2'
        API = 'API', 'API'

    protocol = models.CharField(
        '프로토콜', max_length=10,
        choices=Protocol.choices, default=Protocol.API,
    )
    # TODO: connection_settings에 비밀번호/API키 등 민감정보 포함 가능 — EncryptedJSONField 도입 검토
    connection_settings = models.JSONField('연결 설정', default=dict, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'EDI 거래처'
        verbose_name_plural = 'EDI 거래처'
        ordering = ['edi_id']

    def __str__(self):
        return f'{self.partner.name} ({self.edi_id})'


class EDIDocumentType(BaseModel):
    """EDI 문서 유형"""

    class Direction(models.TextChoices):
        INBOUND = 'INBOUND', '수신'
        OUTBOUND = 'OUTBOUND', '발신'

    class Format(models.TextChoices):
        XML = 'XML', 'XML'
        JSON = 'JSON', 'JSON'
        CSV = 'CSV', 'CSV'
        EDIFACT = 'EDIFACT', 'EDIFACT'

    code = models.CharField('문서코드', max_length=20, unique=True)
    name = models.CharField('문서명', max_length=100)
    direction = models.CharField(
        '방향', max_length=10,
        choices=Direction.choices,
    )
    format = models.CharField(
        '포맷', max_length=10,
        choices=Format.choices, default=Format.XML,
    )
    mapping_template = models.JSONField('매핑 템플릿', default=dict, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'EDI 문서유형'
        verbose_name_plural = 'EDI 문서유형'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class EDITransaction(BaseModel):
    """EDI 트랜잭션"""
    BUSINESS_KEY_FIELD = 'transaction_id'

    class Direction(models.TextChoices):
        INBOUND = 'INBOUND', '수신'
        OUTBOUND = 'OUTBOUND', '발신'

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        SENT = 'SENT', '전송됨'
        RECEIVED = 'RECEIVED', '수신됨'
        PROCESSED = 'PROCESSED', '처리완료'
        ERROR = 'ERROR', '오류'

    transaction_id = models.CharField('트랜잭션 ID', max_length=20, unique=True, blank=True)
    partner = models.ForeignKey(
        EDIPartner, verbose_name='EDI 거래처',
        on_delete=models.PROTECT, related_name='transactions',
    )
    document_type = models.ForeignKey(
        EDIDocumentType, verbose_name='문서 유형',
        on_delete=models.PROTECT, related_name='transactions',
    )
    direction = models.CharField(
        '방향', max_length=10,
        choices=Direction.choices,
    )
    status = models.CharField(
        '상태', max_length=10,
        choices=Status.choices, default=Status.PENDING,
    )
    payload = models.TextField('데이터', blank=True)
    processed_at = models.DateTimeField('처리일시', null=True, blank=True)
    error_message = models.TextField('오류 메시지', blank=True)
    related_content_type = models.ForeignKey(
        ContentType, verbose_name='관련 모델',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    related_object_id = models.PositiveIntegerField('관련 객체 ID', null=True, blank=True)
    related_object = GenericForeignKey('related_content_type', 'related_object_id')

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'EDI 트랜잭션'
        verbose_name_plural = 'EDI 트랜잭션'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='idx_edi_tx_status'),
            models.Index(fields=['direction'], name='idx_edi_tx_direction'),
        ]

    def __str__(self):
        return f'{self.transaction_id} ({self.get_status_display()})'

    STATUS_TRANSITIONS = {
        'PENDING': ['SENT', 'RECEIVED', 'ERROR'],
        'SENT': ['PROCESSED', 'ERROR'],
        'RECEIVED': ['PROCESSED', 'ERROR'],
        'PROCESSED': [],
        'ERROR': ['PENDING'],
    }

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.pk:
            old_status = EDITransaction.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if old_status and old_status != self.status:
                allowed = self.STATUS_TRANSITIONS.get(old_status, [])
                if self.status not in allowed:
                    old_label = dict(self.Status.choices).get(old_status, old_status)
                    new_label = dict(self.Status.choices).get(self.status, self.status)
                    raise ValidationError(
                        f'{old_label}에서 {new_label}(으)로 전이할 수 없습니다.'
                    )

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = generate_document_number(
                EDITransaction, 'transaction_id', 'EDI',
            )
        super().save(*args, **kwargs)


class EDIMapping(BaseModel):
    """EDI 필드 매핑"""
    document_type = models.ForeignKey(
        EDIDocumentType, verbose_name='문서 유형',
        on_delete=models.PROTECT, related_name='mappings',
    )
    source_field = models.CharField('원본 필드', max_length=100)
    target_model = models.CharField('대상 모델', max_length=100)
    target_field = models.CharField('대상 필드', max_length=100)
    transformation = models.CharField('변환 규칙', max_length=200, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'EDI 매핑'
        verbose_name_plural = 'EDI 매핑'
        ordering = ['document_type', 'source_field']

    def __str__(self):
        return f'{self.source_field} -> {self.target_model}.{self.target_field}'


class EDISchedule(BaseModel):
    """EDI 스케줄"""

    class Frequency(models.TextChoices):
        HOURLY = 'HOURLY', '매시간'
        DAILY = 'DAILY', '매일'
        WEEKLY = 'WEEKLY', '매주'

    partner = models.ForeignKey(
        EDIPartner, verbose_name='EDI 거래처',
        on_delete=models.PROTECT, related_name='schedules',
    )
    document_type = models.ForeignKey(
        EDIDocumentType, verbose_name='문서 유형',
        on_delete=models.PROTECT, related_name='schedules',
    )
    frequency = models.CharField(
        '빈도', max_length=10,
        choices=Frequency.choices, default=Frequency.DAILY,
    )
    last_run = models.DateTimeField('최근 실행', null=True, blank=True)
    next_run = models.DateTimeField('다음 실행', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'EDI 스케줄'
        verbose_name_plural = 'EDI 스케줄'
        ordering = ['partner', 'document_type']
        unique_together = ['partner', 'document_type']

    def __str__(self):
        return f'{self.partner} - {self.document_type} ({self.get_frequency_display()})'
