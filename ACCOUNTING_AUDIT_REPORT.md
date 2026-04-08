# ERP Suite 회계·전표·결산 프로세스 갭 점검 보고서

**점검일**: 2026-04-07  
**점검수준**: Very Thorough  
**점검 항목**: 8개 (전표 생성, AR/AP, 결산, 세금계산서, 은행 대사, 예산, 재무제표, 환율)

---

## 발견사항 요약

| 심각도 | 개수 | 주요 항목 |
|--------|------|---------|
| **CRITICAL** | 4 | 연체 자동 전환 미구현 (AR), 미지급금 연체 자동 전환 미실행, 외화 환차손익 미처리, 기말 조정 전표 기능 부재 |
| **HIGH** | 6 | 마감 기간 전표 생성 차단 미실행, Payment 삭제 시 AR/AP 갱신 미처리, soft delete 연쇄 부족, 예산 초과 경고 부재, AR soft delete 시 Payment 보존 이슈, 환율 미적용 시나리오 |
| **MEDIUM** | 5 | 현금흐름표 계정과목 분류 누락, Trial Balance 필터 불완전, 수수료 출금 시 AP 미연동, 환차손익 계정과목 미설정, ClosingPeriod 필드 부족 |
| **LOW** | 3 | BankAccount 잔액 검증 부재, 세금계산서 REJECTED 상태 처리 미정의, 연체 전환 후 결제 시 상태 복구 미정의 |

---

## 상세 발견사항

### 1. 전표 자동 생성 완전성

#### [CRITICAL] AR 생성 시 자동전표 미생성
- **파일**: `apps/sales/signals.py:401-429`
- **문제**: AR 자동 생성 `_auto_create_ar()` 함수는 **AR 객체만 생성**하고 차변/대변 전표를 생성하지 않음
- **영향**: 주문 확정 → AR 생성 → 전표 **자동 연동 중단**
- **예상 동작**: 주문 확정 시:
  - 차변: 미수금(120) 
  - 대변: 매출(401)
  의 전표가 자동 생성되어야 함
- **현상태**: 전표 없이 AR 객체만 존재
- **심각도**: CRITICAL — 매출 인식 전표 누락

#### [HIGH] AP 생성 시 자동전표 미생성
- **파일**: `apps/purchase/signals.py:148-181`
- **문제**: AP 자동 생성 `_auto_create_ap()` 함수도 **AP 객체만 생성**, 전표 미생성
- **영향**: 발주 전량 입고 완료 → AP 생성 → 전표 **자동 연동 중단**
- **예상 동작**: 입고 완료 시:
  - 차변: 매입원가(501) 또는 재고(140)
  - 대변: 미지급금(253)
  의 전표가 자동 생성되어야 함
- **현상태**: 전표 없이 AP 객체만 존재
- **심각도**: CRITICAL — 매입 인식 전표 누락

#### [HIGH] Payment 시그널의 전표 생성 (부분적 완성)
- **파일**: `apps/accounting/signals.py:61-143` (Payment)
- **평가**: ✓ 입금/출금 Payment → 자동전표 생성 완전 구현
- **차변/대변 균형**: ✓ 복식부기 규칙 준수 (입금/출금 각 2행)
- **단, 문제점**:
  - 계정과목 미존재 시 전표 삭제 후 로그 출력 (데이터 손실 위험)
  - `_get_closing_safe_date()`로 마감 기간 우회하는데, 차단하지 않음 (아래 참조)

#### [HIGH] 수수료 출금 전표 생성
- **파일**: `apps/sales/signals.py:325-399`
- **평가**: ✓ CommissionRecord SETTLED → 수수료 출금(DISBURSEMENT) + 전표 생성 완전 구현
- **문제점**:
  - 차변: 수수료(502) — 비용 과목이 아닌 비용 성격
  - AP와 **미연동** — 수수료 출금 시 AP를 생성하지 않음 (아래 HIGH 참조)
  - 수수료 전표 번호 자동 생성 미정의 (Payment 시그널에 의존)

