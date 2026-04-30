"""
마켓플레이스 주문 동기화 서비스

API 클라이언트에서 조회한 원본 데이터를 MarketplaceOrder로 변환·저장합니다.
"""
import logging
import threading
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .api_client import get_client, get_all_clients
from .models import MarketplaceOrder, ProductMapping, SyncLog

# 시그널 건너뛰기 플래그 (import 경로에서 직접 견적 생성 시)
_import_context = threading.local()

logger = logging.getLogger(__name__)


def _match_product(product_name, option_name='', template_id=None):
    """스토어 상품명을 ERP 제품과 매칭합니다.

    Args:
        product_name: 스토어 상품명
        option_name: 스토어 옵션명
        template_id: ImportTemplate PK (있으면 해당 템플릿 매핑 우선 조회)

    Returns:
        dict: product (Product|None), match_type (str), suggested (list[Product])
    """
    from apps.inventory.models import Product

    # 1) ProductMapping 조회 (저장된 규칙) — 템플릿 매핑 우선, 없으면 전역 매핑
    mapping_qs = ProductMapping.objects.filter(
        store_product_name=product_name,
        store_option_name=option_name,
        is_active=True,
    ).select_related('product')

    if template_id:
        mapping = mapping_qs.filter(template_id=template_id).first()
        if not mapping:
            mapping = mapping_qs.filter(template__isnull=True).first()
    else:
        mapping = mapping_qs.first()

    if mapping:
        return {'product': mapping.product, 'match_type': 'saved', 'suggested': []}

    # 2) 정확 매칭
    exact = Product.objects.filter(name=product_name, is_active=True).first()
    if exact:
        return {'product': exact, 'match_type': 'exact', 'suggested': []}

    # 3) 부분 매칭 (icontains)
    first_word = product_name.split()[0] if product_name else ''
    if first_word:
        partial = list(Product.objects.filter(
            name__icontains=first_word,
            is_active=True,
        )[:5])
        if partial:
            return {'product': partial[0], 'match_type': 'partial', 'suggested': partial}

    # 4) 매칭 실패 — 전체 제품 리스트 (선택용)
    all_products = list(Product.objects.filter(is_active=True).order_by('name')[:20])
    return {'product': None, 'match_type': 'none', 'suggested': all_products}


def _match_customer(buyer_name):
    """스토어 주문자명을 ERP 고객과 매칭합니다.

    Returns:
        dict: customer_name (str), is_new_customer (bool)
    """
    from apps.sales.models import Customer
    exists = Customer.objects.filter(name=buyer_name, is_active=True).exists()
    return {
        'matched_customer_name': buyer_name,
        'is_new_customer': not exists,
    }


def fetch_orders_preview(config=None,
                         from_date: datetime = None,
                         to_date: datetime = None,
                         template_id=None) -> list[dict]:
    """
    마켓플레이스 주문을 조회하여 미리보기용 리스트를 반환합니다.
    DB에 저장하지 않습니다. config=None이면 관리자 설정에서 읽습니다.

    Args:
        template_id: ImportTemplate PK — 저장된 매핑 규칙 적용

    Returns:
        list[dict]: 정규화된 주문 데이터 + 매칭 정보 + 'already_imported' 플래그
    """
    client = get_client(config)
    if not client:
        return []

    raw_orders = client.get_orders(from_date=from_date, to_date=to_date)
    preview = []
    for raw_order in raw_orders:
        try:
            normalized = client.normalize_order(raw_order)
            store_id = normalized.get('store_order_id', '')
            normalized['already_imported'] = MarketplaceOrder.all_objects.filter(
                store_order_id=store_id,
            ).exists()

            # 상품 매칭 정보
            match = _match_product(
                normalized.get('product_name', ''),
                normalized.get('option_name', ''),
                template_id=template_id,
            )
            matched_product = match['product']
            normalized['matched_product_id'] = matched_product.pk if matched_product else None
            normalized['matched_product_name'] = matched_product.name if matched_product else ''
            normalized['match_type'] = match['match_type']
            normalized['suggested_products'] = [
                {'id': p.pk, 'name': p.name} for p in match['suggested']
            ]

            # 고객 매칭 정보
            customer_info = _match_customer(normalized.get('buyer_name', ''))
            normalized.update(customer_info)

            # 예상 금액
            normalized['expected_amount'] = normalized.get('price', 0)

            preview.append(normalized)
        except (ValueError, KeyError, TypeError):
            continue
    return preview


