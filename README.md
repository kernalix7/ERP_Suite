# ERP Suite

Manufacturing & Sales Integrated ERP + Groupware System for SMEs

> [Korean version (한국어)](README_ko.md)

## Key Features

### ERP Modules

| Module | Description |
|--------|-------------|
| **Inventory** | Products (raw/semi/finished), warehouses, stock movements, inter-warehouse transfers, barcode/QR scanning, safety stock alerts |
| **Production** | BOM management, production planning, work orders, production records with auto stock adjustments |
| **Sales** | Partners, customers, orders, quotes (with one-click order conversion), shipment tracking, commission management |
| **Purchase** | Purchase orders, receiving confirmation, auto inventory-in on receipt, PO status tracking |
| **Service** | Service requests, repair history tracking, warranty period verification |
| **Accounting** | Tax invoices, VAT summaries, fixed costs, break-even analysis, monthly P&L, vouchers, account codes, withholding tax, multi-step approval workflow |
| **Investment** | Investors, funding rounds, equity tracking (donut charts), dividend/distribution records |
| **Marketplace** | Naver/Coupang store integration, order sync, sync history |
| **Inquiry** | Multi-channel inquiry management, Claude AI auto-reply drafts, reply templates |
| **Warranty** | Serial number authentication, warranty period management, QR verification |
| **Advertising** | Ad platforms (Google/Naver/Kakao/Meta), campaigns, creatives, performance tracking (ROAS/CTR/CPC), budget management |

### Groupware Modules

| Module | Description |
|--------|-------------|
| **HR** | Departments, positions, employee profiles, personnel actions, org chart |
| **Attendance** | Check-in/out records, leave requests/approvals, annual leave balance |
| **Board** | Notice/free boards, posts, comments (nested replies) |
| **Calendar** | Schedule management with FullCalendar.js, AJAX API |
| **Messenger** | Internal messaging (1:1 and group chat), real-time WebSocket |

### System Modules

| Module | Description |
|--------|-------------|
| **Core** | Dashboard, notifications, Excel/PDF export, barcode generation, backup/restore, audit trail, access logs |
| **Accounts** | Authentication, RBAC (admin/manager/staff), login protection (django-axes) |
| **API** | REST API (DRF ViewSets), JWT authentication (SimpleJWT) |
| **Active Directory** | LDAP/AD integration, user/group sync, group policy-based role mapping |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 5.x / Python 3.13 |
| Frontend | Django Templates + Tailwind CSS (CDN) + HTMX + Alpine.js + Chart.js + FullCalendar.js |
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

# Configure environment
mkdir -p local
cp .env.example local/.env
# Edit local/.env and set SECRET_KEY

# Run migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Set admin role
python manage.py shell -c "
from apps.accounts.models import User
u = User.objects.get(username='admin')
u.role = 'admin'; u.name = 'Admin'; u.save()
"

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
│   └── api/             # REST API (DRF ViewSets, JWT auth)
├── config/              # Django settings (base/dev/prod), celery, asgi, wsgi
├── templates/           # 190+ HTML templates (Tailwind CSS, responsive)
├── static/              # CSS, JS, PWA (manifest.json, sw.js)
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
# Unit tests (440+ tests across all apps)
python manage.py test apps/ -v 2

# Verification tests (security/integrity/performance/workflow/disaster recovery)
python manage.py test tests.verification -v 2

# E2E tests (Playwright)
cd e2e && pytest -v

# Load tests (Locust)
cd loadtest && locust -f locustfile.py --host http://localhost:8000
```

**Test coverage: 440+ tests (unit + verification)**

Verification criteria cover 82+ items across 7 categories:
- SEC-001~020: Security (OWASP Top 10)
- INT-001~015: Data integrity
- PERF-001~007: Performance
- FUNC-001~015: Functional workflows
- AD-001~010: Active Directory integration
- DR-001~007: Disaster recovery
- DEPLOY-001~005: Deployment/integration

## Key Data Flows

- **Stock Management**: `StockMovement` signals use `F()` expressions for atomic `Product.current_stock` updates (race-condition safe)
- **Order Fulfillment**: Order shipped (SHIPPED) → auto stock OUT via signal
- **Production**: Production record → auto finished goods IN + raw materials OUT (transactional)
- **Purchasing**: Receipt confirmation → auto stock IN + PO status transition
- **Quotes**: One-click quote-to-order conversion (items auto-copied)
- **Tax**: `OrderItem.save()` → auto 10% VAT calculation
- **Approvals**: Multi-step approval workflow (draft → level 1 → level 2 → ... → final)
- **AR/AP**: Payment registration → auto balance recalculation

## Security

- RBAC: `AdminRequiredMixin` (user mgmt, backups), `ManagerRequiredMixin` (accounting, investment, HR)
- Login protection: django-axes (5 failures → 1 hour lockout)
- API: JWT Bearer tokens (1 hour expiry) + session dual auth
- Stock updates: `F()` expressions to prevent race conditions
- File uploads: extension whitelist + 10MB size limit
- Production: HSTS, SSL redirect, HttpOnly cookies, 8-hour session expiry
- Audit trail: django-simple-history on all models
- Access logs: `AccessLogMiddleware` (user/path/response time)
- Monitoring: Prometheus metrics + Sentry error tracking

## Scale

- **20 apps**, **82+ models** (all with history tracking)
- **265+ views**, **190+ templates**, **270+ URL endpoints**
- **~17,000 lines** of Python (excluding migrations)
- **440+ tests** (unit + verification)
- **90+ migrations**, **25 packages**

## License

Apache 2.0
