# 데이터 마이그레이션 가이드 (다른 솔루션 → ERP Suite)

[English](data_migration_guide.md) | **한국어**

> 다른 ERP·엑셀·MES·POS 등에서 ERP Suite로 데이터를 이관하는 절차.
> 데이터 처리 규칙·매핑·검증 절차를 망라합니다.

## 1. 데이터 처리 규칙 (필수 숙지)

### 1.1 모든 모델 공통

| 규칙 | 설명 |
|---|---|
| **BaseModel 상속** | 모든 모델은 `apps.core.models.BaseModel`을 상속 → `created_at`, `updated_at`, `created_by`, `is_active`, `notes` 자동 부여 |
| **소프트 삭제 only** | `delete()` 호출 금지 — `is_active=False` 사용. 기본 매니저 `objects`는 활성 레코드만 반환, `all_objects`로 전체 조회 가능 |
| **simple_history** | 모든 모델 변경 이력 자동 기록 (`HistoricalRecords()`). DB 용량 고려 — 마이그레이션 시 1회성 import는 history 비활성 권장 |
| **verbose_name 한국어** | 필드 라벨은 한글 |

### 1.2 금액·수량

| 규칙 | 설명 |
|---|---|
| **KRW 원화 정수** | `DecimalField(max_digits=15, decimal_places=0)` — 소수점 없음 |
| **수량 소수 가능** | `DecimalField(max_digits=15, decimal_places=3)` — kg, m³ 등 |
| **환율** | `DecimalField(max_digits=15, decimal_places=4)` — 4자리 소수 |
| **세율(%)** | `DecimalField(max_digits=5, decimal_places=2)` — 2자리 소수 |

### 1.3 동시성 / 무결성

| 규칙 | 설명 |
|---|---|
| **F() 원자 갱신** | 재고/잔액 등 갱신은 `F('field') + value` 사용 — race condition 방지 |
| **transaction.atomic** | 다단 작업은 트랜잭션으로 감싸기 |
| **시그널 자동 처리** | StockMovement/Order.status 변경 시 자동으로 부수 작업 (재고 갱신, AR 생성, 세금계산서 발행 등). 마이그레이션 시 시그널을 어떻게 다룰지 사전 결정 |

### 1.4 결산 마감 (ClosingPeriod)

- 마감된 월(`is_closed=True`)의 전표·주문은 생성/수정 불가
- 과거 데이터 import 시 마감 적용 **이전** 시점에 import 하거나 임시 비활성

### 1.5 시그널이 자동으로 만드는 부수 데이터 (주의)

| 트리거 | 자동생성 |
|---|---|
| `Order.status='CONFIRMED'` | reserved_stock 예약 + AR + TaxInvoice |
| `Order.status='SHIPPED'` | OUT StockMovement + reserved_stock 해제 |
| `OrderItem.save()` | VAT 자동계산 (tax_type 기준) |
| `Payment` 생성 | BankAccount.balance 갱신 + 자동전표(복식부기) |
| `DepreciationRecord` 생성 | FixedAsset.book_value 갱신 + 자동전표 |
| `WithholdingTax` 생성 | 자동전표 (지급수수료/예수금/보통예금) |

→ **마이그레이션 옵션 두 가지**:
1. **시그널 ON 그대로 import**: 부수 데이터까지 자동 생성됨. 원본에 이미 있으면 중복 발생.
2. **시그널 임시 비활성 import**: 원본에 있던 부수 데이터(전표, AR, StockMovement)도 별도로 import. 정합성은 사용자 책임.

권장: 마스터 데이터는 그대로, 거래 데이터는 case별 판단.

## 2. 마이그레이션 순서 (의존성 체인)

