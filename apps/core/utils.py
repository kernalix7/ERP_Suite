"""공통 유틸리티 함수"""
from django.utils import timezone


def generate_document_number(model_class, field_name, prefix):
    """날짜 기반 문서번호 자동 생성.

    형식: {PREFIX}-{YYYYMMDD}-{NNN}
    예: QT-20260322-001, ORD-20260322-042

    Args:
        model_class: 대상 모델 클래스
        field_name: 번호 필드명 (예: 'quote_number')
        prefix: 접두사 (예: 'QT')

    Returns:
        생성된 문서번호 문자열
    """
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
