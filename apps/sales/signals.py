import logging
from datetime import date, timedelta

from django.utils import timezone

from django.db import transaction
from django.db.models import F
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from apps.inventory.models import Product, StockMovement, Warehouse, WarehouseStock


logger = logging.getLogger(__name__)


def _get_partner_module(partner):
    """거래처의 스토어 모듈 인스턴스 반환 (없으면 None)."""
    if not partner or not getattr(partner, 'store_module', ''):
        return None
    try:
        from apps.store_modules.registry import registry
        return registry.get_instance(partner.store_module)
    except (ImportError, Exception):
        return None


def _get_product_warehouse(product_id):
    """제품의 실제 재고가 있는 창고 반환 (WarehouseStock 기준, 수량 많은 순)"""
    ws = WarehouseStock.objects.filter(
        product_id=product_id,
        quantity__gt=0,
        is_active=True,
    ).select_related('warehouse').order_by('-quantity').first()
    if ws:
        return ws.warehouse
    return Warehouse.get_default()

class InsufficientStockError(Exception):
    """재고 부족 시 발생하는 예외"""
    pass


@receiver(pre_save, sender='sales.Quotation')
def validate_quotation_status_transition(sender, instance, **kwargs):
    """견적서 상태 전환 규칙 검증"""
    if not instance.pk:
        return
    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.status == instance.status:
        return
    from apps.sales.models import Quotation
    allowed = Quotation.STATUS_TRANSITIONS.get(old.status, [])
    if instance.status not in allowed:
        raise ValueError(
            f'견적 상태를 {old.get_status_display()}에서 '
            f'{instance.get_status_display()}(으)로 변경할 수 없습니다.'
        )


@receiver(pre_save, sender='sales.Order')
def auto_fill_bank_account(sender, instance, **kwargs):
    """bank_account가 비어있으면 거래처 기본 입금계좌로 자동 설정"""
    if not instance.bank_account_id and instance.partner_id:
        try:
            partner = instance.partner
            if partner.default_bank_account_id:
                instance.bank_account_id = partner.default_bank_account_id
        except Exception:
            pass


@receiver(pre_save, sender='sales.Order')
def auto_stock_out_on_ship(sender, instance, **kwargs):
    """주문이 출고완료 상태로 변경되면 자동으로 출고 전표 생성"""
    if not instance.pk:
        return

    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # 상태가 '출고완료'로 변경될 때만
    if old.status not in ('SHIPPED', 'PARTIAL_SHIPPED') and instance.status == 'SHIPPED':
        _auto_full_ship(instance)
        # CONFIRMED에서 전환 시에만 예약재고 해제 (예약된 적이 있는 경우만)
        if old.status == 'CONFIRMED':
            _auto_release_reserved_stock(instance, quantity_source='full')
    # 부분출고→출고완료 전환 시: 미출고 잔량 처리
    elif old.status == 'PARTIAL_SHIPPED' and instance.status == 'SHIPPED':
        _auto_full_ship(instance)
        _auto_release_reserved_stock(instance)

    # 배송완료 시 → Shipment 동기화 + 고객등록 + 종결 체크
    # 수수료는 입금 시 발생 (배송완료 ≠ 입금완료)
    if old.status != 'DELIVERED' and instance.status == 'DELIVERED':
        _sync_shipments_delivered(instance)
        _auto_register_on_delivered(instance)
        _try_close_order(instance)  # 선입금 후 배송완료 시 자동 종결

    # 확정 시 → 거래처 승인 검증 + 주문 유형별 분기
    if old.status != 'CONFIRMED' and instance.status == 'CONFIRMED':
        if instance.partner and getattr(instance.partner, 'approval_status', 'APPROVED') != 'APPROVED':
            raise ValueError(
                f'거래처 "{instance.partner.name}"의 승인상태가 '
                f'"{instance.partner.get_approval_status_display()}"이므로 주문을 확정할 수 없습니다.'
            )
        if instance.order_type == 'RETURN':
            _auto_create_return_stock_in(instance)
            _auto_reverse_ar(instance)
            _auto_cancel_tax_invoice_for_return(instance)
        elif instance.order_type == 'EXCHANGE':
            _auto_create_exchange_stock_movements(instance)
            _auto_exchange_ar_diff(instance)
            _auto_cancel_tax_invoice_for_return(instance)
        else:
            _auto_reserve_stock(instance)
            _check_credit_limit(instance)
            _auto_create_ar(instance)
            _auto_create_tax_invoice(instance)

    # 취소 시 → 연쇄 처리 (재고복원, 수수료취소, AR취소)
    if old.status != 'CANCELLED' and instance.status == 'CANCELLED':
        _auto_cancel_order(instance, old.status)

    # 입금은 주문 상세에서 수동 처리 (자동입금 제거)


