"""
바코드/QR코드 생성 유틸리티
"""
import base64
import io

import barcode
from barcode.writer import ImageWriter
import qrcode
from django.http import HttpResponse
from reportlab.lib.pagesizes import mm
from reportlab.lib.units import mm as mm_unit
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def generate_barcode_image(code, barcode_type='code128'):
    """바코드 이미지를 base64 인코딩된 PNG 문자열로 반환"""
    barcode_class = barcode.get_barcode_class(barcode_type)
    barcode_instance = barcode_class(str(code), writer=ImageWriter())
    buffer = io.BytesIO()
    barcode_instance.write(buffer, options={
        'module_width': 0.4,
        'module_height': 15.0,
        'font_size': 10,
        'text_distance': 5.0,
        'quiet_zone': 6.5,
    })
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


def generate_qr_image(data):
    """QR코드 이미지를 base64 인코딩된 PNG 문자열로 반환"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


def generate_barcode_label_pdf(product, request=None):
    """제품 바코드 라벨 PDF를 HttpResponse로 반환 (60mm x 40mm 라벨)"""
    from django.urls import reverse

    label_width = 60 * mm_unit
    label_height = 40 * mm_unit

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="barcode_{product.code}.pdf"'
    )

    c = canvas.Canvas(response, pagesize=(label_width, label_height))

    # 제품명
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(label_width / 2, label_height - 8 * mm_unit, product.name[:20])

    # 제품코드
    c.setFont('Helvetica', 7)
    c.drawCentredString(label_width / 2, label_height - 12 * mm_unit, f'Code: {product.code}')

    # 바코드 이미지
    barcode_class = barcode.get_barcode_class('code128')
    barcode_instance = barcode_class(str(product.code), writer=ImageWriter())
    barcode_buffer = io.BytesIO()
    barcode_instance.write(barcode_buffer, options={
        'module_width': 0.3,
        'module_height': 10.0,
        'font_size': 7,
        'text_distance': 3.0,
        'quiet_zone': 3.0,
    })
    barcode_buffer.seek(0)
    barcode_img = ImageReader(barcode_buffer)
    c.drawImage(
        barcode_img,
        5 * mm_unit, 5 * mm_unit,
        width=50 * mm_unit, height=18 * mm_unit,
        preserveAspectRatio=True,
        anchor='c',
    )

    # 가격
    c.setFont('Helvetica', 6)
    price_str = f'{int(product.unit_price):,}원'
    c.drawCentredString(label_width / 2, 3 * mm_unit, price_str)

    c.showPage()
    c.save()
    return response
