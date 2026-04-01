"""공통 유틸리티 함수"""
from django.db import IntegrityError, transaction
from django.utils import timezone


def generate_document_number(model_class, field_name, prefix):
    """날짜 기반 문서번호 자동 생성.

    형식: {PREFIX}-{YYYYMMDD}-{NNN}
    예: QT-20260322-001, ORD-20260322-042

    동시성 충돌 시 최대 3회 재시도.

    Args:
        model_class: 대상 모델 클래스
        field_name: 번호 필드명 (예: 'quote_number')
        prefix: 접두사 (예: 'QT')

    Returns:
        생성된 문서번호 문자열
    """
    for attempt in range(3):
        try:
            with transaction.atomic():
                today = timezone.localdate()
                date_str = today.strftime('%Y%m%d')
                pattern = f'{prefix}-{date_str}-'

                last = (
                    model_class.all_objects
                    .filter(**{f'{field_name}__startswith': pattern})
                    .order_by(f'-{field_name}')
                    .values_list(field_name, flat=True)
                    .first()
                )

                if last:
                    seq = int(last.split('-')[-1]) + 1
                else:
                    seq = 1

                return f'{pattern}{seq:03d}'
        except IntegrityError:
            if attempt == 2:
                raise
            continue


def generate_sequential_code(model_class, field_name, prefix, digits=4):
    """순번 기반 코드 자동 생성 (날짜 없음).

    형식: {PREFIX}-{NNNN}
    예: CST-0001, SUP-001

    Args:
        model_class: 대상 모델 클래스
        field_name: 코드 필드명 (예: 'code')
        prefix: 접두사 (예: 'CST')
        digits: 순번 자릿수 (기본 4)

    Returns:
        생성된 코드 문자열
    """
    pattern = f'{prefix}-'

    last = (
        model_class.all_objects
        .filter(**{f'{field_name}__startswith': pattern})
        .order_by(f'-{field_name}')
        .values_list(field_name, flat=True)
        .first()
    )

    if last:
        # 접두사 뒤의 숫자 부분만 추출 (예: 'CUS-003-ABC' → '003')
        after_prefix = last[len(pattern):]  # '003-ABC' or '0001'
        num_part = after_prefix.split('-')[0]  # '003' or '0001'
        try:
            seq = int(num_part) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1

    return f'{pattern}{seq:0{digits}d}'
