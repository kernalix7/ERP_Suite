import logging
import uuid

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import (
    AccountCode, AccountPayable, AccountReceivable, AccountTransfer,
    BankAccount, CardTransaction, CashReceiptItem, CreditCard, Payment,
    PaymentDistribution, SalesSettlement, Voucher, VoucherLine,
)

logger = logging.getLogger(__name__)


def _get_account_code(code):
    """계정과목 코드로 AccountCode 조회 (없으면 None)"""
    try:
        return AccountCode.objects.get(code=code, is_active=True)
    except AccountCode.DoesNotExist:
        logger.warning('AccountCode %s not found — skipping voucher line', code)
        return None


def _generate_voucher_number():
    """전표번호 자동 생성"""
    from django.utils import timezone
    prefix = timezone.now().strftime('V%Y%m%d')
    suffix = uuid.uuid4().hex[:6].upper()
    return f'{prefix}-{suffix}'


def _validate_closing_period(target_date):
    """마감된 월이면 ValidationError 발생, 아니면 원본 반환

    공통 유틸 `apps.accounting.utils.validate_closing_period` 위임.
    """
    from apps.accounting.utils import validate_closing_period
    validate_closing_period(target_date, raise_exception=True, context='전표 생성')
    return target_date


@receiver(pre_save, sender=Voucher)
def voucher_block_on_closed_period(sender, instance, **kwargs):
    """수동 전표 생성/수정이 마감된 월이면 ValidationError로 차단.

    자동전표(다른 시그널에서 `validate_closing_period(raise_exception=False)` 로 skip 처리)
    는 이미 함수 내부에서 막히므로 여기까지 오지 않는다. 사용자가 수동으로
    `Voucher.objects.create(voucher_date=...)` 한 경우에만 블록된다.
    """
    from apps.accounting.utils import validate_closing_period
    validate_closing_period(
        instance.voucher_date,
        raise_exception=True,
        context=f'Voucher {instance.voucher_number or "(신규)"} 수동 생성',
    )


@receiver(post_save, sender=VoucherLine)
def voucher_apply_approval_policy(sender, instance, created, **kwargs):
    """전표 라인 추가/변경 시 VoucherApprovalConfig 정책 적용 (GAP-8.1).

    - 자동전표 정책 `auto_voucher_default_status` ≠ APPROVED 이면 강제 다운그레이드
    - 합계 금액이 `auto_approval_amount_threshold` 초과 시 자동전표도 SUBMITTED 강제
    - 수동 전표(approval_status=DRAFT)에서 라인 합계가 manual threshold 초과 시
      ApprovalRequest 자동 생성 (이미 있으면 skip)
    """
    if not created:
        return
    from .models import VoucherApprovalConfig
    voucher = instance.voucher
    if not voucher or not voucher.is_active:
        return
    config = VoucherApprovalConfig.get_active()

    total_debit = voucher.total_debit
    auto_threshold = int(config.auto_approval_amount_threshold or 0)

    # 자동전표 (APPROVED 로 생성됐을 때) 다운그레이드 정책 적용
    if voucher.approval_status == Voucher.ApprovalStatus.APPROVED:
        target = config.auto_voucher_default_status
        downgrade = False
        if target != Voucher.ApprovalStatus.APPROVED:
            voucher.approval_status = target
            downgrade = True
        if auto_threshold and int(total_debit) > auto_threshold:
            voucher.approval_status = Voucher.ApprovalStatus.SUBMITTED
            downgrade = True
        if downgrade:
            Voucher.objects.filter(pk=voucher.pk).update(
                approval_status=voucher.approval_status,
            )

    # 수동전표(DRAFT) — 한도 초과시 ApprovalRequest 자동생성
    manual_threshold = int(config.manual_approval_amount_threshold or 0)
    if (
        voucher.approval_status == Voucher.ApprovalStatus.DRAFT
        and manual_threshold and int(total_debit) > manual_threshold
    ):
        try:
            from apps.approval.models import ApprovalRequest
            if not ApprovalRequest.objects.filter(
                content_type__model='voucher',
                object_id=voucher.pk,
                is_active=True,
            ).exists():
                from django.contrib.contenttypes.models import ContentType
                ApprovalRequest.objects.create(
                    title=f'전표 결재요청 — {voucher.voucher_number} ({total_debit:,}원)',
                    category='ETC',
                    content_type=ContentType.objects.get_for_model(Voucher),
                    object_id=voucher.pk,
                    requester=voucher.created_by,
                    status='PENDING',
                )
        except Exception:
            logger.warning(
                'ApprovalRequest 자동생성 실패 (voucher=%s)',
                voucher.voucher_number, exc_info=True,
            )


