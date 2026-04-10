# ERP Suite 구매·생산·재고 프로세스 갭 분석 보고서

**점검일**: 2026-04-07  
**점검 대상**: Very thorough 수준의 7대 영역  
**검증 범위**: apps/purchase, apps/production, apps/inventory, apps/sales 시그널 + 모델 + 뷰 전수 검토

---

## 요약

ERP Suite의 구매·생산·재고 프로세스는 **전반적으로 견고한 설계**를 갖추고 있으나, **7개 영역에서 중요도 갭이 발견**되었습니다:
- **[CRITICAL]** 1건: ~~BOM 다단계(BOM of BOM) 미지원~~ ✅ **해결 (Phase 12)** — BOM.explode_multilevel() 재귀 전개
- **[HIGH]** 4건: 입고 검수 → 불량 조정/반품 미연결, ~~재고 마이너스 방지 로직 부재~~ ✅ **(Phase 11)**, ~~조건부합격 미처리~~ ✅ **(Phase 13)**, ~~MRP 재주문점 미지원~~ ✅ **(Phase 13)**
- **[MEDIUM]** 3건: 창고간이동 중 재고 카운팅 오류 우려, ~~ShipmentItem 출고 예약재고 해제 시점 문제~~ ✅ **(Phase 11)**, 이동평균단가 역산 계산식 정확도

---

## 발견사항 상세

### [CRITICAL] 1. BOM 다단계(BOM of BOM) 미지원

**현상**:  
- `BOMItem.material`은 RAW/SEMI 제품만 지원 (완제품 불가)
- 반제품(SEMI) → 원자재(RAW) 단계만 가능, SEMI → SEMI 다단계 구성 불가
- MRP 전개 시 BOM 재귀 처리 미구현 → 최상위 완제품만 BOM 전개

**영향**:  
- 반제품을 부품으로 사용하는 조립형 제조 프로세스 미지원
- 예: 완제품(FIN-001) → 부품조립(SEMI-001, SEMI-002) → 원자재 구성 불가능
- MRP에서 반제품 소요량을 계산하면 원자재까지 자동 전개 불가

**관련 코드**:
- `apps/production/models.py:63-71` — BOMItem.material의 `limit_choices_to={'product_type__in': ['RAW', 'SEMI']}`에서 FINISHED 제외
- `apps/production/views.py:519-527` — MRP _calculate_mrp()에서 BOM.items 반복만 수행, 재귀 없음
- `apps/production/models.py:40-60` — check_material_availability()도 1단계만 체크

**권장 조치**:
```
1. BOMItem.material을 FIN, RAW, SEMI 모두 허용으로 변경
2. MRP._calculate_mrp()에 재귀 BOM 전개 함수 추가 (_expand_bom_recursive())
3. BOM 순환참조(circular dependency) 방지 검증 추가
4. test_production_workflow.py에 다단계 BOM 테스트 케이스 추가
```

**심각도**: **CRITICAL** — 복합 제조 구조 구현 불가능

---

### [HIGH] 2. 입고 검수 → 불량 조정/반품 프로세스 미연결

**현상**:  
- `GoodsReceiptItem.is_inspected` 필드는 있으나, 검수 결과(합격/불합격)와 무관하게 IN StockMovement 자동 생성
- QualityInspection(INCOMING) 결과가 FAIL/CONDITIONAL이어도 입고 재고는 그대로 반영
- 불량 수량 처리 경로 없음:
  - FAIL: 반품 발주서 자동 생성 안 함
  - CONDITIONAL: 별도 추적 안 함

**관련 코드**:
- `apps/purchase/signals.py:15-85` — handle_goods_receipt()에서 is_inspected 체크 없음, 항상 IN StockMovement 생성
- `apps/production/models.py:336-414` — QualityInspection 모델은 있지만, GoodsReceipt와의 연결 FK 없음
- `apps/purchase/models.py:205-230` — GoodsReceiptItem에 inspection_result, fail_qty 필드 없음

