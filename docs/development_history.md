# ERP Suite Development History & Session Summary

> Date: 2026-03-16
> Purpose: Full development context and prompt history for local environment migration

---

## 1. Project Background

**Product**: Manufacturing/sales device for freediving equalization practice
**Goal**: Build an in-house ERP covering production management, inventory management, after-sales service, sales management, and accounting
**Tech Stack**: Django 5.x + Tailwind CSS + HTMX + Alpine.js + SQLite (dev) / PostgreSQL (prod)
**Deployment**: Docker Compose (home server)

---

## 2. Development History by Session

### Session 1 — Initial Project Structure Design

**Key Prompts:**
```
프리다이빙 이퀄라이징 연습용 디바이스를 만들었어. 이걸 판매할거야.
그래서 제품의 생산 관리 입출고 AS 등에 대해서 프로그램으로 관리하려 하거든?

github에 올라가는거라 테스트용 데이터 등 보안상 민감한 사항은
별도 폴더를 만들어서 저장해.
```
<!-- English: "I made a freediving equalization practice device. I'm going to sell it. I want to manage production, inventory, and after-sales service through a program. Since it's going on GitHub, store sensitive data like test data in a separate folder." -->

**What was built:**
- Overall project structure design
- `local/` folder (gitignored) — separated `.env`, `db.sqlite3`, `erp.log`
- `config/settings/` — split into base/development/production
- `.env.example` created
- `.gitignore` created
- `CLAUDE.md` created (development rules)
- `Dockerfile` + `docker-compose.yml` created

**Key Decisions:**
- Sensitive files separated into `local/` folder (gitignored)
- Environment variable management via `django-environ`
- Common fields unified through `BaseModel` abstract model

---

### Session 2 — Full Implementation of 11 Apps (v1)

**Key Prompts:**
```
음 좀 더 잘 만들어봐 손익분기점도 만들고 세금 처리도 편하게
```
<!-- English: "Make it better. Add break-even point analysis and make tax handling easier." -->

**Implementation (5 parallel agents):**

| Agent | Apps Built | Key Features |
|-------|-----------|-------------|
| core+accounts | `core`, `accounts` | BaseModel, RBAC, login, dashboard |
| inventory | `inventory` | Products, categories, warehouses, stock movements, stock status, barcodes |
| production | `production` | BOM, production plans, work orders, production records |
| sales+service | `sales`, `service` | Partners, customers, orders (VAT), service requests, repair history |
| accounting+investment | `accounting`, `investment` | Tax invoices, VAT, BEP, P&L, vouchers, investors, equity |

**Key Models (40):**
```
inventory: Product, Category, Warehouse, StockMovement, StockTransfer
production: BOM, BOMItem, ProductionPlan, WorkOrder, ProductionRecord
sales: Partner, Customer, Order, OrderItem, CommissionRate, CommissionRecord
service: ServiceRequest, RepairRecord
accounting: TaxRate, TaxInvoice, TaxInvoiceItem, FixedCost, WithholdingTax,
            AccountCode, Voucher, VoucherLine, ApprovalRequest
investment: Investor, InvestmentRound, Investment, EquityChange, Distribution
warranty: ProductRegistration
marketplace: MarketplaceConfig, MarketplaceOrder, SyncLog
inquiry: InquiryChannel, Inquiry, InquiryReply, ReplyTemplate
core: Notification, Attachment
```

---

### Session 3 — Security Audit & Vulnerability Fixes

**Key Prompts:**
```
더 할 부분 없나
보안상 취약점찾아봐
좀 더 찾아서 개선해봐
```
<!-- English: "Anything else to do? Find security vulnerabilities. Find more and improve." -->

**Fixes Applied:**
- Fixed 8 template variable name mismatches (e.g., product_name -> product.name)
- Added `total_repair_cost` context to `ServiceRequestDetailView`
- Verified F() expression usage for stock updates (race condition prevention)
- Verified `created_by` auto-save middleware

---

### Session 4 — Additional Feature Implementation (v2)

**Key Prompts:**
```
모두 다 진행해
```
<!-- English: "Proceed with everything." -->

**What was built:**
- `apps/sales/commission.py` — CommissionRate, CommissionRecord models
- `apps/core/backup.py` — JSON backup/download (AdminRequiredMixin)
- `apps/accounting/` — AccountCode, Voucher, VoucherLine models + views added
- `apps/smartstore/` -> `apps/marketplace/` renamed (generalized)
- `apps/warranty/` — ProductRegistration, serial number verification
- `apps/inquiry/` — Inquiry, InquiryReply, LLM (Claude) auto-reply
- `apps/core/trash.py` — Soft-deleted item trash can / restore
- `apps/core/attachment.py` — Evidence attachments (GenericForeignKey)
- `docs/` — 4 guides written (user, developer, API, deployment)
- `README.md` fully updated

---

### Session 5 — Full Inspection & Missing Items

**Key Prompts:**
```
없는데? 만들어놓고 안집어넣은거 있는지 점검해봐
```
<!-- English: "It's missing? Check if there's anything that was built but not wired in." -->