def import_selected_orders(orders_data: list[dict],
                           user=None, config=None) -> SyncLog:
    """
    선택된 주문만 가져옵니다.
    matched_product_id가 있으면 시그널 대신 직접 고객+견적 생성.

    Args:
        orders_data: 정규화된 주문 데이터 리스트
        user: 실행한 사용자
        config: 미사용 (하위호환)

    Returns:
        SyncLog: 동기화 결과 로그
    """
    sync_log = SyncLog(
        direction=SyncLog.Direction.PULL,
        started_at=timezone.now(),
        total_count=len(orders_data),
        created_by=user,
    )
    sync_log.save()

    success = 0
    errors = 0
    error_messages = []

    for data in orders_data:
        try:
            matched_product_id = data.pop('matched_product_id', None)
            data.pop('already_imported', None)
            # 미리보기 전용 필드 제거
            for key in ('matched_product_name', 'match_type', 'suggested_products',
                        'matched_customer_name', 'is_new_customer', 'expected_amount'):
                data.pop(key, None)

            if matched_product_id:
                # 시그널 건너뛰고 직접 고객+견적 생성
                order = _upsert_order(data, user=user, skip_signal=True)
                _create_quotation_for_import(order, matched_product_id, user)
            else:
                _upsert_order(data, user=user)
            success += 1
        except (ValueError, KeyError, TypeError) as e:
            errors += 1
            order_id = data.get('store_order_id', 'unknown')
            error_messages.append(f'{order_id}: {str(e)}')

    sync_log.success_count = success
    sync_log.error_count = errors
    sync_log.error_message = '\n'.join(error_messages[:50])
    sync_log.completed_at = timezone.now()
    sync_log.save(update_fields=[
        'total_count', 'success_count', 'error_count',
        'error_message', 'completed_at', 'updated_at',
    ])
    return sync_log


def sync_orders(user=None, config=None,
                from_date: datetime = None, to_date: datetime = None) -> SyncLog:
    """
    마켓플레이스 주문을 동기화합니다.
    config=None이면 관리자 설정(SystemConfig)에서 읽습니다.

    Args:
        user: 실행한 사용자
        config: 미사용 (하위호환)
        from_date: 조회 시작일
        to_date: 조회 종료일

    Returns:
        SyncLog: 동기화 결과 로그
    """
    sync_log = SyncLog(
        direction=SyncLog.Direction.PULL,
        started_at=timezone.now(),
        created_by=user,
    )
    sync_log.save()

    client = get_client(config)
    if not client:
        sync_log.error_message = '마켓플레이스 API 설정이 없습니다. 관리자 설정에서 API 키를 입력해주세요.'
        sync_log.completed_at = timezone.now()
        sync_log.save(update_fields=['error_message', 'completed_at', 'updated_at'])
        return sync_log

    try:
        raw_orders = client.get_orders(from_date=from_date, to_date=to_date)
        sync_log.total_count = len(raw_orders)
        success = 0
        errors = 0
        error_messages = []

        for raw_order in raw_orders:
            try:
                normalized = client.normalize_order(raw_order)
                _upsert_order(normalized, user=user)
                success += 1
            except Exception as e:
                errors += 1
                order_id = raw_order.get('productOrder', {}).get(
                    'productOrderId', raw_order.get('orderId', 'unknown'),
                )
                error_messages.append(f'{order_id}: {str(e)}')
                logger.error('주문 동기화 실패 (%s): %s', order_id, e)

        sync_log.success_count = success
        sync_log.error_count = errors
        sync_log.error_message = '\n'.join(error_messages[:50])

    except (ConnectionError, OSError, ValueError) as e:
        sync_log.error_count = 1
        sync_log.error_message = f'동기화 중 오류 발생: {str(e)}'
        logger.exception('마켓플레이스 동기화 실패')

    sync_log.completed_at = timezone.now()
    sync_log.save(update_fields=[
        'total_count', 'success_count', 'error_count',
        'error_message', 'completed_at', 'updated_at',
    ])
    return sync_log