**flow 갭**:
```
현재:
GoodsReceipt → GoodsReceiptItem(qty=100) → StockMovement(IN, qty=100) ✓

요구:
GoodsReceipt → GoodsReceiptItem(qty=100)
  ↓
QualityInspection(pass=95, fail=5)
  ↓
StockMovement(IN, qty=95) ← pass_quantity만 입고
StockMovement(OUT, qty=5) ← 또는 별도 창고로 전용/반품 발주서 생성
```

**권장 조치**:
```
1. GoodsReceiptItem에 FK 추가: 
   - quality_inspection = ForeignKey(QualityInspection, ...)
   - received_as_passed_quantity (최종 입고 수량)
   
2. handle_goods_receipt() 개선:
   - GoodsReceiptItem 생성 직후, 관련 QualityInspection 확인
   - inspection.result == 'FAIL' → fail_qty만큼 OUT 또는 별도 처리 로직
   - 반품 발주서(PO) 자동 생성 옵션
   
3. 불합격 수량 추적:
   - FAIL_WAREHOUSE (별도 창고) 또는 soft delete로 미처리 상태 유지
   
4. 테스트: e2e/test_purchase_workflow.py에 QC FAIL 시나리오 추가
```

**심각도**: **HIGH** — 품질관리 프로세스 미완성, 부정확한 입고 재고 반영

---

### [HIGH] 3. 재고 마이너스 방지 로직 부재 (체크 제약만 존재)

**현상**:  
- Product.current_stock에 CHECK CONSTRAINT가 있음 (`stock_non_negative`)
- 하지만:
  1. **출고 시 선제 체크 없음** — StockMovement OUT 생성 허용 후 재고 부족 로깅만 함 (경고, 차단 아님)
  2. **데이터베이스 레벨 제약은 거동 불확정** — SQLite는 CHECK 미지원 (경고 무시), PostgreSQL 프로덕션에서만 작동
  3. **부분 출고 + 다중 프로세스** — 동시성 환경에서 재고 계산 오류 가능성 높음

**관련 코드**:
- `apps/inventory/models.py:95-104` — CheckConstraint만 존재, 애플리케이션 로직 제약 없음
- `apps/inventory/signals.py:204-210` — OutBound 시 warning 로깅만:
  ```python
  if product.current_stock < instance.quantity:
      logger.warning('Stock going negative: ...')
  ```
  차단하지 않음!
  
- `apps/sales/signals.py:96-126` — _auto_full_ship()에서는 InsufficientStockError 던지지만, 이건 Order 차원이고 개별 StockMovement 검증은 없음

**위험 시나리오**:
```
상황: 상품 현재고 10개, 주문 2건(각 8개) 동시 출고 처리
1. Order1 출고 신청 → StockMovement(OUT, 8) 생성 → current_stock: 10 - 8 = 2 ✓
2. Order2 출고 신청 → StockMovement(OUT, 8) 생성 → current_stock: 2 - 8 = -6 ✗ (음수!)
   → SQLite: CHECK 무시, PostgreSQL: CONSTRAINT VIOLATION (트랜잭션 롤백)

결과: 재고 음수 발생 (심각한 재무 결과)
```

**권장 조치**:
```
1. StockMovement.post_save() 또는 pre_save()에서:
   ```python
   if instance.movement_type in OUTBOUND_TYPES:
       product = Product.objects.select_for_update().get(pk=instance.product_id)
       if product.current_stock < instance.quantity and product.is_stockable:
           raise ValidationError(f'{product.name}: 재고 부족 ({product.current_stock}/{instance.quantity})')
   ```

2. 대안: 선택적 허용 플래그
   - Product.allow_negative_stock = BooleanField(default=False)
   - 서비스/보증(무형상품) 제외 설정
   
3. 트랜잭션 격리 수준: select_for_update() 사용 (현재 대부분 사용 중이나 전수 검증 필요)

4. 테스트: test_inventory.py에 동시성 테스트 추가 (threading)
```

**심각도**: **HIGH** — 재고 음수 발생 시 재무 결과 왜곡, 생산 계획 오류 (SQLite dev에서 특히 위험)

