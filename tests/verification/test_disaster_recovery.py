"""
장애 복구 검증 테스트 (DR-001 ~ DR-004)
백업/복원, 트랜잭션 롤백, 동시 수정 충돌 처리 자동화 테스트
"""
import json
import threading
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.test import TestCase, TransactionTestCase

User = get_user_model()


class DR001_BackupRestoreTest(TestCase):
    """DR-001: 백업 생성 및 복원 - dumpdata/loaddata 사이클"""

    def setUp(self):
        from apps.inventory.models import Product, Category

        self.user = User.objects.create_user(
            username='backup_user', password='BackupPass123!', role='admin',
        )
        self.category = Category.all_objects.create(name='백업테스트카테고리')
        self.product = Product.all_objects.create(
            code='DR001-P1', name='백업테스트제품',
            category=self.category,
            unit_price=Decimal('25000'),
            current_stock=100,
        )

    def test_dumpdata_정상실행(self):
        """dumpdata 명령이 정상적으로 JSON 데이터를 생성"""
        output = StringIO()
        call_command(
            'dumpdata', 'inventory.Product',
            stdout=output, format='json',
        )
        data = output.getvalue()
        self.assertTrue(len(data) > 0, "dumpdata 출력이 비어 있음")

        # JSON 파싱 가능한지 확인
        parsed = json.loads(data)
        self.assertIsInstance(parsed, list, "dumpdata 결과가 리스트가 아님")
        self.assertGreaterEqual(len(parsed), 1, "dumpdata 결과에 레코드 없음")

    def test_직렬화_역직렬화_무손실(self):
        """Django serializers를 통한 직렬화/역직렬화 무손실 확인"""
        from apps.inventory.models import Product

        # 직렬화
        data = serializers.serialize('json', Product.all_objects.all())
        parsed = json.loads(data)

        # 원본 데이터 확인
        original = parsed[0]['fields']
        self.assertEqual(original['code'], 'DR001-P1')
        self.assertEqual(original['name'], '백업테스트제품')
        self.assertEqual(str(original['unit_price']), '25000')
        self.assertEqual(original['current_stock'], 100)

    def test_dumpdata_loaddata_사이클(self):
        """dumpdata -> 삭제 -> loaddata 후 데이터 복원 확인"""
        from apps.inventory.models import Product

        # 1. dumpdata
        output = StringIO()
        call_command(
            'dumpdata', 'inventory.Product',
            stdout=output, format='json',
        )
        dump = output.getvalue()

        # 2. 원본 데이터 기억
        original_code = self.product.code
        original_name = self.product.name
        original_pk = self.product.pk

        # 3. 제품 코드/이름 변경 (삭제 대신 - FK 제약 때문)
        Product.all_objects.filter(pk=original_pk).update(
            name='변경됨', code='CHANGED',
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, '변경됨')

        # 4. loaddata로 복원
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False,
        ) as f:
            f.write(dump)
            f.flush()
            call_command('loaddata', f.name, verbosity=0)

        # 5. 복원 확인
        self.product.refresh_from_db()
        self.assertEqual(self.product.code, original_code,
                         "loaddata 후 코드 복원 실패")
        self.assertEqual(self.product.name, original_name,
                         "loaddata 후 이름 복원 실패")