@transaction.atomic
def _upsert_order(data: dict, user=None, skip_signal=False):
    """주문 데이터를 생성하거나 업데이트합니다."""
    store_order_id = data.pop('store_order_id')
    ordered_at = data.pop('ordered_at', '')

    if isinstance(ordered_at, str) and ordered_at:
        ordered_at = parse_datetime(ordered_at) or timezone.now()
    elif not ordered_at:
        ordered_at = timezone.now()

    defaults = {
        **data,
        'ordered_at': ordered_at,
        'synced_at': timezone.now(),
    }

    if skip_signal:
        _import_context.skip_signal = True

    try:
        order, created = MarketplaceOrder.all_objects.update_or_create(
            store_order_id=store_order_id,
            defaults=defaults,
        )
        if created and user:
            order.created_by = user
            order.save(update_fields=['created_by'])
    finally:
        _import_context.skip_signal = False

    return order


def _parse_address(receiver_address):
    """receiver_address를 road + detail로 분리 (줄바꿈 구분)"""
    if not receiver_address:
        return '', '', ''
    parts = receiver_address.split('\n')
    road = parts[0].strip() if parts else ''
    detail = parts[1].strip() if len(parts) > 1 else ''
    return receiver_address, road, detail


@transaction.atomic
def _create_quotation_for_import(order, product_id, user=None):
    """import 경로에서 직접 고객+견적서를 생성합니다."""
    from datetime import date, timedelta as td
    from decimal import Decimal

    from apps.core.utils import generate_document_number
    from apps.inventory.models import Product
    from apps.sales.models import Customer, Quotation, QuotationItem

    product = Product.objects.filter(pk=product_id, is_active=True).first()
    if not product:
        logger.warning(
            'MarketplaceOrder %s: 제품 ID %s 없음 — 견적서 미생성',
            order.store_order_id, product_id,
        )
        return

    # 주소 분리
    address, address_road, address_detail = _parse_address(order.receiver_address)

    # 고객 get_or_create
    customer, customer_created = Customer.objects.get_or_create(
        name=order.buyer_name,
        defaults={
            'phone': order.buyer_phone or '',
            'address': address,
            'address_road': address_road,
            'address_detail': address_detail,
            'created_by': user,
        },
    )
    if not customer_created:
        updated_fields = []
        if not customer.phone and order.buyer_phone:
            customer.phone = order.buyer_phone
            updated_fields.append('phone')
        if not customer.address and address:
            customer.address = address
            customer.address_road = address_road
            customer.address_detail = address_detail
            updated_fields.extend(['address', 'address_road', 'address_detail'])
        if updated_fields:
            updated_fields.append('updated_at')
            customer.save(update_fields=updated_fields)

    # 견적서 생성 (스토어 주문일 기준)
    quote_date = order.ordered_at.date() if order.ordered_at else date.today()
    quote_number = generate_document_number(
        Quotation, 'quote_number', 'QT', reference_date=quote_date,
    )
    quotation = Quotation.objects.create(
        quote_number=quote_number,
        quote_date=quote_date,
        valid_until=quote_date + td(days=30),
        customer=customer,
        status=Quotation.Status.DRAFT,
        created_by=user,
    )

    # 부가세 포함 금액 → 공급가액 역산 (스토어 가격은 VAT 포함)
    if product.unit_price:
        unit_price = product.unit_price
    else:
        from apps.localizations import get_vat_multiplier
        unit_price = int(Decimal(str(order.price)) / get_vat_multiplier())

    QuotationItem.objects.create(
        quotation=quotation,
        product=product,
        quantity=order.quantity,
        cost_price=product.cost_price or 0,
        unit_price=unit_price,
        created_by=user,
    )

    quotation.update_total()

    # 견적서 연결
    MarketplaceOrder.all_objects.filter(pk=order.pk).update(erp_quotation=quotation)

    logger.info(
        'MarketplaceOrder %s → Quotation %s 직접 생성 (고객: %s, 상품: %s)',
        order.store_order_id, quotation.quote_number,
        customer.name, product.name,
    )


def _get_store_modules_with_clients():
    """API가 있는 스토어 모듈과 클라이언트 쌍을 반환합니다.

    Returns:
        list[tuple[BaseStoreModule, client]]: (모듈 인스턴스, API 클라이언트) 리스트
    """
    from apps.store_modules.registry import registry

    pairs = []
    for module_id, module_cls in registry.all().items():
        module = module_cls()
        if not module.has_api:
            continue
        try:
            client = module.get_api_client()
            if client:
                pairs.append((module, client))
        except Exception as e:
            logger.debug('스토어 모듈 %s 클라이언트 생성 실패: %s', module_id, e)
    return pairs


class PushShippingError(Exception):
    """배송정보 PUSH 일시 실패 — Celery retry 트리거용 예외."""


