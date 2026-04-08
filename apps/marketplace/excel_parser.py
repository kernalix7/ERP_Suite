"""
스토어 엑셀 파서 — 네이버/쿠팡 주문 Excel을 표준 dict 리스트로 변환
"""
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

NAVER_MAP = {
    '상품주문번호': 'store_order_id',
    '주문번호': 'platform_order_id',
    '상품명': 'product_name',
    '옵션정보': 'option_name',
    '옵션': 'option_name',
    '수량': 'quantity',
    '상품별 총 주문금액': 'price',
    '총 주문금액': 'price',
    '상품금액': 'price',
    '결제금액': 'price',
    '구매자명': 'buyer_name',
    '구매자ID': 'buyer_id',
    '구매자연락처': 'buyer_phone',
    '수취인명': 'receiver_name',
    '수취인연락처1': 'receiver_phone',
    '수취인연락처2': 'receiver_phone2',
    '배송지': 'receiver_address',
    '배송지 주소': 'receiver_address',
    '우편번호': 'receiver_zipcode',
    '주문상태': 'status',
    '상세주문상태': 'status_detail',
    '결제일': 'ordered_at',
    '주문일': 'ordered_at',
    '결제일시': 'ordered_at',
    '택배사': 'delivery_company',
    '송장번호': 'tracking_number',
    '발송일': 'shipped_at',
}

COUPANG_MAP = {
    '주문번호': 'store_order_id',
    '묶음배송번호': 'platform_order_id',
    '상품명': 'product_name',
    '노출상품명': 'product_name',
    '옵션': 'option_name',
    '옵션명': 'option_name',
    '옵션정보': 'option_name',
    '수량': 'quantity',
    '주문금액': 'price',
    '결제금액': 'price',
    '판매가': 'price',
    '주문자': 'buyer_name',
    '구매자': 'buyer_name',
    '주문자 연락처': 'buyer_phone',
    '구매자 연락처': 'buyer_phone',
    '수취인': 'receiver_name',
    '수취인명': 'receiver_name',
    '수취인 연락처': 'receiver_phone',
    '수취인연락처': 'receiver_phone',
    '수취인 주소': 'receiver_address',
    '배송지 주소': 'receiver_address',
    '배송지': 'receiver_address',
    '우편번호': 'receiver_zipcode',
    '주문상태': 'status',
    '주문일시': 'ordered_at',
    '결제일': 'ordered_at',
    '택배사': 'delivery_company',
    '운송장번호': 'tracking_number',
    '송장번호': 'tracking_number',
    '배송메시지': 'delivery_message',
}

# 기타/범용 컬럼 매핑
GENERIC_MAP = {
    'store_order_id': 'store_order_id',
    '스토어주문번호': 'store_order_id',
    '주문번호': 'store_order_id',
    '상품주문번호': 'store_order_id',
    'product_name': 'product_name',
    '상품명': 'product_name',
    'option_name': 'option_name',
    '옵션': 'option_name',
    '옵션명': 'option_name',
    '옵션정보': 'option_name',
    'quantity': 'quantity',
    '수량': 'quantity',
    'price': 'price',
    '결제금액': 'price',
    '금액': 'price',
    '판매가': 'price',
    '주문금액': 'price',
    '상품금액': 'price',
    'buyer_name': 'buyer_name',
    '주문자': 'buyer_name',
    '구매자명': 'buyer_name',
    '구매자': 'buyer_name',
    'buyer_phone': 'buyer_phone',
    '주문자연락처': 'buyer_phone',
    '구매자연락처': 'buyer_phone',
    '주문자 연락처': 'buyer_phone',
    '구매자 연락처': 'buyer_phone',
    'receiver_name': 'receiver_name',
    '수취인': 'receiver_name',
    '수취인명': 'receiver_name',
    'receiver_phone': 'receiver_phone',
    '수취인연락처': 'receiver_phone',
    '수취인연락처1': 'receiver_phone',
    '수취인 연락처': 'receiver_phone',
    'receiver_address': 'receiver_address',
    '배송주소': 'receiver_address',
    '배송지': 'receiver_address',
    '배송지 주소': 'receiver_address',
    '수취인 주소': 'receiver_address',
    'receiver_zipcode': 'receiver_zipcode',
    '우편번호': 'receiver_zipcode',
    'ordered_at': 'ordered_at',
    '주문일시': 'ordered_at',
    '주문일': 'ordered_at',
    '결제일': 'ordered_at',
    '결제일시': 'ordered_at',
    'delivery_company': 'delivery_company',
    '택배사': 'delivery_company',
    'tracking_number': 'tracking_number',
    '운송장번호': 'tracking_number',
    '송장번호': 'tracking_number',
    'platform_order_id': 'platform_order_id',
    '플랫폼주문번호': 'platform_order_id',
    'status': 'status',
    '주문상태': 'status',
}


