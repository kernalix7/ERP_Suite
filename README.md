# ERP Suite

Manufacturing & Sales Integrated ERP + Groupware System for SMEs

**English** | [한국어](docs/README.ko.md)

## Key Features

### ERP Modules

| Module | Description |
|--------|-------------|
| **Inventory** | Products (raw/semi/finished), warehouses, stock movements, inter-warehouse transfers, barcode/QR scanning, safety stock alerts, reorder point monitoring, StockLot (FIFO/LIFO inventory valuation), WarehouseStock (per-warehouse stock), reserved stock management, SerialNumber tracking (per-product opt-in, auto-generation on production, FIFO shipment assignment) |
| **Production** | BOM management (multi-level Sub-assembly explosion), production planning, work orders, production records with auto stock adjustments, scrap quantity tracking, MRP (Material Requirements Planning with reorder point), StandardCost (standard costing), QualityInspection (quality control with conditional approval workflow), WorkCenter (capacity planning), ProductionSchedule (scheduling with Gantt data), CostVariance (actual vs standard cost analysis) |
| **Sales** | Partners, customers, orders (with CONFIRMED order modification), quotes (with one-click order conversion, PriceRule auto-application), return/exchange order workflows, ShipmentItem (partial shipments with serial range tracking, auto PARTIAL_SHIPPED status), ShippingCarrier (carriers), ShipmentTracking (delivery tracking), PriceRule (min quantity enforcement), commission management, partner analytics, CustomerTier (customer grading), SalesTarget (quota tracking), SalesLead (CRM pipeline), CustomerSatisfaction (NPS tracking), credit limit management |
| **Purchase** | Purchase orders, receiving confirmation, auto inventory-in on receipt, PO status tracking, reverse cascade on PO cancellation, RFQ (Request for Quotation with response comparison and PO conversion), VendorScore (supplier evaluation scoring) |
| **Service** | Service requests, repair history tracking, warranty period verification (serial-based auto-verification), paid repair auto-AR generation, cancellation with AR reversal |
| **Accounting** | Tax invoices, VAT summaries (VAT return report), fixed costs, break-even analysis, monthly P&L, balance sheet, cash flow statement (with account classification), vouchers, account codes, withholding tax, ClosingPeriod (period closing), Budget (budget management with overspend warnings), Currency/ExchangeRate (multi-currency), exchange gain/loss reporting, AR/AP Aging (auto-overdue transition, aged trial balance), bank reconciliation, settlements (auto-voucher for shipping/platform fees), CostCenter/ProfitCenter (departmental P&L), DashboardWidget (customizable), advanced reports (YoY/MoM comparison, product profitability) |
| **Investment** | Investors, funding rounds, equity tracking (donut charts), dividend/distribution records |
| **Asset** | Fixed asset management (with acquisition validation), depreciation (straight-line / declining balance), asset transfers, certifications (KC/CE/FCC/ISO/RoHS), lease contracts (operating/finance), asset audits, barcode/QR tag generation |
| **Marketplace** | Naver/Coupang store integration, order sync (bidirectional — ERP→marketplace shipping status push), 6-stage Import Wizard, settlement reconciliation (auto-matching), sync history |
| **Inquiry** | Multi-channel inquiry management, Claude AI auto-reply drafts, reply templates |
| **Warranty** | Serial number authentication, warranty period management, QR verification |
| **Approval** | Multi-step approval workflows, document categories (purchase/expense/budget/contract/leave/travel/IT), per-step approvers, file attachments |
| **Advertising** | Ad platforms (Google/Naver/Kakao/Meta), campaigns, creatives, performance tracking (ROAS/CTR/CPC), budget management |

### Groupware Modules

| Module | Description |
|--------|-------------|
| **HR** | Departments, positions, employee profiles, personnel actions, org chart, Payroll (payroll management), PayrollConfig (4 major insurance settings), SeverancePay (retirement pay calculation), YearEndSettlement (year-end tax settlement), LaborConfig (labor law compliance: overtime limits, minimum wage, annual leave), weekly compliance checks |
| **Attendance** | Check-in/out records, leave requests/approvals, annual leave balance |
| **Board** | Notice/free boards, posts, comments (nested replies) |
| **Calendar** | Schedule management with FullCalendar.js, AJAX API |
| **Messenger** | Internal messaging (1:1 and group chat), real-time WebSocket |

### System Modules