---

### ~~[HIGH] 4. QualityInspection 조건부합격(CONDITIONAL) 미처리~~ ✅ **해결 (Phase 13)**

**현상**:  
- QualityInspection.result = 'CONDITIONAL' 옵션 있음
- 하지만 **이 상태에 대한 후속 처리 로직 없음**:
  - 조건부합격 → 추가 검수 필요? 별도 액션?
  - 입고 지연? 아니면 그대로 입고 허용?
  - CONDITIONAL 상태에서 주문 확정/출고 가능?

**관련 코드**:
- `apps/production/models.py:348` — Result.CONDITIONAL 정의만 있음
- 시그널, 뷰에서 CONDITIONAL 분기 처리 없음
- QualityInspection 모델에 conditional_action, re_inspection_date 필드 없음

**권장 조치**:
```
1. QualityInspection 모델 확장:
   - conditional_action = TextField('조건부 액션') — 추가 검수 내용
   - re_inspection_date = DateField('재검수일', null=True)
   - approval_user = ForeignKey(User, ...) — 조건부 승인자
   
2. 입고 로직 개선:
   - CONDITIONAL 시 일부만 입고 가능, 나머지는 pending 상태 유지
   - 또는 전량 입고되지만 출고 금지 플래그 설정
   
3. 대시보드: 조건부합격 건 추적 뷰 추가
```

**심각도**: **HIGH** — 조건부합격 건의 상태 추적 불가, 품질 감시 미완성

---

### ~~[HIGH] 5. 재주문점(Reorder Point) 기반 자동 발주 미지원~~ ✅ **해결 (Phase 13)**

**현상**:  
- Product 모델에 `safety_stock` 필드만 있음 (안전재고)
- `reorder_point` 필드 없음 — 자동 발주 트리거 기준 부재
- MRP는 **수동 선택 기반** (생산계획 확인 후 MRP 뷰에서 부족 자재 선택)
- 정기 발주(re-order point 기반 자동화) 미지원

**현재 MRP**:
```python
MRPView._calculate_mrp():
  for plan in selected_plans:  # ← 수동 선택 필수!
    for bom_item in plan.bom.items:
      required = bom_item.quantity * remaining_qty
      if required > available_stock:
        → shortage 리스트에만 표시
```

**요구**:
```
1. Product.reorder_point (재주문점) = 자동 발주 기준
2. 일일/주간 스케줄러 (Celery Beat):
   - 전체 상품 current_stock 조사
   - if current_stock <= reorder_point → 자동 발주
   
3. 또는 실시간 신호 (post_save StockMovement):
   - OUT 후 current_stock < reorder_point → 경고/발주 제안
```

**권장 조치**:
```
1. Product에 필드 추가:
   - reorder_point = PositiveIntegerField(default=0)
   - reorder_qty = PositiveIntegerField(default=0) — 1회 발주 기본 수량
   - enable_auto_reorder = BooleanField(default=False)
   
2. Celery task 추가 (apps/production/tasks.py):
   def auto_reorder_task():
       for product in Product.objects.filter(enable_auto_reorder=True, is_active=True):
           if product.available_stock <= product.reorder_point:
               → 자동 발주 제안 또는 발주 생성
               
3. 테스트: test_production_workflow.py에 auto-reorder 시나리오 추가
```

**심각도**: **HIGH** — 정기 발주 자동화 미지원, 재고 부족 수동 관리 부담

---

### [MEDIUM] 6. 창고간이동(StockTransfer) 중 재고 동기화 오류 우려

**현상**:  
- StockTransfer 생성 → post_save 시그널에서 OUT + IN 스톡무브먼트 자동 생성
- 하지만 **상황에 따라 부정확**:
  1. **출발 창고 재고 부족** — OUT이 생성되어도 실제 출고 불가 → 재고 음수 발생 가능
  2. **IN 생성 후 OUT 실패** — 트랜잭션 내에서는 원자적이나, 시그널 순서 보장 문제
  3. **WarehouseStock 동기화** — StockTransfer ↔ WarehouseStock 관계 명시적 유지 미흡

