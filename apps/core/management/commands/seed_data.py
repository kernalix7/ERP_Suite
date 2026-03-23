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
        parser.add_argument(
            '--rich', action='store_true',
            help='풍부한 데모 데이터 생성 (모든 모델 포함, sandbox용)',
        )

    def handle(self, *args, **options):
        self.rich = options.get('rich', False)

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
        self._create_quotations(admin, partners, customers, products)
        boms = self._create_boms(admin, products)
        self._create_production(admin, products, boms)
        self._create_purchase_orders(admin, partners, products, warehouses)
        self._create_accounting(admin, partners, orders)
        bank_accounts = self._create_bank_accounts(admin)
        self._create_approval(admin)
        departments, positions = self._create_hr(admin)
        self._create_attendance(admin)
        self._create_boards(admin)
        self._create_investment(admin)

        if self.rich:
            self._create_stock_movements(admin, products, warehouses)
            self._create_stock_transfers(admin, products, warehouses)
            self._create_shipments(admin, orders)
            self._create_commissions(admin, partners, products, orders)
            self._create_goods_receipts(admin, warehouses)
            self._create_payments_vouchers(admin, partners, bank_accounts)
            self._create_account_transfers(admin, bank_accounts)
            self._create_service_requests(admin, customers, products)
            self._create_warranty_registrations(admin, products)
            self._create_calendar_events(admin)
            self._create_inquiries(admin)
            self._create_leave_requests(admin)
            self._create_personnel_actions(admin, departments, positions)
            self._create_approval_steps(admin)

        self.stdout.write(self.style.SUCCESS('데모 데이터 생성 완료!'))

    # =========================================================================
    # FLUSH
    # =========================================================================
    def _flush(self):
        from apps.inventory.models import Category, Warehouse, Product, StockMovement, StockTransfer
        from apps.sales.models import Partner, Customer, Order, Quotation, Shipment
        from apps.sales.commission import CommissionRate, CommissionRecord
        from apps.production.models import BOM, ProductionPlan, ProductionRecord, WorkOrder
        from apps.purchase.models import PurchaseOrder, GoodsReceipt
        from apps.accounting.models import (
            TaxInvoice, AccountCode, Voucher, VoucherLine, AccountReceivable,
            AccountPayable, FixedCost, BankAccount, AccountTransfer,
            Payment, PaymentDistribution, WithholdingTax,
        )
        from apps.approval.models import ApprovalRequest, ApprovalStep
        from apps.hr.models import Department, Position, EmployeeProfile, PersonnelAction
        from apps.attendance.models import AttendanceRecord, LeaveRequest, AnnualLeaveBalance
        from apps.board.models import Board, Post, Comment
        from apps.investment.models import Investor, InvestmentRound, Investment, EquityChange, Distribution
        from apps.warranty.models import ProductRegistration
        from apps.service.models import ServiceRequest, RepairRecord
        from apps.calendar_app.models import Event
        from apps.inquiry.models import InquiryChannel, Inquiry, InquiryReply, ReplyTemplate

        for model in [
            # Inquiry
            InquiryReply, Inquiry, InquiryChannel, ReplyTemplate,
            # Calendar
            Event,
            # Board
            Comment, Post, Board,
            # Investment
            Distribution, EquityChange, Investment, InvestmentRound, Investor,
            # Attendance
            AttendanceRecord, LeaveRequest, AnnualLeaveBalance,
            # HR
            PersonnelAction, EmployeeProfile, Department, Position,
            # Approval
            ApprovalStep, ApprovalRequest,
            # Accounting
            PaymentDistribution, Payment,
            AccountTransfer, WithholdingTax,
            VoucherLine, Voucher,
            FixedCost, AccountReceivable, AccountPayable,
            TaxInvoice, BankAccount,
            # Service / Warranty
            RepairRecord, ServiceRequest, ProductRegistration,
            # Sales
            CommissionRecord, CommissionRate,
            Shipment,
            # Production
            ProductionRecord, WorkOrder, ProductionPlan, BOM,
            # Purchase
            GoodsReceipt, PurchaseOrder,
            # Inventory
            StockTransfer, StockMovement,
            # Sales (parents)
            Quotation, Order, Customer,
            Product, Category, Warehouse, Partner,
        ]:
            model.objects.all().delete()

        User.objects.filter(is_superuser=False).delete()

    # =========================================================================
    # USERS
    # =========================================================================
    def _create_users(self):
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@erp.local',
                'role': 'admin',
                'name': '관리자',
                'is_staff': True,
                'is_superuser': True,
                'is_auditor': True,
            },
        )
        if created or not admin.password:
            admin.set_password('admin1234!')
            admin.save()

        users_data = [
            ('manager1', '김영수', 'manager', 'kim.ys@erp.local'),
            ('manager2', '이정민', 'manager', 'lee.jm@erp.local'),
            ('manager3', '박현우', 'manager', 'park.hw@erp.local'),
            ('staff1', '최지원', 'staff', 'choi.jw@erp.local'),
            ('staff2', '정서연', 'staff', 'jung.sy@erp.local'),
            ('staff3', '한도윤', 'staff', 'han.dy@erp.local'),
            ('staff4', '송민서', 'staff', 'song.ms@erp.local'),
            ('staff5', '윤하준', 'staff', 'yoon.hj@erp.local'),
        ]
        if self.rich:
            users_data += [
                ('staff6', '강예준', 'staff', 'kang.yj@erp.local'),
                ('staff7', '오수아', 'staff', 'oh.sa@erp.local'),
                ('staff8', '임시우', 'staff', 'lim.sw@erp.local'),
                ('staff9', '서지호', 'staff', 'seo.jh@erp.local'),
                ('staff10', '조하은', 'staff', 'jo.he@erp.local'),
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

    # =========================================================================
    # CATEGORIES
    # =========================================================================
    def _create_categories(self, admin):
        from apps.inventory.models import Category

        cats = {}
        top_cats = ['전자부품', '기구부품', '완제품', '포장재', '소모품']
        for name in top_cats:
            cat, _ = Category.objects.get_or_create(
                name=name, defaults={'created_by': admin},
            )
            cats[name] = cat

        if self.rich:
            sub_cats = {
                '전자부품': ['반도체', '수동소자', '커넥터', '센서'],
                '기구부품': ['플라스틱', '금속', '고무/실리콘'],
                '완제품': ['IoT 디바이스', '산업용 센서', 'LED 조명'],
            }
            for parent_name, children in sub_cats.items():
                parent = cats.get(parent_name)
                for child_name in children:
                    child, _ = Category.objects.get_or_create(
                        name=child_name,
                        defaults={'parent': parent, 'created_by': admin},
                    )
                    cats[child_name] = child

        self.stdout.write(f'  카테고리: {Category.objects.count()}개')
        return cats

    # =========================================================================
    # WAREHOUSES
    # =========================================================================
    def _create_warehouses(self, admin):
        from apps.inventory.models import Warehouse

        wh_data = [
            ('WH-001', '본사 창고', '서울 강남구 테헤란로 123'),
            ('WH-002', '제2 창고', '경기 화성시 동탄대로 456'),
            ('WH-003', '출하 창고', '서울 강남구 역삼로 78'),
        ]
        if self.rich:
            wh_data += [
                ('WH-004', '원자재 창고', '경기 화성시 동탄순환대로 90'),
                ('WH-005', '반품 창고', '서울 강남구 선릉로 55'),
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

    # =========================================================================
    # PRODUCTS
    # =========================================================================
    def _create_products(self, admin, categories):
        from apps.inventory.models import Product

        products_data = [
            ('RAW-001', 'PCB 기판 (양면)', 'RAW', '전자부품', 'EA', 5000, 3500, 500, 100),
            ('RAW-002', '저항 10kΩ (100pcs)', 'RAW', '전자부품', 'SET', 2000, 1200, 2000, 500),
            ('RAW-003', '콘덴서 100μF (50pcs)', 'RAW', '전자부품', 'SET', 3000, 2000, 1000, 300),
            ('RAW-004', 'LED 모듈 (RGB)', 'RAW', '전자부품', 'EA', 8000, 5500, 300, 50),
            ('RAW-005', '플라스틱 케이스 (A타입)', 'RAW', '기구부품', 'EA', 3500, 2200, 400, 100),
            ('RAW-006', '나사 세트 M3 (10pcs)', 'RAW', '기구부품', 'SET', 500, 300, 5000, 1000),
            ('RAW-007', '전원 어댑터 5V/2A', 'RAW', '전자부품', 'EA', 12000, 8000, 200, 50),
            ('RAW-008', '온도 센서 (NTC)', 'RAW', '전자부품', 'EA', 3200, 1800, 600, 150),
            ('RAW-009', '습도 센서 모듈', 'RAW', '전자부품', 'EA', 4500, 2800, 400, 100),
            ('RAW-010', '블루투스 모듈 (BLE 5.0)', 'RAW', '전자부품', 'EA', 15000, 9500, 250, 50),
            ('RAW-011', 'WiFi 모듈 (ESP32)', 'RAW', '전자부품', 'EA', 8500, 5200, 350, 80),
            ('RAW-012', '알루미늄 방열판', 'RAW', '기구부품', 'EA', 2500, 1500, 800, 200),
            ('RAW-013', 'USB-C 커넥터', 'RAW', '전자부품', 'EA', 1200, 700, 1500, 300),
            ('RAW-014', '리튬 배터리 3.7V 2000mAh', 'RAW', '전자부품', 'EA', 6500, 4200, 200, 40),
            ('RAW-015', '실리콘 개스킷', 'RAW', '기구부품', 'EA', 800, 450, 1200, 300),
            ('SEMI-001', '메인보드 조립체 v2', 'SEMI', '전자부품', 'EA', 25000, 18000, 150, 30),
            ('SEMI-002', '센서 보드 조립체', 'SEMI', '전자부품', 'EA', 18000, 12000, 100, 20),
            ('SEMI-003', 'LED 드라이버 보드', 'SEMI', '전자부품', 'EA', 12000, 7500, 120, 25),
            ('FIN-001', '스마트 센서 A100', 'FINISHED', '완제품', 'EA', 89000, 45000, 80, 20),
            ('FIN-002', '스마트 센서 B200 Pro', 'FINISHED', '완제품', 'EA', 129000, 65000, 50, 10),
            ('FIN-003', 'IoT 게이트웨이 G300', 'FINISHED', '완제품', 'EA', 250000, 120000, 30, 5),
            ('FIN-004', 'LED 컨트롤러 L100', 'FINISHED', '완제품', 'EA', 55000, 28000, 60, 15),
            ('FIN-005', '스마트 온습도계 TH500', 'FINISHED', '완제품', 'EA', 69000, 32000, 45, 10),
            ('FIN-006', '무선 환경 센서 E200', 'FINISHED', '완제품', 'EA', 159000, 78000, 25, 5),
            ('PKG-001', '제품 박스 (소)', 'RAW', '포장재', 'EA', 800, 500, 1000, 200),
            ('PKG-002', '제품 박스 (대)', 'RAW', '포장재', 'EA', 1500, 900, 500, 100),
            ('PKG-003', '완충재 (에어캡)', 'RAW', '포장재', 'M', 200, 120, 3000, 500),
            ('CON-001', '납땜 와이어', 'RAW', '소모품', 'ROLL', 15000, 10000, 50, 10),
            ('CON-002', '플럭스', 'RAW', '소모품', 'EA', 8000, 5000, 30, 5),
            ('CON-003', '열수축 튜브 세트', 'RAW', '소모품', 'SET', 3000, 1800, 100, 20),
        ]

        products = {}
        for row in products_data:
            code, name, ptype, cat_name = row[0], row[1], row[2], row[3]
            unit, price, cost, stock, safety = row[4], row[5], row[6], row[7], row[8]
            prod, _ = Product.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'product_type': ptype,
                    'category': categories.get(cat_name),
                    'unit': unit,
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

    # =========================================================================
    # PARTNERS
    # =========================================================================
    def _create_partners(self, admin):
        from apps.sales.models import Partner

        partners_data = [
            ('P-001', '(주)테크놀로지솔루션', 'BOTH', '123-45-67890', '김대표', '서울 서초구', '김상무', '02-555-0101'),
            ('P-002', '삼성전자부품(주)', 'SUPPLIER', '234-56-78901', '이사장', '경기 수원시', '이과장', '031-888-0202'),
            ('P-003', '대한전자(주)', 'CUSTOMER', '345-67-89012', '박사장', '서울 영등포구', '박대리', '02-666-0303'),
            ('P-004', '글로벌ICT', 'CUSTOMER', '456-78-90123', '최대표', '서울 마포구', '최팀장', '02-777-0404'),
            ('P-005', '부품나라', 'SUPPLIER', '567-89-01234', '정사장', '경기 안산시', '정주임', '031-999-0505'),
            ('P-006', '스마트솔루션즈(주)', 'CUSTOMER', '678-90-12345', '한대표', '서울 강남구', '한과장', '02-111-0606'),
            ('P-007', '동양전자(주)', 'BOTH', '789-01-23456', '윤대표', '인천 남동구', '윤부장', '032-222-0707'),
            ('P-008', '하이텍컴포넌트', 'SUPPLIER', '890-12-34567', '강대표', '경기 평택시', '강대리', '031-333-0808'),
            ('P-009', '에이스시스템', 'CUSTOMER', '901-23-45678', '오대표', '대전 유성구', '오차장', '042-444-0909'),
            ('P-010', '센서테크(주)', 'BOTH', '012-34-56789', '배대표', '경기 성남시', '배매니저', '031-555-1010'),
            ('P-011', '나노전자', 'SUPPLIER', '111-22-33344', '조대표', '충남 천안시', '조주임', '041-666-1111'),
            ('P-012', '미래에너지(주)', 'CUSTOMER', '222-33-44455', '임대표', '부산 해운대구', '임실장', '051-777-1212'),
        ]

        partners = {}
        for row in partners_data:
            code, name, ptype, biz_num, rep = row[0], row[1], row[2], row[3], row[4]
            address = row[5] if len(row) > 5 else ''
            contact_name = row[6] if len(row) > 6 else ''
            phone = row[7] if len(row) > 7 else f'02-{random.randint(1000,9999)}-{random.randint(1000,9999)}'
            partner, _ = Partner.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'partner_type': ptype,
                    'business_number': biz_num,
                    'representative': rep,
                    'contact_name': contact_name,
                    'phone': phone,
                    'email': f'contact@{name.replace("(주)", "").replace(" ", "").lower()}.co.kr',
                    'address': address,
                    'created_by': admin,
                },
            )
            partners[code] = partner

        self.stdout.write(f'  거래처: {len(partners)}개')
        return partners

    # =========================================================================
    # CUSTOMERS
    # =========================================================================
    def _create_customers(self, admin, products):
        from apps.sales.models import Customer

        customers_data = [
            ('홍길동', '010-1234-5678', 'hong@example.com', '서울 강남구 역삼동'),
            ('김철수', '010-2345-6789', 'kim@example.com', '경기 성남시 분당구'),
            ('이영희', '010-3456-7890', 'lee@example.com', '서울 서초구 방배동'),
            ('박지민', '010-4567-8901', 'park@example.com', '인천 연수구 송도동'),
            ('최수현', '010-5678-9012', 'choi@example.com', '경기 고양시 일산동구'),
            ('정우진', '010-6789-0123', 'jung@example.com', '서울 마포구 상암동'),
            ('강민지', '010-7890-1234', 'kang@example.com', '대전 유성구 봉명동'),
            ('한승우', '010-8901-2345', 'han@example.com', '부산 해운대구 우동'),
            ('오서연', '010-9012-3456', 'oh@example.com', '광주 서구 치평동'),
            ('윤재호', '010-0123-4567', 'yoon@example.com', '대구 수성구 범어동'),
        ]

        customers = []
        finished = [p for p in products.values() if p.product_type == 'FINISHED']
        for name, phone, email, address in customers_data:
            prod = random.choice(finished) if finished else None
            pdate = date.today() - timedelta(days=random.randint(30, 365))
            wend = pdate + timedelta(days=365)
            cust, _ = Customer.objects.get_or_create(
                name=name, phone=phone,
                defaults={
                    'email': email,
                    'address': address,
                    'product': prod,
                    'purchase_date': pdate,
                    'serial_number': f'SN-{random.randint(10000000, 99999999)}',
                    'warranty_end': wend,
                    'created_by': admin,
                },
            )
            customers.append(cust)

        self.stdout.write(f'  고객: {len(customers)}명')
        return customers

    # =========================================================================
    # ORDERS (with discounts)
    # =========================================================================
    def _create_orders(self, admin, partners, customers, products):
        from apps.sales.models import Order, OrderItem

        finished = {k: v for k, v in products.items() if v.product_type == 'FINISHED'}
        customer_partners = {k: v for k, v in partners.items()
                            if v.partner_type in ('CUSTOMER', 'BOTH')}

        orders = []
        count = 25 if self.rich else 10
        statuses = ['DRAFT', 'CONFIRMED', 'CONFIRMED', 'SHIPPED', 'DELIVERED', 'DELIVERED']
        discount_rates = [Decimal('0'), Decimal('0'), Decimal('0'), Decimal('5'), Decimal('10'), Decimal('3')]

        for i in range(count):
            order_date = date.today() - timedelta(days=random.randint(1, 120))
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
                    'shipping_address': customer.address if customer and hasattr(customer, 'address') else '',
                    'created_by': admin,
                },
            )
            if created:
                num_items = random.randint(1, 3)
                selected = random.sample(list(finished.values()), min(num_items, len(finished)))
                for prod in selected:
                    qty = random.randint(1, 15)
                    OrderItem.objects.create(
                        order=order,
                        product=prod,
                        quantity=qty,
                        unit_price=prod.unit_price,
                        discount_rate=random.choice(discount_rates),
                        created_by=admin,
                    )
                order.update_total()
            orders.append(order)

        self.stdout.write(f'  주문: {len(orders)}건')
        return orders

    # =========================================================================
    # QUOTATIONS
    # =========================================================================
    def _create_quotations(self, admin, partners, customers, products):
        from apps.sales.models import Quotation, QuotationItem

        finished = [v for v in products.values() if v.product_type == 'FINISHED']
        customer_partners = [v for v in partners.values()
                            if v.partner_type in ('CUSTOMER', 'BOTH')]

        count = 0
        total = 12 if self.rich else 5
        statuses = ['DRAFT', 'SENT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED']
        for i in range(total):
            qdate = date.today() - timedelta(days=random.randint(1, 90))
            q, created = Quotation.objects.get_or_create(
                quote_number=f'QT-2026-{i+1:04d}',
                defaults={
                    'partner': random.choice(customer_partners),
                    'customer': random.choice(customers) if customers else None,
                    'quote_date': qdate,
                    'valid_until': qdate + timedelta(days=30),
                    'status': random.choice(statuses),
                    'created_by': admin,
                },
            )
            if created:
                for prod in random.sample(finished, min(random.randint(1, 3), len(finished))):
                    QuotationItem.objects.create(
                        quotation=q, product=prod,
                        quantity=random.randint(5, 30),
                        unit_price=prod.unit_price,
                        discount_rate=random.choice([Decimal('0'), Decimal('0'), Decimal('5'), Decimal('8')]),
                        created_by=admin,
                    )
                q.update_total()
                count += 1

        self.stdout.write(f'  견적: {count}건')

    # =========================================================================
    # BOM
    # =========================================================================
    def _create_boms(self, admin, products):
        from apps.production.models import BOM, BOMItem

        boms = {}
        bom_defs = {
            'FIN-001': [('RAW-001', 1), ('RAW-002', 2), ('RAW-003', 1), ('RAW-005', 1), ('RAW-006', 1), ('RAW-008', 1)],
            'FIN-002': [('RAW-001', 1), ('RAW-002', 3), ('RAW-003', 2), ('RAW-004', 1), ('RAW-005', 1), ('RAW-007', 1), ('RAW-010', 1)],
            'FIN-003': [('RAW-001', 2), ('RAW-011', 1), ('RAW-010', 1), ('RAW-007', 1), ('RAW-005', 1), ('RAW-012', 2), ('RAW-013', 2)],
            'FIN-004': [('RAW-004', 2), ('RAW-001', 1), ('RAW-006', 1), ('SEMI-003', 1)],
            'FIN-005': [('RAW-001', 1), ('RAW-008', 1), ('RAW-009', 1), ('RAW-010', 1), ('RAW-005', 1), ('RAW-014', 1)],
            'FIN-006': [('RAW-001', 1), ('RAW-008', 1), ('RAW-009', 1), ('RAW-011', 1), ('RAW-014', 1), ('RAW-005', 1), ('RAW-015', 1)],
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
                            loss_rate=Decimal(str(random.choice([0, 0, 2, 3, 5]))),
                            created_by=admin,
                        )
            boms[fin_code] = bom

        # Semi-product BOMs
        semi_bom_defs = {
            'SEMI-001': [('RAW-001', 1), ('RAW-002', 3), ('RAW-003', 2), ('RAW-013', 1)],
            'SEMI-002': [('RAW-001', 1), ('RAW-008', 2), ('RAW-009', 1)],
            'SEMI-003': [('RAW-001', 1), ('RAW-004', 3), ('RAW-002', 2)],
        }
        for semi_code, materials in semi_bom_defs.items():
            if semi_code not in products:
                continue
            bom, created = BOM.objects.get_or_create(
                product=products[semi_code], version='1.0',
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
            boms[semi_code] = bom

        self.stdout.write(f'  BOM: {len(boms)}개')
        return boms

    # =========================================================================
    # PRODUCTION
    # =========================================================================
    def _create_production(self, admin, products, boms):
        from apps.production.models import ProductionPlan, WorkOrder, ProductionRecord

        workers = list(User.objects.filter(role='staff')[:5])
        count = 0
        plan_count = 8 if self.rich else 3

        fin_boms = [(k, v) for k, v in boms.items() if k.startswith('FIN')]
        for i in range(plan_count):
            fin_code, bom = fin_boms[i % len(fin_boms)]
            planned_qty = random.randint(10, 50)
            pstart = date.today() - timedelta(days=random.randint(5, 45))
            status = random.choice(['DRAFT', 'CONFIRMED', 'IN_PROGRESS', 'IN_PROGRESS', 'COMPLETED'])

            plan, created = ProductionPlan.objects.get_or_create(
                plan_number=f'PP-2026-{i+1:04d}',
                defaults={
                    'product': products[fin_code],
                    'bom': bom,
                    'planned_quantity': planned_qty,
                    'planned_start': pstart,
                    'planned_end': pstart + timedelta(days=random.randint(7, 21)),
                    'status': status,
                    'created_by': admin,
                },
            )
            if created:
                wo_status = 'COMPLETED' if status == 'COMPLETED' else (
                    'IN_PROGRESS' if status == 'IN_PROGRESS' else 'PENDING'
                )
                wo = WorkOrder.objects.create(
                    order_number=f'WO-2026-{i+1:04d}',
                    production_plan=plan,
                    assigned_to=random.choice(workers) if workers else None,
                    quantity=planned_qty,
                    status=wo_status,
                    started_at=timezone.now() - timedelta(days=random.randint(1, 20)) if wo_status != 'PENDING' else None,
                    completed_at=timezone.now() - timedelta(days=random.randint(0, 5)) if wo_status == 'COMPLETED' else None,
                    created_by=admin,
                )
                # Production records for in-progress / completed
                if self.rich and wo_status in ('IN_PROGRESS', 'COMPLETED'):
                    remaining = planned_qty
                    for d in range(random.randint(1, 3)):
                        if remaining <= 0:
                            break
                        good = min(random.randint(5, 20), remaining)
                        defect = random.randint(0, 2)
                        ProductionRecord.objects.create(
                            work_order=wo,
                            good_quantity=good,
                            defect_quantity=defect,
                            record_date=pstart + timedelta(days=d + 3),
                            worker=random.choice(workers) if workers else None,
                            created_by=admin,
                        )
                        remaining -= good

                count += 1

        self.stdout.write(f'  생산계획: {count}건')

    # =========================================================================
    # PURCHASE ORDERS
    # =========================================================================
    def _create_purchase_orders(self, admin, partners, products, warehouses):
        from apps.purchase.models import PurchaseOrder, PurchaseOrderItem

        suppliers = {k: v for k, v in partners.items()
                     if v.partner_type in ('SUPPLIER', 'BOTH')}
        raw_products = [v for v in products.values() if v.product_type == 'RAW']

        count = 0
        total = 12 if self.rich else 5
        statuses = ['DRAFT', 'CONFIRMED', 'CONFIRMED', 'CONFIRMED', 'PARTIAL_RECEIVED', 'RECEIVED']
        for i in range(total):
            odate = date.today() - timedelta(days=random.randint(1, 90))
            po, created = PurchaseOrder.objects.get_or_create(
                po_number=f'PO-2026-{i+1:04d}',
                defaults={
                    'partner': random.choice(list(suppliers.values())),
                    'order_date': odate,
                    'expected_date': odate + timedelta(days=random.randint(7, 21)),
                    'status': random.choice(statuses),
                    'created_by': admin,
                },
            )
            if created:
                for prod in random.sample(raw_products, min(random.randint(2, 5), len(raw_products))):
                    PurchaseOrderItem.objects.create(
                        purchase_order=po, product=prod,
                        quantity=random.randint(50, 500),
                        unit_price=prod.cost_price,
                        created_by=admin,
                    )
                po.update_total()
                count += 1

        self.stdout.write(f'  구매발주: {count}건')

    # =========================================================================
    # ACCOUNTING (Chart of Accounts, Tax Invoices, Fixed Costs, AR/AP)
    # =========================================================================
    def _create_accounting(self, admin, partners, orders):
        from apps.accounting.models import (
            AccountCode, TaxInvoice, FixedCost,
            AccountReceivable, AccountPayable, WithholdingTax,
        )

        # 계정과목 (확장)
        codes_data = [
            ('1000', '자산', 'ASSET'), ('1100', '현금및현금성자산', 'ASSET'),
            ('1110', '보통예금', 'ASSET'), ('1120', '정기예금', 'ASSET'),
            ('1200', '매출채권', 'ASSET'), ('1300', '재고자산', 'ASSET'),
            ('1400', '선급금', 'ASSET'), ('1500', '유형자산', 'ASSET'),
            ('2000', '부채', 'LIABILITY'), ('2100', '매입채무', 'LIABILITY'),
            ('2200', '미지급금', 'LIABILITY'), ('2300', '선수금', 'LIABILITY'),
            ('2400', '예수금', 'LIABILITY'), ('2500', '단기차입금', 'LIABILITY'),
            ('3000', '자본', 'EQUITY'), ('3100', '자본금', 'EQUITY'),
            ('3200', '이익잉여금', 'EQUITY'),
            ('4000', '매출', 'REVENUE'), ('4100', '상품매출', 'REVENUE'),
            ('4200', '제품매출', 'REVENUE'), ('4300', '서비스매출', 'REVENUE'),
            ('5000', '매출원가', 'EXPENSE'), ('5100', '원재료비', 'EXPENSE'),
            ('5200', '노무비', 'EXPENSE'), ('5300', '경비', 'EXPENSE'),
            ('6000', '판관비', 'EXPENSE'), ('6100', '급여', 'EXPENSE'),
            ('6200', '임차료', 'EXPENSE'), ('6300', '통신비', 'EXPENSE'),
            ('6400', '접대비', 'EXPENSE'), ('6500', '여비교통비', 'EXPENSE'),
            ('6600', '감가상각비', 'EXPENSE'), ('6700', '수선비', 'EXPENSE'),
            ('6800', '보험료', 'EXPENSE'), ('6900', '세금과공과', 'EXPENSE'),
        ]
        # Set parent relationships
        parent_map = {}
        for code, name, atype in codes_data:
            parent = None
            if len(code) == 4 and code[1:] != '000':
                parent_code = code[0] + '000'
                parent = parent_map.get(parent_code)
            obj, _ = AccountCode.objects.get_or_create(
                code=code, defaults={
                    'name': name, 'account_type': atype,
                    'parent': parent, 'created_by': admin,
                },
            )
            parent_map[code] = obj

        # 세금계산서 (매출 + 매입)
        customer_partners = [v for v in partners.values() if v.partner_type in ('CUSTOMER', 'BOTH')]
        supplier_partners = [v for v in partners.values() if v.partner_type in ('SUPPLIER', 'BOTH')]

        inv_count = 15 if self.rich else 5
        for i in range(inv_count):
            idate = date.today() - timedelta(days=random.randint(1, 90))
            is_sales = i < (inv_count * 2 // 3)
            supply = random.randint(200, 5000) * 1000
            tax = int(supply * 0.1)
            partner = random.choice(customer_partners if is_sales else supplier_partners)
            order = random.choice(orders) if is_sales and orders else None
            TaxInvoice.objects.get_or_create(
                invoice_number=f'INV-2026-{i+1:04d}',
                defaults={
                    'invoice_type': 'SALES' if is_sales else 'PURCHASE',
                    'partner': partner,
                    'order': order,
                    'issue_date': idate,
                    'supply_amount': supply,
                    'tax_amount': tax,
                    'total_amount': supply + tax,
                    'description': f'{"매출" if is_sales else "매입"} 세금계산서 ({partner.name})',
                    'created_by': admin,
                },
            )

        # 고정비 (최근 3개월)
        fixed_costs = [
            ('RENT', '사무실 임차료', 3000000),
            ('RENT', '공장 임차료', 5000000),
            ('LABOR', '직원 급여', 35000000),
            ('LABOR', '4대보험 사업주부담', 3500000),
            ('TELECOM', '인터넷/전화', 150000),
            ('SUBSCRIPTION', 'ERP 라이선스', 500000),
            ('SUBSCRIPTION', 'MS365 구독', 300000),
            ('INSURANCE', '화재보험', 200000),
            ('INSURANCE', '배상책임보험', 350000),
            ('EQUIPMENT', '설비 리스', 2000000),
            ('OTHER', '경비용역비', 800000),
        ]
        months = 3 if self.rich else 1
        for m in range(months):
            month_date = (date.today().replace(day=1) - timedelta(days=30 * m)).replace(day=1)
            for cat, name, amount in fixed_costs:
                FixedCost.objects.get_or_create(
                    category=cat, name=name, month=month_date,
                    defaults={'amount': amount, 'created_by': admin},
                )

        # 매출채권
        ar_statuses = ['PENDING', 'PENDING', 'PARTIAL', 'PAID', 'OVERDUE']
        for partner in customer_partners:
            for j in range(random.randint(1, 3)):
                amt = random.randint(500, 8000) * 1000
                status = random.choice(ar_statuses)
                paid = 0
                if status == 'PARTIAL':
                    paid = int(amt * random.choice([0.3, 0.5, 0.7]))
                elif status == 'PAID':
                    paid = amt
                AccountReceivable.objects.create(
                    partner=partner,
                    amount=amt,
                    paid_amount=paid,
                    due_date=date.today() + timedelta(days=random.randint(-30, 60)),
                    status=status,
                    created_by=admin,
                )

        # 매입채무
        ap_statuses = ['PENDING', 'PENDING', 'PARTIAL', 'PAID']
        for partner in supplier_partners:
            for j in range(random.randint(1, 2)):
                amt = random.randint(300, 5000) * 1000
                status = random.choice(ap_statuses)
                paid = 0
                if status == 'PARTIAL':
                    paid = int(amt * random.choice([0.4, 0.6]))
                elif status == 'PAID':
                    paid = amt
                AccountPayable.objects.create(
                    partner=partner,
                    amount=amt,
                    paid_amount=paid,
                    due_date=date.today() + timedelta(days=random.randint(-15, 45)),
                    status=status,
                    created_by=admin,
                )

        # 원천징수 (rich only)
        if self.rich:
            wh_data = [
                ('INCOME', '프리랜서 개발비', 5000000, Decimal('3.3')),
                ('INCOME', '디자인 외주비', 3000000, Decimal('3.3')),
                ('CORPORATE', '법인세 중간예납', 10000000, Decimal('10')),
            ]
            for tax_type, payee, gross, rate in wh_data:
                tax_amt = int(gross * rate / 100)
                WithholdingTax.objects.create(
                    tax_type=tax_type,
                    payee_name=payee,
                    payment_date=date.today() - timedelta(days=random.randint(1, 30)),
                    gross_amount=gross,
                    tax_rate=rate,
                    tax_amount=tax_amt,
                    net_amount=gross - tax_amt,
                    created_by=admin,
                )

        self.stdout.write('  회계: 계정과목/세금계산서/고정비/채권·채무/원천징수')

    # =========================================================================
    # BANK ACCOUNTS
    # =========================================================================
    def _create_bank_accounts(self, admin):
        from apps.accounting.models import BankAccount, AccountCode

        cash_code = AccountCode.objects.filter(code='1110').first() or AccountCode.objects.filter(code='1100').first()

        accounts_data = [
            ('법인 주거래 통장', 'BUSINESS', '(주)스마트ERP', '국민은행', '123-456-789012', True, 85000000),
            ('법인 예비 통장', 'BUSINESS', '(주)스마트ERP', '신한은행', '234-567-890123', False, 32000000),
            ('급여 전용 통장', 'BUSINESS', '(주)스마트ERP', '우리은행', '345-678-901234', False, 45000000),
            ('대표이사 개인', 'PERSONAL', '김대표', '하나은행', '456-789-012345', False, 15000000),
            ('네이버페이 정산', 'PLATFORM', '(주)스마트ERP', '네이버페이', '', False, 5800000),
            ('쿠팡 정산', 'PLATFORM', '(주)스마트ERP', '쿠팡', '', False, 3200000),
            ('11번가 정산', 'PLATFORM', '(주)스마트ERP', '11번가', '', False, 1500000),
        ]

        bank_accounts = []
        for name, atype, owner, bank, acc_num, is_default, balance in accounts_data:
            obj, _ = BankAccount.objects.get_or_create(
                name=name,
                defaults={
                    'account_type': atype,
                    'owner': owner,
                    'bank': bank,
                    'account_number': acc_num,
                    'is_default': is_default,
                    'account_code': cash_code,
                    'opening_balance': balance,
                    'balance': balance,
                    'created_by': admin,
                },
            )
            bank_accounts.append(obj)

        self.stdout.write(f'  계좌: {len(bank_accounts)}개')
        return bank_accounts

    # =========================================================================
    # APPROVAL
    # =========================================================================
    def _create_approval(self, admin):
        from apps.approval.models import ApprovalRequest

        managers = list(User.objects.filter(role='manager'))
        staff = list(User.objects.filter(role='staff'))
        if not managers:
            self.stdout.write('  결재: 매니저 없음 — 건너뜀')
            return

        approvals_data = [
            ('APR-2026-0001', '사무용품 구매 요청', 'PURCHASE', 250000, '복합기 토너 및 A4용지 구매 (경영지원팀)'),
            ('APR-2026-0002', '부산 출장 승인', 'TRAVEL', 450000, '3/25~3/26 부산 고객사 방문 출장 (숙박 1박 포함)'),
            ('APR-2026-0003', '3월 초과근무 수당', 'OVERTIME', 380000, '생산팀 3월 초과근무 38시간 수당 신청'),
            ('APR-2026-0004', '노트북 교체 요청', 'IT_REQUEST', 1800000, 'R&D팀 개발용 노트북 2대 교체 (맥북프로 14)'),
            ('APR-2026-0005', '하절기 휴가 계획', 'LEAVE', 0, '7/21~7/25 연차 5일 사용 신청'),
            ('APR-2026-0006', '전시회 참가비', 'EXPENSE', 5000000, '2026 스마트팩토리 전시회 부스 참가비'),
            ('APR-2026-0007', '원자재 긴급 발주', 'PURCHASE', 12000000, 'PCB 기판 긴급 발주 (납기 단축 할증 포함)'),
            ('APR-2026-0008', '서버 호스팅 계약', 'CONTRACT', 36000000, 'AWS 연간 호스팅 계약 갱신 (3년 약정)'),
        ]

        statuses = ['DRAFT', 'SUBMITTED', 'SUBMITTED', 'APPROVED', 'APPROVED', 'REJECTED']
        count = 0
        all_requesters = staff + managers
        for req_num, title, category, amount, desc in approvals_data:
            status = random.choice(statuses)
            requester = random.choice(all_requesters)
            approver = random.choice(managers)
            while approver == requester and len(managers) > 1:
                approver = random.choice(managers)

            _, created = ApprovalRequest.objects.get_or_create(
                request_number=req_num,
                defaults={
                    'title': title,
                    'category': category,
                    'amount': amount,
                    'content': desc,
                    'requester': requester,
                    'approver': approver,
                    'status': status,
                    'submitted_at': timezone.now() - timedelta(days=random.randint(1, 10)) if status != 'DRAFT' else None,
                    'approved_at': timezone.now() - timedelta(days=random.randint(0, 5)) if status == 'APPROVED' else None,
                    'reject_reason': '예산 초과로 재검토 필요' if status == 'REJECTED' else '',
                    'created_by': admin,
                },
            )
            if created:
                count += 1

        self.stdout.write(f'  결재: {count}건')

    # =========================================================================
    # HR
    # =========================================================================
    def _create_hr(self, admin):
        from apps.hr.models import Department, Position, EmployeeProfile

        dept_data = [
            ('DEP-01', '경영지원', None),
            ('DEP-02', '영업', None),
            ('DEP-03', '생산', None),
            ('DEP-04', 'R&D', None),
            ('DEP-05', '품질관리', None),
            ('DEP-06', '물류', None),
        ]
        departments = {}
        for code, name, parent_code in dept_data:
            parent = departments.get(parent_code)
            dept, _ = Department.objects.get_or_create(
                code=code, defaults={'name': name, 'parent': parent, 'created_by': admin},
            )
            departments[code] = dept

        pos_data = [
            ('대표이사', 1), ('이사', 2), ('부장', 3), ('차장', 4),
            ('과장', 5), ('대리', 6), ('주임', 7), ('사원', 8),
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
        pos_assignments = {
            'manager': ['부장', '차장', '과장'],
            'staff': ['대리', '주임', '사원'],
        }
        contract_types = ['FULL_TIME', 'FULL_TIME', 'FULL_TIME', 'CONTRACT']

        for i, user in enumerate(users):
            role_positions = pos_assignments.get(user.role, ['사원'])
            pos = positions.get(random.choice(role_positions), positions.get('사원'))
            EmployeeProfile.objects.get_or_create(
                user=user,
                defaults={
                    'employee_number': f'EMP-{i+1:04d}',
                    'department': dept_list[i % len(dept_list)],
                    'position': pos,
                    'hire_date': date(2023, 1, 1) + timedelta(days=random.randint(0, 730)),
                    'birth_date': date(1985, 1, 1) + timedelta(days=random.randint(0, 5475)),
                    'contract_type': random.choice(contract_types),
                    'status': 'ACTIVE',
                    'created_by': admin,
                },
            )

        # Set department managers
        for dept in departments.values():
            manager_profiles = EmployeeProfile.objects.filter(
                department=dept, position__level__lte=5,
            ).first()
            if manager_profiles:
                dept.manager = manager_profiles.user
                dept.save(update_fields=['manager'])

        self.stdout.write(f'  인사: 부서 {len(departments)}, 직급 {len(positions)}, 직원 {users.count()}')
        return departments, positions

    # =========================================================================
    # ATTENDANCE
    # =========================================================================
    def _create_attendance(self, admin):
        from apps.attendance.models import AttendanceRecord, AnnualLeaveBalance

        users = User.objects.filter(is_superuser=False)
        today = date.today()
        att_count = 0
        days_back = 30 if self.rich else 5

        for user in users:
            AnnualLeaveBalance.objects.get_or_create(
                user=user, year=today.year,
                defaults={
                    'total_days': Decimal('15'),
                    'used_days': Decimal(str(random.randint(0, 8))),
                    'created_by': admin,
                },
            )

            for d in range(days_back):
                work_date = today - timedelta(days=d + 1)
                if work_date.weekday() >= 5:
                    continue
                hour = random.choices([8, 9, 10, 7], weights=[40, 40, 5, 15])[0]
                minute = random.randint(0, 59)
                checkin = timezone.now().replace(hour=hour, minute=minute, second=0, microsecond=0) - timedelta(days=d + 1)
                checkout = checkin + timedelta(hours=random.choices([8, 9, 10, 11], weights=[30, 40, 20, 10])[0])

                if hour >= 10:
                    status = 'LATE'
                elif hour <= 7 and random.random() < 0.3:
                    status = 'NORMAL'
                else:
                    status = 'NORMAL'

                overtime = max(Decimal('0'), Decimal(str((checkout - checkin).seconds / 3600 - 8)))
                _, created = AttendanceRecord.objects.get_or_create(
                    user=user, date=work_date,
                    defaults={
                        'check_in': checkin,
                        'check_out': checkout,
                        'status': status,
                        'overtime_hours': overtime.quantize(Decimal('0.1')),
                        'created_by': admin,
                    },
                )
                if created:
                    att_count += 1

        self.stdout.write(f'  출퇴근: {att_count}건')

    # =========================================================================
    # BOARDS + COMMENTS
    # =========================================================================
    def _create_boards(self, admin):
        from apps.board.models import Board, Post, Comment

        boards_data = [
            ('notice', '공지사항', True, '전사 공지사항 게시판'),
            ('general', '자유게시판', False, '자유롭게 소통하는 게시판'),
            ('qna', '질문/답변', False, 'ERP 시스템 사용 Q&A'),
            ('suggestion', '건의사항', False, '회사 개선 건의'),
        ]

        users = list(User.objects.all()[:6])
        total_posts = 0
        total_comments = 0

        posts_content = {
            'notice': [
                ('ERP 시스템 정식 오픈 안내', '전사 ERP 시스템이 정식 오픈되었습니다.\n\n1. 모든 부서에서 즉시 사용 가능합니다.\n2. 매뉴얼은 공유폴더에 업로드 되었습니다.\n3. 문의사항은 경영지원팀으로 연락 바랍니다.'),
                ('시스템 정기점검 안내', '매주 일요일 02:00~06:00 시스템 정기점검이 진행됩니다.\n점검 시간에는 접속이 제한될 수 있으니 양해 부탁드립니다.'),
                ('개인정보 보호 교육 안내', '2026년 상반기 개인정보 보호 교육을 아래와 같이 진행합니다.\n- 일시: 4/5(월) 14:00~16:00\n- 장소: 대회의실\n- 대상: 전 직원 (필수)'),
                ('사무실 이전 안내', '4월 중순 사무실 이전이 예정되어 있습니다.\n- 이전일: 4/15(수)\n- 신규 주소: 서울 강남구 테헤란로 155\n- 이전 기간 중 재택근무 시행'),
            ],
            'general': [
                ('신규 입사자 환영합니다!', '이번 달 새로 합류하신 3분을 환영합니다! 🎉\n점심시간에 간단한 환영 모임이 있을 예정이니 많은 참석 부탁드립니다.'),
                ('사내 동호회 모집', '등산 동호회 신규 회원을 모집합니다!\n- 활동: 월 1회 주말 등산\n- 회비: 월 10,000원\n- 문의: 한도윤 대리'),
                ('점심 맛집 추천해주세요', '역삼역 근처 점심 맛집 추천 부탁드립니다.\n최근에 새로 오픈한 곳 있으면 알려주세요!'),
                ('금요일 회식 장소 투표', '이번 주 금요일 팀 회식 장소를 골라주세요.\n1. 고기집\n2. 횟집\n3. 이탈리안\n댓글로 투표해주세요!'),
                ('사내 풋살 대회 안내', '봄맞이 사내 풋살 대회를 개최합니다.\n- 일시: 4/12(토) 10:00\n- 장소: 양재 풋살장\n- 팀 구성: 부서 대항전'),
            ],
            'qna': [
                ('재고 입고 방법 문의', '신규 원자재 입고 시 어떤 메뉴를 사용해야 하나요?\n구매발주서가 있는 경우와 없는 경우를 각각 알려주세요.'),
                ('세금계산서 발행 절차', '매출 세금계산서 발행 절차를 알려주세요.\n특히 역발행 건은 어떻게 처리하나요?'),
                ('견적서 → 주문 전환 방법', '견적서에서 바로 주문으로 전환할 수 있나요?\n메뉴가 어디에 있는지 모르겠습니다.'),
                ('출퇴근 기록 수정 요청', '어제 퇴근 시간 찍는 것을 깜빡했는데,\n출퇴근 기록을 수정하려면 어떻게 해야 하나요?'),
                ('BOM 등록 시 loss rate란?', 'BOM 등록할 때 loss rate 항목이 있는데,\n이게 정확히 무엇을 의미하나요?'),
            ],
            'suggestion': [
                ('모바일 출퇴근 체크 건의', '현재 PC에서만 출퇴근이 가능한데,\n모바일 앱이나 모바일 웹에서도 체크인/아웃이 가능하면 좋겠습니다.'),
                ('대시보드 커스텀 기능 요청', '대시보드에 각자 필요한 위젯을 선택해서 배치할 수 있으면 좋겠습니다.\n부서마다 중요한 지표가 다릅니다.'),
            ],
        }

        comment_data = {
            'notice': [
                ['확인했습니다. 감사합니다!', '교육자료 사전에 공유해주시면 감사하겠습니다.'],
                ['주말 점검 중에도 읽기 전용으로 접속 가능한가요?'],
                ['필수 교육이면 시간 조정이 필요한 분은 어떻게 하나요?', '인사팀에 문의하세요.'],
            ],
            'general': [
                ['환영합니다! 같이 잘 해봐요 👋', '반갑습니다~'],
                ['저도 참가하고 싶습니다! 연락드릴게요.', '이번 주 관악산 가신다고 들었는데, 일정 공유 부탁드려요.'],
                ['역삼동 스시오마카세 추천합니다. 가성비 좋아요!', '테헤란로 쪽에 새로 생긴 쌀국수집도 괜찮아요.', '삼성역 근처 분식집도 추천!'],
                ['1번이요! 고기!', '3번 이탈리안에 한 표', '2번 횟집 추천합니다'],
            ],
            'qna': [
                ['구매 > 입고 메뉴에서 처리하시면 됩니다.', '발주서 없는 경우는 재고 > 입출고에서 직접 IN으로 생성하세요.'],
                ['회계 > 세금계산서에서 발행 가능합니다.'],
                ['견적서 상세 페이지에 "주문 전환" 버튼이 있습니다!', '감사합니다! 찾았어요.'],
            ],
            'suggestion': [
                ['좋은 건의입니다! 검토해보겠습니다.', 'PWA로 이미 모바일 접속이 가능한데, 출퇴근 기능이 최적화되면 좋겠네요.'],
            ],
        }

        for slug, name, is_notice, desc in boards_data:
            board, _ = Board.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'is_notice': is_notice, 'description': desc, 'created_by': admin},
            )

            for idx, (title, content) in enumerate(posts_content.get(slug, [])):
                post, created = Post.objects.get_or_create(
                    board=board, title=title,
                    defaults={
                        'content': content,
                        'author': random.choice(users) if users else admin,
                        'is_pinned': is_notice and idx == 0,
                        'view_count': random.randint(5, 120),
                        'created_by': admin,
                    },
                )
                if created:
                    total_posts += 1

                    # Comments
                    if self.rich:
                        slug_comments = comment_data.get(slug, [])
                        if idx < len(slug_comments):
                            for c_text in slug_comments[idx]:
                                Comment.objects.create(
                                    post=post,
                                    content=c_text,
                                    author=random.choice(users) if users else admin,
                                    created_by=admin,
                                )
                                total_comments += 1

        msg = f'  게시판: {len(boards_data)}개, 게시글: {total_posts}건'
        if total_comments:
            msg += f', 댓글: {total_comments}건'
        self.stdout.write(msg)

    # =========================================================================
    # INVESTMENT
    # =========================================================================
    def _create_investment(self, admin):
        from apps.investment.models import Investor, InvestmentRound, Investment, EquityChange, Distribution

        investors_data = [
            ('시드벤처캐피탈', '(주)시드벤처', '김투자', '02-1234-5678', 'seed@vc.kr'),
            ('성장파트너스', '성장파트너스(유)', '이파트너', '02-2345-6789', 'growth@partners.kr'),
            ('엔젤투자자 박', '', '박엔젤', '010-3456-7890', 'angel@park.kr'),
            ('테크인베스트', '(주)테크인베스트', '최벤처', '02-4567-8901', 'tech@invest.kr'),
        ]

        investors = []
        for name, company, contact, phone, email in investors_data:
            inv, _ = Investor.objects.get_or_create(
                name=name,
                defaults={
                    'company': company,
                    'contact_person': contact,
                    'phone': phone,
                    'email': email,
                    'registration_date': date(2024, 1, 15),
                    'created_by': admin,
                },
            )
            investors.append(inv)

        round_data = [
            ('Seed', 'SEED', date(2024, 3, 1), 500000000, 2000000000),
            ('Pre-A', 'PRE_A', date(2025, 1, 15), 1500000000, 8000000000),
            ('Series A', 'SERIES_A', date(2025, 9, 1), 5000000000, 25000000000),
        ]
        rounds = []
        for name, rtype, rdate, amount, valuation in round_data:
            rnd, created = InvestmentRound.objects.get_or_create(
                name=name,
                defaults={
                    'round_type': rtype,
                    'round_date': rdate,
                    'target_amount': amount,
                    'raised_amount': amount,
                    'pre_valuation': valuation - amount,
                    'post_valuation': valuation,
                    'created_by': admin,
                },
            )
            if created:
                participating = random.sample(investors, min(random.randint(2, 3), len(investors)))
                inv_amount = amount // len(participating)
                for inv in participating:
                    Investment.objects.create(
                        investor=inv, round=rnd,
                        amount=inv_amount,
                        investment_date=rdate,
                        share_percentage=Decimal(str(round(inv_amount / valuation * 100, 3))),
                        created_by=admin,
                    )
            rounds.append(rnd)

        # Equity changes & distributions (rich)
        if self.rich:
            for inv in investors[:2]:
                EquityChange.objects.create(
                    investor=inv,
                    change_type='DILUTION',
                    change_date=date(2025, 9, 1),
                    before_percentage=Decimal('8.333'),
                    after_percentage=Decimal('5.200'),
                    related_round=rounds[-1] if rounds else None,
                    created_by=admin,
                )

            for inv in investors:
                Distribution.objects.create(
                    investor=inv,
                    distribution_type='DIVIDEND',
                    amount=random.randint(5, 30) * 1000000,
                    scheduled_date=date(2026, 3, 31),
                    status='SCHEDULED',
                    fiscal_year=2025,
                    created_by=admin,
                )

        self.stdout.write(f'  투자: 투자자 {len(investors)}명, 라운드 {len(round_data)}개')

    # =========================================================================
    # RICH-ONLY DATA GENERATORS
    # =========================================================================

    def _create_stock_movements(self, admin, products, warehouses):
        """입출고 이력 (수동 재고 조정 제외, 운영 이력만)"""
        from apps.inventory.models import StockMovement

        if not warehouses:
            return

        count = 0
        raw_products = [v for v in products.values() if v.product_type == 'RAW']
        fin_products = [v for v in products.values() if v.product_type == 'FINISHED']

        for i in range(40):
            mv_date = date.today() - timedelta(days=random.randint(1, 60))
            if i < 20:
                # 입고 (원자재)
                prod = random.choice(raw_products)
                mv_type = 'IN'
                qty = random.randint(50, 300)
                wh = warehouses[0]
            elif i < 30:
                # 출고 (완제품) - 재고 확인 후 출고
                prod = random.choice(fin_products)
                prod.refresh_from_db()
                if prod.current_stock < 2:
                    continue
                mv_type = 'OUT'
                qty = random.randint(1, min(10, int(prod.current_stock) // 2))
                wh = warehouses[2] if len(warehouses) > 2 else warehouses[0]
            elif i < 35:
                # 재고 조정 (+)
                prod = random.choice(raw_products)
                mv_type = 'ADJ_PLUS'
                qty = random.randint(5, 20)
                wh = warehouses[0]
            else:
                # 반품
                prod = random.choice(fin_products)
                mv_type = 'RETURN'
                qty = random.randint(1, 3)
                wh = warehouses[2] if len(warehouses) > 2 else warehouses[0]

            _, created = StockMovement.objects.get_or_create(
                movement_number=f'MV-2026-{i+1:04d}',
                defaults={
                    'movement_type': mv_type,
                    'product': prod,
                    'warehouse': wh,
                    'quantity': qty,
                    'unit_price': prod.cost_price,
                    'movement_date': mv_date,
                    'reference': f'SEED-{mv_type}',
                    'created_by': admin,
                },
            )
            if created:
                count += 1

        self.stdout.write(f'  입출고: {count}건')

    def _create_stock_transfers(self, admin, products, warehouses):
        """창고간 이동"""
        from apps.inventory.models import StockTransfer

        if len(warehouses) < 2:
            return

        count = 0
        all_products = list(products.values())
        for i in range(8):
            from_wh, to_wh = random.sample(warehouses[:3], 2)
            prod = random.choice(all_products)
            # 현재 재고 확인 - 재고보다 많이 이동하면 CHECK constraint 위반
            prod.refresh_from_db()
            if prod.current_stock < 5:
                continue
            max_qty = min(int(prod.current_stock) // 2, 50)
            qty = random.randint(1, max(1, max_qty))
            _, created = StockTransfer.objects.get_or_create(
                transfer_number=f'TF-2026-{i+1:04d}',
                defaults={
                    'from_warehouse': from_wh,
                    'to_warehouse': to_wh,
                    'product': prod,
                    'quantity': qty,
                    'transfer_date': date.today() - timedelta(days=random.randint(1, 30)),
                    'created_by': admin,
                },
            )
            if created:
                count += 1

        self.stdout.write(f'  창고이동: {count}건')

    def _create_shipments(self, admin, orders):
        """배송 정보"""
        from apps.sales.models import Shipment, Order

        shipped_orders = Order.objects.filter(status__in=['SHIPPED', 'DELIVERED'])
        carriers = ['CJ', 'HANJIN', 'LOTTE', 'LOGEN', 'POST']
        statuses_map = {
            'SHIPPED': ['SHIPPED', 'IN_TRANSIT'],
            'DELIVERED': ['DELIVERED'],
        }

        count = 0
        for i, order in enumerate(shipped_orders):
            ship_date = order.order_date + timedelta(days=random.randint(1, 5))
            ship_status = random.choice(statuses_map.get(order.status, ['SHIPPED']))
            delivered_date = ship_date + timedelta(days=random.randint(1, 3)) if ship_status == 'DELIVERED' else None

            _, created = Shipment.objects.get_or_create(
                shipment_number=f'SHP-2026-{i+1:04d}',
                defaults={
                    'order': order,
                    'carrier': random.choice(carriers),
                    'tracking_number': f'{random.randint(100000000000, 999999999999)}',
                    'status': ship_status,
                    'shipped_date': ship_date,
                    'delivered_date': delivered_date,
                    'receiver_name': order.customer.name if order.customer else '수취인',
                    'receiver_phone': order.customer.phone if order.customer else '010-0000-0000',
                    'receiver_address': order.shipping_address or '서울 강남구',
                    'created_by': admin,
                },
            )
            if created:
                count += 1

        self.stdout.write(f'  배송: {count}건')

    def _create_commissions(self, admin, partners, products, orders):
        """수수료율 & 수수료 기록"""
        from apps.sales.commission import CommissionRate, CommissionRecord

        customer_partners = [v for v in partners.values() if v.partner_type in ('CUSTOMER', 'BOTH')]
        finished = [v for v in products.values() if v.product_type == 'FINISHED']

        rate_count = 0
        for partner in customer_partners:
            for prod in random.sample(finished, min(2, len(finished))):
                _, created = CommissionRate.objects.get_or_create(
                    partner=partner, product=prod,
                    defaults={'rate': Decimal(str(random.choice([3, 5, 7, 10]))), 'created_by': admin},
                )
                if created:
                    rate_count += 1

        rec_count = 0
        from apps.sales.models import Order
        delivered_orders = Order.objects.filter(status='DELIVERED').select_related('partner')[:10]
        for order in delivered_orders:
            rate_obj = CommissionRate.objects.filter(partner=order.partner).first()
            rate = rate_obj.rate if rate_obj else Decimal('5')
            amount = order.total_amount
            comm_amount = int(amount * rate / 100)
            CommissionRecord.objects.create(
                partner=order.partner,
                order=order,
                order_amount=amount,
                commission_rate=rate,
                commission_amount=comm_amount,
                status=random.choice(['PENDING', 'SETTLED']),
                settled_date=date.today() - timedelta(days=random.randint(0, 10)) if random.random() > 0.5 else None,
                created_by=admin,
            )
            rec_count += 1

        self.stdout.write(f'  수수료: 요율 {rate_count}건, 기록 {rec_count}건')

    def _create_goods_receipts(self, admin, warehouses):
        """입고 처리 (CONFIRMED 이상 PO 대상)"""
        from apps.purchase.models import PurchaseOrder, GoodsReceipt, GoodsReceiptItem

        confirmed_pos = PurchaseOrder.objects.filter(
            status__in=['CONFIRMED', 'PARTIAL_RECEIVED', 'RECEIVED'],
        ).prefetch_related('items')[:6]

        count = 0
        for i, po in enumerate(confirmed_pos):
            gr, created = GoodsReceipt.objects.get_or_create(
                receipt_number=f'GR-2026-{i+1:04d}',
                defaults={
                    'purchase_order': po,
                    'receipt_date': po.order_date + timedelta(days=random.randint(7, 14)),
                    'created_by': admin,
                },
            )
            if created:
                for po_item in po.items.all():
                    recv_qty = min(po_item.quantity, random.randint(
                        int(po_item.quantity * 0.5), po_item.quantity,
                    ))
                    GoodsReceiptItem.objects.create(
                        goods_receipt=gr,
                        po_item=po_item,
                        received_quantity=recv_qty,
                        is_inspected=random.choice([True, True, False]),
                        created_by=admin,
                    )
                count += 1

        self.stdout.write(f'  입고: {count}건')

    def _create_payments_vouchers(self, admin, partners, bank_accounts):
        """입출금 기록 & 전표"""
        from apps.accounting.models import (
            Payment, Voucher, VoucherLine, AccountCode,
        )

        customer_partners = [v for v in partners.values() if v.partner_type in ('CUSTOMER', 'BOTH')]
        supplier_partners = [v for v in partners.values() if v.partner_type in ('SUPPLIER', 'BOTH')]
        default_account = bank_accounts[0] if bank_accounts else None

        cash_code = AccountCode.objects.filter(code='1110').first() or AccountCode.objects.filter(code='1100').first()
        ar_code = AccountCode.objects.filter(code='1200').first()
        ap_code = AccountCode.objects.filter(code='2100').first()
        revenue_code = AccountCode.objects.filter(code='4100').first()
        expense_code = AccountCode.objects.filter(code='5100').first()

        # Vouchers (전표)
        voucher_count = 0
        for i in range(15):
            vdate = date.today() - timedelta(days=random.randint(1, 60))
            vtype = random.choice(['RECEIPT', 'PAYMENT', 'TRANSFER'])
            amount = random.randint(100, 3000) * 1000

            v, created = Voucher.objects.get_or_create(
                voucher_number=f'V-2026-{i+1:04d}',
                defaults={
                    'voucher_type': vtype,
                    'voucher_date': vdate,
                    'description': f'{"입금" if vtype == "RECEIPT" else "출금" if vtype == "PAYMENT" else "대체"} 전표',
                    'approval_status': random.choice(['DRAFT', 'APPROVED', 'APPROVED']),
                    'created_by': admin,
                },
            )
            if created and cash_code:
                if vtype == 'RECEIPT' and ar_code:
                    VoucherLine.objects.create(voucher=v, account=cash_code, debit=amount, credit=0, description='입금', created_by=admin)
                    VoucherLine.objects.create(voucher=v, account=ar_code, debit=0, credit=amount, description='매출채권 회수', created_by=admin)
                elif vtype == 'PAYMENT' and ap_code:
                    VoucherLine.objects.create(voucher=v, account=ap_code, debit=amount, credit=0, description='매입채무 상환', created_by=admin)
                    VoucherLine.objects.create(voucher=v, account=cash_code, debit=0, credit=amount, description='출금', created_by=admin)
                elif revenue_code and expense_code:
                    VoucherLine.objects.create(voucher=v, account=revenue_code, debit=0, credit=amount, description='매출', created_by=admin)
                    VoucherLine.objects.create(voucher=v, account=expense_code, debit=amount, credit=0, description='원가', created_by=admin)
                voucher_count += 1

        # Payments (입출금)
        payment_count = 0
        methods = ['BANK_TRANSFER', 'BANK_TRANSFER', 'CASH', 'CARD']
        for i in range(20):
            pdate = date.today() - timedelta(days=random.randint(1, 60))
            is_receipt = i < 12
            partner = random.choice(customer_partners if is_receipt else supplier_partners)
            amount = random.randint(200, 5000) * 1000

            Payment.objects.create(
                payment_number=f'PAY-2026-{i+1:04d}',
                payment_type='RECEIPT' if is_receipt else 'DISBURSEMENT',
                partner=partner,
                bank_account=random.choice(bank_accounts) if bank_accounts else None,
                amount=amount,
                payment_date=pdate,
                payment_method=random.choice(methods),
                reference=f'{"매출대금" if is_receipt else "원자재대금"} ({partner.name})',
                created_by=admin,
            )
            payment_count += 1

        self.stdout.write(f'  전표: {voucher_count}건, 입출금: {payment_count}건')

    def _create_account_transfers(self, admin, bank_accounts):
        """계좌간 이체"""
        from apps.accounting.models import AccountTransfer

        if len(bank_accounts) < 2:
            return

        count = 0
        for i in range(5):
            from_acc, to_acc = random.sample(bank_accounts[:4], 2)
            AccountTransfer.objects.create(
                transfer_number=f'AT-2026-{i+1:04d}',
                from_account=from_acc,
                to_account=to_acc,
                amount=random.randint(1000, 10000) * 1000,
                transfer_date=date.today() - timedelta(days=random.randint(1, 30)),
                description=f'{from_acc.name} → {to_acc.name} 자금이체',
                created_by=admin,
            )
            count += 1

        self.stdout.write(f'  계좌이체: {count}건')

    def _create_service_requests(self, admin, customers, products):
        """A/S 요청 + 수리 이력"""
        from apps.service.models import ServiceRequest, RepairRecord

        finished = [v for v in products.values() if v.product_type == 'FINISHED']
        technicians = list(User.objects.filter(role='staff')[:3])

        sr_data = [
            ('SR-2026-0001', 'WARRANTY', '전원 불량', '제품 전원이 켜지지 않습니다.'),
            ('SR-2026-0002', 'PAID', '센서 오작동', '온도 센서 값이 실제보다 5도 높게 측정됩니다.'),
            ('SR-2026-0003', 'WARRANTY', 'LED 깜빡임', 'LED 제어 시 불규칙 깜빡임 발생'),
            ('SR-2026-0004', 'EXCHANGE', '외관 불량', '케이스 크랙 발생 — 교환 요청'),
            ('SR-2026-0005', 'PAID', 'WiFi 연결 불안정', '간헐적 WiFi 연결 끊김'),
            ('SR-2026-0006', 'REFUND', '기능 불만족', '광고 대비 성능 부족 — 환불 요청'),
            ('SR-2026-0007', 'WARRANTY', '배터리 부풀음', '배터리가 부풀어 오름'),
            ('SR-2026-0008', 'PAID', '펌웨어 오류', '펌웨어 업데이트 후 부팅 안됨'),
        ]

        statuses = ['RECEIVED', 'INSPECTING', 'REPAIRING', 'COMPLETED', 'COMPLETED', 'RETURNED']
        count = 0
        repair_count = 0

        for req_num, req_type, symptom, detail in sr_data:
            customer = random.choice(customers)
            prod = random.choice(finished)
            status = random.choice(statuses)
            recv_date = date.today() - timedelta(days=random.randint(3, 45))
            comp_date = recv_date + timedelta(days=random.randint(3, 14)) if status in ('COMPLETED', 'RETURNED') else None

            sr, created = ServiceRequest.objects.get_or_create(
                request_number=req_num,
                defaults={
                    'customer': customer,
                    'product': prod,
                    'serial_number': f'SN-{random.randint(10000000, 99999999)}',
                    'request_type': req_type,
                    'status': status,
                    'symptom': f'{symptom}\n\n상세: {detail}',
                    'received_date': recv_date,
                    'completed_date': comp_date,
                    'is_warranty': req_type == 'WARRANTY',
                    'created_by': admin,
                },
            )
            if created:
                count += 1
                # 수리 이력
                if status in ('REPAIRING', 'COMPLETED', 'RETURNED'):
                    repairs_needed = random.randint(1, 2)
                    for r in range(repairs_needed):
                        RepairRecord.objects.create(
                            service_request=sr,
                            repair_date=recv_date + timedelta(days=r + 2),
                            description=f'{symptom} 수리 {"1차 점검" if r == 0 else "2차 수리 완료"}',
                            parts_used='전원보드' if 'power' in symptom.lower() or '전원' in symptom else '센서 모듈 교체',
                            cost=0 if req_type == 'WARRANTY' else random.randint(20, 80) * 1000,
                            technician=random.choice(technicians) if technicians else None,
                            created_by=admin,
                        )
                        repair_count += 1

        self.stdout.write(f'  A/S: {count}건, 수리: {repair_count}건')

    def _create_warranty_registrations(self, admin, products):
        """정품등록"""
        from apps.warranty.models import ProductRegistration

        finished = [v for v in products.values() if v.product_type == 'FINISHED']
        names = ['김지수', '박현준', '이서연', '최도현', '정유나', '한승민', '오지윤', '윤태우', '강하린', '임준혁',
                 '서예은', '조성훈', '배소율', '신동해', '황미래']

        count = 0
        for i, name in enumerate(names):
            prod = random.choice(finished)
            pdate = date.today() - timedelta(days=random.randint(30, 365))
            _, created = ProductRegistration.objects.get_or_create(
                serial_number=f'{random.randint(10000000, 99999999):08X}',
                defaults={
                    'product': prod,
                    'customer_name': name,
                    'phone': f'010-{random.randint(1000,9999)}-{random.randint(1000,9999)}',
                    'email': f'{name.lower().replace(" ", "")}@example.com',
                    'purchase_date': pdate,
                    'purchase_channel': random.choice(['공식몰', '네이버', '쿠팡', '11번가', '오프라인']),
                    'warranty_start': pdate,
                    'warranty_end': pdate + timedelta(days=365),
                    'is_verified': random.choice([True, True, False]),
                    'created_by': admin,
                },
            )
            if created:
                count += 1

        self.stdout.write(f'  정품등록: {count}건')

    def _create_calendar_events(self, admin):
        """캘린더 일정"""
        from apps.calendar_app.models import Event

        users = list(User.objects.all()[:6])
        events_data = [
            ('주간 경영회의', 'MEETING', '#3B82F6', '대회의실', False),
            ('영업팀 미팅', 'TEAM', '#10B981', '소회의실 A', False),
            ('생산 현황 리뷰', 'MEETING', '#F59E0B', '소회의실 B', False),
            ('스마트팩토리 전시회', 'COMPANY', '#EF4444', 'COEX', True),
            ('신제품 런칭 행사', 'COMPANY', '#8B5CF6', '본사 로비', True),
            ('분기 워크숍', 'COMPANY', '#EC4899', '양평 리조트', True),
            ('대한전자 미팅', 'MEETING', '#3B82F6', '고객사 방문', False),
            ('ISO 인증 심사', 'COMPANY', '#EF4444', '본사', True),
            ('팀 빌딩 행사', 'TEAM', '#10B981', '난지캠핑장', True),
            ('R&D 기술 세미나', 'TEAM', '#F59E0B', '대회의실', False),
            ('1분기 실적 발표', 'COMPANY', '#8B5CF6', '대회의실', False),
            ('채용 면접', 'MEETING', '#3B82F6', '소회의실 A', False),
        ]

        count = 0
        for i, (title, etype, color, location, all_day) in enumerate(events_data):
            days_offset = random.randint(-15, 30)
            start = timezone.now() + timedelta(days=days_offset, hours=random.randint(9, 15))
            end = start + timedelta(hours=random.randint(1, 4)) if not all_day else start + timedelta(days=random.randint(1, 3))

            event, created = Event.objects.get_or_create(
                title=title, start_datetime=start,
                defaults={
                    'description': f'{title} 일정입니다.',
                    'end_datetime': end,
                    'all_day': all_day,
                    'event_type': etype,
                    'color': color,
                    'location': location,
                    'creator': random.choice(users) if users else admin,
                    'created_by': admin,
                },
            )
            if created:
                # Add attendees
                attendees = random.sample(users, min(random.randint(2, 5), len(users)))
                event.attendees.set(attendees)
                count += 1

        self.stdout.write(f'  캘린더: {count}건')

    def _create_inquiries(self, admin):
        """문의 관리"""
        from apps.inquiry.models import InquiryChannel, Inquiry, InquiryReply, ReplyTemplate

        channels_data = [
            ('전화', 'phone'), ('이메일', 'email'), ('카카오톡', 'chat'),
            ('홈페이지', 'globe'), ('네이버 톡톡', 'message-circle'),
        ]
        channels = []
        for name, icon in channels_data:
            ch, _ = InquiryChannel.objects.get_or_create(
                name=name, defaults={'icon': icon, 'created_by': admin},
            )
            channels.append(ch)

        # 답변 템플릿
        templates = [
            ('배송', '배송 조회 안내', '안녕하세요.\n배송 조회는 택배사 홈페이지에서 운송장 번호로 확인하실 수 있습니다.\n감사합니다.'),
            ('반품', '반품/교환 안내', '안녕하세요.\n반품/교환은 수령 후 7일 이내 가능합니다.\n고객센터로 연락 주시면 안내 도와드리겠습니다.'),
            ('A/S', 'A/S 접수 안내', '안녕하세요.\nA/S 접수는 서비스 > A/S 요청 메뉴에서 가능합니다.\n접수 후 1~2일 내 담당 기사가 연락드립니다.'),
        ]
        for cat, title, content in templates:
            ReplyTemplate.objects.get_or_create(
                category=cat, title=title,
                defaults={'content': content, 'created_by': admin},
            )

        staff = list(User.objects.filter(role='staff')[:4])
        inquiries_data = [
            ('제품 배송 일정 문의', '주문한 스마트 센서 A100이 언제 배송되나요?', '김하나', '010-1111-2222', 'HIGH'),
            ('대량 구매 할인 문의', '50대 이상 구매 시 할인 가능한가요?', '박둘', '02-3333-4444', 'NORMAL'),
            ('A/S 접수 방법', '보증기간 내 A/S 접수는 어떻게 하나요?', '이세셋', '010-5555-6666', 'NORMAL'),
            ('IoT 게이트웨이 호환성', 'G300이 기존 시스템과 호환되나요?', '최네넷', 'choi4@test.com', 'HIGH'),
            ('견적서 요청', '스마트 센서 B200 Pro 100대 견적 부탁드립니다.', '정다섯', '02-7777-8888', 'URGENT'),
            ('납품 기한 조율', '4월 납기를 3월로 앞당길 수 있나요?', '한여섯', '010-9999-0000', 'HIGH'),
            ('제품 사양 문의', 'LED 컨트롤러 L100의 최대 출력은?', '강일곱', 'kang7@test.com', 'LOW'),
            ('반품 요청', '불량품 반품 처리 부탁드립니다.', '오여덟', '010-1212-3434', 'NORMAL'),
            ('기술지원 요청', '펌웨어 업데이트 방법을 알려주세요.', '윤아홉', '010-5656-7878', 'NORMAL'),
            ('신제품 출시 일정', '2분기 신제품 출시 일정이 있나요?', '임열', '010-9090-1212', 'LOW'),
        ]

        inq_count = 0
        reply_count = 0
        statuses = ['RECEIVED', 'WAITING', 'REPLIED', 'REPLIED', 'CLOSED']

        for subject, content, cname, ccontact, priority in inquiries_data:
            status = random.choice(statuses)
            inq = Inquiry.objects.create(
                channel=random.choice(channels),
                customer_name=cname,
                customer_contact=ccontact,
                subject=subject,
                content=content,
                status=status,
                priority=priority,
                received_date=timezone.now() - timedelta(days=random.randint(1, 30)),
                assigned_to=random.choice(staff) if staff else None,
                created_by=admin,
            )
            inq_count += 1

            if status in ('REPLIED', 'CLOSED'):
                InquiryReply.objects.create(
                    inquiry=inq,
                    content=f'안녕하세요 {cname}님,\n문의 주신 내용 확인하였습니다.\n담당자가 검토 후 회신 드리겠습니다.\n감사합니다.',
                    is_llm_generated=random.choice([True, False]),
                    replied_by=random.choice(staff) if staff else admin,
                    created_by=admin,
                )
                reply_count += 1

        self.stdout.write(f'  문의: {inq_count}건, 답변: {reply_count}건')

    def _create_leave_requests(self, admin):
        """휴가 신청"""
        from apps.attendance.models import LeaveRequest

        users = list(User.objects.filter(role='staff'))
        managers = list(User.objects.filter(role='manager'))
        if not users or not managers:
            return

        leave_data = [
            ('ANNUAL', 1), ('ANNUAL', 1), ('HALF_AM', 0.5), ('HALF_PM', 0.5),
            ('ANNUAL', 2), ('SICK', 1), ('ANNUAL', 3), ('SPECIAL', 5),
        ]

        count = 0
        statuses = ['PENDING', 'APPROVED', 'APPROVED', 'APPROVED', 'REJECTED']
        for i, (leave_type, days) in enumerate(leave_data):
            user = users[i % len(users)]
            start = date.today() + timedelta(days=random.randint(-10, 20))
            end = start + timedelta(days=max(0, int(days) - 1))
            status = random.choice(statuses)

            reasons = {
                'ANNUAL': '개인 사유로 연차 사용합니다.',
                'HALF_AM': '오전 병원 방문',
                'HALF_PM': '오후 개인 용무',
                'SICK': '감기 몸살로 병가 신청합니다.',
                'SPECIAL': '경조사 (결혼식)',
            }

            LeaveRequest.objects.create(
                user=user,
                leave_type=leave_type,
                start_date=start,
                end_date=end,
                days=Decimal(str(days)),
                reason=reasons.get(leave_type, '개인 사유'),
                status=status,
                approved_by=random.choice(managers) if status in ('APPROVED', 'REJECTED') else None,
                approved_at=timezone.now() - timedelta(days=random.randint(0, 5)) if status in ('APPROVED', 'REJECTED') else None,
                created_by=admin,
            )
            count += 1

        self.stdout.write(f'  휴가: {count}건')

    def _create_personnel_actions(self, admin, departments, positions):
        """인사발령"""
        from apps.hr.models import PersonnelAction, EmployeeProfile

        profiles = list(EmployeeProfile.objects.all()[:6])
        if not profiles:
            return

        dept_list = list(departments.values())
        pos_list = list(positions.values())

        actions_data = [
            ('HIRE', '신규 채용'),
            ('PROMOTION', '진급'),
            ('TRANSFER', '부서 이동'),
            ('PROMOTION', '진급'),
        ]

        count = 0
        for i, (action_type, reason) in enumerate(actions_data):
            profile = profiles[i % len(profiles)]
            from_dept = profile.department
            to_dept = random.choice(dept_list) if action_type == 'TRANSFER' else from_dept
            from_pos = profile.position
            to_pos = random.choice([p for p in pos_list if p.level < (from_pos.level if from_pos else 99)]) if action_type == 'PROMOTION' and from_pos else from_pos

            PersonnelAction.objects.create(
                employee=profile,
                action_type=action_type,
                effective_date=date.today() - timedelta(days=random.randint(30, 365)),
                from_department=from_dept,
                to_department=to_dept,
                from_position=from_pos,
                to_position=to_pos,
                reason=reason,
                created_by=admin,
            )
            count += 1

        self.stdout.write(f'  인사발령: {count}건')

    def _create_approval_steps(self, admin):
        """다단계 결재"""
        from apps.approval.models import ApprovalRequest, ApprovalStep

        managers = list(User.objects.filter(role='manager'))
        if len(managers) < 2:
            return

        submitted = ApprovalRequest.objects.filter(status='SUBMITTED')[:3]
        count = 0
        for approval in submitted:
            step_approvers = random.sample(managers, min(2, len(managers)))
            for order, approver in enumerate(step_approvers, 1):
                _, created = ApprovalStep.objects.get_or_create(
                    request=approval, step_order=order,
                    defaults={
                        'approver': approver,
                        'status': 'APPROVED' if order < approval.current_step else 'PENDING',
                        'comment': '승인합니다.' if order < approval.current_step else '',
                        'acted_at': timezone.now() - timedelta(days=random.randint(0, 3)) if order < approval.current_step else None,
                        'created_by': admin,
                    },
                )
                if created:
                    count += 1

        self.stdout.write(f'  결재단계: {count}건')