def push_shipping_info(marketplace_order, raise_on_failure: bool = False) -> bool:
    """마켓플레이스 주문의 배송정보를 스토어 모듈을 통해 API로 전송합니다.

    Args:
        marketplace_order: MarketplaceOrder 인스턴스
        raise_on_failure: True면 일시 실패(API/모듈 호출) 시 PushShippingError 발생.
            Celery task에서 retry 트리거용. 기본 False(하위호환).

    Returns:
        bool: 전송 성공 여부
    """
    if not marketplace_order.delivery_company or not marketplace_order.tracking_number:
        logger.warning(
            '배송정보 미입력 (주문: %s) — 택배사/운송장번호 필요',
            marketplace_order.store_order_id,
        )
        return False

    if not marketplace_order.platform_product_order_id:
        logger.warning(
            '플랫폼 상품주문번호 없음 (주문: %s) — PUSH 불가',
            marketplace_order.store_order_id,
        )
        return False

    pairs = _get_store_modules_with_clients()
    if not pairs:
        logger.error('마켓플레이스 API 설정 없음 — PUSH 불가')
        if raise_on_failure:
            raise PushShippingError('마켓플레이스 API 설정 없음')
        return False

    sync_log = SyncLog(
        direction=SyncLog.Direction.PUSH,
        started_at=timezone.now(),
        total_count=1,
    )
    sync_log.save()

    last_error_message = ''
    for module, client in pairs:
        try:
            result = module.push_shipment(
                client,
                marketplace_order.platform_product_order_id,
                marketplace_order.delivery_company,
                marketplace_order.tracking_number,
            )
        except Exception as exc:
            last_error_message = f'{module.module_id}: {exc}'
            logger.warning(
                '배송정보 전송 예외 (%s, 모듈: %s): %s',
                marketplace_order.store_order_id, module.module_id, exc,
            )
            continue

        if result.get('success'):
            sync_log.success_count = 1
            sync_log.completed_at = timezone.now()
            sync_log.save(update_fields=[
                'success_count', 'completed_at', 'updated_at',
            ])
            logger.info(
                '배송정보 전송 완료: %s (모듈: %s, 택배사: %s, 운송장: %s)',
                marketplace_order.store_order_id,
                module.module_id,
                marketplace_order.delivery_company,
                marketplace_order.tracking_number,
            )
            return True
        last_error_message = f'{module.module_id}: {result.get("message", "")}'
        logger.warning(
            '배송정보 전송 실패 (%s, 모듈: %s): %s',
            marketplace_order.store_order_id, module.module_id,
            result.get('message', ''),
        )

    sync_log.error_count = 1
    sync_log.error_message = f'{marketplace_order.store_order_id}: 모든 모듈 전송 실패'
    sync_log.completed_at = timezone.now()
    sync_log.save(update_fields=[
        'error_count', 'error_message', 'completed_at', 'updated_at',
    ])
    if raise_on_failure:
        raise PushShippingError(last_error_message or '모든 모듈 전송 실패')
    return False


def push_return_info(marketplace_order, reason='') -> bool:
    """마켓플레이스 주문의 반품정보를 스토어 모듈을 통해 API로 전송합니다.

    Args:
        marketplace_order: MarketplaceOrder 인스턴스
        reason: 반품 사유

    Returns:
        bool: 전송 성공 여부
    """
    if not marketplace_order.platform_product_order_id:
        logger.warning(
            '플랫폼 상품주문번호 없음 (주문: %s) — 반품 PUSH 불가',
            marketplace_order.store_order_id,
        )
        return False

    pairs = _get_store_modules_with_clients()
    if not pairs:
        logger.error('마켓플레이스 API 설정 없음 — 반품 PUSH 불가')
        return False

    sync_log = SyncLog(
        direction=SyncLog.Direction.PUSH,
        started_at=timezone.now(),
        total_count=1,
    )
    sync_log.save()

    for module, client in pairs:
        result = module.push_return(
            client,
            marketplace_order.platform_product_order_id,
            reason,
        )
        if result.get('success'):
            sync_log.success_count = 1
            sync_log.completed_at = timezone.now()
            sync_log.save(update_fields=[
                'success_count', 'completed_at', 'updated_at',
            ])
            logger.info(
                '반품정보 전송 완료: %s (모듈: %s)',
                marketplace_order.store_order_id, module.module_id,
            )
            return True
        logger.warning(
            '반품정보 전송 결과 (%s, 모듈: %s): %s',
            marketplace_order.store_order_id, module.module_id,
            result.get('message', ''),
        )

    sync_log.error_count = 1
    sync_log.error_message = f'{marketplace_order.store_order_id}: 반품 전송 실패'
    sync_log.completed_at = timezone.now()
    sync_log.save(update_fields=[
        'error_count', 'error_message', 'completed_at', 'updated_at',
    ])
    return False


