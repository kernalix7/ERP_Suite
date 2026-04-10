# ERP Suite — 비즈니스 프로세스 갭 분석

**작성일**: 2026-04-07  
**분석 범위**: Order → Shipment → Payment → Closure 전체 파이프라인, 발주→입고, 생산→재고, 회계 자동화

---

## 1. 서비스(Service) vs 제품(Product) 관계 — 구조적 불일치 발견 ⚠️

### 현재 상태
- **Product 모델**: `product_type` choice에 `SERVICE='서비스'`, `INTANGIBLE='무형상품'` 포함 ✅
- **ServiceRequest 모델**: 독립적 앱 (`apps/service/`) 에서 Product 참조 ✅
- **Product.is_stockable 속성**: SERVICE/INTANGIBLE 제외 ✅

### 갭 발견

| 갭 | 영향 | 심각도 | 원인 |
|-----|------|--------|------|
| **Service 취소 프로세스 미구현** | AS 요청을 취소하면 비용(RepairRecord.cost) 계정처리 로직 없음 | 🟡 HIGH | ServiceRequest 신호 없음 |
| **Service→ AR/선입금 자동 연결 미구현** | 유상수리(PAID) 요청 생성 시 AR/결제 자동 매칭 로직 없음 | 🟡 HIGH | Service 신호 처리 부재 |
| **Product.reserved_stock과 Service 미조율** | 교환(EXCHANGE) 서비스 수행 시 기존 제품 반품입고 처리 로직 없음 | 🔴 CRITICAL | EXCHANGE 상태는 모델만 존재, 자동화 없음 |
| **Warranty 검증 미동작** | ServiceRequest.is_warranty 필드는 수동 입력만, 자동 계산 로직 없음 | 🟡 MEDIUM | Signal 미구현 |

---

## 2. 주문→출고→배송→입금→종결 파이프라인 — 부분 자동화

### 현재 상태 (apps/sales/signals.py 분석)

| 전환 | 자동화 | 세부 사항 |
|------|--------|---------|
| **DRAFT → CONFIRMED** | ✅ YES | `_auto_reserve_stock()` + `_auto_create_ar()` + `_auto_create_tax_invoice()` |
| **CONFIRMED → SHIPPED** | ✅ YES | `_auto_full_ship()` (StockMovement OUT 생성) |
| **SHIPPED → DELIVERED** | ✅ YES | `_sync_shipments_delivered()` + `_auto_register_on_delivered()` (고객구매내역 생성) |
| **DELIVERED → CLOSED** | ✅ PARTIAL | `_try_close_order()` — **입금 상태에만 의존** |
| **기타 → CANCELLED** | ✅ YES | `_auto_cancel_order()` 역방향 처리 |

### 갭 발견

| 갭 | 영향 | 심각도 | 원인 |
|-----|------|--------|------|
| **PARTIAL_SHIPPED 상태 미흡** | 주문 일부 출고 후 남은 수량 처리 로직이 불명확 | 🟡 HIGH | `_auto_full_ship()` 호출 2회 (중복?) |
| **주문 수정(CONFIRMED 후) 불가** | 확정된 주문의 수량/가격 변경 시나리오 처리 로직 없음 | 🔴 CRITICAL | Status transition 제약만 있고 부분수정 불가 |
| **RETURN/EXCHANGE 주문유형 미구현** | Order.order_type에 RETURN/EXCHANGE 필드는 있지만 자동화 로직 없음 | 🔴 CRITICAL | 상태머신 없음 |
| **반품 재입고 프로세스 미구현** | 출고된 제품이 반품 들어올 때 StockMovement RETURN 생성 로직 없음 | 🔴 CRITICAL | Service/Inventory 연결 끊김 |
| **주문 입금 자동 매칭 미구현** | Payment 생성 시 Order.is_paid 자동 갱신 로직 불명확 (매뉴얼?) | 🟡 HIGH | OrderItem.cost_price ← 어디서 입력되는가? |
| **배송비/플랫폼 수수료 → AR/전표 연결 미구현** | Order.shipping_cost, platform_commission 필드는 있지만 회계 자동화 없음 | 🟡 MEDIUM | 수동 조정만 가능 |
| **다중통화(exchange_rate) 환산 로직 미구현** | Order.currency/exchange_rate 필드만 있고, AR 금액 환산 로직 없음 | 🟡 MEDIUM | 환율 적용 미명확 |

### 주문 CLOSED 조건 분석

```python
# sales/signals.py line 666-675
if db_status == 'DELIVERED' and is_paid:
    fresh.status = 'CLOSED'
```