```
[Phase 0] 환경 준비
  └─ 마이그레이션 적용, 점검모드 ON, 백업

[Phase 1] 시스템 마스터 (참조 무결성 기반)
  ├─ AccountCode (계정과목)
  ├─ TaxRate (세율)
  ├─ Currency / ExchangeRate (다중통화 사용 시)
  ├─ BankAccount (결제계좌)
  ├─ Department / Position (HR)
  └─ ClosingPeriod (선택, 과거 마감일자)

[Phase 2] 도메인 마스터
  ├─ Category (제품/거래처)
  ├─ Warehouse (창고)
  ├─ Partner (거래처)
  ├─ Customer (고객)
  ├─ Product (제품) — current_stock 0으로 두고 Phase 4에서 채우기
  ├─ User / EmployeeProfile (직원)
  ├─ FixedAsset 카테고리 (AssetCategory)
  └─ PlatformFinancialConfig (플랫폼 설정)

[Phase 3] 운영 설정
  ├─ CommissionRate (거래처 수수료)
  ├─ PriceRule (가격 규칙)
  ├─ BOM (생산)
  ├─ StandardCost (표준원가)
  ├─ PayrollConfig (급여 설정)
  └─ LaborConfig (근로기준)

[Phase 4] 기초 잔액 (오프닝 밸런스)
  ├─ Product.current_stock (재고)
  ├─ StockLot (FIFO/LIFO 사용 시)
  ├─ AccountReceivable (이전 시스템 미수금)
  ├─ AccountPayable (이전 시스템 미지급금)
  ├─ BankAccount.balance (계좌 잔액)
  └─ FixedAsset (자산 + accumulated_depreciation)

[Phase 5] 거래 데이터 (선택, 과거 분 보존 시)
  ├─ Quotation
  ├─ Order + OrderItem
  ├─ PurchaseOrder + 입고
  ├─ TaxInvoice
  ├─ CashReceipt
  ├─ Payment
  ├─ Voucher + VoucherLine
  └─ ProductionRecord

[Phase 6] 검증 + 시산표 대조
  └─ checklist (§5)
```

## 3. 도구 선택

### 3.1 django-import-export (권장 — Excel 기반)

```python
# apps/sales/resources.py 패턴
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from apps.sales.models import Partner

class PartnerResource(resources.ModelResource):
    default_bank_account = fields.Field(
        column_name='기본 계좌',
        attribute='default_bank_account',
        widget=ForeignKeyWidget('accounting.BankAccount', 'name'),
    )
    class Meta:
        model = Partner
        skip_unchanged = True
        report_skipped = True
        import_id_fields = ('code',)
        fields = (
            'code', 'name', 'partner_type', 'entity_type',
            'business_number', 'representative',
            'phone', 'email', 'address',
            'default_bank_account',
            'default_sales_channel', 'default_payment_method',
        )
```

→ `/admin/<app>/<model>/import/` 또는 코드:
```bash
python manage.py loaddata partners.json
# 또는
python manage.py shell -c "from import_export import ...; Partner.objects.import_from_csv(...)"
```

### 3.2 Management Command (대량 — 만건 이상)

```python
# apps/<app>/management/commands/migrate_<entity>.py
from django.core.management.base import BaseCommand
from django.db import transaction
import csv

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, csv_path, dry_run=False, **opts):
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            with transaction.atomic():
                for row in reader:
                    # ... 비즈니스 로직
                    pass
                if dry_run:
                    transaction.set_rollback(True)
```

### 3.3 Raw SQL (수십만 건 이상, 시그널 우회 필요)

```python
from django.db import connection

with connection.cursor() as cursor:
    cursor.executemany(
        "INSERT INTO inventory_product (code, name, ...) VALUES (%s, %s, ...)",
        rows,
    )
```

⚠ Raw SQL은 시그널 우회 → **재고/AR 등 부수 데이터를 직접 INSERT 해야 함**. simple_history 이력도 누락 가능.

### 3.4 Django bulk_create (중간 — 시그널 X)

```python
Product.objects.bulk_create([
    Product(code=r['code'], name=r['name'], ...)
    for r in rows
], batch_size=1000)
```

bulk_create는 `save()` 시그널을 발생시키지 **않음**. 자동 부수 데이터 생성 안 됨.

## 4. 핵심 모델 매핑 가이드

### 4.1 거래처 (Partner)

| 외부 컬럼 예시 | ERP Suite 필드 | 비고 |
|---|---|---|
| 거래처코드 | `code` | unique. 비우면 자동 생성 |
| 거래처명 | `name` | |
| 사업자등록번호 | `business_number` | `123-45-67890` 포맷 |
| 대표자 | `representative` | |
| 거래유형 | `partner_type` | CUSTOMER / SUPPLIER / BOTH |
| 사업자/개인 | `entity_type` | BUSINESS / INDIVIDUAL / FOREIGN |
| 전화번호 | `phone` | **EncryptedCharField** — 자동 암호화 |
| 이메일 | `email` | EncryptedCharField |
| 주소 | `address` | EncryptedTextField |
| 거래처 등급 | `tier` | (선택) |
| 신용한도 | `credit_limit` | KRW 정수 |
| 기본 채널 | `default_sales_channel` | DIRECT/NAVER/COUPANG/... (Order.SalesChannel 값) |

### 4.2 제품 (Product)

