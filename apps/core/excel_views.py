"""전체 앱 Excel 내보내기 뷰 — 모든 데이터를 이쁘게 Excel로 출력"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

from apps.core.excel import export_to_excel


# ═══════════════════════════════════════════════════
# 영업 — 거래처, 고객, 견적, 배송
# ═══════════════════════════════════════════════════

class PartnerExcelView(LoginRequiredMixin, View):
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


class CustomerExcelView(LoginRequiredMixin, View):
    def get(self, request):
        from apps.sales.models import Customer
        qs = Customer.objects.filter(is_active=True).select_related('product')
        headers = [
            ('고객명', 15), ('연락처', 16), ('이메일', 22), ('주소', 30),
            ('구매일', 12), ('구매제품', 20), ('시리얼번호', 18), ('보증만료', 12),
        ]
        rows = [[
            c.name, c.phone, c.email, c.address,
            c.purchase_date.strftime('%Y-%m-%d') if c.purchase_date else '',
            c.product.name if c.product else '',
            c.serial_number, c.warranty_end.strftime('%Y-%m-%d') if c.warranty_end else '',
        ] for c in qs]
        return export_to_excel('고객 목록', headers, rows)


class QuotationExcelView(LoginRequiredMixin, View):
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


class ShipmentExcelView(LoginRequiredMixin, View):
    def get(self, request):
        from apps.sales.models import Shipment
        qs = Shipment.objects.filter(is_active=True).select_related('order')
        headers = [
            ('배송번호', 18), ('주문번호', 18), ('택배사', 10), ('송장번호', 18),
            ('상태', 10), ('발송일', 12), ('수령인', 12), ('수령인 연락처', 16),
        ]
        rows = [[
            s.shipment_number, s.order.order_number, s.get_carrier_display(),
            s.tracking_number, s.get_status_display(),
            s.shipped_date.strftime('%Y-%m-%d') if s.shipped_date else '',
            s.receiver_name, s.receiver_phone,
        ] for s in qs]
        return export_to_excel('배송 목록', headers, rows)


# ═══════════════════════════════════════════════════
# 재고 — 입출고, 재고현황, 창고이동
# ═══════════════════════════════════════════════════

class StockMovementExcelView(LoginRequiredMixin, View):
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


class StockStatusExcelView(LoginRequiredMixin, View):
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


class StockTransferExcelView(LoginRequiredMixin, View):
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

class BOMExcelView(LoginRequiredMixin, View):
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


class ProductionPlanExcelView(LoginRequiredMixin, View):
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


class WorkOrderExcelView(LoginRequiredMixin, View):
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


class ProductionRecordExcelView(LoginRequiredMixin, View):
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

class PurchaseOrderExcelView(LoginRequiredMixin, View):
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


class GoodsReceiptExcelView(LoginRequiredMixin, View):
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


# ═══════════════════════════════════════════════════
# 회계
# ═══════════════════════════════════════════════════

class TaxInvoiceExcelView(LoginRequiredMixin, View):
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


class VoucherExcelView(LoginRequiredMixin, View):
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
            l.voucher.voucher_number, l.voucher.get_voucher_type_display(),
            l.voucher.voucher_date.strftime('%Y-%m-%d'),
            l.voucher.get_approval_status_display(),
            l.voucher.description, l.account.code, l.account.name,
            int(l.debit), int(l.credit),
        ] for l in lines]
        return export_to_excel('전표 상세', headers, rows, money_columns=[7, 8])


class AccountCodeExcelView(LoginRequiredMixin, View):
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


class FixedCostExcelView(LoginRequiredMixin, View):
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


class ARExcelView(LoginRequiredMixin, View):
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


class APExcelView(LoginRequiredMixin, View):
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


class ApprovalExcelView(LoginRequiredMixin, View):
    def get(self, request):
        from apps.accounting.models import ApprovalRequest
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


class WithholdingTaxExcelView(LoginRequiredMixin, View):
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

class InvestorExcelView(LoginRequiredMixin, View):
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


class InvestmentRoundExcelView(LoginRequiredMixin, View):
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


class DistributionExcelView(LoginRequiredMixin, View):
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

class WarrantyExcelView(LoginRequiredMixin, View):
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

class MarketplaceOrderExcelView(LoginRequiredMixin, View):
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

class InquiryExcelView(LoginRequiredMixin, View):
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

class ServiceRequestExcelView(LoginRequiredMixin, View):
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

class EmployeeExcelView(LoginRequiredMixin, View):
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


class DepartmentExcelView(LoginRequiredMixin, View):
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


class PersonnelActionExcelView(LoginRequiredMixin, View):
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

class AttendanceExcelView(LoginRequiredMixin, View):
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


class LeaveRequestExcelView(LoginRequiredMixin, View):
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


class LeaveBalanceExcelView(LoginRequiredMixin, View):
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

class PostExcelView(LoginRequiredMixin, View):
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

class AdCampaignExcelView(LoginRequiredMixin, View):
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


class AdPerformanceExcelView(LoginRequiredMixin, View):
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


class AdBudgetExcelView(LoginRequiredMixin, View):
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

class CommissionExcelView(LoginRequiredMixin, View):
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
