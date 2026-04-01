"""해시 기반 파일 업로드 경로 생성"""
import os
import uuid

from django.db.models.fields.files import FileField  # noqa: F401
from django.utils import timezone
from django.utils.deconstruct import deconstructible


@deconstructible
class hashed_upload_path:
    """upload_to callable — 해시 파일명으로 저장.

    사용: upload_to=hashed_upload_path('attachments')
    결과: attachments/2026/03/a1b2c3d4e5f6...ext
    """

    def __init__(self, base_dir):
        self.base_dir = base_dir

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()
        hashed = uuid.uuid4().hex
        now = timezone.now()
        return f'{self.base_dir}/{now:%Y}/{now:%m}/{hashed}{ext}'
