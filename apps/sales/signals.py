import logging
from datetime import date, timedelta

from django.db import transaction
from django.db.models import F
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from apps.inventory.models import Product, StockMovement, Warehouse


logger = logging.getLogger(__name__)

WARRANTY_DAYS = 365  # 기본 보증기간 (1년)


class InsufficientStockError(Exception):
    """재고 부족 시 발생하는 예외"""
    pass


@receiver(pre_save, sender='sales.Order')
def auto_stock_out_on_ship(sender, instance, **kwargs):
    """주문이 출고완료 상태로 변경되면 자동으로 출고 전표 생성"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # 상태가 '출고완료'로 변경될 때만
    if old.status not in ('SHIPPED', 'PARTIAL_SHIPPED') and instance.status == 'SHIPPED':
        _auto_full_ship(instance)
        # CONFIRMED/PARTIAL_SHIPPED에서 전환 시에만 예약재고 해제 (예약된 적이 있는 경우만)
        if old.status in ('CONFIRMED', 'PARTIAL_SHIPPED'):
            _auto_release_reserved_stock(instance, quantity_source='full')
    # 부분출고→출고완료 전환 시 이미 ShipmentItem으로 처리됨 → 스킵
    if old.status == 'PARTIAL_SHIPPED' and instance.status == 'SHIPPED':
        pass  # ShipmentItem 시그널에서 이미 처리 (예약재고 포함)

    # 배송완료 시 → 고객 구매내역 + 정품등록 자동 생성
    if old.status != 'DELIVERED' and instance.status == 'DELIVERED':
        _auto_register_on_delivered(instance)

    # 배송완료 시 → 수수료 자동 생성
    if old.status != 'DELIVERED' and instance.status == 'DELIVERED':
        _auto_create_commission(instance)

    # 확정 시 → 재고 예약 + 매출채권(AR) + 세금계산서 자동 생성
    if old.status != 'CONFIRMED' and instance.status == 'CONFIRMED':
        _auto_reserve_stock(instance)
        _auto_create_ar(instance)
        _auto_create_tax_invoice(instance)

    # 취소 시 → 연쇄 처리 (재고복원, 수수료취소, AR취소)
    if old.status != 'CANCELLED' and instance.status == 'CANCELLED':
        _auto_cancel_order(instance, old.status)

    # 입금은 주문 상세에서 수동 처리 (자동입금 제거)


def _auto_full_ship(instance):
    """전량 출고 처리 (기존 all-or-nothing 방식)"""
    warehouse = Warehouse.get_default()
    if not warehouse:
        logger.error(
            'No warehouse configured — '
            'cannot create stock movement for %s',
            instance,
        )
        return

    # C2: Idempotency — skip if movements already exist
    existing = StockMovement.all_objects.filter(
        reference__startswith=f'주문 {instance.order_number}',
        movement_type='OUT',
    ).exists()
    if existing:
        return

    # C1: 미출고 수량만 체크 (부분출고 이력 고려)
    insufficient = []
    for item in instance.items.all():
        remaining = item.quantity - item.shipped_quantity
        if remaining <= 0:
            continue
        product = Product.all_objects.get(pk=item.product_id)
        if product.current_stock < remaining:
            insufficient.append(
                f'{product.name}({product.code}): '
                f'현재 {product.current_stock}, '
                f'필요 {remaining}'
            )

    if insufficient:
        raise InsufficientStockError(
            '재고 부족으로 출고할 수 없습니다.\n'
            + '\n'.join(insufficient)
        )

    with transaction.atomic():
        from apps.sales.models import OrderItem
        for item in instance.items.all():
            remaining = item.quantity - item.shipped_quantity
            if remaining <= 0:
                continue
            StockMovement.objects.create(
                movement_number=(
                    f'OUT-{instance.order_number}-{item.pk}'
                ),
                movement_type='OUT',
                product=item.product,
                warehouse=warehouse,
                quantity=remaining,
                unit_price=item.unit_price,
                movement_date=date.today(),
                reference=f'주문 {instance.order_number}',
                created_by=instance.created_by,
            )
            OrderItem.objects.filter(pk=item.pk).update(
                shipped_quantity=item.quantity,
            )


def _auto_reserve_stock(order):
    """주문 확정 시 각 주문항목의 수량만큼 예약재고 증가"""
    with transaction.atomic():
        for item in order.items.select_related('product').all():
            Product.objects.filter(pk=item.product_id).update(
                reserved_stock=F('reserved_stock') + item.quantity,
            )
        logger.info(
            'Reserved stock for order %s (%d items)',
            order.order_number, order.items.count(),
        )


def _auto_release_reserved_stock(order, quantity_source='full'):
    """예약재고 해제

    Args:
        order: 주문 객체
        quantity_source: 'full' = 주문 전체 수량 해제, 'shipped' = 출고된 수량만 해제
    """
    with transaction.atomic():
        for item in order.items.select_related('product').all():
            if quantity_source == 'shipped':
                release_qty = item.shipped_quantity
            else:
                release_qty = item.quantity
            if release_qty > 0:
                # 예약재고가 해제량보다 적으면 0으로 설정 (직접 CONFIRMED 생성 등 대응)
                product = Product.objects.get(pk=item.product_id)
                actual_release = min(release_qty, product.reserved_stock)
                if actual_release > 0:
                    Product.objects.filter(pk=item.product_id).update(
                        reserved_stock=F('reserved_stock') - actual_release,
                    )
        logger.info(
            'Released reserved stock for order %s (source=%s)',
            order.order_number, quantity_source,
        )


def _auto_register_on_delivered(order):
    """배송완료 시 고객구매내역 + 정품등록 자동 생성"""
    from apps.sales.models import CustomerPurchase
    from apps.warranty.models import ProductRegistration

    customer = order.customer
    today = date.today()
    warranty_end = today + timedelta(days=WARRANTY_DAYS)

    with transaction.atomic():
        for item in order.items.select_related('product').all():
            # 고객 구매내역 자동 생성 (고객이 있을 때만)
            if customer:
                CustomerPurchase.objects.get_or_create(
                    customer=customer,
                    product=item.product,
                    serial_number=f'{order.order_number}-{item.pk}',
                    defaults={
                        'purchase_date': today,
                        'warranty_end': warranty_end,
                        'created_by': order.created_by,
                    },
                )

            # 정품등록 자동 생성
            serial = f'{order.order_number}-{item.pk}'
            if not ProductRegistration.all_objects.filter(serial_number=serial).exists():
                ProductRegistration.objects.create(
                    serial_number=serial,
                    product=item.product,
                    customer=customer,
                    customer_name=customer.name if customer else (order.partner.name if order.partner else '-'),
                    phone=customer.phone if customer else '',
                    purchase_date=today,
                    purchase_channel=order.partner.name if order.partner else '',
                    warranty_start=today,
                    warranty_end=warranty_end,
                    is_verified=True,
                    created_by=order.created_by,
                )
                logger.info('Auto-created ProductRegistration %s for order %s', serial, order.order_number)


def _auto_create_commission(order):
    """배송완료 시 거래처 수수료율 기반 수수료 자동 생성"""
    from apps.sales.commission import CommissionRecord

    if not order.partner:
        return

    # 이미 수수료 내역이 있으면 스킵
    if CommissionRecord.objects.filter(order=order).exists():
        return

    # 수수료 항목 기반 계산
    order_amount = int(order.total_amount)
    commission_amount = order.partner.calculate_commission(order_amount)
    if commission_amount <= 0:
        return

    rate = order.partner.total_commission_rate

    with transaction.atomic():
        CommissionRecord.objects.create(
            partner=order.partner,
            order=order,
            order_amount=order_amount,
            commission_rate=rate,
            commission_amount=commission_amount,
            created_by=order.created_by,
        )
        logger.info(
            'Auto-created CommissionRecord for order %s: %s원 (%s%%)',
            order.order_number, commission_amount, rate,
        )


def _auto_create_ar(order):
    """주문 확정 시 매출채권(AR) 자동 생성"""
    from apps.accounting.models import AccountReceivable

    if not order.partner:
        return

    grand_total = int(order.grand_total) if order.grand_total else 0
    if grand_total <= 0:
        return

    # 이미 AR이 있으면 스킵
    if AccountReceivable.objects.filter(order=order, is_active=True).exists():
        return

    with transaction.atomic():
        ar = AccountReceivable.objects.create(
            partner=order.partner,
            order=order,
            amount=grand_total,
            due_date=order.delivery_date or (date.today() + timedelta(days=30)),
            status='PENDING',
            created_by=order.created_by,
        )
        logger.info(
            'Auto-created AR for order %s: %s원 (납기: %s)',
            order.order_number, grand_total, ar.due_date,
        )


def _auto_create_tax_invoice(order):
    """주문 확정 시 매출 세금계산서 자동 생성"""
    from apps.accounting.models import TaxInvoice

    if not order.partner:
        return

    supply_amount = int(order.total_amount) if order.total_amount else 0
    tax_amount = int(order.tax_total) if order.tax_total else 0
    if supply_amount <= 0:
        return

    # 이미 세금계산서가 있으면 스킵
    if TaxInvoice.objects.filter(order=order, is_active=True).exists():
        return

    with transaction.atomic():
        inv = TaxInvoice.objects.create(
            invoice_type='SALES',
            partner=order.partner,
            order=order,
            issue_date=date.today(),
            supply_amount=supply_amount,
            tax_amount=tax_amount,
            total_amount=supply_amount + tax_amount,
            description=f'주문 {order.order_number} 매출 세금계산서',
            created_by=order.created_by,
        )
        logger.info(
            'Auto-created TaxInvoice %s for order %s',
            inv.invoice_number, order.order_number,
        )


def _auto_cancel_order(order, old_status):
    """주문 취소 시 연쇄 처리: 재고복원, 수수료취소, AR취소, 세금계산서취소"""
    from apps.accounting.models import AccountReceivable, TaxInvoice
    from apps.sales.commission import CommissionRecord

    with transaction.atomic():
        # 1. AR 취소 (soft delete)
        ars = AccountReceivable.objects.filter(order=order, is_active=True)
        for ar in ars:
            if ar.paid_amount > 0:
                logger.warning(
                    'AR %s has paid_amount=%s — skipping auto-cancel',
                    ar.pk, ar.paid_amount,
                )
                continue
            ar.is_active = False
            ar.save(update_fields=['is_active', 'updated_at'])
            logger.info('Auto-cancelled AR pk=%s for order %s', ar.pk, order.order_number)

        # 2. 수수료 취소 (soft delete)
        commissions = CommissionRecord.objects.filter(order=order, is_active=True)
        for comm in commissions:
            if comm.status == 'SETTLED':
                logger.warning(
                    'CommissionRecord %s already settled — skipping auto-cancel',
                    comm.pk,
                )
                continue
            comm.is_active = False
            comm.save(update_fields=['is_active', 'updated_at'])
            logger.info('Auto-cancelled CommissionRecord pk=%s for order %s', comm.pk, order.order_number)

        # 2-1. 예약재고 해제 (확정 이후 취소 시)
        if old_status in ('CONFIRMED', 'PARTIAL_SHIPPED'):
            for item in order.items.select_related('product').all():
                # CONFIRMED에서 취소: 전량 해제
                # PARTIAL_SHIPPED에서 취소: 미출고분만 해제 (출고분은 ShipmentItem에서 이미 해제)
                release_qty = item.quantity - item.shipped_quantity
                if release_qty > 0:
                    product = Product.objects.get(pk=item.product_id)
                    actual_release = min(release_qty, product.reserved_stock)
                    if actual_release > 0:
                        Product.objects.filter(pk=item.product_id).update(
                            reserved_stock=F('reserved_stock') - actual_release,
                        )
            logger.info(
                'Released reserved stock for cancelled order %s (from %s)',
                order.order_number, old_status,
            )

        # 3. 재고 복원 — 출고 이동(OUT)이 있으면 soft delete → 시그널이 재고 복원
        if old_status in ('PARTIAL_SHIPPED', 'SHIPPED', 'DELIVERED'):
            from apps.inventory.models import StockMovement
            from django.db.models import Q
            movements = StockMovement.objects.filter(
                Q(reference=f'주문 {order.order_number}')
                | Q(reference=f'부분출고 {order.order_number}'),
                movement_type='OUT',
                is_active=True,
            )
            for mv in movements:
                mv.is_active = False
                mv.save(update_fields=['is_active', 'updated_at'])
                logger.info(
                    'Auto-reversed stock movement %s for cancelled order %s',
                    mv.movement_number, order.order_number,
                )

        # 3-1. shipped_quantity 초기화
        if old_status in ('PARTIAL_SHIPPED', 'SHIPPED', 'DELIVERED'):
            from apps.sales.models import OrderItem
            order.items.update(shipped_quantity=0)

        # 4. 세금계산서 취소 (soft delete)
        invoices = TaxInvoice.objects.filter(order=order, is_active=True)
        for inv in invoices:
            inv.is_active = False
            inv.save(update_fields=['is_active', 'updated_at'])
            logger.info('Auto-cancelled TaxInvoice %s for order %s', inv.invoice_number, order.order_number)

    logger.info('Order %s cancelled — AR/commission/stock/invoice reversed', order.order_number)


@receiver(post_save, sender='sales.ShipmentItem')
def auto_stock_on_shipment_item(sender, instance, created, **kwargs):
    """배송항목 생성 시 부분 출고 처리"""
    if not created:
        return

    shipment = instance.shipment
    order = shipment.order
    order_item = instance.order_item
    warehouse = Warehouse.get_default()
    if not warehouse:
        logger.error('No warehouse — cannot create partial shipment')
        return

    with transaction.atomic():
        # 재고 부족 체크
        product = Product.all_objects.get(pk=order_item.product_id)
        if product.current_stock < instance.quantity:
            raise InsufficientStockError(
                f'재고 부족: {product.name} '
                f'(현재 {product.current_stock}, '
                f'필요 {instance.quantity})'
            )

        # OUT 재고이동 생성
        StockMovement.objects.create(
            movement_number=(
                f'OUT-{order.order_number}'
                f'-SH{shipment.pk}-{instance.pk}'
            ),
            movement_type='OUT',
            product=order_item.product,
            warehouse=warehouse,
            quantity=instance.quantity,
            unit_price=order_item.unit_price,
            movement_date=shipment.shipped_date or date.today(),
            reference=f'부분출고 {order.order_number}',
            created_by=shipment.created_by,
        )

        # 예약재고 해제 (출고된 수량만큼, 예약 없으면 스킵)
        prod = Product.objects.get(pk=order_item.product_id)
        actual_release = min(instance.quantity, prod.reserved_stock)
        if actual_release > 0:
            Product.objects.filter(pk=order_item.product_id).update(
                reserved_stock=F('reserved_stock') - actual_release,
            )

        # OrderItem.shipped_quantity 갱신
        from apps.sales.models import OrderItem
        OrderItem.objects.filter(pk=order_item.pk).update(
            shipped_quantity=F('shipped_quantity') + instance.quantity,
        )

        # 주문 상태 자동 전환
        order_item.refresh_from_db()
        all_items = order.items.all()
        total_ordered = sum(i.quantity for i in all_items)
        total_shipped = sum(i.shipped_quantity for i in all_items)

        from apps.sales.models import Order
        if total_shipped >= total_ordered:
            Order.objects.filter(pk=order.pk).update(
                status='SHIPPED',
            )
        elif total_shipped > 0:
            Order.objects.filter(pk=order.pk).update(
                status='PARTIAL_SHIPPED',
            )

    logger.info(
        'Partial shipment: %s item %s qty=%s '
        '(shipped %s/%s)',
        order.order_number,
        order_item.product.code,
        instance.quantity,
        order_item.shipped_quantity,
        order_item.quantity,
    )


def _auto_create_payment(order, deposit_amount=None, commission_amount=0):
    """입금 생성 + 복식부기 전표 + 계좌 잔액 반영

    Args:
        order: 주문 객체
        deposit_amount: 실 입금액 (None이면 grand_total 전액)
        commission_amount: 플랫폼 수수료 차감액
    """
    from apps.accounting.models import (
        BankAccount, Payment, Voucher, VoucherLine, AccountCode,
    )

    grand_total = int(order.grand_total) if order.grand_total else 0

    if grand_total <= 0:
        # 0원 주문은 전표 없이 입금완료 처리
        from apps.sales.models import Order as _Order
        _Order.objects.filter(pk=order.pk).update(
            is_paid=True, paid_date=date.today(),
        )
        return

    # 이미 입금 처리된 주문이면 스킵
    if Payment.objects.filter(
        reference=f'주문 {order.order_number}',
        payment_type='RECEIPT',
    ).exists():
        return

    # 주문에 설정된 계좌 우선, 없으면 기본계좌
    bank = order.bank_account
    if not bank:
        bank = BankAccount.objects.filter(
            is_active=True, is_default=True,
        ).first()
    if not bank:
        logger.warning(
            '입금계좌 미설정 — 주문 %s 입금 자동생성 불가',
            order.order_number,
        )
        return

    # 실 입금액 결정
    commission_amount = int(commission_amount or 0)
    if deposit_amount is not None:
        actual_deposit = int(deposit_amount)
    else:
        actual_deposit = grand_total - commission_amount

    supply_amount = int(order.total_amount)
    tax_amount = int(order.tax_total)

    with transaction.atomic():
        # 1) 복식부기 전표 생성
        desc = f'매출 입금 - {order.order_number}'
        if commission_amount > 0:
            desc += f' (수수료 {commission_amount:,}원 차감)'
        voucher = Voucher.objects.create(
            voucher_type='RECEIPT',
            voucher_date=date.today(),
            description=desc,
            approval_status='APPROVED',
            created_by=order.created_by,
        )

        acct_deposit = AccountCode.objects.filter(
            code='103',
        ).first()  # 보통예금
        acct_revenue = AccountCode.objects.filter(
            code='401',
        ).first()  # 매출
        acct_vat = AccountCode.objects.filter(
            code='204',
        ).first()  # 부가세예수금
        acct_commission = AccountCode.objects.filter(
            code='502',
        ).first()  # 수수료비용 (배송비/수수료)

        # 차변: 보통예금 (실 입금액)
        if acct_deposit:
            VoucherLine.objects.create(
                voucher=voucher,
                account=acct_deposit,
                debit=actual_deposit,
                credit=0,
                description=f'{bank.name} 입금',
            )

        # 차변: 수수료비용 (플랫폼 수수료)
        if commission_amount > 0 and acct_commission:
            VoucherLine.objects.create(
                voucher=voucher,
                account=acct_commission,
                debit=commission_amount,
                credit=0,
                description=f'{order.order_number} 플랫폼 수수료',
            )

        # 대변: 매출 (공급가액)
        if acct_revenue:
            VoucherLine.objects.create(
                voucher=voucher,
                account=acct_revenue,
                debit=0,
                credit=supply_amount,
                description=f'{order.order_number} 매출',
            )

        # 대변: 부가세예수금
        if acct_vat and tax_amount > 0:
            VoucherLine.objects.create(
                voucher=voucher,
                account=acct_vat,
                debit=0,
                credit=tax_amount,
                description=f'{order.order_number} 부가세',
            )

        # 2) 입금 기록 생성 (실 입금액 기준)
        Payment.objects.create(
            payment_type='RECEIPT',
            partner=order.partner,
            bank_account=bank,
            voucher=voucher,
            amount=actual_deposit,
            payment_date=date.today(),
            payment_method='BANK_TRANSFER',
            reference=f'주문 {order.order_number}',
            created_by=order.created_by,
        )

        # 3) is_paid 플래그 업데이트
        from apps.sales.models import Order
        Order.objects.filter(pk=order.pk).update(
            is_paid=True, paid_date=date.today(),
        )
        logger.info(
            'Auto-created Payment+Voucher for order %s: '
            '%s원 → %s (전표: %s)',
            order.order_number, grand_total,
            bank.name, voucher.voucher_number,
        )