def _get_expense_account(reference):
    """출금 reference에 따라 적절한 비용 계정과목 반환"""
    if reference and '수수료' in reference:
        acct = _get_account_code('521')  # 판매비
        if acct:
            return acct
    return _get_account_code('501')  # 매입원가 (기본)


@receiver(post_save, sender=Payment)
def payment_update_balance_and_voucher(sender, instance, created, **kwargs):
    """입출금 → 계좌잔액 원자적 갱신 + 자동전표 생성"""
    if not created:
        return
    if not instance.bank_account:
        return

    with transaction.atomic():
        # Distribution이 있는 Payment는 bank_account 잔액 갱신 스킵
        # (Distribution 시그널에서 각 분배 계좌별로 처리)
        if not instance.distributions.exists():
            if instance.payment_type == 'RECEIPT':
                BankAccount.objects.filter(pk=instance.bank_account_id).update(
                    balance=F('balance') + instance.amount,
                )
            elif instance.payment_type == 'DISBURSEMENT':
                BankAccount.objects.filter(pk=instance.bank_account_id).update(
                    balance=F('balance') - instance.amount,
                )

        # 자동전표 생성 — 복식부기 (차변+대변 2행 이상)
        acct = instance.bank_account
        acct.refresh_from_db()
        if acct.account_code and not instance.voucher:
            from apps.accounting.utils import validate_closing_period
            if not validate_closing_period(
                instance.payment_date,
                raise_exception=False,
                notify_user=instance.created_by,
                context=f'Payment {instance.payment_number} 자동전표',
            ):
                return
            voucher_date = instance.payment_date
            voucher = Voucher.objects.create(
                voucher_number=_generate_voucher_number(),
                voucher_type='RECEIPT' if instance.payment_type == 'RECEIPT' else 'PAYMENT',
                voucher_date=voucher_date,
                description=f'자동전표: {instance.payment_number} ({instance.get_payment_type_display()})',
                approval_status='APPROVED',
                created_by=instance.created_by,
            )

            # 상대 계정과목 조회
            if instance.payment_type == 'RECEIPT':
                counter_acct = _get_account_code('401')  # 매출
            else:
                counter_acct = _get_expense_account(instance.reference)

            if not counter_acct:
                logger.error(
                    'Counter account not found for payment %s — voucher deleted to prevent unbalanced entry',
                    instance.payment_number,
                )
                voucher.delete()
                return

            if instance.payment_type == 'RECEIPT':
                # 차변: 보통예금(은행계좌), 대변: 매출(401) 또는 미수금 관련
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=acct.account_code,
                    debit=instance.amount, credit=0,
                    description=f'{instance.partner} 입금 ({acct.name})',
                    created_by=instance.created_by,
                )
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=counter_acct,
                    debit=0, credit=instance.amount,
                    description=f'{instance.partner} 매출 입금',
                    created_by=instance.created_by,
                )
            else:
                # 차변: 매입/비용(501), 대변: 보통예금(은행계좌)
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=counter_acct,
                    debit=instance.amount, credit=0,
                    description=f'{instance.partner} 출금',
                    created_by=instance.created_by,
                )
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=acct.account_code,
                    debit=0, credit=instance.amount,
                    description=f'{instance.partner} 출금 ({acct.name})',
                    created_by=instance.created_by,
                )

            Payment.objects.filter(pk=instance.pk).update(voucher=voucher)


