# ERP Suite REST API Guide

**English** | [한국어](api_guide_ko.md)

> This document covers **REST API usage** for ERP Suite.
> URL routing tables: see [api_reference.md](api_reference.md).
> Interactive schema: dev server `/api/docs/` (Swagger UI) or `/api/redoc/`.

## 1. Overview

| Item | Value |
|---|---|
| Framework | Django REST Framework + drf-spectacular |
| Authentication | JWT (SimpleJWT, Bearer token) + Session (browser) |
| Base URL | `https://<host>/api/` |
| Pagination | PageNumberPagination, **20** per page |
| Throttling | Anonymous 20 req/min, authenticated 60 req/min |
| Response format | JSON |
| OpenAPI schema | `/api/schema/` |
| Swagger UI | `/api/docs/` |
| ReDoc | `/api/redoc/` |
| ViewSet count | 78 (sales/purchase/inventory/accounting/hr/asset/marketplace, etc.) |

## 2. Authentication (JWT)

### 2.1 Obtain token

```bash
curl -X POST https://<host>/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword"}'
```

Response:
```json
{"access": "eyJ0eXAi...", "refresh": "eyJ0eXAi..."}
```

- `access`: 5-minute lifetime (default). Use as `Bearer <access>` in Authorization header.
- `refresh`: 7-day lifetime. Used to obtain a new access token.

### 2.2 Authenticated request

```bash
curl https://<host>/api/orders/ -H "Authorization: Bearer <access_token>"
```

### 2.3 Refresh token

```bash
curl -X POST https://<host>/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```

## 3. Request/Response Patterns

### 3.1 Pagination

```bash
curl "https://<host>/api/orders/?page=2&page_size=50" -H "Authorization: Bearer <token>"
```

Response shape:
```json
{
  "count": 1234,
  "next": "https://.../api/orders/?page=3",
  "previous": "https://.../api/orders/?page=1",
  "results": [/* 20 objects */]
}
```

### 3.2 Filter / Search / Order

| Param | Example | Description |
|---|---|---|
| `?<field>=value` | `?status=CONFIRMED` | django-filter exact match |
| `?search=<keyword>` | `?search=naver` | partial match on searchable fields |
| `?ordering=<field>` | `?ordering=-order_date` | sort (`-` prefix for descending) |

Each ViewSet's `filterset_fields` / `search_fields` / `ordering_fields` are listed in the Swagger schema.

### 3.3 Standard HTTP methods

| Method | URL pattern | Purpose |
|---|---|---|
| `GET` | `/api/orders/` | list |
| `POST` | `/api/orders/` | create |
| `GET` | `/api/orders/{id}/` | detail |
| `PUT` | `/api/orders/{id}/` | replace |
| `PATCH` | `/api/orders/{id}/` | partial update |
| `DELETE` | `/api/orders/{id}/` | delete (soft-delete: `is_active=False`) |

### 3.4 Error responses

| Code | Meaning |
|---|---|
| 400 | validation error — `{"field": ["message"]}` |
| 401 | not authenticated |
| 403 | not permitted |
| 404 | not found |
| 429 | throttled |
| 500 | server error (auto-reported to Sentry) |

## 4. Permissions (RBAC)

| Role | Capability |
|---|---|
| `admin` | full |
| `manager` | manager + staff (create/update) |
| `staff` | mostly read (varies per module) |

ViewSets default to `IsAuthenticated`; some require `ManagerRequired` / `AdminRequired`.
Module-scoped permissions: see `apps/accounts/permission_utils.py`.

## 5. Endpoint Categories

### 5.1 Sales
| Resource | URL | Notes |
|---|---|---|
| Partners | `/api/partners/` | filter: partner_type, entity_type |
| Customers | `/api/customers/` | |
| Orders | `/api/orders/` | filter: status, sales_channel, payment_method, tax_type |
| Order items | `/api/order-items/` | |
| Quotations | `/api/quotations/` | |
| Shipments | `/api/shipments/` | |
| Marketplace orders | `/api/marketplace-orders/` | imported external orders |

### 5.2 Inventory
| Resource | URL |
|---|---|
| Products | `/api/products/` |
| Categories | `/api/categories/` |
| Warehouses | `/api/warehouses/` |
| Stock movements | `/api/stock-movements/` |
| Serial numbers | `/api/serial-numbers/` |

