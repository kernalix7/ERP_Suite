"""RPA 자동화 실행 엔진 (Celery 기반)"""
import logging
import time
from urllib.parse import urlparse

import requests
from django.db import transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)

OPERATOR_MAP = {
    'EQ': lambda a, b: str(a) == str(b),
    'NEQ': lambda a, b: str(a) != str(b),
    'GT': lambda a, b: float(a) > float(b),
    'LT': lambda a, b: float(a) < float(b),
    'GTE': lambda a, b: float(a) >= float(b),
    'LTE': lambda a, b: float(a) <= float(b),
    'CONTAINS': lambda a, b: str(b) in str(a),
    'IN': lambda a, b: str(a) in str(b).split(','),
    'IS_NULL': lambda a, b: a is None if b.lower() == 'true' else a is not None,
}

# RCE 방지: 허용된 모델만 RPA에서 조작 가능
ALLOWED_RPA_MODELS = {}


def _get_allowed_model(model_key):
    """허용된 모델 클래스 반환. 미등록 모델은 ValueError 발생."""
    if not ALLOWED_RPA_MODELS:
        # 지연 초기화 (앱 로딩 순서 문제 방지)
        from apps.core.notification import Notification
        from apps.inventory.models import Product
        from apps.sales.models import Order, Partner
        ALLOWED_RPA_MODELS.update({
            'core.Notification': Notification,
            'inventory.Product': Product,
            'sales.Order': Order,
            'sales.Partner': Partner,
        })
    model_class = ALLOWED_RPA_MODELS.get(model_key)
    if model_class is None:
        raise ValueError(
            f'Model "{model_key}" is not allowed for RPA operations. '
            f'Allowed: {", ".join(sorted(ALLOWED_RPA_MODELS.keys()))}'
        )
    return model_class


# RCE 방지: RUN_FUNCTION에 허용된 함수만 등록
ALLOWED_RPA_FUNCTIONS = {}


def register_rpa_function(name, func):
    """RPA에서 호출 가능한 함수 등록"""
    ALLOWED_RPA_FUNCTIONS[name] = func


def _get_allowed_function(function_key):
    """허용된 함수 반환. 미등록 함수는 ValueError 발생."""
    func = ALLOWED_RPA_FUNCTIONS.get(function_key)
    if func is None:
        raise ValueError(
            f'Function "{function_key}" is not registered for RPA execution. '
            f'Allowed: {", ".join(sorted(ALLOWED_RPA_FUNCTIONS.keys()))}'
        )
    return func


# SSRF 방지: 웹훅 허용 도메인
ALLOWED_WEBHOOK_DOMAINS = frozenset()


def _validate_webhook_url(url):
    """외부 웹훅 URL 검증 (SSRF 방지)"""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f'Webhook URL scheme must be http or https, got: {parsed.scheme}')
    hostname = parsed.hostname or ''
    # 내부 네트워크 차단
    if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1', ''):
        raise ValueError(f'Webhook URL must not target internal addresses: {hostname}')
    if hostname.startswith(('10.', '172.', '192.168.')):
        raise ValueError(f'Webhook URL must not target private networks: {hostname}')
    if hostname.endswith('.local') or hostname.endswith('.internal'):
        raise ValueError(f'Webhook URL must not target local/internal domains: {hostname}')
    # 허용 도메인 체크 (설정된 경우만)
    if ALLOWED_WEBHOOK_DOMAINS and hostname not in ALLOWED_WEBHOOK_DOMAINS:
        raise ValueError(
            f'Webhook domain "{hostname}" is not allowed. '
            f'Allowed: {", ".join(sorted(ALLOWED_WEBHOOK_DOMAINS))}'
        )


def check_conditions(rule, trigger_data=None):
    """규칙 조건을 평가하여 실행 여부 결정"""
    conditions = rule.conditions.filter(is_active=True)
    if not conditions.exists():
        return True

    data = trigger_data or {}
    results = []

    for cond in conditions:
        field_val = data.get(cond.field)
        op_func = OPERATOR_MAP.get(cond.operator)
        if op_func:
            try:
                results.append((cond.logic_op, op_func(field_val, cond.value)))
            except (ValueError, TypeError):
                results.append((cond.logic_op, False))
        else:
            results.append((cond.logic_op, False))

    if not results:
        return True

    # 첫 번째 결과로 시작
    result = results[0][1]
    for logic_op, val in results[1:]:
        if logic_op == 'AND':
            result = result and val
        else:
            result = result or val

    return result


