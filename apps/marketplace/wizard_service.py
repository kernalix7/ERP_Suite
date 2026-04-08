"""
Import Wizard 서비스 — 6단계 가져오기 워크플로 오케스트레이션

단계:
1. FETCH     — API 조회 or Excel 업로드 → MarketplaceOrder 생성
2. PREVIEW   — 미리보기 + 선택/해제 + 상품 매칭
3. CUSTOMER  — 고객 등록
4. QUOTATION — 견적 생성
5. ORDER     — 견적→주문 전환
6. DONE      — 완료
"""
import logging
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import ImportSession, MarketplaceOrder, ProductMapping

logger = logging.getLogger(__name__)

STAGE_ORDER = ['FETCH', 'PREVIEW', 'CUSTOMER', 'QUOTATION', 'ORDER', 'DONE']


class WizardService:

    def create_session(self, source_type, platform, user):
        """새 Import Wizard 세션 생성"""
        return ImportSession.objects.create(
            source_type=source_type,
            platform=platform,
            stage='FETCH',
            created_by=user,
        )

    def get_session(self, session_id):
        return ImportSession.objects.filter(
            pk=session_id, is_active=True,
        ).first()

    def advance_stage(self, session):
        """다음 단계로 이동"""
        idx = STAGE_ORDER.index(session.stage)
        if idx < len(STAGE_ORDER) - 1:
            session.stage = STAGE_ORDER[idx + 1]
            session.save(update_fields=['stage', 'updated_at'])
        return session.stage

    # ── Stage 1: FETCH ──

    def fetch_from_api(self, session, from_date, to_date, user=None):
        """API에서 주문 가져와서 MarketplaceOrder 생성"""
        from .sync_service import fetch_orders_preview

        preview = fetch_orders_preview(from_date=from_date, to_date=to_date)
        created_count = 0

        for data in preview:
            store_order_id = data.get('store_order_id', '')
            if not store_order_id:
                continue
            # 중복 검사
            if MarketplaceOrder.all_objects.filter(
                store_order_id=store_order_id,
            ).exists():
                continue

            ordered_at = data.get('ordered_at', '')
            if isinstance(ordered_at, str) and ordered_at:
                ordered_at = parse_datetime(ordered_at) or timezone.now()
            elif not ordered_at:
                ordered_at = timezone.now()

            MarketplaceOrder.objects.create(
                store_order_id=store_order_id,
                product_name=data.get('product_name', ''),
                option_name=data.get('option_name', ''),
                quantity=data.get('quantity', 1),
                price=data.get('price', 0),
                buyer_name=data.get('buyer_name', '-'),
                buyer_phone=data.get('buyer_phone', ''),
                receiver_name=data.get('receiver_name', '-'),
                receiver_phone=data.get('receiver_phone', ''),
                receiver_address=data.get('receiver_address', ''),
                platform_order_id=data.get('platform_order_id', ''),
                platform_product_order_id=data.get('platform_product_order_id', ''),
                ordered_at=ordered_at,
                status='NEW',
                import_session=session,
                import_status='PENDING',
                created_by=user,
            )
            created_count += 1

        session.total_count = created_count
        session.save(update_fields=['total_count', 'updated_at'])
        logger.info('Wizard fetch API: %d orders created for session %s', created_count, session.pk)
        return created_count

    def fetch_from_excel(self, session, file, store_type, user=None):
        """Excel 파싱 → MarketplaceOrder 생성"""
        from .excel_parser import parse_store_excel

        rows = parse_store_excel(file, store_type)
        created_count = 0

        for data in rows:
            store_order_id = data.get('store_order_id', '')
            if not store_order_id:
                continue
            if MarketplaceOrder.all_objects.filter(
                store_order_id=store_order_id,
            ).exists():
                continue

            ordered_at = data.get('ordered_at', '')
            if isinstance(ordered_at, str) and ordered_at:
                ordered_at = parse_datetime(ordered_at) or timezone.now()
            elif not ordered_at:
                ordered_at = timezone.now()

            MarketplaceOrder.objects.create(
                store_order_id=store_order_id,
                product_name=data.get('product_name', ''),
                option_name=data.get('option_name', ''),
                quantity=data.get('quantity', 1),
                price=data.get('price', 0),
                buyer_name=data.get('buyer_name', '-'),
                buyer_phone=data.get('buyer_phone', ''),
                receiver_name=data.get('receiver_name', '-'),
                receiver_phone=data.get('receiver_phone', ''),
                receiver_address=data.get('receiver_address', ''),
                platform_order_id=data.get('platform_order_id', ''),
                delivery_company=data.get('delivery_company', ''),
                tracking_number=data.get('tracking_number', ''),
                ordered_at=ordered_at,
                status='NEW',
                import_session=session,
                import_status='PENDING',
                created_by=user,
            )
            created_count += 1

        session.total_count = created_count
        session.save(update_fields=['total_count', 'updated_at'])
        logger.info('Wizard fetch Excel: %d orders created for session %s', created_count, session.pk)
        return created_count

    # ── Stage 2: PREVIEW ──

    def get_preview_data(self, session):
        """미리보기 데이터 + 매칭 정보"""
        from .sync_service import _match_product, _match_customer

        orders = session.orders.filter(is_active=True).order_by('pk')
        preview = []
        for order in orders:
            match = _match_product(order.product_name, order.option_name)
            customer_info = _match_customer(order.buyer_name)
            preview.append({
                'order': order,
                'matched_product': match['product'],
                'match_type': match['match_type'],
                'suggested_products': match['suggested'],
                'is_new_customer': customer_info['is_new_customer'],
            })
        return preview

    def update_selections(self, session, selected_ids, skipped_ids=None):
        """선택/해제 업데이트"""
        if skipped_ids:
            session.orders.filter(
                pk__in=skipped_ids, is_active=True,
            ).update(import_status='SKIPPED')

        selected_count = session.orders.filter(
            is_active=True,
        ).exclude(import_status='SKIPPED').count()
        session.selected_count = selected_count
        session.save(update_fields=['selected_count', 'updated_at'])

    # ── Stage 3: CUSTOMER ──

    def register_customers(self, session, user=None):
        """미매칭 고객 등록 — 행별 transaction.atomic()"""
        from apps.sales.models import Customer
        from .sync_service import _parse_address

        orders = session.orders.filter(
            is_active=True, import_status='PENDING',
        )
        success = 0
        errors = 0

        for order in orders:
            try:
                with transaction.atomic():
                    address, road, detail = _parse_address(order.receiver_address)
                    customer, created = Customer.objects.get_or_create(
                        name=order.buyer_name,
                        defaults={
                            'phone': order.buyer_phone or '',
                            'address': address,
                            'address_road': road,
                            'address_detail': detail,
                            'created_by': user,
                        },
                    )
                    if not created:
                        updated_fields = []
                        if not customer.phone and order.buyer_phone:
                            customer.phone = order.buyer_phone
                            updated_fields.append('phone')
                        if not customer.address and address:
                            customer.address = address
                            customer.address_road = road
                            customer.address_detail = detail
                            updated_fields.extend(['address', 'address_road', 'address_detail'])
                        if updated_fields:
                            updated_fields.append('updated_at')
                            customer.save(update_fields=updated_fields)

                    MarketplaceOrder.objects.filter(pk=order.pk).update(
                        import_status='CUSTOMER_DONE',
                    )
                    success += 1
            except Exception as e:
                MarketplaceOrder.objects.filter(pk=order.pk).update(
                    import_status='ERROR',
                    import_error=str(e),
                )
                errors += 1
                logger.error('Customer registration error for %s: %s', order.store_order_id, e)

        logger.info(
            'Wizard customers: session %s — %d success, %d errors',
            session.pk, success, errors,
        )
        return success, errors

    # ── Stage 4: QUOTATION ──

    def create_quotations(self, session, user=None):
        """견적 생성 — 행별 transaction.atomic()"""
        from decimal import Decimal as D

        from apps.inventory.models import Product
        from apps.sales.models import Customer, Quotation, QuotationItem
        from .sync_service import _match_product

        orders = session.orders.filter(
            is_active=True, import_status='CUSTOMER_DONE',
        )
        success = 0
        errors = 0

        for order in orders:
            try:
                with transaction.atomic():
                    # 상품 매칭
                    match = _match_product(order.product_name, order.option_name)
                    product = match['product']
                    if not product:
                        MarketplaceOrder.objects.filter(pk=order.pk).update(
                            import_status='ERROR',
                            import_error=f'상품 매칭 실패: {order.product_name}',
                        )
                        errors += 1
                        continue

                    # 고객 조회
                    customer = Customer.objects.filter(
                        name=order.buyer_name, is_active=True,
                    ).first()

                    # 견적 생성
                    quote_date = order.ordered_at.date() if order.ordered_at else date.today()
                    quotation = Quotation.objects.create(
                        quote_date=quote_date,
                        valid_until=quote_date + timedelta(days=30),
                        customer=customer,
                        status=Quotation.Status.DRAFT,
                        created_by=user,
                    )

                    # 단가 결정
                    unit_price = product.unit_price
                    if not unit_price:
                        unit_price = int(D(str(order.price)) / D('1.1'))

                    QuotationItem.objects.create(
                        quotation=quotation,
                        product=product,
                        quantity=order.quantity,
                        cost_price=product.cost_price or 0,
                        unit_price=unit_price,
                        created_by=user,
                    )
                    quotation.update_total()

                    # 연결
                    MarketplaceOrder.objects.filter(pk=order.pk).update(
                        erp_quotation=quotation,
                        import_status='QUOTATION_DONE',
                    )
                    success += 1
            except Exception as e:
                MarketplaceOrder.objects.filter(pk=order.pk).update(
                    import_status='ERROR',
                    import_error=str(e),
                )
                errors += 1
                logger.error('Quotation creation error for %s: %s', order.store_order_id, e)

        logger.info(
            'Wizard quotations: session %s — %d success, %d errors',
            session.pk, success, errors,
        )
        return success, errors

    # ── Stage 5: ORDER ──

    def convert_to_orders(self, session, user=None):
        """견적→주문 일괄 전환 — 행별 transaction.atomic()"""
        from apps.sales.models import Order, OrderItem

        orders = session.orders.filter(
            is_active=True, import_status='QUOTATION_DONE',
            erp_quotation__isnull=False,
        ).select_related('erp_quotation')
        success = 0
        errors = 0

        for mkt_order in orders:
            try:
                with transaction.atomic():
                    quotation = mkt_order.erp_quotation
                    if quotation.status == 'CONVERTED':
                        MarketplaceOrder.objects.filter(pk=mkt_order.pk).update(
                            import_status='ORDER_DONE',
                        )
                        success += 1
                        continue

                    # 견적→주문 전환
                    erp_order = Order.objects.create(
                        order_date=quotation.quote_date,
                        delivery_date=quotation.valid_until,
                        partner=quotation.partner,
                        customer=quotation.customer,
                        vat_included=quotation.vat_included,
                        bank_account=quotation.bank_account,
                        status=Order.Status.DRAFT,
                        created_by=user,
                    )

                    for qi in quotation.quote_items.filter(is_active=True):
                        OrderItem.objects.create(
                            order=erp_order,
                            product=qi.product,
                            quantity=qi.quantity,
                            cost_price=qi.cost_price,
                            unit_price=qi.unit_price,
                            discount_rate=qi.discount_rate,
                            discount_amount=qi.discount_amount,
                            created_by=user,
                        )

                    erp_order.update_total()

                    quotation.status = 'CONVERTED'
                    quotation.converted_order = erp_order
                    quotation.save(update_fields=[
                        'status', 'converted_order', 'updated_at',
                    ])

                    MarketplaceOrder.objects.filter(pk=mkt_order.pk).update(
                        erp_order=erp_order,
                        import_status='ORDER_DONE',
                    )
                    success += 1
            except Exception as e:
                MarketplaceOrder.objects.filter(pk=mkt_order.pk).update(
                    import_status='ERROR',
                    import_error=str(e),
                )
                errors += 1
                logger.error('Order conversion error for %s: %s', mkt_order.store_order_id, e)

        logger.info(
            'Wizard orders: session %s — %d success, %d errors',
            session.pk, success, errors,
        )
        return success, errors

    # ── Summary ──

    def get_summary(self, session):
        """세션 요약 정보"""
        from django.db.models import Count
        orders = session.orders.filter(is_active=True)
        status_counts = dict(
            orders.values_list('import_status').annotate(c=Count('pk')).values_list('import_status', 'c'),
        )
        return {
            'total': orders.count(),
            'pending': status_counts.get('PENDING', 0),
            'customer_done': status_counts.get('CUSTOMER_DONE', 0),
            'quotation_done': status_counts.get('QUOTATION_DONE', 0),
            'order_done': status_counts.get('ORDER_DONE', 0),
            'skipped': status_counts.get('SKIPPED', 0),
            'error': status_counts.get('ERROR', 0),
        }
