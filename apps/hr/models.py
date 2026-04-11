from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
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
        config = PayrollConfig.objects.filter(year=self.year, is_active=True).first()
        if not config:
            raise ValidationError(f'{self.year}년 급여설정이 없거나 비활성 상태입니다. 관리자에게 문의하세요.')

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


class SeverancePay(BaseModel):
    """퇴직금 산정 — 근로기준법 제34조"""

    class Status(models.TextChoices):
        CALCULATED = 'CALCULATED', '계산완료'
        PAID = 'PAID', '지급완료'

    employee = models.ForeignKey(
        EmployeeProfile,
        verbose_name='직원',
        on_delete=models.PROTECT,
        related_name='severance_pays',
    )
    calculation_date = models.DateField('산정일')
    hire_date = models.DateField('입사일')
    years_of_service = models.DecimalField('근속연수', max_digits=5, decimal_places=2, default=0)
    total_days = models.PositiveIntegerField('총근무일수', default=0)
    recent_3month_salary = models.DecimalField(
        '최근3개월급여합', max_digits=15, decimal_places=0, default=0,
    )
    recent_3month_days = models.PositiveIntegerField('최근3개월일수', default=90)
    average_daily_wage = models.DecimalField(
        '1일평균임금', max_digits=15, decimal_places=0, default=0,
    )
    total_amount = models.DecimalField('퇴직금', max_digits=15, decimal_places=0, default=0)
    status = models.CharField(
        '상태', max_length=20, choices=Status.choices, default=Status.CALCULATED,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '퇴직금'
        verbose_name_plural = '퇴직금'
        ordering = ['-calculation_date']

    def __str__(self):
        return f'{self.employee} 퇴직금 ({self.calculation_date})'

    def calculate(self):
        """근로기준법 제34조: 퇴직금 = 1일평균임금 × 30 × (총근무일수/365)
        단, 계속근로기간 1년 미만 또는 4주 평균 15시간 미만은 퇴직금 미발생.
        """
        three_months_ago = self.calculation_date - timedelta(days=90)
        payrolls = Payroll.objects.filter(
            employee=self.employee,
            paid_date__gte=three_months_ago,
            paid_date__lte=self.calculation_date,
            is_active=True,
        )
        self.recent_3month_salary = payrolls.aggregate(
            total=Sum('gross_pay'),
        )['total'] or Decimal('0')
        self.average_daily_wage = (
            self.recent_3month_salary // self.recent_3month_days
            if self.recent_3month_days else Decimal('0')
        )
        self.total_days = (self.calculation_date - self.hire_date).days
        self.years_of_service = Decimal(str(round(self.total_days / 365, 2)))
        # 1년 미만 근속 시 퇴직금 미발생 (근로기준법 제34조 요건)
        if self.total_days < 365:
            self.total_amount = Decimal('0')
        else:
            self.total_amount = self.average_daily_wage * 30 * self.total_days // 365


class LaborConfig(BaseModel):
    """근로기준 설정 — 연도별 법정 기준"""
    year = models.PositiveIntegerField('적용연도')
    country_code = models.CharField('국가코드', max_length=10, default='KR')
    min_hourly_wage = models.DecimalField('최저시급', max_digits=10, decimal_places=0, default=0)
    max_weekly_hours = models.PositiveIntegerField('주간최대근로시간', default=52)
    overtime_rate = models.DecimalField(
        '연장근로수당배율', max_digits=3, decimal_places=1, default=Decimal('1.5'),
    )
    night_rate = models.DecimalField(
        '야간근로수당배율', max_digits=3, decimal_places=1, default=Decimal('1.5'),
    )
    annual_leave_base = models.PositiveIntegerField('기본연차일수', default=15)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '근로기준설정'
        verbose_name_plural = '근로기준설정'
        ordering = ['-year']
        constraints = [
            models.UniqueConstraint(
                fields=['year', 'country_code'],
                name='uq_labor_config_year_country',
            ),
        ]

    def __str__(self):
        return f'{self.year}년 근로기준설정 ({self.country_code})'


class YearEndSettlement(BaseModel):
    """연말정산"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        CALCULATED = 'CALCULATED', '계산완료'
        CONFIRMED = 'CONFIRMED', '확정'

    employee = models.ForeignKey(
        EmployeeProfile,
        verbose_name='직원',
        on_delete=models.PROTECT,
        related_name='year_end_settlements',
    )
    year = models.PositiveIntegerField('정산연도')
    total_income = models.DecimalField('총급여', max_digits=15, decimal_places=0, default=0)
    tax_paid = models.DecimalField('기납부세액', max_digits=15, decimal_places=0, default=0)
    insurance_deduction = models.DecimalField(
        '보험료공제', max_digits=15, decimal_places=0, default=0,
    )
    medical_deduction = models.DecimalField(
        '의료비공제', max_digits=15, decimal_places=0, default=0,
    )
    education_deduction = models.DecimalField(
        '교육비공제', max_digits=15, decimal_places=0, default=0,
    )
    housing_deduction = models.DecimalField(
        '주택자금공제', max_digits=15, decimal_places=0, default=0,
    )
    donation_deduction = models.DecimalField(
        '기부금공제', max_digits=15, decimal_places=0, default=0,
    )
    credit_card_deduction = models.DecimalField(
        '신용카드공제', max_digits=15, decimal_places=0, default=0,
    )
    total_deduction = models.DecimalField(
        '소득공제합계', max_digits=15, decimal_places=0, default=0,
    )
    taxable_income = models.DecimalField('과세표준', max_digits=15, decimal_places=0, default=0)
    calculated_tax = models.DecimalField('산출세액', max_digits=15, decimal_places=0, default=0)
    final_tax = models.DecimalField('결정세액', max_digits=15, decimal_places=0, default=0)
    refund_amount = models.DecimalField(
        '환급(추가납부)액', max_digits=15, decimal_places=0, default=0,
    )
    status = models.CharField(
        '상태', max_length=20, choices=Status.choices, default=Status.DRAFT,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '연말정산'
        verbose_name_plural = '연말정산'
        ordering = ['-year']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'year'],
                name='uq_year_end_settlement',
            ),
        ]

    def __str__(self):
        return f'{self.employee} {self.year}년 연말정산'

    def calculate(self):
        """해당 연도 급여 합산 후 누진세율 적용"""
        payrolls = Payroll.objects.filter(
            employee=self.employee,
            year=self.year,
            is_active=True,
        )
        agg = payrolls.aggregate(
            total_gross=Sum('gross_pay'),
            total_tax=Sum('income_tax'),
            total_local_tax=Sum('local_income_tax'),
        )
        self.total_income = agg['total_gross'] or Decimal('0')
        self.tax_paid = (agg['total_tax'] or Decimal('0')) + (agg['total_local_tax'] or Decimal('0'))

        self.total_deduction = (
            self.insurance_deduction
            + self.medical_deduction
            + self.education_deduction
            + self.housing_deduction
            + self.donation_deduction
            + self.credit_card_deduction
        )
        self.taxable_income = max(self.total_income - self.total_deduction, Decimal('0'))
        self.calculated_tax = Decimal(str(Payroll._calculate_income_tax(self.taxable_income)))
        self.final_tax = self.calculated_tax
        self.refund_amount = self.tax_paid - self.final_tax
        self.status = self.Status.CALCULATED