**문제점:**
1. `is_paid` 플래그는 Payment 생성 시 설정되는데, 정확한 트리거 로직이 불명확
2. 수동 결제 입력 시 `is_paid`를 언제 TRUE로 변경하는가? → **뷰 레벨에서 수동 처리** (CLAUDE.md 명시)
3. 부분 입금 후 잔액이 있어도 자동 CLOSED 처리 위험

---

## 3. 발주→입고→재고 파이프라인 — 대부분 자동화 ✅

### 현재 상태 (apps/purchase/signals.py)

| 전환 | 자동화 | 세부 사항 |
|------|--------|---------|
| **GoodsReceiptItem 생성** | ✅ YES | `handle_goods_receipt()` → StockMovement IN + PO status 갱신 + AP + 세금계산서 |
| **PO CONFIRMED → PARTIAL_RECEIVED/RECEIVED** | ✅ YES | PurchaseOrderItem.received_quantity 기반 자동 상태 전환 |
| **전량 입고 시** | ✅ YES | AP + 매입 세금계산서 자동 생성 |
| **PO CANCELLED** | ✅ YES | 역방향 (AP/세금계산서 soft delete, 단 입고 존재 시 차단) |
| **GoodsReceiptItem soft delete** | ✅ YES | StockMovement soft delete + PO.received_quantity 차감 |

### 갭 발견

| 갭 | 영향 | 심각도 | 원인 |
|-----|------|--------|------|
| **입고 지연 시 MRP 미트리거** | PO expected_date 경과 시 자동 알림/재발주 로직 없음 | 🟡 MEDIUM | 일정 관리 시스템 부재 |
| **분할 입고(PARTIAL_RECEIVED) 후 남은 수량 처리** | PO 일부 입고 후 나머지는 수동 추적만 가능 | 🟡 MEDIUM | 자동 재발주 로직 없음 |
| **GoodsReceipt.warehouse 선택 미흡** | 입고 창고가 고정이 아니면 WarehouseStock 갱신 위험 | 🟡 MEDIUM | warehouse FK nullable |
| **AP 중복 생성 가능** | 같은 PO에 여러 GoodsReceipt 존재 시 조건문이 구체적이나, 실제 중복 방지 검증 부족 | 🟡 MEDIUM | `notes` 필드 텍스트 기반 중복 검사만 함 |
| **FixedAsset 자동 생성 미흡** | GoodsReceiptItem.asset_category 있을 때만 생성, 실제 구분이 정확한가? | 🟡 MEDIUM | is_fixed_asset 필드 검증 필요 |

---

## 4. 생산→재고 파이프라인 — 자동화 부분적 ⚠️

### 현재 상태 (apps/production/ 신호)

**ProductionRecord 신호 검증 필요:**
- CLAUDE.md: "ProductionRecord → signal auto-creates PROD_IN (finished) + PROD_OUT (materials)"
- **실제 구현 확인 필요**: `apps/production/signals.py` 존재 여부?

```bash
ls -la /home/kernalix7/Desktop/00_Personal_Project/00G_ERP_Suite/apps/production/signals.py
# → 파일 존재 여부 확인 필요
```

### 갭 발견

| 갭 | 영향 | 심각도 | 원인 |
|-----|------|--------|------|
| **BOM 유효성 검증 미흡** | ProductionPlan 생성 시 BOM 자재 가용성 자동 체크 로직이 불명확 | 🟡 HIGH | BOM.check_material_availability() 메서드 존재하나 신호 연결 미확인 |
| **ProductionPlan CANCELLED 시 역방향** | 생산 계획 취소 시 예약재고 복원/자동 발주 취소 로직 없음 | 🔴 CRITICAL | 신호 미구현 확인 |
| **WorkOrder 상태 머신 미흡** | WorkOrder → ProductionRecord의 상태 전환이 명확하지 않음 | 🟡 MEDIUM | 모델 검증 필요 |
| **불량품(scrap) 처리 미구현** | ProductionRecord.scrap_quantity는 필드만 있고, 자동 조정 로직 없음 | 🟡 MEDIUM | 불량품이 재고에서 제외되는가? |
| **다단계 생산 BON(Sub-assembly) 미지원** | BOM item이 반제품(SEMI)인 경우 다단계 전개 로직 불명확 | 🟡 MEDIUM | MRP 알고리즘 미확인 |

---

## 5. 회계 파이프라인 — 자동화 대부분 구현 ✅

### 현재 상태 (apps/accounting/signals.py)