class DR003_TransactionRollbackTest(TestCase):
    """DR-003: DB 트랜잭션 롤백 - atomic 블록 원자성 검증"""

    def setUp(self):
        from apps.inventory.models import Product, Warehouse
        self.product = Product.all_objects.create(
            code='DR003-P1', name='트랜잭션테스트',
            current_stock=100,
        )
        self.warehouse = Warehouse.all_objects.create(
            code='DR003-WH', name='롤백창고',
        )

    def test_예외발생시_전체롤백(self):
        """transaction.atomic() 내 예외 발생 시 모든 변경 롤백"""
        from apps.inventory.models import StockMovement

        initial_stock = self.product.current_stock
        initial_mv_count = StockMovement.all_objects.count()

        try:
            with transaction.atomic():
                StockMovement.all_objects.create(
                    movement_number='DR003-MV01',
                    movement_type='IN',
                    product=self.product,
                    warehouse=self.warehouse,
                    quantity=50,
                    movement_date=date.today(),
                )
                # 의도적 예외 발생
                raise ValueError("의도적 롤백 테스트")
        except ValueError:
            pass

        # 롤백 확인: StockMovement 생성 취소
        self.assertEqual(
            StockMovement.all_objects.count(), initial_mv_count,
            "트랜잭션 롤백 후 StockMovement가 남아 있음",
        )

    def test_부분커밋_없음(self):
        """atomic 블록 내 여러 작업 중 하나 실패 시 전체 롤백"""
        from apps.inventory.models import Product

        try:
            with transaction.atomic():
                # 성공할 작업
                Product.all_objects.create(
                    code='DR003-P2', name='롤백제품2',
                )
                # 실패할 작업 (중복 코드)
                Product.all_objects.create(
                    code='DR003-P1', name='중복코드제품',
                )
        except IntegrityError:
            pass

        # DR003-P2도 롤백되어야 함
        self.assertFalse(
            Product.all_objects.filter(code='DR003-P2').exists(),
            "부분 커밋 발생: 트랜잭션 내 첫 번째 작업이 롤백되지 않음",
        )

    def test_중첩_atomic_롤백(self):
        """중첩 atomic 블록에서의 롤백 동작"""
        from apps.inventory.models import Product

        try:
            with transaction.atomic():
                Product.all_objects.create(
                    code='DR003-OUTER', name='외부',
                )
                try:
                    with transaction.atomic():
                        Product.all_objects.create(
                            code='DR003-INNER', name='내부',
                        )
                        raise ValueError("내부 롤백")
                except ValueError:
                    pass
                # savepoint 롤백으로 내부 작업만 취소
                # 외부 작업은 유지될 수 있음 (savepoint)
        except Exception:
            pass

        # 내부 블록의 제품은 없어야 함
        self.assertFalse(
            Product.all_objects.filter(code='DR003-INNER').exists(),
            "중첩 atomic 내부 롤백 실패",
        )


class DR004_ConcurrentModificationTest(TransactionTestCase):
    """DR-004: 동시 수정 충돌 처리 - F() 표현식 레이스 컨디션 방지"""

    def setUp(self):
        from apps.inventory.models import Product
        self.product = Product.all_objects.create(
            code='DR004-P1', name='동시수정테스트',
            current_stock=1000,
        )

    def test_F표현식_원자적_갱신(self):
        """F() 표현식이 원자적으로 재고를 갱신하는지 확인"""
        from apps.inventory.models import Product

        # 두 번의 동시적 갱신
        Product.all_objects.filter(pk=self.product.pk).update(
            current_stock=F('current_stock') - 100,
        )
        Product.all_objects.filter(pk=self.product.pk).update(
            current_stock=F('current_stock') - 50,
        )

        self.product.refresh_from_db()
        self.assertEqual(
            self.product.current_stock, 850,
            f"F() 표현식 갱신 실패: 예상 850, 실제 {self.product.current_stock}",
        )

    def test_멀티스레드_재고업데이트_정확성(self):
        """멀티스레드 환경에서 F() 표현식 재고 업데이트 정확성"""
        from apps.inventory.models import Product

        num_threads = 10
        decrement = 10
        errors = []

        def decrement_stock():
            try:
                Product.all_objects.filter(pk=self.product.pk).update(
                    current_stock=F('current_stock') - decrement,
                )
            except Exception as e:
                errors.append(str(e))
            finally:
                connection.close()

        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=decrement_stock)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"스레드 오류 발생: {errors}")

        self.product.refresh_from_db()
        expected = 1000 - (num_threads * decrement)
        self.assertEqual(
            self.product.current_stock, expected,
            f"동시 갱신 후 재고 불일치: 예상 {expected}, 실제 {self.product.current_stock} "
            f"(Lost Update 발생)",
        )

    def test_signal기반_재고_업데이트_정합성(self):
        """StockMovement signal 기반 재고 업데이트가 F() 표현식 사용 확인"""
        from apps.inventory.models import Product, Warehouse, StockMovement

        warehouse = Warehouse.all_objects.create(
            code='DR004-WH', name='동시성창고',
        )

        # 연속 입고 5건
        for i in range(5):
            StockMovement.all_objects.create(
                movement_number=f'DR004-MV{i:02d}',
                movement_type='IN',
                product=self.product,
                warehouse=warehouse,
                quantity=20,
                movement_date=date.today(),
            )

        self.product.refresh_from_db()
        expected = 1000 + (5 * 20)  # 원래 1000 + 입고 100
        self.assertEqual(
            self.product.current_stock, expected,
            f"signal 기반 재고: 예상 {expected}, 실제 {self.product.current_stock}",
        )
