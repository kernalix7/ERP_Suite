"""데모 데이터 생성 management command"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = '데모 데이터를 생성합니다 (개발/테스트/파일럿 환경용)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='기존 데모 데이터 삭제 후 재생성',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write('기존 데이터 정리 중...')
            self._flush()

        self.stdout.write('데모 데이터 생성 시작...')
        admin = self._create_users()
        categories = self._create_categories(admin)
        warehouses = self._create_warehouses(admin)
        products = self._create_products(admin, categories)
        partners = self._create_partners(admin)
        customers = self._create_customers(admin, products)
        orders = self._create_orders(admin, partners, customers, products)
        self._create_quotations(admin, partners, products)
        boms = self._create_boms(admin, products)
        self._create_production(admin, products, boms)
        self._create_purchase_orders(admin, partners, products, warehouses)
        self._create_accounting(admin, partners, orders)
        departments, positions = self._create_hr(admin)
        self._create_attendance(admin)
        self._create_boards(admin)
        self._create_investment(admin)

        self.stdout.write(self.style.SUCCESS('데모 데이터 생성 완료!'))

    def _flush(self):
        from apps.inventory.models import Category, Warehouse, Product, StockMovement
        from apps.sales.models import Partner, Customer, Order, Quotation
        from apps.production.models import BOM, ProductionPlan
        from apps.purchase.models import PurchaseOrder
        from apps.accounting.models import (
            TaxInvoice, AccountCode, Voucher, AccountReceivable,
            AccountPayable, FixedCost,
        )
        from apps.hr.models import Department, Position, EmployeeProfile
        from apps.attendance.models import AttendanceRecord, LeaveRequest, AnnualLeaveBalance
        from apps.board.models import Board
        from apps.investment.models import Investor, InvestmentRound

        from apps.production.models import ProductionRecord, WorkOrder
        from apps.board.models import Post, Comment
        from apps.investment.models import Investment, EquityChange, Distribution

        # Delete in dependency order (children first)
        for model in [
            Comment, Post, Board,
            Distribution, EquityChange, Investment, InvestmentRound, Investor,
            AttendanceRecord, LeaveRequest, AnnualLeaveBalance,
            FixedCost, AccountReceivable, AccountPayable,
            TaxInvoice, Voucher,
            ProductionRecord, WorkOrder, ProductionPlan, BOM,
            StockMovement, PurchaseOrder,
            Quotation, Order, Customer,
            Product, Category, Warehouse, Partner,
            EmployeeProfile, Department, Position,
        ]:
            model.objects.all().delete()

        User.objects.filter(is_superuser=False).delete()

    def _create_users(self):
        admin, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@erp.local',
                'role': 'admin',
                'name': '관리자',
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if not admin.has_usable_password():
            admin.set_password('admin1234!')
            admin.save()

        users_data = [
            ('manager1', '김매니저', 'manager', 'manager1@erp.local'),
            ('manager2', '이부장', 'manager', 'manager2@erp.local'),
            ('staff1', '박사원', 'staff', 'staff1@erp.local'),
            ('staff2', '최사원', 'staff', 'staff2@erp.local'),
            ('staff3', '정사원', 'staff', 'staff3@erp.local'),
        ]
        for username, name, role, email in users_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'role': role, 'name': name},
            )
            if created:
                user.set_password('demo1234!')
                user.save()

        self.stdout.write(f'  사용자: {User.objects.count()}명')
        return admin

    def _create_categories(self, admin):
        from apps.inventory.models import Category

        cats = {}
        for name in ['전자부품', '기구부품', '완제품', '포장재', '소모품']:
            cat, _ = Category.objects.get_or_create(
                name=name, defaults={'created_by': admin},
            )
            cats[name] = cat

        self.stdout.write(f'  카테고리: {len(cats)}개')
        return cats

    def _create_warehouses(self, admin):
        from apps.inventory.models import Warehouse

        wh_data = [
            ('WH-001', '본사 창고', '서울 강남구'),
            ('WH-002', '제2 창고', '경기 화성시'),
            ('WH-003', '출하 창고', '서울 강남구'),
        ]
        warehouses = []
        for code, name, location in wh_data:
            wh, _ = Warehouse.objects.get_or_create(
                code=code,
                defaults={'name': name, 'location': location, 'created_by': admin},
            )
            warehouses.append(wh)

        self.stdout.write(f'  창고: {len(warehouses)}개')
        return warehouses

    def _create_products(self, admin, categories):
        from apps.inventory.models import Product

        products_data = [
            ('RAW-001', 'PCB 기판', 'RAW', '전자부품', 5000, 3500, 500, 100),
            ('RAW-002', '저항 10kΩ (100pcs)', 'RAW', '전자부품', 2000, 1200, 2000, 500),
            ('RAW-003', '콘덴서 100μF (50pcs)', 'RAW', '전자부품', 3000, 2000, 1000, 300),
            ('RAW-004', 'LED 모듈', 'RAW', '전자부품', 8000, 5500, 300, 50),
            ('RAW-005', '플라스틱 케이스', 'RAW', '기구부품', 3500, 2200, 400, 100),
            ('RAW-006', '나사 세트 (10pcs)', 'RAW', '기구부품', 500, 300, 5000, 1000),
            ('RAW-007', '전원 어댑터', 'RAW', '전자부품', 12000, 8000, 200, 50),
            ('SEMI-001', '메인보드 조립체', 'SEMI', '전자부품', 25000, 18000, 150, 30),
            ('FIN-001', '스마트 센서 A100', 'FINISHED', '완제품', 89000, 45000, 80, 20),
            ('FIN-002', '스마트 센서 B200', 'FINISHED', '완제품', 129000, 65000, 50, 10),
            ('FIN-003', 'IoT 게이트웨이 G300', 'FINISHED', '완제품', 250000, 120000, 30, 5),
            ('FIN-004', 'LED 컨트롤러 L100', 'FINISHED', '완제품', 55000, 28000, 60, 15),
            ('PKG-001', '제품 박스 (소)', 'RAW', '포장재', 800, 500, 1000, 200),
            ('PKG-002', '제품 박스 (대)', 'RAW', '포장재', 1500, 900, 500, 100),
            ('CON-001', '납땜 와이어', 'RAW', '소모품', 15000, 10000, 50, 10),
        ]

        products = {}
        for code, name, ptype, cat_name, price, cost, stock, safety in products_data:
            prod, _ = Product.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'product_type': ptype,
                    'category': categories.get(cat_name),
                    'unit_price': price,
                    'cost_price': cost,
                    'current_stock': stock,
                    'safety_stock': safety,
                    'created_by': admin,
                },
            )
            products[code] = prod

        self.stdout.write(f'  제품: {len(products)}개')
        return products

    def _create_partners(self, admin):
        from apps.sales.models import Partner

        partners_data = [
            ('P-001', '(주)테크놀로지', 'BOTH', '123-45-67890', '김대표'),
            ('P-002', '삼성전자부품', 'SUPPLIER', '234-56-78901', '이사장'),
            ('P-003', '대한전자', 'CUSTOMER', '345-67-89012', '박사장'),
            ('P-004', '글로벌ICT', 'CUSTOMER', '456-78-90123', '최대표'),
            ('P-005', '부품나라', 'SUPPLIER', '567-89-01234', '정사장'),
            ('P-006', '스마트솔루션즈', 'CUSTOMER', '678-90-12345', '한대표'),
            ('P-007', '동양전자', 'BOTH', '789-01-23456', '윤대표'),
        ]

        partners = {}
        for code, name, ptype, biz_num, rep in partners_data:
            partner, _ = Partner.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'partner_type': ptype,
                    'business_number': biz_num,
                    'representative': rep,
                    'phone': f'02-{random.randint(1000,9999)}-{random.randint(1000,9999)}',
                    'email': f'contact@{name.replace("(주)", "").replace(" ", "").lower()}.co.kr',
                    'created_by': admin,
                },
            )
            partners[code] = partner

        self.stdout.write(f'  거래처: {len(partners)}개')
        return partners

    def _create_customers(self, admin, products):
        from apps.sales.models import Customer

        customers_data = [
            ('홍길동', '010-1234-5678', 'hong@example.com'),
            ('김철수', '010-2345-6789', 'kim@example.com'),
            ('이영희', '010-3456-7890', 'lee@example.com'),
            ('박지민', '010-4567-8901', 'park@example.com'),
            ('최수현', '010-5678-9012', 'choi@example.com'),
        ]

        customers = []
        finished = [p for p in products.values() if p.product_type == 'FINISHED']
        for name, phone, email in customers_data:
            prod = random.choice(finished) if finished else None
            cust, _ = Customer.objects.get_or_create(
                name=name, phone=phone,
                defaults={
                    'email': email,
                    'product': prod,
                    'purchase_date': date.today() - timedelta(days=random.randint(30, 365)),
                    'created_by': admin,
                },
            )
            customers.append(cust)

        self.stdout.write(f'  고객: {len(customers)}명')
        return customers

    def _create_orders(self, admin, partners, customers, products):
        from apps.sales.models import Order, OrderItem

        finished = {k: v for k, v in products.items() if v.product_type == 'FINISHED'}
        customer_partners = {k: v for k, v in partners.items()
                            if v.partner_type in ('CUSTOMER', 'BOTH')}

        orders = []
        statuses = ['DRAFT', 'CONFIRMED', 'CONFIRMED', 'DELIVERED', 'DELIVERED']
        for i in range(10):
            order_date = date.today() - timedelta(days=random.randint(1, 90))
            partner = random.choice(list(customer_partners.values()))
            customer = random.choice(customers) if customers else None
            status = random.choice(statuses)

            order, created = Order.objects.get_or_create(
                order_number=f'ORD-2026-{i+1:04d}',
                defaults={
                    'partner': partner,
                    'customer': customer,
                    'order_date': order_date,
                    'delivery_date': order_date + timedelta(days=random.randint(7, 30)),
                    'status': status,
                    'created_by': admin,
                },
            )
            if created:
                num_items = random.randint(1, 3)
                selected = random.sample(list(finished.values()), min(num_items, len(finished)))
                for prod in selected:
                    qty = random.randint(1, 10)
                    OrderItem.objects.create(
                        order=order,
                        product=prod,
                        quantity=qty,
                        unit_price=prod.unit_price,
                        created_by=admin,
                    )
            orders.append(order)

        self.stdout.write(f'  주문: {len(orders)}건')
        return orders

    def _create_quotations(self, admin, partners, products):
        from apps.sales.models import Quotation, QuotationItem

        finished = [v for v in products.values() if v.product_type == 'FINISHED']
        customer_partners = [v for v in partners.values()
                            if v.partner_type in ('CUSTOMER', 'BOTH')]

        count = 0
        for i in range(5):
            qdate = date.today() - timedelta(days=random.randint(1, 60))
            q, created = Quotation.objects.get_or_create(
                quote_number=f'QT-2026-{i+1:04d}',
                defaults={
                    'partner': random.choice(customer_partners),
                    'quote_date': qdate,
                    'valid_until': qdate + timedelta(days=30),
                    'status': random.choice(['DRAFT', 'SENT', 'ACCEPTED']),
                    'created_by': admin,
                },
            )
            if created:
                for prod in random.sample(finished, min(2, len(finished))):
                    QuotationItem.objects.create(
                        quotation=q, product=prod,
                        quantity=random.randint(5, 20),
                        unit_price=prod.unit_price,
                        created_by=admin,
                    )
                count += 1

        self.stdout.write(f'  견적: {count}건')

    def _create_boms(self, admin, products):
        from apps.production.models import BOM, BOMItem

        boms = {}

        bom_defs = {
            'FIN-001': [('RAW-001', 1), ('RAW-002', 2), ('RAW-003', 1), ('RAW-005', 1), ('RAW-06', 1)],
            'FIN-002': [('RAW-001', 1), ('RAW-002', 3), ('RAW-003', 2), ('RAW-004', 1), ('RAW-005', 1), ('RAW-07', 1)],
            'FIN-004': [('RAW-004', 2), ('RAW-001', 1), ('RAW-06', 1)],
        }

        for fin_code, materials in bom_defs.items():
            if fin_code not in products:
                continue
            bom, created = BOM.objects.get_or_create(
                product=products[fin_code], version='1.0',
                defaults={'is_default': True, 'created_by': admin},
            )
            if created:
                for mat_code, qty in materials:
                    if mat_code in products:
                        BOMItem.objects.create(
                            bom=bom, material=products[mat_code],
                            quantity=Decimal(str(qty)),
                            created_by=admin,
                        )
            boms[fin_code] = bom

        self.stdout.write(f'  BOM: {len(boms)}개')
        return boms

    def _create_production(self, admin, products, boms):
        from apps.production.models import ProductionPlan, WorkOrder

        count = 0
        for i, (fin_code, bom) in enumerate(boms.items()):
            plan, created = ProductionPlan.objects.get_or_create(
                plan_number=f'PP-2026-{i+1:04d}',
                defaults={
                    'product': products[fin_code],
                    'bom': bom,
                    'planned_quantity': random.randint(10, 50),
                    'planned_start': date.today() - timedelta(days=random.randint(1, 30)),
                    'planned_end': date.today() + timedelta(days=random.randint(7, 30)),
                    'status': random.choice(['DRAFT', 'CONFIRMED', 'IN_PROGRESS']),
                    'created_by': admin,
                },
            )
            if created:
                WorkOrder.objects.create(
                    order_number=f'WO-2026-{i+1:04d}',
                    production_plan=plan,
                    quantity=plan.planned_quantity,
                    status='PENDING',
                    created_by=admin,
                )
                count += 1

        self.stdout.write(f'  생산계획: {count}건')

    def _create_purchase_orders(self, admin, partners, products, warehouses):
        from apps.purchase.models import PurchaseOrder, PurchaseOrderItem

        suppliers = {k: v for k, v in partners.items()
                     if v.partner_type in ('SUPPLIER', 'BOTH')}
        raw_products = [v for v in products.values() if v.product_type == 'RAW']

        count = 0
        for i in range(5):
            odate = date.today() - timedelta(days=random.randint(1, 60))
            po, created = PurchaseOrder.objects.get_or_create(
                po_number=f'PO-2026-{i+1:04d}',
                defaults={
                    'partner': random.choice(list(suppliers.values())),
                    'order_date': odate,
                    'expected_date': odate + timedelta(days=random.randint(7, 21)),
                    'status': random.choice(['DRAFT', 'CONFIRMED', 'CONFIRMED']),
                    'created_by': admin,
                },
            )
            if created:
                for prod in random.sample(raw_products, min(3, len(raw_products))):
                    PurchaseOrderItem.objects.create(
                        purchase_order=po, product=prod,
                        quantity=random.randint(50, 500),
                        unit_price=prod.cost_price,
                        created_by=admin,
                    )
                count += 1

        self.stdout.write(f'  구매발주: {count}건')

    def _create_accounting(self, admin, partners, orders):
        from apps.accounting.models import (
            AccountCode, TaxInvoice, FixedCost,
            AccountReceivable, AccountPayable,
        )

        # 계정과목
        codes_data = [
            ('1000', '자산', 'ASSET'), ('1100', '현금', 'ASSET'),
            ('1200', '매출채권', 'ASSET'), ('1300', '재고자산', 'ASSET'),
            ('2000', '부채', 'LIABILITY'), ('2100', '매입채무', 'LIABILITY'),
            ('3000', '자본', 'EQUITY'), ('3100', '자본금', 'EQUITY'),
            ('4000', '매출', 'REVENUE'), ('4100', '상품매출', 'REVENUE'),
            ('5000', '매출원가', 'EXPENSE'), ('5100', '원재료비', 'EXPENSE'),
            ('6000', '판관비', 'EXPENSE'), ('6100', '급여', 'EXPENSE'),
            ('6200', '임차료', 'EXPENSE'), ('6300', '통신비', 'EXPENSE'),
        ]
        for code, name, atype in codes_data:
            AccountCode.objects.get_or_create(
                code=code, defaults={'name': name, 'account_type': atype, 'created_by': admin},
            )

        # 세금계산서
        customer_partners = [v for v in partners.values()
                            if v.partner_type in ('CUSTOMER', 'BOTH')]
        for i in range(5):
            idate = date.today() - timedelta(days=random.randint(1, 60))
            supply = random.randint(100, 1000) * 1000
            tax = int(supply * 0.1)
            partner = random.choice(customer_partners)
            TaxInvoice.objects.get_or_create(
                invoice_number=f'INV-2026-{i+1:04d}',
                defaults={
                    'invoice_type': 'SALES',
                    'partner': partner,
                    'issue_date': idate,
                    'supply_amount': supply,
                    'tax_amount': tax,
                    'total_amount': supply + tax,
                    'created_by': admin,
                },
            )

        # 고정비
        fixed_costs = [
            ('RENT', '사무실 임차료', 3000000),
            ('LABOR', '직원 급여 (5인)', 25000000),
            ('TELECOM', '인터넷/전화', 150000),
            ('SUBSCRIPTION', 'ERP 라이선스', 500000),
            ('INSURANCE', '화재보험', 200000),
        ]
        for cat, name, amount in fixed_costs:
            FixedCost.objects.get_or_create(
                category=cat, name=name,
                defaults={
                    'amount': amount,
                    'month': date.today().replace(day=1),
                    'created_by': admin,
                },
            )

        # 매출채권
        for partner in random.sample(customer_partners, min(3, len(customer_partners))):
            amt = random.randint(500, 5000) * 1000
            AccountReceivable.objects.get_or_create(
                partner=partner,
                defaults={
                    'amount': amt,
                    'due_date': date.today() + timedelta(days=random.randint(15, 60)),
                    'status': 'PENDING',
                    'created_by': admin,
                },
            )

        # 매입채무
        supplier_partners = [v for v in partners.values()
                            if v.partner_type in ('SUPPLIER', 'BOTH')]
        for partner in random.sample(supplier_partners, min(2, len(supplier_partners))):
            amt = random.randint(300, 3000) * 1000
            AccountPayable.objects.get_or_create(
                partner=partner,
                defaults={
                    'amount': amt,
                    'due_date': date.today() + timedelta(days=random.randint(15, 45)),
                    'status': 'PENDING',
                    'created_by': admin,
                },
            )

        self.stdout.write('  회계: 계정과목/세금계산서/고정비/채권·채무')

    def _create_hr(self, admin):
        from apps.hr.models import Department, Position, EmployeeProfile

        dept_data = [
            ('DEP-01', '경영지원'), ('DEP-02', '영업'),
            ('DEP-03', '생산'), ('DEP-04', 'R&D'), ('DEP-05', '품질관리'),
        ]
        departments = {}
        for code, name in dept_data:
            dept, _ = Department.objects.get_or_create(
                code=code, defaults={'name': name, 'created_by': admin},
            )
            departments[code] = dept

        pos_data = [
            ('대표이사', 1), ('부장', 2), ('차장', 3),
            ('과장', 4), ('대리', 5), ('사원', 6),
        ]
        positions = {}
        for name, level in pos_data:
            pos, _ = Position.objects.get_or_create(
                name=name, defaults={'level': level, 'created_by': admin},
            )
            positions[name] = pos

        # 직원 프로필
        users = User.objects.filter(is_superuser=False)
        dept_list = list(departments.values())
        pos_list = [positions.get('과장'), positions.get('대리'), positions.get('사원')]
        for i, user in enumerate(users):
            EmployeeProfile.objects.get_or_create(
                user=user,
                defaults={
                    'employee_number': f'EMP-{i+1:04d}',
                    'department': dept_list[i % len(dept_list)],
                    'position': pos_list[i % len(pos_list)],
                    'hire_date': date(2024, 1, 1) + timedelta(days=random.randint(0, 365)),
                    'created_by': admin,
                },
            )

        self.stdout.write(f'  인사: 부서 {len(departments)}, 직급 {len(positions)}, 직원 {users.count()}')
        return departments, positions

    def _create_attendance(self, admin):
        from apps.attendance.models import AttendanceRecord, AnnualLeaveBalance

        users = User.objects.filter(is_superuser=False)
        today = date.today()
        count = 0

        for user in users:
            # 연차 잔여
            AnnualLeaveBalance.objects.get_or_create(
                user=user, year=today.year,
                defaults={
                    'total_days': Decimal('15'),
                    'used_days': Decimal(str(random.randint(0, 8))),
                    'created_by': admin,
                },
            )

            # 최근 5일 출퇴근
            for d in range(5):
                work_date = today - timedelta(days=d + 1)
                if work_date.weekday() >= 5:
                    continue
                checkin = timezone.now().replace(
                    hour=random.choice([8, 8, 9, 9, 9]),
                    minute=random.randint(0, 59),
                )
                checkout = checkin + timedelta(hours=random.randint(8, 10))
                status = 'LATE' if checkin.hour >= 10 else 'NORMAL'
                _, created = AttendanceRecord.objects.get_or_create(
                    user=user, date=work_date,
                    defaults={
                        'check_in': checkin,
                        'check_out': checkout,
                        'status': status,
                        'created_by': admin,
                    },
                )
                if created:
                    count += 1

        self.stdout.write(f'  출퇴근: {count}건')

    def _create_boards(self, admin):
        from apps.board.models import Board, Post

        boards_data = [
            ('notice', '공지사항', True),
            ('general', '자유게시판', False),
            ('qna', '질문/답변', False),
        ]

        users = list(User.objects.all()[:3])
        total_posts = 0

        for slug, name, is_notice in boards_data:
            board, _ = Board.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'is_notice': is_notice, 'created_by': admin},
            )

            posts_content = {
                'notice': [
                    ('ERP 시스템 오픈 안내', '전사 ERP 시스템이 정식 오픈되었습니다. 모든 부서에서 사용 부탁드립니다.'),
                    ('시스템 정기점검 안내', '매주 일요일 02:00~06:00 시스템 정기점검이 진행됩니다.'),
                ],
                'general': [
                    ('신규 입사자 환영합니다', '이번 달 새로 합류하신 분들 환영합니다!'),
                    ('사내 동호회 모집', '등산 동호회 회원을 모집합니다. 관심 있으신 분은 연락주세요.'),
                ],
                'qna': [
                    ('재고 입고 방법 문의', '신규 원자재 입고 시 어떤 메뉴를 사용해야 하나요?'),
                    ('세금계산서 발행 절차', '매출 세금계산서 발행 절차에 대해 알려주세요.'),
                ],
            }

            for title, content in posts_content.get(slug, []):
                _, created = Post.objects.get_or_create(
                    board=board, title=title,
                    defaults={
                        'content': content,
                        'author': random.choice(users) if users else admin,
                        'is_pinned': is_notice,
                        'created_by': admin,
                    },
                )
                if created:
                    total_posts += 1

        self.stdout.write(f'  게시판: {len(boards_data)}개, 게시글: {total_posts}건')

    def _create_investment(self, admin):
        from apps.investment.models import Investor, InvestmentRound, Investment

        investors_data = [
            ('시드벤처', '김투자', 'seed@vc.kr'),
            ('성장파트너스', '이파트너', 'growth@partners.kr'),
            ('엔젤투자자 박', '박엔젤', 'angel@park.kr'),
        ]

        investors = []
        for name, contact, email in investors_data:
            inv, _ = Investor.objects.get_or_create(
                name=name,
                defaults={
                    'contact_person': contact,
                    'email': email,
                    'registration_date': date(2024, 1, 15),
                    'created_by': admin,
                },
            )
            investors.append(inv)

        # 투자 라운드
        round_data = [
            ('Seed', date(2024, 3, 1), 500000000, 2000000000),
            ('Series A', date(2025, 6, 1), 3000000000, 15000000000),
        ]
        for name, rdate, amount, valuation in round_data:
            rnd, created = InvestmentRound.objects.get_or_create(
                name=name,
                defaults={
                    'round_date': rdate,
                    'target_amount': amount,
                    'raised_amount': amount,
                    'pre_valuation': valuation - amount,
                    'post_valuation': valuation,
                    'created_by': admin,
                },
            )
            if created:
                inv_amount = amount // len(investors)
                for inv in investors:
                    Investment.objects.create(
                        investor=inv, round=rnd,
                        amount=inv_amount,
                        investment_date=rdate,
                        share_percentage=Decimal(str(round(
                            inv_amount / valuation * 100, 3
                        ))),
                        created_by=admin,
                    )

        self.stdout.write(f'  투자: 투자자 {len(investors)}명, 라운드 {len(round_data)}개')
