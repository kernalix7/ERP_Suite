from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cmms.models import (
    Equipment, EquipmentDowntime, MaintenanceSchedule,
    MaintenanceWorkOrder, SparePart,
)


class EquipmentTest(TestCase):
    def test_equipment_creation(self):
        eq = Equipment.objects.create(
            name='CNC 선반', code='EQ-CNC-001',
            category='가공설비', status='ACTIVE',
        )
        self.assertEqual(eq.name, 'CNC 선반')
        self.assertEqual(str(eq), '[EQ-CNC-001] CNC 선반')

    def test_default_status(self):
        eq = Equipment.objects.create(name='프레스', code='EQ-PRS-001')
        self.assertEqual(eq.status, 'ACTIVE')


class MaintenanceScheduleTest(TestCase):
    def setUp(self):
        self.equipment = Equipment.objects.create(
            name='CNC 선반', code='EQ-CNC-001',
        )

    def test_schedule_creation(self):
        schedule = MaintenanceSchedule.objects.create(
            equipment=self.equipment,
            title='윤활유 교체',
            maintenance_type='PREVENTIVE',
            frequency_days=90,
        )
        self.assertEqual(schedule.frequency_days, 90)
        self.assertEqual(str(schedule), 'EQ-CNC-001 - 윤활유 교체')


class MaintenanceWorkOrderTest(TestCase):
    def setUp(self):
        self.equipment = Equipment.objects.create(
            name='CNC 선반', code='EQ-CNC-001',
        )

    def test_auto_number(self):
        wo = MaintenanceWorkOrder.objects.create(equipment=self.equipment)
        self.assertTrue(wo.wo_number.startswith('MWO-'))

    def test_default_status(self):
        wo = MaintenanceWorkOrder.objects.create(equipment=self.equipment)
        self.assertEqual(wo.status, 'OPEN')


class SparePartTest(TestCase):
    def test_sparepart_creation(self):
        part = SparePart.objects.create(
            name='베어링', code='SP-BRG-001',
            current_stock=5, min_stock=10, unit_cost=Decimal('50000'),
        )
        self.assertEqual(str(part), '[SP-BRG-001] 베어링')
        self.assertTrue(part.is_below_min)

    def test_above_min_stock(self):
        part = SparePart.objects.create(
            name='필터', code='SP-FLT-001',
            current_stock=20, min_stock=10,
        )
        self.assertFalse(part.is_below_min)


class EquipmentDowntimeTest(TestCase):
    def setUp(self):
        self.equipment = Equipment.objects.create(
            name='CNC 선반', code='EQ-CNC-001',
        )

    def test_downtime_duration(self):
        now = timezone.now()
        dt = EquipmentDowntime.objects.create(
            equipment=self.equipment,
            start_time=now - timedelta(hours=2),
            end_time=now,
            reason='긴급수리',
        )
        self.assertAlmostEqual(dt.duration_hours, 2.0, places=1)

    def test_open_downtime(self):
        dt = EquipmentDowntime.objects.create(
            equipment=self.equipment,
            start_time=timezone.now(),
            reason='점검중',
        )
        self.assertIsNone(dt.duration_hours)


# ── Signal Tests ────────────────────────────────────────────────


class MWOCompletedSignalTest(TestCase):
    """보전작업 완료 시그널 테스트"""

    def setUp(self):
        self.equipment = Equipment.objects.create(
            name='CNC 선반', code='EQ-SIG-001',
            status='MAINTENANCE',
        )
        self.schedule = MaintenanceSchedule.objects.create(
            equipment=self.equipment,
            title='윤활유 교체',
            maintenance_type='PREVENTIVE',
            frequency_days=30,
            next_due=date.today() - timedelta(days=1),
        )

    def test_completed_restores_equipment_active(self):
        """보전작업 완료 시 설비상태 ACTIVE 복원"""
        wo = MaintenanceWorkOrder.objects.create(
            equipment=self.equipment,
            schedule=self.schedule,
            status='IN_PROGRESS',
        )
        wo.status = 'COMPLETED'
        wo.save()

        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.status, 'ACTIVE')

    def test_completed_updates_schedule_next_due(self):
        """보전작업 완료 시 스케줄 다음 예정일 갱신"""
        wo = MaintenanceWorkOrder.objects.create(
            equipment=self.equipment,
            schedule=self.schedule,
            status='IN_PROGRESS',
        )
        wo.status = 'COMPLETED'
        wo.save()

        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.last_performed, date.today())
        expected_next = date.today() + timedelta(days=30)
        self.assertEqual(self.schedule.next_due, expected_next)

    def test_non_completed_no_change(self):
        """COMPLETED가 아닌 상태에서는 설비상태 변경 없음"""
        wo = MaintenanceWorkOrder.objects.create(
            equipment=self.equipment,
            status='OPEN',
        )
        wo.status = 'IN_PROGRESS'
        wo.save()

        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.status, 'MAINTENANCE')