| 트리거 | 자동화 | 세부 사항 |
|--------|--------|---------|
| **Order CONFIRMED** | ✅ YES | `_auto_create_ar()` (신호 in sales/signals.py) |
| **Order SHIPPED** | ✅ YES | StockMovement OUT (신호 in sales/signals.py) |
| **GoodsReceiptItem 생성** | ✅ YES | StockMovement IN + AP (신호 in purchase/signals.py) |
| **Payment 생성** | ✅ YES | BankAccount 잔액 갱신 + 자동전표 생성 |
| **AccountTransfer** | ✅ YES | 양쪽 계좌 잔액 갱신 + 대체전표 |
| **ClosingPeriod 마감** | ✅ YES | 마감된 월 전표 수정 차단 |

### 갭 발견

| 갭 | 영향 | 심각도 | 원인 |
|-----|------|--------|------|
| **AR/AP 자동 연체 전환** | is_overdue() 메서드는 있지만, 정기 배치 작업 미구현 | 🟡 HIGH | 일일 배치 스케줄 필요 (Celery) |
| **AR 입금액 자동 매칭 미흡** | Payment 생성 시 어떤 AR을 결제했는가 추적 로직 불명확 | 🟡 HIGH | Payment←→AR 명시적 FK 없음 (다대다?) |
| **부분 입금 처리 미구현** | AR 100 중 50만 입금 시, 잔액 추적 로직 불명확 | 🔴 CRITICAL | AR.amount가 고정인가? 부분 결제 후 AR 재분할? |
| **환율 변동 손익(환차손익) 미구현** | 외화 Order/AP의 환율 변동 시 자동 환차 계정 생성 로직 없음 | 🟡 MEDIUM | 결산 시 환차 조정 수동 처리? |
| **Voucher 자동생성 계정과목 매핑 하드코딩** | payment_update_balance_and_voucher()에서 계정코드 '401', '501' 등 하드코딩 | 🟡 MEDIUM | 거래처별/선택 가능한 계정과목 매핑 필요 |
| **ClosingPeriod 마감 후 계약금 입금 시나리오** | 마감 월 전표는 다음 월로 자동 이동하나, AR 기한 재계산 미구현 | 🟡 MEDIUM | 기한 이월 로직 필요 |

---

## 6. 누락된 비즈니스 프로세스 — 설계 미흡

### 6.1 반품(Return) 프로세스 — **구조 부재** 🔴 CRITICAL

**현재:**
- Order.order_type = 'RETURN' (필드만 있음)
- StockMovement.movement_type = 'RETURN' (타입만 있음)

**미구현:**
1. ✗ 주문 반품 신청 후 자동 StockMovement RETURN 생성
2. ✗ 반품 RETURN 입고 시 원주문 AR 차감/환불 결정 로직
3. ✗ 반품 제품 검수(상태 양호/불량) 후 차등 처리
4. ✗ 반품 세금계산서 자동 취소 (원 세금계산서 동시 취소)

**필요 모델:**
```
ReturnRequest (Order과 별도 모델?)
├── source_order FK
├── status (REQUESTED → RECEIVED → INSPECTED → APPROVED/REJECTED)
└── return_items
    ├── order_item FK
    ├── quantity
    └── condition (GOOD/DAMAGED/MISSING)
```

### 6.2 교환(Exchange) 프로세스 — **상태만 정의, 자동화 없음** 🔴 CRITICAL

**현재:**
- Order.order_type = 'EXCHANGE'
- ServiceRequest.request_type = 'EXCHANGE'

**미구현:**
1. ✗ 교환 주문 생성 시 기존 제품 반품 예약 + 신규 제품 출고 예약
2. ✗ 반품/신규 물량 동시 처리
3. ✗ 차액 정산(원 주문가 > 신규 제품가인 경우 환불/보정)

### 6.3 견적 만료(Quotation Expiry) — **상태만 정의, 만료 자동화 없음** 🟡 HIGH

**현재:**
- Quotation.valid_until 필드
- Quotation.status = 'EXPIRED' (상태만)

**미구현:**
1. ✗ 정기 배치: valid_until < today() 인 DRAFT/SENT 견적 자동 EXPIRED 전환
2. ✗ 만료 통지 알림 (이메일/내부 메시지)

### 6.4 재고 안전재고(Safety Stock) 경고 및 MRP — **필드만 존재, 자동화 없음** 🟡 HIGH

**현재:**
- Product.safety_stock (필드만)
- Product.is_below_safety_stock / .shortage (프로퍼티만)