def push_order_status(marketplace_order, new_status: str) -> bool:
    """마켓플레이스 주문 상태 변경을 스토어 모듈을 통해 API로 전송합니다.

    Args:
        marketplace_order: MarketplaceOrder 인스턴스
        new_status: 변경할 상태 코드

    Returns:
        bool: 전송 성공 여부
    """
    if not marketplace_order.platform_product_order_id:
        logger.warning(
            '플랫폼 상품주문번호 없음 (주문: %s) — 상태 PUSH 불가',
            marketplace_order.store_order_id,
        )
        return False

    if new_status == 'SHIPPED':
        return push_shipping_info(marketplace_order)
    if new_status in ('RETURNED', 'CANCELLED'):
        return push_return_info(marketplace_order)

    pairs = _get_store_modules_with_clients()
    if not pairs:
        logger.error('마켓플레이스 API 설정 없음 — 상태 PUSH 불가')
        return False

    for module, client in pairs:
        try:
            result = module.push_shipment(
                client,
                marketplace_order.platform_product_order_id,
                '', '',
            )
            if result.get('success'):
                logger.info(
                    '상태 전송 완료: %s → %s (모듈: %s)',
                    marketplace_order.store_order_id, new_status, module.module_id,
                )
                return True
        except Exception as e:
            logger.error(
                '상태 전송 실패 (%s → %s, 모듈: %s): %s',
                marketplace_order.store_order_id, new_status, module.module_id, e,
            )
            continue

    return False


def sync_order_statuses():
    """스토어 상태 → ERP 주문 상태 동기화

    MarketplaceOrder와 연결된 ERP 주문의 상태를 API에서 최신으로 가져와 반영합니다.
    """
    clients = get_all_clients()
    if not clients:
        logger.warning('sync_order_statuses: API 클라이언트 없음')
        return 0

    target_orders = MarketplaceOrder.objects.filter(
        erp_order__isnull=False,
        is_active=True,
    ).exclude(
        status__in=['DELIVERED', 'CANCELLED'],
    ).select_related('erp_order')

    updated = 0
    for mkt_order in target_orders:
        for client in clients:
            try:
                from .api_client import NaverCommerceClient, CoupangClient

                if isinstance(client, NaverCommerceClient):
                    if not mkt_order.platform_product_order_id:
                        continue
                    orders = client.get_orders()
                    for raw in orders:
                        po = raw.get('productOrder', {})
                        if po.get('productOrderId') == mkt_order.platform_product_order_id:
                            new_status = po.get('productOrderStatus', '')
                            _apply_status_sync(mkt_order, new_status, 'naver')
                            updated += 1
                            break

                elif isinstance(client, CoupangClient):
                    if not mkt_order.platform_product_order_id:
                        continue
                    orders = client.get_orders()
                    for raw in orders:
                        if str(raw.get('orderItemId', '')) == mkt_order.platform_product_order_id:
                            new_status = raw.get('status', '')
                            _apply_status_sync(mkt_order, new_status, 'coupang')
                            updated += 1
                            break

            except Exception as e:
                logger.error(
                    'Status sync error for %s: %s',
                    mkt_order.store_order_id, e,
                )
                continue

    logger.info('sync_order_statuses: %d orders updated', updated)
    return updated


def _apply_status_sync(mkt_order, platform_status, platform_type):
    """플랫폼 상태를 MarketplaceOrder에 반영"""
    from apps.store_modules.registry import registry

    module = registry.get_instance(
        'naver_smartstore' if platform_type == 'naver' else 'coupang',
    )
    if not module:
        return

    mapped_status = module.map_status(platform_status)

    if mapped_status and mapped_status != mkt_order.status:
        valid_statuses = [s[0] for s in MarketplaceOrder.Status.choices]
        if mapped_status in valid_statuses:
            MarketplaceOrder.objects.filter(pk=mkt_order.pk).update(
                status=mapped_status,
                synced_at=timezone.now(),
            )
            logger.info(
                'Status synced: %s → %s (%s)',
                mkt_order.store_order_id, mapped_status, platform_type,
            )
