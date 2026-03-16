from datetime import date

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Department(BaseModel):
    """부서"""
    name = models.CharField('부서명', max_length=100)
    code = models.CharField('부서코드', max_length=20, unique=True)
    parent = models.ForeignKey(
        'self',
        verbose_name='상위부서',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='부서장',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_departments',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '부서'
        verbose_name_plural = '부서'
        ordering = ['code']

    def __str__(self):
        return f'{self.name} ({self.code})'

    def get_ancestors(self):
        """상위 부서 목록 반환 (root까지)"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return list(reversed(ancestors))

    def get_descendants(self):
        """하위 부서 목록 반환 (재귀)"""
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants


class Position(BaseModel):
    """직급"""
    name = models.CharField('직급명', max_length=50)
    level = models.PositiveIntegerField(
        '레벨',
        help_text='1=최하위, 숫자가 클수록 높은 직급',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '직급'
        verbose_name_plural = '직급'
        ordering = ['level']

    def __str__(self):
        return self.name


class EmployeeProfile(BaseModel):
    """직원 프로필"""

    class ContractType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', '정규직'
        PART_TIME = 'PART_TIME', '파트타임'
        CONTRACT = 'CONTRACT', '계약직'
        INTERN = 'INTERN', '인턴'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', '재직'
        ON_LEAVE = 'ON_LEAVE', '휴직'
        RESIGNED = 'RESIGNED', '퇴사'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name='사용자',
        on_delete=models.CASCADE,
        related_name='profile',
    )
    employee_number = models.CharField('사번', max_length=20, unique=True)
    department = models.ForeignKey(
        Department,
        verbose_name='부서',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='employees',
    )
    position = models.ForeignKey(
        Position,
        verbose_name='직급',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='employees',
    )
    hire_date = models.DateField('입사일')
    birth_date = models.DateField('생년월일', null=True, blank=True)
    address = models.TextField('주소', blank=True)
    emergency_contact = models.CharField('비상연락처', max_length=100, blank=True)
    bank_name = models.CharField('은행명', max_length=50, blank=True)
    bank_account = models.CharField('계좌번호', max_length=50, blank=True)
    contract_type = models.CharField(
        '계약유형',
        max_length=20,
        choices=ContractType.choices,
        default=ContractType.FULL_TIME,
    )
    status = models.CharField(
        '상태',
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    resignation_date = models.DateField('퇴사일', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '직원 프로필'
        verbose_name_plural = '직원 프로필'
        ordering = ['employee_number']

    def __str__(self):
        return f'{self.user.name or self.user.username} ({self.employee_number})'

    @property
    def years_of_service(self):
        """근속연수"""
        end = self.resignation_date or date.today()
        delta = end - self.hire_date
        return round(delta.days / 365.25, 1)


class PersonnelAction(BaseModel):
    """인사발령"""

    class ActionType(models.TextChoices):
        HIRE = 'HIRE', '입사'
        PROMOTION = 'PROMOTION', '승진'
        TRANSFER = 'TRANSFER', '전보'
        DEMOTION = 'DEMOTION', '강등'
        RESIGNATION = 'RESIGNATION', '퇴사'
        LEAVE = 'LEAVE', '휴직'
        RETURN = 'RETURN', '복직'

    employee = models.ForeignKey(
        EmployeeProfile,
        verbose_name='직원',
        on_delete=models.PROTECT,
        related_name='personnel_actions',
    )
    action_type = models.CharField(
        '발령유형',
        max_length=20,
        choices=ActionType.choices,
    )
    effective_date = models.DateField('발령일')
    from_department = models.ForeignKey(
        Department,
        verbose_name='이전 부서',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    to_department = models.ForeignKey(
        Department,
        verbose_name='이동 부서',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    from_position = models.ForeignKey(
        Position,
        verbose_name='이전 직급',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    to_position = models.ForeignKey(
        Position,
        verbose_name='변경 직급',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    reason = models.TextField('사유', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '인사발령'
        verbose_name_plural = '인사발령'
        ordering = ['-effective_date', '-created_at']

    def __str__(self):
        return f'{self.employee} - {self.get_action_type_display()} ({self.effective_date})'