def _auto_full_ship(instance):
    """전량 출고 처리 (기존 all-or-nothing 방식)"""
    # C2: Idempotency — skip if active movements already exist
    existing = StockMovement.objects.filter(
        reference__startswith=f'주문 {instance.order_number}',
        movement_type='OUT',
        is_active=True,
    ).exists()
    if existing:
        return

    # C1: 미출고 수량만 체크 (부분출고 이력 고려, 재고추적 상품만)
    insufficient = []
    for item in instance.items.all():
        remaining = item.quantity - item.shipped_quantity
        if remaining <= 0:
            continue
        product = Product.all_objects.get(pk=item.product_id)
        if product.is_stockable and product.current_stock < remaining:
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
            if item.product.is_stockable:
                warehouse = _get_product_warehouse(item.product_id)
                if not warehouse:
                    logger.error(
                        'No warehouse for product %s — '
                        'cannot create stock movement for %s',
                        item.product, instance,
                    )
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
            if item.product.is_stockable:
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
            if not item.product.is_stockable:
                continue
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

    # 고객/거래처 모두 없으면 ProductRegistration 생성 스킵
    if not customer and not order.partner:
        logger.warning(
            '주문 %s: 고객/거래처 없음 — ProductRegistration 생성 스킵',
            order.order_number,
        )
        return

    today = date.today()

    with transaction.atomic():
        for item in order.items.select_related('product').all():
            # 고객 구매내역 자동 생성 (고객이 있을 때만)
            if customer:
                from apps.warranty.models import DEFAULT_VERIFIED_WARRANTY_DAYS
                CustomerPurchase.objects.get_or_create(
                    customer=customer,
                    product=item.product,
                    serial_number=f'{order.order_number}-{item.pk}',
                    defaults={
                        'purchase_date': today,
                        'warranty_end': today + timedelta(days=DEFAULT_VERIFIED_WARRANTY_DAYS),
                        'created_by': order.created_by,
                    },
                )

            # 정품등록 자동 생성 (warranty_end는 모델 save()에서 자동 계산)
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
                    warranty_end=today,  # save()에서 재계산됨
                    is_verified=True,
                    created_by=order.created_by,
                )
                logger.info('Auto-created ProductRegistration %s for order %s', serial, order.order_number)


def _auto_create_commission(order):
    """배송완료 시 거래처 수수료율 기반 수수료 자동 생성 + 출금(DISBURSEMENT) 처리

    입금은 전액 처리, 수수료는 별도 출금으로 처리.
    """
    from apps.sales.commission import CommissionRecord
    from apps.sales.models import Order

    if not order.partner:
        return

    # 이미 수수료 내역이 있으면 → PENDING이면 정산 처리, SETTLED면 스킵
    existing = CommissionRecord.objects.filter(order=order).first()
    if existing:
        if existing.status == 'PENDING':
            with transaction.atomic():
                existing.status = 'SETTLED'
                existing.settled_date = date.today()
                existing.save(update_fields=['status', 'settled_date', 'updated_at'])
                _auto_create_commission_disbursement(existing)
                logger.info(
                    'Settled existing CommissionRecord pk=%s for order %s',
                    existing.pk, order.order_number,
                )
        return

    # 주문 항목별 수수료 계산 — base_type에 따라 공급가액 or 판매가 기준
    module = _get_partner_module(order.partner)
    if module:
        total_commission = int(module.calculate_commission(order, order.partner))
    else:
        total_commission = 0
        for item in order.items.filter(is_active=True):
            supply = int(item.amount) if item.amount else 0
            total_with_tax = supply + (int(item.tax_amount) if item.tax_amount else 0)
            total_commission += order.partner.calculate_commission(
                supply, total_amount=total_with_tax, product=item.product,
            )

    if total_commission <= 0:
        return

    order_amount = int(order.total_amount)

    with transaction.atomic():
        record = CommissionRecord.objects.create(
            partner=order.partner,
            order=order,
            order_amount=order_amount,
            commission_rate=0,
            commission_amount=total_commission,
            status='SETTLED',
            settled_date=date.today(),
            created_by=order.created_by,
        )

        # 주문에 플랫폼 수수료 기록
        Order.objects.filter(pk=order.pk).update(
            platform_commission=total_commission,
        )

        # 수수료 출금(DISBURSEMENT) 자동 생성
        _auto_create_commission_disbursement(record)

        logger.info(
            'Auto-created CommissionRecord for order %s: %s원 (SETTLED + DISBURSEMENT)',
            order.order_number, total_commission,
        )