**Fixes Applied:**
- Checked sidebar for missing menus (compared all URLs vs sidebar entries)
- Found 3 missing commission menus (`commission_rate_list`, `commission_list`, `commission_summary`)
- Found missing account code (`accountcode_list`) and voucher (`voucher_list`) menus

---

### Session 6 — Comprehensive Audit System + Security Hardening + Reports (In Progress)

**Key Prompts:**
```
전체적으로 싹 다 분석해서 개선할 점 있는지 확인해봐
삭제된 항목 별도로 볼 수 있게 하자.
그리고 증빙 등 증적 관리도 하고

ERP로써 어느정도 구현이 되었는지 부족한건 뭔지 개선할 건 뭔지 알려줘
문서도 정리하고 보안기능도 충분한지 보고 보고서 한번 만들어봐.
그리고 감사는 따로 메뉴 만들고
```
<!-- English: "Analyze everything thoroughly and check for improvements. Let's make deleted items viewable separately. Also handle evidence/audit trail management. Tell me how complete the ERP is, what's missing, and what to improve. Organize docs, check security, and create a report. Make a separate menu for auditing." -->

**In Progress:**
- Audit trail system (`/audit/`, `/audit/log/`, `/audit/logins/`)
- Security middleware (`SecurityHeadersMiddleware`, `RequestLoggingMiddleware`)
- Notification system views/templates (`/notifications/`)
- Added all missing sidebar menus
- Comprehensive report writing

---

## 3. Local Environment Migration Guide

### 3-1. Prerequisites

```
Python 3.13+
Git
(Optional) Docker Desktop
```

### 3-2. Clone & Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/ERP_Suite.git
cd ERP_Suite

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
venv\Scripts\activate             # Windows

# 3. Install packages
pip install -r requirements/dev.txt

# 4. Configure environment variables
mkdir -p local
cp .env.example local/.env
# Open local/.env and change the SECRET_KEY value (required!)
# SECRET_KEY=django-insecure-your-random-50-char-key-here

# 5. How to generate a SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 6. Create DB and run migrations
python manage.py migrate

# 7. Create admin account
python manage.py createsuperuser
# username: admin
# email: admin@yourdomain.com
# password: (8+ characters, alphanumeric)

# 8. Set account role
python manage.py shell
>>> from apps.accounts.models import User
>>> u = User.objects.get(username='admin')
>>> u.role = 'admin'
>>> u.name = '관리자'
>>> u.save()
>>> exit()

# 9. Start development server
python manage.py runserver 0.0.0.0:8000
# Browser: http://localhost:8000
```

### 3-3. Running with Docker Compose (Production)

```bash
# Prepare .env file (separate file in project root)
cat > .env << 'EOF'
SECRET_KEY=your-production-secret-key-here
DB_PASSWORD=strong-db-password-here
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
EOF

# Start services
docker compose up -d

# Initial migration
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser

# Check logs
docker compose logs -f web
```

### 3-4. Claude API Setup (LLM Auto-Reply Feature)

Add to `local/.env`:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Available via the "AI Reply Generation" button in Inquiry Management -> Inquiry Detail.

---

## 4. Current Project Structure (Final)

```
ERP_Suite/
├── .env.example              # Environment variable template
├── .gitignore                # Excludes local/, __pycache__, .env, etc.
├── CLAUDE.md                 # AI development guidelines
├── README.md                 # Project introduction
├── Dockerfile                # Docker image
├── docker-compose.yml        # Service orchestration
├── manage.py
├── requirements/
│   ├── base.txt              # Django, common packages
│   ├── dev.txt               # + debug-toolbar
│   └── prod.txt              # + gunicorn, psycopg2
├── config/
│   ├── settings/
│   │   ├── base.py           # Common settings
│   │   ├── development.py    # Dev settings (DEBUG=True, SQLite)
│   │   └── production.py     # Prod settings (security headers, PostgreSQL)
│   ├── urls.py               # Root URL configuration
│   └── wsgi.py
├── apps/
│   ├── core/                 # BaseModel, notifications, backup, trash, attachments, audit
│   ├── accounts/             # Users, roles (admin/manager/staff)
│   ├── inventory/            # Products, categories, warehouses, stock movements, inventory
│   ├── production/           # BOM, production plans, work orders, production records
│   ├── sales/                # Partners, customers, orders, commissions
│   ├── service/              # Service requests, repair history
│   ├── accounting/           # Tax invoices, VAT, break-even point, vouchers
│   ├── investment/           # Investors, rounds, equity, dividends
│   ├── warranty/             # Product registration, serial number verification
│   ├── marketplace/          # External store integration (Naver/Coupang, etc.)
│   └── inquiry/              # Inquiry management, LLM auto-reply
├── templates/
│   ├── base.html             # Common layout (sidebar, header)
│   ├── accounts/             # Login, user management (3)
│   ├── core/                 # Dashboard, backup, trash, attachments, audit, notifications (9)
│   ├── inventory/            # Products, warehouses, stock movements, etc. (12)
│   ├── production/           # BOM, production plans, etc. (11)
│   ├── sales/                # Partners, customers, orders, commissions (13)
│   ├── service/              # Service, repairs (4)
│   ├── accounting/           # Tax invoices, vouchers, etc. (13)
│   ├── investment/           # Investors, equity, etc. (11)
│   ├── warranty/             # Product registration (3)
│   ├── marketplace/          # External stores (5)
│   └── inquiry/              # Inquiry management (6)
├── docs/
│   ├── 사용자_가이드.md
│   ├── 개발자_가이드.md
│   ├── API_레퍼런스.md
│   ├── 배포_가이드.md
│   └── development_history.md  ← This file
└── local/                    # gitignored — sensitive files
    ├── .env                  # Environment variables (create manually)
    ├── db.sqlite3            # Dev DB (created after migrate)
    └── erp.log               # Logs (created after server start)
