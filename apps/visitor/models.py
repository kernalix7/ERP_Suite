from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords
from apps.core.models import BaseModel


class VisitorPurpose(BaseModel):
    """방문 목적 코드"""
    name = models.CharField('방문목적', max_length=100)
    code = models.CharField('코드', max_length=20, unique=True)
    requires_escort = models.BooleanField('에스코트 필요', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '방문목적'
        verbose_name_plural = '방문목적'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class Visitor(BaseModel):
    """방문자 마스터"""
    name = models.CharField('방문자명', max_length=100)
    company = models.CharField('소속회사', max_length=200, blank=True)
    phone = models.CharField('연락처', max_length=20, blank=True)
    email = models.EmailField('이메일', blank=True)
    id_type = models.CharField('신분증종류', max_length=50, blank=True)
    id_number_masked = models.CharField('신분증번호(마스킹)', max_length=50, blank=True)
    photo = models.ImageField('사진', upload_to='visitor/photos/', blank=True)
    blacklisted = models.BooleanField('블랙리스트', default=False)
    blacklist_reason = models.TextField('블랙리스트 사유', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '방문자'
        verbose_name_plural = '방문자'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.company or "-"})'


class VisitRequest(BaseModel):
    """방문 예약 (사전 신청)"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '승인대기'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '거부'
        CANCELLED = 'CANCELLED', '취소'
        VISITED = 'VISITED', '방문완료'

    visit_number = models.CharField('방문번호', max_length=20, unique=True, blank=True)
    visitor = models.ForeignKey(
        Visitor, verbose_name='방문자',
        on_delete=models.PROTECT, related_name='visit_requests',
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='방문대상자(호스트)',
        on_delete=models.PROTECT, related_name='hosting_visits',
    )
    purpose = models.ForeignKey(
        VisitorPurpose, verbose_name='방문목적',
        on_delete=models.PROTECT, related_name='visit_requests',
    )
    department = models.ForeignKey(
        'hr.Department', verbose_name='방문부서',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    scheduled_at = models.DateTimeField('예정 방문일시')
    expected_duration_minutes = models.PositiveIntegerField('예상소요시간(분)', default=60)
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.TextField('거부사유', blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='승인자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approved_visits',
    )
    approved_at = models.DateTimeField('승인일시', null=True, blank=True)
    visitor_count = models.PositiveIntegerField('방문 인원수', default=1)
    description = models.TextField('방문 내용', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '방문예약'
        verbose_name_plural = '방문예약'
        ordering = ['-scheduled_at']

    def __str__(self):
        return f'[{self.visit_number}] {self.visitor.name} → {self.host.get_full_name() or self.host.username}'

    def clean(self):
        super().clean()
        if self.pk:
            old_status = (
                VisitRequest.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            )
            if old_status and old_status != self.status:
                valid_transitions = {
                    VisitRequest.Status.PENDING: [
                        VisitRequest.Status.APPROVED,
                        VisitRequest.Status.REJECTED,
                        VisitRequest.Status.CANCELLED,
                    ],
                    VisitRequest.Status.APPROVED: [
                        VisitRequest.Status.VISITED,
                        VisitRequest.Status.CANCELLED,
                    ],
                    VisitRequest.Status.REJECTED: [],
                    VisitRequest.Status.CANCELLED: [],
                    VisitRequest.Status.VISITED: [],
                }
                if self.status not in valid_transitions.get(old_status, []):
                    raise ValidationError(
                        f'{self.get_status_display()} 상태에서 {VisitRequest.Status(self.status).label}(으)로 전이할 수 없습니다.'
                    )

    def save(self, *args, **kwargs):
        if not self.visit_number:
            from apps.core.utils import generate_document_number
            self.visit_number = generate_document_number(VisitRequest, 'visit_number', 'VIS')
        super().save(*args, **kwargs)


class VisitLog(BaseModel):
    """실제 방문 기록 (체크인/체크아웃)"""
    visit_request = models.OneToOneField(
        VisitRequest, verbose_name='방문예약',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='visit_log',
    )
    visitor = models.ForeignKey(
        Visitor, verbose_name='방문자',
        on_delete=models.PROTECT, related_name='visit_logs',
    )
    check_in_at = models.DateTimeField('체크인일시', default=timezone.now)
    check_out_at = models.DateTimeField('체크아웃일시', null=True, blank=True)
    badge_number = models.CharField('방문증번호', max_length=20, blank=True)
    receptionist = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='접수담당자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='processed_visits',
    )
    temperature = models.DecimalField('체온', max_digits=4, decimal_places=1, null=True, blank=True)
    remarks = models.TextField('특이사항', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '방문기록'
        verbose_name_plural = '방문기록'
        ordering = ['-check_in_at']

    def __str__(self):
        return f'{self.visitor.name} 체크인 {self.check_in_at:%Y-%m-%d %H:%M}'

    @property
    def duration_minutes(self):
        if self.check_out_at:
            delta = self.check_out_at - self.check_in_at
            return int(delta.total_seconds() / 60)
        return None


class VisitorNDA(BaseModel):
    """방문자 NDA 서명"""
    visit_log = models.OneToOneField(
        VisitLog, verbose_name='방문기록',
        on_delete=models.PROTECT, related_name='nda',
    )
    signed_at = models.DateTimeField('서명일시', default=timezone.now)
    signature_image = models.ImageField('서명이미지', upload_to='visitor/signatures/', blank=True)
    nda_version = models.CharField('NDA버전', max_length=20, default='1.0')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '방문자NDA'
        verbose_name_plural = '방문자NDA'
        ordering = ['-signed_at']

    def __str__(self):
        return f'{self.visit_log.visitor.name} NDA {self.signed_at:%Y-%m-%d}'
