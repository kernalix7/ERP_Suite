from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
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

    class Meta:
        verbose_name = '사용자'
        verbose_name_plural = '사용자'

    def __str__(self):
        return self.name or self.username

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_manager_role(self):
        return self.role in (self.Role.ADMIN, self.Role.MANAGER)
