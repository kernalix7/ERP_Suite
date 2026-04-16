"""
PDF generation utilities for Korean ERP documents.

Supports:
- 세금계산서 (Tax Invoice)
- 견적서 (Quotation)
- 발주서 (Purchase Order)

Uses ReportLab with NanumGothic Korean font.
"""
import io
import os
from datetime import date

from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)

# ---------------------------------------------------------------------------
# Font registration
# ---------------------------------------------------------------------------
_FONT_REGISTERED = False
FONT_NAME = 'Helvetica'  # fallback
FONT_NAME_BOLD = 'Helvetica-Bold'

_KOREAN_FONT_PATHS = [
    '/usr/share/fonts/truetype/NanumGothic.ttf',
    '/usr/share/fonts/truetype/NanumGothicBold.ttf',
    '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
    '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
    '/usr/share/fonts/nanum-fonts/NanumGothic.ttf',
    '/usr/share/fonts/nanum-fonts/NanumGothicBold.ttf',
]


def _register_korean_font():
    """Register Korean font if available on the system."""
    global _FONT_REGISTERED, FONT_NAME, FONT_NAME_BOLD

    if _FONT_REGISTERED:
        return

    regular_path = None
    bold_path = None

    for path in _KOREAN_FONT_PATHS:
        if os.path.isfile(path):
            if 'Bold' in path:
                bold_path = path
            else:
                regular_path = path

    if regular_path:
        try:
            pdfmetrics.registerFont(TTFont('NanumGothic', regular_path))
            FONT_NAME = 'NanumGothic'
            if bold_path:
                pdfmetrics.registerFont(TTFont('NanumGothicBold', bold_path))
                FONT_NAME_BOLD = 'NanumGothicBold'
            else:
                FONT_NAME_BOLD = 'NanumGothic'
        except (OSError, IOError, ValueError):
            pass  # fall back to Helvetica

    _FONT_REGISTERED = True


def _get_font():
    _register_korean_font()
    return FONT_NAME


def _get_font_bold():
    _register_korean_font()
    return FONT_NAME_BOLD


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def format_won(amount):
    """Format a number as Korean Won with comma separators."""
    try:
        value = int(amount)
    except (TypeError, ValueError):
        return '0'
    return f'{value:,}'


# ---------------------------------------------------------------------------
# Company header configuration
# ---------------------------------------------------------------------------
# Override these in Django settings as PDF_COMPANY_NAME, PDF_COMPANY_INFO, etc.
def _get_company_name():
    try:
        from django.conf import settings
        return getattr(settings, 'PDF_COMPANY_NAME', 'ERP Suite')
    except (AttributeError, ImportError):
        return 'ERP Suite'


def _get_company_info():
    try:
        from django.conf import settings
        return getattr(settings, 'PDF_COMPANY_INFO', '')
    except (AttributeError, ImportError):
        return ''


# ---------------------------------------------------------------------------
# Common styles
# ---------------------------------------------------------------------------
def _build_styles():
    """Build paragraph styles for PDF documents."""
    _register_korean_font()
    font = _get_font()
    font_bold = _get_font_bold()

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'KorTitle',
        fontName=font_bold,
        fontSize=18,
        leading=22,
        alignment=1,  # center
        spaceAfter=6 * mm,
    ))
    styles.add(ParagraphStyle(
        'KorSubTitle',
        fontName=font_bold,
        fontSize=12,
        leading=16,
        spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        'KorNormal',
        fontName=font,
        fontSize=9,
        leading=12,
    ))
    styles.add(ParagraphStyle(
        'KorSmall',
        fontName=font,
        fontSize=8,
        leading=10,
    ))
    styles.add(ParagraphStyle(
        'KorRight',
        fontName=font,
        fontSize=9,
        leading=12,
        alignment=2,  # right
    ))
    return styles


# ---------------------------------------------------------------------------
# Common building blocks
# ---------------------------------------------------------------------------
HEADER_BG = colors.HexColor('#1F4E79')
HEADER_FG = colors.white
LINE_COLOR = colors.HexColor('#D9D9D9')
ALT_ROW_BG = colors.HexColor('#F2F7FB')


def _company_header(styles, doc_title):
    """Return elements for the common company header."""
    elements = []
    elements.append(Paragraph(doc_title, styles['KorTitle']))
    company = _get_company_name()
    info = _get_company_info()
    if company:
        elements.append(Paragraph(company, styles['KorSubTitle']))
    if info:
        elements.append(Paragraph(info, styles['KorSmall']))
    elements.append(Spacer(1, 4 * mm))
    return elements


