from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.localizations import get_default_timezone


class AutomationRule(BaseModel):
    """자동화 규칙"""

    class TriggerType(models.TextChoices):
        SCHEDULE = 'SCHEDULE', '스케줄'
        EVENT = 'EVENT', '이벤트'
        CONDITION = 'CONDITION', '조건'

    name = models.CharField('규칙명', max_length=200)
    description = models.TextField('설명', blank=True)
    trigger_type = models.CharField(
        '트리거유형', max_length=20, choices=TriggerType.choices, default=TriggerType.EVENT,
    )
    trigger_config = models.JSONField(
        '트리거설정', default=dict, blank=True,
        help_text='event_model, event_action (create/update/delete), field_conditions',
    )
    priority = models.IntegerField('우선순위', default=0)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='automation_rules', verbose_name='소유자',
    )
    run_count = models.IntegerField('실행횟수', default=0)
    last_run = models.DateTimeField('최근실행일', null=True, blank=True)
    error_count = models.IntegerField('오류횟수', default=0)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '자동화규칙'
        verbose_name_plural = verbose_name
        ordering = ['-priority', '-updated_at']

    def __str__(self):
        return self.name


class RuleAction(BaseModel):
    """규칙 실행 액션"""

    class ActionType(models.TextChoices):
        SEND_NOTIFICATION = 'SEND_NOTIFICATION', '알림발송'
        CREATE_RECORD = 'CREATE_RECORD', '레코드생성'
        UPDATE_FIELD = 'UPDATE_FIELD', '필드수정'
        SEND_EMAIL = 'SEND_EMAIL', '이메일발송'
        CALL_WEBHOOK = 'CALL_WEBHOOK', '웹훅호출'
        RUN_FUNCTION = 'RUN_FUNCTION', '함수실행'

    class OnError(models.TextChoices):
        SKIP = 'SKIP', '건너뛰기'
        STOP = 'STOP', '중단'
        RETRY = 'RETRY', '재시도'

    rule = models.ForeignKey(
        AutomationRule, on_delete=models.CASCADE,
        related_name='actions', verbose_name='규칙',
    )
    sequence = models.IntegerField('순서', default=0)
    action_type = models.CharField(
        '액션유형', max_length=20, choices=ActionType.choices,
    )
    action_config = models.JSONField(
        '액션설정', default=dict, blank=True,
        help_text='target_model, field_values, template, url, function_path',
    )
    on_error = models.CharField(
        '오류처리', max_length=10, choices=OnError.choices, default=OnError.SKIP,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '규칙액션'
        verbose_name_plural = verbose_name
        ordering = ['sequence']

    def __str__(self):
        return f'{self.rule.name} - {self.get_action_type_display()} #{self.sequence}'


class RuleCondition(BaseModel):
    """규칙 조건"""

    class Operator(models.TextChoices):
        EQ = 'EQ', '같음'
        NEQ = 'NEQ', '같지않음'
        GT = 'GT', '초과'
        LT = 'LT', '미만'
        GTE = 'GTE', '이상'
        LTE = 'LTE', '이하'
        CONTAINS = 'CONTAINS', '포함'
        IN = 'IN', '목록포함'
        IS_NULL = 'IS_NULL', 'NULL여부'

    class LogicOp(models.TextChoices):
        AND = 'AND', 'AND'
        OR = 'OR', 'OR'

    rule = models.ForeignKey(
        AutomationRule, on_delete=models.CASCADE,
        related_name='conditions', verbose_name='규칙',
    )
    field = models.CharField('필드명', max_length=200)
    operator = models.CharField(
        '연산자', max_length=10, choices=Operator.choices, default=Operator.EQ,
    )
    value = models.CharField('비교값', max_length=500, blank=True)
    logic_op = models.CharField(
        '논리연산', max_length=5, choices=LogicOp.choices, default=LogicOp.AND,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '규칙조건'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.field} {self.operator} {self.value}'


class AutomationLog(BaseModel):
    """자동화 실행 로그"""

    class Status(models.TextChoices):
        SUCCESS = 'SUCCESS', '성공'
        PARTIAL = 'PARTIAL', '부분성공'
        FAILED = 'FAILED', '실패'

    rule = models.ForeignKey(
        AutomationRule, on_delete=models.CASCADE,
        related_name='logs', verbose_name='규칙',
    )
    triggered_at = models.DateTimeField('트리거시각', auto_now_add=True)
    trigger_data = models.JSONField('트리거데이터', default=dict, blank=True)
    status = models.CharField(
        '상태', max_length=10, choices=Status.choices, default=Status.SUCCESS,
    )
    actions_executed = models.IntegerField('실행액션수', default=0)
    error_message = models.TextField('오류메시지', blank=True)
    duration_ms = models.IntegerField('소요시간(ms)', default=0)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '자동화로그'
        verbose_name_plural = verbose_name
        ordering = ['-triggered_at']

    def __str__(self):
        return f'{self.rule.name} - {self.get_status_display()} ({self.triggered_at})'


class AutomationSchedule(BaseModel):
    """자동화 스케줄"""

    rule = models.OneToOneField(
        AutomationRule, on_delete=models.CASCADE,
        related_name='schedule', verbose_name='규칙',
    )
    cron_expression = models.CharField('Cron 표현식', max_length=100)
    timezone = models.CharField('시간대', max_length=50, default=get_default_timezone)
    next_run = models.DateTimeField('다음실행', null=True, blank=True)
    is_paused = models.BooleanField('일시중지', default=False)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '자동화스케줄'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.rule.name} - {self.cron_expression}'
