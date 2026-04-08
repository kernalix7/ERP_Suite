import logging

from django.db import transaction
from django.db.models import F, Q, Sum
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import GoodsReceiptItem, GoodsReceipt, PurchaseOrder

from datetime import date, timedelta

logger = logging.getLogger(__name__)


@receiver(post_save, sender=GoodsReceiptItem)
def handle_goods_receipt(sender, instance, created, **kwargs):
    """입고항목 생성 시 재고 입고(StockMovement IN) 및 발주 상태 갱신"""
    if not created:
        return

    with transaction.atomic():
        po_item = instance.po_item
        goods_receipt = instance.goods_receipt
        po = goods_receipt.purchase_order

        # 1. StockMovement(IN) 자동 생성 (재고 추적 대상만)
        from apps.inventory.models import StockMovement, Warehouse

        product = po_item.product
        if product.is_stockable:
            warehouse = goods_receipt.warehouse or Warehouse.get_default()
            if not warehouse:
                logger.error(
                    'No warehouse configured — cannot create stock movement for %s',
                    instance,
                )
            else:
                # 고유한 movement_number 생성
                movement_number = f'GR-{goods_receipt.receipt_number}-{instance.pk}'
                StockMovement.objects.create(
                    movement_number=movement_number,
                    movement_type='IN',
                    product=product,
                    warehouse=warehouse,
                    quantity=instance.received_quantity,
                    unit_price=po_item.unit_price,
                    movement_date=goods_receipt.receipt_date,
                    reference=f'발주입고: {po.po_number}',
                    created_by=goods_receipt.created_by,
                )

        # 2. 이동평균 원가 갱신은 inventory signals의 _update_weighted_avg_cost에 일원화
        #    (StockMovement 생성 시 unit_price=po_item.unit_price로 전달됨)

        # 3. PurchaseOrderItem.received_quantity 갱신
        total_received = po_item.receipt_items.aggregate(
            total=Sum('received_quantity')
        )['total'] or 0
        po_item.received_quantity = total_received
        po_item.save(update_fields=['received_quantity', 'updated_at'])

        # 4. PurchaseOrder 상태 갱신
        all_items = po.items.all()
        fully_received = all(
            item.received_quantity >= item.quantity for item in all_items
        )
        partially_received = any(
            item.received_quantity > 0 for item in all_items
        )

        if fully_received:
            po.status = PurchaseOrder.Status.RECEIVED
        elif partially_received:
            po.status = PurchaseOrder.Status.PARTIAL_RECEIVED
        po.save(update_fields=['status', 'updated_at'])

        # 5. 전량 입고 시 매입채무(AP) + 매입 세금계산서 자동 생성
        if fully_received:
            _auto_create_ap(po)
            _auto_create_purchase_tax_invoice(po)

        # 6. 고정자산 등록 (자산 추적 대상만)
        if instance.is_fixed_asset and instance.asset_category:
            _auto_create_fixed_asset(instance, po_item, product, goods_receipt)


def _auto_create_fixed_asset(receipt_item, po_item, product, goods_receipt):
    """입고항목이 자산등록 대상인 경우 FixedAsset + 취득전표 자동 생성"""
    from apps.asset.models import FixedAsset
    from apps.core.utils import generate_document_number

    asset_number = generate_document_number(FixedAsset, 'asset_number', 'FA')
    cat = receipt_item.asset_category
    acquisition_cost = int(po_item.unit_price * receipt_item.received_quantity)

    FixedAsset.objects.create(
        asset_number=asset_number,
        name=product.name,
        category=cat,
        acquisition_date=goods_receipt.receipt_date,
        acquisition_cost=acquisition_cost,
        residual_value=0,
        useful_life_years=cat.useful_life_years,
        depreciation_method=cat.depreciation_method,
        book_value=acquisition_cost,
        source_receipt_item=receipt_item,
        created_by=goods_receipt.created_by,
    )

    # 취득 전표: 차변 150(유형자산), 대변 253(미지급금)
    from apps.accounting.models import AccountCode, Voucher, VoucherLine
    import uuid

    try:
        acct_asset = AccountCode.objects.get(code='150', is_active=True)
        acct_payable = AccountCode.objects.get(code='253', is_active=True)
    except AccountCode.DoesNotExist:
        logger.warning('자산취득 전표 생성 실패: 계정과목 150 또는 253 없음')
        return

    voucher_number = f'V{goods_receipt.receipt_date.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
    voucher = Voucher.objects.create(
        voucher_number=voucher_number,
        voucher_type='TRANSFER',
        voucher_date=goods_receipt.receipt_date,
        description=f'자산취득: {product.name} ({asset_number})',
        approval_status='APPROVED',
        created_by=goods_receipt.created_by,
    )
    VoucherLine.objects.create(
        voucher=voucher, account=acct_asset,
        debit=acquisition_cost, credit=0,
        description=f'{product.name} 유형자산 취득',
        created_by=goods_receipt.created_by,
    )
    VoucherLine.objects.create(
        voucher=voucher, account=acct_payable,
        debit=0, credit=acquisition_cost,
        description=f'{product.name} 미지급금',
        created_by=goods_receipt.created_by,
    )
    logger.info(
        'Auto-created FixedAsset %s + voucher %s for GoodsReceiptItem %s',
        asset_number, voucher_number, receipt_item.pk,
    )