@receiver(post_save, sender=Payment)
def payment_recognize_exchange_gain_loss(sender, instance, created, **kwargs):
    """외화 결제 시 환차손익 자동전표 (GAP-9.2).

    조건:
    - Payment.receivable.order 가 외화 주문 (currency.code != 활성 국가 통화)
    - 주문 환율(order.exchange_rate) vs payment_date 의 ExchangeRate 차이 발생

    환차익(REVENUE 470) / 환차손(EXPENSE 925) 계정 분기.
    """
    if not created:
        return
    if not instance.receivable_id:
        return
    try:
        ar = instance.receivable
        order = getattr(ar, 'order', None)
        if not order or not getattr(order, 'currency_id', None):
            return
        currency = order.currency
        try:
            from apps.localizations import get_default_currency_code
            base_ccy = get_default_currency_code()
        except Exception:
            base_ccy = 'KRW'
        if currency.code == base_ccy:
            return
        order_rate = order.exchange_rate or 1
        from .models import ExchangeRate
        try:
            payment_rate_obj = (
                ExchangeRate.objects.filter(
                    currency=currency, rate_date__lte=instance.payment_date,
                )
                .order_by('-rate_date')
                .first()
            )
        except Exception:
            payment_rate_obj = None
        if not payment_rate_obj:
            return
        payment_rate = payment_rate_obj.rate
        if order_rate == payment_rate:
            return

        # 외화 결제 가정: payment.amount는 KRW 환산금액
        # 차이 = (payment_rate − order_rate) × 외화금액
        # 외화금액 ≈ payment.amount / payment_rate (KRW 역환산)
        from decimal import Decimal
        try:
            foreign_amount = (Decimal(instance.amount) / Decimal(payment_rate)).quantize(
                Decimal('0.01'),
            )
        except Exception:
            return
        diff = (Decimal(payment_rate) - Decimal(order_rate)) * foreign_amount
        diff_int = int(diff.quantize(Decimal('1')))
        if diff_int == 0:
            return

        from apps.accounting.utils import validate_closing_period
        if not validate_closing_period(
            instance.payment_date,
            raise_exception=False,
            notify_user=instance.created_by,
            context=f'Payment {instance.payment_number} 외환손익',
        ):
            return

        # 환차익(diff_int > 0, 입금이면 이득), 환차손(diff_int < 0)
        # RECEIPT + diff>0 → 외환차익, RECEIPT + diff<0 → 외환차손
        # DISBURSEMENT + diff>0 → 외환차손, DISBURSEMENT + diff<0 → 외환차익
        is_receipt = instance.payment_type == 'RECEIPT'
        is_gain = (diff_int > 0) if is_receipt else (diff_int < 0)
        # 외환차익/차손 계정코드 — 활성 국가 어댑터에 위임 (KR 기본 470/925).
        # 어댑터는 SystemConfig('TAX','fx_*_account_code') 오버라이드를 우선 적용한다.
        from apps.localizations import get_active_adapter
        try:
            tax_adp = get_active_adapter().tax
            gain_code = tax_adp.fx_gain_code()
            loss_code = tax_adp.fx_loss_code()
        except Exception:
            from apps.core.models import SystemConfig
            gain_code = SystemConfig.get_value('TAX', 'fx_gain_account_code', '470')
            loss_code = SystemConfig.get_value('TAX', 'fx_loss_account_code', '925')
        gain_acct = _get_account_code(gain_code)
        loss_acct = _get_account_code(loss_code)
        if not (gain_acct and loss_acct):
            logger.warning(
                '외환손익 계정과목(%s/%s) 없음 — Payment %s skip',
                gain_code, loss_code, instance.payment_number,
            )
            return

        from .models import VoucherApprovalConfig
        config = VoucherApprovalConfig.get_active()
        fx_voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='TRANSFER',
            voucher_date=instance.payment_date,
            description=(
                f'환차{"익" if is_gain else "손"}: {instance.payment_number} '
                f'({currency.code} {order_rate}→{payment_rate})'
            ),
            approval_status=config.auto_voucher_default_status,
            created_by=instance.created_by,
        )
        abs_amount = abs(diff_int)
        if is_gain:
            # 차변: 매출채권/예금, 대변: 외환차익(470)
            VoucherLine.objects.create(
                voucher=fx_voucher, account=instance.bank_account.account_code if instance.bank_account else gain_acct,
                debit=abs_amount, credit=0,
                description='환차익 인식',
                created_by=instance.created_by,
            )
            VoucherLine.objects.create(
                voucher=fx_voucher, account=gain_acct,
                debit=0, credit=abs_amount,
                description='외환차익(470)',
                created_by=instance.created_by,
            )
        else:
            VoucherLine.objects.create(
                voucher=fx_voucher, account=loss_acct,
                debit=abs_amount, credit=0,
                description='외환차손(925)',
                created_by=instance.created_by,
            )
            VoucherLine.objects.create(
                voucher=fx_voucher, account=instance.bank_account.account_code if instance.bank_account else loss_acct,
                debit=0, credit=abs_amount,
                description='환차손 인식',
                created_by=instance.created_by,
            )
    except Exception:
        logger.warning(
            '외환손익 자동전표 생성 실패 (payment=%s)',
            instance.payment_number, exc_info=True,
        )


