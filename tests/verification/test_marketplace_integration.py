"""마켓플레이스 통합 시그널 검증.

검증 항목:
- Shipment 상태 SHIPPED 전환 시 마켓플레이스 주문이 연결되어 있으면
  push_shipping_async 가 큐잉되는지
- 마켓플레이스 주문이 없으면 호출되지 않는지
- 이미 SHIPPED → SHIPPED 재저장 시 중복 호출되지 않는지
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.marketplace.models import MarketplaceOrder
from apps.sales.models import Customer, Order, Shipment

User = get_user_model()


class ShipmentShippedPushIntegrationTest(TestCase):
    """Shipment SHIPPED → push_shipping_async 호출 흐름."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='mkpship', password='testpass123', role='manager',
        )
        self.customer = Customer.objects.create(
            name='테스트고객', phone='01012345678', created_by=self.user,
        )
        self.order = Order.objects.create(
            order_date=date.today(),
            customer=self.customer,
            status='CONFIRMED',
            created_by=self.user,
        )
        self.shipment = Shipment.objects.create(
            order=self.order,
            status='PREPARING',
            created_by=self.user,
        )

    def _make_marketplace_order(self, **overrides):
        defaults = dict(
            store_order_id='MKT-INT-001',
            product_name='상품A',
            quantity=1,
            price=Decimal('10000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=timezone.now(),
            delivery_company='CJ대한통운',
            tracking_number='TRACK-001',
            platform_product_order_id='PPO-001',
            erp_order=self.order,
            status=MarketplaceOrder.Status.NEW,
            created_by=self.user,
        )
        defaults.update(overrides)
        return MarketplaceOrder.objects.create(**defaults)

    def test_shipment_shipped_triggers_push(self):
        """마켓플레이스 주문이 연결된 Shipment SHIPPED → push_shipping_async.delay 호출."""
        mkt = self._make_marketplace_order()

        with patch('apps.marketplace.tasks.push_shipping_async.delay') as mock_delay:
            self.shipment.status = 'SHIPPED'
            self.shipment.save()

        mock_delay.assert_called_once_with(mkt.pk)

    def test_non_marketplace_shipment_no_push(self):
        """일반 주문 Shipment SHIPPED → push_shipping_async 호출 안 됨."""
        with patch('apps.marketplace.tasks.push_shipping_async.delay') as mock_delay:
            self.shipment.status = 'SHIPPED'
            self.shipment.save()

        mock_delay.assert_not_called()

    def test_shipped_to_shipped_resave_no_double_push(self):
        """SHIPPED → SHIPPED 재저장 시 push 시그널이 다시 호출되지 않음."""
        self._make_marketplace_order()

        with patch('apps.marketplace.tasks.push_shipping_async.delay') as mock_delay:
            self.shipment.status = 'SHIPPED'
            self.shipment.save()
            self.assertEqual(mock_delay.call_count, 1)

            self.shipment.status = 'SHIPPED'
            self.shipment.save()
            self.assertEqual(mock_delay.call_count, 1)

    def test_cancelled_marketplace_order_no_push(self):
        """마켓플레이스 주문이 CANCELLED 상태면 push 호출 안 됨."""
        self._make_marketplace_order(status=MarketplaceOrder.Status.CANCELLED)

        with patch('apps.marketplace.tasks.push_shipping_async.delay') as mock_delay:
            self.shipment.status = 'SHIPPED'
            self.shipment.save()

        mock_delay.assert_not_called()

    def test_preparing_to_in_transit_no_push(self):
        """SHIPPED 가 아닌 다른 상태로 전환되면 push 호출 안 됨."""
        self._make_marketplace_order()

        with patch('apps.marketplace.tasks.push_shipping_async.delay') as mock_delay:
            self.shipment.status = 'IN_TRANSIT'
            self.shipment.save()

        mock_delay.assert_not_called()
