import logging
from datetime import date, timedelta

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='sales.Shipment', dispatch_uid='marketplace.Shipment.push_on_shipped')
def push_marketplace_shipping_on_shipped(sender, instance, **kwargs):
    """Shipment SHIPPED 전환 시 마켓플레이스 주문이면 push_shipping_async 호출.

    - Shipment.order에 연결된 MarketplaceOrder가 있을 때만 push 큐잉
    - 비활성/취소된 마켓 주문은 제외
    """
    if not instance.pk:
        return
    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.status == 'SHIPPED' or instance.status != 'SHIPPED':
        return

    from .models import MarketplaceOrder
    mkt_orders = MarketplaceOrder.objects.filter(
        erp_order_id=instance.order_id, is_active=True,
    ).exclude(status__in=['CANCELLED', 'RETURNED']).only('pk', 'store_order_id')

    if not mkt_orders.exists():
        return

    from .tasks import push_shipping_async
    for mkt in mkt_orders:
        try:
            push_shipping_async.delay(mkt.pk)
            logger.info(
                'Shipment %s SHIPPED → push_shipping_async queued (mkt_order=%s)',
                instance.pk, mkt.store_order_id,
            )
        except Exception:
            logger.exception(
                'push_shipping_async 큐잉 실패 (mkt_order=%s)', mkt.store_order_id,
            )


@receiver(post_save, sender='marketplace.MarketplaceOrder')
def auto_create_erp_quotation(sender, instance, created, **kwargs):
    """마켓플레이스 주문 NEW → ERP 견적서 자동 생성

    - status=NEW이고 erp_quotation이 없을 때만 생성
    - _skip_signal attr이 있으면 건너뜀 (import 경로에서 직접 처리)
    - matched_product_id attr이 있으면 그 제품 사용
    - 고객 생성 시 전화번호/주소 포함
    - 주문 전환은 수동으로 진행
    """
    # import 경로에서는 시그널 건너뜀 (import_selected_orders가 직접 처리)
    from .sync_service import _import_context
    if getattr(_import_context, 'skip_signal', False):
        return
    if instance.status != 'NEW':
        return
    if instance.erp_quotation_id is not None:
        return

    from apps.inventory.models import Product
    from apps.sales.models import Customer, Quotation, QuotationItem
    from .models import ProductMapping

    with transaction.atomic():
        # 주소 분리
        from .sync_service import _parse_address
        address, address_road, address_detail = _parse_address(instance.receiver_address)

        # 고객 찾기/생성 (buyer_name 기준, 전화번호+주소 포함)
        customer, customer_created = Customer.objects.get_or_create(
            name=instance.buyer_name,
            defaults={
                'phone': instance.buyer_phone or '',
                'address': address,
                'address_road': address_road,
                'address_detail': address_detail,
                'created_by': instance.created_by,
            },
        )
        # 기존 고객이면 빈 필드만 업데이트
        if not customer_created:
            updated_fields = []
            if not customer.phone and instance.buyer_phone:
                customer.phone = instance.buyer_phone
                updated_fields.append('phone')
            if not customer.address and address:
                customer.address = address
                customer.address_road = address_road
                customer.address_detail = address_detail
                updated_fields.extend(['address', 'address_road', 'address_detail'])
            if updated_fields:
                updated_fields.append('updated_at')
                customer.save(update_fields=updated_fields)

        # 상품 매칭: matched_product_id attr → ProductMapping → 이름 검색
        product = None
        matched_id = getattr(instance, '_matched_product_id', None)
        if matched_id:
            product = Product.objects.filter(pk=matched_id, is_active=True).first()

        if not product:
            mapping = ProductMapping.objects.filter(
                store_product_name=instance.product_name,
                store_option_name=instance.option_name or '',
                is_active=True,
            ).select_related('product').first()
            if mapping:
                product = mapping.product

        if not product:
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