#### [HIGH] 자산 취득·감가상각·처분 전표 (부분적 완성)
- **파일**: `apps/purchase/signals.py:87-145`, `apps/asset/signals.py:32-208`
- **평가**: ✓ 자산 취득, 감가상각 비용 전표 생성 구현
  - 자산 취득: 차변 150(유형자산) / 대변 253(미지급금) ✓
  - 감가상각: 차변 820(감가상각비) / 대변 159(감가상각누계액) ✓
  - 자산 처분: 차변 159(누적액), 현금 / 대변 150, 손익 ✓
- **완성도**: 높음 (계정과목 코드 명확, 복식부기 준수)

#### [HIGH] 배당 전표 (부분적 완성)
- **파일**: `apps/investment/signals.py:36-203`
- **평가**: ✓ Distribution 상태별 전표 생성 구현
  - PENDING: 차변 330(이익잉여금) / 대변 270(미지급배당금) ✓
  - PAID: 차변 270 / 대변 101(현금) ✓
- **문제**: 중복 방지 로직이 `description__contains`로 느슨함 (같은 이름의 여러 배당 시 충돌 위험)

---

### 2. AR/AP 라이프사이클

#### [CRITICAL] AR 연체(OVERDUE) 자동 전환 미구현
- **파일**: `apps/accounting/views.py:766-793` (ARListView)
- **현상태**: 
  ```python
  # ARListView.get_queryset()에서:
  # 연체 자동 전환 로직 **없음**
  # 마감 기간 체크도 없음
  ```
- **비교 (AP는 구현됨)**:
  ```python
  # APListView.get_queryset()에서 (line 858-864):
  AccountPayable.objects.filter(
      is_active=True,
      due_date__lt=today,
      status__in=['PENDING', 'PARTIAL'],
  ).update(status='OVERDUE')
  ```
- **문제**: AR은 due_date 경과해도 PENDING → OVERDUE 자동 전환 **없음**
- **영향**: 연체 추적 불가, 재무제표 오류 (PENDING으로 표시)
- **심각도**: CRITICAL — 선수금 관리 실패

#### [HIGH] Payment 시 AR/AP 잔액 갱신 (부분적 완성)
- **파일**: `apps/accounting/views.py:818-844` (PaymentCreateView)
- **평가**: ✓ 입금 처리 시 AR 잔액 갱신 완전 구현
  ```python
  ar.paid_amount = F('paid_amount') + amount
  ar.status = 'PAID' if ar.paid_amount >= ar.amount else 'PARTIAL'
  ```
- **문제**:
  1. **연체 상태 미처리**: OVERDUE → PAID 전환 시 이전 상태 확인 미흡
  2. **부분입금 후 재연체**: PARTIAL → 추가 미수 발생 시 다시 OVERDUE로 자동 전환되는가? (미정의)
  3. **Payment soft delete 시**: AR 잔액 **미복원**
     - 파일: `apps/accounting/models.py` — Payment soft delete 시그널 **없음**

#### [HIGH] Payment soft delete 시 AR/AP 미복원
- **파일**: `apps/accounting/signals.py`, `apps/sales/signals.py:465-571`
- **문제**: 
  - 주문 취소 시 Payment soft delete:
    ```python
    # sales/signals.py:475-481
    for payment in payments:
        payment.soft_delete()
    ```
  - 그러나 **AR 잔액 복원 로직 없음**
- **영향**: 부분입금 후 주문 취소 → AR.paid_amount가 그대로 유지 → 잔액 부정확
- **예상 동작**:
  ```python
  # soft_delete 시그널에서:
  ar.paid_amount = F('paid_amount') - payment.amount  # 복원
  ar.status = 'PENDING'  # 상태 복원
  ```

#### [MEDIUM] AR/AP soft delete 시 Payment 보존 이슈
- **파일**: `apps/accounting/models.py:337-436`
- **관계**: 
  ```python
  # AccountReceivable.payments (역참조)
  # AccountPayable.payments (역참조)
  ```
- **문제**: AR/AP soft delete 시:
  - Payment는 **is_active=True로 유지** (FK는 SET_NULL이 아님)
  - 결과: 삭제된 AR에 대한 orphaned Payment 존재
- **영향**: 입금 기록이 AR 없이 떠다님