def _auto_create_commission_disbursement(record):
    """수수료 출금(DISBURSEMENT) Payment + 복식부기 전표 자동 생성"""
    from apps.accounting.models import (
        AccountCode, BankAccount, Payment, Voucher, VoucherLine,
    )

    amount = int(record.commission_amount)
    if amount <= 0:
        return

    if Payment.objects.filter(
        reference__contains=f'수수료 {record.pk}',
        payment_type='DISBURSEMENT',
    ).exists():
        return

    # 모듈이 있으면 정산 계좌를 모듈에서 결정, 없으면 기존 로직
    module = _get_partner_module(record.partner) if record.partner else None
    if module:
        bank = module.get_settlement_bank_account(record.order, record.partner)
    else:
        bank = None
        if record.order and record.order.bank_account:
            bank = record.order.bank_account
        if not bank:
            bank = BankAccount.objects.filter(
                is_active=True, is_default=True,
            ).first()
    if not bank:
        logger.warning('출금계좌 미설정 — 수수료 %s 출금 불가', record.pk)
        return

    acct_commission = AccountCode.objects.filter(
        code='502', is_active=True,
    ).first()
    acct_bank = bank.account_code

    voucher = Voucher.objects.create(
        voucher_type='PAYMENT',
        voucher_date=date.today(),
        description=(
            f'수수료 정산 - {record.partner.name} '
            f'({record.order.order_number if record.order else ""})'
        ),
        approval_status='APPROVED',
        created_by=record.created_by,
    )

    if acct_commission:
        VoucherLine.objects.create(
            voucher=voucher, account=acct_commission,
            debit=amount, credit=0,
            description=f'{record.partner.name} 수수료',
            created_by=record.created_by,
        )
    if acct_bank:
        VoucherLine.objects.create(
            voucher=voucher, account=acct_bank,
            debit=0, credit=amount,
            description=f'{record.partner.name} 수수료 출금 ({bank.name})',
            created_by=record.created_by,
        )

    Payment.objects.create(
        payment_type='DISBURSEMENT',
        partner=record.partner,
        bank_account=bank,
        voucher=voucher,
        amount=amount,
        payment_date=date.today(),
        payment_method='BANK_TRANSFER',
        reference=f'주문 {record.order.order_number} 수수료',
        created_by=record.created_by,
    )


def _check_credit_limit(order):
    """주문 확정 시 신용한도 초과 경고 (차단하지 않음, 알림만 생성)"""
    if not order.partner:
        return
    partner = order.partner
    if partner.credit_limit <= 0:
        return
    total = int(order.grand_total) if order.grand_total else 0
    if partner.credit_used + total > partner.credit_limit:
        from apps.core.notification import create_notification
        over = partner.credit_used + total - partner.credit_limit
        create_notification(
            'manager',
            f'[신용한도 초과] {partner.name}',
            f'주문 {order.order_number} 확정 시 신용한도를 {over:,}원 초과합니다. '
            f'(한도: {int(partner.credit_limit):,}원, '
            f'사용중: {int(partner.credit_used):,}원, '
            f'주문금액: {total:,}원)',
            noti_type='SYSTEM',
        )
        logger.warning(
            'Credit limit exceeded for partner %s on order %s: over %s',
            partner.name, order.order_number, over,
        )


def _auto_create_ar(order):
    """주문 확정 시 매출채권(AR) 자동 생성"""
    from apps.accounting.models import AccountReceivable
    from apps.accounting.utils import validate_closing_period

    if not order.partner:
        return

    grand_total = int(order.grand_total) if order.grand_total else 0
    if grand_total <= 0:
        return

    # 이미 AR이 있으면 스킵
    if AccountReceivable.objects.filter(order=order, is_active=True).exists():
        return

    # 마감기간 검증 — 마감된 월이면 silent skip + 알림
    if not validate_closing_period(
        order.order_date,
        raise_exception=False,
        notify_user=order.created_by,
        context=f'주문 {order.order_number} AR 자동생성',
    ):
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
    """주문 확정 시 매출 세금계산서 자동 생성.

    - 면세/영세율 주문은 tax_type을 승계해 생성 (세무신고 분류용).
    - sales_channel이 PlatformFinancialConfig에서 tax_invoice_issuer='PLATFORM' 설정인 경우
      플랫폼이 이미 발행했으므로 자동생성을 skip하고 담당자에게 알림만 발송한다.
    """
    from apps.accounting.models import TaxInvoice
    from apps.accounting.models_platform import PlatformFinancialConfig
    from apps.accounting.utils import validate_closing_period

    if not order.partner:
        return

    supply_amount = int(order.total_amount) if order.total_amount else 0
    tax_amount = int(order.tax_total) if order.tax_total else 0
    if supply_amount <= 0:
        return

    # 이미 세금계산서가 있으면 스킵
    if TaxInvoice.objects.filter(order=order, is_active=True).exists():
        return

    # 마감기간 검증 — 마감된 월이면 silent skip + 알림
    if not validate_closing_period(
        order.order_date,
        raise_exception=False,
        notify_user=order.created_by,
        context=f'주문 {order.order_number} 매출 세금계산서',
    ):
        return

    order_tax_type = getattr(order, 'tax_type', TaxInvoice.TaxType.TAXABLE)
    issuer_type = TaxInvoice.IssuerType.SELF
    platform_name = ''

    channel = getattr(order, 'sales_channel', '')
    config = None
    if channel:
        config = PlatformFinancialConfig.objects.filter(
            code=channel, is_enabled=True, is_active=True,
        ).first()

    if config and config.tax_invoice_issuer == PlatformFinancialConfig.IssuerType.PLATFORM:
        # 플랫폼 대행 발행 채널 — 자사 자동생성 skip + 알림
        try:
            from apps.core.notification import Notification
            if order.created_by_id:
                Notification.objects.create(
                    user_id=order.created_by_id,
                    title=f'[세금계산서 자동생성 skip] {order.order_number}',
                    message=(
                        f'주문 {order.order_number}: {config.name} 채널은 '
                        f'세금계산서를 플랫폼이 대행 발행하도록 설정되어 자사 자동발행을 건너뛰었습니다.'
                    ),
                    noti_type=Notification.NotiType.SYSTEM,
                )
        except Exception:
            logger.warning(
                'TaxInvoice skip 알림 발송 실패 (order=%s)', order.order_number,
                exc_info=True,
            )
        logger.info(
            'Skipped TaxInvoice auto-creation for order %s (platform=%s)',
            order.order_number, config.code,
        )
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
            tax_type=order_tax_type,
            issuer_type=issuer_type,
            platform_name=platform_name,
            description=f'주문 {order.order_number} 매출 세금계산서',
            created_by=order.created_by,
        )
        logger.info(
            'Auto-created TaxInvoice %s for order %s (tax_type=%s, issuer=%s)',
            inv.invoice_number, order.order_number, order_tax_type, issuer_type,
        )


