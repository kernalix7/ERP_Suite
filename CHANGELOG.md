# Changelog

**English** | [한국어](docs/CHANGELOG.ko.md)

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 22 Django apps (inventory, production, sales, purchase, service, accounting, investment, marketplace, inquiry, warranty, advertising, hr, attendance, board, calendar_app, messenger, core, accounts, ad, advertising, approval, asset, api)
- 107+ models with django-simple-history audit trail
- 420+ views with RBAC (admin/manager/staff) access control
- 250+ responsive HTML templates (Tailwind CSS + HTMX + Alpine.js)
- REST API with 28 ViewSets and JWT authentication (SimpleJWT)
- Real-time messaging via Django Channels + WebSocket
- Celery async task processing with Redis broker
- Docker Compose deployment (7 containers: web, db, redis, celery_worker, celery_beat, prometheus, grafana)
- GitHub Actions CI pipeline (test + lint + docker build)
- 988+ tests (unit + verification) covering security, integrity, performance, workflow, DR
- E2E tests (Playwright) and load tests (Locust)
- Korean/English i18n support
- PWA manifest and service worker

### Fixed
- Atomic stock/amount integrity via F() expressions (race-condition safe)
- Multi-step approval workflow chain consistency