---

### 3. 결산 마감 (ClosingPeriod)

#### [CRITICAL] 마감 기간 전표 생성 차단 미작동
- **파일**: `apps/accounting/signals.py:34-49` (`_get_closing_safe_date()`)
- **현상태**:
  ```python
  def _get_closing_safe_date(target_date):
      """마감된 월이면 다음 월 1일자 반환, 아니면 원본 반환"""
      if ClosingPeriod.objects.filter(
          year=target_date.year,
          month=target_date.month,
          is_closed=True,
          is_active=True,
      ).exists():
          # → 다음 월로 날짜 **변경**
          return date(target_date.year + 1, 1, 1)  # (잘못된 로직)
      return target_date
  ```
- **문제**: 
  1. 마감 기간 전표를 **차단하지 않고 날짜 변경** → 회계 기록이 틀림
  2. 예: 3월 마감 후 3월 15일 입금 → 자동으로 12월 1일자 전표 생성 (오류!)
  3. 각 시그널에서 호출되나, 실제로는 **차단이 아닌 우회**
- **예상 동작**: 마감된 월의 전표는 **생성 거부** (ValidationError)
- **심각도**: CRITICAL — 결산 무결성 위반

#### [HIGH] 기말 조정 전표(기말 조정 일정) 미구현
- **파일**: `apps/accounting/models.py:942-969` (ClosingPeriod)
- **문제**: ClosingPeriod 모델은 마감 일시/자만 기록하고, **기말 조정 기능 없음**
  - 감가상각 (월말 일괄)
  - 선급료 → 비용 전환
  - 미지급료 → 미지급금 전환
  - 대손상각비
  - 기타 기말 조정
  등이 **자동화되지 않음**
- **현상태**: 수동으로 전표 입력해야 함
- **영향**: 월말 마감 프로세스 불완전

#### [MEDIUM] ClosingPeriod 필드 부족
- **파일**: `apps/accounting/models.py:942-969`
- **누락 필드**:
  - `close_reason` — 왜 마감했는가 (정기 vs 특별)?
  - `reopened_at`, `reopened_by` — 재개통 기록
  - `locked_after` — 마감 후 추가 작업 가능 여부 (예: 세금계산서만 추가 발행)
- **영향**: 마감 관리 추적성 약함

---

### 4. 세금계산서 완전성

#### [HIGH] 세금계산서 자동 생성 미완전 (AR/AP 고아 문제)
- **파일**: `apps/sales/signals.py:431-462`, `apps/purchase/signals.py:183-222`
- **평가**: ✓ Order 확정 시 매출 세금계산서 자동 생성
- **문제점**:
  1. **TaxInvoice가 독립적 엔티티** — Order와 FK 연결이지만, AR과는 미연동
     ```python
     # AR과 TaxInvoice의 관계 미정의
     # TaxInvoice.receivable (역참조) 없음
     ```
  2. **Order 취소 시 TaxInvoice soft delete는 되지만, AR과 함께 관리되는가?**
     - AR 취소 → TaxInvoice 취소 (별도 로직)
     - 일관성 검증 부재

#### [MEDIUM] 세금계산서 상태 REJECTED 처리 미정의
- **파일**: `apps/accounting/models.py:75-151`
- **현상태**:
  ```python
  class ElectronicStatus(models.TextChoices):
      NONE = 'NONE', '미발행'
      ISSUED = 'ISSUED', '발행완료'
      REJECTED = 'REJECTED', '국세청 반려'  # ← 반려 후 처리?
  ```
- **문제**: REJECTED 상태 후 **재발행 절차 미정의**
  - 재발행 시 이전 REJECTED 세금계산서 처리?
  - 재발행 후 AR 업데이트?
- **영향**: 국세청 반려 건 처리 절차 불명확

---

### 5. 은행 대사 (Bank Reconciliation)

#### [MEDIUM] BankAccount.balance 검증 부재
- **파일**: `apps/accounting/models.py:438-493`
- **현상태**: balance는 F() 원자적 갱신되나, **검증 로직 없음**
- **문제**: 
  1. Payment/AccountTransfer 외 다른 경로로 잔액이 변경될 가능성
  2. DB 직접 수정 시 불일치
  3. **은행 대사(Reconciliation) 보고서** 없음 — 실제 은행 잔액과 비교 불가