def _info_table(rows_data, col_widths=None):
    """Build a key-value info table (label | value pairs)."""
    font = _get_font()
    font_bold = _get_font_bold()

    if col_widths is None:
        col_widths = [30 * mm, 70 * mm, 30 * mm, 70 * mm]

    table = Table(rows_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
        ('FONTNAME', (0, 0), (0, -1), font_bold),
        ('FONTNAME', (2, 0), (2, -1), font_bold),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#F5F5F5')),
        ('GRID', (0, 0), (-1, -1), 0.5, LINE_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return table


def _items_table(headers, rows):
    """Build a styled data table with header row and alternating row colors."""
    font = _get_font()
    font_bold = _get_font_bold()

    data = [headers] + rows
    table = Table(data, repeatRows=1)

    style_commands = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), HEADER_FG),
        ('FONTNAME', (0, 0), (-1, 0), font_bold),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGNMENT', (0, 0), (-1, 0), 'CENTER'),
        # Body
        ('FONTNAME', (0, 1), (-1, -1), font),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, LINE_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]

    # Alternate row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(('BACKGROUND', (0, i), (-1, i), ALT_ROW_BG))

    table.setStyle(TableStyle(style_commands))
    return table


def _summary_table(rows_data, col_widths=None):
    """Build a right-aligned summary table (e.g. totals)."""
    font = _get_font()
    font_bold = _get_font_bold()

    if col_widths is None:
        col_widths = [50 * mm, 50 * mm]

    table = Table(rows_data, colWidths=col_widths, hAlign='RIGHT')
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), font_bold),
        ('FONTNAME', (1, 0), (1, -1), font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGNMENT', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, LINE_COLOR),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return table


def _build_pdf(elements, filename):
    """Render elements to an HttpResponse PDF attachment."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    doc.build(elements)
    buf.seek(0)

    response = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ===========================================================================
# 1) 세금계산서 (Tax Invoice) PDF
# ===========================================================================
def generate_tax_invoice_pdf(invoice):
    """
    Generate a Korean tax invoice PDF from a TaxInvoice model instance.

    Args:
        invoice: accounting.TaxInvoice instance

    Returns:
        HttpResponse with PDF attachment
    """
    styles = _build_styles()
    elements = []

    # Title
    type_label = '매출' if invoice.invoice_type == 'SALES' else '매입'
    elements += _company_header(styles, f'세금계산서 ({type_label})')

    # Issue info
    elements.append(Paragraph(
        f'발행일: {invoice.issue_date.strftime("%Y-%m-%d")}',
        styles['KorRight'],
    ))
    elements.append(Spacer(1, 3 * mm))

    # Invoice info table
    partner = invoice.partner
    info_rows = [
        ['세금계산서번호', invoice.invoice_number, '유형', type_label],
        ['거래처명', partner.name if partner else '', '사업자번호', partner.business_number if partner else ''],
        ['대표자', partner.representative if partner else '', '주소', partner.address if partner else ''],
    ]
    elements.append(_info_table(info_rows))
    elements.append(Spacer(1, 5 * mm))

    # Amount summary
    summary_rows = [
        ['공급가액', f'{format_won(invoice.supply_amount)} 원'],
        ['부가세', f'{format_won(invoice.tax_amount)} 원'],
        ['합계금액', f'{format_won(invoice.total_amount)} 원'],
    ]
    elements.append(_summary_table(summary_rows))
    elements.append(Spacer(1, 5 * mm))

    # Description
    if invoice.description:
        elements.append(Paragraph('적요', styles['KorSubTitle']))
        elements.append(Paragraph(invoice.description, styles['KorNormal']))
        elements.append(Spacer(1, 5 * mm))

    # If linked to an order with items, show line items
    if invoice.order:
        order_items = invoice.order.items.select_related('product').all()
        if order_items.exists():
            elements.append(Paragraph('품목 내역', styles['KorSubTitle']))
            headers = ['No', '품명', '수량', '단가', '공급가액', '부가세', '합계']
            rows = []
            for idx, item in enumerate(order_items, 1):
                rows.append([
                    str(idx),
                    item.product.name,
                    f'{item.quantity:,}',
                    f'{format_won(item.unit_price)}',
                    f'{format_won(item.amount)}',
                    f'{format_won(item.tax_amount)}',
                    f'{format_won(item.total_with_tax)}',
                ])
            elements.append(_items_table(headers, rows))

    # Footer
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        f'출력일: {date.today().strftime("%Y-%m-%d")}',
        styles['KorSmall'],
    ))

    filename = f'tax_invoice_{invoice.invoice_number}_{date.today().strftime("%Y%m%d")}.pdf'
    return _build_pdf(elements, filename)


# ===========================================================================
# 2) 견적서 (Quotation) PDF
# ===========================================================================
def generate_quotation_pdf(order):
    """
    Generate a Korean quotation (견적서) PDF from an Order model instance.

    Args:
        order: sales.Order instance

    Returns:
        HttpResponse with PDF attachment
    """
    styles = _build_styles()
    elements = []

    # Title
    elements += _company_header(styles, '견 적 서')

    # Date
    elements.append(Paragraph(
        f'견적일: {order.order_date.strftime("%Y-%m-%d") if order.order_date else ""}',
        styles['KorRight'],
    ))
    elements.append(Spacer(1, 3 * mm))

    # Info table
    partner = order.partner
    info_rows = [
        ['주문번호', order.order_number, '견적일', order.order_date.strftime('%Y-%m-%d') if order.order_date else ''],
        ['거래처명', partner.name if partner else '', '사업자번호', partner.business_number if partner else ''],
        ['대표자', partner.representative if partner else '', '주소', partner.address if partner else ''],
    ]
    if order.customer:
        info_rows.append(['고객명', order.customer.name, '연락처', order.customer.phone or ''])
    elements.append(_info_table(info_rows))
    elements.append(Spacer(1, 5 * mm))

    # Items table
    items = order.items.select_related('product').all()
    if items.exists():
        elements.append(Paragraph('품목 내역', styles['KorSubTitle']))
        headers = ['No', '품명', '수량', '단가', '공급가액', '부가세', '합계']
        rows = []
        for idx, item in enumerate(items, 1):
            rows.append([
                str(idx),
                item.product.name,
                f'{item.quantity:,}',
                f'{format_won(item.unit_price)}',
                f'{format_won(item.amount)}',
                f'{format_won(item.tax_amount)}',
                f'{format_won(item.total_with_tax)}',
            ])
        elements.append(_items_table(headers, rows))
        elements.append(Spacer(1, 5 * mm))

    # Summary
    summary_rows = [
        ['공급가액', f'{format_won(order.total_amount)} 원'],
        ['부가세', f'{format_won(order.tax_total)} 원'],
        ['총합계', f'{format_won(order.grand_total)} 원'],
    ]
    elements.append(_summary_table(summary_rows))

    # Footer
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        '상기 금액을 견적합니다.',
        styles['KorNormal'],
    ))
    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph(
        f'{date.today().strftime("%Y년 %m월 %d일")}',
        styles['KorRight'],
    ))
    elements.append(Paragraph(
        f'{_get_company_name()}',
        styles['KorRight'],
    ))
    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph(
        f'출력일: {date.today().strftime("%Y-%m-%d")}',
        styles['KorSmall'],
    ))

    filename = f'quotation_{order.order_number}_{date.today().strftime("%Y%m%d")}.pdf'
    return _build_pdf(elements, filename)


# ===========================================================================
# 3) 발주서 (Purchase Order) PDF
# ===========================================================================
def generate_purchase_order_pdf(order):
    """
    Generate a Korean purchase order (발주서) PDF from an Order model instance.

    Args:
        order: sales.Order instance

    Returns:
        HttpResponse with PDF attachment
    """
    styles = _build_styles()
    elements = []

    # Title
    elements += _company_header(styles, '발 주 서')

    # Date
    elements.append(Paragraph(
        f'발주일: {order.order_date.strftime("%Y-%m-%d") if order.order_date else ""}',
        styles['KorRight'],
    ))
    elements.append(Spacer(1, 3 * mm))

    # Info table
    partner = order.partner
    info_rows = [
        ['주문번호', order.order_number, '발주일', order.order_date.strftime('%Y-%m-%d') if order.order_date else ''],
        ['거래처명', partner.name if partner else '', '사업자번호', partner.business_number if partner else ''],
        ['대표자', partner.representative if partner else '', '주소', partner.address if partner else ''],
    ]
    if order.delivery_date:
        info_rows.append(['납기일', order.delivery_date.strftime('%Y-%m-%d'), '', ''])
    if order.customer:
        info_rows.append(['고객명', order.customer.name, '연락처', order.customer.phone or ''])
    elements.append(_info_table(info_rows))
    elements.append(Spacer(1, 5 * mm))

    # Items table
    items = order.items.select_related('product').all()
    if items.exists():
        elements.append(Paragraph('품목 내역', styles['KorSubTitle']))
        headers = ['No', '품명', '수량', '단가', '공급가액', '부가세', '합계']
        rows = []
        for idx, item in enumerate(items, 1):
            rows.append([
                str(idx),
                item.product.name,
                f'{item.quantity:,}',
                f'{format_won(item.unit_price)}',
                f'{format_won(item.amount)}',
                f'{format_won(item.tax_amount)}',
                f'{format_won(item.total_with_tax)}',
            ])
        elements.append(_items_table(headers, rows))
        elements.append(Spacer(1, 5 * mm))

    # Summary
    summary_rows = [
        ['공급가액', f'{format_won(order.total_amount)} 원'],
        ['부가세', f'{format_won(order.tax_total)} 원'],
        ['총합계', f'{format_won(order.grand_total)} 원'],
    ]
    elements.append(_summary_table(summary_rows))

    # Footer
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        '상기와 같이 발주합니다.',
        styles['KorNormal'],
    ))
    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph(
        f'{date.today().strftime("%Y년 %m월 %d일")}',
        styles['KorRight'],
    ))
    elements.append(Paragraph(
        f'{_get_company_name()}',
        styles['KorRight'],
    ))
    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph(
        f'출력일: {date.today().strftime("%Y-%m-%d")}',
        styles['KorSmall'],
    ))

    filename = f'purchase_order_{order.order_number}_{date.today().strftime("%Y%m%d")}.pdf'
    return _build_pdf(elements, filename)


# ===========================================================================
# 4) 매출정산서 (Sales Settlement) PDF
# ===========================================================================

# Settlement-specific colors
_CARD_BLUE = colors.HexColor('#EFF6FF')
_CARD_RED = colors.HexColor('#FEF2F2')
_CARD_ORANGE = colors.HexColor('#FFF7ED')
_CARD_GREEN = colors.HexColor('#F0FDF4')
_CARD_GRAY = colors.HexColor('#F9FAFB')
_TEXT_RED = colors.HexColor('#DC2626')
_TEXT_ORANGE = colors.HexColor('#EA580C')
_TEXT_GREEN = colors.HexColor('#15803D')
_TEXT_BLUE = colors.HexColor('#2563EB')
_TEXT_GRAY = colors.HexColor('#374151')
_PASS_GREEN = colors.HexColor('#166534')
_FAIL_RED = colors.HexColor('#991B1B')
_BORDER_LIGHT = colors.HexColor('#E5E7EB')


def _settlement_summary_cards(settlement):
    """Build 2-row summary card grid mirroring the web UI (portrait A4)."""
    font = _get_font()
    font_bold = _get_font_bold()

    def _card(label, value, bg, text_color=_TEXT_GRAY):
        return [label, value, bg, text_color]

    cards_row1 = [
        _card('공급가액', f'{format_won(settlement.total_revenue)}원', _CARD_GRAY),
        _card('원가', f'{format_won(settlement.total_cost)}원', _CARD_GRAY),
        _card('배송비', f'{format_won(settlement.total_shipping)}원', _CARD_GRAY),
        _card('부가세', f'{format_won(settlement.total_tax)}원', _CARD_GRAY),
    ]
    cards_row2 = [
        _card('플랫폼 수수료', f'{format_won(settlement.total_platform_commission)}원',
              _CARD_RED, _TEXT_RED),
        _card('정산 수수료', f'{format_won(settlement.total_commission)}원',
              _CARD_ORANGE, _TEXT_ORANGE),
        _card('원가차이', f'{format_won(settlement.total_cost_variance)}원',
              _CARD_GRAY, _TEXT_RED if int(settlement.total_cost_variance) > 0 else _TEXT_GREEN),
        _card('순이익', f'{format_won(settlement.total_profit)}원 ({settlement.profit_rate}%)',
              _CARD_GREEN, _TEXT_GREEN if int(settlement.total_profit) >= 0 else _TEXT_RED),
    ]

    tables = []
    col_w = 45 * mm
    for row_cards in [cards_row1, cards_row2]:
        labels = [c[0] for c in row_cards]
        values = [c[1] for c in row_cards]
        data = [labels, values]
        t = Table(data, colWidths=[col_w] * 4)
        style_cmds = [
            ('FONTNAME', (0, 0), (-1, 0), font),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTNAME', (0, 1), (-1, 1), font_bold),
            ('FONTSIZE', (0, 1), (-1, 1), 10),
            ('ALIGNMENT', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]
        for i, c in enumerate(row_cards):
            bg, fg = c[2], c[3]
            style_cmds.append(('BACKGROUND', (i, 0), (i, -1), bg))
            style_cmds.append(('TEXTCOLOR', (i, 0), (i, 0), colors.HexColor('#6B7280')))
            style_cmds.append(('TEXTCOLOR', (i, 1), (i, 1), fg))
            style_cmds.append(('BOX', (i, 0), (i, -1), 0.5, _BORDER_LIGHT))
        t.setStyle(TableStyle(style_cmds))
        tables.append(t)
    return tables


def _settlement_verification_page(settlement, items_qs, styles):
    """Build multi-section verification (검증) page elements for portrait A4."""
    font = _get_font()
    font_bold = _get_font_bold()
    page_w = 180 * mm  # portrait A4 usable width

    elements = []
    elements.append(Paragraph('정산 검증 보고서', styles['KorTitle']))
    elements.append(Paragraph(
        f'{settlement.settlement_number} | {settlement.settlement_date.strftime("%Y-%m-%d")}',
        styles['KorRight'],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── Section 1: Formula definitions ──
    elements.append(Paragraph('1. 계산 공식', styles['KorSubTitle']))
    formulas = [
        ['매출이익', '= 공급가액 − 원가 − 배송비 − 플랫폼수수료'],
        ['정산수수료 (실입금)', '= (공급가액 − 플랫폼수수료) × 수수료율'],
        ['정산수수료 (이익)', '= (공급가액 − 플랫폼수수료 − 원가 − 배송비) × 수수료율'],
        ['순이익', '= 공급가액 − 원가 − 배송비 − 플랫폼수수료 − 정산수수료'],
        ['이익률', '= 순이익 ÷ 공급가액 × 100'],
    ]
    ft = Table(formulas, colWidths=[45 * mm, 135 * mm])
    ft.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), font_bold),
        ('FONTNAME', (1, 0), (1, -1), font),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (0, -1), HEADER_BG),
        ('GRID', (0, 0), (-1, -1), 0.5, LINE_COLOR),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(ft)
    elements.append(Spacer(1, 5 * mm))

    # ── Collect per-item data ──
    all_pass = True
    sum_revenue = sum_cost = sum_shipping = 0
    sum_platform = sum_commission = sum_profit = sum_tax = 0
    sum_cost_variance = 0
    item_data = []

    for item in items_qs:
        r = int(item.revenue)
        c = int(item.cost)
        cc = int(item.current_cost)
        s = int(item.shipping)
        p = int(item.platform_commission)
        e = int(item.commission)
        t = int(item.tax)
        cv = int(item.cost_variance)
        stored_profit = int(item.profit)
        calc_profit = r - c - s - p - e
        gross = r - c - s - p
        rate = float(item.commission_rate)

        # Commission base check (reverse-engineer)
        if rate > 0 and e > 0:
            implied_base = round(e / rate * 100)
            net_rev = max(r - p, 0)
            profit_base = max(net_rev - c - s, 0)
            if abs(implied_base - net_rev) <= 1:
                comm_mode = '실입금'
                comm_base_val = net_rev
            elif abs(implied_base - profit_base) <= 1:
                comm_mode = '매출이익'
                comm_base_val = profit_base
            else:
                comm_mode = '?'
                comm_base_val = implied_base
        else:
            comm_mode = '-'
            comm_base_val = 0

        ok = calc_profit == stored_profit
        if not ok:
            all_pass = False

        sum_revenue += r
        sum_cost += c
        sum_shipping += s
        sum_platform += p
        sum_commission += e
        sum_profit += stored_profit
        sum_tax += t
        sum_cost_variance += cv

        item_data.append({
            'order': item.order.order_number,
            'r': r, 'c': c, 'cc': cc, 's': s, 'p': p,
            'e': e, 't': t, 'cv': cv, 'rate': rate,
            'stored_profit': stored_profit, 'calc_profit': calc_profit,
            'gross': gross, 'comm_mode': comm_mode,
            'comm_base': comm_base_val, 'ok': ok,
        })

    # ── Section 2: Per-order profit verification ──
    elements.append(Paragraph('2. 건별 이익 검증 (A−B−C−D−E = 순이익)', styles['KorSubTitle']))
    headers2 = ['No', '주문번호', 'A 공급가액', 'B 원가', 'C 배송비',
                'D 플랫폼', 'E 정산', '계산값', '저장값', '결과']
    rows2 = []
    for idx, d in enumerate(item_data, 1):
        rows2.append([
            str(idx), d['order'],
            format_won(d['r']), format_won(d['c']), format_won(d['s']),
            format_won(d['p']), format_won(d['e']),
            format_won(d['calc_profit']), format_won(d['stored_profit']),
            'OK' if d['ok'] else 'FAIL',
        ])
    cw2 = [7*mm, 27*mm, 20*mm, 18*mm, 16*mm, 16*mm, 16*mm, 20*mm, 20*mm, 12*mm]
    t2 = _items_table(headers2, rows2)
    t2._colWidths = cw2
    # Color result column
    for i in range(len(rows2)):
        clr = _PASS_GREEN if rows2[i][-1] == 'OK' else _FAIL_RED
        t2.setStyle(TableStyle([('TEXTCOLOR', (9, i+1), (9, i+1), clr)]))
    elements.append(t2)
    elements.append(Spacer(1, 5 * mm))

    # ── Section 3: Commission calculation verification ──
    elements.append(Paragraph('3. 수수료 계산 검증', styles['KorSubTitle']))
    headers3 = ['No', '주문번호', '수수료율', '기준', '산출근거',
                '계산값', '저장값', '결과']
    rows3 = []
    for idx, d in enumerate(item_data, 1):
        rate = d['rate']
        if rate > 0:
            calc_comm = round(d['comm_base'] * rate / 100)
            ok3 = abs(calc_comm - d['e']) <= 1  # rounding tolerance
        else:
            calc_comm = 0
            ok3 = d['e'] == 0
        if not ok3:
            all_pass = False
        basis_str = f'{format_won(d["comm_base"])}원'
        rows3.append([
            str(idx), d['order'],
            f'{rate}%', d['comm_mode'], basis_str,
            format_won(calc_comm), format_won(d['e']),
            'OK' if ok3 else 'FAIL',
        ])
    cw3 = [7*mm, 27*mm, 16*mm, 16*mm, 32*mm, 22*mm, 22*mm, 12*mm]
    t3 = _items_table(headers3, rows3)
    t3._colWidths = cw3
    for i in range(len(rows3)):
        clr = _PASS_GREEN if rows3[i][-1] == 'OK' else _FAIL_RED
        t3.setStyle(TableStyle([('TEXTCOLOR', (7, i+1), (7, i+1), clr)]))
    elements.append(t3)
    elements.append(Spacer(1, 5 * mm))

    # ── Section 4: Cost variance verification ──
    elements.append(Paragraph('4. 원가차이 검증 (정산시점 − 주문시점)', styles['KorSubTitle']))
    headers4 = ['No', '주문번호', '주문시점 원가', '정산시점 원가',
                '차이 계산', '저장 차이', '결과']
    rows4 = []
    for idx, d in enumerate(item_data, 1):
        calc_cv = d['cc'] - d['c']
        ok4 = calc_cv == d['cv']
        if not ok4:
            all_pass = False
        rows4.append([
            str(idx), d['order'],
            f'{format_won(d["c"])}원', f'{format_won(d["cc"])}원',
            f'{format_won(calc_cv)}원', f'{format_won(d["cv"])}원',
            'OK' if ok4 else 'FAIL',
        ])
    cw4 = [7*mm, 27*mm, 28*mm, 28*mm, 28*mm, 28*mm, 12*mm]
    t4 = _items_table(headers4, rows4)
    t4._colWidths = cw4
    for i in range(len(rows4)):
        clr = _PASS_GREEN if rows4[i][-1] == 'OK' else _FAIL_RED
        t4.setStyle(TableStyle([('TEXTCOLOR', (6, i+1), (6, i+1), clr)]))
    elements.append(t4)
    elements.append(Spacer(1, 5 * mm))

    # ── Section 5: Totals cross-check ──
    elements.append(Paragraph('5. 합계 검증 (건별 합산 vs 정산 저장 값)', styles['KorSubTitle']))

    def _check(label, calc, stored):
        ok = calc == stored
        return [
            label,
            f'{format_won(calc)} 원',
            f'{format_won(stored)} 원',
            'OK' if ok else f'FAIL ({format_won(calc - stored)})',
        ]

    check_rows = [
        ['항목', '건별 합산', '저장 값', '검증'],
        _check('공급가액', sum_revenue, int(settlement.total_revenue)),
        _check('원가', sum_cost, int(settlement.total_cost)),
        _check('배송비', sum_shipping, int(settlement.total_shipping)),
        _check('부가세', sum_tax, int(settlement.total_tax)),
        _check('플랫폼 수수료', sum_platform, int(settlement.total_platform_commission)),
        _check('정산 수수료', sum_commission, int(settlement.total_commission)),
        _check('원가차이', sum_cost_variance, int(settlement.total_cost_variance)),
        _check('순이익', sum_profit, int(settlement.total_profit)),
    ]

    totals_ok = all(r[3] == 'OK' for r in check_rows[1:])
    if not totals_ok:
        all_pass = False

    ct = Table(check_rows, colWidths=[35*mm, 45*mm, 45*mm, 55*mm])
    ct_style = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), HEADER_FG),
        ('FONTNAME', (0, 0), (-1, 0), font_bold),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (0, -1), font_bold),
        ('FONTNAME', (1, 1), (-1, -1), font),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGNMENT', (1, 0), (2, -1), 'RIGHT'),
        ('ALIGNMENT', (3, 0), (3, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, LINE_COLOR),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#F5F5F5')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(check_rows)):
        if check_rows[i][3] == 'OK':
            ct_style.append(('TEXTCOLOR', (3, i), (3, i), _PASS_GREEN))
        else:
            ct_style.append(('TEXTCOLOR', (3, i), (3, i), _FAIL_RED))
            ct_style.append(('FONTNAME', (3, i), (3, i), font_bold))
        if i % 2 == 0:
            ct_style.append(('BACKGROUND', (1, i), (-1, i), ALT_ROW_BG))
    ct.setStyle(TableStyle(ct_style))
    elements.append(ct)
    elements.append(Spacer(1, 5 * mm))

    # ── Section 6: Profit rate verification ──
    elements.append(Paragraph('6. 이익률 검증', styles['KorSubTitle']))
    s_rev = int(settlement.total_revenue)
    s_profit = int(settlement.total_profit)
    if s_rev > 0:
        calc_rate = round(s_profit / s_rev * 100, 1)
    else:
        calc_rate = 0.0
    stored_rate = settlement.profit_rate
    rate_ok = abs(calc_rate - stored_rate) < 0.15  # rounding tolerance
    if not rate_ok:
        all_pass = False

    rate_rows = [
        ['항목', '값'],
        ['총순이익', f'{format_won(s_profit)} 원'],
        ['총공급가액', f'{format_won(s_rev)} 원'],
        ['계산 이익률', f'{calc_rate}%'],
        ['저장 이익률', f'{stored_rate}%'],
        ['검증', 'OK' if rate_ok else f'FAIL (차이: {round(calc_rate - stored_rate, 2)}%)'],
    ]
    rt = Table(rate_rows, colWidths=[40*mm, 60*mm])
    rt_style = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), HEADER_FG),
        ('FONTNAME', (0, 0), (-1, 0), font_bold),
        ('FONTNAME', (0, 1), (0, -1), font_bold),
        ('FONTNAME', (1, 1), (1, -1), font),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGNMENT', (1, 1), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, LINE_COLOR),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#F5F5F5')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]
    last_i = len(rate_rows) - 1
    if rate_ok:
        rt_style.append(('TEXTCOLOR', (1, last_i), (1, last_i), _PASS_GREEN))
    else:
        rt_style.append(('TEXTCOLOR', (1, last_i), (1, last_i), _FAIL_RED))
    rt.setStyle(TableStyle(rt_style))
    elements.append(rt)
    elements.append(Spacer(1, 5 * mm))

    # ── Section 7: Final result banner ──
    elements.append(Paragraph('7. 최종 검증 결과', styles['KorSubTitle']))
    if all_pass:
        result_text = 'ALL PASS — 모든 계산이 정확합니다.'
        result_color = _PASS_GREEN
        result_bg = _CARD_GREEN
    else:
        result_text = 'FAIL — 불일치 항목이 있습니다. 위 표를 확인하세요.'
        result_color = _FAIL_RED
        result_bg = _CARD_RED

    banner = Table([[result_text]], colWidths=[page_w])
    banner.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_bold),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (-1, -1), result_color),
        ('BACKGROUND', (0, 0), (-1, -1), result_bg),
        ('ALIGNMENT', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, result_color),
    ]))
    elements.append(banner)

    return elements


def generate_settlement_pdf(settlement):
    """
    Generate a Korean sales settlement (매출정산서) PDF with verification page.

    Args:
        settlement: accounting.SalesSettlement instance

    Returns:
        HttpResponse with PDF attachment
    """
    from reportlab.platypus import PageBreak

    styles = _build_styles()
    elements = []
    items_qs = settlement.settlement_orders.select_related(
        'order__partner', 'order__customer',
    ).all()

    # ===== Page 1: Settlement Report =====
    elements += _company_header(styles, '매 출 정 산 서')
    elements.append(Paragraph(
        f'정산일: {settlement.settlement_date.strftime("%Y-%m-%d")}',
        styles['KorRight'],
    ))
    elements.append(Spacer(1, 3 * mm))

    # Info table (portrait widths)
    info_rows = [
        ['정산번호', settlement.settlement_number, '정산일',
         settlement.settlement_date.strftime('%Y-%m-%d')],
        ['정산 건수', f'{settlement.order_count}건', '이익률',
         f'{settlement.profit_rate}%'],
    ]
    if settlement.description:
        info_rows.append(['적요', settlement.description, '', ''])
    elements.append(_info_table(info_rows, col_widths=[25*mm, 65*mm, 25*mm, 65*mm]))
    elements.append(Spacer(1, 5 * mm))

    # Summary cards (2 rows, matching web UI)
    elements.append(Paragraph('정산 요약', styles['KorSubTitle']))
    for card_table in _settlement_summary_cards(settlement):
        elements.append(card_table)
        elements.append(Spacer(1, 2 * mm))
    elements.append(Spacer(1, 4 * mm))

    # Commission payment status
    if settlement.commission_paid:
        pay_info = f'수수료 지급완료: {format_won(settlement.commission_paid_amount)}원'
        if settlement.commission_paid_date:
            pay_info += f' ({settlement.commission_paid_date.strftime("%Y-%m-%d")})'
        elements.append(Paragraph(pay_info, styles['KorNormal']))
        elements.append(Spacer(1, 3 * mm))

    # Order items table (portrait: compact columns)
    if items_qs.exists():
        elements.append(Paragraph('정산 주문 내역', styles['KorSubTitle']))
        headers = [
            'No', '주문번호', '거래처', '고객', '공급가액', '원가',
            '배송비', '플랫폼', '수수료율', '정산수수료', '이익',
        ]
        rows = []
        for idx, item in enumerate(items_qs, 1):
            partner = item.order.partner
            customer = item.order.customer
            rows.append([
                str(idx),
                item.order.order_number,
                partner.name[:6] if partner else '-',
                customer.name[:4] if customer else '-',
                format_won(item.revenue),
                format_won(item.cost),
                format_won(item.shipping),
                format_won(item.platform_commission),
                f'{item.commission_rate}%',
                format_won(item.commission),
                format_won(item.profit),
            ])
        t = _items_table(headers, rows)
        t._colWidths = [
            7*mm, 26*mm, 17*mm, 13*mm, 19*mm, 17*mm,
            15*mm, 15*mm, 13*mm, 17*mm, 17*mm,
        ]
        elements.append(t)

    # Footer
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(
        f'출력일: {date.today().strftime("%Y-%m-%d")}',
        styles['KorSmall'],
    ))

    # ===== Page 2: Verification =====
    elements.append(PageBreak())
    elements += _settlement_verification_page(settlement, items_qs, styles)
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(
        f'출력일: {date.today().strftime("%Y-%m-%d")}',
        styles['KorSmall'],
    ))

    filename = f'settlement_{settlement.settlement_number}_{date.today().strftime("%Y%m%d")}.pdf'

    # Portrait A4
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    doc.build(elements)
    buf.seek(0)

    response = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