| Module | Description |
|--------|-------------|
| **Core** | Dashboard (KPI widgets, asset/certification/lease summaries), real-time notifications (WebSocket push), Excel/PDF export, barcode generation, backup/restore, audit trail, access logs |
| **Accounts** | Authentication, RBAC (admin/manager/staff), login protection (django-axes) |
| **API** | REST API (34 DRF ViewSets), JWT authentication (SimpleJWT), OpenAPI/Swagger docs |
| **Module Manager** | Pluggable module architecture (enable/disable features per installation), category-based organization (Compliance/Production/Purchase/Sales/Accounting/HR/System), country-code filtering (KR/US/universal), dependency checking, admin toggle UI, 30 registered modules |
| **Store Modules** | Modular store architecture (pluggable per-channel modules: Naver SmartStore, Coupang, direct sales) |
| **Active Directory** | LDAP/AD integration, user/group sync, group policy-based role mapping |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 5.x / Python 3.13 |
| Frontend | Django Templates + Tailwind CSS (local build) + HTMX + Alpine.js + Chart.js + FullCalendar.js (all served from static/vendor/) |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| Real-time | Django Channels + WebSocket (Daphne ASGI) |
| Async Tasks | Celery + Redis (task queue, scheduled backups, certification expiry alerts, lease voucher auto-generation, monthly depreciation, quotation expiry, safety stock alerts, reorder point monitoring, overdue PO alerts, AR overdue transition) |
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
│   ├── asset/           # Fixed assets, depreciation, transfers, certifications, leases, audits, barcode/QR
│   ├── approval/        # Standalone approval workflows
│   ├── store_modules/   # Modular store architecture (pluggable per-channel)
│   ├── modules/         # Channel modules (Naver SmartStore, Coupang, direct sales)
│   ├── module_manager/  # Feature module registry, enable/disable, country-based filtering
│   └── api/             # REST API (34 DRF ViewSets, JWT auth)
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
# Unit tests (1000+ tests across all apps, --parallel for speed)
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

**Test coverage: 1162+ tests (unit)**

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
- **Asset Transfer**: Asset transfer → department/location/person updated, transfer history tracked
- **Depreciation**: Monthly batch depreciation run → `F()` atomic book value updates
- **Lease Contracts**: `LeaseContract.save()` → auto total_amount calculation (monthly_payment x months)
- **Settlement Reconciliation**: Marketplace settlements auto-matched with orders (amount/date/channel)
- **Financial Statements**: P&L + balance sheet + cash flow statement generation from voucher data
- **Serial Tracking**: Production record → auto serial generation (opt-in per product) → shipment FIFO assignment → serial range per shipment
- **Return Orders**: Return order CONFIRMED → AR refund + SHIPPED → RETURN stock movement (inventory restored)
- **Exchange Orders**: Exchange order → return inbound + new outbound + price difference settlement
- **Order Modification**: CONFIRMED order → qty/price change → reserved_stock + AR + tax invoice auto-recalculation
- **Service AR**: Paid repair COMPLETED → AR auto-creation; service CANCELLED → AR soft delete
- **Budget Warning**: VoucherLine saved → budget overspend check → warning notification
- **Exchange Gain/Loss**: Foreign currency AR/AP → exchange rate variance calculation at closing
- **Safety Stock**: Daily batch → products below safety_stock → notification alerts
- **Marketplace Push**: Shipment SHIPPED → auto push tracking info to Naver/Coupang APIs
- **Partial Shipment**: ShipmentItem created → auto PARTIAL_SHIPPED/SHIPPED status transition based on shipped vs total quantities
- **Settlement Voucher**: SalesSettlement confirmed → auto voucher for shipping costs + platform commissions (double-entry)
- **Warranty Verification**: Service request with serial → auto ProductRegistration lookup → warranty status auto-set
- **Asset Validation**: FixedAsset creation → acquisition cost/residual value/useful life validation, category defaults
- **Price Rules**: OrderItem/QuotationItem save → PriceRule auto-application with min quantity enforcement
- **Conditional QC**: QualityInspection CONDITIONAL → manager notification → approve (→PASS) or reject (→FAIL)
- **Reorder Point**: Daily batch → products below reorder_point → notification alerts + MRP suggested order qty

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

- **25 apps**, **140+ models** (all with history tracking)
- **450+ views**, **260+ templates**, **380+ URL endpoints**
- **~35,000 lines** of Python (excluding migrations)
- **1162+ tests** (unit), **17 E2E test files**, **load test suite**
- **130+ migrations**, **25+ packages**
- **34 REST API ViewSets** with JWT authentication

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and workflow.

## Security

For security issues, follow the process in [SECURITY.md](SECURITY.md).

## License

Proprietary