- **영향**: 잔액 오류 감지 어려움

#### [HIGH] Payment soft delete 시 BankAccount 잔액 미복원
- **파일**: `apps/sales/signals.py:505-510`
- **현상태**:
  ```python
  # 수수료 DISBURSEMENT 취소 시:
  BankAccount.objects.filter(pk=pmt.bank_account_id).update(
      balance=F('balance') + pmt.amount,  # ✓ 입금 취소는 복원됨
  )
  ```
- **문제**: 일반 Payment soft delete 시그널이 **없음**
  - AR 취소 → Payment soft delete → BankAccount 잔액 미복원
- **영향**: 잔액 불일치

---

### 6. 예산 관리

#### [HIGH] 예산 초과 경고/차단 기능 부재
- **파일**: `apps/accounting/models.py:869-940`
- **현상태**: Budget 모델에는 `budget_amount`와 `actual_amount` 계산만 있고
- **누락**:
  1. **초과 경고**: actual > budget 시 경고
  2. **차단**: 예산 초과 시 voucher/payment 생성 거부 옵션
  3. **부서별/계정과목별 예산** — Budget은 단일 계정과목 기반만 지원
- **영향**: 예산 관리 기능이 대시보드 조회용일 뿐, 통제 불가

#### [MEDIUM] Budget 커리 예산 편성 프로세스 부재
- **파일**: `apps/accounting/models.py:869-940`
- **문제**: 
  - Budget 생성 후 상태 추적 없음 (DRAFT → APPROVED → ACTIVE?)
  - 월중 예산 수정 가능 여부 미정의
  - 부서장 승인 프로세스 없음

---

### 7. 재무제표

#### [HIGH] 현금흐름표 계정과목 분류 누락
- **파일**: `apps/accounting/views.py:3156-3210`
- **현상태**: CashFlowView는 존재하나, 구현이 **불완전**
  ```python
  class CashFlowView(ManagerRequiredMixin, TemplateView):
      def get_context_data(self, **kwargs):
          # ... 변수 초기화만 있고
          # 영업/투자/재무 활동별 분류 로직 **미완성**
  ```
- **문제**: 
  1. 계정과목별 CF 분류 테이블 없음
  2. 간접법 계산 미구현
  3. 직접법 계산 미구현
- **영향**: 현금흐름표 조회 불가 또는 부정확

#### [HIGH] Trial Balance 필터 불완전
- **파일**: `apps/accounting/views.py:2229-2265`
- **현상태**:
  ```python
  qs = VoucherLine.objects.filter(
      is_active=True, voucher__is_active=True,
      voucher__approval_status='APPROVED',
      voucher__voucher_date__lte=as_of,
  )
  ```
- **문제**: 
  1. **DRAFT 전표 제외** — 관리자가 draft로 남겨둔 전표가 누락됨
  2. **ClosingPeriod 마감 기간 필터 없음** — 마감된 월의 추가 전표가 포함될 수 있음
  3. **다중 통화 시산표** — 환율 적용 불명확

#### [MEDIUM] 대차대조표 정확성 (부분적 우려)
- **파일**: `apps/accounting/views.py:3023-3090`
- **평가**: ✓ 계정과목 분류 명확 (ASSET/LIABILITY/EQUITY)
- **우려점**:
  1. **ClosingPeriod 마감 검증 없음** — 마감 후 전표 추가 시 혼란
  2. **미완성 주문/발주** — off-balance 항목 미추적
     - 예: 발주했으나 미입고 → 약정 채무 미기록
  3. **이연자산/부채** — prepaid/accrued 자동 계산 없음

---

### 8. 통화/환율

#### [CRITICAL] 외화 주문의 환차손익 미처리
- **파일**: `apps/sales/models.py:278-284`, `apps/sales/signals.py` (전체)
- **현상태**:
  ```python
  # Order 모델에는 currency, exchange_rate 필드가 있으나
  class Order(BaseModel):
      currency = models.ForeignKey('accounting.Currency', ...)
      exchange_rate = models.DecimalField('적용환율', ...)
  ```
