from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.fields import EncryptedCharField
from apps.core.models import BaseModel


class SystemConfig(BaseModel):
    """시스템 설정 — 카테고리별 API/서비스 설정 저장소"""

    class Category(models.TextChoices):
        NTS = 'NTS', '국세청 API'
        MARKETPLACE = 'MARKETPLACE', '마켓플레이스'
        SHIPPING = 'SHIPPING', '택배/배송'
        EMAIL = 'EMAIL', '이메일'
        AI = 'AI', 'AI/자동화'
        ADDRESS = 'ADDRESS', '주소검색'
        GENERAL = 'GENERAL', '일반'
        COMPANY = 'COMPANY', '회사정보'
        HR = 'HR', '인사'
        SECURITY = 'SECURITY', '보안'
        BACKUP = 'BACKUP', '백업/복구'

    class ValueType(models.TextChoices):
        TEXT = 'text', '텍스트'
        PASSWORD = 'password', '비밀번호'
        URL = 'url', 'URL'
        NUMBER = 'number', '숫자'
        BOOLEAN = 'boolean', '참/거짓'
        FILE = 'file', '파일경로'

    category = models.CharField(
        '카테고리', max_length=20, choices=Category.choices,
    )
    key = models.CharField('설정키', max_length=100)
    value = EncryptedCharField('설정값', max_length=1000, blank=True)
    display_name = models.CharField('표시명', max_length=200)
    description = models.TextField('설명', blank=True)
    is_secret = models.BooleanField(
        '민감정보', default=False,
        help_text='마스킹 표시 여부',
    )
    value_type = models.CharField(
        '값 타입', max_length=20,
        choices=ValueType.choices, default=ValueType.TEXT,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '시스템 설정'
        verbose_name_plural = '시스템 설정'
        unique_together = ('category', 'key')
        ordering = ['category', 'key']

    def __str__(self):
        return f'[{self.get_category_display()}] {self.display_name}'

    @property
    def masked_value(self):
        """민감정보인 경우 마스킹된 값 반환"""
        if self.is_secret and self.value:
            return '*' * 8
        return self.value

    @classmethod
    def get_value(cls, category, key, default=''):
        """설정값 조회 헬퍼"""
        try:
            config = cls.objects.get(category=category, key=key)
            return config.value or default
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_value(cls, category, key, value, **kwargs):
        """설정값 저장 헬퍼"""
        config, created = cls.all_objects.get_or_create(
            category=category,
            key=key,
            defaults={
                'value': value,
                'display_name': kwargs.get('display_name', key),
                'description': kwargs.get('description', ''),
                'is_secret': kwargs.get('is_secret', False),
                'value_type': kwargs.get('value_type', cls.ValueType.TEXT),
            },
        )
        if not created:
            config.value = value
            config.is_active = True
            config.save(update_fields=['value', 'is_active', 'updated_at'])
        return config

    @classmethod
    def initialize_defaults(cls):
        """카테고리별 기본 설정값 초기화 (이미 존재하면 건너뜀)"""
        defaults = [
            # 회사정보
            ('COMPANY', 'company_name', '', '회사명', '', False, 'text'),
            ('COMPANY', 'business_number', '', '사업자번호', '', False, 'text'),
            ('COMPANY', 'ceo_name', '', '대표자', '', False, 'text'),
            ('COMPANY', 'company_address', '', '주소', '', False, 'text'),
            ('COMPANY', 'company_phone', '', '전화번호', '', False, 'text'),
            # 주소검색 API
            ('ADDRESS', 'JUSO_API_KEY', '', '도로명주소 API 키', '행안부 도로명주소 API 인증키 (juso.go.kr에서 발급)', True, 'password'),
            # 국세청 API
            ('NTS', 'business_number', '', '사업자번호', '국세청 API 사업자번호', False, 'text'),
            ('NTS', 'cert_path', '', '인증서 경로', '공인인증서 파일 경로', False, 'file'),
            ('NTS', 'api_key', '', 'API 키', '국세청 API 인증 키', True, 'password'),
            ('NTS', 'api_secret', '', 'API 시크릿', '국세청 API 시크릿', True, 'password'),
            ('NTS', 'environment', 'test', '환경', 'test 또는 prod', False, 'text'),
            # 마켓플레이스 API
            ('MARKETPLACE', 'naver_client_id', '', '네이버 Client ID', '네이버 커머스 API Client ID', True, 'password'),
            ('MARKETPLACE', 'naver_client_secret', '', '네이버 Client Secret', '네이버 커머스 API Client Secret', True, 'password'),
            ('MARKETPLACE', 'coupang_access_key', '', '쿠팡 Access Key', '쿠팡 WING API Access Key', True, 'password'),
            ('MARKETPLACE', 'coupang_secret_key', '', '쿠팡 Secret Key', '쿠팡 WING API Secret Key', True, 'password'),
            # 택배/배송 API
            ('SHIPPING', 'default_carrier_api_key', '', '기본 택배 API 키', '택배 조회 API 키 (스마트택배 등)', True, 'password'),
            ('SHIPPING', 'tracking_api_url', '', '배송추적 API URL', '배송추적 서비스 API 엔드포인트', False, 'url'),
            # AI/자동화
            ('AI', 'anthropic_api_key', '', 'Anthropic API 키', '문의 자동답변용 Claude API 키', True, 'password'),
            ('AI', 'auto_reply_enabled', 'false', '자동답변 활성화', '문의 접수 시 AI 자동답변 사용 여부', False, 'boolean'),
            # 이메일
            ('EMAIL', 'smtp_host', '', 'SMTP 호스트', '발송 메일 서버 주소', False, 'text'),
            ('EMAIL', 'smtp_port', '587', 'SMTP 포트', '', False, 'number'),
            ('EMAIL', 'smtp_user', '', 'SMTP 계정', '발송 메일 계정', False, 'text'),
            ('EMAIL', 'smtp_password', '', 'SMTP 비밀번호', '', True, 'password'),
            ('EMAIL', 'from_email', '', '발신 이메일', '기본 발신자 이메일 주소', False, 'text'),
            # 인사
            ('HR', 'default_password_rule', '사번+!', '기본 비밀번호 규칙', '신규 계정 생성 시 기본 비밀번호 규칙', False, 'text'),
            ('HR', 'default_role', 'staff', '기본 역할', '신규 사용자 기본 역할', False, 'text'),
            ('HR', 'employee_prefix', 'EMP', '사번 접두사', '사번 자동생성 접두사', False, 'text'),
            # 보안
            ('SECURITY', 'session_timeout', '30', '세션 타임아웃(분)', '비활동 시 자동 로그아웃 시간(분)', False, 'number'),
            ('SECURITY', 'min_password_length', '8', '최소 비밀번호 길이', '', False, 'number'),
            ('SECURITY', 'max_login_attempts', '5', '최대 로그인 시도', '계정 잠금까지 허용 횟수', False, 'number'),
            # 백업/복구
            ('BACKUP', 'auto_backup_enabled', 'true', '자동 백업', '자동 백업 활성화 여부', False, 'boolean'),
            ('BACKUP', 'backup_retention_days', '30', '백업 보관일수', '자동 백업 파일 보관 기간(일)', False, 'number'),
        ]
        created_count = 0
        for cat, key, value, display, desc, secret, vtype in defaults:
            _, created = cls.all_objects.get_or_create(
                category=cat,
                key=key,
                defaults={
                    'value': value,
                    'display_name': display,
                    'description': desc,
                    'is_secret': secret,
                    'value_type': vtype,
                },
            )
            if created:
                created_count += 1
        return created_count
