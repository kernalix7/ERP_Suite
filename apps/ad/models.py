from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class ADDomain(BaseModel):
    """Active Directory 도메인 설정"""

    name = models.CharField('도메인명', max_length=100, unique=True)
    domain = models.CharField('도메인 주소', max_length=255, unique=True,
                              help_text='예: corp.example.com')
    ldap_server = models.CharField('LDAP 서버', max_length=255,
                                   help_text='예: ldap://dc01.corp.example.com:389')
    ldap_bind_dn = models.CharField('바인드 DN', max_length=255,
                                    help_text='예: CN=svc_erp,OU=ServiceAccounts,DC=corp,DC=example,DC=com')
    ldap_bind_password = models.CharField('바인드 비밀번호', max_length=255)
    base_dn = models.CharField('Base DN', max_length=255,
                               help_text='예: DC=corp,DC=example,DC=com')
    user_search_base = models.CharField('사용자 검색 Base', max_length=255, blank=True,
                                        help_text='예: OU=Users,DC=corp,DC=example,DC=com')
    group_search_base = models.CharField('그룹 검색 Base', max_length=255, blank=True,
                                         help_text='예: OU=Groups,DC=corp,DC=example,DC=com')
    use_ssl = models.BooleanField('SSL 사용', default=False)
    use_start_tls = models.BooleanField('StartTLS 사용', default=True)
    sync_enabled = models.BooleanField('자동 동기화', default=True)
    sync_interval_minutes = models.PositiveIntegerField('동기화 주기(분)', default=60)
    last_sync_at = models.DateTimeField('마지막 동기화', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'AD 도메인'
        verbose_name_plural = 'AD 도메인'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.domain})'