@receiver(post_save, sender=AccountTransfer)
def transfer_update_balance_and_voucher(sender, instance, created, **kwargs):
    """계좌이체 → 양쪽 잔액 원자적 갱신 + 대체전표 생성"""
    if not created:
        return

    with transaction.atomic():
        BankAccount.objects.filter(pk=instance.from_account_id).update(
            balance=F('balance') - instance.amount,
        )
        BankAccount.objects.filter(pk=instance.to_account_id).update(
            balance=F('balance') + instance.amount,
        )

        # 양쪽 모두 계정과목이 있으면 대체전표 생성
        from_acct = instance.from_account
        to_acct = instance.to_account
        from_acct.refresh_from_db()
        to_acct.refresh_from_db()

        if from_acct.account_code and to_acct.account_code and not instance.voucher:
            from apps.accounting.utils import validate_closing_period
            if not validate_closing_period(
                instance.transfer_date,
                raise_exception=False,
                notify_user=instance.created_by,
                context=f'AccountTransfer {instance.transfer_number} 자동전표',
            ):
                return
            voucher_date = instance.transfer_date
            voucher = Voucher.objects.create(
                voucher_number=_generate_voucher_number(),
                voucher_type='TRANSFER',
                voucher_date=voucher_date,
                description=f'자동전표: 계좌이체 {from_acct.name} → {to_acct.name}',
                approval_status='APPROVED',
                created_by=instance.created_by,
            )
            VoucherLine.objects.create(
                voucher=voucher,
                account=to_acct.account_code,
                debit=instance.amount,
                credit=0,
                description=f'{to_acct.name} 입금',
                created_by=instance.created_by,
            )
            VoucherLine.objects.create(
                voucher=voucher,
                account=from_acct.account_code,
                debit=0,
                credit=instance.amount,
                description=f'{from_acct.name} 출금',
                created_by=instance.created_by,
            )
            AccountTransfer.objects.filter(pk=instance.pk).update(voucher=voucher)


@receiver(post_save, sender=PaymentDistribution)
def distribution_update_balance(sender, instance, created, **kwargs):
    """결제분배 → 대상계좌 잔액 갱신"""
    if not created:
        return

    payment = instance.payment
    with transaction.atomic():
        if payment.payment_type == 'RECEIPT':
            BankAccount.objects.filter(pk=instance.bank_account_id).update(
                balance=F('balance') + instance.amount,
            )
        elif payment.payment_type == 'DISBURSEMENT':
            BankAccount.objects.filter(pk=instance.bank_account_id).update(
                balance=F('balance') - instance.amount,
            )


@receiver(pre_save, sender=Payment)
def payment_soft_delete_restore_balance(sender, instance, **kwargs):
    """Payment soft delete (is_active True→False) 시 잔액 복원

    - AR/AP paid_amount 차감 + status 재계산
    - BankAccount 잔액 복원 (입금→차감, 출금→가산)
    - _skip_balance_restore 플래그로 중복 복원 방지
      (sales 시그널 등에서 수동 복원 후 플래그 설정 시 스킵)
    """
    if not instance.pk:
        return

    # _skip_balance_restore 플래그 확인
    if getattr(instance, '_skip_balance_restore', False):
        return

    try:
        old = Payment.objects.get(pk=instance.pk)
    except Payment.DoesNotExist:
        return

    # is_active True → False 전환만 처리
    if old.is_active and not instance.is_active:
        with transaction.atomic():
            # 1. AR paid_amount 복원 + status 재계산
            if old.receivable_id:
                AccountReceivable.objects.filter(pk=old.receivable_id).update(
                    paid_amount=F('paid_amount') - old.amount,
                )
                _recalculate_ar_status(old.receivable_id)

            # 2. AP paid_amount 복원 + status 재계산
            if old.payable_id:
                AccountPayable.objects.filter(pk=old.payable_id).update(
                    paid_amount=F('paid_amount') - old.amount,
                )
                _recalculate_ap_status(old.payable_id)

            # 3. BankAccount 잔액 복원
            if old.bank_account_id:
                if old.payment_type == 'RECEIPT':
                    # 입금 취소 → 잔액 차감
                    BankAccount.objects.filter(pk=old.bank_account_id).update(
                        balance=F('balance') - old.amount,
                    )
                elif old.payment_type == 'DISBURSEMENT':
                    # 출금 취소 → 잔액 가산
                    BankAccount.objects.filter(pk=old.bank_account_id).update(
                        balance=F('balance') + old.amount,
                    )

        logger.info(
            'Payment %s soft-deleted — restored AR/AP/bank balance (amount=%s)',
            old.payment_number, old.amount,
        )