**미구현:**
1. ✗ 정기 배치: current_stock < safety_stock 시 자동 알림
2. ✗ MRP 시뮬레이션: 안전재고 고려한 자동 발주 제안
3. ✗ lead_time_days 기반 선제적 발주

### 6.5 거래처 승인(Partner Approval) — **모델 미구현** 🟡 MEDIUM

**현재:**
- Partner 모델에 approval 관련 필드 없음

**필요:**
1. Partner.is_approved (기본 FALSE)
2. Partner.approved_by FK
3. Partner.approval_date
4. Partner 미승인 상태일 때 주문 가능 여부 제어

### 6.6 가격 규칙(PriceRule) 자동 적용 — **모델만 존재, 뷰 레벨 미확인** 🟡 MEDIUM

**현재:**
- PriceRule 모델 완성
- OrderItem 수동 생성 시 단가 선택

**미구현:**
1. ✗ OrderItem 생성 시 PriceRule 자동 조회 및 단가 적용
2. ✗ 유효 기간(valid_from/valid_to) 검증

### 6.7 마켓플레이스 통합 — **부분 구현, 동기화 미흡** 🟡 HIGH

**현재:**
- MarketplaceOrder ← Naver/Coupang API 동기
- Quotation → Order → MarketplaceOrder 연결 (in views.py)

**미구현:**
1. ✗ 주문 수정(수량/가격 변경) 시 마켓플레이스 API 동기화
2. ✗ 출고/배송 상태 역동기 (ERP → 마켓플레이스)
3. ✗ 반품 처리 시 마켓플레이스 반영

---

## 7. 모델 간 FK 연결 및 데이터 무결성 갭

| 갭 | 영향 | 심각도 | 원인 |
|-----|------|--------|------|
| **Order←Payment 직접 FK 없음** | 주문과 결제의 관계를 Payment에서 특정 필드로만 추적 (partner 기반?) | 🔴 CRITICAL | 다중통화/거래처 간 결제 혼동 가능 |
| **AR←Order 직접 FK 없음** | AccountReceivable과 Order의 관계 미명시 (notes 필드 텍스트 기반) | 🔴 CRITICAL | AR 추적 불명확, 부분 결제 불가능 |
| **AP←PO 직접 FK 없음** | AccountPayable과 PurchaseOrder의 관계 미명시 | 🔴 CRITICAL | 결제 추적 불명확 |
| **Shipment←Order 관계 역참조만 존재** | Shipment.order FK 있음 (✓), 부분 출고 복수 shipment 처리 가능 (✓) | ✅ OK | 현재 설계 적절 |
| **ShipmentItem←OrderItem 명시** | ShipmentItem.order_item FK (✓) | ✅ OK | 부분 출고 추적 가능 |
| **ServiceRequest←Order 관계 미흡** | 원주문(Order)과 반품 요청(ServiceRequest) 연결 필드 없음 | 🟡 HIGH | Service.request_type='RETURN' 분석 필요 |

---

## 8. 시그널 연쇄 및 원자성(Atomicity) 검증

### 확인된 원자성 ✅
- StockMovement → Product.current_stock: F() 식 사용, transaction.atomic()
- Payment → BankAccount.balance: F() 식 사용, transaction.atomic()
- Voucher 자동생성: transaction.atomic()

### 의심 영역 ⚠️

| 시나리오 | 현재 상태 | 위험 |
|---------|---------|------|
| **Order CONFIRMED 시 AR + 세금계산서 동시 생성** | sales/signals.py: atomic() 래핑됨 (✓) | ✅ OK |
| **PO 전량 입고 시 AP + 세금계산서 + 자산 등록** | purchase/signals.py: atomic() 래핑됨 (✓), 단 자산 계정과목 미존재 시 로깅만 | ⚠️ 실패 로그만 남김 |
| **주문 취소 시 연쇄 역방향** | sales/signals.py: `_auto_cancel_order()` atomic() 래핑 (✓) | ✅ OK |

---

## 9. 정책/설정 의존성 — 명시 부족

| 설정 | 현재 위치 | 필요성 |
|------|---------|--------|
| **PO_APPROVAL_REQUIRED** | PurchaseOrder.save() 조건부 체크 | 🟡 명시 부족 — CLAUDE.md에 기재 필요 |
| **ORDER_AUTO_CLOSE_ON_DELIVERY** | sales/signals.py 하드코딩 (`_try_close_order`) | 🟡 설정 옵션화 고려 |
| **AR_AUTO_MATCH_PAYMENT** | 구현 불명확 | 🔴 필수 명시 |
| **MRP_AUTO_CREATE_PO** | 미구현 | 🟡 권장 설정 |