**관련 코드**:
- `apps/inventory/signals.py:440-474` — create_transfer_movements():
  ```python
  @receiver(post_save, sender=StockTransfer)
  def create_transfer_movements(sender, instance, created, **kwargs):
      # OUT + IN 각각 생성 (트랜잭션 안)
      StockMovement.objects.create(...movement_type='OUT'...)
      StockMovement.objects.create(...movement_type='IN'...)
  ```
  출발 창고 재고 검증 없음!

**위험 시나리오**:
```
상황: 창고A 상품 현재고 5개, 창고B로 10개 이동 요청
1. StockTransfer(from_warehouse=A, to_warehouse=B, qty=10) 생성
2. create_transfer_movements() 발동:
   - StockMovement(OUT, warehouse=A, qty=10) 생성
   - StockMovement(IN, warehouse=B, qty=10) 생성
3. A의 current_stock: 5 - 10 = -5 ✗
   B의 warehouse_stock: 0 + 10 = 10 (부정확!)
```

**권장 조치**:
```
1. StockTransfer.pre_save() 또는 유효성 검증에서:
   from_ws = WarehouseStock.objects.get(warehouse=from_warehouse, product=product)
   if from_ws.quantity < quantity:
       raise ValidationError(f'출발 창고 재고 부족')
       
2. 트랜잭션 격리: select_for_update() 추가
   
3. 부분 이동 지원:
   - 재고 부족 시 가능한 범위만 이동
   - 또는 상태 = 'PENDING' → 승인 후 이동
```

**심각도**: **MEDIUM** — 창고간 이동 시 재고 음수 발생 가능, 창고별 재고 부정확

---

### [MEDIUM] 7. ShipmentItem → 예약재고 해제 시점 모호

**현상**:  
1. **Order CONFIRMED** → _auto_reserve_stock() → reserved_stock += qty ✓
2. **Order SHIPPED** → _auto_release_reserved_stock() → reserved_stock -= qty ✓
3. **ShipmentItem** 생성 시 → reserved_stock 해제? 아니면 Order 차원에서만?

실제로는 Order 상태로만 제어되고, ShipmentItem 자체는 예약재고와 무관:
- `apps/sales/models.py:685-705` — ShipmentItem은 단순 추적용, 재고 관련 시그널 없음
- `apps/sales/signals.py:55-95` — Order pre_save에서만 reserved_stock 처리

**문제**:
```
부분 출고 시나리오:
1. Order 확정: qty=100 → reserved=100
2. Shipment1: qty=50 → reserved는 여전히 100 (아직 50개 예약 중)
3. Shipment1 배송중 취소 → OUT StockMovement soft delete, reserved=100으로 유지?
   아니면 reserved=50으로 감소? 불명확!
```

**관련 코드**:
- `apps/sales/signals.py:614-625` — ShipmentItem post_save는 없고, 대신 수동 뷰에서만 처리
- `apps/sales/views.py:655-673` — 뷰에서 ShipmentItem.quantity 기반으로 reserved_stock 조정

**권장 조치**:
```
1. ShipmentItem post_save 시그널 추가:
   @receiver(post_save, sender=ShipmentItem)
   def release_reserved_on_shipment(sender, instance, created, **kwargs):
       if created:
           # Order 부분 출고 시 해당 출고분만 reserved 해제
           order_item = instance.order_item
           product = order_item.product
           if product.is_stockable:
               Product.objects.filter(pk=product.pk).update(
                   reserved_stock=F('reserved_stock') - instance.quantity
               )
               
2. ShipmentItem soft delete 시 reversed_stock 복원
   
3. 테스트: partial shipment 시나리오 추가
```

**심각도**: **MEDIUM** — 부분 출고 시 예약재고 추적 불명확, 수동 조정 필요

---

### [MEDIUM] 8. 이동평균단가 역산 계산식 정확도

