# ERP Suite

Manufacturing & Sales Integrated ERP + Groupware System for SMEs

**English** | [한국어](docs/README.ko.md)

## Key Features

### ERP Modules

| Module | Description |
|--------|-------------|
| **Inventory** | Products (raw/semi/finished), warehouses, stock movements, inter-warehouse transfers, barcode/QR scanning, safety stock alerts, StockLot (FIFO/LIFO inventory valuation), WarehouseStock (per-warehouse stock), reserved stock management |
| **Production** | BOM management, production planning, work orders, production records with auto stock adjustments, MRP (Material Requirements Planning), StandardCost (standard costing), QualityInspection (quality control) |
| **Sales** | Partners, customers, orders, quotes (with one-click order conversion), ShipmentItem (partial shipments), ShippingCarrier (carriers), ShipmentTracking (delivery tracking), commission management, partner analytics |
| **Purchase** | Purchase orders, receiving confirmation, auto inventory-in on receipt, PO status tracking, reverse cascade on PO cancellation |
| **Service** | Service requests, repair history tracking, warranty period verification |
| **Accounting** | Tax invoices, VAT summaries, fixed costs, break-even analysis, monthly P&L, vouchers, account codes, withholding tax, ClosingPeriod (period closing), Budget (budget management), Currency/ExchangeRate (multi-currency), AR/AP Aging, bank reconciliation, settlements |
| **Investment** | Investors, funding rounds, equity tracking (donut charts), dividend/distribution records |
| **Asset** | Fixed asset management, depreciation (straight-line / declining balance methods) |
| **Marketplace** | Naver/Coupang store integration, order sync, sync history |
| **Inquiry** | Multi-channel inquiry management, Claude AI auto-reply drafts, reply templates |
| **Warranty** | Serial number authentication, warranty period management, QR verification |
| **Approval** | Multi-step approval workflows, document categories (purchase/expense/budget/contract/leave/travel/IT), per-step approvers, file attachments |
| **Advertising** | Ad platforms (Google/Naver/Kakao/Meta), campaigns, creatives, performance tracking (ROAS/CTR/CPC), budget management |

### Groupware Modules

| Module | Description |
|--------|-------------|
| **HR** | Departments, positions, employee profiles, personnel actions, org chart, Payroll (payroll management), PayrollConfig (4 major insurance settings) |
| **Attendance** | Check-in/out records, leave requests/approvals, annual leave balance |
| **Board** | Notice/free boards, posts, comments (nested replies) |
| **Calendar** | Schedule management with FullCalendar.js, AJAX API |
| **Messenger** | Internal messaging (1:1 and group chat), real-time WebSocket |

### System Modules

| Module | Description |
|--------|-------------|
| **Core** | Dashboard, notifications, Excel/PDF export, barcode generation, backup/restore, audit trail, access logs |
| **Accounts** | Authentication, RBAC (admin/manager/staff), login protection (django-axes) |
| **API** | REST API (28 DRF ViewSets), JWT authentication (SimpleJWT), OpenAPI/Swagger docs |
| **Active Directory** | LDAP/AD integration, user/group sync, group policy-based role mapping |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 5.x / Python 3.13 |
| Frontend | Django Templates + Tailwind CSS (local build) + HTMX + Alpine.js + Chart.js + FullCalendar.js (all served from static/vendor/) |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| Real-time | Django Channels + WebSocket (Daphne ASGI) |
| Async Tasks | Celery + Redis (task queue, scheduled backups) |
| Caching | Redis (django-redis) |
| API | Django REST Framework + JWT (SimpleJWT) |
| Security | django-axes (login throttling), RBAC, HSTS/CSP, django-prometheus |
| Monitoring | Prometheus + Grafana + Sentry |
| Deployment | Docker Compose (7 containers) |
| CI/CD | GitHub Actions |
| i18n | Korean / English (django i18n) |
| History | django-simple-history (all models) |

## Quick Start