def _recalculate_ar_status(ar_id):
    """AR의 paid_amount 기반 status 재계산"""
    ar = AccountReceivable.objects.get(pk=ar_id)
    if ar.paid_amount <= 0:
        new_status = 'PENDING'
    elif ar.paid_amount >= ar.amount:
        new_status = 'PAID'
    else:
        new_status = 'PARTIAL'
    if ar.status != new_status:
        AccountReceivable.objects.filter(pk=ar_id).update(status=new_status)


def _recalculate_ap_status(ap_id):
    """AP의 paid_amount 기반 status 재계산"""
    ap = AccountPayable.objects.get(pk=ap_id)
    if ap.paid_amount <= 0:
        new_status = 'PENDING'
    elif ap.paid_amount >= ap.amount:
        new_status = 'PAID'
    else:
        new_status = 'PARTIAL'
    if ap.status != new_status:
        AccountPayable.objects.filter(pk=ap_id).update(status=new_status)


# === 카드 거래 시그널 ===

# 카테고리별 비용 계정과목 코드 매핑
CARD_CATEGORY_ACCOUNT_MAP = {
    'PURCHASE': '501',       # 매입원가
    'TRAVEL': '524',         # 여비교통비
    'ENTERTAINMENT': '523',  # 접대비
    'SUPPLIES': '525',       # 사무용품비
    'FUEL': '526',           # 유류비
    'SUBSCRIPTION': '527',   # 정기구독비
    'OTHER': '529',          # 기타비용
}


def _get_card_expense_account(category):
    """카드 카테고리에 해당하는 비용 계정과목 반환"""
    code = CARD_CATEGORY_ACCOUNT_MAP.get(category, '529')
    acct = _get_account_code(code)
    if not acct and code != '529':
        acct = _get_account_code('529')  # fallback to 기타비용
    return acct


@receiver(post_save, sender=CardTransaction)
def card_transaction_voucher(sender, instance, created, **kwargs):
    """카드 거래 생성 → used_amount 원자적 증가 + 자동전표 생성"""
    if not created:
        return

    with transaction.atomic():
        # 1. CreditCard.used_amount F() 원자적 증가
        CreditCard.objects.filter(pk=instance.card_id).update(
            used_amount=F('used_amount') + instance.amount,
        )

        # 2. 자동전표 생성 (차변: 비용, 대변: 미지급금 253)
        expense_acct = _get_card_expense_account(instance.category)
        payable_acct = _get_account_code('253')  # 미지급금

        if not expense_acct or not payable_acct:
            logger.warning(
                'CardTransaction %s — missing account codes, skipping voucher',
                instance.pk,
            )
            return

        from apps.accounting.utils import validate_closing_period
        if not validate_closing_period(
            instance.transaction_date,
            raise_exception=False,
            notify_user=instance.created_by,
            context=f'CardTransaction {instance.pk} 자동전표',
        ):
            return
        voucher_date = instance.transaction_date
        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='PAYMENT',
            voucher_date=voucher_date,
            description=f'카드전표: {instance.card.name} {instance.merchant_name}',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=expense_acct,
            debit=instance.amount, credit=0,
            description=f'{instance.merchant_name} 카드결제',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=payable_acct,
            debit=0, credit=instance.amount,
            description=f'{instance.card.name} 미지급금',
            created_by=instance.created_by,
        )

        # 3. voucher FK 연결
        CardTransaction.objects.filter(pk=instance.pk).update(voucher=voucher)


