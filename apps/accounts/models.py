from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from simple_history.models import HistoricalRecords

from apps.accounts.permissions import ACTION_CHOICES, MODULE_CHOICES
from apps.core.models import BaseModel


class User(AbstractUser):
    history = HistoricalRecords()
    class Role(models.TextChoices):
        ADMIN = 'admin', '관리자'
        MANAGER = 'manager', '매니저'
        STAFF = 'staff', '직원'

    name = models.CharField('이름', max_length=50, blank=True)
    phone = models.CharField('연락처', max_length=20, blank=True)
    role = models.CharField(
        '역할',
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
    )
    is_auditor = models.BooleanField(
        '감사권한',
        default=False,
        help_text='감사 증적 열람 권한 (ISMS/회계 증빙 접근)',
    )

    class Meta:
        verbose_name = '사용자'
        verbose_name_plural = '사용자'
        indexes = [
            models.Index(fields=['role'], name='idx_user_role'),
        ]

    def __str__(self):
        if self.name:
            return f'{self.name} ({self.username})'
        return self.username

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_manager_role(self):
        return self.role in (self.Role.ADMIN, self.Role.MANAGER)

    def get_module_permissions(self):
        from apps.accounts.permission_utils import get_user_permissions
        return get_user_permissions(self)

    def has_module_permission(self, module, action):
        if self.role == 'admin':
            return True
        perms = self.get_module_permissions()
        return f'{module}.{action}' in perms


class ModulePermission(BaseModel):
    module = models.CharField(
        '모듈', max_length=30, choices=MODULE_CHOICES,
    )
    action = models.CharField(
        '액션', max_length=10, choices=ACTION_CHOICES,
    )
    codename = models.CharField(
        '코드명', max_length=50, unique=True,
    )
    description = models.CharField(
        '설명', max_length=200, blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '모듈 권한'
        verbose_name_plural = '모듈 권한'
        ordering = ['module', 'action']

    def __str__(self):
        return self.codename

    def save(self, *args, **kwargs):
        if not self.codename:
            self.codename = f'{self.module}.{self.action}'
        if not self.description:
            module_label = dict(MODULE_CHOICES).get(self.module, self.module)
            action_label = dict(ACTION_CHOICES).get(self.action, self.action)
            self.description = f'{module_label} {action_label}'
        super().save(*args, **kwargs)


class PermissionGroup(BaseModel):
    name = models.CharField('그룹명', max_length=100, unique=True)
    description = models.TextField('설명', blank=True)
    priority = models.PositiveIntegerField('우선순위', default=0)
    permissions = models.ManyToManyField(
        ModulePermission,
        through='PermissionGroupPermission',
        verbose_name='권한 목록',
        blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '권한 그룹'
        verbose_name_plural = '권한 그룹'
        ordering = ['-priority', 'name']

    def __str__(self):
        return self.name


class PermissionGroupPermission(BaseModel):
    group = models.ForeignKey(
        PermissionGroup,
        on_delete=models.CASCADE,
        verbose_name='권한 그룹',
        related_name='group_permissions',
    )
    permission = models.ForeignKey(
        ModulePermission,
        on_delete=models.CASCADE,
        verbose_name='권한',
        related_name='group_assignments',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '그룹-권한 매핑'
        verbose_name_plural = '그룹-권한 매핑'
        unique_together = ['group', 'permission']

    def __str__(self):
        return f'{self.group} - {self.permission}'


class PermissionGroupMembership(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='사용자',
        related_name='permission_memberships',
    )
    group = models.ForeignKey(
        PermissionGroup,
        on_delete=models.CASCADE,
        verbose_name='권한 그룹',
        related_name='memberships',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name='할당자',
        null=True, blank=True,
        related_name='+',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '그룹 멤버십'
        verbose_name_plural = '그룹 멤버십'
        unique_together = ['user', 'group']

    def __str__(self):
        return f'{self.user} → {self.group}'


class UserPermission(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='사용자',
        related_name='user_permissions_custom',
    )
    permission = models.ForeignKey(
        ModulePermission,
        on_delete=models.CASCADE,
        verbose_name='권한',
        related_name='user_assignments',
    )
    grant = models.BooleanField('허용', default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name='할당자',
        null=True, blank=True,
        related_name='+',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '사용자 직접 권한'
        verbose_name_plural = '사용자 직접 권한'
        unique_together = ['user', 'permission']

    def __str__(self):
        prefix = '+' if self.grant else '-'
        return f'{prefix}{self.permission} → {self.user}'
