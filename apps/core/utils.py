from datetime import date


def generate_number(model_class, prefix, date_field='created_at'):
    """자동 채번: prefix-YYYY-NNNN 형태"""
    today = date.today()
    year = today.strftime('%Y')
    prefix_str = f'{prefix}-{year}-'

    last = (
        model_class.all_objects
        .filter(**{f'{date_field}__year': today.year})
        .order_by('-pk')
        .first()
    )

    if last and hasattr(last, get_number_field(model_class)):
        field_name = get_number_field(model_class)
        last_number = getattr(last, field_name, '')
        if last_number.startswith(prefix_str):
            try:
                seq = int(last_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
    else:
        seq = 1

    return f'{prefix_str}{seq:04d}'


def get_number_field(model_class):
    """모델에서 번호 필드명을 찾는다."""
    for field in model_class._meta.fields:
        if field.name.endswith('_number') or field.name.endswith('number'):
            return field.name
    return None