def execute_action(action, trigger_data=None):
    """개별 액션 실행"""
    config = action.action_config or {}

    if action.action_type == 'SEND_NOTIFICATION':
        return _action_send_notification(config, trigger_data)
    elif action.action_type == 'CREATE_RECORD':
        return _action_create_record(config, trigger_data)
    elif action.action_type == 'UPDATE_FIELD':
        return _action_update_field(config, trigger_data)
    elif action.action_type == 'SEND_EMAIL':
        return _action_send_email(config, trigger_data)
    elif action.action_type == 'CALL_WEBHOOK':
        return _action_call_webhook(config, trigger_data)
    elif action.action_type == 'RUN_FUNCTION':
        return _action_run_function(config, trigger_data)
    else:
        raise ValueError(f'Unknown action type: {action.action_type}')


def execute_rule(rule, trigger_data=None):
    """규칙 실행 (조건 확인 -> 액션 순차 실행)"""
    from .models import AutomationLog

    start = time.monotonic()
    log = AutomationLog(
        rule=rule,
        trigger_data=trigger_data or {},
        created_by=rule.owner,
    )

    if not check_conditions(rule, trigger_data):
        log.status = 'SUCCESS'
        log.actions_executed = 0
        log.duration_ms = int((time.monotonic() - start) * 1000)
        log.save()
        return log

    actions = rule.actions.filter(is_active=True).order_by('sequence')
    executed = 0
    errors = []

    for action in actions:
        try:
            execute_action(action, trigger_data)
            executed += 1
        except Exception as e:
            error_msg = f'Action #{action.sequence} ({action.get_action_type_display()}): {e}'
            errors.append(error_msg)
            logger.error('RPA action error: %s', error_msg, exc_info=True)

            if action.on_error == 'STOP':
                break
            elif action.on_error == 'RETRY':
                try:
                    execute_action(action, trigger_data)
                    executed += 1
                    errors.pop()
                except Exception:
                    pass

    duration = int((time.monotonic() - start) * 1000)

    if errors and executed == 0:
        log.status = 'FAILED'
    elif errors:
        log.status = 'PARTIAL'
    else:
        log.status = 'SUCCESS'

    log.actions_executed = executed
    log.error_message = '\n'.join(errors)
    log.duration_ms = duration
    log.save()

    # 규칙 통계 갱신
    with transaction.atomic():
        AutomationRule = rule.__class__
        updates = {'run_count': F('run_count') + 1, 'last_run': timezone.now()}
        if errors:
            updates['error_count'] = F('error_count') + 1
        AutomationRule.objects.filter(pk=rule.pk).update(**updates)

    return log


# ── Action Implementations ───────────────────────────────────

def _action_send_notification(config, trigger_data):
    from apps.core.notification import create_notification
    users = config.get('users', 'admin')
    title = config.get('title', '자동화 알림')
    message = config.get('message', '')
    if trigger_data:
        message = message.format(**{k: v for k, v in trigger_data.items() if isinstance(v, (str, int, float))})
    create_notification(users, title, message, noti_type='SYSTEM')


def _action_create_record(config, trigger_data):
    target_model = config.get('target_model')
    if not target_model:
        raise ValueError('target_model not specified')
    model_class = _get_allowed_model(target_model)
    field_values = config.get('field_values', {})
    model_class.objects.create(**field_values)


def _action_update_field(config, trigger_data):
    target_model = config.get('target_model')
    if not target_model:
        raise ValueError('target_model not specified')
    model_class = _get_allowed_model(target_model)
    filters = config.get('filters', {})
    updates = config.get('field_values', {})
    if filters and updates:
        model_class.objects.filter(**filters).update(**updates)


def _action_send_email(config, trigger_data):
    from django.core.mail import send_mail
    subject = config.get('subject', '자동화 이메일')
    body = config.get('body', '')
    recipients = config.get('recipients', [])
    sender = config.get('sender', 'noreply@erp.local')
    if trigger_data:
        body = body.format(**{k: v for k, v in trigger_data.items() if isinstance(v, (str, int, float))})
    if recipients:
        send_mail(subject, body, sender, recipients)


def _action_call_webhook(config, trigger_data):
    url = config.get('url')
    if not url:
        raise ValueError('url not specified')
    _validate_webhook_url(url)
    method = config.get('method', 'POST').upper()
    if method not in ('GET', 'POST'):
        raise ValueError(f'Webhook method must be GET or POST, got: {method}')
    headers = config.get('headers', {})
    payload = config.get('payload', trigger_data or {})
    timeout = min(config.get('timeout', 10), 30)

    if method == 'GET':
        resp = requests.get(url, headers=headers, timeout=timeout)
    else:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()


def _action_run_function(config, trigger_data):
    function_key = config.get('function_path')
    if not function_key:
        raise ValueError('function_path not specified')
    func = _get_allowed_function(function_key)
    func(trigger_data)
