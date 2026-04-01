import logging
from datetime import date, timedelta

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='marketplace.MarketplaceOrder')
def auto_create_erp_quotation(sender, instance, created, **kwargs):
    """마켓플레이스 주문 NEW → ERP 견적서 자동 생성

    - status=NEW이고 erp_quotation이 없을 때만 생성
    - 고객 생성 시 전화번호/주소 포함
    - 주문 전환은 수동으로 진행
    """
    if instance.status != 'NEW':
        return
    if instance.erp_quotation_id is not None:
        return

    from apps.inventory.models import Product
    from apps.sales.models import Customer, Quotation, QuotationItem

    with transaction.atomic():
        # 고객 찾기/생성 (buyer_name 기준, 전화번호+주소 포함)
        customer, customer_created = Customer.objects.get_or_create(
            name=instance.buyer_name,
            defaults={
                'phone': instance.buyer_phone or '',
                'address': instance.receiver_address or '',
                'created_by': instance.created_by,
            },
        )
        # 기존 고객이면 빈 필드만 업데이트
        if not customer_created:
            updated_fields = []
            if not customer.phone and instance.buyer_phone:
                customer.phone = instance.buyer_phone
                updated_fields.append('phone')
            if not customer.address and instance.receiver_address:
                customer.address = instance.receiver_address
                updated_fields.append('address')
            if updated_fields:
                updated_fields.append('updated_at')
                customer.save(update_fields=updated_fields)

        # 상품 매칭 (product_name으로 검색, 없으면 스킵)
        product = Product.objects.filter(
            name=instance.product_name, is_active=True,
        ).first()
        if not product:
            logger.warning(
                'MarketplaceOrder %s: 상품 "%s" 매칭 실패 — 견적서 미생성',
                instance.store_order_id, instance.product_name,
            )
            return

        # 견적서 생성 (구매일 기준, 유효기한 30일)
        quote_date = instance.ordered_at.date() if instance.ordered_at else date.today()
        quotation = Quotation.objects.create(
            quote_date=quote_date,
            valid_until=quote_date + timedelta(days=30),
            customer=customer,
            status=Quotation.Status.DRAFT,
            created_by=instance.created_by,
        )

        # 견적 항목 생성
        QuotationItem.objects.create(
            quotation=quotation,
            product=product,
            quantity=instance.quantity,
            cost_price=product.cost_price or 0,
            unit_price=product.unit_price if product.unit_price else instance.price,
            created_by=instance.created_by,
        )

        # 견적 합계 갱신
        quotation.update_total()

        # MarketplaceOrder에 견적서 연결 (시그널 재진입 방지: update)
        sender.objects.filter(pk=instance.pk).update(erp_quotation=quotation)

        logger.info(
            'MarketplaceOrder %s → Quotation %s 자동 생성 (고객: %s, 상품: %s, 수량: %s)',
            instance.store_order_id, quotation.quote_number,
            customer.name, product.name, instance.quantity,
        )