| 외부 컬럼 | ERP Suite 필드 | 비고 |
|---|---|---|
| 제품코드 | `code` | unique. 비우면 product_type 기반 자동 (FIN-0001 등) |
| 제품명 | `name` | |
| 유형 | `product_type` | RAW / SEMI / FINISHED / SERVICE / INTANGIBLE |
| 판매단가 | `unit_price` | KRW 정수 |
| 원가 | `cost_price` | KRW 정수 |
| NRV | `net_realizable_value` | 순실현가능가액 (저가법 기말평가용, 선택) |
| 재고평가법 | `valuation_method` | AVG / FIFO / LIFO |
| 안전재고 | `safety_stock` | 정수 |
| 현재고 | `current_stock` | 마이그레이션 시 0으로 두고 Phase 4 StockMovement(IN)으로 채우기 권장 |

### 4.3 주문 (Order)

| 외부 컬럼 | ERP Suite 필드 | 비고 |
|---|---|---|
| 주문번호 | `order_number` | unique |
| 거래처 | `partner` | FK |
| 주문일 | `order_date` | DateField |
| 회계인식일 | `accounting_date` | (선택) 정산일/카드 승인일과 다를 때 |
| 상태 | `status` | DRAFT/CONFIRMED/PARTIAL_SHIPPED/SHIPPED/DELIVERED/CLOSED/CANCELLED |
| 채널 | `sales_channel` | DIRECT/NAVER/COUPANG/OFFLINE/PHONE/OTHER |
| 결제수단 | `payment_method` | CARD/BANK_TRANSFER/CASH/VIRTUAL_ACCOUNT/NAVER_PAY/KAKAO_PAY/PLATFORM/OTHER |
| 과세구분 | `tax_type` | TAXABLE/ZERO_RATE/EXEMPT |
| 수익인식 | `revenue_recognition_method` | DELIVERY/PROGRESS/COMPLETION |

### 4.4 전표 (Voucher + VoucherLine)

복식부기 전표는 차변·대변 합계가 일치해야 함 (`is_balanced` 검증).

```python
with transaction.atomic():
    v = Voucher.objects.create(
        voucher_number='V-2026-0001',
        voucher_type='RECEIPT',  # 입금
        voucher_date=date(2026, 1, 1),
        description='기초이월',
        approval_status='APPROVED',
    )
    VoucherLine.objects.create(voucher=v, account=cash_acct, debit=1_000_000, credit=0)
    VoucherLine.objects.create(voucher=v, account=capital_acct, debit=0, credit=1_000_000)
```

### 4.5 미수금/미지급금 (AR/AP)

원래 시스템의 미수/미지급 잔액을 그대로 import:
- `AccountReceivable.amount` = 채권 총액
- `AccountReceivable.paid_amount` = 부분입금된 금액 (없으면 0)
- 미수 잔액 = `amount - paid_amount`

기초이월 시점의 잔액으로 **새 AR 1건씩** 생성하는 방법이 깔끔.

### 4.6 재고 기초이월 (StockMovement IN)

```python
StockMovement.objects.create(
    movement_number='OPEN-2026-001',
    movement_type='IN',
    product=p, warehouse=w,
    quantity=100,
    unit_price=p.cost_price,
    movement_date=date(2026, 1, 1),
    reference='기초이월',
)
```

→ 시그널이 자동으로 `Product.current_stock += 100` + `StockLot` 생성.

## 5. 검증 체크리스트

마이그레이션 후 반드시 확인:

```
[ ] 1. 모델별 레코드 수 = 원본 시스템 레코드 수 (sample 비교)
[ ] 2. Product.current_stock 합계 = 원본 재고 합계
[ ] 3. AR 잔액 합계 = 원본 미수금 합계
[ ] 4. AP 잔액 합계 = 원본 미지급금 합계
[ ] 5. BankAccount.balance 합계 = 원본 계좌 잔액 합계
[ ] 6. 시산표 (Trial Balance) 차변=대변 → /accounting/trial-balance/
[ ] 7. ClosingPeriod 미마감 상태 확인 (마이그 후 마감 처리)
[ ] 8. simple_history 활성화 (필요 시 마이그 중 비활성, 후 활성)
[ ] 9. 시그널 통한 부수 데이터 미중복 확인 (StockMovement, AR, TaxInvoice)
[ ] 10. 인덱스 / 권한 / 캐시 재구성 (manage.py rebuild_index)
[ ] 11. Celery beat 스케줄 작동 확인 (정산 자동배치 등)
[ ] 12. PWA 캐시 / static 재수집 (manage.py collectstatic)
```

### 5.1 시산표 빠른 검증