### Prerequisites
- Python 3.13+
- pip

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/ERP_Suite.git
cd ERP_Suite

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements/base.txt

# Download frontend vendor libraries (local build)
bash scripts/download_vendor.sh

# Configure environment
mkdir -p local
cp .env.example local/.env
# Edit local/.env and set SECRET_KEY

# Run migrations
python manage.py migrate

# Option A: Production — admin account only (ID: admin / PW: Admin12#)
python manage.py init_prod

# Option B: Sandbox — demo data with sample users/products/orders
python manage.py seed_data

# Compile translations
python manage.py compilemessages

# Start development server
python manage.py runserver 0.0.0.0:8000
```

Open http://localhost:8000 in your browser.

### Docker Deployment

```bash
# Set environment variables
export DB_PASSWORD=your-secure-password
export SECRET_KEY=your-secret-key
export ALLOWED_HOSTS=your-domain.com

# Build and start all services
docker-compose up -d
```

**Docker services (7 containers):**

| Service | Port | Description |
|---------|------|-------------|
| web | 8000 | Django app (Daphne ASGI) |
| db | 5432 | PostgreSQL 16 |
| redis | 6379 | Cache + message broker |
| celery_worker | - | Async task processing |
| celery_beat | - | Periodic task scheduler |
| prometheus | 9090 | Metrics collection |
| grafana | 3000 | Monitoring dashboards |

## Project Structure

```
ERP_Suite/
├── apps/
│   ├── core/            # Common: BaseModel, notifications, Excel/PDF, barcode, backup, dashboard, audit
│   ├── accounts/        # Authentication, RBAC (admin/manager/staff)
│   ├── inventory/       # Products, categories, warehouses, stock movements, transfers, barcode/QR
│   ├── production/      # BOM, production plans, work orders, production records
│   ├── sales/           # Partners, customers, orders, quotes, shipments, commissions
│   ├── purchase/        # Purchase orders, receiving, auto inventory integration
│   ├── service/         # Service requests, repair history
│   ├── accounting/      # Tax invoices, VAT, fixed costs, break-even, P&L, vouchers, approvals
│   ├── investment/      # Investors, rounds, equity, dividends
│   ├── marketplace/     # Naver/Coupang store integration, order sync
│   ├── inquiry/         # Inquiry management, Claude AI auto-reply, templates
│   ├── warranty/        # Serial number authentication, warranty verification
│   ├── hr/              # Departments, positions, employee profiles, personnel actions, org chart
│   ├── attendance/      # Check-in/out, leave requests, annual leave balance
│   ├── board/           # Notice/free boards, posts, comments
│   ├── calendar_app/    # Schedule management (FullCalendar.js, AJAX API)
│   ├── messenger/       # Internal chat (1:1/group, WebSocket real-time)
│   ├── ad/              # Active Directory / LDAP integration
│   ├── advertising/     # Ad campaign/creative management, performance tracking, budgets
│   ├── asset/           # Fixed asset management, depreciation (straight-line/declining balance)
│   ├── approval/        # Standalone approval workflows
│   └── api/             # REST API (28 DRF ViewSets, JWT auth)
├── config/              # Django settings (base/dev/prod), celery, asgi, wsgi
├── templates/           # 250+ HTML templates (Tailwind CSS, responsive)
├── static/              # CSS, JS, PWA (manifest.json, sw.js)
│   └── vendor/          # Local vendor libraries (Tailwind, HTMX, Alpine.js, Chart.js, FullCalendar.js)
├── scripts/             # Utility scripts (download_vendor.sh, etc.)
├── tests/verification/  # Verification tests (security/integrity/performance/workflow/DR)
├── e2e/                 # Playwright E2E tests
├── loadtest/            # Locust load tests
├── monitoring/          # Prometheus & Grafana configs
├── docs/                # Verification criteria, guides
├── locale/              # i18n translations (ko, en)
├── local/               # Git-ignored: .env, db.sqlite3, logs, backups
├── requirements/        # pip dependencies (base.txt, dev.txt, prod.txt)
├── docker-compose.yml   # Docker Compose (7 services)
├── Dockerfile           # Docker image build
└── manage.py            # Django management commands
```

## Testing

```bash
# Unit tests (878 tests across all apps, --parallel for speed)
python manage.py test apps/ -v 2 --parallel

