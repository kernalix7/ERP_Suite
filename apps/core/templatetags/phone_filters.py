import re

from django import template

register = template.Library()


@register.filter
def format_phone(value):
    """전화번호를 국제 표시 형식으로 포맷팅.

    저장 형식: +82-10-1234-5678
    레거시 형식: +82-010-1234-5678 (leading 0 포함)
    표시: +82-10-1234-5678 (leading 0 제거)
    """
    if not value:
        return value

    value = str(value).strip()

    # +CC-번호 패턴 매칭
    match = re.match(r'^(\+\d{1,4})[-\s](.+)$', value)
    if not match:
        return value

    country_code = match.group(1)
    number_part = match.group(2).replace('-', '').replace(' ', '')

    # leading 0 제거
    if number_part.startswith('0'):
        number_part = number_part[1:]

    # 한국 번호 포맷팅
    if country_code == '+82':
        if len(number_part) <= 1:
            formatted = number_part
        elif number_part[0] == '2':
            # 서울 (02→2): 2-XXXX-XXXX
            if len(number_part) <= 4:
                formatted = f"{number_part[:1]}-{number_part[1:]}"
            else:
                formatted = f"{number_part[:1]}-{number_part[1:5]}-{number_part[5:9]}"
        else:
            # 휴대폰/지역 (010→10): 10-XXXX-XXXX
            if len(number_part) <= 6:
                formatted = f"{number_part[:2]}-{number_part[2:]}"
            else:
                formatted = f"{number_part[:2]}-{number_part[2:6]}-{number_part[6:10]}"
    else:
        # 기타 국가: 4자리씩
        parts = [number_part[i:i + 4] for i in range(0, len(number_part), 4)]
        formatted = '-'.join(parts)

    return f"{country_code}-{formatted}"