```

---

## 5. Key URL List

| Path | Description |
|------|-------------|
| `/` | Dashboard |
| `/accounts/login/` | Login |
| `/inventory/products/` | Product list |
| `/inventory/stock/` | Stock status |
| `/production/bom/` | BOM list |
| `/production/plans/` | Production plans |
| `/sales/orders/` | Order list |
| `/sales/commissions/` | Commission records |
| `/service/requests/` | Service requests |
| `/accounting/` | Financial dashboard |
| `/accounting/breakeven/` | Break-even point |
| `/accounting/monthly-pl/` | Monthly P&L |
| `/accounting/vouchers/` | Vouchers |
| `/investment/` | Investment dashboard |
| `/warranty/` | Product registration |
| `/marketplace/` | External stores |
| `/inquiry/` | Inquiry management |
| `/audit/` | Audit dashboard |
| `/audit/log/` | Audit log |
| `/audit/logins/` | Login history |
| `/trash/` | Trash (soft-deleted items) |
| `/attachments/` | Evidence/attachment management |
| `/backup/` | Backup |
| `/mgmt-console-x/` | Django Admin |

---

## 6. Role-Based Access Control

| Role | Description | Accessible Menus |
|------|-------------|-----------------|
| `admin` | System administrator | All + user management + backup |
| `manager` | Department manager | All (except user management and backup) |
| `staff` | General staff | Inventory, production, sales, service |

---

## 7. Security Configuration

| Item | Details |
|------|---------|
| Login protection | django-axes (5 failed attempts -> 1-hour lockout) |
| RBAC | AdminRequiredMixin, ManagerRequiredMixin |
| Stock concurrency | F() expressions (race condition prevention) |
| File upload | Extension whitelist + 10MB limit |
| Soft delete | is_active=False (no physical deletion) |
| Change history | simple_history (all 82+ models) |
| Production security | HSTS, SSL Redirect, HttpOnly cookies |
| Audit trail | /audit/ — unified change history across all models |
| Request logging | Automatic logging of sensitive path access |

---

## 8. Future Improvement Tasks (By Priority)

### High (Feature Completeness)
1. **Real API Integration** — Naver Commerce API (Smart Store), Coupang Partners API
2. **Barcode/QR Scanning** — Barcode scanner support for stock movements
3. **Excel Import** — Bulk upload for products/orders/inventory
4. **PDF Export** — Tax invoices, transaction statements, delivery notes

### Medium (UX Improvements)
5. **Enhanced Dashboard KPIs** — Real-time stock alerts, approaching deadline alerts
6. **Mobile Responsive** — Currently desktop-focused, needs mobile optimization
7. **Dark Mode** — Apply Tailwind CSS dark: classes
8. **Enhanced Search** — Global search functionality

### Low (Extensions)
9. **Multi-Location** — Separate inventory/production management per branch
10. **REST API** — DRF API for external integrations
11. **PWA** — Offline support

---

## 9. Common Management Commands

```bash
# Start development server
python manage.py runserver 0.0.0.0:8000

# Migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Django shell
python manage.py shell

# Collect static files (production)
python manage.py collectstatic

# Run tests
python manage.py test

# Reset DB (during development)
rm local/db.sqlite3
python manage.py migrate
DJANGO_SUPERUSER_PASSWORD=admin123 python manage.py createsuperuser --username admin --email admin@example.com --noinput
python manage.py shell -c "from apps.accounts.models import User; u=User.objects.get(username='admin'); u.name='관리자'; u.role='admin'; u.save()"
```

---

## 10. Known Issues & TODO

| Item | Status | Details |
|------|--------|---------|
| Audit menu | In progress | /audit/ path, sidebar integration in progress |
| Notification read status | In progress | Top bar bell icon notification count integration |
| Marketplace API | Not implemented | Real Naver/Coupang API integration needed |
| PDF export | Not implemented | Need to adopt reportlab or weasyprint |
| Excel import | Not implemented | Use django-import-export |
| Unit tests | Not written | Need test code for core models/views |