```bash
python manage.py shell --settings=config.settings.<target> << 'EOF'
from django.db.models import Sum
from apps.accounting.models import VoucherLine
agg = VoucherLine.objects.filter(
    is_active=True, voucher__is_active=True,
    voucher__approval_status='APPROVED',
).aggregate(d=Sum('debit'), c=Sum('credit'))
print(f"차변 {agg['d']:,} / 대변 {agg['c']:,}")
assert agg['d'] == agg['c'], '차대변 불일치 — 마이그 데이터 정합성 점검 필요'
EOF
```

## 6. 흔한 실수와 대응

| 함정 | 대응 |
|---|---|
| 거래처 phone에 평문 길이 초과 | EncryptedCharField는 암호화 후 길이가 늘어남 → `max_length=500` |
| Product.current_stock을 직접 INSERT | StockMovement(IN)로 채워야 시그널 정합 |
| Order.status를 DRAFT로 import 후 CONFIRMED로 일괄 변경 | 시그널이 모든 주문에 대해 reserved_stock + AR + TaxInvoice 재생성 → 부하 폭발. 한 건씩 처리 |
| simple_history 누락 | bulk_create는 history 안 만듦. 사후 history 마이그레이션 필요 |
| 마감기간 검증 위반 | 과거 데이터 import 시 ClosingPeriod 임시 해제 |
| 외화 환율 누락 | Order.exchange_rate 기본 1. 외화 거래는 미리 ExchangeRate 적재 |
| 사업자번호 포맷 | 외부 시스템: `1234567890`, ERP Suite: `123-45-67890` 권장. 검증 로직 추가 가능 |
| 재고 음수 | CheckConstraint(stock_non_negative) — 음수 재고 import 시 차단됨 |

## 7. 도메인별 마이그레이션 팁

### 7.1 ERP → ERP Suite (SAP/Oracle/SAP B1 등)

- 계정과목 매핑이 가장 어려움. 한국 K-GAAP 코드 체계로 변환 (4xx 매출, 501~509 매출원가, 52x 판관비 등)
- 시산표 차대변 일치 후 import

### 7.2 엑셀 / 수기장부 → ERP Suite

- 거래처/제품은 import_export로 즉시 가능
- 미수/미지급 잔액은 기초이월 전표 1건으로 통합 처리
- 과거 거래 내역은 선택적 (필수 아님)

### 7.3 POS / 마켓플레이스 → ERP Suite

- 마켓플레이스(네이버/쿠팡)는 **Marketplace Wizard** 사용 (`/marketplace/wizard/fetch/`)
- POS는 일별 매출 합계로 Order 1건씩 + OrderItem 단순화 가능

### 7.4 재고관리시스템 (WMS) → ERP Suite

- WarehouseStock 직접 INSERT 권장 (창고별 재고)
- StockLot은 FIFO/LIFO 사용 시만

## 8. 마이그레이션 실행 명령 예시

```bash
# 1) 점검모드 ON
python manage.py maintenance on --settings=config.settings.beta

# 2) 마스터 import (대상별)
python manage.py loaddata fixtures/master_accounts.json --settings=config.settings.beta
python manage.py loaddata fixtures/master_partners.json --settings=config.settings.beta
python manage.py migrate_products data/products.csv --settings=config.settings.beta

# 3) 기초잔액
python manage.py migrate_opening_balance data/opening.json --settings=config.settings.beta

# 4) 검증
python manage.py validate_migration --settings=config.settings.beta

# 5) 시산표 확인
# /accounting/trial-balance/ 접속

# 6) 점검모드 OFF
python manage.py maintenance off --settings=config.settings.beta
```

## 9. 롤백 전략

마이그레이션은 **반드시 beta DB 환경에서 검증** 후 prod 적용:

```bash
# 백업
sqlite3 local/db_prod.sqlite3 .dump > backup_$(date +%Y%m%d).sql
# 또는 PostgreSQL
pg_dump erp_prod > backup_$(date +%Y%m%d).sql

# 검증 환경(beta)에서 마이그 → 검증 OK → prod 적용
# 문제 발생 시 백업에서 복구
```

## 10. 참고 파일

- `apps/core/models.py` — BaseModel 정의
- `apps/sales/resources.py` — django-import-export Resource 예시
- `tests/verification/` — 정합성 검증 테스트 (마이그 후 실행 권장)
- `apps/<app>/management/commands/seed_*.py` — 시드 데이터 패턴 참고

## 11. 지원 도구 (이미 구현된 마이그)

- `seed_platform_configs` — 플랫폼 재무설정 시드
- `seed_account_codes` (선택, 있으면 K-GAAP 표준 계정과목 자동)
- Marketplace Wizard — 네이버/쿠팡 자동 가져오기
- import_export Resource — 다수 모델 (apps 별 resources.py 확인)
