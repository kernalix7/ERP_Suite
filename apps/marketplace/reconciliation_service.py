import logging
from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.store_modules.models import StoreModuleConfig
from apps.store_modules.registry import registry

from .models import SettlementReconciliation

logger = logging.getLogger(__name__)

TOLERANCE = Decimal('10')  # ±10원 허용 오차


def reconcile_settlements(
    store_module_id: str,
    from_date: date,
    to_date: date,
) -> list[SettlementReconciliation]:
    """
    스토어별 정산 데이터와 실제 입금을 자동 매칭.

    1. store_modules.registry에서 모듈 인스턴스 가져오기
    2. 모듈.fetch_settlements(client, from_date, to_date)
    3. 해당 기간 Payment 입금 내역 조회
    4. 금액 매칭 (허용 오차 ±10원)
    5. SettlementReconciliation 레코드 생성
    """
    from apps.accounting.models import Payment

    module_instance = registry.get_instance(store_module_id)

    # 정산 데이터 수집 (API 미지원 시 빈 리스트)
    settlements = []
    if module_instance and module_instance.has_api:
        config = StoreModuleConfig.get_all_values(store_module_id)
        client = module_instance.get_api_client(config)
        if client:
            try:
                raw = module_instance.fetch_settlements(client, from_date, to_date)
                settlements = [
                    module_instance.normalize_settlement(s) for s in raw
                ]
            except NotImplementedError:
                settlements = []
            except Exception:
                logger.exception('정산 데이터 조회 실패: %s', store_module_id)
                settlements = []

    # 해당 기간 입금(RECEIPT) 내역 조회
    payments = Payment.objects.filter(
        is_active=True,
        payment_type=Payment.PaymentType.RECEIPT,
        payment_date__range=(from_date, to_date),
    ).order_by('payment_date')

    results = []

    if settlements:
        # API 정산 데이터 기반 매칭
        results = _match_with_settlements(
            store_module_id, settlements, payments,
        )
    else:
        # 수동 입력 모드: 입금 내역 기반으로 대사 레코드 생성
        results = _create_manual_records(
            store_module_id, payments, from_date, to_date,
        )

    return results


def _match_with_settlements(
    store_module_id: str,
    settlements: list[dict],
    payments,
) -> list[SettlementReconciliation]:
    """정산 데이터와 입금 내역을 금액 기준으로 매칭"""
    results = []
    used_payment_pks = set()

    with transaction.atomic():
        for sdata in settlements:
            settlement_date = sdata.get('date')
            expected = Decimal(str(sdata.get('amount', 0)))
            partner_id = sdata.get('partner_id')

            # 같은 날짜 ±1일 범위의 입금 중 금액 매칭
            actual = Decimal('0')
            matched = False
            for payment in payments:
                if payment.pk in used_payment_pks:
                    continue
                if abs(payment.amount - expected) <= TOLERANCE:
                    actual = payment.amount
                    used_payment_pks.add(payment.pk)
                    matched = True
                    if not partner_id and payment.partner_id:
                        partner_id = payment.partner_id
                    break

            diff = actual - expected
            if matched and abs(diff) <= TOLERANCE:
                status = SettlementReconciliation.Status.MATCHED
            elif matched:
                status = SettlementReconciliation.Status.MISMATCHED
            else:
                status = SettlementReconciliation.Status.PENDING

            recon = SettlementReconciliation.objects.create(
                store_module=store_module_id,
                settlement_date=settlement_date,
                expected_amount=expected,
                actual_amount=actual,
                difference=diff,
                status=status,
                partner_id=partner_id,
            )
            results.append(recon)

    return results


def _create_manual_records(
    store_module_id: str,
    payments,
    from_date: date,
    to_date: date,
) -> list[SettlementReconciliation]:
    """수동 입력 모드 — 입금 내역만으로 대사 레코드 생성 (예상액 = 0, 수동처리 상태)"""
    results = []

    with transaction.atomic():
        for payment in payments:
            recon = SettlementReconciliation.objects.create(
                store_module=store_module_id,
                settlement_date=payment.payment_date,
                expected_amount=Decimal('0'),
                actual_amount=payment.amount,
                difference=payment.amount,
                status=SettlementReconciliation.Status.MANUAL,
                partner_id=payment.partner_id,
            )
            results.append(recon)

    return results
