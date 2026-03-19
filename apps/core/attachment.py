"""증빙/증적 파일 첨부 시스템 - 모든 모듈에서 공통 사용"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models


ALLOWED_EXTENSIONS = [
    'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp',
    'xlsx', 'xls', 'csv', 'doc', 'docx', 'hwp', 'hwpx',
    'zip', 'txt',
]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# MIME type whitelist mapped to allowed extensions
ALLOWED_MIME_TYPES = {
    'application/pdf': 'pdf',
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.ms-excel': 'xls',
    'text/csv': 'csv',
    'application/csv': 'csv',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/x-hwp': 'hwp',
    'application/haansofthwp': 'hwp',
    'application/vnd.hancom.hwpx': 'hwpx',
    'application/zip': 'zip',
    'text/plain': 'txt',
    'application/octet-stream': None,  # checked via extension only
}


def validate_file_content_type(uploaded_file):
    """Validate file MIME type matches its extension."""
    content_type = getattr(uploaded_file, 'content_type', '')
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f'허용되지 않는 파일 형식입니다: {content_type}'
        )


class Attachment(models.Model):
    """증빙/증적 첨부파일 (GenericFK로 어떤 모델에든 연결 가능)"""

    class DocType(models.TextChoices):
        EVIDENCE = 'EVIDENCE', '증빙'
        RECEIPT = 'RECEIPT', '영수증'
        INVOICE = 'INVOICE', '세금계산서'
        CONTRACT = 'CONTRACT', '계약서'
        PHOTO = 'PHOTO', '사진'
        REPORT = 'REPORT', '보고서'
        OTHER = 'OTHER', '기타'

    # GenericForeignKey - 어떤 모델이든 연결 가능
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    file = models.FileField(
        '파일', upload_to='attachments/%Y/%m/',
        validators=[
            FileExtensionValidator(ALLOWED_EXTENSIONS),
            validate_file_content_type,
        ],
    )
    original_filename = models.CharField('원본파일명', max_length=255)
    file_size = models.PositiveIntegerField('파일크기(bytes)', default=0)
    doc_type = models.CharField(
        '문서유형', max_length=20,
        choices=DocType.choices, default=DocType.OTHER,
    )
    description = models.CharField('설명', max_length=200, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='업로더',
        null=True, on_delete=models.SET_NULL,
    )
    uploaded_at = models.DateTimeField('업로드일', auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = '첨부파일'
        verbose_name_plural = '첨부파일'

    def __str__(self):
        return f'{self.original_filename} ({self.get_doc_type_display()})'

    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f'{self.file_size} B'
        elif self.file_size < 1024 * 1024:
            return f'{self.file_size / 1024:.1f} KB'
        return f'{self.file_size / (1024 * 1024):.1f} MB'

    @property
    def is_image(self):
        ext = self.original_filename.rsplit('.', 1)[-1].lower()
        return ext in ('jpg', 'jpeg', 'png', 'gif', 'webp')