### 5.3 Accounting
| Resource | URL |
|---|---|
| Vouchers | `/api/vouchers/` |
| Tax invoices | `/api/tax-invoices/` |
| Receivables | `/api/accounts-receivable/` |
| Payables | `/api/accounts-payable/` |
| Payments | `/api/payments/` |
| Bank accounts | `/api/bank-accounts/` |

### 5.4 Production
| Resource | URL |
|---|---|
| BOMs | `/api/boms/` |
| BOM items | `/api/bom-items/` |
| Production plans | `/api/production-plans/` |
| Work orders | `/api/work-orders/` |

### 5.5 HR
| Resource | URL |
|---|---|
| Employees | `/api/employees/` |
| Payrolls | `/api/payrolls/` |

### 5.6 Asset
| Resource | URL |
|---|---|
| Fixed assets | `/api/fixed-assets/` |
| Asset categories | `/api/asset-categories/` |
| Asset transfers | `/api/asset-transfers/` |
| Certifications | `/api/certifications/` |
| Lease contracts | `/api/lease-contracts/` |
| Asset audits | `/api/asset-audits/` |

### 5.7 Approval / Service / Inquiry
| Resource | URL |
|---|---|
| Approval requests | `/api/approval-requests/` |
| Approval steps | `/api/approval-steps/` |
| Service requests | `/api/service-requests/` |
| Inquiries | `/api/inquiries/` |

Full list of 78 ViewSets: `apps/api/urls.py`.

## 6. Usage Examples

### 6.1 Python (requests)

```python
import requests
BASE = "https://your-host"

# Authenticate
access = requests.post(
    f"{BASE}/api/token/",
    json={"username": "admin", "password": "yourpassword"},
).json()["access"]
headers = {"Authorization": f"Bearer {access}"}

# List orders
orders = requests.get(
    f"{BASE}/api/orders/",
    headers=headers,
    params={"status": "CONFIRMED", "sales_channel": "NAVER", "ordering": "-order_date"},
).json()["results"]

# Create
new_id = requests.post(f"{BASE}/api/orders/", headers=headers, json={
    "order_number": "ORD-API-001",
    "partner": 1, "order_date": "2026-04-26", "status": "DRAFT",
    "sales_channel": "DIRECT", "payment_method": "CARD", "tax_type": "TAXABLE",
}).json()["id"]

# Update
requests.patch(f"{BASE}/api/orders/{new_id}/", headers=headers, json={"status": "CONFIRMED"})
```

### 6.2 cURL — fetch marketplace orders

```bash
ACCESS=$(curl -s -X POST https://your-host/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"pass"}' | jq -r .access)

curl "https://your-host/api/marketplace-orders/?platform=NAVER" \
  -H "Authorization: Bearer $ACCESS" | jq '.results[].order_number'
```

## 7. Business Rules to Know

- **Soft delete**: DELETE flips `is_active=False`. List queries auto-filter active.
- **Auto signals**: Order.status changes trigger stock movement, AR, tax invoice creation. No separate API calls needed.
- **Closing period**: ClosingPeriod-locked months reject voucher/order edits (400).
- **F() atomic**: Stock changes are race-safe; concurrent calls are OK.
- **VAT auto-compute**: OrderItem on save branches VAT by `tax_type` (zero-rate/exempt → VAT 0).
- **History**: All changes auto-tracked via simple_history; no separate audit endpoint.

## 8. Known Constraints

- Per-ViewSet permissions vary; some require `ManagerRequired`. Use Swagger schema or 403 response to detect.
- No bulk create on default ViewSet POST. Loop or use management command for bulk.
- Search uses SQL ILIKE; no Korean morpheme analysis.
- Encrypted fields (Partner.phone/email/address) auto-decrypt in responses — apply permissions carefully.

## 9. References

- DRF: https://www.django-rest-framework.org/
- SimpleJWT: https://django-rest-framework-simplejwt.readthedocs.io/
- drf-spectacular: https://drf-spectacular.readthedocs.io/
- Project OpenAPI schema: download from `/api/schema/` and import into Postman/Insomnia.