- **문제**: 
  1. **환율 적용 시점**: 주문 확정 시 환율을 기록하지만, **환차손익 계산 미구현**
  2. **환차손익 인식 시점**: 
     - 입금 시? (결제액이 다를 때)
     - 월말? (기한말 평가 재계산)
  3. **계정과목**: 환차손익 계정(970, 971 등) **미설정**
  4. **전표 자동 생성**: 환차손익 전표 **없음**
- **시나리오 예**:
  - 주문: USD 1,000 @ 1,300 KRW = 1,300,000 KRW
  - AR 생성: 1,300,000 KRW
  - 입금: USD 1,000 @ 1,320 KRW (환율 변동) = 1,320,000 KRW
  - 결과: 20,000 KRW **환차손** 미처리 → 잘못된 AR 잔액
- **심각도**: CRITICAL — 다국적 거래가 있는 경우 심각한 오류

#### [HIGH] 환율 미적용 시나리오
- **파일**: `apps/sales/models.py`, `apps/accounting/views.py`
- **문제**:
  1. **외화 Order 생성 후 환율 변경** — 기존 주문의 환율 업데이트 정책 미정의
  2. **Order.exchange_rate** 기록만 되고, **실제 환율 적용 로직 부재**
  3. **결산 시 외화 자산 평가** — 기말 환율로 재평가하지 않음
- **영향**: 외화 거래 정확성 심각함

#### [MEDIUM] 환차손익 계정과목 미설정
- **파일**: `apps/accounting/models.py` (AccountCode 초기화)
- **누락 계정**:
  - 970 — 환차이익
  - 971 — 환차손
  - (또는 501-509 비용 내 환차손 구분)
- **영향**: 환차손익 전표 생성 불가

---

## 요약 및 우선순위

### CRITICAL (즉시 해결 필수)
1. **AR 자동전표 생성 추가** — 주문 확정 시 AR + 전표 자동 생성
2. **AP 자동전표 생성 추가** — 입고 완료 시 AP + 전표 자동 생성
3. **AR 연체 자동 전환 추가** (AR은 미구현, AP는 구현됨)
4. **마감 기간 전표 차단 구현** — `_get_closing_safe_date()`를 진정한 **차단 로직**으로 변경
5. **외화 환차손익 처리 추가** — 환율 변동 시 손익 인식 및 전표 자동 생성

### HIGH (1주일 내)
1. **Payment soft delete 시 AR/AP 잔액 복원** — 주문 취소 시 정확한 상태 관리
2. **BankAccount 잔액 자동 복원** — soft delete 시그널 추가
3. **수수료 출금 시 AP 연동** — CommissionRecord 정산 → AP 자동 생성
4. **ClosingPeriod 마감 검증** — 마감된 월의 전표 생성/수정 완전 차단
5. **현금흐름표 완성** — 영업/투자/재무 활동별 분류 완전 구현
6. **Trial Balance 필터 강화** — DRAFT 전표 제외, 마감 검증 추가

### MEDIUM (2주일 내)
1. **기말 조정 전표 자동화** — 감가상각, 선급료 등 정기 조정
2. **예산 초과 경고/차단** — 예산 대비 실적 모니터링 기능
3. **AR/AP soft delete 시 연쇄 처리** — Payment 상태 관리 개선
4. **환차손익 계정과목 설정** — 970, 971 등 추가 및 정책 문서화

### LOW (3주일 이상)
1. **은행 대사 보고서** — 실제 은행 잔액과 비교 기능
2. **세금계산서 반려 재발행 절차** — REJECTED → 재발행 프로세스
3. **다중 통화 재무제표** — 기본 통화 기준 통합 재무제표

---

## 코드 예시 (수정안)

### 1. AR 자동전표 생성 (sales/signals.py)