---

## 10. 종합 갭 요약

### 🔴 CRITICAL (즉시 해결 필요)
1. ~~**주문 수정 불가**~~ ✅ **해결 (Phase 12)** — OrderModifyView 구현, reserved_stock/AR/세금계산서 재계산
2. ~~**Return/Exchange 자동화 완전 부재**~~ ✅ **해결 (Phase 12)** — 반품/교환 주문 생성 뷰, 시그널 자동화
3. ~~**AR/AP←Order/PO 직접 연결 없음**~~ ✅ **기존 구현 확인** — AR.order FK, AP.purchase_order FK 이미 존재
4. ~~**Payment←Order 직접 연결 없음**~~ ✅ **기존 구현 확인** — Payment.ar/ap FK로 추적
5. ~~**Service 취소 시 회계 자동화 없음**~~ ✅ **해결 (Phase 12)** — 서비스 취소 시그널, AR soft delete

### 🟡 HIGH (근중기 개선)
1. **PARTIAL_SHIPPED 상태 처리 미흡** — 부분 출고 후 남은 수량 추적 불명확
2. **배송비/플랫폼 수수료 → 전표 연결 없음** — 수동 조정만 가능
3. ~~**견적 만료 자동화 없음**~~ ✅ **해결 (Phase 12)** — Celery 배치 매일 새벽 1시 자동 EXPIRED 전환
4. ~~**안전재고 경고/MRP 없음**~~ ✅ **해결 (Phase 12)** — Celery 배치 매일 오전 7시 + Notification
5. ~~**입고 지연 시 알림 없음**~~ ✅ **해결 (Phase 12)** — Celery 배치 매일 오전 7:30
6. ~~**AR 자동 연체 전환**~~ ✅ **해결 (Phase 12)** — Celery 배치 AR OVERDUE 자동 전환
7. ~~**마켓플레이스 상태 역동기**~~ ✅ **해결 (Phase 12)** — Shipment SHIPPED → 네이버/쿠팡 API push

### 🟠 MEDIUM (선택적 개선)
1. **Warranty 자동 검증** — is_warranty 수동 입력
2. **FixedAsset 자동 생성 검증** — 구분 기준 불명확
3. ~~**다단계 BOM (Sub-assembly)**~~ ✅ **해결 (Phase 12)** — BOM.explode_multilevel() 재귀 전개
4. ~~**환율 변동 손익**~~ ✅ **해결 (Phase 12)** — ExchangeGainLossView 구현
5. ~~**Partner 승인 프로세스**~~ ✅ **해결 (Phase 12)** — PO 생성 시 approval_status 체크
6. **가격 규칙 자동 적용** — 뷰 레벨 미확인

---

## 11. 권장 우선순위 수정 순서

### Phase 1 (CRITICAL — 1주)
1. **AR/AP←Order/PO FK 추가** (마이그레이션)
2. **Return 프로세스 구현** (모델 + 신호 + 뷰)
3. **주문 수정 기능** (DRAFT/CONFIRMED 제한 해제, AR/세금계산서 재계산)

### Phase 2 (HIGH — 2-3주)
1. **배송비/플랫폼 수수료 → 전표 연결**
2. **견적 만료 배치**
3. **AR 자동 연체 배치**
4. **PARTIAL_SHIPPED 명확화**

### Phase 3 (선택 — 월 단위)
1. **Exchange 프로세스**
2. **MRP + 안전재고 자동화**
3. **마켓플레이스 역동기**

---

## 12. 검증 및 다음 단계

### 추가 확인 필요
```bash
# 1. Production 신호 존재 여부
ls -la apps/production/signals.py

# 2. AR/AP 모델 상세 검증
grep -n "class AccountReceivable\|class AccountPayable" apps/accounting/models.py

# 3. Payment←Order 연결 로직
grep -n "is_paid\|Order.objects.filter" apps/sales/signals.py

# 4. PriceRule 적용 뷰
grep -n "PriceRule" apps/sales/views.py

# 5. 마켓플레이스 동기화
grep -n "def sync" apps/marketplace/*.py
```

### 테스트 플랜
- [ ] OrderItem 부분 출고 후 재출고 시나리오
- [ ] Order 취소 → AR 역방향 완전성 검증
- [ ] PO 부분 입고 → AP 생성 중복 검증
- [ ] Return/Exchange 엣지 케이스
- [ ] 다중통화 환율 적용 검증