def parse_store_excel(file, store_type='OTHER'):
    """네이버/쿠팡/범용 Excel을 파싱하여 표준 dict 리스트로 반환

    Args:
        file: 업로드된 파일 객체
        store_type: 'NAVER', 'COUPANG', 'OTHER'

    Returns:
        list[dict]: 정규화된 주문 데이터 리스트
    """
    import openpyxl

    wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return []

    # 스토어 유형별 컬럼 매핑 선택
    if store_type == 'NAVER':
        col_map = NAVER_MAP
    elif store_type == 'COUPANG':
        col_map = COUPANG_MAP
    else:
        col_map = GENERIC_MAP

    # 헤더 행 매핑
    headers = [str(h).strip() if h else '' for h in rows[0]]
    col_indices = {}
    for i, header in enumerate(headers):
        normalized_key = col_map.get(header)
        if normalized_key and normalized_key not in col_indices:
            col_indices[normalized_key] = i

    if 'store_order_id' not in col_indices:
        raise ValueError(
            '필수 컬럼 "주문번호" 또는 "상품주문번호"가 없습니다. '
            '엑셀 첫 행에 컬럼명이 포함되어야 합니다.'
        )

    result = []
    for row in rows[1:]:
        store_order_id = _cell_str(row, col_indices.get('store_order_id'))
        if not store_order_id:
            continue

        product_name = _cell_str(row, col_indices.get('product_name'))
        if not product_name:
            continue

        quantity = _cell_int(row, col_indices.get('quantity'), default=1)
        price = _cell_decimal(row, col_indices.get('price'), default=0)

        result.append({
            'store_order_id': store_order_id,
            'product_name': product_name,
            'option_name': _cell_str(row, col_indices.get('option_name')),
            'quantity': quantity,
            'price': int(price),
            'buyer_name': _cell_str(row, col_indices.get('buyer_name')) or '-',
            'buyer_phone': _cell_str(row, col_indices.get('buyer_phone')),
            'receiver_name': _cell_str(row, col_indices.get('receiver_name')) or '-',
            'receiver_phone': _cell_str(row, col_indices.get('receiver_phone')),
            'receiver_address': _cell_str(row, col_indices.get('receiver_address')),
            'receiver_zipcode': _cell_str(row, col_indices.get('receiver_zipcode')),
            'ordered_at': _cell_str(row, col_indices.get('ordered_at')),
            'delivery_company': _cell_str(row, col_indices.get('delivery_company')),
            'tracking_number': _cell_str(row, col_indices.get('tracking_number')),
            'platform_order_id': _cell_str(row, col_indices.get('platform_order_id')),
            'status': _cell_str(row, col_indices.get('status')),
        })

    logger.info('Excel parsed: %d rows from %s store', len(result), store_type)
    return result


def _cell_str(row, idx):
    if idx is None or idx >= len(row):
        return ''
    val = row[idx]
    return str(val).strip() if val is not None else ''


def _cell_int(row, idx, default=0):
    val = _cell_str(row, idx)
    if not val:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _cell_decimal(row, idx, default=0):
    val = _cell_str(row, idx)
    if not val:
        return Decimal(str(default))
    val = val.replace(',', '').replace('원', '').replace('₩', '').strip()
    try:
        return Decimal(val)
    except InvalidOperation:
        return Decimal(str(default))