def _auto_create_return_stock_in(order):
    """반품주문 확정 시 원본 주문의 출고 아이템 기준 IN(반품입고) StockMovement 생성

    T10 — 원본 OrderItem.actual_cogs 를 반품 수량 비율에 비례해 F() 차감한다.
    차감액 = original_item.actual_cogs × return_qty / original_item.quantity
    """
    if not order.original_order:
        logger.warning('반품주문 %s: 원본주문 미지정 — 반품입고 스킵', order.order_number)
        return

    from apps.sales.models import OrderItem as _OI

    with transaction.atomic():
        for item in order.items.select_related('product').all():
            if not item.product.is_stockable:
                continue
            warehouse = _get_product_warehouse(item.product_id)
            if not warehouse:
                warehouse = Warehouse.get_default()
            if not warehouse:
                logger.error('No warehouse — cannot create return stock in for %s', order.order_number)
                continue
            StockMovement.objects.create(
                movement_number=f'IN-RTN-{order.order_number}-{item.pk}',
                movement_type='IN',
                product=item.product,
                warehouse=warehouse,
                quantity=item.quantity,
                unit_price=item.unit_price,
                movement_date=date.today(),
                reference=f'반품입고 {order.order_number} (원본: {order.original_order.order_number})',
                created_by=order.created_by,
            )

            # T10 — 원본 주문 내 동일 product OrderItem 의 actual_cogs 비례 차감
            _reverse_original_actual_cogs(
                order.original_order, item.product_id, item.quantity,
                reason=f'반품 {order.order_number}',
            )
        logger.info('Auto-created return stock IN for order %s', order.order_number)


def _reverse_original_actual_cogs(original_order, product_id, return_qty, *, reason=''):
    """원본 주문의 동일 product OrderItem 에서 actual_cogs 를 비례 차감(F()).

    반품/교환 공통 헬퍼. 원본 수량 기준으로 비례 배분하며,
    반품수량이 원본수량을 초과하면 원본 전액 차감.
    """
    from apps.sales.models import OrderItem as _OI
    from decimal import Decimal

    orig_item = (
        _OI.objects.filter(
            order=original_order,
            product_id=product_id,
            is_active=True,
        )
        .order_by('pk')
        .first()
    )
    if not orig_item:
        logger.warning(
            'Original OrderItem not found for product=%s in order=%s — '
            'actual_cogs reversal skipped (%s)',
            product_id, original_order.order_number, reason,
        )
        return

    if not orig_item.actual_cogs or orig_item.quantity <= 0:
        return

    ratio_qty = min(int(return_qty), int(orig_item.quantity))
    reverse_amount = (
        Decimal(orig_item.actual_cogs)
        * Decimal(ratio_qty)
        / Decimal(orig_item.quantity)
    ).quantize(Decimal('1'))

    if reverse_amount <= 0:
        return

    _OI.objects.filter(pk=orig_item.pk).update(
        actual_cogs=F('actual_cogs') - reverse_amount,
    )
    logger.info(
        'Reversed actual_cogs -%s on original OrderItem pk=%s (qty %s/%s) [%s]',
        reverse_amount, orig_item.pk, ratio_qty, orig_item.quantity, reason,
    )


def _auto_reverse_ar(order):
    """반품주문 확정 시 원본 주문의 AR 역전표(환불) 생성"""
    from apps.accounting.models import AccountReceivable
    from apps.accounting.utils import validate_closing_period

    original = order.original_order
    if not original or not original.partner:
        return

    grand_total = int(order.grand_total) if order.grand_total else 0
    if grand_total <= 0:
        return

    # 이미 역전표가 있으면 스킵
    if AccountReceivable.objects.filter(order=order, is_active=True).exists():
        return

    # 마감기간 검증 — 환불 AR 생성 시점 (order_date) 기준
    if not validate_closing_period(
        order.order_date,
        raise_exception=False,
        notify_user=order.created_by,
        context=f'반품주문 {order.order_number} AR 역전표',
    ):
        return

    with transaction.atomic():
        ar = AccountReceivable.objects.create(
            partner=original.partner,
            order=order,
            amount=-grand_total,
            due_date=date.today() + timedelta(days=30),
            status='PENDING',
            created_by=order.created_by,
        )
        logger.info(
            'Auto-created reverse AR for return order %s: -%s원',
            order.order_number, grand_total,
        )


