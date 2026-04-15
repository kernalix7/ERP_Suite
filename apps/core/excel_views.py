"""전체 앱 Excel 내보내기 뷰 — 모든 데이터를 이쁘게 Excel로 출력"""
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

from apps.core.excel import export_to_excel
from apps.core.mixins import ManagerRequiredMixin

logger = logging.getLogger(__name__)


class ExcelAuditMixin:
    """Excel 다운로드 감사 로그 Mixin.

    dispatch()를 오버라이드하여 성공적인 Excel 응답 후 다운로드 로그를 기록합니다.
    1일 50건 초과 시 관리자 Notification을 생성합니다.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if (
            response.status_code == 200
            and hasattr(request, 'user')
            and request.user.is_authenticated
            and response.get('Content-Type', '').startswith(
                'application/vnd.openxmlformats'
            )
        ):
            try:
                from apps.core.excel_audit import ExcelDownloadLog
                # row_count 추정: Content-Length 기반은 불가능하므로 뷰 이름만 기록
                xff = request.META.get('HTTP_X_FORWARDED_FOR')
                ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
                ExcelDownloadLog.log_download(
                    user=request.user,
                    view_name=self.__class__.__name__,
                    row_count=getattr(self, '_excel_row_count', 0),
                    ip_address=ip,
                )
            except Exception:
                logger.exception('Excel audit log failed')
        return response


# ═══════════════════════════════════════════════════
# 영업 — 거래처, 고객, 견적, 배송
# ═══════════════════════════════════════════════════

class PartnerExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.sales.models import Partner
        qs = Partner.objects.filter(is_active=True).order_by('code')
        headers = [
            ('코드', 12), ('거래처명', 25), ('유형', 10), ('사업자번호', 15),
            ('대표자', 12), ('담당자', 12), ('연락처', 16), ('이메일', 22),
            ('주소', 30),
        ]
        rows = [[
            p.code, p.name, p.get_partner_type_display(), p.business_number,
            p.representative, p.contact_name, p.phone, p.email, p.address,
        ] for p in qs]
        return export_to_excel('거래처 목록', headers, rows)


class CustomerExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.sales.models import Customer
        qs = Customer.objects.filter(is_active=True).order_by('code')
        headers = [
            ('고객코드', 12), ('고객명', 15), ('연락처', 16),
            ('이메일', 22), ('주소', 30),
        ]
        rows = [[
            c.code, c.name, c.phone, c.email, c.address,
        ] for c in qs]
        return export_to_excel('고객 목록', headers, rows)


class CustomerPurchaseExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.sales.models import CustomerPurchase
        qs = CustomerPurchase.objects.filter(
            is_active=True, customer__is_active=True,
        ).select_related('customer', 'product')
        headers = [
            ('고객명', 15), ('연락처', 16), ('이메일', 22),
            ('구매제품', 20), ('시리얼번호', 18), ('구매일', 12), ('보증만료', 12),
        ]
        rows = [[
            p.customer.name, p.customer.phone, p.customer.email,
            p.product.name if p.product else '',
            p.serial_number,
            p.purchase_date.strftime('%Y-%m-%d') if p.purchase_date else '',
            p.warranty_end.strftime('%Y-%m-%d') if p.warranty_end else '',
        ] for p in qs]
        return export_to_excel('고객구매내역', headers, rows)


class QuotationExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.sales.models import Quotation
        qs = Quotation.objects.filter(is_active=True).select_related('partner', 'customer')
        headers = [
            ('견적번호', 18), ('거래처', 20), ('고객', 15), ('견적일', 12),
            ('유효기한', 12), ('상태', 10), ('공급가액', 15), ('부가세', 15), ('합계', 15),
        ]
        rows = [[
            q.quote_number, q.partner.name if q.partner else '', q.customer.name if q.customer else '',
            q.quote_date.strftime('%Y-%m-%d'), q.valid_until.strftime('%Y-%m-%d'),
            q.get_status_display(), int(q.total_amount), int(q.tax_total), int(q.grand_total),
        ] for q in qs]
        return export_to_excel('견적서 목록', headers, rows, money_columns=[6, 7, 8])


class ShipmentExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.sales.models import Shipment
        qs = Shipment.objects.filter(is_active=True).select_related('order')
        headers = [
            ('배송번호', 18), ('주문번호', 18), ('배송유형', 10), ('택배사', 10),
            ('송장번호', 18), ('상태', 10), ('발송일', 12), ('수령인', 12),
            ('수령인 연락처', 16),
        ]
        rows = [[
            s.shipment_number, s.order.order_number,
            s.get_shipping_type_display(), s.get_carrier_display(),
            s.tracking_number, s.get_status_display(),
            s.shipped_date.strftime('%Y-%m-%d') if s.shipped_date else '',
            s.receiver_name, s.receiver_phone,
        ] for s in qs]
        return export_to_excel('배송 목록', headers, rows)


# ═══════════════════════════════════════════════════
# 재고 — 입출고, 재고현황, 창고이동
# ═══════════════════════════════════════════════════

class StockMovementExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.inventory.models import StockMovement
        qs = StockMovement.objects.filter(is_active=True).select_related('product', 'warehouse')
        headers = [
            ('입출고번호', 20), ('유형', 10), ('제품코드', 12), ('제품명', 20),
            ('창고', 15), ('수량', 10), ('단가', 15), ('금액', 15),
            ('일자', 12), ('참조', 20),
        ]
        rows = [[
            m.movement_number, m.get_movement_type_display(),
            m.product.code, m.product.name, m.warehouse.name,
            m.quantity, int(m.unit_price), int(m.total_amount),
            m.movement_date.strftime('%Y-%m-%d'), m.reference,
        ] for m in qs]
        return export_to_excel('입출고 내역', headers, rows, money_columns=[6, 7])


class StockStatusExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.inventory.models import Product
        qs = Product.objects.filter(is_active=True).select_related('category')
        headers = [
            ('제품코드', 12), ('제품명', 25), ('유형', 10), ('카테고리', 12),
            ('현재재고', 10), ('안전재고', 10), ('판매단가', 15), ('원가', 15),
            ('재고금액', 18),
        ]
        rows = [[
            p.code, p.name, p.get_product_type_display(),
            p.category.name if p.category else '',
            p.current_stock, p.safety_stock, int(p.unit_price), int(p.cost_price),
            int(p.current_stock * p.cost_price),
        ] for p in qs]
        return export_to_excel('재고현황', headers, rows, money_columns=[6, 7, 8])


class StockTransferExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.inventory.models import StockTransfer
        qs = StockTransfer.objects.filter(is_active=True).select_related(
            'from_warehouse', 'to_warehouse', 'product',
        )
        headers = [
            ('이동번호', 18), ('제품코드', 12), ('제품명', 20),
            ('출발창고', 15), ('도착창고', 15), ('수량', 10), ('이동일', 12),
        ]
        rows = [[
            t.transfer_number, t.product.code, t.product.name,
            t.from_warehouse.name, t.to_warehouse.name,
            t.quantity, t.transfer_date.strftime('%Y-%m-%d'),
        ] for t in qs]
        return export_to_excel('창고간 이동', headers, rows)


# ═══════════════════════════════════════════════════
# 생산
# ═══════════════════════════════════════════════════

class BOMExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.production.models import BOM, BOMItem
        items = BOMItem.objects.filter(is_active=True).select_related(
            'bom__product', 'material',
        )
        headers = [
            ('완제품코드', 12), ('완제품명', 20), ('BOM버전', 10),
            ('자재코드', 12), ('자재명', 20), ('소요량', 10), ('로스율(%)', 10),
            ('유효소요량', 12),
        ]
        rows = [[
            i.bom.product.code, i.bom.product.name, i.bom.version,
            i.material.code, i.material.name,
            float(i.quantity), float(i.loss_rate),
            float(i.effective_quantity),
        ] for i in items]
        return export_to_excel('BOM 자재명세', headers, rows)


class ProductionPlanExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.production.models import ProductionPlan
        qs = ProductionPlan.objects.filter(is_active=True).select_related('product', 'bom')
        headers = [
            ('계획번호', 18), ('제품명', 20), ('BOM', 10), ('계획수량', 10),
            ('시작일', 12), ('종료일', 12), ('상태', 10),
            ('예상비용', 15), ('실제비용', 15),
        ]
        rows = [[
            p.plan_number, p.product.name, p.bom.version, p.planned_quantity,
            p.planned_start.strftime('%Y-%m-%d'), p.planned_end.strftime('%Y-%m-%d'),
            p.get_status_display(), int(p.estimated_cost), int(p.actual_cost),
        ] for p in qs]
        return export_to_excel('생산계획', headers, rows, money_columns=[7, 8])


class WorkOrderExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.production.models import WorkOrder
        qs = WorkOrder.objects.filter(is_active=True).select_related(
            'production_plan__product', 'assigned_to',
        )
        headers = [
            ('지시번호', 18), ('생산계획', 18), ('제품명', 20), ('수량', 10),
            ('담당자', 12), ('상태', 10), ('시작일시', 18), ('완료일시', 18),
        ]
        rows = [[
            w.order_number, w.production_plan.plan_number,
            w.production_plan.product.name, w.quantity,
            w.assigned_to.name if w.assigned_to else '',
            w.get_status_display(),
            w.started_at.strftime('%Y-%m-%d %H:%M') if w.started_at else '',
            w.completed_at.strftime('%Y-%m-%d %H:%M') if w.completed_at else '',
        ] for w in qs]
        return export_to_excel('작업지시', headers, rows)


class ProductionRecordExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.production.models import ProductionRecord
        qs = ProductionRecord.objects.filter(is_active=True).select_related(
            'work_order__production_plan__product', 'worker',
        )
        headers = [
            ('작업지시', 18), ('제품명', 20), ('실적일', 12),
            ('양품수량', 10), ('불량수량', 10), ('작업자', 12),
        ]
        rows = [[
            r.work_order.order_number,
            r.work_order.production_plan.product.name,
            r.record_date.strftime('%Y-%m-%d'),
            r.good_quantity, r.defect_quantity,
            r.worker.name if r.worker else '',
        ] for r in qs]
        return export_to_excel('생산실적', headers, rows)


# ═══════════════════════════════════════════════════
# 구매
# ═══════════════════════════════════════════════════

class PurchaseOrderExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.purchase.models import PurchaseOrder
        qs = PurchaseOrder.objects.filter(is_active=True).select_related('partner')
        headers = [
            ('발주번호', 18), ('거래처', 20), ('발주일', 12), ('납기일', 12),
            ('상태', 12), ('공급가액', 15), ('부가세', 15), ('합계', 15),
        ]
        rows = [[
            po.po_number, po.partner.name,
            po.order_date.strftime('%Y-%m-%d'),
            po.expected_date.strftime('%Y-%m-%d') if po.expected_date else '',
            po.get_status_display(),
            int(po.total_amount), int(po.tax_total), int(po.grand_total),
        ] for po in qs]
        return export_to_excel('구매발주', headers, rows, money_columns=[5, 6, 7])


class GoodsReceiptExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.purchase.models import GoodsReceipt, GoodsReceiptItem
        items = GoodsReceiptItem.objects.filter(is_active=True).select_related(
            'goods_receipt__purchase_order__partner', 'po_item__product',
        )
        headers = [
            ('입고번호', 18), ('발주번호', 18), ('거래처', 20), ('입고일', 12),
            ('제품코드', 12), ('제품명', 20), ('입고수량', 10), ('검수여부', 8),
        ]
        rows = [[
            i.goods_receipt.receipt_number,
            i.goods_receipt.purchase_order.po_number,
            i.goods_receipt.purchase_order.partner.name,
            i.goods_receipt.receipt_date.strftime('%Y-%m-%d'),
            i.po_item.product.code, i.po_item.product.name,
            i.received_quantity, '완료' if i.is_inspected else '대기',
        ] for i in items]
        return export_to_excel('입고 내역', headers, rows)


class RFQExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.purchase.models import RFQ
        qs = RFQ.objects.filter(is_active=True).select_related(
            'requested_by',
        ).order_by('-rfq_number')
        headers = [
            ('견적요청번호', 15), ('제목', 25), ('상태', 10),
            ('요청자', 12), ('마감일', 12),
        ]
        rows = [[
            r.rfq_number, r.title,
            r.get_status_display(),
            r.requested_by.get_full_name() if r.requested_by else '',
            r.due_date.strftime('%Y-%m-%d') if r.due_date else '',
        ] for r in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('견적요청 목록', headers, rows)


class VendorScoreExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.purchase.models import VendorScore
        qs = VendorScore.objects.filter(is_active=True).select_related(
            'partner', 'evaluator',
        ).order_by('-evaluation_date')
        headers = [
            ('공급처', 20), ('평가일', 12), ('납기', 8),
            ('품질', 8), ('가격', 8), ('서비스', 8),
            ('종합', 8), ('평가자', 12),
        ]
        rows = [[
            v.partner.name if v.partner else '',
            v.evaluation_date.strftime('%Y-%m-%d'),
            v.delivery_score, v.quality_score,
            v.price_score, v.service_score,
            float(v.overall_score),
            v.evaluator.get_full_name() if v.evaluator else '',
        ] for v in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('공급처 평가', headers, rows)


# ═══════════════════════════════════════════════════
# 회계
# ═══════════════════════════════════════════════════

class TaxInvoiceExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.accounting.models import TaxInvoice
        qs = TaxInvoice.objects.filter(is_active=True).select_related('partner')
        headers = [
            ('계산서번호', 18), ('유형', 10), ('거래처', 20), ('발행일', 12),
            ('공급가액', 15), ('세액', 15), ('합계', 15), ('적요', 25),
        ]
        rows = [[
            inv.invoice_number, inv.get_invoice_type_display(), inv.partner.name,
            inv.issue_date.strftime('%Y-%m-%d'),
            int(inv.supply_amount), int(inv.tax_amount), int(inv.total_amount),
            inv.description,
        ] for inv in qs]
        return export_to_excel('세금계산서', headers, rows, money_columns=[4, 5, 6])


class VoucherExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.accounting.models import Voucher, VoucherLine
        lines = VoucherLine.objects.filter(is_active=True).select_related(
            'voucher', 'account',
        )
        headers = [
            ('전표번호', 18), ('유형', 10), ('전표일', 12), ('결재상태', 10),
            ('적요', 25), ('계정코드', 10), ('계정명', 15), ('차변', 15), ('대변', 15),
        ]
        rows = [[
            line.voucher.voucher_number, line.voucher.get_voucher_type_display(),
            line.voucher.voucher_date.strftime('%Y-%m-%d'),
            line.voucher.get_approval_status_display(),
            line.voucher.description, line.account.code, line.account.name,
            int(line.debit), int(line.credit),
        ] for line in lines]
        return export_to_excel('전표 상세', headers, rows, money_columns=[7, 8])


class AccountCodeExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.accounting.models import AccountCode
        qs = AccountCode.objects.filter(is_active=True).select_related('parent')
        headers = [
            ('코드', 10), ('계정명', 20), ('유형', 10), ('상위계정', 15),
        ]
        rows = [[
            a.code, a.name, a.get_account_type_display(),
            a.parent.name if a.parent else '',
        ] for a in qs]
        return export_to_excel('계정과목', headers, rows)


class FixedCostExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.accounting.models import FixedCost
        qs = FixedCost.objects.filter(is_active=True)
        headers = [
            ('구분', 12), ('항목명', 20), ('금액', 15), ('기준월', 12), ('반복여부', 8),
        ]
        rows = [[
            fc.get_category_display(), fc.name, int(fc.amount),
            fc.month.strftime('%Y-%m'), '반복' if fc.is_recurring else '단발',
        ] for fc in qs]
        return export_to_excel('고정비', headers, rows, money_columns=[2])


class ARExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.accounting.models import AccountReceivable
        qs = AccountReceivable.objects.filter(is_active=True).select_related('partner')
        headers = [
            ('거래처', 20), ('매출채권액', 15), ('수금액', 15), ('잔액', 15),
            ('만기일', 12), ('상태', 10),
        ]
        rows = [[
            ar.partner.name, int(ar.amount), int(ar.paid_amount),
            int(ar.amount - ar.paid_amount),
            ar.due_date.strftime('%Y-%m-%d'), ar.get_status_display(),
        ] for ar in qs]
        return export_to_excel('매출채권(미수금)', headers, rows, money_columns=[1, 2, 3])


class APExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.accounting.models import AccountPayable
        qs = AccountPayable.objects.filter(is_active=True).select_related('partner')
        headers = [
            ('거래처', 20), ('매입채무액', 15), ('지급액', 15), ('잔액', 15),
            ('만기일', 12), ('상태', 10),
        ]
        rows = [[
            ap.partner.name, int(ap.amount), int(ap.paid_amount),
            int(ap.amount - ap.paid_amount),
            ap.due_date.strftime('%Y-%m-%d'), ap.get_status_display(),
        ] for ap in qs]
        return export_to_excel('매입채무(미지급금)', headers, rows, money_columns=[1, 2, 3])


class ApprovalExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.approval.models import ApprovalRequest
        qs = ApprovalRequest.objects.filter(is_active=True).select_related('requester', 'approver')
        headers = [
            ('결재번호', 18), ('구분', 10), ('제목', 30), ('금액', 15),
            ('상태', 10), ('요청자', 12), ('결재자', 12), ('제출일', 18),
        ]
        rows = [[
            a.request_number, a.get_category_display(), a.title, int(a.amount),
            a.get_status_display(),
            a.requester.name if a.requester else '',
            a.approver.name if a.approver else '',
            a.submitted_at.strftime('%Y-%m-%d %H:%M') if a.submitted_at else '',
        ] for a in qs]
        return export_to_excel('결재/품의', headers, rows, money_columns=[3])


class WithholdingTaxExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.accounting.models import WithholdingTax
        qs = WithholdingTax.objects.filter(is_active=True)
        headers = [
            ('세목', 12), ('지급대상', 15), ('지급일', 12),
            ('총액', 15), ('세율(%)', 10), ('원천세', 15), ('실수령액', 15),
        ]
        rows = [[
            wt.get_tax_type_display(), wt.payee_name,
            wt.payment_date.strftime('%Y-%m-%d'),
            int(wt.gross_amount), float(wt.tax_rate),
            int(wt.tax_amount), int(wt.net_amount),
        ] for wt in qs]
        return export_to_excel('원천세', headers, rows, money_columns=[3, 5, 6])


# ═══════════════════════════════════════════════════
# 투자
# ═══════════════════════════════════════════════════

class InvestorExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.investment.models import Investor
        qs = Investor.objects.filter(is_active=True)
        headers = [
            ('투자자명', 20), ('소속회사', 20), ('담당자', 12),
            ('연락처', 16), ('이메일', 22), ('등록일', 12),
            ('총투자액', 15), ('현재지분(%)', 12),
        ]
        rows = [[
            i.name, i.company, i.contact_person, i.phone, i.email,
            i.registration_date.strftime('%Y-%m-%d'),
            int(i.total_invested), float(i.current_share),
        ] for i in qs]
        return export_to_excel('투자자 목록', headers, rows, money_columns=[6])


class InvestmentRoundExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.investment.models import InvestmentRound
        qs = InvestmentRound.objects.filter(is_active=True)
        headers = [
            ('라운드명', 15), ('라운드일', 12), ('목표금액', 18),
            ('달성금액', 18), ('Pre-밸류', 18), ('Post-밸류', 18),
        ]
        rows = [[
            r.name, r.round_date.strftime('%Y-%m-%d'),
            int(r.target_amount), int(r.raised_amount),
            int(r.pre_valuation), int(r.post_valuation),
        ] for r in qs]
        return export_to_excel('투자 라운드', headers, rows, money_columns=[2, 3, 4, 5])


class DistributionExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.investment.models import Distribution
        qs = Distribution.objects.filter(is_active=True).select_related('investor')
        headers = [
            ('투자자', 20), ('배당유형', 12), ('배당금액', 15),
            ('예정일', 12), ('지급일', 12), ('상태', 10),
        ]
        rows = [[
            d.investor.name, d.get_distribution_type_display(), int(d.amount),
            d.scheduled_date.strftime('%Y-%m-%d'),
            d.paid_date.strftime('%Y-%m-%d') if d.paid_date else '',
            d.get_status_display(),
        ] for d in qs]
        return export_to_excel('배당/분배', headers, rows, money_columns=[2])


# ═══════════════════════════════════════════════════
# 보증
# ═══════════════════════════════════════════════════

class WarrantyExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.warranty.models import ProductRegistration
        qs = ProductRegistration.objects.filter(is_active=True).select_related('product')
        headers = [
            ('시리얼번호', 18), ('제품명', 20), ('고객명', 15),
            ('연락처', 16), ('구매일', 12), ('보증시작', 12), ('보증만료', 12),
        ]
        rows = [[
            pr.serial_number, pr.product.name if pr.product else '', pr.customer_name,
            pr.phone,
            pr.purchase_date.strftime('%Y-%m-%d') if pr.purchase_date else '',
            pr.warranty_start.strftime('%Y-%m-%d') if pr.warranty_start else '',
            pr.warranty_end.strftime('%Y-%m-%d') if pr.warranty_end else '',
        ] for pr in qs]
        return export_to_excel('제품보증 등록', headers, rows)


# ═══════════════════════════════════════════════════
# 마켓플레이스
# ═══════════════════════════════════════════════════

class MarketplaceOrderExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.marketplace.models import MarketplaceOrder
        qs = MarketplaceOrder.objects.filter(is_active=True)
        headers = [
            ('스토어주문번호', 20), ('상품명', 25), ('옵션', 15), ('수량', 8),
            ('결제금액', 15), ('주문자', 12), ('수취인', 12),
            ('주문일시', 18), ('상태', 10),
        ]
        rows = [[
            o.store_order_id, o.product_name, o.option_name, o.quantity,
            int(o.price), o.buyer_name, o.receiver_name,
            o.ordered_at.strftime('%Y-%m-%d %H:%M') if o.ordered_at else '',
            o.get_status_display(),
        ] for o in qs]
        return export_to_excel('스토어 주문', headers, rows, money_columns=[4])


# ═══════════════════════════════════════════════════
# 문의
# ═══════════════════════════════════════════════════

class InquiryExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.inquiry.models import Inquiry
        qs = Inquiry.objects.filter(is_active=True).select_related('assigned_to')
        headers = [
            ('채널', 10), ('고객명', 15), ('연락처', 16),
            ('제목', 30), ('상태', 10), ('우선순위', 8), ('담당자', 12),
            ('접수일', 18),
        ]
        rows = [[
            i.get_channel_display(), i.customer_name, i.customer_contact,
            i.subject, i.get_status_display(),
            i.get_priority_display(),
            i.assigned_to.name if i.assigned_to else '',
            i.created_at.strftime('%Y-%m-%d %H:%M'),
        ] for i in qs]
        return export_to_excel('문의 목록', headers, rows)


# ═══════════════════════════════════════════════════
# A/S
# ═══════════════════════════════════════════════════

class ServiceRequestExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.service.models import ServiceRequest
        qs = ServiceRequest.objects.filter(is_active=True).select_related('customer', 'product')
        headers = [
            ('접수번호', 18), ('고객명', 15), ('제품명', 20), ('시리얼', 18),
            ('유형', 10), ('상태', 10), ('접수일', 12), ('완료일', 12), ('증상', 30),
        ]
        rows = [[
            sr.request_number, sr.customer.name if sr.customer else '',
            sr.product.name if sr.product else '', sr.serial_number,
            sr.get_request_type_display(), sr.get_status_display(),
            sr.received_date.strftime('%Y-%m-%d'),
            sr.completed_date.strftime('%Y-%m-%d') if sr.completed_date else '',
            sr.symptom[:50],
        ] for sr in qs]
        return export_to_excel('A/S 접수', headers, rows)


# ═══════════════════════════════════════════════════
# 인사
# ═══════════════════════════════════════════════════

class EmployeeExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.hr.models import EmployeeProfile
        qs = EmployeeProfile.objects.filter(is_active=True).select_related(
            'user', 'department', 'position',
        )
        headers = [
            ('사번', 12), ('이름', 12), ('부서', 15), ('직급', 10),
            ('계약유형', 10), ('입사일', 12), ('상태', 8),
            ('이메일', 22), ('연락처', 16),
        ]
        rows = [[
            e.employee_number, e.user.name, e.department.name if e.department else '',
            e.position.name if e.position else '', e.get_contract_type_display(),
            e.hire_date.strftime('%Y-%m-%d'), e.get_status_display(),
            e.user.email, e.user.phone,
        ] for e in qs]
        return export_to_excel('직원 목록', headers, rows)


class DepartmentExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.hr.models import Department
        qs = Department.objects.filter(is_active=True).select_related('parent', 'manager')
        headers = [
            ('코드', 10), ('부서명', 20), ('상위부서', 15), ('부서장', 12),
        ]
        rows = [[
            d.code, d.name, d.parent.name if d.parent else '', d.manager.name if d.manager else '',
        ] for d in qs]
        return export_to_excel('부서 목록', headers, rows)


class PersonnelActionExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.hr.models import PersonnelAction
        qs = PersonnelAction.objects.filter(is_active=True).select_related(
            'employee__user', 'from_department', 'to_department', 'from_position', 'to_position',
        )
        headers = [
            ('직원', 12), ('발령유형', 10), ('시행일', 12),
            ('이전부서', 15), ('변경부서', 15), ('이전직급', 10), ('변경직급', 10),
            ('사유', 30),
        ]
        rows = [[
            a.employee.user.name, a.get_action_type_display(),
            a.effective_date.strftime('%Y-%m-%d'),
            a.from_department.name if a.from_department else '',
            a.to_department.name if a.to_department else '',
            a.from_position.name if a.from_position else '',
            a.to_position.name if a.to_position else '',
            a.reason,
        ] for a in qs]
        return export_to_excel('인사발령', headers, rows)


# ═══════════════════════════════════════════════════
# 근태
# ═══════════════════════════════════════════════════

class AttendanceExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.attendance.models import AttendanceRecord
        qs = AttendanceRecord.objects.filter(is_active=True).select_related('user')
        headers = [
            ('직원', 12), ('날짜', 12), ('출근', 12), ('퇴근', 12),
            ('상태', 10), ('초과근무(h)', 10),
        ]
        rows = [[
            a.user.name, a.date.strftime('%Y-%m-%d'),
            a.check_in.strftime('%H:%M') if a.check_in else '',
            a.check_out.strftime('%H:%M') if a.check_out else '',
            a.get_status_display(), float(a.overtime_hours),
        ] for a in qs]
        return export_to_excel('출퇴근 기록', headers, rows)


class LeaveRequestExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.attendance.models import LeaveRequest
        qs = LeaveRequest.objects.filter(is_active=True).select_related('user', 'approved_by')
        headers = [
            ('직원', 12), ('휴가유형', 10), ('시작일', 12), ('종료일', 12),
            ('일수', 8), ('상태', 10), ('승인자', 12), ('사유', 30),
        ]
        rows = [[
            lr.user.name, lr.get_leave_type_display(),
            lr.start_date.strftime('%Y-%m-%d'), lr.end_date.strftime('%Y-%m-%d'),
            float(lr.days), lr.get_status_display(),
            lr.approved_by.name if lr.approved_by else '', lr.reason,
        ] for lr in qs]
        return export_to_excel('휴가 신청', headers, rows)


class LeaveBalanceExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.attendance.models import AnnualLeaveBalance
        qs = AnnualLeaveBalance.objects.filter(is_active=True).select_related('user')
        headers = [
            ('직원', 12), ('연도', 8), ('총연차', 8), ('사용', 8), ('잔여', 8),
        ]
        rows = [[
            lb.user.name, lb.year, float(lb.total_days), float(lb.used_days),
            float(lb.total_days - lb.used_days),
        ] for lb in qs]
        return export_to_excel('연차 잔여현황', headers, rows)


# ═══════════════════════════════════════════════════
# 게시판
# ═══════════════════════════════════════════════════

class PostExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.board.models import Post
        qs = Post.objects.filter(is_active=True).select_related('board', 'author')
        headers = [
            ('게시판', 12), ('제목', 35), ('작성자', 12), ('작성일', 18),
            ('조회수', 8), ('고정', 6),
        ]
        rows = [[
            p.board.name, p.title, p.author.name if hasattr(p.author, 'name') else str(p.author),
            p.created_at.strftime('%Y-%m-%d %H:%M'), p.view_count,
            'O' if p.is_pinned else '',
        ] for p in qs]
        return export_to_excel('게시글 목록', headers, rows)


# ═══════════════════════════════════════════════════
# 광고
# ═══════════════════════════════════════════════════

class AdCampaignExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.advertising.models import AdCampaign
        qs = AdCampaign.objects.filter(is_active=True).select_related('platform')
        headers = [
            ('플랫폼', 15), ('캠페인명', 25), ('유형', 10), ('상태', 10),
            ('예산', 15), ('집행액', 15), ('시작일', 12), ('종료일', 12),
            ('소진율(%)', 10),
        ]
        rows = [[
            c.platform.name, c.name, c.get_campaign_type_display(),
            c.get_status_display(), int(c.budget), int(c.spent),
            c.start_date.strftime('%Y-%m-%d'), c.end_date.strftime('%Y-%m-%d'),
            c.budget_utilization,
        ] for c in qs]
        return export_to_excel('광고 캠페인', headers, rows, money_columns=[4, 5])


class AdPerformanceExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.advertising.models import AdPerformance
        qs = AdPerformance.objects.filter(is_active=True).select_related('campaign', 'creative')
        headers = [
            ('캠페인', 25), ('소재', 20), ('날짜', 12),
            ('노출수', 12), ('클릭수', 10), ('전환수', 10),
            ('비용', 15), ('매출', 15), ('CTR(%)', 10), ('ROAS(%)', 10),
        ]
        rows = [[
            p.campaign.name, p.creative.name if p.creative else '',
            p.date.strftime('%Y-%m-%d'),
            p.impressions, p.clicks, p.conversions,
            int(p.cost), int(p.revenue), p.ctr, p.roas,
        ] for p in qs]
        return export_to_excel('광고 성과', headers, rows, money_columns=[6, 7])


class AdBudgetExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.advertising.models import AdBudget
        qs = AdBudget.objects.filter(is_active=True).select_related('platform')
        headers = [
            ('연도', 8), ('월', 6), ('플랫폼', 15),
            ('계획예산', 15), ('실제집행', 15), ('소진율(%)', 10),
        ]
        rows = [[
            b.year, b.month, b.platform.name if b.platform else '전체',
            int(b.planned_budget), int(b.actual_spent), b.utilization_rate,
        ] for b in qs]
        return export_to_excel('광고 예산', headers, rows, money_columns=[3, 4])


# ═══════════════════════════════════════════════════
# 수수료
# ═══════════════════════════════════════════════════

class CommissionExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.sales.commission import CommissionRecord
        qs = CommissionRecord.objects.filter(is_active=True).select_related(
            'order', 'partner',
        )
        headers = [
            ('주문번호', 18), ('거래처', 20),
            ('주문금액', 15), ('수수료율(%)', 10), ('수수료액', 15),
            ('상태', 10), ('정산일', 12),
        ]
        rows = [[
            cr.order.order_number if cr.order else '',
            cr.partner.name if cr.partner else '',
            int(cr.order_amount), float(cr.commission_rate),
            int(cr.commission_amount), cr.get_status_display(),
            cr.settled_date.strftime('%Y-%m-%d') if cr.settled_date else '',
        ] for cr in qs]
        return export_to_excel('수수료 내역', headers, rows, money_columns=[2, 4])


# ═══════════════════════════════════════════════════
# LMS
# ═══════════════════════════════════════════════════

class CourseExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.lms.models import Course
        qs = Course.objects.filter(is_active=True).select_related('category', 'instructor')
        headers = [
            ('강좌번호', 12), ('강좌명', 30), ('분류', 15), ('강사', 12),
            ('난이도', 8), ('상태', 8), ('필수교육', 6), ('학습시간(h)', 10),
        ]
        rows = [[
            c.course_number, c.title,
            c.category.name if c.category else '',
            c.instructor.get_full_name() if c.instructor else '',
            c.get_level_display(), c.get_status_display(),
            'O' if c.is_mandatory else '', float(c.duration_hours),
        ] for c in qs]
        return export_to_excel('강좌 목록', headers, rows)


class EnrollmentExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.lms.models import CourseEnrollment
        qs = CourseEnrollment.objects.filter(is_active=True).select_related(
            'course', 'learner',
        ).order_by('-enrolled_at')
        headers = [
            ('수강자', 12), ('강좌명', 30), ('상태', 8),
            ('진도율(%)', 10), ('최종점수', 10), ('등록일', 18), ('수료일', 18),
        ]
        rows = [[
            e.learner.get_full_name() or e.learner.username,
            e.course.title, e.get_status_display(),
            e.progress_pct, float(e.final_score),
            e.enrolled_at.strftime('%Y-%m-%d'),
            e.completed_at.strftime('%Y-%m-%d') if e.completed_at else '',
        ] for e in qs]
        return export_to_excel('수강 현황', headers, rows)


# ═══════════════════════════════════════════════════
# 프로젝트
# ═══════════════════════════════════════════════════

class ProjectExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.project.models import Project
        qs = Project.objects.filter(is_active=True).select_related('category', 'manager', 'department')
        headers = [
            ('프로젝트번호', 14), ('프로젝트명', 30), ('분류', 12), ('담당부서', 15),
            ('관리자', 12), ('상태', 8), ('우선순위', 8),
            ('시작일', 12), ('목표완료일', 12), ('진행률(%)', 10),
        ]
        rows = [[
            p.project_number, p.name,
            p.category.name if p.category else '',
            p.department.name if p.department else '',
            p.manager.get_full_name() or p.manager.username,
            p.get_status_display(), p.get_priority_display(),
            p.start_date.strftime('%Y-%m-%d') if p.start_date else '',
            p.due_date.strftime('%Y-%m-%d') if p.due_date else '',
            p.progress_pct,
        ] for p in qs]
        return export_to_excel('프로젝트 목록', headers, rows)


class TaskExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.project.models import Task
        qs = Task.objects.filter(is_active=True).select_related(
            'project', 'assignee', 'milestone',
        )
        headers = [
            ('프로젝트', 20), ('태스크명', 35), ('담당자', 12),
            ('마일스톤', 20), ('상태', 8), ('우선순위', 8),
            ('시작일', 12), ('마감일', 12), ('예상(h)', 8), ('실제(h)', 8),
        ]
        rows = [[
            t.project.name, t.title,
            t.assignee.get_full_name() if t.assignee else '',
            t.milestone.title if t.milestone else '',
            t.get_status_display(), t.get_priority_display(),
            t.start_date.strftime('%Y-%m-%d') if t.start_date else '',
            t.due_date.strftime('%Y-%m-%d') if t.due_date else '',
            float(t.estimated_hours), float(t.actual_hours),
        ] for t in qs]
        return export_to_excel('태스크 목록', headers, rows)


# ═══════════════════════════════════════════════════
# 위키
# ═══════════════════════════════════════════════════

class WikiArticleExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.wiki.models import WikiArticle
        qs = WikiArticle.objects.filter(
            is_active=True, status=WikiArticle.Status.PUBLISHED,
        ).select_related('space', 'category', 'author')
        headers = [
            ('문서번호', 12), ('공간', 12), ('카테고리', 15),
            ('제목', 40), ('작성자', 12), ('상태', 8),
            ('조회수', 8), ('수정일', 18),
        ]
        rows = [[
            a.article_number, a.space.name,
            a.category.name if a.category else '',
            a.title,
            a.author.get_full_name() or a.author.username,
            a.get_status_display(),
            a.view_count,
            a.updated_at.strftime('%Y-%m-%d %H:%M'),
        ] for a in qs]
        return export_to_excel('위키 문서 목록', headers, rows)


# ═══════════════════════════════════════════════════
# 방문자
# ═══════════════════════════════════════════════════

class VisitRequestExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.visitor.models import VisitRequest
        qs = VisitRequest.objects.filter(is_active=True).select_related(
            'visitor', 'host', 'purpose', 'department',
        ).order_by('-scheduled_at')
        headers = [
            ('방문번호', 14), ('방문자', 12), ('소속', 20),
            ('호스트', 12), ('방문목적', 15), ('방문부서', 15),
            ('예정일시', 18), ('상태', 8),
        ]
        rows = [[
            vr.visit_number, vr.visitor.name, vr.visitor.company or '',
            vr.host.get_full_name() or vr.host.username,
            vr.purpose.name, vr.department.name if vr.department else '',
            vr.scheduled_at.strftime('%Y-%m-%d %H:%M'),
            vr.get_status_display(),
        ] for vr in qs]
        return export_to_excel('방문 예약 목록', headers, rows)


class VisitLogExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.visitor.models import VisitLog
        qs = VisitLog.objects.filter(is_active=True).select_related(
            'visitor', 'receptionist',
        ).order_by('-check_in_at')
        headers = [
            ('방문자', 12), ('소속', 20), ('방문증번호', 12),
            ('체크인', 18), ('체크아웃', 18), ('체류시간(분)', 12), ('접수담당', 12),
        ]
        rows = [[
            vl.visitor.name, vl.visitor.company or '',
            vl.badge_number,
            vl.check_in_at.strftime('%Y-%m-%d %H:%M'),
            vl.check_out_at.strftime('%Y-%m-%d %H:%M') if vl.check_out_at else '',
            vl.duration_minutes or '',
            vl.receptionist.get_full_name() if vl.receptionist else '',
        ] for vl in qs]
        return export_to_excel('방문 기록', headers, rows)


# ═══════════════════════════════════════════════════
# 자산
# ═══════════════════════════════════════════════════

class FixedAssetExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.asset.models import FixedAsset
        qs = FixedAsset.objects.filter(is_active=True).select_related(
            'category', 'department', 'responsible_person',
        ).order_by('asset_number')
        headers = [
            ('자산번호', 16), ('자산명', 25), ('카테고리', 15), ('상태', 10),
            ('부서', 15), ('담당자', 12), ('취득일', 12), ('취득가', 15),
            ('감가상각누계', 15), ('장부가', 15), ('잔존가', 15),
        ]
        rows = [[
            a.asset_number, a.name,
            a.category.name if a.category else '',
            a.get_status_display(),
            a.department.name if a.department else '',
            a.responsible_person.get_full_name() if a.responsible_person else '',
            a.acquisition_date.strftime('%Y-%m-%d') if a.acquisition_date else '',
            int(a.acquisition_cost),
            int(a.accumulated_depreciation),
            int(a.book_value),
            int(a.residual_value),
        ] for a in qs]
        self._excel_row_count = len(rows)
        return export_to_excel(
            '고정자산 목록', headers, rows,
            money_columns=[7, 8, 9, 10],
        )


class AssetTransferExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.asset.models import AssetTransfer
        qs = AssetTransfer.objects.filter(is_active=True).select_related(
            'asset', 'from_department', 'to_department', 'from_person', 'to_person',
        ).order_by('-transfer_date')
        headers = [
            ('자산번호', 16), ('자산명', 20), ('이관일', 12),
            ('이전부서', 15), ('이전담당', 12), ('이관부서', 15), ('이관담당', 12),
            ('사유', 25),
        ]
        rows = [[
            t.asset.asset_number, t.asset.name,
            t.transfer_date.strftime('%Y-%m-%d'),
            t.from_department.name if t.from_department else '',
            t.from_person.get_full_name() if t.from_person else '',
            t.to_department.name if t.to_department else '',
            t.to_person.get_full_name() if t.to_person else '',
            t.reason or '',
        ] for t in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('자산 이관 내역', headers, rows)


# ═══════════════════════════════════════════════════
# 문서/계약
# ═══════════════════════════════════════════════════

class DocumentExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.document.models import Document
        qs = Document.objects.filter(is_active=True).select_related(
            'category', 'owner', 'department',
        ).order_by('-pk')
        headers = [
            ('문서번호', 16), ('제목', 30), ('카테고리', 15), ('상태', 10),
            ('버전', 8), ('접근레벨', 10), ('작성자', 12), ('부서', 15),
        ]
        rows = [[
            d.document_number, d.title,
            d.category.name if d.category else '',
            d.get_status_display(),
            d.version,
            d.get_access_level_display(),
            d.owner.get_full_name() if d.owner else '',
            d.department.name if d.department else '',
        ] for d in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('문서 목록', headers, rows)


class ContractExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.document.models import Contract
        qs = Contract.objects.filter(is_active=True).select_related(
            'partner', 'signed_by',
        ).order_by('-start_date')
        headers = [
            ('계약번호', 16), ('제목', 25), ('계약유형', 12), ('거래처', 20),
            ('상태', 10), ('시작일', 12), ('종료일', 12), ('계약금액', 15),
        ]
        rows = [[
            c.contract_number, c.title,
            c.get_contract_type_display(),
            c.partner.name if c.partner else '',
            c.get_status_display(),
            c.start_date.strftime('%Y-%m-%d') if c.start_date else '',
            c.end_date.strftime('%Y-%m-%d') if c.end_date else '',
            int(c.value or 0),
        ] for c in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('계약 목록', headers, rows, money_columns=[7])


# ═══════════════════════════════════════════════════
# 경비
# ═══════════════════════════════════════════════════

class ExpenseClaimExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.expense.models import ExpenseClaim
        qs = ExpenseClaim.objects.filter(is_active=True).select_related(
            'employee', 'approved_by',
        ).order_by('-pk')
        headers = [
            ('청구번호', 16), ('제목', 25), ('청구자', 12), ('상태', 10),
            ('총금액', 15), ('제출일', 12), ('승인일', 12), ('승인자', 12),
        ]
        rows = [[
            c.claim_number, c.title,
            c.employee.user.get_full_name() if c.employee and c.employee.user else '',
            c.get_status_display(),
            int(c.total_amount or 0),
            c.submitted_date.strftime('%Y-%m-%d') if c.submitted_date else '',
            c.approved_date.strftime('%Y-%m-%d') if c.approved_date else '',
            c.approved_by.get_full_name() if c.approved_by else '',
        ] for c in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('경비 청구 목록', headers, rows, money_columns=[4])


# ═══════════════════════════════════════════════════
# ESG
# ═══════════════════════════════════════════════════

class CarbonEmissionExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.esg.models import CarbonEmission
        qs = CarbonEmission.objects.filter(is_active=True).order_by('-period')
        headers = [
            ('배출원', 20), ('범위', 10), ('배출량(kg)', 15),
            ('기간', 12), ('시설', 20), ('비고', 25),
        ]
        rows = [[
            e.source,
            e.get_scope_display(),
            float(e.amount_kg),
            e.period.strftime('%Y-%m-%d') if e.period else '',
            e.facility or '',
            e.notes or '',
        ] for e in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('탄소 배출 내역', headers, rows)


class ComplianceExcelView(ExcelAuditMixin, ManagerRequiredMixin, View):
    def get(self, request):
        from apps.esg.models import ComplianceRequirement
        qs = ComplianceRequirement.objects.filter(is_active=True).select_related(
            'responsible',
        ).order_by('-due_date')
        headers = [
            ('요구사항명', 25), ('규정', 20), ('상태', 10),
            ('기한', 12), ('담당자', 12), ('비고', 25),
        ]
        rows = [[
            c.name,
            c.regulation or '',
            c.get_status_display(),
            c.due_date.strftime('%Y-%m-%d') if c.due_date else '',
            c.responsible.get_full_name() if c.responsible else '',
            c.notes or '',
        ] for c in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('컴플라이언스 요구사항', headers, rows)


# ═══════════════════════════════════════════════════
# WMS — 창고구역, 보관위치, 피킹오더, 적치작업
# ═══════════════════════════════════════════════════

class WmsZoneExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.wms.models import WarehouseZone
        qs = WarehouseZone.objects.filter(is_active=True).select_related(
            'warehouse',
        ).order_by('code')
        headers = [
            ('코드', 12), ('구역명', 20), ('창고', 15),
            ('유형', 12), ('비고', 25),
        ]
        rows = [[
            z.code, z.name,
            z.warehouse.name if z.warehouse else '',
            z.get_zone_type_display(),
            z.notes or '',
        ] for z in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('창고구역 목록', headers, rows)


class WmsPickOrderExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.wms.models import PickOrder
        qs = PickOrder.objects.filter(is_active=True).select_related(
            'order', 'assigned_to',
        ).order_by('-created_at')
        headers = [
            ('피킹번호', 15), ('주문', 15), ('상태', 10),
            ('우선순위', 10), ('담당자', 12), ('생성일', 12),
        ]
        rows = [[
            str(p.pk),
            str(p.order) if p.order else '',
            p.get_status_display(),
            p.get_priority_display(),
            p.assigned_to.get_full_name() if p.assigned_to else '',
            p.created_at.strftime('%Y-%m-%d'),
        ] for p in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('피킹오더 목록', headers, rows)


class WmsPutAwayExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.wms.models import PutAwayTask
        qs = PutAwayTask.objects.filter(is_active=True).select_related(
            'product', 'suggested_bin', 'actual_bin', 'assigned_to',
        ).order_by('-created_at')
        headers = [
            ('제품', 20), ('수량', 10), ('상태', 10),
            ('제안위치', 12), ('실제위치', 12), ('담당자', 12),
        ]
        rows = [[
            p.product.name if p.product else '',
            float(p.quantity),
            p.get_status_display(),
            p.suggested_bin.code if p.suggested_bin else '',
            p.actual_bin.code if p.actual_bin else '',
            p.assigned_to.get_full_name() if p.assigned_to else '',
        ] for p in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('적치작업 목록', headers, rows)


# ═══════════════════════════════════════════════════
# CMMS — 설비, 보전스케줄, 작업지시, 예비부품
# ═══════════════════════════════════════════════════

class EquipmentExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.cmms.models import Equipment
        qs = Equipment.objects.filter(is_active=True).select_related(
            'department',
        ).order_by('code')
        headers = [
            ('코드', 12), ('설비명', 20), ('상태', 10),
            ('부서', 15), ('모델번호', 15), ('구입일', 12),
        ]
        rows = [[
            e.code, e.name,
            e.get_status_display(),
            e.department.name if e.department else '',
            e.model_number or '',
            e.purchase_date.strftime('%Y-%m-%d') if e.purchase_date else '',
        ] for e in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('설비 목록', headers, rows)


class MaintenanceWorkOrderExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.cmms.models import MaintenanceWorkOrder
        qs = MaintenanceWorkOrder.objects.filter(is_active=True).select_related(
            'equipment', 'assigned_to',
        ).order_by('-created_at')
        headers = [
            ('작업번호', 15), ('설비', 20), ('우선순위', 10),
            ('상태', 10), ('담당자', 12), ('생성일', 12),
        ]
        rows = [[
            w.wo_number, w.equipment.name if w.equipment else '',
            w.get_priority_display(),
            w.get_status_display(),
            w.assigned_to.get_full_name() if w.assigned_to else '',
            w.created_at.strftime('%Y-%m-%d'),
        ] for w in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('보전 작업지시', headers, rows)


class SparePartExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.cmms.models import SparePart
        qs = SparePart.objects.filter(is_active=True).order_by('code')
        headers = [
            ('코드', 12), ('부품명', 20), ('현재고', 10),
            ('최소재고', 10), ('단가', 12), ('비고', 25),
        ]
        rows = [[
            s.code, s.name,
            float(s.current_stock),
            float(s.min_stock),
            int(s.unit_cost or 0),
            s.notes or '',
        ] for s in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('예비부품 목록', headers, rows, money_columns=[4])


# ═══════════════════════════════════════════════════
# PLM — 제품버전, ECN, 도면
# ═══════════════════════════════════════════════════

class ProductVersionExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.plm.models import ProductVersion
        qs = ProductVersion.objects.filter(is_active=True).select_related(
            'product',
        ).order_by('-created_at')
        headers = [
            ('제품', 20), ('버전', 10), ('상태', 10),
            ('변경사유', 30), ('생성일', 12),
        ]
        rows = [[
            v.product.name if v.product else '',
            v.version_number,
            v.get_status_display(),
            v.change_reason or '',
            v.created_at.strftime('%Y-%m-%d'),
        ] for v in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('제품버전 목록', headers, rows)


class ECNExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.plm.models import EngineeringChangeNotice
        qs = EngineeringChangeNotice.objects.filter(is_active=True).select_related(
            'requested_by',
        ).order_by('-created_at')
        headers = [
            ('ECN번호', 15), ('제목', 25), ('상태', 10),
            ('우선순위', 10), ('요청자', 12), ('생성일', 12),
        ]
        rows = [[
            e.ecn_number, e.title,
            e.get_status_display(),
            e.get_priority_display(),
            e.requested_by.get_full_name() if e.requested_by else '',
            e.created_at.strftime('%Y-%m-%d'),
        ] for e in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('ECN 목록', headers, rows)


# ═══════════════════════════════════════════════════
# QMS — 부적합, CAPA, 내부감사
# ═══════════════════════════════════════════════════

class NCExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.qms.models import NonConformance
        qs = NonConformance.objects.filter(is_active=True).select_related(
            'product', 'detected_by',
        ).order_by('-created_at')
        headers = [
            ('NC번호', 15), ('제목', 25), ('제품', 15),
            ('심각도', 10), ('상태', 10), ('발견자', 12),
            ('발견일', 12),
        ]
        rows = [[
            n.nc_number, n.title,
            n.product.name if n.product else '',
            n.get_severity_display(),
            n.get_status_display(),
            n.detected_by.get_full_name() if n.detected_by else '',
            n.created_at.strftime('%Y-%m-%d'),
        ] for n in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('부적합 목록', headers, rows)


class CAPAExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.qms.models import CAPA
        qs = CAPA.objects.filter(is_active=True).select_related(
            'nc', 'assigned_to',
        ).order_by('-created_at')
        headers = [
            ('CAPA번호', 15), ('유형', 10), ('부적합', 15),
            ('상태', 10), ('담당자', 12), ('기한', 12),
        ]
        rows = [[
            str(c.pk),
            c.get_type_display(),
            c.nc.nc_number if c.nc else '',
            c.get_status_display(),
            c.assigned_to.get_full_name() if c.assigned_to else '',
            c.due_date.strftime('%Y-%m-%d') if c.due_date else '',
        ] for c in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('CAPA 목록', headers, rows)


# ═══════════════════════════════════════════════════
# Forecast — 수요예측, S&OP
# ═══════════════════════════════════════════════════

class DemandForecastExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.forecast.models import DemandForecast
        qs = DemandForecast.objects.filter(is_active=True).select_related(
            'product',
        ).order_by('-period_start')
        headers = [
            ('제품', 20), ('예측방법', 12), ('기간시작', 12),
            ('기간종료', 12), ('예측수량', 12), ('실제수량', 12),
            ('정확도(%)', 10),
        ]
        rows = [[
            f.product.name if f.product else '',
            f.get_forecast_method_display(),
            f.period_start.strftime('%Y-%m-%d'),
            f.period_end.strftime('%Y-%m-%d'),
            float(f.forecast_qty),
            float(f.actual_qty),
            float(f.accuracy_pct) if f.accuracy_pct is not None else '',
        ] for f in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('수요예측 목록', headers, rows)


class SOPMeetingExcelView(ExcelAuditMixin, LoginRequiredMixin, View):
    def get(self, request):
        from apps.forecast.models import SOPMeeting
        qs = SOPMeeting.objects.filter(is_active=True).order_by('-meeting_date')
        headers = [
            ('제목', 25), ('회의일', 12), ('대상기간', 15),
            ('상태', 10), ('의사결정', 30),
        ]
        rows = [[
            m.title,
            m.meeting_date.strftime('%Y-%m-%d'),
            m.period,
            m.get_status_display(),
            m.decisions or '',
        ] for m in qs]
        self._excel_row_count = len(rows)
        return export_to_excel('S&OP 회의 목록', headers, rows)
