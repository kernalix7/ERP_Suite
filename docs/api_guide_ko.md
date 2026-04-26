# ERP Suite REST API 가이드

[English](api_guide.md) | **한국어**

> 이 문서는 ERP Suite의 **REST API 사용법**을 다룹니다.
> URL 라우팅 표는 [api_reference_ko.md](api_reference_ko.md) 참조.
> 인터랙티브 스키마는 dev 서버에서 `/api/docs/` (Swagger UI) 또는 `/api/redoc/` 접속.

## 1. 개요

| 항목 | 값 |
|---|---|
| 프레임워크 | Django REST Framework + drf-spectacular |
| 인증 | JWT (SimpleJWT, Bearer 토큰) + Session (브라우저용) |
| 베이스 URL | `https://<host>/api/` |
| 페이지네이션 | PageNumberPagination, 페이지당 **20**건 |
| 스로틀링 | 익명 20req/min, 인증 사용자 60req/min |
| 응답 포맷 | JSON |
| OpenAPI 스키마 | `/api/schema/` |
| Swagger UI | `/api/docs/` |
| ReDoc | `/api/redoc/` |
| ViewSet 수 | 78개 (sales/purchase/inventory/accounting/hr/asset/marketplace 등 전 도메인) |

## 2. 인증 (JWT)

### 2.1 토큰 발급

```bash
curl -X POST https://<host>/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword"}'
```

응답:
```json
{
  "access": "eyJ0eXAi...",
  "refresh": "eyJ0eXAi..."
}
```

- **access**: 5분 유효 (기본). 인증 헤더에 `Bearer <access>` 형식 사용
- **refresh**: 7일 유효. access 갱신용

### 2.2 인증된 요청

```bash
curl https://<host>/api/orders/ \
  -H "Authorization: Bearer <access_token>"
```

### 2.3 토큰 갱신

```bash
curl -X POST https://<host>/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```

### 2.4 토큰 검증

```bash
curl -X POST https://<host>/api/token/verify/ \
  -H "Content-Type: application/json" \
  -d '{"token": "<access_token>"}'
```

## 3. 요청/응답 패턴

### 3.1 페이지네이션

```bash
curl "https://<host>/api/orders/?page=2&page_size=50" \
  -H "Authorization: Bearer <token>"
```

응답 구조:
```json
{
  "count": 1234,
  "next": "https://.../api/orders/?page=3",
  "previous": "https://.../api/orders/?page=1",
  "results": [ ... 20개 객체 ... ]
}
```

### 3.2 필터/검색/정렬

| 파라미터 | 예시 | 설명 |
|---|---|---|
| `?<field>=value` | `?status=CONFIRMED` | django-filter 정확일치 |
| `?search=<keyword>` | `?search=네이버` | 검색 가능 필드에서 부분일치 |
| `?ordering=<field>` | `?ordering=-order_date` | 정렬 (앞에 `-` 시 내림차순) |

각 ViewSet의 `filterset_fields`/`search_fields`/`ordering_fields` 는 Swagger 스키마에서 확인.

### 3.3 표준 HTTP 메서드

| 메서드 | URL 패턴 | 용도 |
|---|---|---|
| `GET` | `/api/orders/` | 목록 |
| `POST` | `/api/orders/` | 생성 |
| `GET` | `/api/orders/{id}/` | 상세 |
| `PUT` | `/api/orders/{id}/` | 전체 수정 |
| `PATCH` | `/api/orders/{id}/` | 부분 수정 |
| `DELETE` | `/api/orders/{id}/` | 삭제 (soft delete: is_active=False) |

### 3.4 에러 응답

| 코드 | 의미 | 본문 예시 |
|---|---|---|
| 400 | 검증 실패 | `{"field": ["error message"]}` |
| 401 | 미인증 | `{"detail": "Authentication credentials were not provided."}` |
| 403 | 권한 없음 | `{"detail": "You do not have permission to perform this action."}` |
| 404 | 미존재 | `{"detail": "Not found."}` |
| 429 | 스로틀 초과 | `{"detail": "Request was throttled."}` |
| 500 | 서버 오류 | (Sentry로 자동 전송) |

## 4. 권한 (RBAC)

| 역할 | 권한 |
|---|---|
| `admin` | 전체 |
| `manager` | 매니저 + 직원 권한 (생성/수정 가능) |
| `staff` | 조회 위주 (모듈별 권한 다름) |

ViewSet은 기본 `IsAuthenticated`이며, 일부는 `ManagerRequired`/`AdminRequired` 적용.
모듈별 세분 권한은 `apps/accounts/permission_utils.py` 참조.

## 5. 핵심 엔드포인트 카테고리

### 5.1 영업 (Sales)
| 리소스 | URL | 비고 |
|---|---|---|
| 거래처 | `/api/partners/` | filter: partner_type, entity_type |
| 고객 | `/api/customers/` | |
| 주문 | `/api/orders/` | filter: status, sales_channel, payment_method, tax_type |
| 주문항목 | `/api/order-items/` | |
| 견적서 | `/api/quotations/` | |
| 출고 | `/api/shipments/` | |
| 마켓플레이스 주문 | `/api/marketplace-orders/` | 가져온 외부 주문 |

### 5.2 재고 (Inventory)
| 리소스 | URL | 비고 |
|---|---|---|
| 제품 | `/api/products/` | filter: product_type, category |
| 카테고리 | `/api/categories/` | |
| 창고 | `/api/warehouses/` | |
| 재고이동 | `/api/stock-movements/` | |
| 시리얼번호 | `/api/serial-numbers/` | |

