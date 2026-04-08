from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Phase 10 기능 추가에 따른 기존 데이터 소급 보완'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 변경 없이 대상 건수만 출력',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN 모드] 실제 변경 없이 대상 건수만 출력합니다.\n'))

        with transaction.atomic():
            self._backfill_ap_po(dry_run)
            self._backfill_expired_quotations(dry_run)
            self._backfill_converted_quotations(dry_run)
            self._backfill_shipment_tracking(dry_run)
            self._verify_partner_approval(dry_run)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS('\nPhase 10 소급 보완 완료.'))

    def _backfill_ap_po(self, dry_run):
        """AP ← PO 연결: purchase_order가 None인 AP를 partner+금액으로 PO 매칭"""
        from apps.accounting.models import AccountPayable
        from apps.purchase.models import PurchaseOrder

        orphan_aps = AccountPayable.objects.filter(
            purchase_order__isnull=True, is_active=True,
        )
        total = orphan_aps.count()
        matched = 0

        for ap in orphan_aps:
            po = PurchaseOrder.objects.filter(
                partner=ap.partner,
                grand_total=ap.amount,
                is_active=True,
            ).order_by('-order_date').first()
            if po:
                if not dry_run:
                    ap.purchase_order = po
                    ap.save(update_fields=['purchase_order', 'updated_at'])
                matched += 1

        self.stdout.write(f'[AP←PO 연결] 대상: {total}건, 매칭: {matched}건')

    def _backfill_expired_quotations(self, dry_run):
        """만료 견적 소급: valid_until < today이고 DRAFT/SENT/ACCEPTED → EXPIRED"""
        from apps.sales.models import Quotation

        expired_qs = Quotation.objects.filter(
            valid_until__lt=date.today(),
            status__in=['DRAFT', 'SENT', 'ACCEPTED'],
            is_active=True,
        )
        count = expired_qs.count()

        if not dry_run:
            expired_qs.update(status='EXPIRED')

        self.stdout.write(f'[견적 만료 소급] 대상: {count}건')

    def _backfill_converted_quotations(self, dry_run):
        """CONVERTED 소급: ACCEPTED이면서 converted_order가 있는 견적 → CONVERTED"""
        from apps.sales.models import Quotation

        converted_qs = Quotation.objects.filter(
            status='ACCEPTED',
            converted_order__isnull=False,
            is_active=True,
        )
        count = converted_qs.count()

        if not dry_run:
            converted_qs.update(status='CONVERTED')

        self.stdout.write(f'[견적 CONVERTED 소급] 대상: {count}건')

    def _backfill_shipment_tracking(self, dry_run):
        """ShipmentTracking 소급: 추적 이력 없는 배송에 초기 기록 생성"""
        from apps.sales.models import Shipment, ShipmentTracking

        created = 0
        for shipment in Shipment.objects.filter(is_active=True):
            if not ShipmentTracking.objects.filter(shipment=shipment).exists():
                if not dry_run:
                    ShipmentTracking.objects.create(
                        shipment=shipment,
                        status=shipment.status,
                        description='초기 상태 기록 (소급 생성)',
                        tracked_at=shipment.updated_at or shipment.created_at,
                    )
                created += 1

        self.stdout.write(f'[배송추적 소급] 대상: {created}건')

    def _verify_partner_approval(self, dry_run):
        """거래처 승인상태 확인: default=APPROVED이므로 확인만"""
        from apps.sales.models import Partner

        total = Partner.objects.filter(is_active=True).count()
        approved = Partner.objects.filter(
            is_active=True, approval_status='APPROVED',
        ).count()
        pending = total - approved

        self.stdout.write(
            f'[거래처 승인상태] 전체: {total}건, '
            f'승인: {approved}건, 미승인: {pending}건'
        )