def _auto_cancel_tax_invoice_for_return(order):
    """반품/교환 주문 확정 시 원본 주문의 세금계산서를 soft delete"""
    from apps.accounting.models import TaxInvoice

    original = order.original_order
    if not original:
        return

    with transaction.atomic():
        invoices = TaxInvoice.objects.filter(order=original, is_active=True)
        for inv in invoices:
            inv.is_active = False
            inv.save(update_fields=['is_active', 'updated_at'])
            logger.info(
                'Auto-cancelled TaxInvoice %s for return/exchange order %s',
                inv.invoice_number, order.order_number,
            )


def _auto_create_exchange_stock_movements(order):
    """교환주문 확정 시 원본품 반품입고(IN) + 교환품 출고(OUT) StockMovement 생성

    T10 — 원본 OrderItem.actual_cogs 를 반품수량 비율만큼 차감하고,
    교환 OUT StockMovement.cogs_amount 를 교환 OrderItem.actual_cogs 에 F() 누적.
    """
    original = order.original_order
    if not original:
        logger.warning('교환주문 %s: 원본주문 미지정 — 교환 재고처리 스킵', order.order_number)
        return

    from apps.sales.models import OrderItem as _OI

    with transaction.atomic():
        # 원본 주문의 아이템: 반품입고(IN) + 원본 actual_cogs 비례 차감
        for item in original.items.select_related('product').all():
            if not item.product.is_stockable:
                continue
            warehouse = _get_product_warehouse(item.product_id)
            if not warehouse:
                warehouse = Warehouse.get_default()
            if not warehouse:
                continue
            StockMovement.objects.create(
                movement_number=f'IN-EXC-{order.order_number}-ORIG-{item.pk}',
                movement_type='IN',
                product=item.product,
                warehouse=warehouse,
                quantity=item.quantity,
                unit_price=item.unit_price,
                movement_date=date.today(),
                reference=f'교환반품입고 {order.order_number} (원본: {original.order_number})',
                created_by=order.created_by,
            )
            _reverse_original_actual_cogs(
                original, item.product_id, item.quantity,
                reason=f'교환 {order.order_number}',
            )

        # 교환 주문의 아이템: 교환출고(OUT) + 교환 actual_cogs 누적
        for item in order.items.select_related('product').all():
            if not item.product.is_stockable:
                continue
            warehouse = _get_product_warehouse(item.product_id)
            if not warehouse:
                warehouse = Warehouse.get_default()
            if not warehouse:
                continue
            movement = StockMovement.objects.create(
                movement_number=f'OUT-EXC-{order.order_number}-{item.pk}',
                movement_type='OUT',
                product=item.product,
                warehouse=warehouse,
                quantity=item.quantity,
                unit_price=item.unit_price,
                movement_date=date.today(),
                reference=f'교환출고 {order.order_number}',
                created_by=order.created_by,
            )
            # T10 — inventory signals 가 cogs_amount 를 F() update 해두므로 refresh.
            movement.refresh_from_db(fields=['cogs_amount'])
            if movement.cogs_amount:
                _OI.objects.filter(pk=item.pk).update(
                    actual_cogs=F('actual_cogs') + movement.cogs_amount,
                )
        logger.info('Auto-created exchange stock movements for order %s', order.order_number)