@receiver(pre_save, sender=CardTransaction)
def card_transaction_cancel(sender, instance, **kwargs):
    """카드 거래 취소 (is_cancelled False→True) → used_amount 감소 + 역전표"""
    if not instance.pk:
        return

    try:
        old = CardTransaction.objects.get(pk=instance.pk)
    except CardTransaction.DoesNotExist:
        return

    # is_cancelled False → True 전환만 처리
    if old.is_cancelled or not instance.is_cancelled:
        return

    with transaction.atomic():
        # 1. CreditCard.used_amount F() 원자적 감소
        CreditCard.objects.filter(pk=instance.card_id).update(
            used_amount=F('used_amount') - old.amount,
        )

        # 2. 역전표 생성 (차변/대변 반대)
        expense_acct = _get_card_expense_account(old.category)
        payable_acct = _get_account_code('253')

        if not expense_acct or not payable_acct:
            logger.warning(
                'CardTransaction %s cancel — missing account codes, skipping reverse voucher',
                instance.pk,
            )
            return

        cancel_date = instance.cancelled_date or instance.transaction_date
        from apps.accounting.utils import validate_closing_period
        if not validate_closing_period(
            cancel_date,
            raise_exception=False,
            notify_user=instance.created_by,
            context=f'CardTransaction {instance.pk} 취소 역전표',
        ):
            return
        voucher_date = cancel_date
        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='PAYMENT',
            voucher_date=voucher_date,
            description=f'카드취소전표: {old.card.name} {old.merchant_name}',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        # 역전표: 차변=미지급금, 대변=비용
        VoucherLine.objects.create(
            voucher=voucher,
            account=payable_acct,
            debit=old.amount, credit=0,
            description=f'{old.merchant_name} 카드결제 취소',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=expense_acct,
            debit=0, credit=old.amount,
            description=f'{old.card.name} 미지급금 취소',
            created_by=instance.created_by,
        )


# === AR/AP 자동전표 시그널 ===

@receiver(post_save, sender=AccountReceivable)
def ar_auto_voucher_on_create(sender, instance, created, **kwargs):
    """AR 생성 시 자동전표: 차변 120(미수금) / 대변 401(매출)"""
    if not created or not instance.is_active:
        return

    with transaction.atomic():
        acct_120 = _get_account_code('120')  # 미수금
        acct_401 = _get_account_code('401')  # 매출

        if not acct_120 or not acct_401:
            logger.warning(
                'AR %s — missing account codes (120 or 401), skipping auto voucher',
                instance.pk,
            )
            return

        from apps.accounting.utils import validate_closing_period
        if not validate_closing_period(
            instance.due_date,
            raise_exception=False,
            notify_user=instance.created_by,
            context=f'AR pk={instance.pk} 자동전표',
        ):
            return
        voucher_date = instance.due_date

        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='RECEIPT',
            voucher_date=voucher_date,
            description=f'자동전표: 미수금 발생 ({instance.partner})',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_120,
            debit=instance.amount, credit=0,
            description=f'{instance.partner} 미수금',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_401,
            debit=0, credit=instance.amount,
            description=f'{instance.partner} 매출',
            created_by=instance.created_by,
        )


@receiver(post_save, sender=VoucherLine)
def check_budget_overspend_on_voucher_line(sender, instance, created, **kwargs):
    """전표항목 저장 시 해당 계정의 예산 초과 여부 체크

    VoucherLine의 account가 Budget에 등록된 계정이면,
    해당 월 실적이 예산을 초과할 때 경고 로깅.
    """
    if not created or not instance.is_active:
        return
    if not instance.voucher or not instance.account:
        return

    from .models import Budget
    from django.utils.dateparse import parse_date

    voucher_date = instance.voucher.voucher_date
    if isinstance(voucher_date, str):
        voucher_date = parse_date(voucher_date)
    if not voucher_date:
        return
    year = voucher_date.year
    month = voucher_date.month

    budgets = Budget.objects.filter(
        year=year, month=month, is_active=True,
        account=instance.account,
    ).select_related('account')

    for budget in budgets:
        actual = budget.actual_amount
        if actual > budget.budget_amount:
            overspend = actual - budget.budget_amount
            logger.warning(
                'Budget overspend: [%s] %s — %d년 %02d월 예산 %s원 초과 (예산: %s, 실적: %s)',
                budget.account.code, budget.account.name,
                year, month, overspend,
                budget.budget_amount, actual,
            )