**현상**:  
입고 취소 시 이동평균단가 재계산이 수행되지만, **정확도 검증 부재**:
- `apps/inventory/signals.py:370-389` — reverse_stock_on_soft_delete():
  ```python
  old_stock = product.current_stock  # ← 아직 차감되지 않은 기존값
  old_cost = product.cost_price
  new_stock = old_stock - old.quantity
  new_cost = ((old_stock * old_cost - old.quantity * old.unit_price) / new_stock)
  ```

**정확성 문제**:
1. **Decimal 정밀도** — 정수 계산만 사용, 소수점 이하 손실 (현재 Decimal 사용하나 확인 필요)
2. **다중 입고 취소 시** — 순서에 따라 결과 다를 수 있음
3. **LOT 소진 역순** — FIFO/LIFO 정확도 검증 부재

**코드 분석**:
- 현재 Decimal 사용 중이므로 정밀도는 OK
- 하지만 **단가 계산 검증 테스트 부재** → test_inventory.py에 다중 입고/취소 시나리오 없음

**권장 조치**:
```
1. test_inventory.py에 테스트 케이스 추가:
   def test_weighted_avg_reversal():
       # IN 3회: (100@10, 50@12, 30@15) → avg = ?
       # cancel 2번째 입고 → avg 재계산 검증
       
2. 모니터링: 원가 불일치 리포트 추가
   - 월별 이동평균단가 변동 로그
```

**심각도**: **MEDIUM** — 우려는 적으나, 원가 정확도 영향

---

## 추가 정보

### 잘 구현된 부분 (추천 유지)
1. **발주→입고→재고 기본 파이프라인** ✓
   - GoodsReceiptItem post_save → IN StockMovement 자동 생성
   - PO status 자동 전환 (PARTIAL_RECEIVED → RECEIVED)
   - AP + 세금계산서 자동 생성

2. **생산→재고 신호 처리** ✓
   - ProductionRecord 저장 시 PROD_IN (완제품) + PROD_OUT (BOM 기반) 자동 생성
   - 표준원가 자동 동기화
   - Plan/WorkOrder 상태 자동 전환

3. **StockLot (FIFO/LIFO) 관리** ✓
   - 입고 시 자동 생성
   - 출고 시 선택 방식 정확
   - 출고 취소 시 LOT 복원 로직

4. **Order → 예약재고 → 출고** ✓
   - 확정 시 예약 / 출고 시 해제
   - 취소 시 연쇄 처리

### 테스트 커버리지 확인 필요
- `test_inventory.py`: 재고 음수 방지, 동시성 테스트 부재
- `test_purchase.py`: QC FAIL 시나리오, 반품 프로세스 테스트 부재
- `e2e/test_production_workflow.py`: 다단계 BOM, 자동 재주문 시나리오 부재

---

## 우선순위 액션 플랜

| 우선순위 | 항목 | 영향도 | 개발 비용 | 일정 |
|---------|------|--------|---------|------|
| P1 | BOM 다단계 지원 | CRITICAL | H (5-7일) | 즉시 |
| P1 | 재고 마이너스 방지 (pre_save 검증) | CRITICAL | M (2-3일) | 즉시 |
| P2 | 입고 검수 → 불량 조정/반품 | HIGH | H (5-7일) | 1주 내 |
| P2 | 자동 재주문점(reorder) | HIGH | M (3-4일) | 1주 내 |
| P3 | 창고간이동 재고 검증 | MEDIUM | M (2-3일) | 2주 내 |
| P3 | ShipmentItem 예약재고 신호 | MEDIUM | S (1-2일) | 2주 내 |
| P4 | CONDITIONAL 결과 처리 | MEDIUM | S (1-2일) | 월간 |
| P4 | 이동평균단가 검증 테스트 | MEDIUM | S (1-2일) | 월간 |

---

## 결론

ERP Suite의 구매·생산·재고 시스템은 **기본 흐름은 견고**하나, **조직 프로세스 고도화(QC, 자동 발주, 다단계 생산)**와 **위험 관리(재고 음수 방지, 부분 출고 추적)**에서 개선이 필요합니다.

**P1(즉시) 항목 해결 후 전체 E2E 통합 테스트 강화** 권장.