def _auto_create_ap(po):
    """발주 전량 입고 완료 시 매입채무(AP) 자동 생성"""
    from apps.accounting.models import AccountPayable

    if not po.partner:
        return

    grand_total = int(po.grand_total) if po.grand_total else 0
    if grand_total <= 0:
        return

    # 이미 AP가 있으면 스킵
    if AccountPayable.objects.filter(
        partner=po.partner,
        notes=f'발주 {po.po_number} 입고완료',
        is_active=True,
    ).exists():
        return

    due_date = po.expected_date or (date.today() + timedelta(days=30))

    AccountPayable.objects.create(
        partner=po.partner,
        amount=grand_total,
        due_date=due_date,
        status='PENDING',
        notes=f'발주 {po.po_number} 입고완료',
        created_by=po.created_by,
    )
    logger.info(
        'Auto-created AP for PO %s: %s원 (납기: %s)',
        po.po_number, grand_total, due_date,
    )


def _auto_create_purchase_tax_invoice(po):
    """발주 전량 입고 완료 시 매입 세금계산서 자동 생성"""
    from apps.accounting.models import TaxInvoice

    if not po.partner:
        return

    # 면세 거래는 세금계산서 생성하지 않음
    if not po.is_taxable:
        return

    supply_amount = int(po.total_amount) if po.total_amount else 0
    tax_amount = int(po.tax_total) if po.tax_total else 0
    if supply_amount <= 0:
        return

    # 이미 세금계산서가 있으면 스킵
    if TaxInvoice.objects.filter(
        partner=po.partner,
        description=f'발주 {po.po_number} 매입 세금계산서',
        invoice_type='PURCHASE',
        is_active=True,
    ).exists():
        return

    TaxInvoice.objects.create(
        invoice_type='PURCHASE',
        partner=po.partner,
        issue_date=date.today(),
        supply_amount=supply_amount,
        tax_amount=tax_amount,
        total_amount=supply_amount + tax_amount,
        description=f'발주 {po.po_number} 매입 세금계산서',
        created_by=po.created_by,
    )
    logger.info(
        'Auto-created purchase TaxInvoice for PO %s',
        po.po_number,
    )


@receiver(pre_save, sender=PurchaseOrder)
def handle_po_cancellation(sender, instance, **kwargs):
    """발주 취소 시 역방향 연쇄 처리:
    - 이미 입고된 건이 있으면 취소 불가 (ValidationError)
    - 관련 AP soft delete
    - 관련 매입 세금계산서 soft delete
    """
    if not instance.pk:
        return

    try:
        old = PurchaseOrder.objects.get(pk=instance.pk)
    except PurchaseOrder.DoesNotExist:
        return

    # CANCELLED로 전환되는 경우만 처리
    if old.status == instance.status or instance.status != 'CANCELLED':
        return

    # 1. 이미 입고된 건이 있는지 확인
    has_receipts = GoodsReceipt.objects.filter(
        purchase_order=instance,
        is_active=True,
    ).exists()
    if has_receipts:
        # 입고된 항목 중 실제 수량이 있는 것만 확인
        from .models import GoodsReceiptItem as GRI
        has_received_items = GRI.objects.filter(
            goods_receipt__purchase_order=instance,
            goods_receipt__is_active=True,
            received_quantity__gt=0,
        ).exists()
        if has_received_items:
            logger.warning(
                'PO %s: 입고 존재 — 취소 차단, 상태 복원',
                instance.po_number,
            )
            instance.status = old.status
            return

    with transaction.atomic():
        # 2. 관련 AP soft delete
        from apps.accounting.models import AccountPayable
        cancelled_ap = AccountPayable.objects.filter(
            partner=instance.partner,
            notes=f'발주 {instance.po_number} 입고완료',
            is_active=True,
        ).update(is_active=False)
        if cancelled_ap:
            logger.info(
                'Soft-deleted %d AP(s) for cancelled PO %s',
                cancelled_ap, instance.po_number,
            )

        # 3. 관련 매입 세금계산서 soft delete
        from apps.accounting.models import TaxInvoice
        cancelled_invoices = TaxInvoice.objects.filter(
            partner=instance.partner,
            invoice_type='PURCHASE',
            description=f'발주 {instance.po_number} 매입 세금계산서',
            is_active=True,
        ).update(is_active=False)
        if cancelled_invoices:
            logger.info(
                'Soft-deleted %d purchase TaxInvoice(s) for cancelled PO %s',
                cancelled_invoices, instance.po_number,
            )


@receiver(pre_save, sender=GoodsReceiptItem)
def cascade_receipt_item_soft_delete(sender, instance, **kwargs):
    """입고항목 soft delete 시 연결된 StockMovement soft delete + PO received_quantity 차감"""
    if not instance.pk:
        return
    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.is_active and not instance.is_active:
        with transaction.atomic():
            from apps.inventory.models import StockMovement

            goods_receipt = instance.goods_receipt
            # 재고 추적 대상만 StockMovement soft delete
            product = instance.po_item.product
            if product.is_stockable:
                # 개별 save()로 inventory pre_save 시그널(재고 복원) 발동
                # movement_number로 정확히 매칭 (동일 PO/제품 분할입고 시 다른 item 보호)
                movements = StockMovement.objects.filter(
                    movement_number=f'GR-{goods_receipt.receipt_number}-{instance.pk}',
                    is_active=True,
                )
                for mv in movements:
                    mv.is_active = False
                    mv.save(update_fields=['is_active', 'updated_at'])

            # PO received_quantity 차감 (F() + update로 simple_history INSERT 에러 방지)
            from apps.purchase.models import PurchaseOrderItem
            PurchaseOrderItem.objects.filter(
                purchase_order=goods_receipt.purchase_order,
                product=instance.po_item.product,
                is_active=True,
            ).update(received_quantity=F('received_quantity') - instance.received_quantity)