@receiver(post_save, sender=AccountPayable)
def ap_auto_voucher_on_create(sender, instance, created, **kwargs):
    """AP 생성 시 자동전표: 차변 501(매입원가) / 대변 253(미지급금)"""
    if not created or not instance.is_active:
        return

    with transaction.atomic():
        acct_501 = _get_account_code('501')  # 매입원가
        acct_253 = _get_account_code('253')  # 미지급금

        if not acct_501 or not acct_253:
            logger.warning(
                'AP %s — missing account codes (501 or 253), skipping auto voucher',
                instance.pk,
            )
            return

        from apps.accounting.utils import validate_closing_period
        if not validate_closing_period(
            instance.due_date,
            raise_exception=False,
            notify_user=instance.created_by,
            context=f'AP pk={instance.pk} 자동전표',
        ):
            return
        voucher_date = instance.due_date

        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='PAYMENT',
            voucher_date=voucher_date,
            description=f'자동전표: 미지급금 발생 ({instance.partner})',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_501,
            debit=instance.amount, credit=0,
            description=f'{instance.partner} 매입원가',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_253,
            debit=0, credit=instance.amount,
            description=f'{instance.partner} 미지급금',
            created_by=instance.created_by,
        )


# === 매출 정산 수수료/배송비 자동전표 ===

@receiver(post_save, sender=SalesSettlement)
def auto_voucher_on_settlement(sender, instance, **kwargs):
    """SalesSettlement 저장 시 배송비/플랫폼수수료 자동전표 생성

    - commission_voucher가 이미 있으면 스킵 (중복 방지)
    - total_shipping 또는 total_platform_commission이 0보다 클 때만 전표 생성
    - 차변: 판매수수료(521) + 운반비(524), 대변: 미지급금(253)
    """
    if instance.commission_voucher_id:
        return

    shipping = instance.total_shipping or 0
    commission = instance.total_platform_commission or 0

    if shipping <= 0 and commission <= 0:
        return

    with transaction.atomic():
        acct_521 = _get_account_code('521')  # 판매수수료
        acct_524 = _get_account_code('524')  # 운반비(배송비)
        acct_253 = _get_account_code('253')  # 미지급금

        if not acct_253:
            logger.warning(
                'SalesSettlement %s — missing account 253 (미지급금), skipping voucher',
                instance.settlement_number,
            )
            return

        if commission > 0 and not acct_521:
            logger.warning(
                'SalesSettlement %s — missing account 521 (판매수수료), skipping voucher',
                instance.settlement_number,
            )
            return

        if shipping > 0 and not acct_524:
            logger.warning(
                'SalesSettlement %s — missing account 524 (운반비), skipping voucher',
                instance.settlement_number,
            )
            return

        from apps.accounting.utils import validate_closing_period
        if not validate_closing_period(
            instance.settlement_date,
            raise_exception=False,
            notify_user=instance.created_by,
            context=f'SalesSettlement {instance.settlement_number} 수수료 자동전표',
        ):
            return
        voucher_date = instance.settlement_date

        total_amount = commission + shipping

        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='TRANSFER',
            voucher_date=voucher_date,
            description=f'자동전표: 정산 수수료/배송비 ({instance.settlement_number})',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )

        if commission > 0:
            VoucherLine.objects.create(
                voucher=voucher,
                account=acct_521,
                debit=commission, credit=0,
                description=f'플랫폼수수료 ({instance.settlement_number})',
                created_by=instance.created_by,
            )

        if shipping > 0:
            VoucherLine.objects.create(
                voucher=voucher,
                account=acct_524,
                debit=shipping, credit=0,
                description=f'배송비 ({instance.settlement_number})',
                created_by=instance.created_by,
            )

        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_253,
            debit=0, credit=total_amount,
            description=f'수수료/배송비 미지급금 ({instance.settlement_number})',
            created_by=instance.created_by,
        )

        SalesSettlement.objects.filter(pk=instance.pk).update(
            commission_voucher=voucher,
        )


@receiver(post_delete, sender=CashReceiptItem)
def recalc_cash_receipt_on_item_delete(sender, instance, **kwargs):
    """CashReceiptItem 삭제 시 부모 CashReceipt 합계 재계산"""
    if instance.receipt_id:
        try:
            receipt = instance.receipt
        except sender._meta.get_field('receipt').related_model.DoesNotExist:
            return
        receipt.recalculate_totals()