# Verification tests (security/integrity/performance/workflow/disaster recovery)
python manage.py test tests.verification -v 2 --parallel

# All tests at once
python manage.py test apps/ tests.verification -v 0 --parallel

# E2E tests (Playwright)
cd e2e && pytest -v

# Load tests (Locust)
cd loadtest && locust -f locustfile.py --host http://localhost:8000
```

**Test coverage: 988+ tests (unit + verification)**

Verification criteria cover 152 items across 10 categories:
- SEC-001~035: Security (OWASP Top 10)
- INT-001~030: Data integrity
- PERF-001~015: Performance
- FUNC-001~030: Functional workflows
- AD-001~010: Active Directory integration
- DR-001~012: Disaster recovery
- DEPLOY-001~010: Deployment/integration
- COMPAT-001~005: Compatibility
- UX-001~005: User experience

## Key Data Flows

- **Stock Management**: `StockMovement` signals use `F()` expressions for atomic `Product.current_stock` updates (race-condition safe)
- **Order Confirmation**: Order CONFIRMED → reserved_stock reservation + AR auto-creation + tax invoice generation
- **Order Fulfillment**: Order shipped (SHIPPED) → auto stock OUT via signal
- **FIFO/LIFO**: StockLot auto-creation on receipt, auto-consumption on outbound (FIFO/LIFO valuation)
- **Production**: Production record → auto finished goods IN + raw materials OUT (transactional)
- **MRP**: MRP run → BOM explosion + auto purchase order generation for shortages
- **Production Cancellation**: ProductionPlan/WorkOrder CANCELLED → auto stock movement reversal
- **Purchasing**: Receipt confirmation → auto stock IN + PO status transition
- **Purchase Cancellation**: PurchaseOrder CANCELLED → AP/tax invoice soft delete (reverse cascade)
- **Quotes**: One-click quote-to-order conversion (items auto-copied)
- **Tax**: `OrderItem.save()` → auto 10% VAT calculation
- **Approvals**: Multi-step approval workflow (draft → level 1 → level 2 → ... → final)
- **AR/AP**: Payment registration → auto balance recalculation
- **Period Closing**: ClosingPeriod → blocks voucher modifications for the closed month
- **Payroll**: `Payroll.save()` → auto deductions for 4 major insurances and taxes

## Security

- RBAC: `AdminRequiredMixin` (user mgmt, backups), `ManagerRequiredMixin` (accounting, investment, HR)
- Login protection: django-axes (5 failures → 1 hour lockout)
- API: JWT Bearer tokens (1 hour expiry) + session dual auth
- Stock updates: `F()` expressions to prevent race conditions
- File uploads: extension whitelist + 10MB size limit
- Production: HSTS, SSL redirect, HttpOnly cookies, 8-hour session expiry
- CSP: `unsafe-eval` removed, strict Content Security Policy enforced
- OWASP: OWASP Top 10 audit passed
- Offline: 100% offline-capable (all vendor assets served locally)
- Audit trail: django-simple-history on all models, ISMS-level audit dashboard (access logs, data changes, login history, meta-audit)
- Access logs: `AccessLogMiddleware` (user/path/response time)
- Audit access control: `is_auditor` role-based access, all audit views logged (who viewed what)
- Monitoring: Prometheus metrics + Sentry error tracking

## Scale

- **22 apps**, **107+ models** (all with history tracking)
- **420+ views**, **250+ templates**, **350+ URL endpoints**
- **~30,000 lines** of Python (excluding migrations)
- **988+ tests** (unit + verification)
- **120+ migrations**, **25+ packages**

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and workflow.

## Security

For security issues, follow the process in [SECURITY.md](SECURITY.md).

## License

Proprietary