class EquipmentBreakdownSignalTest(TestCase):
    """설비 고장 시그널 테스트"""

    def test_maintenance_creates_emergency_wo(self):
        """설비 MAINTENANCE 전환 시 긴급 작업지시 자동 생성"""
        eq = Equipment.objects.create(
            name='프레스', code='EQ-BRK-001',
            status='ACTIVE',
        )
        eq.status = 'MAINTENANCE'
        eq.save()

        wo = MaintenanceWorkOrder.objects.filter(
            equipment=eq,
            priority='EMERGENCY',
        ).first()
        self.assertIsNotNone(wo)
        self.assertEqual(wo.status, 'OPEN')

    def test_maintenance_creates_downtime_record(self):
        """설비 MAINTENANCE 전환 시 비가동 기록 자동 생성"""
        eq = Equipment.objects.create(
            name='프레스', code='EQ-BRK-002',
            status='ACTIVE',
        )
        eq.status = 'MAINTENANCE'
        eq.save()

        dt = EquipmentDowntime.objects.filter(equipment=eq).first()
        self.assertIsNotNone(dt)
        self.assertIsNotNone(dt.start_time)
        self.assertIsNone(dt.end_time)

    def test_active_to_retired_no_wo(self):
        """ACTIVE→RETIRED에서는 긴급 작업지시 미생성"""
        eq = Equipment.objects.create(
            name='프레스', code='EQ-BRK-003',
            status='ACTIVE',
        )
        eq.status = 'RETIRED'
        eq.save()

        count = MaintenanceWorkOrder.objects.filter(
            equipment=eq,
            priority='EMERGENCY',
        ).count()
        self.assertEqual(count, 0)


class PreventiveMaintenanceTaskTest(TestCase):
    """예방보전 Celery 태스크 테스트"""

    def test_creates_wo_for_due_schedule(self):
        """예정일 도래 시 WorkOrder 자동 생성"""
        from apps.cmms.tasks import check_preventive_maintenance

        eq = Equipment.objects.create(
            name='테스트설비', code='EQ-PM-001',
        )
        schedule = MaintenanceSchedule.objects.create(
            equipment=eq,
            title='정기점검',
            frequency_days=30,
            next_due=date.today() - timedelta(days=1),
        )

        result = check_preventive_maintenance()
        self.assertEqual(result, 1)

        wo = MaintenanceWorkOrder.objects.filter(
            schedule=schedule,
            equipment=eq,
        ).first()
        self.assertIsNotNone(wo)
        self.assertEqual(wo.status, 'OPEN')

    def test_skips_if_open_wo_exists(self):
        """미완료 작업지시가 있으면 중복 생성 안 함"""
        from apps.cmms.tasks import check_preventive_maintenance

        eq = Equipment.objects.create(
            name='테스트설비', code='EQ-PM-002',
        )
        schedule = MaintenanceSchedule.objects.create(
            equipment=eq,
            title='정기점검',
            frequency_days=30,
            next_due=date.today() - timedelta(days=1),
        )
        # 이미 열린 WO
        MaintenanceWorkOrder.objects.create(
            equipment=eq,
            schedule=schedule,
            status='OPEN',
        )

        result = check_preventive_maintenance()
        self.assertEqual(result, 0)

    def test_skips_future_schedule(self):
        """예정일 미도래 시 WorkOrder 미생성"""
        from apps.cmms.tasks import check_preventive_maintenance

        eq = Equipment.objects.create(
            name='테스트설비', code='EQ-PM-003',
        )
        MaintenanceSchedule.objects.create(
            equipment=eq,
            title='정기점검',
            frequency_days=30,
            next_due=date.today() + timedelta(days=10),
        )

        result = check_preventive_maintenance()
        self.assertEqual(result, 0)