def _auto_exchange_ar_diff(order):
    """교환주문 확정 시 원본과의 AR 차액 처리"""
    from apps.accounting.models import AccountReceivable
    from apps.accounting.utils import validate_closing_period

    original = order.original_order
    if not original or not original.partner:
        return

    orig_total = int(original.grand_total) if original.grand_total else 0
    new_total = int(order.grand_total) if order.grand_total else 0
    diff = new_total - orig_total

    if diff == 0:
        return

    # 이미 AR이 있으면 스킵
    if AccountReceivable.objects.filter(order=order, is_active=True).exists():
        return

    # 마감기간 검증
    if not validate_closing_period(
        order.order_date,
        raise_exception=False,
        notify_user=order.created_by,
        context=f'교환주문 {order.order_number} AR 차액',
    ):
        return

    with transaction.atomic():
        AccountReceivable.objects.create(
            partner=original.partner,
            order=order,
            amount=diff,
            due_date=date.today() + timedelta(days=30),
            status='PENDING',
            created_by=order.created_by,
        )
        logger.info(
            'Auto-created exchange AR diff for order %s: %s원',
            order.order_number, diff,
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
                payments = ar.payments.filter(is_active=True)
                for payment in payments:
                    payment._skip_balance_restore = True
                    payment.soft_delete()
                    logger.info(
                        'Auto-cancelled Payment %s for order %s',
                        payment.payment_number, order.order_number,
                    )
                ar.paid_amount = 0
                ar.status = AccountReceivable.Status.PENDING
                ar.save(update_fields=['paid_amount', 'status', 'updated_at'])
            ar.soft_delete()
            logger.info('Auto-cancelled AR pk=%s for order %s', ar.pk, order.order_number)

        # 2. 수수료 취소 (SETTLED 포함 — 관련 Payment DISBURSEMENT도 함께 soft delete)
        from apps.accounting.models import BankAccount, Payment
        from django.db.models import Q
        commissions = CommissionRecord.objects.filter(order=order, is_active=True)
        for comm in commissions:
            if comm.status == 'SETTLED':
                # 정산완료 수수료 → 관련 DISBURSEMENT Payment soft delete + 계좌잔액 복원
                disbursements = Payment.objects.filter(
                    partner=comm.partner,
                    payment_type='DISBURSEMENT',
                    is_active=True,
                    amount=comm.commission_amount,
                ).filter(
                    Q(reference__contains=f'주문 {order.order_number} 수수료')
                    | Q(reference__contains=f'수수료 {comm.pk}'),
                )
                for pmt in disbursements:
                    # 계좌 잔액 복원 (출금 취소이므로 잔액 증가)
                    if pmt.bank_account:
                        BankAccount.objects.filter(pk=pmt.bank_account_id).update(
                            balance=F('balance') + pmt.amount,
                        )
                    pmt._skip_balance_restore = True
                    pmt.soft_delete()
                    logger.info(
                        'Auto-cancelled DISBURSEMENT Payment %s for commission %s',
                        pmt.payment_number, comm.pk,
                    )
            comm.is_active = False
            comm.save(update_fields=['is_active', 'updated_at'])
            logger.info('Auto-cancelled CommissionRecord pk=%s for order %s', comm.pk, order.order_number)

        # 2-1. 예약재고 해제 (확정 이후 취소 시)
        if old_status in ('CONFIRMED', 'PARTIAL_SHIPPED'):
            for item in order.items.select_related('product').all():
                if not item.product.is_stockable:
                    continue
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
        # 방어적 코드: SHIPPED/DELIVERED→CANCELLED는 STATUS_TRANSITIONS에서 도달 불가하나,
        # 관리자 직접 수정 등 예외 상황 대비. 삭제 금지.
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

        # 3-1. shipped_quantity 초기화 (방어적 코드 — SHIPPED/DELIVERED 포함)
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


def _check_order_shipment_status(order):
    """주문의 출고수량을 집계하여 PARTIAL_SHIPPED / SHIPPED 자동 전환.

    시그널 루프 방지를 위해 Order.objects.filter().update() 사용.
    """
    from apps.sales.models import Order

    all_items = order.items.filter(is_active=True)
    total_ordered = sum(i.quantity for i in all_items)
    total_shipped = sum(i.shipped_quantity for i in all_items)

    if total_ordered <= 0:
        return

    if total_shipped >= total_ordered:
        new_status = Order.Status.SHIPPED
    elif total_shipped > 0:
        new_status = Order.Status.PARTIAL_SHIPPED
    else:
        return

    if order.status != new_status:
        Order.objects.filter(pk=order.pk).update(status=new_status)


@receiver(post_save, sender='sales.ShipmentItem')
def auto_stock_on_shipment_item(sender, instance, created, **kwargs):
    """배송항목 생성 시 부분 출고 처리"""
    if not created:
        return

    shipment = instance.shipment
    order = shipment.order
    order_item = instance.order_item
    warehouse = _get_product_warehouse(order_item.product_id)
    if not warehouse:
        logger.error('No warehouse — cannot create partial shipment')
        return

    with transaction.atomic():
        product = Product.all_objects.get(pk=order_item.product_id)

        if product.is_stockable:
            # 재고 부족 체크
            if product.current_stock < instance.quantity:
                raise InsufficientStockError(
                    f'재고 부족: {product.name} '
                    f'(현재 {product.current_stock}, '
                    f'필요 {instance.quantity})'
                )

            # OUT 재고이동 생성
            movement = StockMovement.objects.create(
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

            # T10 — StockLot 소진 기반 실제매출원가를 OrderItem.actual_cogs 누적.
            # inventory.signals._consume_lots_on_outbound 가 동기 post_save 체인에서
            # StockMovement.cogs_amount 를 F() update 해두므로 refresh 후 누적.
            movement.refresh_from_db(fields=['cogs_amount'])
            if movement.cogs_amount:
                from apps.sales.models import OrderItem
                OrderItem.objects.filter(pk=order_item.pk).update(
                    actual_cogs=F('actual_cogs') + movement.cogs_amount,
                )

            # 예약재고 해제 (출고된 수량만큼, 예약 없으면 스킵)
            prod = Product.objects.get(pk=order_item.product_id)
            actual_release = min(instance.quantity, prod.reserved_stock)
            if actual_release > 0:
                Product.objects.filter(pk=order_item.product_id).update(
                    reserved_stock=F('reserved_stock') - actual_release,
                )

        # OrderItem.shipped_quantity 갱신 (서비스 상품도 출고 수량 추적)
        from apps.sales.models import OrderItem
        OrderItem.objects.filter(pk=order_item.pk).update(
            shipped_quantity=F('shipped_quantity') + instance.quantity,
        )

        # 주문 상태 자동 전환 (시그널 루프 방지를 위해 .update() 사용)
        order_item.refresh_from_db()
        _check_order_shipment_status(order)

        # 시리얼 추적 제품: FIFO 순서로 시리얼 자동 할당
        if getattr(product, 'serial_tracking', False):
            _assign_serials_to_shipment_item(instance, product)

    logger.info(
        'Partial shipment: %s item %s qty=%s '
        '(shipped %s/%s)',
        order.order_number,
        order_item.product.code,
        instance.quantity,
        order_item.shipped_quantity,
        order_item.quantity,
    )


def _assign_serials_to_shipment_item(shipment_item, product):
    """시리얼 추적 제품의 ShipmentItem에 FIFO 순서로 시리얼 자동 할당

    IN_STOCK 상태의 시리얼을 created_at 오름차순(FIFO)으로 수량만큼 선택하여
    SHIPPED 상태로 변경하고, shipment_item / shipped_date를 설정한다.
    """
    from apps.inventory.models import SerialNumber

    available_serials = list(
        SerialNumber.objects.filter(
            product=product,
            status=SerialNumber.Status.IN_STOCK,
            is_active=True,
        ).order_by('created_at')[:shipment_item.quantity]
    )

    if not available_serials:
        logger.warning(
            'No IN_STOCK serials for product %s — serial assignment skipped',
            product.code,
        )
        return

    today = timezone.now().date()
    update_fields = ['status', 'shipped_date', 'updated_at']
    # shipment_item FK가 SerialNumber에 존재하면 함께 갱신
    has_shipment_item_fk = hasattr(SerialNumber, 'shipment_item')
    if has_shipment_item_fk:
        update_fields.append('shipment_item')

    for sn in available_serials:
        sn.status = SerialNumber.Status.SHIPPED
        sn.shipped_date = today
        if has_shipment_item_fk:
            sn.shipment_item = shipment_item
        sn.save(update_fields=update_fields)

    logger.info(
        'Assigned %d serials to ShipmentItem pk=%s (product %s, FIFO)',
        len(available_serials), shipment_item.pk, product.code,
    )


def _restore_serials_on_shipment_item_delete(shipment_item):
    """ShipmentItem soft delete 시 연결된 시리얼을 IN_STOCK으로 복원"""
    from apps.inventory.models import SerialNumber

    has_shipment_item_fk = hasattr(SerialNumber, 'shipment_item')
    if not has_shipment_item_fk:
        # shipment_item FK가 없으면 shipped_date + product 기준으로 역추적 불가 — 스킵
        logger.warning(
            'SerialNumber.shipment_item FK not found — '
            'cannot restore serials for ShipmentItem pk=%s',
            shipment_item.pk,
        )
        return

    linked_serials = SerialNumber.objects.filter(
        shipment_item=shipment_item,
        status=SerialNumber.Status.SHIPPED,
        is_active=True,
    )
    count = linked_serials.count()
    if count == 0:
        return

    for sn in linked_serials:
        sn.status = SerialNumber.Status.IN_STOCK
        sn.shipment_item = None
        sn.shipped_date = None
        sn.save(update_fields=['status', 'shipment_item', 'shipped_date', 'updated_at'])

    logger.info(
        'Restored %d serials to IN_STOCK (ShipmentItem pk=%s soft delete)',
        count, shipment_item.pk,
    )


@receiver(pre_save, sender='sales.ShipmentItem')
def restore_reserved_on_shipment_item_soft_delete(sender, instance, **kwargs):
    """ShipmentItem soft delete 시 예약재고 복원 + 시리얼 복원"""
    if not instance.pk:
        return
    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    # is_active True → False (soft delete) 시 예약재고 복원 + 시리얼 복원
    if old.is_active and not instance.is_active:
        order_item = instance.order_item
        if order_item.product.is_stockable:
            with transaction.atomic():
                Product.objects.filter(pk=order_item.product_id).update(
                    reserved_stock=F('reserved_stock') + instance.quantity,
                )
            logger.info(
                'Restored reserved_stock +%s for product %s (ShipmentItem soft delete)',
                instance.quantity, order_item.product.code,
            )
        # 시리얼 추적 제품: 연결된 시리얼 IN_STOCK 복원
        product = Product.all_objects.get(pk=order_item.product_id)
        if getattr(product, 'serial_tracking', False):
            _restore_serials_on_shipment_item_delete(instance)


def _try_close_order(order):
    """배송완료 + 입금완료 시 자동 종결 (history 보존을 위해 save() 사용)

    pre_save에서 호출 시: 인메모리 status 사용 (DB에 아직 미반영).
    외부(post-payment)에서 호출 시: refresh_from_db로 최신 상태 확인.
    """
    from apps.sales.models import Order
    # pre_save에서 호출 시 인메모리 status가 DELIVERED일 수 있음 (아직 DB 미반영)
    in_memory_status = order.status
    is_paid = Order.objects.filter(pk=order.pk).values_list(
        'is_paid', flat=True,
    ).first()
    if in_memory_status == 'DELIVERED' and is_paid:
        # DB 상태가 이미 CLOSED면 스킵
        db_status = Order.objects.filter(pk=order.pk).values_list(
            'status', flat=True,
        ).first()
        if db_status == 'CLOSED':
            return
        # history 보존을 위해 refresh + save (pre_save 밖에서만 DB 반영됨)
        fresh = Order.objects.get(pk=order.pk)
        fresh.status = 'CLOSED'
        fresh.save(update_fields=['status', 'updated_at'])
        logger.info('Order %s auto-closed (DELIVERED + paid)', order.order_number)


def _sync_shipments_delivered(order):
    """주문 배송완료 → 연결 Shipment도 배송완료 (history 보존을 위해 개별 save())"""
    from apps.sales.models import Shipment
    shipments = order.shipments.filter(
        is_active=True,
        status__in=['PREPARING', 'SHIPPED', 'IN_TRANSIT'],
    )
    count = 0
    for s in shipments:
        s.status = 'DELIVERED'
        s.delivered_date = date.today()
        s._skip_order_sync = True  # sync_order_on_shipment_delivered 무한루프 방지
        s.save(update_fields=['status', 'delivered_date', 'updated_at'])
        count += 1
    if count:
        logger.info('Synced %d shipments to DELIVERED for order %s', count, order.order_number)


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

    # order.is_paid는 Payment 생성과 같은 atomic 트랜잭션에서 설정됨
    # is_paid=True → 성공적 결제 존재, is_paid=False → 결제 없음 (확정)
    order.refresh_from_db(fields=['is_paid'])
    if order.is_paid:
        return

    # 이전 실패/불일치 Payment 정리 (금액 변경, 주문 수정 등으로 고아 상태)
    stale = Payment.objects.filter(
        reference=f'주문 {order.order_number}',
        payment_type='RECEIPT',
    )
    if stale.exists():
        for p in stale:
            p.soft_delete()
        logger.info('고아 Payment %d건 정리 — %s', stale.count(), order.order_number)

    # 주문에 설정된 계좌 우선, 없으면 기본계좌
    bank = order.bank_account
    if not bank:
        bank = BankAccount.objects.filter(
            is_active=True, is_default=True,
        ).first()
    if not bank:
        raise ValueError(
            '입금계좌가 설정되지 않았습니다. '
            '주문에 계좌를 지정하거나 기본 계좌를 설정해주세요.',
        )

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

    # 입금 처리 완료 → 수수료 자동 생성 + 종결 시도
    _auto_create_commission(order)
    _try_close_order(order)


@receiver(post_save, sender='sales.Partner')
def sync_partner_bank_account(sender, instance, **kwargs):
    """거래처 계좌정보 변경 시 회계 BankAccount 자동 생성/갱신"""
    if not instance.bank_name or not instance.bank_account:
        return

    try:
        from apps.accounting.models import BankAccount
    except ImportError:
        return

    with transaction.atomic():
        acct, created = BankAccount.objects.update_or_create(
            partner=instance,
            defaults={
                'name': f'{instance.name} 거래계좌',
                'account_type': BankAccount.AccountType.BUSINESS,
                'owner': instance.bank_holder or instance.name,
                'bank': instance.bank_name,
                'account_number': instance.bank_account,
                'is_active': instance.is_active,
            },
        )
        if created:
            logger.info('BankAccount created for partner %s', instance.code)


@receiver(pre_save, sender='sales.Shipment')
def sync_order_on_shipment_delivered(sender, instance, **kwargs):
    """배송 DELIVERED → 주문도 DELIVERED (모든 배송 완료 시)"""
    if not instance.pk:
        return
    # _sync_shipments_delivered에서 설정한 플래그 — 무한루프 방지
    if getattr(instance, '_skip_order_sync', False):
        return
    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.status != 'DELIVERED' and instance.status == 'DELIVERED':
        order = instance.order
        # 이 Shipment 제외 나머지 중 미완료 있는지 확인
        pending = order.shipments.filter(
            is_active=True,
        ).exclude(pk=instance.pk).exclude(status='DELIVERED').exists()
        if not pending and order.status in ('SHIPPED', 'PARTIAL_SHIPPED'):
            order.refresh_from_db()
            order.status = 'DELIVERED'
            order.save(update_fields=['status', 'updated_at'])
            logger.info(
                'All shipments delivered — order %s auto-set to DELIVERED',
                order.order_number,
            )


@receiver(pre_save, sender='sales.Shipment')
def auto_create_shipment_tracking(sender, instance, **kwargs):
    """배송 상태 변경 시 ShipmentTracking 자동 생성"""
    if not instance.pk:
        return
    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.status == instance.status:
        return

    from datetime import datetime
    from apps.sales.models import ShipmentTracking

    status_labels = dict(instance.Status.choices)
    ShipmentTracking.objects.create(
        shipment=instance,
        status=instance.get_status_display(),
        description=f'{status_labels.get(old.status, old.status)} → {status_labels.get(instance.status, instance.status)}',
        tracked_at=timezone.now(),
        created_by=instance.created_by,
    )
