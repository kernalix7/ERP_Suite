import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='warranty.ProductRegistration')
def auto_link_order_on_registration(sender, instance, created, **kwargs):
    """정품등록 시 serial_number로 OrderItem 매칭하여 order FK 자동 설정

    - serial_number가 'ORD-XXXX-N' 형태이면 주문번호 + 항목 추출
    - customer FK도 OrderItem의 주문 고객으로 자동 설정
    """
    if not created:
        return

    if not instance.serial_number:
        return

    # 기존 sales 시그널에서 생성하는 serial: '{order_number}-{item_pk}' 형태
    # 예: 'ORD-2026-0001-3' → order_number='ORD-2026-0001', item_pk=3
    serial = instance.serial_number
    if not serial.startswith('ORD-'):
        return

    # 마지막 '-' 기준으로 분리
    parts = serial.rsplit('-', 1)
    if len(parts) != 2:
        return

    order_number = parts[0]

    from apps.sales.models import Order

    order = Order.objects.filter(
        order_number=order_number, is_active=True,
    ).first()
    if not order:
        return

    # customer FK 자동 설정 (없을 때만)
    updated_fields = []
    if not instance.customer_id and order.customer_id:
        instance.customer_id = order.customer_id
        updated_fields.append('customer_id')

    if updated_fields:
        sender.objects.filter(pk=instance.pk).update(
            **{f: getattr(instance, f) for f in updated_fields}
        )
        logger.info(
            'ProductRegistration %s → Order %s 연결 (customer=%s)',
            instance.serial_number, order.order_number,
            order.customer_id,
        )
