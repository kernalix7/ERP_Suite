"""PII (개인식별정보) 마스킹 템플릿 필터.

Usage:
    {% load pii_filters %}
    {{ ssn_value|mask_ssn }}           → "123456-*******"
    {{ account_value|mask_account }}   → "***-***-**6789"
    {{ phone_value|mask_phone }}       → "010-****-5678"
    {{ email_value|mask_email }}       → "us***@example.com"
    {{ name_value|mask_name }}         → "홍*동"
"""
import re

from django import template

register = template.Library()


@register.filter
def mask_ssn(value):
    """주민등록번호 마스킹: "123456-1234567" -> "123456-*******" """
    if not value:
        return value
    value = str(value).strip()
    match = re.match(r'^(\d{6})-?(\d{7})$', value)
    if match:
        return f'{match.group(1)}-*******'
    return value


@register.filter
def mask_account(value):
    """계좌번호 마스킹: "110-123-456789" -> "***-***-**6789"

    마지막 4자리만 노출, 나머지는 * 처리. 구분자(-) 유지.
    """
    if not value:
        return value
    value = str(value).strip()
    # 숫자와 하이픈만 추출
    digits = re.sub(r'[^\d]', '', value)
    if len(digits) < 4:
        return value

    # 원본 구조 유지하면서 마스킹
    parts = value.split('-')
    if len(parts) >= 2:
        # 하이픈 구분 계좌: 마지막 4자리만 노출
        visible_tail = digits[-4:]
        masked_digits = '*' * (len(digits) - 4) + visible_tail

        result_parts = []
        idx = 0
        for part in parts:
            part_len = len(re.sub(r'[^\d]', '', part))
            result_parts.append(masked_digits[idx:idx + part_len])
            idx += part_len
        return '-'.join(result_parts)
    else:
        # 하이픈 없는 계좌
        return '*' * (len(digits) - 4) + digits[-4:]


@register.filter
def mask_phone(value):
    """전화번호 마스킹: "010-1234-5678" -> "010-****-5678" """
    if not value:
        return value
    value = str(value).strip()

    # 010-1234-5678 or 01012345678
    match = re.match(r'^(\d{2,3})-?(\d{3,4})-?(\d{4})$', value)
    if match:
        return f'{match.group(1)}-****-{match.group(3)}'

    # +82-10-1234-5678 국제형식
    match = re.match(r'^(\+\d{1,4})-?(\d{1,3})-?(\d{3,4})-?(\d{4})$', value)
    if match:
        return f'{match.group(1)}-{match.group(2)}-****-{match.group(4)}'

    return value


@register.filter
def mask_email(value):
    """이메일 마스킹: "user@example.com" -> "us***@example.com"

    로컬파트 앞 2자리만 노출, 나머지 ***.
    """
    if not value:
        return value
    value = str(value).strip()
    match = re.match(r'^(.+)@(.+)$', value)
    if not match:
        return value

    local = match.group(1)
    domain = match.group(2)
    if len(local) <= 2:
        masked_local = local[0] + '***'
    else:
        masked_local = local[:2] + '***'
    return f'{masked_local}@{domain}'


@register.filter
def mask_name(value):
    """이름 마스킹: "홍길동" -> "홍*동", "김철수" -> "김*수"

    2글자: "김*", 3글자 이상: 첫/끝 글자만 노출.
    """
    if not value:
        return value
    value = str(value).strip()
    if len(value) <= 1:
        return value
    if len(value) == 2:
        return value[0] + '*'
    return value[0] + '*' * (len(value) - 2) + value[-1]