### 5.3 회계 (Accounting)
| 리소스 | URL | 비고 |
|---|---|---|
| 전표 | `/api/vouchers/` | |
| 세금계산서 | `/api/tax-invoices/` | filter: invoice_type, tax_type, issuer_type, vat_deduction_type |
| AR (미수금) | `/api/accounts-receivable/` | |
| AP (미지급금) | `/api/accounts-payable/` | |
| 입출금 | `/api/payments/` | filter: payment_type, payment_method |
| 결제계좌 | `/api/bank-accounts/` | |

### 5.4 생산 (Production)
| 리소스 | URL |
|---|---|
| BOM | `/api/boms/` |
| BOM 항목 | `/api/bom-items/` |
| 생산계획 | `/api/production-plans/` |
| 작업지시 | `/api/work-orders/` |

### 5.5 인사 (HR)
| 리소스 | URL |
|---|---|
| 직원 | `/api/employees/` |
| 급여 | `/api/payrolls/` |

### 5.6 자산 (Asset)
| 리소스 | URL |
|---|---|
| 자산 | `/api/fixed-assets/` |
| 자산 카테고리 | `/api/asset-categories/` |
| 자산 이전 | `/api/asset-transfers/` |
| 인증/검사 | `/api/certifications/` |
| 리스 계약 | `/api/lease-contracts/` |
| 자산 감사 | `/api/asset-audits/` |

### 5.7 결재/AS/문의
| 리소스 | URL |
|---|---|
| 결재 요청 | `/api/approval-requests/` |
| 결재 단계 | `/api/approval-steps/` |
| AS 요청 | `/api/service-requests/` |
| 문의 | `/api/inquiries/` |

전체 78개 ViewSet은 `apps/api/urls.py` 참조.

## 6. 사용 예시

### 6.1 Python (requests)

```python
import requests

BASE = "https://your-host"

# 1) 인증
r = requests.post(f"{BASE}/api/token/", json={
    "username": "admin", "password": "yourpassword",
})
access = r.json()["access"]
headers = {"Authorization": f"Bearer {access}"}

# 2) 주문 목록 조회
r = requests.get(f"{BASE}/api/orders/", headers=headers, params={
    "status": "CONFIRMED",
    "sales_channel": "NAVER",
    "ordering": "-order_date",
    "page_size": 50,
})
orders = r.json()["results"]

# 3) 주문 생성
r = requests.post(f"{BASE}/api/orders/", headers=headers, json={
    "order_number": "ORD-API-001",
    "partner": 1,
    "order_date": "2026-04-26",
    "status": "DRAFT",
    "sales_channel": "DIRECT",
    "payment_method": "CARD",
    "tax_type": "TAXABLE",
})
new_id = r.json()["id"]

# 4) 부분 수정
requests.patch(
    f"{BASE}/api/orders/{new_id}/",
    headers=headers,
    json={"status": "CONFIRMED"},
)
```

### 6.2 cURL — 마켓플레이스 주문 가져오기

```bash
ACCESS=$(curl -s -X POST https://your-host/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"pass"}' | jq -r .access)

curl "https://your-host/api/marketplace-orders/?platform=NAVER&imported_at__gte=2026-04-01" \
  -H "Authorization: Bearer $ACCESS" | jq '.results[].order_number'
```

### 6.3 JavaScript (fetch)

```javascript
const access = (await (await fetch('/api/token/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({username: 'admin', password: 'pass'}),
})).json()).access;

const orders = await (await fetch('/api/orders/?status=CONFIRMED', {
  headers: {Authorization: `Bearer ${access}`},
})).json();
```

## 7. 비즈니스 규칙 (API 호출 시 알아두면 좋은 것)

- **Soft delete**: DELETE 호출 시 실제 삭제 안 됨. `is_active=False` 처리. 목록 조회 시 자동 제외.
- **자동 시그널**: Order.status 변경 시 자동으로 stock movement, AR, tax invoice 생성됨. API 클라이언트가 별도 호출 불필요.
- **마감기간**: ClosingPeriod로 마감된 월의 전표/주문은 수정 불가 (400 응답).
- **F() atomic**: 재고 변동은 race condition 안전. 동시 호출 가능.
- **VAT 자동계산**: OrderItem 생성 시 `tax_type`에 따라 VAT 자동 분기 (영세율/면세는 0).
- **History**: 모든 변경 이력은 simple_history로 자동 기록. 별도 audit endpoint 없이 admin에서 조회.

## 8. 알려진 제약

- **개별 ViewSet 권한**: 일부는 `ManagerRequired` (직원은 조회만 가능). Swagger 스키마 또는 403 응답으로 판별.
- **벌크 생성 미지원**: ViewSet 기본 `POST`는 단일 객체만. 다중 생성은 반복 호출 또는 별도 management command.
- **검색은 SQL ILIKE**: 한글 형태소 분석 안 함. 정확한 키워드 사용 권장.
- **암호화 필드**: Partner.phone/email/address 등 일부는 EncryptedCharField. API 응답에서는 자동 복호화되어 평문 노출 — 권한 적용 신중히.

## 9. 참고

- DRF 공식 문서: https://www.django-rest-framework.org/
- SimpleJWT 문서: https://django-rest-framework-simplejwt.readthedocs.io/
- drf-spectacular 문서: https://drf-spectacular.readthedocs.io/
- 본 프로젝트 OpenAPI 스키마: `/api/schema/` 다운로드 후 Postman/Insomnia 등에 import 가능
