from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.fields import EncryptedCharField, EncryptedTextField
from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class ExternalCompany(BaseModel):
    """외부 협력업체"""
    name = models.CharField('업체명', max_length=100)
    business_number = models.CharField('사업자번호', max_length=20, unique=True)
    representative = models.CharField('대표자', max_length=50)
    contact_person = models.CharField('담당자', max_length=50, blank=True)
    phone = models.CharField('연락처', max_length=20, blank=True)
    email = models.EmailField('이메일', blank=True)
    address = models.TextField('주소', blank=True)
    contract_start = models.DateField('계약시작일', null=True, blank=True)
    contract_end = models.DateField('계약종료일', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '외부 협력업체'
        verbose_name_plural = '외부 협력업체'
        ordering = ['name']

    def __str__(self):
        return self.name


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
    code = models.CharField('직급코드', max_length=20, unique=True)
    name = models.CharField('직급명', max_length=50)
    level = models.PositiveIntegerField(
        '레벨',
        help_text='1=최상위, 숫자가 클수록 낮은 직급',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '직급'
        verbose_name_plural = '직급'
        ordering = ['level']

    def __str__(self):
        return f'{self.name} ({self.code})'


class EmployeeProfile(BaseModel):
    """직원 프로필"""
    BUSINESS_KEY_FIELD = 'employee_number'

    class EmployeeType(models.TextChoices):
        INTERNAL = 'INTERNAL', '정규직'
        CONTRACT = 'CONTRACT', '계약직'
        EXTERNAL = 'EXTERNAL', '외부협력'
        DISPATCH = 'DISPATCH', '파견'

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
        on_delete=models.PROTECT,
        related_name='profile',
    )
    employee_number = models.CharField('사번', max_length=20, unique=True, blank=True)
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
    address = EncryptedTextField('주소', blank=True)
    emergency_contact = EncryptedCharField(
        '비상연락처', max_length=500, blank=True,
    )
    bank_name = models.CharField('은행명', max_length=50, blank=True)
    bank_account = EncryptedCharField(
        '계좌번호', max_length=500, blank=True,
    )
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
    base_salary = models.DecimalField(
        '기본급', max_digits=15, decimal_places=0, default=0,
        help_text='월 기본급 (원)',
    )
    employee_type = models.CharField(
        '고용유형',
        max_length=20,
        choices=EmployeeType.choices,
        default=EmployeeType.INTERNAL,
    )
    external_company = models.ForeignKey(
        ExternalCompany,
        verbose_name='소속 외부업체',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='employees',
    )
    contract_start = models.DateField('계약시작일', null=True, blank=True)
    contract_end = models.DateField('계약종료일', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '직원 프로필'
        verbose_name_plural = '직원 프로필'
        ordering = ['employee_number']
        indexes = [
            models.Index(fields=['department'], name='idx_employee_dept'),
            models.Index(fields=['status'], name='idx_employee_status'),
        ]

    def __str__(self):
        return f'{self.user.name or self.user.username} ({self.employee_number})'

    def save(self, *args, **kwargs):
        if not self.employee_number:
            self.employee_number = generate_document_number(EmployeeProfile, 'employee_number', 'EMP')
        super().save(*args, **kwargs)

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
        MANAGER_APPOINT = 'MANAGER_APPOINT', '부서장 임명'
        RESIGNATION = 'RESIGNATION', '퇴사'
        LEAVE = 'LEAVE', '휴직'
        RETURN = 'RETURN', '복직'
        DISPATCH_IN = 'DISPATCH_IN', '파견입사'
        DISPATCH_EXTEND = 'DISPATCH_EXTEND', '파견연장'
        DISPATCH_END = 'DISPATCH_END', '파견종료'
        EXTERNAL_IN = 'EXTERNAL_IN', '외부인력 투입'
        EXTERNAL_OUT = 'EXTERNAL_OUT', '외부인력 철수'

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


class PayrollConfig(BaseModel):
    """급여 설정"""
    year = models.PositiveIntegerField('년도')
    minimum_wage_hourly = models.DecimalField(
        '최저시급', max_digits=10, decimal_places=0, default=0,
    )
    national_pension_rate = models.DecimalField(
        '국민연금율(%)', max_digits=5, decimal_places=2, default=Decimal('4.50'),
    )
    health_insurance_rate = models.DecimalField(
        '건강보험율(%)', max_digits=5, decimal_places=2, default=Decimal('3.545'),
    )
    long_term_care_rate = models.DecimalField(
        '장기요양보험율(%)', max_digits=5, decimal_places=2, default=Decimal('12.81'),
        help_text='건강보험의 %',
    )
    employment_insurance_rate = models.DecimalField(
        '고용보험율(%)', max_digits=5, decimal_places=2, default=Decimal('0.90'),
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '급여설정'
        verbose_name_plural = '급여설정'
        ordering = ['-year']
        constraints = [
            models.UniqueConstraint(fields=['year'], name='uq_payroll_config_year'),
        ]

    def __str__(self):
        return f'{self.year}년 급여설정'


class Payroll(BaseModel):
    """급여 대장"""
    employee = models.ForeignKey(
        EmployeeProfile,
        verbose_name='직원',
        on_delete=models.PROTECT,
        related_name='payrolls',
    )
    year = models.PositiveIntegerField('년도')
    month = models.PositiveIntegerField('월')

    # 지급 항목
    base_salary = models.DecimalField('기본급', max_digits=15, decimal_places=0, default=0)
    overtime_pay = models.DecimalField('초과근무수당', max_digits=15, decimal_places=0, default=0)
    bonus = models.DecimalField('상여금', max_digits=15, decimal_places=0, default=0)
    allowances = models.DecimalField('제수당', max_digits=15, decimal_places=0, default=0)
    gross_pay = models.DecimalField('총지급액', max_digits=15, decimal_places=0, default=0)

    # 공제 항목
    national_pension = models.DecimalField('국민연금', max_digits=15, decimal_places=0, default=0)
    health_insurance = models.DecimalField('건강보험', max_digits=15, decimal_places=0, default=0)
    long_term_care = models.DecimalField('장기요양', max_digits=15, decimal_places=0, default=0)
    employment_insurance = models.DecimalField('고용보험', max_digits=15, decimal_places=0, default=0)
    income_tax = models.DecimalField('소득세', max_digits=15, decimal_places=0, default=0)
    local_income_tax = models.DecimalField('지방소득세', max_digits=15, decimal_places=0, default=0)
    total_deductions = models.DecimalField('공제합계', max_digits=15, decimal_places=0, default=0)

    # 실수령액
    net_pay = models.DecimalField('실수령액', max_digits=15, decimal_places=0, default=0)

    # 상태
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성'
        CONFIRMED = 'CONFIRMED', '확정'
        PAID = 'PAID', '지급완료'

    status = models.CharField(
        '상태', max_length=10, choices=Status.choices, default=Status.DRAFT,
    )
    paid_date = models.DateField('지급일', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '급여'
        verbose_name_plural = '급여'
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'year', 'month'],
                name='uq_payroll_employee_period',
            ),
        ]

    def __str__(self):
        return f'{self.employee} - {self.year}년 {self.month}월 급여'

    @staticmethod
    def _calculate_income_tax(annual_taxable: Decimal) -> int:
        """연간 과세표준에 누진세율 적용 → 연간 소득세(원) 반환"""
        brackets = [
            (Decimal('14000000'),  Decimal('0.06'), Decimal('0')),
            (Decimal('50000000'),  Decimal('0.15'), Decimal('1260000')),
            (Decimal('88000000'),  Decimal('0.24'), Decimal('5760000')),
            (Decimal('150000000'), Decimal('0.35'), Decimal('15440000')),
            (Decimal('300000000'), Decimal('0.38'), Decimal('19940000')),
            (Decimal('500000000'), Decimal('0.40'), Decimal('25940000')),
            (Decimal('1000000000'), Decimal('0.42'), Decimal('35940000')),
        ]
        t = annual_taxable
        for limit, rate, deduction in brackets:
            if t <= limit:
                return max(int(t * rate - deduction), 0)
        # 10억 초과
        return max(int(t * Decimal('0.45') - Decimal('65940000')), 0)

    def calculate_deductions(self):
        """4대 보험 + 세금 자동 계산"""
        try:
            config = PayrollConfig.objects.get(year=self.year, is_active=True)
        except PayrollConfig.DoesNotExist:
            raise ValidationError(
                f'{self.year}년 급여 설정(PayrollConfig)이 존재하지 않습니다. '
                f'급여 계산 전에 해당 연도의 급여 설정을 먼저 등록하세요.'
            )

        self.national_pension = int(self.gross_pay * config.national_pension_rate / 100)
        self.health_insurance = int(self.gross_pay * config.health_insurance_rate / 100)
        self.long_term_care = int(self.health_insurance * config.long_term_care_rate / 100)
        self.employment_insurance = int(self.gross_pay * config.employment_insurance_rate / 100)
        # 누진세율 적용 (과세표준 기반)
        taxable = (
            self.gross_pay
            - self.national_pension
            - self.health_insurance
            - self.long_term_care
            - self.employment_insurance
        )
        self.income_tax = max(self._calculate_income_tax(taxable * 12) // 12, 0)
        self.local_income_tax = int(self.income_tax * Decimal('0.10'))  # 소득세의 10%

        self.total_deductions = (
            self.national_pension + self.health_insurance + self.long_term_care
            + self.employment_insurance + self.income_tax + self.local_income_tax
        )
        self.net_pay = self.gross_pay - self.total_deductions

    def save(self, *args, **kwargs):
        self.gross_pay = self.base_salary + self.overtime_pay + self.bonus + self.allowances
        self.calculate_deductions()
        super().save(*args, **kwargs)
