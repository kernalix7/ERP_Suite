from datetime import date
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User
from apps.sales.models import Partner

from .models import (
    DeliveryRoute,
    DeliveryZone,
    Driver,
    FreightCost,
    RouteStop,
    Vehicle,
)


class DriverTests(TestCase):
    def test_create_driver(self):
        user = User.objects.create_user(username='driver01', password='testpass123')
        driver = Driver.objects.create(
            user=user,
            license_number='11-22-334455-66',
            license_type='TYPE1_NORMAL',
            license_expiry=date(2028, 12, 31),
            phone='010-1234-5678',
        )
        self.assertIn('driver01', str(driver))
        self.assertEqual(driver.license_type, 'TYPE1_NORMAL')


class VehicleTests(TestCase):
    def test_create_vehicle(self):
        vehicle = Vehicle.objects.create(
            name='1톤 트럭',
            plate_number='12가 3456',
            vehicle_type=Vehicle.VehicleType.TRUCK,
            capacity_kg=Decimal('1000.00'),
        )
        self.assertEqual(vehicle.status, Vehicle.VehicleStatus.AVAILABLE)
        self.assertIn('12가 3456', str(vehicle))

    def test_status_change(self):
        vehicle = Vehicle.objects.create(
            name='밴', plate_number='34나 5678',
            vehicle_type=Vehicle.VehicleType.VAN,
        )
        vehicle.status = Vehicle.VehicleStatus.IN_USE
        vehicle.save()
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, Vehicle.VehicleStatus.IN_USE)


class DeliveryZoneTests(TestCase):
    def test_create_zone(self):
        zone = DeliveryZone.objects.create(
            name='수도권', region='서울/경기',
            base_cost=5000, cost_per_kg=100, cost_per_km=200,
        )
        self.assertIn('수도권', str(zone))
        self.assertEqual(zone.base_cost, 5000)


class DeliveryRouteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='route_driver', password='testpass123')
        self.driver = Driver.objects.create(
            user=self.user, license_number='AA-BB-001',
            license_type='TYPE1_NORMAL', license_expiry=date(2029, 1, 1),
            phone='010-0000-0000',
        )
        self.vehicle = Vehicle.objects.create(
            name='배송차', plate_number='56다 7890',
            vehicle_type=Vehicle.VehicleType.TRUCK,
        )

    def test_create_route_auto_number(self):
        route = DeliveryRoute.objects.create(
            name='서울 배송',
            date=date(2026, 4, 1),
            vehicle=self.vehicle,
            driver=self.driver,
        )
        self.assertTrue(route.route_number.startswith('RT-'))
        self.assertEqual(route.status, DeliveryRoute.RouteStatus.PLANNED)

    def test_route_status_flow(self):
        route = DeliveryRoute.objects.create(
            name='경기 배송', date=date(2026, 4, 2),
            vehicle=self.vehicle, driver=self.driver,
        )
        route.status = DeliveryRoute.RouteStatus.IN_PROGRESS
        route.save()
        route.refresh_from_db()
        self.assertEqual(route.status, DeliveryRoute.RouteStatus.IN_PROGRESS)

        route.status = DeliveryRoute.RouteStatus.COMPLETED
        route.save()
        route.refresh_from_db()
        self.assertEqual(route.status, DeliveryRoute.RouteStatus.COMPLETED)

    def test_soft_delete(self):
        route = DeliveryRoute.objects.create(
            name='삭제 테스트', date=date(2026, 4, 3),
            vehicle=self.vehicle, driver=self.driver,
        )
        route.soft_delete()
        self.assertFalse(DeliveryRoute.objects.filter(pk=route.pk).exists())
        self.assertTrue(DeliveryRoute.all_objects.filter(pk=route.pk).exists())


class RouteStopTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='stop_driver', password='testpass123')
        self.driver = Driver.objects.create(
            user=self.user, license_number='CC-DD-002',
            license_type='TYPE1_NORMAL', license_expiry=date(2029, 1, 1),
            phone='010-1111-2222',
        )
        self.vehicle = Vehicle.objects.create(
            name='테스트차', plate_number='78라 9012',
            vehicle_type=Vehicle.VehicleType.VAN,
        )
        self.route = DeliveryRoute.objects.create(
            name='경유지 테스트', date=date(2026, 4, 5),
            vehicle=self.vehicle, driver=self.driver,
        )
        self.partner = Partner.objects.create(
            code='PTN-L01', name='배송처', partner_type='CUSTOMER',
        )

    def test_create_stop(self):
        stop = RouteStop.objects.create(
            route=self.route, sequence=1,
            partner=self.partner, address='서울시 강남구',
        )
        self.assertEqual(stop.status, RouteStop.StopStatus.PENDING)
        self.assertIn('#1', str(stop))


class FreightCostTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cost_driver', password='testpass123')
        self.driver = Driver.objects.create(
            user=self.user, license_number='EE-FF-003',
            license_type='TYPE1_NORMAL', license_expiry=date(2029, 1, 1),
            phone='010-3333-4444',
        )
        self.vehicle = Vehicle.objects.create(
            name='비용차', plate_number='90마 1234',
            vehicle_type=Vehicle.VehicleType.TRUCK,
        )
        self.route = DeliveryRoute.objects.create(
            name='비용 테스트', date=date(2026, 4, 6),
            vehicle=self.vehicle, driver=self.driver,
        )

    def test_create_freight_cost(self):
        cost = FreightCost.objects.create(
            route=self.route,
            cost_type=FreightCost.CostType.FUEL,
            amount=50000,
            description='경유 40L',
        )
        self.assertEqual(cost.cost_type, 'FUEL')
        self.assertIn('유류비', str(cost))


class LogisticsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='log_staff', password='testpass123', role='staff',
        )
        self.manager = User.objects.create_user(
            username='log_manager', password='testpass123', role='manager',
        )

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('logistics:dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_authenticated(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('logistics:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_route_list_requires_login(self):
        resp = self.client.get(reverse('logistics:route_list'))
        self.assertEqual(resp.status_code, 302)

    def test_route_list_authenticated(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('logistics:route_list'))
        self.assertEqual(resp.status_code, 200)
