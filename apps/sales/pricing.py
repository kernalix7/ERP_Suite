from datetime import date

from django.db import models

from apps.sales.models import PriceRule


def get_applicable_price(product, partner=None, customer=None, quantity=1, ref_date=None):
    """가격규칙 조회. 반환: {'unit_price': int, 'discount_rate': Decimal, 'source': str}"""
    if ref_date is None:
        ref_date = date.today()

    rules = PriceRule.objects.filter(
        product=product, is_active=True, min_quantity__lte=quantity,
    ).filter(
        models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=ref_date),
    ).filter(
        models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=ref_date),
    )

    if partner:
        rules = rules.filter(
            models.Q(partner=partner) | models.Q(partner__isnull=True),
        )
    else:
        rules = rules.filter(partner__isnull=True)

    if customer:
        rules = rules.filter(
            models.Q(customer=customer) | models.Q(customer__isnull=True),
        )
    else:
        rules = rules.filter(customer__isnull=True)

    # 우선순위: priority DESC -> 구체적(partner/customer not null) -> min_quantity DESC
    rule = rules.order_by(
        '-priority',
        models.Case(
            models.When(partner__isnull=False, customer__isnull=False, then=0),
            models.When(partner__isnull=False, then=1),
            models.When(customer__isnull=False, then=1),
            default=2,
        ),
        '-min_quantity',
    ).first()

    base_price = int(product.unit_price)
    if not rule:
        return {'unit_price': base_price, 'discount_rate': 0, 'source': 'default'}

    if rule.unit_price is not None:
        return {'unit_price': int(rule.unit_price), 'discount_rate': 0, 'source': 'fixed'}

    if rule.discount_rate > 0:
        discounted = int(base_price * (1 - rule.discount_rate / 100))
        return {
            'unit_price': discounted,
            'discount_rate': float(rule.discount_rate),
            'source': 'discount',
        }

    return {'unit_price': base_price, 'discount_rate': 0, 'source': 'default'}