class ADOrganizationalUnit(BaseModel):
    """Active Directory OU (조직 단위)"""

    domain = models.ForeignKey(ADDomain, verbose_name='도메인',
                               on_delete=models.CASCADE, related_name='ous')
    distinguished_name = models.CharField('DN', max_length=500, unique=True)
    name = models.CharField('OU명', max_length=200)
    parent = models.ForeignKey('self', verbose_name='상위 OU',
                               null=True, blank=True,
                               on_delete=models.CASCADE, related_name='children')
    description = models.TextField('설명', blank=True)
    mapped_department = models.ForeignKey(
        'hr.Department', verbose_name='매핑된 부서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='ad_ous',
        help_text='이 OU에 매핑할 ERP 부서',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'AD 조직단위(OU)'
        verbose_name_plural = 'AD 조직단위(OU)'
        ordering = ['distinguished_name']

    def __str__(self):
        return self.name


class ADGroup(BaseModel):
    """Active Directory 그룹"""

    class GroupType(models.TextChoices):
        SECURITY = 'SECURITY', '보안 그룹'
        DISTRIBUTION = 'DISTRIBUTION', '배포 그룹'

    class GroupScope(models.TextChoices):
        DOMAIN_LOCAL = 'DOMAIN_LOCAL', '도메인 로컬'
        GLOBAL = 'GLOBAL', '글로벌'
        UNIVERSAL = 'UNIVERSAL', '유니버설'

    domain = models.ForeignKey(ADDomain, verbose_name='도메인',
                               on_delete=models.CASCADE, related_name='groups')
    distinguished_name = models.CharField('DN', max_length=500, unique=True)
    sam_account_name = models.CharField('sAMAccountName', max_length=256)
    display_name = models.CharField('표시명', max_length=256, blank=True)
    description = models.TextField('설명', blank=True)
    group_type = models.CharField('그룹 유형', max_length=20,
                                  choices=GroupType.choices,
                                  default=GroupType.SECURITY)
    group_scope = models.CharField('그룹 범위', max_length=20,
                                   choices=GroupScope.choices,
                                   default=GroupScope.GLOBAL)
    mapped_role = models.CharField(
        '매핑된 ERP 역할', max_length=20,
        choices=[('admin', '관리자'), ('manager', '매니저'), ('staff', '직원')],
        blank=True,
        help_text='이 AD 그룹의 구성원에게 자동 부여할 ERP 역할',
    )
    ou = models.ForeignKey(ADOrganizationalUnit, verbose_name='소속 OU',
                           null=True, blank=True,
                           on_delete=models.SET_NULL, related_name='groups')
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'AD 그룹'
        verbose_name_plural = 'AD 그룹'
        ordering = ['sam_account_name']
        indexes = [
            models.Index(fields=['sam_account_name'], name='idx_adgroup_sam'),
        ]

    def __str__(self):
        return f'{self.sam_account_name} ({self.get_group_type_display()})'


class ADUserMapping(BaseModel):
    """ERP 사용자 ↔ AD 계정 매핑"""

    class SyncStatus(models.TextChoices):
        SYNCED = 'SYNCED', '동기화됨'
        PENDING = 'PENDING', '대기중'
        ERROR = 'ERROR', '오류'
        DISABLED = 'DISABLED', '비활성'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='ERP 사용자',
        on_delete=models.CASCADE, related_name='ad_mapping',
    )
    domain = models.ForeignKey(ADDomain, verbose_name='도메인',
                               on_delete=models.CASCADE, related_name='user_mappings')
    distinguished_name = models.CharField('DN', max_length=500, unique=True)
    sam_account_name = models.CharField('sAMAccountName', max_length=256)
    user_principal_name = models.CharField('UPN', max_length=256, blank=True,
                                           help_text='예: user@corp.example.com')
    object_guid = models.CharField('objectGUID', max_length=36, unique=True,
                                   help_text='AD 고유 식별자')
    ad_groups = models.ManyToManyField(ADGroup, verbose_name='AD 그룹',
                                       blank=True, related_name='user_mappings')
    ou = models.ForeignKey(ADOrganizationalUnit, verbose_name='소속 OU',
                           null=True, blank=True,
                           on_delete=models.SET_NULL, related_name='user_mappings')
    sync_status = models.CharField('동기화 상태', max_length=20,
                                   choices=SyncStatus.choices,
                                   default=SyncStatus.PENDING)
    last_sync_at = models.DateTimeField('마지막 동기화', null=True, blank=True)
    ad_enabled = models.BooleanField('AD 계정 활성', default=True)
    ad_locked = models.BooleanField('AD 계정 잠금', default=False)
    ad_password_last_set = models.DateTimeField('비밀번호 마지막 변경', null=True, blank=True)
    ad_last_logon = models.DateTimeField('AD 마지막 로그온', null=True, blank=True)
    sync_error_message = models.TextField('동기화 오류 메시지', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'AD 사용자 매핑'
        verbose_name_plural = 'AD 사용자 매핑'
        ordering = ['sam_account_name']
        indexes = [
            models.Index(fields=['sam_account_name'], name='idx_admapping_sam'),
            models.Index(fields=['object_guid'], name='idx_admapping_guid'),
            models.Index(fields=['sync_status'], name='idx_admapping_sync'),
        ]

    def __str__(self):
        return f'{self.sam_account_name} → {self.user}'


class ADSyncLog(BaseModel):
    """AD 동기화 로그"""

    class SyncType(models.TextChoices):
        FULL = 'FULL', '전체 동기화'
        INCREMENTAL = 'INCREMENTAL', '증분 동기화'
        MANUAL = 'MANUAL', '수동 동기화'

    class Status(models.TextChoices):
        RUNNING = 'RUNNING', '진행중'
        SUCCESS = 'SUCCESS', '성공'
        PARTIAL = 'PARTIAL', '부분성공'
        FAILED = 'FAILED', '실패'

    domain = models.ForeignKey(ADDomain, verbose_name='도메인',
                               on_delete=models.CASCADE, related_name='sync_logs')
    sync_type = models.CharField('동기화 유형', max_length=20,
                                 choices=SyncType.choices)
    status = models.CharField('상태', max_length=20,
                              choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField('시작시각', auto_now_add=True)
    finished_at = models.DateTimeField('완료시각', null=True, blank=True)
    users_created = models.PositiveIntegerField('생성된 사용자', default=0)
    users_updated = models.PositiveIntegerField('수정된 사용자', default=0)
    users_disabled = models.PositiveIntegerField('비활성화 사용자', default=0)
    groups_synced = models.PositiveIntegerField('동기화된 그룹', default=0)
    ous_synced = models.PositiveIntegerField('동기화된 OU', default=0)
    errors_count = models.PositiveIntegerField('오류 수', default=0)
    error_details = models.TextField('오류 상세', blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='실행자',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'AD 동기화 로그'
        verbose_name_plural = 'AD 동기화 로그'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['status'], name='idx_adsynclog_status'),
            models.Index(fields=['-started_at'], name='idx_adsynclog_started'),
        ]

    def __str__(self):
        return f'{self.domain.name} - {self.get_sync_type_display()} ({self.get_status_display()})'

    @property
    def total_processed(self):
        return self.users_created + self.users_updated + self.users_disabled


class ADGroupPolicy(BaseModel):
    """AD 그룹 정책 → ERP 권한 매핑 규칙"""

    class Action(models.TextChoices):
        ASSIGN_ROLE = 'ASSIGN_ROLE', '역할 부여'
        ASSIGN_DEPARTMENT = 'ASSIGN_DEPARTMENT', '부서 배정'
        GRANT_MODULE_ACCESS = 'GRANT_MODULE_ACCESS', '모듈 접근 허용'

    name = models.CharField('정책명', max_length=100)
    domain = models.ForeignKey(ADDomain, verbose_name='도메인',
                               on_delete=models.CASCADE, related_name='policies')
    ad_group = models.ForeignKey(ADGroup, verbose_name='AD 그룹',
                                 on_delete=models.CASCADE, related_name='policies')
    action = models.CharField('적용 동작', max_length=30,
                              choices=Action.choices)
    action_value = models.CharField(
        '동작 값', max_length=100,
        help_text='역할명(admin/manager/staff), 부서ID, 모듈명 등',
    )
    priority = models.PositiveIntegerField('우선순위', default=100,
                                           help_text='낮을수록 높은 우선순위')
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'AD 그룹 정책'
        verbose_name_plural = 'AD 그룹 정책'
        ordering = ['priority', 'name']

    def __str__(self):
        return f'{self.name} ({self.ad_group.sam_account_name})'