```python
def _auto_create_ar_and_voucher(order):
    """주문 확정 시 AR + 자동전표 생성"""
    if not order.partner:
        return

    grand_total = int(order.grand_total) if order.grand_total else 0
    if grand_total <= 0:
        return

    if AccountReceivable.objects.filter(order=order, is_active=True).exists():
        return

    with transaction.atomic():
        ar = AccountReceivable.objects.create(
            partner=order.partner,
            order=order,
            amount=grand_total,
            due_date=order.delivery_date or (date.today() + timedelta(days=30)),
            status='PENDING',
            created_by=order.created_by,
        )

        # ✓ NEW: 자동전표 생성
        from apps.accounting.models import AccountCode, Voucher, VoucherLine
        
        ar_acct = AccountCode.objects.get(code='120', is_active=True)  # 미수금
        revenue_acct = AccountCode.objects.get(code='401', is_active=True)  # 매출
        
        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='TRANSFER',
            voucher_date=order.confirmed_date or date.today(),
            description=f'주문 {order.order_number} 매출 인식',
            approval_status='APPROVED',
            created_by=order.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=ar_acct,
            debit=grand_total, credit=0,
            description=f'{order.partner.name} 미수금',
            created_by=order.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=revenue_acct,
            debit=0, credit=grand_total,
            description=f'주문 {order.order_number} 매출',
            created_by=order.created_by,
        )
        
        logger.info(
            'Auto-created AR + voucher for order %s: %s원',
            order.order_number, grand_total,
        )
```

### 2. 마감 기간 전표 차단 (accounting/signals.py)

```python
def _validate_closing_period(voucher_date):
    """마감된 월의 전표 생성 차단"""
    from .models import ClosingPeriod
    from django.core.exceptions import ValidationError
    
    closed = ClosingPeriod.objects.filter(
        year=voucher_date.year,
        month=voucher_date.month,
        is_closed=True,
        is_active=True,
    ).exists()
    
    if closed:
        raise ValidationError(
            f'{voucher_date.year}년 {voucher_date.month}월은 마감되었습니다. '
            '전표 생성이 불가합니다.'
        )

# 각 시그널의 voucher 생성 전에 호출
@receiver(post_save, sender=Payment)
def payment_update_balance_and_voucher(sender, instance, created, **kwargs):
    if not created or not instance.voucher:
        return

    with transaction.atomic():
        # ...
        _validate_closing_period(instance.payment_date)  # ✓ 추가
        # 전표 생성 로직
```

### 3. AR 연체 자동 전환 추가 (accounting/views.py)

```python
class ARListView(ManagerRequiredMixin, ListView):
    def get_queryset(self):
        # ✓ NEW: AR 연체 자동 전환 (AP와 동일)
        today = date.today()
        AccountReceivable.objects.filter(
            is_active=True,
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL'],
        ).update(status='OVERDUE')
        
        qs = super().get_queryset().filter(is_active=True).select_related('partner')
        # ... 기존 필터링
```

---

## 테스트 권장사항

1. **AR/AP 자동전표**: 주문 확정 시 AR + 전표 동시 생성 확인
2. **환차손익**: 외화 주문 → 입금 시 환율 차이 전표 자동 생성 확인
3. **마감 차단**: 마감된 월의 입금 등록 시 ValidationError 발생 확인
4. **soft delete 연쇄**: 주문 취소 → Payment soft delete → AR/AP 잔액 복원 확인
5. **재무제표**: 대차대조표 + 시산표 차변/대변 균형 확인

---

## 결론

ERP Suite의 회계·전표·결산 프로세스는 **약 60~70% 완성** 상태입니다.

**강점**:
- Payment 입출금 전표 자동 생성 ✓
- 자산 감가상각 전표 자동 생성 ✓
- AP 연체 자동 전환 ✓
- 복식부기 원칙 준수 ✓

**약점**:
- AR/AP 자동전표 미생성 (CRITICAL)
- AR 연체 자동 전환 미구현 (CRITICAL)
- 외화 환차손익 미처리 (CRITICAL)
- 마감 기간 차단 미작동 (CRITICAL)
- 기말 조정 자동화 부재

**권장사항**: CRITICAL 항목 4개를 우선 해결하고, 이후 HIGH 항목을 순차적으로 처리하여 **완전한 회계 자동화**를 달성할 것을 권장합니다.
