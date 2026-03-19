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
from reportlab.lib.pagesizes import A4
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
