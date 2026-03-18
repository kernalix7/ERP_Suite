# ERP Suite Production Deployment Verification Criteria

## 1. Document Overview

### 1.1 Purpose
This document defines the criteria for systematically verifying the stability, security, data integrity,
performance, and functional completeness of the ERP Suite system prior to production deployment.
Written in accordance with ISMS/ISO 27001, OWASP Top 10, and KISA Web Security Guide standards.

### 1.2 Scope
- **Target System**: ERP Suite (Django 5.x-based Manufacturing/Sales Integrated ERP + Groupware)
- **Target Apps**: core, accounts, inventory, production, sales, service, accounting, investment, warranty, marketplace, inquiry, purchase, attendance, board, calendar_app, hr, messenger, api
- **Target Environments**: Development (SQLite), Staging (PostgreSQL), Production (PostgreSQL + Docker)
- **Total Verification Items**: 152

### 1.3 Verification Schedule
| Category | Frequency | Notes |
|----------|-----------|-------|
| Security Verification (SEC) | Quarterly | Mandatory before every deployment |
| Data Integrity (INT) | Monthly | Mandatory before deployment |
| Performance Verification (PERF) | Quarterly | Ad-hoc for large data volumes |
| Functional Workflow (FUNC) | Every deployment | CI/CD pipeline integration |
| AD/LDAP Verification (AD) | Quarterly | After domain changes |
| Disaster Recovery (DR) | Semi-annually | Linked to DR drills |
| Deployment (DEPLOY) | Every deployment | Pre-release checklist |
| Compatibility (COMPAT) | Quarterly | After frontend changes |
| User Experience (UX) | Every deployment | Manual + automated checks |

### 1.4 Responsible Parties
| Role | Assigned To | Notes |
|------|-------------|-------|
| Verification Lead | System Admin (admin) | Final approval authority |
| Verification Executor | Development Team | Automated test execution |
| Result Reviewer | Manager (manager) | Result review and sign-off |
| Security Auditor | External/Internal | Penetration testing, OWASP review |
| UX Reviewer | QA Team | Usability and compatibility review |

### 1.5 Risk Classification
| Level | Description | Response SLA | Escalation Path |
|-------|-------------|--------------|-----------------|
| **Critical** | System compromise, data breach, complete service failure | Immediate (within 4 hours) | CTO + Security Team |
| **High** | Data integrity loss, authentication bypass, major feature failure | Within 24 hours | Tech Lead + DevOps |
| **Medium** | Performance degradation, minor security gap, partial feature issue | Within 1 week | Development Team |
| **Low** | Cosmetic issues, non-critical optimization, minor UX issues | Next release cycle | Product Owner |

---

## 2. Security Verification (SEC-001 ~ SEC-035)

### SEC-001: SQL Injection Defense

| Item | Details |
|------|---------|
| **ID** | SEC-001 |
| **Name** | SQL Injection Attack Prevention |
| **Criteria** | All DB access must use Django ORM or parameterized queries. When `raw()`, `extra()`, or `cursor.execute()` is used, parameter binding must be applied. No user input may be directly interpolated into SQL strings. |
| **Pass Conditions** | (1) Source code static analysis confirms zero string-formatted SQL. (2) Malicious input (`' OR 1=1 --`, `'; DROP TABLE--`, `UNION SELECT`) returns proper error responses. (3) No `raw()` or `extra()` calls found without parameter binding. (4) All search/filter views parameterize user input. (5) `semgrep` or `bandit` scan reports zero SQL injection findings. |
| **Fail Conditions** | (1) Any SQL query constructed via string formatting/concatenation with user-controlled input. (2) `raw()` or `extra()` used with f-string or `.format()` interpolation. (3) Search endpoint directly embeds query parameter into SQL. |
| **Method** | Automated - Static analysis (grep/semgrep/bandit) + Django TestCase with injection payloads |
| **Test Code** | `tests/verification/test_security.py::TestSQLInjection` |
| **Risk** | **Critical** |
| **OWASP Ref** | A03:2021 - Injection |

### SEC-002: XSS (Cross-Site Scripting) Defense

| Item | Details |
|------|---------|
| **ID** | SEC-002 |
| **Name** | XSS Attack Prevention |
| **Criteria** | Django template auto-escaping must be active. `|safe` filter or `{% autoescape off %}` usage requires documented justification and input validation. All user-generated content must be escaped on output. |
| **Pass Conditions** | (1) `|safe` usage count is 0 or each instance has validated/sanitized input. (2) `{% autoescape off %}` not used with user input. (3) `<script>alert('xss')</script>` input is rendered as escaped text in all user-input-accepting views. (4) CSP header prevents inline script execution. (5) Reflected XSS payloads in URL parameters are neutralized. |
| **Fail Conditions** | (1) User input rendered via `|safe` without sanitization. (2) Stored XSS possible via any form field. (3) DOM-based XSS via client-side JavaScript template rendering. |
| **Method** | Automated - Template static analysis + manual review + XSS payload injection test |
| **Test Code** | `tests/verification/test_security.py::TestXSS` |
| **Risk** | **Critical** |
| **OWASP Ref** | A03:2021 - Injection |

### SEC-003: CSRF Token Verification

| Item | Details |
|------|---------|
| **ID** | SEC-003 |
| **Name** | CSRF Token Validation |
| **Criteria** | All POST/PUT/DELETE forms must include `{% csrf_token %}`. `CsrfViewMiddleware` must be active. `@csrf_exempt` is prohibited except on API endpoints using JWT authentication. |
| **Pass Conditions** | (1) CSRF middleware is in MIDDLEWARE list. (2) POST without CSRF token returns 403. (3) No non-API view uses `@csrf_exempt`. (4) AJAX requests include X-CSRFToken header. (5) CSRF token rotated per session. |
| **Fail Conditions** | (1) POST form missing csrf_token. (2) Non-API view with `@csrf_exempt`. (3) CSRF token not validated on state-changing AJAX requests. |
| **Method** | Automated - CSRF-less POST request test + template scan |
| **Test Code** | `tests/verification/test_security.py::TestCSRF` |
| **Risk** | **High** |
| **OWASP Ref** | A01:2021 - Broken Access Control |

### SEC-004: Authentication Bypass Prevention

| Item | Details |
|------|---------|
| **ID** | SEC-004 |
| **Name** | LoginRequiredMixin Coverage Verification |
| **Criteria** | All business views must have `LoginRequiredMixin` or equivalent authentication. Unauthenticated users must be redirected to login page. No business data accessible without authentication. |
| **Pass Conditions** | (1) All business URLs return 302 (to login) or 403 for anonymous access. (2) No business data leaks in 302 redirect response body. (3) URL pattern traversal confirms 100% coverage. (4) Direct URL access to detail/edit/delete views redirects anonymous users. (5) API endpoints return 401 for unauthenticated requests. |
| **Fail Conditions** | (1) Any business URL accessible without authentication. (2) Business data included in redirect response. (3) Static file path exposes uploaded user content without auth check. |
| **Method** | Automated - URL pattern enumeration + anonymous access test |
| **Test Code** | `tests/verification/test_security.py::TestAuthRequired` |
| **Risk** | **Critical** |
| **OWASP Ref** | A07:2021 - Identification and Authentication Failures |

### SEC-005: Privilege Escalation Prevention (RBAC)

| Item | Details |
|------|---------|
| **ID** | SEC-005 |
| **Name** | Role-Based Access Control Verification |
| **Criteria** | `AdminRequiredMixin` views: admin role only. `ManagerRequiredMixin` views: manager/admin only. Staff role cannot access admin functions. Horizontal privilege escalation (accessing other users' data via ID manipulation) must be blocked. |
| **Pass Conditions** | (1) Staff account accessing admin view returns 403. (2) Staff accessing manager view returns 403. (3) Manager accessing admin view returns 403. (4) User A cannot access User B's data by changing URL ID parameter. (5) Role changes require admin-level authorization. |
| **Fail Conditions** | (1) Lower-privilege user accesses higher-privilege function. (2) Horizontal access via URL ID parameter manipulation succeeds. (3) Role field modifiable via form POST by non-admin users. |
| **Method** | Automated - Role-based access test matrix + IDOR test |
| **Test Code** | `tests/verification/test_security.py::TestRBAC` |
| **Risk** | **Critical** |
| **OWASP Ref** | A01:2021 - Broken Access Control |

### SEC-006: Password Policy Enforcement

| Item | Details |
|------|---------|
| **ID** | SEC-006 |
| **Name** | Password Complexity & Policy Verification |
| **Criteria** | All 4 Django AUTH_PASSWORD_VALIDATORS active: UserAttributeSimilarityValidator, MinimumLengthValidator (min 8 chars), CommonPasswordValidator, NumericPasswordValidator. Password stored as hash (PBKDF2+SHA256). |
| **Pass Conditions** | (1) `1234567` (7 chars, too short) rejected. (2) `12345678` (numeric only) rejected. (3) `password` (common password) rejected. (4) `username123` (similar to username) rejected. (5) DB stores password as PBKDF2 hash, never plaintext. |
| **Fail Conditions** | (1) Any weak password accepted by the system. (2) Plaintext password stored in database. (3) Password validator bypassed during user creation. |
| **Method** | Automated - `password_validation.validate_password` test + DB hash verification |
| **Test Code** | `tests/verification/test_security.py::TestPasswordPolicy` |
| **Risk** | **High** |
| **OWASP Ref** | A07:2021 - Identification and Authentication Failures |

### SEC-007: Session Management

| Item | Details |
|------|---------|
| **ID** | SEC-007 |
| **Name** | Session Security Configuration Verification |
| **Criteria** | Production settings: `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_AGE=28800` (8h), `SESSION_EXPIRE_AT_BROWSER_CLOSE=True`, `SESSION_COOKIE_SAMESITE='Lax'`. Session ID regenerated on login. |
| **Pass Conditions** | (1) All 5 session cookie settings correctly configured in production.py. (2) Session cookie has HttpOnly flag. (3) Session cookie has Secure flag in production. (4) Session expires after 8 hours of inactivity. (5) Session ID changes after successful authentication. |
| **Fail Conditions** | (1) Any session setting missing or misconfigured. (2) Session cookie accessible via JavaScript (HttpOnly missing). (3) Session persists indefinitely without timeout. |
| **Method** | Automated - Production settings file verification + session behavior test |
| **Test Code** | `tests/verification/test_security.py::TestSessionSecurity` |
| **Risk** | **High** |
| **OWASP Ref** | A07:2021 - Identification and Authentication Failures |

### SEC-008: Brute-Force Prevention

| Item | Details |
|------|---------|
| **ID** | SEC-008 |
| **Name** | django-axes Login Lockout Verification |
| **Criteria** | `AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_TIME=1` (hour), `AXES_RESET_ON_SUCCESS=True`. After 5 consecutive failures, login blocked for 1 hour even with correct password. |
| **Pass Conditions** | (1) 5 wrong passwords followed by correct password on 6th attempt still fails. (2) After cooloff period, login succeeds with correct credentials. (3) Lockout template displayed with clear message. (4) Lockout logged in axes AccessAttempt table. (5) Successful login resets failure counter. |
| **Fail Conditions** | (1) Login possible after more than 5 consecutive failed attempts. (2) Lockout does not expire after cooloff period. (3) No audit trail of failed attempts. |
| **Method** | Automated - Sequential login failure test |
| **Test Code** | `tests/verification/test_security.py::TestBruteForce` |
| **Risk** | **High** |
| **OWASP Ref** | A07:2021 - Identification and Authentication Failures |

### SEC-009: File Upload Validation

| Item | Details |
|------|---------|
| **ID** | SEC-009 |
| **Name** | File Upload Extension/Size Restriction Verification |
| **Criteria** | Allowed extensions: pdf, jpg, jpeg, png, gif, webp, xlsx, xls, csv, doc, docx, hwp, hwpx, zip, txt. Max size: 10MB. Executable files (.exe, .sh, .bat, .py, .php, .jsp) blocked. Double extension attacks blocked (e.g., `malware.php.jpg` with PHP content). |
| **Pass Conditions** | (1) `.exe` upload returns ValidationError. (2) 15MB file rejected with clear error message. (3) Uploaded file stored outside web root (`MEDIA_ROOT` not under `STATIC_ROOT`). (4) MIME type validation matches extension. (5) Double extension file (`.php.jpg`) with executable content rejected. |
| **Fail Conditions** | (1) Executable file upload succeeds. (2) Size limit bypassed via chunked upload. (3) Uploaded file directly executable via URL. |
| **Method** | Automated - File upload validation test with various payloads |
| **Test Code** | `tests/verification/test_security.py::TestFileUpload` |
| **Risk** | **High** |
| **OWASP Ref** | A04:2021 - Insecure Design |

### SEC-010: Security Headers

| Item | Details |
|------|---------|
| **ID** | SEC-010 |
| **Name** | HTTP Security Header Configuration Verification |
| **Criteria** | Production: `SECURE_HSTS_SECONDS=31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`, `SECURE_HSTS_PRELOAD=True`, `X_FRAME_OPTIONS='DENY'`, `SECURE_CONTENT_TYPE_NOSNIFF=True`, `SECURE_SSL_REDIRECT=True`, `SECURE_REFERRER_POLICY='strict-origin-when-cross-origin'`. |
| **Pass Conditions** | (1) All 7 security header settings correctly configured in production.py. (2) Response headers include `Strict-Transport-Security`. (3) Response headers include `X-Frame-Options: DENY`. (4) Response headers include `X-Content-Type-Options: nosniff`. (5) Referrer-Policy header present. |
| **Fail Conditions** | (1) Any security header missing from production config. (2) HSTS max-age less than 31536000. (3) X-Frame-Options set to SAMEORIGIN when DENY is required. |
| **Method** | Automated - Settings file verification + response header check |
| **Test Code** | `tests/verification/test_security.py::TestSecurityHeaders` |
| **Risk** | **Medium** |
| **OWASP Ref** | A05:2021 - Security Misconfiguration |

### SEC-011: Error Information Disclosure Prevention

| Item | Details |
|------|---------|
| **ID** | SEC-011 |
| **Name** | DEBUG Mode & Error Page Verification |
| **Criteria** | Production: `DEBUG=False`. 500 error must not expose stack trace. Custom 404/500 templates must be served. Error details logged to Sentry, not displayed to user. Django version not exposed in headers. |
| **Pass Conditions** | (1) `DEBUG=False` in production.py. (2) 404 returns custom template without path disclosure. (3) 500 returns custom template without stack trace, local variables, or settings. (4) Sentry DSN configured for error capture. (5) Response headers do not reveal Django version or server software. |
| **Fail Conditions** | (1) Stack trace exposed to user in any error page. (2) `DEBUG=True` in production settings. (3) Settings values (SECRET_KEY, database credentials) visible in error output. |
| **Method** | Automated - Settings verification + error page content check |
| **Test Code** | `tests/verification/test_security.py::TestErrorDisclosure` |
| **Risk** | **High** |
| **OWASP Ref** | A05:2021 - Security Misconfiguration |

### SEC-012: API Authentication

| Item | Details |
|------|---------|
| **ID** | SEC-012 |
| **Name** | REST API JWT Authentication Verification |
| **Criteria** | All API endpoints require `IsAuthenticated`. No API data accessible without token. JWT: ACCESS lifetime 1h, REFRESH 7d. Token rotation enabled. Expired tokens rejected. |
| **Pass Conditions** | (1) `/api/*` without token returns 401 Unauthorized. (2) Valid JWT token returns 200 with correct data. (3) Expired access token returns 401. (4) Refresh token generates new access token. (5) Rotated refresh token blacklisted and cannot be reused. |
| **Fail Conditions** | (1) API data accessible without authentication token. (2) Expired tokens accepted by any endpoint. (3) Refresh token reusable after rotation (replay attack). |
| **Method** | Automated - API authentication test suite |
| **Test Code** | `tests/verification/test_security.py::TestAPIAuth` |
| **Risk** | **Critical** |
| **OWASP Ref** | A07:2021 - Identification and Authentication Failures |

### SEC-013: CORS Policy

| Item | Details |
|------|---------|
| **ID** | SEC-013 |
| **Name** | CORS Policy Verification |
| **Criteria** | `CORS_ALLOW_ALL_ORIGINS=False`. Only explicitly listed origins allowed. No wildcard (`*`). Credentials mode properly restricted. Preflight responses correct. |
| **Pass Conditions** | (1) `CORS_ALLOW_ALL_ORIGINS=False` in settings. (2) `CORS_ALLOWED_ORIGINS` contains only known, trusted domains. (3) Request from unlisted origin receives no Access-Control-Allow-Origin header. (4) Preflight OPTIONS request returns correct allowed methods. (5) Credentials not allowed from untrusted origins. |
| **Fail Conditions** | (1) `CORS_ALLOW_ALL_ORIGINS=True` in any non-dev settings. (2) Wildcard `*` in allowed origins. (3) Sensitive API accessible from arbitrary origins. |
| **Method** | Automated - Settings verification + cross-origin request test |
| **Test Code** | `tests/verification/test_security.py::TestCORS` |
| **Risk** | **Medium** |
| **OWASP Ref** | A05:2021 - Security Misconfiguration |

### SEC-014: Sensitive Data Protection

| Item | Details |
|------|---------|
| **ID** | SEC-014 |
| **Name** | Password Hashing & Secret Management Verification |
| **Criteria** | Passwords hashed with PBKDF2+SHA256. `SECRET_KEY` managed via environment variable. `.env` file excluded from Git. No secrets in source code. API keys stored in environment, not code. |
| **Pass Conditions** | (1) `User.password` stored as PBKDF2 hash. (2) `SECRET_KEY` loaded from env via `os.environ` or `decouple`. (3) `.env` in `.gitignore`. (4) `ANTHROPIC_API_KEY` loaded from env. (5) `grep -r` finds no hardcoded secrets (API keys, passwords, tokens) in source files. |
| **Fail Conditions** | (1) Plaintext password in database. (2) Hardcoded SECRET_KEY in settings.py. (3) API key or password literal in any Python source file. |
| **Method** | Automated - Model/settings verification + secret scanning (trufflehog/gitleaks) |
| **Test Code** | `tests/verification/test_security.py::TestSensitiveData` |
| **Risk** | **Critical** |
| **OWASP Ref** | A02:2021 - Cryptographic Failures |

### SEC-015: Audit Trail

| Item | Details |
|------|---------|
| **ID** | SEC-015 |
| **Name** | simple_history Coverage Verification |
| **Criteria** | All BaseModel-inheriting models must have `history = HistoricalRecords()`. Data modifications must be automatically recorded in history tables. History records must include user, timestamp, and changed fields. |
| **Pass Conditions** | (1) All business models have HistoricalRecords field. (2) Model update creates history entry with correct change type (created/changed/deleted). (3) History entry contains `history_user` (modified_by user). (4) Historical data queryable via `.history.all()`. (5) History table row count >= model table row count. |
| **Fail Conditions** | (1) Any business model missing HistoricalRecords. (2) Model update does not create history entry. (3) History entry missing user or timestamp. |
| **Method** | Automated - Model meta verification + history creation test |
| **Test Code** | `tests/verification/test_security.py::TestAuditTrail` |
| **Risk** | **Medium** |
| **OWASP Ref** | A09:2021 - Security Logging and Monitoring Failures |

### SEC-016: Access Logging

| Item | Details |
|------|---------|
| **ID** | SEC-016 |
| **Name** | AccessLogMiddleware Request Logging Verification |
| **Criteria** | `AccessLogMiddleware` must log: user, path, method, response status, response time, IP address. Logs must be written to file and queryable. Sensitive paths (login, password change) must be logged with extra detail. |
| **Pass Conditions** | (1) Request to any URL creates log entry. (2) Log contains user, path, HTTP method, status code, response time in ms. (3) Failed login attempts logged with source IP. (4) Log file rotation configured (size or time-based). (5) Log entries parseable for monitoring/alerting. |
| **Fail Conditions** | (1) Request not logged. (2) Log missing critical fields (user, path, status). (3) Sensitive data (passwords, tokens) written to logs. |
| **Method** | Automated - Middleware log output verification |
| **Test Code** | `tests/verification/test_security.py::TestAccessLog` |
| **Risk** | **Medium** |
| **OWASP Ref** | A09:2021 - Security Logging and Monitoring Failures |

### SEC-017: Rate Limiting

| Item | Details |
|------|---------|
| **ID** | SEC-017 |
| **Name** | API Rate Limiting Verification |
| **Criteria** | API endpoints must enforce rate limiting to prevent abuse. Login endpoint has stricter limits (via django-axes). Bulk operations must be throttled. DRF throttle classes configured per scope. |
| **Pass Conditions** | (1) Rapid-fire API requests eventually return 429 Too Many Requests. (2) Login attempts throttled after AXES_FAILURE_LIMIT. (3) DRF DEFAULT_THROTTLE_CLASSES configured in settings. (4) Throttle headers (X-RateLimit-Remaining) present in responses. (5) Different throttle rates for anonymous vs authenticated users. |
| **Fail Conditions** | (1) Unlimited API requests possible without throttling. (2) No throttle configured in DRF settings. (3) Bulk data export endpoint unthrottled. |
| **Method** | Automated - Rapid request test + settings check |
| **Test Code** | `tests/verification/test_security.py::TestRateLimiting` |
| **Risk** | **Medium** |
| **OWASP Ref** | A04:2021 - Insecure Design |

### SEC-018: Dependency Vulnerability Scan

| Item | Details |
|------|---------|
| **ID** | SEC-018 |
| **Name** | Third-Party Package Vulnerability Verification |
| **Criteria** | All Python packages must be checked against known CVE databases. No package with known Critical/High CVE in use. `pip-audit` or `safety` scan must pass. Dependencies pinned to specific versions. |
| **Pass Conditions** | (1) `pip-audit` returns 0 critical/high vulnerabilities. (2) All packages on supported, maintained versions. (3) Django version receives active security updates. (4) `requirements.txt` pins exact versions (==). (5) No deprecated packages in dependency tree. |
| **Fail Conditions** | (1) Critical/High CVE found in any direct dependency. (2) Django version past end-of-life. (3) Unpinned dependency versions allowing uncontrolled upgrades. |
| **Method** | Automated - `pip-audit` / `safety check` in CI/CD pipeline |
| **Test Code** | CI/CD pipeline step (GitHub Actions) |
| **Risk** | **High** |
| **OWASP Ref** | A06:2021 - Vulnerable and Outdated Components |

### SEC-019: Container Security

| Item | Details |
|------|---------|
| **ID** | SEC-019 |
| **Name** | Docker Image Security Verification |
| **Criteria** | Docker image uses official Python base. Non-root user for application process. No secrets baked into image. `.dockerignore` excludes sensitive files. Multi-stage build or slim image used. |
| **Pass Conditions** | (1) `USER` directive sets non-root user in Dockerfile. (2) `.env` not included in Docker image (`docker history` clean). (3) Image scan (Trivy/Snyk) passes with no critical findings. (4) `.dockerignore` excludes `.env`, `.git`, `local/`, `*.sqlite3`. (5) Final image size < 500MB. |
| **Fail Conditions** | (1) Application process runs as root. (2) Secrets baked into image layer. (3) Unpatched base OS image with critical CVEs. |
| **Method** | Manual - Docker image inspection + Trivy scan |
| **Test Code** | CI/CD pipeline step (Trivy scan) |
| **Risk** | **High** |
| **OWASP Ref** | A05:2021 - Security Misconfiguration |

### SEC-020: Input Validation & Sanitization

| Item | Details |
|------|---------|
| **ID** | SEC-020 |
| **Name** | Form Input Validation Verification |
| **Criteria** | All form inputs validated server-side via Django Forms/Serializers. Numeric fields reject non-numeric input. Date fields reject invalid dates. Email fields validate format. MaxLength enforced at model level. |
| **Pass Conditions** | (1) Invalid email in email field returns ValidationError. (2) Negative quantity in stock field rejected. (3) Overflow value in decimal field rejected. (4) HTML tags in text field escaped on output. (5) MaxLength violation returns clear error message. |
| **Fail Conditions** | (1) Invalid input accepted and stored in database. (2) Server-side validation missing (only client-side). (3) Type coercion error causes 500 instead of validation error. |
| **Method** | Automated - Form validation test with boundary values |
| **Test Code** | `tests/verification/test_security.py::TestInputValidation` |
| **Risk** | **Medium** |
| **OWASP Ref** | A03:2021 - Injection |

### SEC-021: Password History & Change Policy

| Item | Details |
|------|---------|
| **ID** | SEC-021 |
| **Name** | Password Change & Reuse Prevention Verification |
| **Criteria** | Password change requires current password verification. New password must differ from current. Password change invalidates all existing sessions. Password reset via email uses time-limited token (default 3 days). |
| **Pass Conditions** | (1) Password change without correct current password fails. (2) Setting new password identical to current password rejected. (3) After password change, previous session tokens invalidated. (4) Password reset token expires after `PASSWORD_RESET_TIMEOUT` seconds. (5) Password reset link single-use (cannot be reused). |
| **Fail Conditions** | (1) Password changed without current password verification. (2) Same password reused without restriction. (3) Old sessions remain valid after password change. |
| **Method** | Automated - Password change flow test |
| **Test Code** | `tests/verification/test_security.py::TestPasswordChange` |
| **Risk** | **High** |
| **OWASP Ref** | A07:2021 - Identification and Authentication Failures |

### SEC-022: Session Fixation Prevention

| Item | Details |
|------|---------|
| **ID** | SEC-022 |
| **Name** | Session Fixation Attack Prevention Verification |
| **Criteria** | Session ID must be regenerated upon successful authentication. Pre-authentication session ID must not be valid post-login. Django's `SessionMiddleware` must cycle session key on login. |
| **Pass Conditions** | (1) Session ID before login differs from session ID after login. (2) Pre-login session ID cannot access authenticated resources. (3) `django.contrib.auth.login()` calls `request.session.cycle_key()`. (4) Forced session ID via cookie does not persist after authentication. (5) Session backend properly creates new session record on cycle. |
| **Fail Conditions** | (1) Same session ID used before and after authentication. (2) Attacker-set session ID accepted after victim logs in. (3) Session cycle_key not called during login flow. |
| **Method** | Automated - Session ID comparison before/after login |
| **Test Code** | `tests/verification/test_security.py::TestSessionFixation` |
| **Risk** | **High** |
| **OWASP Ref** | A07:2021 - Identification and Authentication Failures |

### SEC-023: Clickjacking Protection

| Item | Details |
|------|---------|
| **ID** | SEC-023 |
| **Name** | X-Frame-Options & Frame-Ancestors Verification |
| **Criteria** | `X_FRAME_OPTIONS = 'DENY'` set in Django settings. `XFrameOptionsMiddleware` active in MIDDLEWARE. CSP `frame-ancestors` directive set to `'none'` or `'self'`. No view uses `@xframe_options_exempt` without documented justification. |
| **Pass Conditions** | (1) `X-Frame-Options: DENY` present in all response headers. (2) `XFrameOptionsMiddleware` in MIDDLEWARE list. (3) Page cannot be loaded in iframe from any origin. (4) No `@xframe_options_exempt` decorator found in codebase (or all uses justified). (5) CSP frame-ancestors directive reinforces X-Frame-Options. |
| **Fail Conditions** | (1) X-Frame-Options header missing. (2) X-Frame-Options set to ALLOWALL or permissive ALLOW-FROM. (3) Business page loadable in attacker-controlled iframe. |
| **Method** | Automated - Response header check + iframe embedding test |
| **Test Code** | `tests/verification/test_security.py::TestClickjacking` |
| **Risk** | **Medium** |
| **OWASP Ref** | A01:2021 - Broken Access Control |

### SEC-024: Content Security Policy Headers

| Item | Details |
|------|---------|
| **ID** | SEC-024 |
| **Name** | CSP Header Configuration Verification |
| **Criteria** | Content-Security-Policy header must restrict resource loading. `script-src` must not include `'unsafe-inline'` (or use nonce/hash). `style-src` permits Tailwind CDN. `img-src` allows `'self'` and data URIs. `connect-src` allows WebSocket and API endpoints. |
| **Pass Conditions** | (1) CSP header present in responses. (2) `script-src` does not allow `'unsafe-eval'`. (3) `default-src` set to `'self'` as baseline. (4) Inline scripts blocked or require nonce. (5) CSP violation reporting endpoint configured (`report-uri` or `report-to`). |
| **Fail Conditions** | (1) No CSP header in responses. (2) `script-src 'unsafe-inline' 'unsafe-eval'` allows arbitrary script execution. (3) CSP so permissive it provides no security benefit. |
| **Method** | Automated - Response header analysis + CSP evaluator tool |
| **Test Code** | `tests/verification/test_security.py::TestCSPHeaders` |
| **Risk** | **Medium** |
| **OWASP Ref** | A05:2021 - Security Misconfiguration |

### SEC-025: CORS Policy Validation (Detailed)

| Item | Details |
|------|---------|
| **ID** | SEC-025 |
| **Name** | CORS Preflight & Credential Policy Verification |
| **Criteria** | OPTIONS preflight requests return correct `Access-Control-Allow-Methods`. `Access-Control-Allow-Credentials` only `true` for trusted origins. `Access-Control-Max-Age` set to reduce preflight frequency. Exposed headers limited to necessary set. |
| **Pass Conditions** | (1) Preflight response includes only allowed HTTP methods. (2) `Access-Control-Allow-Credentials: true` only for whitelisted origins. (3) `Access-Control-Max-Age` set (e.g., 86400). (4) `Access-Control-Expose-Headers` lists only necessary headers. (5) Non-simple requests (PUT/DELETE) trigger proper preflight. |
| **Fail Conditions** | (1) Credentials allowed from any origin. (2) All HTTP methods allowed without restriction. (3) Preflight cache disabled causing excessive OPTIONS requests. |
| **Method** | Automated - Preflight request simulation with various origins |
| **Test Code** | `tests/verification/test_security.py::TestCORSPreflight` |
| **Risk** | **Medium** |
| **OWASP Ref** | A05:2021 - Security Misconfiguration |

### SEC-026: JWT Token Revocation on Password Change

| Item | Details |
|------|---------|
| **ID** | SEC-026 |
| **Name** | JWT Invalidation After Password Change Verification |
| **Criteria** | When a user changes their password, all previously issued JWT access tokens must become invalid. Refresh tokens must be blacklisted. New tokens required after password change. |
| **Pass Conditions** | (1) JWT issued before password change returns 401 after change. (2) Refresh token issued before password change cannot generate new access token. (3) New token pair obtained with new password works correctly. (4) Token blacklist table records revoked tokens. (5) All active sessions invalidated on password change. |
| **Fail Conditions** | (1) Old JWT still accepted after password change. (2) Old refresh token still generates valid access tokens. (3) No mechanism to revoke issued tokens. |
| **Method** | Automated - Password change + token validity test |
| **Test Code** | `tests/verification/test_security.py::TestJWTRevocation` |
| **Risk** | **High** |
| **OWASP Ref** | A07:2021 - Identification and Authentication Failures |

### SEC-027: API Throttling Per Endpoint

| Item | Details |
|------|---------|
| **ID** | SEC-027 |
| **Name** | Per-Endpoint API Throttle Rate Verification |
| **Criteria** | Different API endpoints have appropriate throttle rates. Authentication endpoints (token obtain/refresh) have stricter limits. Data export endpoints throttled to prevent abuse. Read-heavy endpoints allow higher rates than write endpoints. |
| **Pass Conditions** | (1) Token endpoint throttled to max 10 requests/minute. (2) List endpoints allow 60 requests/minute for authenticated users. (3) Create/Update/Delete endpoints allow 30 requests/minute. (4) Export endpoints throttled to 5 requests/minute. (5) Throttle scope properly set per ViewSet. |
| **Fail Conditions** | (1) Any endpoint has no throttle. (2) Write endpoints have same rate as read endpoints. (3) Authentication endpoint allows unlimited attempts. |
| **Method** | Automated - Per-endpoint throttle rate test |
| **Test Code** | `tests/verification/test_security.py::TestAPIThrottling` |
| **Risk** | **Medium** |
| **OWASP Ref** | A04:2021 - Insecure Design |

### SEC-028: File Upload Malicious Content Scanning

| Item | Details |
|------|---------|
| **ID** | SEC-028 |
| **Name** | Uploaded File Content Safety Verification |
| **Criteria** | Uploaded files must have content matching their extension (MIME type validation). Image files validated as actual images (Pillow verification). Office documents scanned for macros. Zip files checked for path traversal (zip slip). |
| **Pass Conditions** | (1) `.jpg` file with PHP content rejected (MIME mismatch). (2) Corrupted image file rejected by Pillow validation. (3) Zip file with `../../etc/passwd` path rejected (zip slip prevention). (4) File with null bytes in name rejected. (5) SVG file with embedded JavaScript rejected. |
| **Fail Conditions** | (1) File with mismatched MIME type accepted. (2) Zip slip attack allows writing outside upload directory. (3) SVG with XSS payload stored and served. |
| **Method** | Automated - Malicious file upload test suite |
| **Test Code** | `tests/verification/test_security.py::TestMaliciousUpload` |
| **Risk** | **High** |
| **OWASP Ref** | A04:2021 - Insecure Design |

### SEC-029: SQL Injection in Search/Filter Parameters

| Item | Details |
|------|---------|
| **ID** | SEC-029 |
| **Name** | Search & Filter Parameter SQL Injection Prevention |
| **Criteria** | All search views use Django ORM `Q` objects or `icontains`/`iexact` lookups. Filter parameters validated against allowed field names. Custom filter backends parameterize all inputs. No raw SQL in search logic. |
| **Pass Conditions** | (1) Search query `'; DROP TABLE products; --` returns empty results, no error. (2) Filter parameter `status=1 OR 1=1` treated as literal string. (3) Order-by parameter `id; DELETE FROM users` rejected or sanitized. (4) All search views use `Q(field__icontains=query)` pattern. (5) Custom queryset filters validate field names against whitelist. |
| **Fail Conditions** | (1) SQL injection via search bar affects database. (2) Filter parameter allows arbitrary SQL execution. (3) Order-by parameter allows SQL injection via column name. |
| **Method** | Automated - Search endpoint injection payload test |
| **Test Code** | `tests/verification/test_security.py::TestSearchInjection` |
| **Risk** | **Critical** |
| **OWASP Ref** | A03:2021 - Injection |

### SEC-030: Mass Assignment Protection

| Item | Details |
|------|---------|
| **ID** | SEC-030 |
| **Name** | Form Field Whitelist & Mass Assignment Prevention |
| **Criteria** | All Django ModelForms use explicit `fields` list (never `fields = '__all__'` for user-facing forms). Sensitive fields (role, is_active, is_superuser, created_by) excluded from forms. DRF Serializers use explicit field lists. |
| **Pass Conditions** | (1) No user-facing form uses `fields = '__all__'`. (2) POST request with `role=admin` in body does not change user role (for non-admin forms). (3) `is_superuser` cannot be set via any public form. (4) `created_by` auto-populated from `request.user`, not form input. (5) DRF serializers use `fields` list or `exclude` for sensitive fields. |
| **Fail Conditions** | (1) User can set `role` or `is_superuser` via form POST. (2) `fields = '__all__'` used on user-facing form with sensitive model. (3) Serializer accepts and applies hidden fields from request body. |
| **Method** | Automated - Form field whitelist scan + POST payload test |
| **Test Code** | `tests/verification/test_security.py::TestMassAssignment` |
| **Risk** | **High** |
| **OWASP Ref** | A04:2021 - Insecure Design |

### SEC-031: IDOR (Insecure Direct Object Reference) Prevention

| Item | Details |
|------|---------|
| **ID** | SEC-031 |
| **Name** | IDOR Prevention in Detail/Update/Delete Views |
| **Criteria** | Users can only access objects they are authorized to view. Detail views filter by ownership or role. Update/Delete views verify user has permission on the specific object. Sequential ID enumeration does not expose other users' data. |
| **Pass Conditions** | (1) User A requesting `/orders/123/` (User B's order) returns 403 or 404. (2) Staff user cannot access admin-only record by ID. (3) Incrementing IDs in URL does not reveal existence of unauthorized records (404 preferred over 403). (4) Bulk operations validate ownership for each item. (5) API detail endpoints enforce object-level permissions. |
| **Fail Conditions** | (1) User accesses another user's record by changing URL ID. (2) 403 response reveals existence of the record (information leak). (3) Bulk delete accepts IDs belonging to other users. |
| **Method** | Automated - Cross-user object access test |
| **Test Code** | `tests/verification/test_security.py::TestIDOR` |
| **Risk** | **Critical** |
| **OWASP Ref** | A01:2021 - Broken Access Control |

### SEC-032: Account Enumeration Prevention

| Item | Details |
|------|---------|
| **ID** | SEC-032 |
| **Name** | Username/Email Enumeration Prevention Verification |
| **Criteria** | Login failure message must not distinguish between "user not found" and "wrong password". Password reset must not reveal whether email exists. Registration (if applicable) must not reveal existing usernames. Response timing must be consistent. |
| **Pass Conditions** | (1) Login with non-existent username returns same error as wrong password (e.g., "Invalid credentials"). (2) Password reset for non-existent email returns same response as existing email. (3) Response time for existing vs non-existing username within 100ms variance. (4) No user enumeration via API endpoints. (5) Error messages do not include username or email in response. |
| **Fail Conditions** | (1) "User not found" message for non-existent username. (2) "Email not registered" message on password reset. (3) Timing side-channel reveals user existence. |
| **Method** | Automated - Login/reset timing and message analysis |
| **Test Code** | `tests/verification/test_security.py::TestAccountEnumeration` |
| **Risk** | **Medium** |
| **OWASP Ref** | A07:2021 - Identification and Authentication Failures |

### SEC-033: Sensitive Data Exposure in Error Pages

| Item | Details |
|------|---------|
| **ID** | SEC-033 |
| **Name** | Error Page Information Leakage Prevention |
| **Criteria** | Custom error pages (400, 403, 404, 500) must not expose internal paths, database queries, environment variables, or configuration details. Error pages must use generic messages. Technical details logged server-side only. |
| **Pass Conditions** | (1) 404 page does not reveal file system paths. (2) 500 page shows generic "Internal Server Error" message. (3) 400 page does not expose request parsing details. (4) 403 page does not reveal which permission is missing. (5) No traceback, SQL query, or settings value in any error response body. |
| **Fail Conditions** | (1) Error page exposes Django settings. (2) Database connection string visible in error output. (3) Full Python traceback in production error page. |
| **Method** | Automated - Error page content analysis |
| **Test Code** | `tests/verification/test_security.py::TestErrorPages` |
| **Risk** | **Medium** |
| **OWASP Ref** | A05:2021 - Security Misconfiguration |

### SEC-034: HTTP Security Headers Completeness

| Item | Details |
|------|---------|
| **ID** | SEC-034 |
| **Name** | Complete HTTP Security Header Audit |
| **Criteria** | All recommended security headers present: Strict-Transport-Security, X-Content-Type-Options, X-Frame-Options, Content-Security-Policy, Referrer-Policy, Permissions-Policy, Cache-Control (for sensitive pages). Server header suppressed or generic. |
| **Pass Conditions** | (1) HSTS header with max-age >= 31536000. (2) X-Content-Type-Options: nosniff. (3) Permissions-Policy restricts camera, microphone, geolocation. (4) Cache-Control: no-store on authenticated pages. (5) Server header does not reveal technology stack (no "gunicorn", "daphne", "nginx" version). |
| **Fail Conditions** | (1) Missing HSTS on production. (2) Server header reveals exact software version. (3) Sensitive pages cached by browser (no Cache-Control). |
| **Method** | Automated - Full response header audit against OWASP checklist |
| **Test Code** | `tests/verification/test_security.py::TestHeaderCompleteness` |
| **Risk** | **Medium** |
| **OWASP Ref** | A05:2021 - Security Misconfiguration |

### SEC-035: Admin Panel Path Obfuscation

| Item | Details |
|------|---------|
| **ID** | SEC-035 |
| **Name** | Django Admin URL Path Security Verification |
| **Criteria** | Django admin panel must not be accessible at default `/admin/` path. Custom admin URL configured (e.g., `/mgmt-console-x/` or similar non-guessable path). Admin login page requires additional security (IP whitelist or 2FA recommended). |
| **Pass Conditions** | (1) `/admin/` returns 404 (not the admin login page). (2) Admin panel accessible at custom non-default URL. (3) Admin URL not discoverable via robots.txt or sitemap. (4) Admin login page not indexed by search engines (`X-Robots-Tag: noindex`). (5) Admin access logged separately in access logs. |
| **Fail Conditions** | (1) Default `/admin/` URL serves Django admin. (2) Admin URL easily guessable (e.g., `/administrator/`, `/manage/`). (3) Admin panel exposed without IP restriction in production. |
| **Method** | Manual - URL path test + robots.txt review |
| **Test Code** | `tests/verification/test_security.py::TestAdminPath` |
| **Risk** | **Low** |
| **OWASP Ref** | A05:2021 - Security Misconfiguration |

---

## 3. Data Integrity Verification (INT-001 ~ INT-030)

### INT-001: Stock Consistency

| Item | Details |
|------|---------|
| **ID** | INT-001 |
| **Name** | Stock Movement Sum vs Current Stock Verification |
| **Criteria** | `Product.current_stock = SUM(inbound qty) - SUM(outbound qty)`. Inbound types: IN, ADJ_PLUS, PROD_IN, RETURN. Outbound types: OUT, ADJ_MINUS, PROD_OUT. Verification must pass for all products simultaneously. |
| **Pass Conditions** | (1) All products: recalculated stock == current_stock. (2) After 100 random movements, consistency maintained. (3) Negative stock prevented or flagged. (4) Zero-quantity movements handled correctly. (5) Stock recalculation management command matches live values. |
| **Fail Conditions** | (1) Any product has mismatched stock. (2) Stock becomes negative without explicit override. (3) Orphaned movements (referencing deleted products) exist. |
| **Method** | Automated - StockMovement aggregate comparison |
| **Test Code** | `tests/verification/test_data_integrity.py::TestStockConsistency` |
| **Risk** | **Critical** |

### INT-002: Order Amount Calculation

| Item | Details |
|------|---------|
| **ID** | INT-002 |
| **Name** | Order Item Amount Auto-Calculation Verification |
| **Criteria** | `OrderItem.amount = quantity * unit_price`. `OrderItem.tax_amount = int(amount * 0.1)`. `Order.total_amount = SUM(items.amount)`. `Order.grand_total = total_amount + tax_total`. Rounding follows Korean Won (no decimals). |
| **Pass Conditions** | (1) Item save triggers auto-calculation. (2) Order totals match item sums. (3) Tax is exactly 10% truncated to integer. (4) Edge case: qty=0, price=0 handled without error. (5) Large amounts (billions of Won) calculate correctly without overflow. |
| **Fail Conditions** | (1) Calculation mismatch between items and order total. (2) Tax not applied or calculated incorrectly. (3) Decimal amounts stored for Won currency. |
| **Method** | Automated - OrderItem creation + amount verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestOrderCalculation` |
| **Risk** | **Critical** |

### INT-003: Double-Entry Bookkeeping Balance

| Item | Details |
|------|---------|
| **ID** | INT-003 |
| **Name** | Voucher Debit/Credit Balance Verification |
| **Criteria** | `Voucher.total_debit == Voucher.total_credit`. `is_balanced` property returns True only when balanced. No approved voucher may be unbalanced. VoucherLine changes tracked via HistoricalRecords. |
| **Pass Conditions** | (1) Balanced voucher: `is_balanced == True`. (2) Unbalanced voucher: `is_balanced == False`. (3) Approval workflow rejects unbalanced vouchers. (4) VoucherLine history recorded on every change. (5) Sum of all debit lines equals sum of all credit lines across entire ledger. |
| **Fail Conditions** | (1) Unbalanced voucher accepted and approved. (2) `is_balanced` returns incorrect result. (3) VoucherLine modification not tracked in history. |
| **Method** | Automated - Voucher/VoucherLine creation + balance verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestDoubleEntry` |
| **Risk** | **Critical** |

### INT-004: BOM Effective Quantity Calculation

| Item | Details |
|------|---------|
| **ID** | INT-004 |
| **Name** | BOM Item Effective Quantity (Loss Rate) Verification |
| **Criteria** | `BOMItem.effective_quantity = quantity * (1 + loss_rate / 100)`. Loss rate 0% means effective == quantity. Loss rate 10% means effective == quantity * 1.1. Loss rate must be >= 0. |
| **Pass Conditions** | (1) Multiple loss rates (0%, 5%, 10%, 25%) produce correct results. (2) Negative loss rate prevented by model validation. (3) Decimal precision maintained through calculation. (4) BOM total cost reflects effective quantities. (5) Nested BOM (sub-assembly) cost rollup accurate. |
| **Fail Conditions** | (1) Effective quantity calculation error. (2) Loss rate not applied to material requirement. (3) Negative loss rate accepted. |
| **Method** | Automated - BOMItem creation + effective_quantity verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestBOMCalculation` |
| **Risk** | **High** |

### INT-005: Production Auto-Stock Reflection

| Item | Details |
|------|---------|
| **ID** | INT-005 |
| **Name** | Production Record Auto-Stock Movement Verification |
| **Criteria** | ProductionRecord creation triggers signal: (1) Finished product PROD_IN auto-created. (2) BOM-based raw material PROD_OUT auto-created for each BOM item. (3) `Product.current_stock` updated atomically via F() expression. (4) Transaction atomic - partial failure rolls back all changes. |
| **Pass Conditions** | (1) 10 production records create 10 PROD_IN + (10 * BOM item count) PROD_OUT movements. (2) Stock changes match expected quantities exactly. (3) Concurrent production records don't corrupt stock (F expression). (4) Failed production record rolls back all associated stock movements. (5) Production with zero quantity handled gracefully. |
| **Fail Conditions** | (1) StockMovement not created on production record save. (2) Stock quantity mismatch after production. (3) Partial stock update (finished good updated but raw materials not deducted). |
| **Method** | Automated - ProductionRecord creation + stock verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestProductionStock` |
| **Risk** | **Critical** |

### INT-006: Shipment Auto-Stock Deduction

| Item | Details |
|------|---------|
| **ID** | INT-006 |
| **Name** | Order SHIPPED Status Auto-Deduction Verification |
| **Criteria** | Order status change to SHIPPED triggers signal: OUT-type StockMovement for each OrderItem. `Product.current_stock` decreases by order item quantity. Duplicate deduction prevented (idempotent). |
| **Pass Conditions** | (1) SHIPPED order creates OUT movements equal to order item count. (2) Stock decreased by correct quantities. (3) Re-saving SHIPPED order doesn't duplicate deduction. (4) Order with multiple items deducts each product correctly. (5) Insufficient stock scenario handled (error or warning). |
| **Fail Conditions** | (1) StockMovement not created on SHIPPED transition. (2) Duplicate deduction on re-save. (3) Wrong product or quantity in stock movement. |
| **Method** | Automated - Order status change + stock verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestShipmentStock` |
| **Risk** | **Critical** |

### INT-007: Accounts Receivable Consistency

| Item | Details |
|------|---------|
| **ID** | INT-007 |
| **Name** | AR Balance Consistency Verification |
| **Criteria** | `AccountReceivable.remaining_amount = amount - paid_amount`. Status transitions: PENDING -> PARTIAL (partial payment) -> PAID (full payment). Overdue detection: `due_date < today AND status != PAID`. |
| **Pass Conditions** | (1) `remaining_amount` equals `amount - paid_amount` at all times. (2) Payment updates `paid_amount` and triggers correct status transition. (3) Past-due AR flagged as overdue. (4) Overpayment prevented (paid_amount cannot exceed amount). (5) Multiple partial payments accumulate correctly. |
| **Fail Conditions** | (1) Balance calculation error after partial payment. (2) Status inconsistent with payment amount. (3) Overdue AR not flagged. |
| **Method** | Automated - AR creation + payment + balance verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestARConsistency` |
| **Risk** | **High** |

### INT-008: Soft Delete Consistency

| Item | Details |
|------|---------|
| **ID** | INT-008 |
| **Name** | ActiveManager Filtering & Soft Delete Verification |
| **Criteria** | `BaseModel.objects` (ActiveManager) returns `is_active=True` only. `soft_delete()` sets `is_active=False`. `all_objects` returns all records including soft-deleted. No physical DELETE on business data. |
| **Pass Conditions** | (1) After soft_delete: `objects.all()` excludes record, `all_objects.all()` includes it. (2) Soft-deleted records recoverable by setting `is_active=True`. (3) `updated_at` timestamp refreshed on soft_delete. (4) Related records' foreign keys remain valid after soft delete. (5) List views and API endpoints exclude soft-deleted records. |
| **Fail Conditions** | (1) Soft-deleted record appears in default queryset. (2) Physical delete occurs on business data. (3) Soft delete breaks related record foreign keys. |
| **Method** | Automated - soft_delete + queryset verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestSoftDelete` |
| **Risk** | **High** |

### INT-009: Unique Constraint Verification

| Item | Details |
|------|---------|
| **ID** | INT-009 |
| **Name** | Unique Field Duplicate Prevention Verification |
| **Criteria** | `Product.code`, `Order.order_number`, `Voucher.voucher_number`, `TaxInvoice.invoice_number` - all unique=True fields must reject duplicates with IntegrityError at database level. |
| **Pass Conditions** | (1) Second record with same unique value raises IntegrityError for all tested fields. (2) Form submission with duplicate value shows user-friendly error (not 500). (3) Case sensitivity handled correctly (case-insensitive where appropriate). (4) Unique constraint survives soft delete (soft-deleted codes still reserved). (5) Auto-generated codes (order numbers) never collide. |
| **Fail Conditions** | (1) Duplicate value accepted in any unique field. (2) IntegrityError displayed as raw 500 error to user. (3) Auto-generated code collision under concurrent creation. |
| **Method** | Automated - Duplicate insertion test per unique field |
| **Test Code** | `tests/verification/test_data_integrity.py::TestUniqueConstraint` |
| **Risk** | **High** |

### INT-010: Foreign Key Referential Integrity

| Item | Details |
|------|---------|
| **ID** | INT-010 |
| **Name** | FK PROTECT Behavior Verification |
| **Criteria** | `on_delete=PROTECT` FKs must raise ProtectedError when referenced record is deleted. Product with StockMovements cannot be deleted. Partner with Orders cannot be deleted. |
| **Pass Conditions** | (1) Referenced record deletion raises ProtectedError for all PROTECT FKs. (2) User-friendly error message displayed (not raw traceback). (3) CASCADE deletions only for intended relationships (e.g., OrderItem when Order deleted). (4) SET_NULL applied only where documented. (5) No orphaned records after any delete operation. |
| **Fail Conditions** | (1) Referenced record deleted despite PROTECT constraint. (2) Silently nullified FK where PROTECT expected. (3) Cascade deletion of unintended related records. |
| **Method** | Automated - FK PROTECT deletion test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestFKProtect` |
| **Risk** | **Critical** |

### INT-011: Purchase Order Auto-Stock Reflection

| Item | Details |
|------|---------|
| **ID** | INT-011 |
| **Name** | Goods Receipt Auto-Stock & PO Status Verification |
| **Criteria** | GoodsReceiptItem creation triggers signal: (1) IN-type StockMovement auto-created. (2) `PurchaseOrderItem.received_quantity` updated. (3) PO status transitions: CONFIRMED -> PARTIAL_RECEIVED -> RECEIVED based on received quantities. |
| **Pass Conditions** | (1) Receipt creates IN-type stock movement with correct product and quantity. (2) Partial receipt (50%) sets PO status to PARTIAL_RECEIVED. (3) Full receipt (100%) sets PO status to RECEIVED. (4) Stock increased by exact receipt quantity. (5) Over-receipt (exceeding PO quantity) prevented or flagged. |
| **Fail Conditions** | (1) Stock not updated on goods receipt. (2) PO status incorrect after receipt. (3) Receipt quantity exceeds PO quantity without warning. |
| **Method** | Automated - GoodsReceipt creation + PO status verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestPurchaseStock` |
| **Risk** | **Critical** |

### INT-012: Quotation-to-Order Conversion Integrity

| Item | Details |
|------|---------|
| **ID** | INT-012 |
| **Name** | Quote Conversion Data Completeness Verification |
| **Criteria** | Quotation conversion creates Order with identical items (product, quantity, unit_price). Quotation status changes to CONVERTED. `converted_order` FK set. Original quotation items unchanged. |
| **Pass Conditions** | (1) Order items match quotation items exactly (product, quantity, unit_price). (2) Quotation marked CONVERTED after conversion. (3) `converted_order` points to newly created order. (4) Re-conversion of same quotation prevented with clear error. (5) Original quotation data remains unmodified. |
| **Fail Conditions** | (1) Item mismatch between quotation and created order. (2) Quotation status not updated to CONVERTED. (3) Duplicate conversion allowed creating multiple orders. |
| **Method** | Automated - Quotation conversion + data comparison test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestQuoteConversion` |
| **Risk** | **High** |

### INT-013: Concurrent Stock Update Safety

| Item | Details |
|------|---------|
| **ID** | INT-013 |
| **Name** | F() Expression Race Condition Prevention Verification |
| **Criteria** | Stock updates use `F('current_stock')` expression, not read-modify-write pattern. Concurrent updates produce correct results. No lost updates under contention. |
| **Pass Conditions** | (1) 100 concurrent stock updates: final stock == initial + sum of all changes. (2) Signal code uses `F()` expression exclusively for stock changes. (3) No direct assignment to `current_stock` field in signal handlers. (4) Thread-safe under 50 concurrent requests. (5) select_for_update used where F() is insufficient. |
| **Fail Conditions** | (1) Lost updates under concurrent access. (2) Direct `product.current_stock = new_value` assignment found in signals. (3) Race condition produces incorrect stock count. |
| **Method** | Automated - Multi-threaded stock update + final balance verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestConcurrentStock` |
| **Risk** | **Critical** |

### INT-014: Accounts Payable Consistency

| Item | Details |
|------|---------|
| **ID** | INT-014 |
| **Name** | AP Balance & Payment Tracking Verification |
| **Criteria** | `AccountPayable.remaining_amount = amount - paid_amount`. Payment creates record and updates `paid_amount`. Status transitions match payment progress. |
| **Pass Conditions** | (1) AP remaining matches expected calculation. (2) Full payment sets status to PAID. (3) Partial payment sets status to PARTIAL. (4) Overdue AP flagged correctly based on due_date. (5) Payment amount cannot exceed remaining amount. |
| **Fail Conditions** | (1) Balance mismatch after payment. (2) Status error (PAID with remaining > 0). (3) Overpayment allowed without validation. |
| **Method** | Automated - AP + Payment cycle test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestAPConsistency` |
| **Risk** | **High** |

### INT-015: Commission Calculation Accuracy

| Item | Details |
|------|---------|
| **ID** | INT-015 |
| **Name** | Sales Commission Calculation Verification |
| **Criteria** | Commission = Order amount * commission rate. Rate lookup by product/partner/tier. Rounding follows Won (truncate). Commission records linked to source order. |
| **Pass Conditions** | (1) Commission matches rate * amount for all test cases. (2) Tiered rates applied correctly at threshold boundaries. (3) Summary totals match sum of individual records. (4) Commission record links back to source order. (5) Zero commission rate produces zero commission. |
| **Fail Conditions** | (1) Commission miscalculation at any tier. (2) Rounding error (decimal Won amounts). (3) Commission not linked to source order. |
| **Method** | Automated - Commission calculation test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestCommissionCalculation` |
| **Risk** | **Medium** |

### INT-016: Voucher Double-Entry Balance Validation

| Item | Details |
|------|---------|
| **ID** | INT-016 |
| **Name** | Voucher Line-Level Debit/Credit Precision Verification |
| **Criteria** | Each voucher must have at least one debit line and one credit line. Sum of debit amounts must exactly equal sum of credit amounts (to the Won). Account codes must be valid and active. Voucher cannot be approved if unbalanced. |
| **Pass Conditions** | (1) Voucher with debit 1,000,000 and credit 1,000,000: `is_balanced == True`. (2) Voucher with debit 1,000,000 and credit 999,999: `is_balanced == False` and approval blocked. (3) Multi-line voucher (3 debits, 2 credits) balances correctly. (4) Voucher with inactive account code rejected. (5) Zero-amount voucher line rejected. |
| **Fail Conditions** | (1) Unbalanced voucher passes `is_balanced` check. (2) Voucher with debit-only or credit-only lines accepted. (3) Rounding causes 1-Won discrepancy in large vouchers. |
| **Method** | Automated - Multi-scenario voucher balance test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestVoucherBalance` |
| **Risk** | **Critical** |

### INT-017: Production BOM Cost Rollup Accuracy

| Item | Details |
|------|---------|
| **ID** | INT-017 |
| **Name** | BOM Material Cost Aggregation Verification |
| **Criteria** | BOM total material cost = SUM(BOMItem.effective_quantity * material.cost_price) for all items. Multi-level BOM (sub-assembly) costs roll up recursively. Cost updates propagate when material prices change. |
| **Pass Conditions** | (1) Single-level BOM cost matches manual calculation. (2) Two-level BOM (product -> sub-assembly -> raw materials) cost includes sub-assembly material costs. (3) Material price change triggers BOM cost recalculation. (4) Loss rate factored into cost (effective_quantity * cost). (5) BOM cost displayed correctly on production plan. |
| **Fail Conditions** | (1) BOM cost does not include all material lines. (2) Sub-assembly cost not rolled up into parent BOM. (3) Stale cost after material price update. |
| **Method** | Automated - BOM cost calculation test with multi-level structure |
| **Test Code** | `tests/verification/test_data_integrity.py::TestBOMCostRollup` |
| **Risk** | **High** |

### INT-018: Tax Invoice Amount Calculation

| Item | Details |
|------|---------|
| **ID** | INT-018 |
| **Name** | Tax Invoice Supply Amount + VAT Verification |
| **Criteria** | `TaxInvoice.supply_amount` = total before tax. `TaxInvoice.tax_amount` = int(supply_amount * tax_rate). `TaxInvoice.total_amount` = supply_amount + tax_amount. Standard VAT rate = 10%. Amounts in whole Won (no decimals). |
| **Pass Conditions** | (1) Supply 1,000,000 with 10% VAT = tax 100,000, total 1,100,000. (2) Supply 999,999 with 10% VAT = tax 99,999 (truncated), total 1,099,998. (3) Zero-rated supply (0% VAT) = tax 0. (4) Tax invoice amounts match linked order amounts. (5) PDF output matches calculated amounts. |
| **Fail Conditions** | (1) VAT calculation uses rounding instead of truncation. (2) Total != supply + tax. (3) Decimal amounts in Won-denominated fields. |
| **Method** | Automated - Tax invoice creation + amount verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestTaxInvoiceAmount` |
| **Risk** | **High** |

### INT-019: Leave Balance Auto-Calculation Accuracy

| Item | Details |
|------|---------|
| **ID** | INT-019 |
| **Name** | Annual Leave Balance Calculation Verification |
| **Criteria** | Leave balance = total_days - used_days. Approved leave request deducts from balance. Rejected/cancelled leave request does not deduct. Balance cannot go negative. Half-day leave deducts 0.5. |
| **Pass Conditions** | (1) Initial balance matches allocated days (e.g., 15 days). (2) Approved 3-day leave: balance = 15 - 3 = 12. (3) Rejected leave does not change balance. (4) Half-day leave deducts 0.5 from balance. (5) Leave request exceeding balance rejected. |
| **Fail Conditions** | (1) Balance miscalculated after approval. (2) Rejected leave deducted from balance. (3) Negative balance allowed without override. |
| **Method** | Automated - Leave request + balance verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestLeaveBalance` |
| **Risk** | **Medium** |

### INT-020: Attendance Record Non-Overlap Validation

| Item | Details |
|------|---------|
| **ID** | INT-020 |
| **Name** | Duplicate Attendance Record Prevention Verification |
| **Criteria** | Only one check-in per user per day. Check-out requires prior check-in on same day. Work hours = check_out - check_in. Overlapping attendance records (same user, same date) prevented at database level. |
| **Pass Conditions** | (1) Second check-in on same day rejected with clear error. (2) Check-out without check-in rejected. (3) Work hours calculated correctly (e.g., 09:00 to 18:00 = 9 hours). (4) Cross-midnight shift handled correctly. (5) Attendance record for future date prevented. |
| **Fail Conditions** | (1) Duplicate check-in accepted for same date. (2) Negative work hours calculated. (3) Check-out before check-in time accepted. |
| **Method** | Automated - Attendance duplicate and edge case test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestAttendanceOverlap` |
| **Risk** | **Medium** |

### INT-021: Board Comment Tree Integrity

| Item | Details |
|------|---------|
| **ID** | INT-021 |
| **Name** | Nested Comment Parent-Child Relationship Verification |
| **Criteria** | Comments support parent-child nesting (replies). Parent comment deletion handles children (soft delete or orphan prevention). Comment tree displays in correct order. Depth limit enforced (max 3 levels). |
| **Pass Conditions** | (1) Reply comment has correct `parent` FK to parent comment. (2) Comment tree renders in chronological order within each level. (3) Soft-deleting parent comment preserves child comments (shows "deleted comment" placeholder). (4) Reply to reply creates proper 3-level nesting. (5) Attempt to create 4th-level nesting rejected or flattened. |
| **Fail Conditions** | (1) Orphaned comments after parent deletion. (2) Comment tree displays in wrong order. (3) Circular parent reference possible. |
| **Method** | Automated - Comment tree creation + display verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestCommentTree` |
| **Risk** | **Low** |

### INT-022: Chat Message Ordering and Delivery Guarantee

| Item | Details |
|------|---------|
| **ID** | INT-022 |
| **Name** | Messenger Message Order & Persistence Verification |
| **Criteria** | Messages displayed in chronological order (created_at). All sent messages persisted to database. WebSocket delivery does not skip messages. Chat history query returns complete message set. |
| **Pass Conditions** | (1) 100 rapid messages display in correct chronological order. (2) All messages saved to database (count matches sent count). (3) Page refresh shows identical message history. (4) Messages from multiple users interleaved correctly by timestamp. (5) Long message content preserved without truncation. |
| **Fail Conditions** | (1) Messages displayed out of order. (2) Message lost (not persisted to database). (3) Duplicate messages displayed. |
| **Method** | Automated - Rapid message send + order verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestMessageOrdering` |
| **Risk** | **Medium** |

### INT-023: Investment Equity Percentage Validation

| Item | Details |
|------|---------|
| **ID** | INT-023 |
| **Name** | Equity Share Total Percentage Verification |
| **Criteria** | Sum of all investor equity percentages for a single round must not exceed 100%. Individual equity percentage must be > 0% and <= 100%. Equity changes tracked via history. Dividend distribution proportional to equity. |
| **Pass Conditions** | (1) Total equity for a round with 3 investors (40% + 30% + 30%) = 100%, accepted. (2) Adding 4th investor at 10% when total is already 100% rejected. (3) Zero or negative equity percentage rejected. (4) Equity > 100% for single investor rejected. (5) Dividend distribution matches equity proportions. |
| **Fail Conditions** | (1) Total equity exceeds 100%. (2) Negative equity percentage accepted. (3) Dividend distributed disproportionally to equity. |
| **Method** | Automated - Equity allocation + boundary test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestEquityPercentage` |
| **Risk** | **High** |

### INT-024: Warranty Expiry Date Calculation Accuracy

| Item | Details |
|------|---------|
| **ID** | INT-024 |
| **Name** | Warranty Period Start/End Date Verification |
| **Criteria** | Warranty start date = registration date (or purchase date). Warranty end date = start date + warranty period (months). `is_valid` property returns True only within warranty period. Expired warranty correctly identified. |
| **Pass Conditions** | (1) 12-month warranty registered today: expiry = today + 12 months. (2) `is_valid` returns True for active warranty. (3) `is_valid` returns False for expired warranty. (4) Warranty verification endpoint returns correct status. (5) Edge case: warranty registered on Feb 29 (leap year) handled. |
| **Fail Conditions** | (1) Expiry date miscalculated. (2) Expired warranty shows as valid. (3) Leap year / month-end date calculation error. |
| **Method** | Automated - Warranty date calculation + boundary test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestWarrantyExpiry` |
| **Risk** | **Medium** |

### INT-025: Stock Transfer Atomic Consistency

| Item | Details |
|------|---------|
| **ID** | INT-025 |
| **Name** | Warehouse-to-Warehouse Transfer Atomicity Verification |
| **Criteria** | Stock transfer creates two movements atomically: OUT from source warehouse, IN to destination warehouse. Source stock decreases by N, destination stock increases by N. Total system stock unchanged. Partial transfer (source insufficient) rolled back entirely. |
| **Pass Conditions** | (1) Transfer of 50 units: source -50, destination +50. (2) Total stock across all warehouses unchanged. (3) Insufficient source stock: entire transfer rolled back (no partial). (4) Both stock movements reference same transfer record. (5) Concurrent transfers from same source don't over-deduct. |
| **Fail Conditions** | (1) Source deducted but destination not credited (partial update). (2) Total system stock changes after transfer. (3) Insufficient stock allows partial transfer. |
| **Method** | Automated - Transfer + dual-warehouse stock verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestStockTransfer` |
| **Risk** | **Critical** |

### INT-026: Multi-Currency Amount Conversion

| Item | Details |
|------|---------|
| **ID** | INT-026 |
| **Name** | Currency Conversion Accuracy Verification |
| **Criteria** | If multi-currency support is active: exchange rate applied correctly. Converted amount = original * exchange_rate. Base currency (KRW) amounts always stored. Exchange rate date-stamped. Rounding follows banking convention. |
| **Pass Conditions** | (1) USD 1,000 at rate 1,300 = KRW 1,300,000. (2) Exchange rate from correct date used. (3) Converted amount stored alongside original. (4) Reverse conversion produces consistent result. (5) Zero or negative exchange rate rejected. |
| **Fail Conditions** | (1) Wrong exchange rate applied. (2) Rounding error exceeds 1 Won. (3) Exchange rate date mismatch. |
| **Method** | Automated - Currency conversion calculation test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestCurrencyConversion` |
| **Risk** | **Medium** |

### INT-027: Soft Delete Cascade Behavior

| Item | Details |
|------|---------|
| **ID** | INT-027 |
| **Name** | Soft Delete Effect on Related Objects Verification |
| **Criteria** | Soft-deleting a parent record must be handled consistently for children. Options: cascade soft-delete children, or prevent soft-delete if active children exist. Soft-deleted parent must not appear in FK dropdown lists. |
| **Pass Conditions** | (1) Soft-deleted partner does not appear in order partner dropdown. (2) Soft-deleted product does not appear in BOM material selection. (3) Soft-deleted category still shows on existing products (historical reference). (4) Report queries exclude soft-deleted records by default. (5) Restore (re-activate) parent makes it available in dropdowns again. |
| **Fail Conditions** | (1) Soft-deleted record selectable in forms. (2) Report includes soft-deleted data in totals. (3) Restore of parent doesn't restore visibility. |
| **Method** | Automated - Soft delete + form queryset verification |
| **Test Code** | `tests/verification/test_data_integrity.py::TestSoftDeleteCascade` |
| **Risk** | **Medium** |

### INT-028: HistoricalRecords Completeness Across All Models

| Item | Details |
|------|---------|
| **ID** | INT-028 |
| **Name** | simple_history Coverage Completeness Verification |
| **Criteria** | Every model inheriting from BaseModel must have `history = HistoricalRecords()`. Historical table exists for each model. All field changes captured in history. History accessible from admin and audit views. |
| **Pass Conditions** | (1) Programmatic scan: all BaseModel subclasses have `history` attribute. (2) Historical table exists in database for each model. (3) Field value change creates history entry with old and new values. (4) `history_user` populated from request.user. (5) History count matches or exceeds model record count. |
| **Fail Conditions** | (1) BaseModel subclass missing HistoricalRecords. (2) Historical table missing in database. (3) History entry missing changed field values. |
| **Method** | Automated - Model introspection + history creation test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestHistoricalRecords` |
| **Risk** | **Medium** |

### INT-029: created_by Auto-Population in All CreateViews

| Item | Details |
|------|---------|
| **ID** | INT-029 |
| **Name** | Creator Field Auto-Population Verification |
| **Criteria** | All CreateView subclasses must auto-set `created_by = request.user` in `form_valid()`. User cannot manually set `created_by` via form. `created_by` field not editable in UpdateView. |
| **Pass Conditions** | (1) New record created via form has `created_by == request.user`. (2) `created_by` field not present in form HTML. (3) POST request with `created_by=other_user_id` does not override auto-population. (4) UpdateView does not allow changing `created_by`. (5) API POST auto-sets created_by from JWT token user. |
| **Fail Conditions** | (1) `created_by` is NULL after creation. (2) `created_by` set to wrong user. (3) `created_by` modifiable via form POST. |
| **Method** | Automated - CreateView form_valid + field presence test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestCreatedByPopulation` |
| **Risk** | **Medium** |

### INT-030: Unique Constraint Enforcement (Codes & Serial Numbers)

| Item | Details |
|------|---------|
| **ID** | INT-030 |
| **Name** | Business Code Uniqueness Across All Modules Verification |
| **Criteria** | All auto-generated business codes must be unique: Product.code, Order.order_number, Voucher.voucher_number, TaxInvoice.invoice_number, PurchaseOrder.po_number, SerialNumber. Codes must be sequential and predictable format. |
| **Pass Conditions** | (1) 1000 rapid creations produce 1000 unique codes with no collision. (2) Code format follows defined pattern (e.g., ORD-YYYYMMDD-NNNN). (3) Code uniqueness enforced at DB level (unique constraint). (4) Concurrent code generation (10 threads) produces no duplicates. (5) Soft-deleted record's code cannot be reused. |
| **Fail Conditions** | (1) Code collision under any circumstance. (2) Code format inconsistent. (3) Gap in sequential numbering not documented. |
| **Method** | Automated - Rapid concurrent code generation test |
| **Test Code** | `tests/verification/test_data_integrity.py::TestCodeUniqueness` |
| **Risk** | **High** |

---

## 4. Performance Verification (PERF-001 ~ PERF-015)

### PERF-001: Page Response Time

| Item | Details |
|------|---------|
| **ID** | PERF-001 |
| **Name** | Major Page Response Time Verification |
| **Criteria** | List pages: <=500ms. Dashboard: <=1000ms. Detail pages: <=300ms. API endpoints: <=200ms. Measured at 95th percentile with representative data volume (10K+ records). |
| **Pass Conditions** | (1) 95th percentile within thresholds for all tested pages. (2) Dashboard renders within 1000ms with 1 year of data. (3) API list endpoints respond within 200ms. (4) Detail page with all related data loads within 300ms. (5) No page exceeds 3000ms at 99th percentile. |
| **Fail Conditions** | (1) Any primary page exceeds its threshold at p95. (2) Dashboard timeout under normal data volume. (3) API endpoint consistently exceeds 1000ms. |
| **Method** | Automated - Response time measurement with `assertNumQueries` + timing |
| **Test Code** | `tests/verification/test_performance.py::TestResponseTime` |
| **Risk** | **Medium** |

### PERF-002: N+1 Query Prevention

| Item | Details |
|------|---------|
| **ID** | PERF-002 |
| **Name** | N+1 Query Problem Verification |
| **Criteria** | List pages: <=10 DB queries regardless of record count. `select_related`/`prefetch_related` used for FK/M2M. Query count must not grow linearly with record count. Dashboard cached data within 5min TTL. |
| **Pass Conditions** | (1) List page with 100 records uses <=10 queries. (2) Same query count with 1000 records (no linear growth). (3) Dashboard uses cache for chart data. (4) All FK fields in list templates use `select_related`. (5) M2M fields use `prefetch_related`. |
| **Fail Conditions** | (1) Query count >10 on any list page. (2) Linear query growth with data volume. (3) Uncached repeated dashboard queries. |
| **Method** | Automated - `assertNumQueries` + data volume scaling test |
| **Test Code** | `tests/verification/test_performance.py::TestNPlusOne` |
| **Risk** | **High** |

### PERF-003: Concurrent User Load

| Item | Details |
|------|---------|
| **ID** | PERF-003 |
| **Name** | Concurrent User Load Handling Verification |
| **Criteria** | 50 concurrent users: 95th percentile <=2s, error rate <1%. 100 concurrent users: 95th <=5s, error rate <5%. No connection pool exhaustion. No deadlocks under load. |
| **Pass Conditions** | (1) 50-user load test: p95 < 2000ms. (2) 100-user load test: p95 < 5000ms. (3) Error rate below threshold. (4) No database connection exhaustion. (5) No HTTP 502/503 errors during test. |
| **Fail Conditions** | (1) p95 >= threshold at either load level. (2) Error rate >= threshold. (3) Connection pool exhaustion causing failures. |
| **Method** | Manual - Locust load test (`loadtest/locustfile.py`) |
| **Test Code** | `loadtest/locustfile.py` |
| **Risk** | **Medium** |

### PERF-004: Large Dataset Pagination

| Item | Details |
|------|---------|
| **ID** | PERF-004 |
| **Name** | Large Dataset Pagination Verification |
| **Criteria** | 100K records: list page renders in <=500ms. Pagination active (no full table scan). `paginate_by` set on all ListViews. DB indexes on filtered/ordered columns. |
| **Pass Conditions** | (1) 100K records: page loads <500ms. (2) SQL EXPLAIN shows index usage (no sequential scan). (3) Memory usage stable across page numbers (page 1 == page 1000). (4) All ListView subclasses have `paginate_by` set. (5) Page navigation works correctly at boundary pages (first, last). |
| **Fail Conditions** | (1) Timeout or OOM with 100K records. (2) Missing pagination on any ListView. (3) Sequential scan on paginated query. |
| **Method** | Automated - Bulk insert + paginated query test |
| **Test Code** | `tests/verification/test_performance.py::TestPagination` |
| **Risk** | **Medium** |

### PERF-005: Cache Effectiveness

| Item | Details |
|------|---------|
| **ID** | PERF-005 |
| **Name** | Redis Cache Hit Rate Verification |
| **Criteria** | Dashboard chart data cached (5min TTL). Repeat requests served from cache. Cache hit rate >=80% for repeated queries. Cache invalidation on data change. |
| **Pass Conditions** | (1) 2nd request >=50% faster than 1st. (2) Cache key exists in Redis after first request. (3) Cache cleared on relevant data update. (4) Cache TTL correctly set (5 minutes). (5) Cache miss on first request after invalidation. |
| **Fail Conditions** | (1) No caching observed (all requests same speed). (2) Stale data served after update (invalidation failure). (3) Hit rate <80% under normal usage. |
| **Method** | Automated - Cache hit/miss timing test |
| **Test Code** | `tests/verification/test_performance.py::TestCacheHitRate` |
| **Risk** | **Low** |

### PERF-006: Database Index Coverage

| Item | Details |
|------|---------|
| **ID** | PERF-006 |
| **Name** | Critical Query Index Verification |
| **Criteria** | All frequently filtered/sorted fields have DB indexes. Foreign key fields auto-indexed by Django. Composite indexes on multi-column filters. `EXPLAIN ANALYZE` confirms index usage on critical paths. |
| **Pass Conditions** | (1) All defined `db_index=True` fields have corresponding indexes in DB. (2) Common list view queries use index scan (not sequential scan). (3) Slow query log (>100ms) shows no unindexed queries. (4) Composite index on (date, status) for commonly filtered views. (5) Index count reasonable (not over-indexed). |
| **Fail Conditions** | (1) Missing index on high-traffic query path. (2) Sequential scan on table >10K rows. (3) Critical report query unindexed. |
| **Method** | Automated - Migration inspection + EXPLAIN verification |
| **Test Code** | `tests/verification/test_performance.py::TestIndexCoverage` |
| **Risk** | **Medium** |

### PERF-007: WebSocket Connection Scalability

| Item | Details |
|------|---------|
| **ID** | PERF-007 |
| **Name** | Django Channels WebSocket Scalability Verification |
| **Criteria** | 100 concurrent WebSocket connections maintained. Message broadcast latency <=1s. Connection recovery after network interruption. Redis channel layer handles message queue without message loss. |
| **Pass Conditions** | (1) 100 connections stable for 5 minutes. (2) Broadcast message received by all connected clients within 1s. (3) Reconnection after disconnect succeeds within 5s. (4) No message loss during broadcast. (5) Channel layer memory usage stable under sustained connections. |
| **Fail Conditions** | (1) Connection drops under load. (2) Message loss during broadcast. (3) Broadcast latency > 5s. |
| **Method** | Manual - WebSocket stress test using custom script |
| **Test Code** | Manual test script |
| **Risk** | **Low** |

### PERF-008: Dashboard Query Count Optimization

| Item | Details |
|------|---------|
| **ID** | PERF-008 |
| **Name** | Dashboard Aggregate Query Efficiency Verification |
| **Criteria** | Main dashboard (core:dashboard) must execute <=15 database queries total. Chart data queries use aggregation (COUNT, SUM, AVG) instead of Python-level iteration. Widget data cached independently with appropriate TTL. |
| **Pass Conditions** | (1) Dashboard page executes <=15 queries (measured by `assertNumQueries`). (2) Revenue chart uses `SUM` aggregation, not Python loop. (3) Stock status widget uses single aggregate query. (4) Each dashboard widget cacheable independently. (5) Dashboard loads within 1000ms with 1 year of transaction data. |
| **Fail Conditions** | (1) Dashboard executes >20 queries. (2) Chart data calculated in Python from individual record iteration. (3) Dashboard timeout with moderate data volume. |
| **Method** | Automated - Dashboard query profiling |
| **Test Code** | `tests/verification/test_performance.py::TestDashboardQueries` |
| **Risk** | **Medium** |

### PERF-009: List View Pagination Efficiency

| Item | Details |
|------|---------|
| **ID** | PERF-009 |
| **Name** | Paginated List View Query Efficiency Verification |
| **Criteria** | Paginated queries use `LIMIT/OFFSET` at SQL level. Count query for pagination uses efficient `COUNT(*)`. Filtering combined with pagination uses indexed columns. Page size configurable (default 20, max 100). |
| **Pass Conditions** | (1) SQL query contains LIMIT and OFFSET clauses. (2) Count query executes in <50ms for 100K row table. (3) Filtering + pagination still uses index. (4) Requesting page beyond range returns empty page (not error). (5) `paginate_by` defaults to 20 across all list views. |
| **Fail Conditions** | (1) Full table loaded into memory before pagination (Python-level slicing). (2) Count query triggers full table scan. (3) Inconsistent page sizes across views. |
| **Method** | Automated - SQL query analysis + timing test |
| **Test Code** | `tests/verification/test_performance.py::TestPaginationEfficiency` |
| **Risk** | **Medium** |

### PERF-010: Excel Export Memory Usage

| Item | Details |
|------|---------|
| **ID** | PERF-010 |
| **Name** | Large Dataset Excel Export Memory Verification |
| **Criteria** | Excel export of 10K+ records must not exceed 200MB memory. Streaming response used for large exports. Export timeout set (max 60s). Memory freed after export completion. |
| **Pass Conditions** | (1) 10K record export completes without OOM. (2) Memory usage during export stays below 200MB. (3) Export uses streaming (openpyxl write-only mode or similar). (4) 50K record export completes within 60s. (5) Memory returns to baseline after export. |
| **Fail Conditions** | (1) OOM error on 10K+ record export. (2) Memory usage exceeds 500MB during export. (3) Export hangs without timeout. |
| **Method** | Automated - Memory profiling during export test |
| **Test Code** | `tests/verification/test_performance.py::TestExcelMemory` |
| **Risk** | **Medium** |

### PERF-011: WebSocket Connection Handling Under Load

| Item | Details |
|------|---------|
| **ID** | PERF-011 |
| **Name** | Concurrent WebSocket + HTTP Load Verification |
| **Criteria** | System handles 50 WebSocket connections + 50 concurrent HTTP requests simultaneously. HTTP response time not degraded by WebSocket connections. WebSocket messages not delayed by HTTP load. |
| **Pass Conditions** | (1) HTTP p95 response time with WebSocket load <= 1.5x baseline. (2) WebSocket message latency with HTTP load <= 2x baseline. (3) No connection drops during combined load. (4) Daphne handles both protocols without resource contention. (5) Redis channel layer queue depth stable. |
| **Fail Conditions** | (1) HTTP response time >3x baseline under WebSocket load. (2) WebSocket disconnections during HTTP surge. (3) Redis channel layer backlog growing unbounded. |
| **Method** | Manual - Combined load test with Locust + WebSocket client |
| **Test Code** | `loadtest/locustfile.py` (extended) |
| **Risk** | **Low** |

### PERF-012: Celery Task Queue Throughput

| Item | Details |
|------|---------|
| **ID** | PERF-012 |
| **Name** | Celery Task Processing Speed Verification |
| **Criteria** | Celery worker processes tasks within expected timeframes. Queue depth monitored and alertable. Failed tasks retried with exponential backoff. Task results stored for debugging. |
| **Pass Conditions** | (1) Simple task (backup) completes within 30s. (2) Queued 100 tasks processed within 5 minutes (1 worker). (3) Failed task retried up to 3 times. (4) Task result accessible via `AsyncResult`. (5) Queue depth returns to 0 after processing burst. |
| **Fail Conditions** | (1) Task stuck in queue >10 minutes. (2) Failed task not retried. (3) Queue depth grows indefinitely. |
| **Method** | Manual - Celery task queue stress test |
| **Test Code** | Manual test procedure |
| **Risk** | **Medium** |

### PERF-013: Static File Serving Performance (WhiteNoise)

| Item | Details |
|------|---------|
| **ID** | PERF-013 |
| **Name** | WhiteNoise Static File Serving Efficiency Verification |
| **Criteria** | Static files served with appropriate Cache-Control headers. Gzip/Brotli compression enabled for text assets. ETag headers prevent unnecessary re-downloads. Static file response time <50ms. |
| **Pass Conditions** | (1) CSS/JS files served with `Cache-Control: max-age=31536000, immutable`. (2) Gzip compression active for text/css and application/javascript. (3) ETag header present on static responses. (4) Conditional request (If-None-Match) returns 304. (5) Static file first-load time <100ms. |
| **Fail Conditions** | (1) No caching headers on static files. (2) Uncompressed static files served. (3) Static file response time >500ms. |
| **Method** | Automated - Static file response header and timing test |
| **Test Code** | `tests/verification/test_performance.py::TestStaticFiles` |
| **Risk** | **Low** |

### PERF-014: Database Connection Pooling

| Item | Details |
|------|---------|
| **ID** | PERF-014 |
| **Name** | Database Connection Pool Configuration Verification |
| **Criteria** | Connection pooling configured (django-db-connection-pool or CONN_MAX_AGE). Idle connections released after timeout. Pool size appropriate for concurrent load. Connection leak detection. |
| **Pass Conditions** | (1) `CONN_MAX_AGE` set to appropriate value (e.g., 600s). (2) Idle connections closed after CONN_MAX_AGE. (3) Under 50-user load, connection count stays below pool max. (4) No connection leak after request completion. (5) Connection error logged when pool exhausted. |
| **Fail Conditions** | (1) `CONN_MAX_AGE=0` (new connection per request) in production. (2) Connection leak (growing count over time). (3) Pool exhaustion under moderate load. |
| **Method** | Manual - Connection pool monitoring under load |
| **Test Code** | Manual monitoring (Prometheus pg_stat_activity) |
| **Risk** | **Medium** |

### PERF-015: Cache Hit Ratio for Frequently Accessed Data

| Item | Details |
|------|---------|
| **ID** | PERF-015 |
| **Name** | Redis Cache Hit/Miss Ratio Monitoring Verification |
| **Criteria** | Frequently accessed data (dashboard stats, user permissions, product catalog) cached in Redis. Cache hit ratio >=80% during normal operation. Cache warming on application start. Cache key naming follows convention. |
| **Pass Conditions** | (1) Redis `INFO stats` shows keyspace_hits / (keyspace_hits + keyspace_misses) >= 0.8. (2) Dashboard stats served from cache on repeat visits. (3) Cache keys follow `erp:{app}:{model}:{id}` naming convention. (4) Cache warm-up script available for cold start. (5) Cache memory usage within allocated Redis limit. |
| **Fail Conditions** | (1) Hit ratio below 50%. (2) Frequently accessed data not cached. (3) Cache memory exceeded causing evictions of important keys. |
| **Method** | Manual - Redis INFO monitoring + cache behavior test |
| **Test Code** | Manual monitoring (Redis CLI / Prometheus) |
| **Risk** | **Low** |

---

## 5. Functional Workflow Verification (FUNC-001 ~ FUNC-030)

### FUNC-001: Order Lifecycle

| Item | Details |
|------|---------|
| **ID** | FUNC-001 |
| **Name** | Order Status Transition Workflow Verification |
| **Criteria** | DRAFT -> CONFIRMED -> SHIPPED -> DELIVERED. SHIPPED triggers auto stock deduction. CANCELLED only before SHIPPED. Invalid transitions (DELIVERED -> DRAFT) rejected. |
| **Pass Conditions** | (1) All valid transitions succeed with correct status change. (2) SHIPPED creates OUT movements for all order items. (3) Invalid transition raises error with clear message. (4) CANCELLED order cannot be shipped. (5) Status history tracked via HistoricalRecords. |
| **Fail Conditions** | (1) Invalid status transition accepted. (2) Stock not deducted on SHIPPED. (3) CANCELLED order allows further transitions. |
| **Method** | Automated - E2E workflow test |
| **Test Code** | `tests/verification/test_workflow.py::TestOrderLifecycle` |
| **Risk** | **Critical** |

### FUNC-002: Production Lifecycle

| Item | Details |
|------|---------|
| **ID** | FUNC-002 |
| **Name** | Production Workflow Verification |
| **Criteria** | Plan (DRAFT->CONFIRMED->IN_PROGRESS->COMPLETED) -> WorkOrder (PENDING->IN_PROGRESS->COMPLETED) -> ProductionRecord. Record registration triggers finished goods IN + raw materials OUT. All work orders completed -> plan auto-completed. |
| **Pass Conditions** | (1) All status transitions succeed in correct order. (2) Auto stock reflection verified (PROD_IN + PROD_OUT). (3) Plan auto-completes when last work order completed. (4) Partially completed plan shows IN_PROGRESS. (5) Production record quantity matches work order planned quantity. |
| **Fail Conditions** | (1) Status transition error. (2) Stock not reflected after production. (3) Plan not auto-completed after all work orders done. |
| **Method** | Automated - E2E workflow test |
| **Test Code** | `tests/verification/test_workflow.py::TestProductionLifecycle` |
| **Risk** | **Critical** |

### FUNC-003: Purchase Lifecycle

| Item | Details |
|------|---------|
| **ID** | FUNC-003 |
| **Name** | Purchase/PO Workflow Verification |
| **Criteria** | PO (DRAFT->CONFIRMED) -> GoodsReceipt -> auto IN stock. Partial receipt -> PARTIAL_RECEIVED. Full receipt -> RECEIVED. Receipt quantities cannot exceed PO quantities. |
| **Pass Conditions** | (1) Receipt creates IN movement with correct product/quantity. (2) Partial receipt correctly sets PARTIAL_RECEIVED status. (3) Full receipt sets RECEIVED status. (4) Over-receipt (quantity > PO) prevented. (5) Multiple receipts against single PO tracked correctly. |
| **Fail Conditions** | (1) Stock not reflected after goods receipt. (2) PO status incorrect after receipt. (3) Over-receipt allowed without validation. |
| **Method** | Automated - E2E workflow test |
| **Test Code** | `tests/verification/test_workflow.py::TestPurchaseLifecycle` |
| **Risk** | **Critical** |

### FUNC-004: Service Request Lifecycle

| Item | Details |
|------|---------|
| **ID** | FUNC-004 |
| **Name** | AS Request Status Transition Verification |
| **Criteria** | RECEIVED -> INSPECTING -> REPAIRING -> COMPLETED -> RETURNED. RepairRecord linked at each stage. Status change timestamps recorded. |
| **Pass Conditions** | (1) All forward transitions succeed. (2) Repair records linked to service request. (3) Backward transitions prevented. (4) Each status change timestamped. (5) Service request history shows complete progression. |
| **Fail Conditions** | (1) Status transition allows backward movement. (2) Repair record not linked. (3) Timestamps missing. |
| **Method** | Automated - Status transition test |
| **Test Code** | `tests/verification/test_workflow.py::TestServiceLifecycle` |
| **Risk** | **Medium** |

### FUNC-005: Multi-Step Approval Workflow

| Item | Details |
|------|---------|
| **ID** | FUNC-005 |
| **Name** | Multi-Step Approval Workflow Verification |
| **Criteria** | ApprovalRequest -> sequential ApprovalStep approval -> final APPROVED. Any step REJECTED -> entire request REJECTED. `current_step` progresses correctly. Only designated approver can approve their step. Out-of-order approval prevented. |
| **Pass Conditions** | (1) 3-step sequential approval results in APPROVED status. (2) Step 2 rejection sets entire request to REJECTED. (3) Wrong approver attempting approval returns 403. (4) Step 3 cannot approve before step 2 is approved. (5) Approval comments recorded per step. |
| **Fail Conditions** | (1) Out-of-order approval accepted. (2) Wrong approver can approve step. (3) Status mismatch after approval/rejection. |
| **Method** | Automated - Multi-step approval scenario test |
| **Test Code** | `tests/verification/test_workflow.py::TestApprovalWorkflow` |
| **Risk** | **High** |

### FUNC-006: Quotation to Order Conversion

| Item | Details |
|------|---------|
| **ID** | FUNC-006 |
| **Name** | Quotation -> Order Conversion Verification |
| **Criteria** | Quotation items auto-copied to Order. Quotation status -> CONVERTED. `converted_order` FK set. Already-converted quotation cannot be re-converted. |
| **Pass Conditions** | (1) Order items match quotation items (product, quantity, unit_price). (2) Quotation status = CONVERTED. (3) `converted_order` FK points to new order. (4) Re-conversion returns error. (5) Order inherits quotation's partner/customer. |
| **Fail Conditions** | (1) Item mismatch between quotation and order. (2) Duplicate conversion creates second order. (3) Quotation status not updated. |
| **Method** | Automated - Conversion + verification test |
| **Test Code** | `tests/verification/test_workflow.py::TestQuoteConversion` |
| **Risk** | **High** |

### FUNC-007: Login/Logout/Lockout

| Item | Details |
|------|---------|
| **ID** | FUNC-007 |
| **Name** | Authentication Workflow Verification |
| **Criteria** | Correct credentials -> login success + session created. Wrong password -> failure. Logout -> session invalidated. 5 failures -> account locked (django-axes). Locked account shows lockout page. |
| **Pass Conditions** | (1) Correct login creates session and redirects to dashboard. (2) Wrong password shows error without revealing which credential is wrong. (3) Logout destroys session and redirects to login. (4) 5 consecutive failures trigger lockout. (5) Lockout page displays with remaining time. |
| **Fail Conditions** | (1) Login with wrong password succeeds. (2) Session persists after logout. (3) Lockout not triggered after 5 failures. |
| **Method** | Automated - Authentication scenario test |
| **Test Code** | `tests/verification/test_workflow.py::TestAuthWorkflow` |
| **Risk** | **Critical** |

### FUNC-008: Excel Import/Export

| Item | Details |
|------|---------|
| **ID** | FUNC-008 |
| **Name** | Excel Import/Export Verification |
| **Criteria** | django-import-export exports valid .xlsx files. Re-import preserves all data. Korean characters preserved. Numeric precision maintained. |
| **Pass Conditions** | (1) Export generates valid, openable Excel file. (2) Re-imported data matches original 100%. (3) Korean text characters intact (UTF-8). (4) Decimal numbers preserve precision. (5) Date fields export in correct format. |
| **Fail Conditions** | (1) Export generates corrupted file. (2) Data loss on round-trip import/export. (3) Korean text garbled (encoding issue). |
| **Method** | Manual - Export/import cycle test |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### FUNC-009: PDF Generation

| Item | Details |
|------|---------|
| **ID** | FUNC-009 |
| **Name** | PDF Output Verification |
| **Criteria** | Tax invoice PDF generated correctly. Korean font rendering works. Amounts display correctly. PDF downloadable via browser. |
| **Pass Conditions** | (1) PDF file generated without error. (2) Korean text readable in PDF viewer. (3) Amounts match source data exactly. (4) PDF layout matches template design. (5) Multiple-page PDF renders correctly for long invoices. |
| **Fail Conditions** | (1) PDF generation throws exception. (2) Korean characters garbled or missing. (3) Amounts differ from source data. |
| **Method** | Manual - PDF generation + visual inspection |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### FUNC-010: Real-Time Notifications

| Item | Details |
|------|---------|
| **ID** | FUNC-010 |
| **Name** | WebSocket Real-Time Notification Verification |
| **Criteria** | Django Channels delivers notifications via WebSocket. Notification created -> delivered to connected user within 1 second. Broadcast notifications reach all connected users. Offline users see notifications on next login. |
| **Pass Conditions** | (1) Notification received via WebSocket within 1s. (2) Broadcast notification reaches all connected users. (3) Offline users see unread notifications on login. (4) Notification count badge updates in real time. (5) Mark-as-read updates persist. |
| **Fail Conditions** | (1) Notification not delivered. (2) Excessive delay (>5s). (3) Notification lost for offline users. |
| **Method** | Manual - WebSocket connection + notification trigger test |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### FUNC-011: Attendance Check-In/Out

| Item | Details |
|------|---------|
| **ID** | FUNC-011 |
| **Name** | Attendance Record Workflow Verification |
| **Criteria** | Check-in records timestamp. Check-out records timestamp and calculates work hours. Duplicate check-in same day prevented. Leave request -> approval workflow. Leave balance decremented on approval. |
| **Pass Conditions** | (1) Check-in/out timestamps recorded accurately. (2) Duplicate check-in on same day rejected. (3) Leave approval decrements balance correctly. (4) Work hours calculated as check_out - check_in. (5) Late arrival flagged based on policy. |
| **Fail Conditions** | (1) Timestamp error or wrong timezone. (2) Duplicate check-in allowed. (3) Leave balance not decremented on approval. |
| **Method** | Automated - Attendance workflow test |
| **Test Code** | `tests/verification/test_workflow.py::TestAttendanceWorkflow` |
| **Risk** | **Medium** |

### FUNC-012: Board & Comment System

| Item | Details |
|------|---------|
| **ID** | FUNC-012 |
| **Name** | Board Post/Comment Lifecycle Verification |
| **Criteria** | Post CRUD operations work. Comments support nesting (replies). Author can edit/delete own content. Non-author cannot modify others' posts. Notice posts pinned to top. |
| **Pass Conditions** | (1) Create/Read/Update/Delete all succeed for author. (2) Nested comments display correctly in tree structure. (3) Non-author edit attempt returns 403. (4) Notice posts appear above regular posts. (5) Soft delete preserves post for admin recovery. |
| **Fail Conditions** | (1) CRUD failure on valid input. (2) Permission bypass (non-author modifies post). (3) Notice posts not pinned. |
| **Method** | Automated - Board CRUD + permission test |
| **Test Code** | `tests/verification/test_workflow.py::TestBoardWorkflow` |
| **Risk** | **Low** |

### FUNC-013: Calendar Event Management

| Item | Details |
|------|---------|
| **ID** | FUNC-013 |
| **Name** | Calendar AJAX API Verification |
| **Criteria** | FullCalendar.js integration works. Events created/updated/deleted via AJAX API. Date range queries return correct events. Event data format matches FullCalendar specification. |
| **Pass Conditions** | (1) Event CRUD via AJAX API returns correct JSON. (2) Date range filter returns only events within range. (3) Events render on calendar UI correctly. (4) Drag-and-drop event move updates database. (5) Overlapping events displayed correctly. |
| **Fail Conditions** | (1) API returns wrong format for FullCalendar. (2) Date filter returns events outside range. (3) Event CRUD does not persist. |
| **Method** | Automated - Calendar API endpoint test |
| **Test Code** | `tests/verification/test_workflow.py::TestCalendarWorkflow` |
| **Risk** | **Low** |

### FUNC-014: Messenger Real-Time Chat

| Item | Details |
|------|---------|
| **ID** | FUNC-014 |
| **Name** | WebSocket Chat Functionality Verification |
| **Criteria** | 1:1 and group chat rooms creatable. Messages delivered in real-time via WebSocket. Message history persisted. Chat participants managed correctly. |
| **Pass Conditions** | (1) Direct (1:1) room creation works. (2) Group room creation with 3+ members works. (3) Messages delivered to all participants in real time. (4) Message history retrievable on room open. (5) Participant addition/removal updates room correctly. |
| **Fail Conditions** | (1) Message not delivered to recipient. (2) Message history lost. (3) Non-member can access chat room. |
| **Method** | Manual - WebSocket chat test |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### FUNC-015: Marketplace Order Sync

| Item | Details |
|------|---------|
| **ID** | FUNC-015 |
| **Name** | External Marketplace Integration Verification |
| **Criteria** | Naver/Coupang API client connects successfully. Order sync imports external orders. Duplicate order prevention. Status sync bidirectional. |
| **Pass Conditions** | (1) API connection test passes with valid credentials. (2) Orders imported with correct product/customer mapping. (3) Duplicate external order ID rejected on re-sync. (4) Status update in ERP reflected to marketplace. (5) Sync errors logged and retryable. |
| **Fail Conditions** | (1) Sync failure without clear error message. (2) Duplicate orders created. (3) Status desynchronization between systems. |
| **Method** | Manual - API integration test with sandbox environment |
| **Test Code** | Manual test procedure |
| **Risk** | **Medium** |

### FUNC-016: Purchase Order to Receipt to Stock Flow

| Item | Details |
|------|---------|
| **ID** | FUNC-016 |
| **Name** | End-to-End Purchase Workflow Verification |
| **Criteria** | Complete flow: PO creation -> PO approval (CONFIRMED) -> Goods receipt creation -> Stock IN movement auto-created -> PO status updated -> Product stock increased. All steps verifiable and traceable. |
| **Pass Conditions** | (1) PO created with correct items and quantities. (2) PO approval changes status to CONFIRMED. (3) Goods receipt linked to PO. (4) IN-type stock movement auto-created for each receipt item. (5) Product.current_stock increased by receipt quantity. |
| **Fail Conditions** | (1) Any step in the chain fails silently. (2) Stock movement not linked to receipt. (3) PO status not updated after receipt. |
| **Method** | Automated - Full chain workflow test |
| **Test Code** | `tests/verification/test_workflow.py::TestPurchaseFullFlow` |
| **Risk** | **Critical** |

### FUNC-017: Multi-Step Accounting Approval Workflow

| Item | Details |
|------|---------|
| **ID** | FUNC-017 |
| **Name** | Accounting Voucher Approval Chain Verification |
| **Criteria** | Voucher submitted for approval creates ApprovalRequest. Approval chain follows configured steps (e.g., team lead -> manager -> CFO). Each step notifies next approver. Final approval marks voucher as APPROVED. Rejected voucher returns to submitter with comments. |
| **Pass Conditions** | (1) Approval request created with correct number of steps. (2) Each approval advances to next step. (3) Notification sent to next approver on step completion. (4) Final approval updates voucher status to APPROVED. (5) Rejection returns to submitter with rejection reason. |
| **Fail Conditions** | (1) Approval step skipped. (2) No notification to next approver. (3) Voucher status not updated after final approval. |
| **Method** | Automated - Multi-step voucher approval test |
| **Test Code** | `tests/verification/test_workflow.py::TestAccountingApproval` |
| **Risk** | **High** |

### FUNC-018: HR Personnel Action Effect

| Item | Details |
|------|---------|
| **ID** | FUNC-018 |
| **Name** | HR Action Impact on Department/Position Verification |
| **Criteria** | Personnel action (transfer, promotion, demotion) updates EmployeeProfile's department and position. Organization chart reflects changes. Historical record of all actions maintained. |
| **Pass Conditions** | (1) Transfer action updates employee's department. (2) Promotion action updates employee's position/rank. (3) Organization chart shows employee in new department. (4) PersonnelAction history records all changes. (5) Effective date respected (future-dated actions applied on date). |
| **Fail Conditions** | (1) Employee department not updated after transfer. (2) Organization chart stale after action. (3) Action history missing or incomplete. |
| **Method** | Automated - Personnel action + org chart verification |
| **Test Code** | `tests/verification/test_workflow.py::TestHRAction` |
| **Risk** | **Medium** |

### FUNC-019: Leave Request Approval and Balance Deduction

| Item | Details |
|------|---------|
| **ID** | FUNC-019 |
| **Name** | Leave Request Full Lifecycle Verification |
| **Criteria** | Leave request submission -> manager approval -> balance deduction. Rejection does not deduct. Cancellation (before start date) restores balance. Overlapping leave requests prevented. |
| **Pass Conditions** | (1) Approved leave deducts correct days from balance. (2) Rejected leave does not change balance. (3) Cancelled leave (before start) restores deducted balance. (4) Overlapping date range with existing approved leave rejected. (5) Half-day leave deducts 0.5 from balance. |
| **Fail Conditions** | (1) Balance not deducted on approval. (2) Rejected leave deducts balance. (3) Overlapping leave approved. |
| **Method** | Automated - Leave lifecycle test |
| **Test Code** | `tests/verification/test_workflow.py::TestLeaveWorkflow` |
| **Risk** | **Medium** |

### FUNC-020: Board Post with Nested Comments (3 Levels)

| Item | Details |
|------|---------|
| **ID** | FUNC-020 |
| **Name** | Three-Level Nested Comment Display Verification |
| **Criteria** | Comments support 3 levels of nesting: comment -> reply -> reply-to-reply. Each level visually indented. Comment count includes all levels. Parent deletion handles children gracefully. |
| **Pass Conditions** | (1) Level 1 comment created on post. (2) Level 2 reply to comment works with correct parent FK. (3) Level 3 reply-to-reply works with correct parent FK. (4) Template renders correct indentation per level. (5) Comment count includes all 3 levels. |
| **Fail Conditions** | (1) Reply FK not set to parent. (2) Display not indented by level. (3) Comment count excludes nested replies. |
| **Method** | Automated - Nested comment creation + display test |
| **Test Code** | `tests/verification/test_workflow.py::TestNestedComments` |
| **Risk** | **Low** |

### FUNC-021: Calendar Event CRUD via AJAX API

| Item | Details |
|------|---------|
| **ID** | FUNC-021 |
| **Name** | Calendar AJAX Event API Complete CRUD Verification |
| **Criteria** | Create event via POST AJAX. Read events via GET with date range. Update event (time/title) via PUT/PATCH AJAX. Delete event via DELETE AJAX. All operations return correct JSON response. |
| **Pass Conditions** | (1) POST creates event and returns JSON with event ID. (2) GET with start/end date returns filtered events. (3) PUT/PATCH updates event fields. (4) DELETE removes event (soft delete). (5) All responses include correct Content-Type: application/json. |
| **Fail Conditions** | (1) AJAX endpoint returns HTML instead of JSON. (2) Date filtering incorrect. (3) Update does not persist. |
| **Method** | Automated - AJAX API endpoint test |
| **Test Code** | `tests/verification/test_workflow.py::TestCalendarAPI` |
| **Risk** | **Low** |

### FUNC-022: Messenger Direct/Group Chat Creation

| Item | Details |
|------|---------|
| **ID** | FUNC-022 |
| **Name** | Chat Room Creation and Messaging Workflow Verification |
| **Criteria** | Direct chat: select user -> create 1:1 room -> send/receive messages. Group chat: select multiple users -> create group room -> name room -> all members can send/receive. Room list shows latest message preview. |
| **Pass Conditions** | (1) Direct chat room created between 2 users. (2) Group chat room created with 3+ members. (3) Message sent by user A visible to user B in real time. (4) Room list sorted by last activity. (5) Unread message count displayed per room. |
| **Fail Conditions** | (1) Room creation fails. (2) Message not delivered to participant. (3) Non-member can send to room. |
| **Method** | Manual - Chat room creation and messaging test |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### FUNC-023: Marketplace Order Sync with External Store

| Item | Details |
|------|---------|
| **ID** | FUNC-023 |
| **Name** | External Store Order Import and Mapping Verification |
| **Criteria** | Manual sync button triggers order import from configured marketplace. Imported orders mapped to internal products. Order status synchronized. Sync timestamp recorded. Conflict resolution for product mapping. |
| **Pass Conditions** | (1) Manual sync button triggers API call. (2) External orders imported with correct data mapping. (3) Product mapping resolves external SKU to internal product. (4) Sync timestamp updated after successful sync. (5) Unmapped products flagged for manual mapping. |
| **Fail Conditions** | (1) Sync button does nothing. (2) Order data mapping incorrect. (3) Unmapped products silently skipped. |
| **Method** | Manual - Marketplace sync with test data |
| **Test Code** | Manual test procedure |
| **Risk** | **Medium** |

### FUNC-024: Inquiry AI Auto-Reply Generation

| Item | Details |
|------|---------|
| **ID** | FUNC-024 |
| **Name** | Claude API Auto-Reply Generation Verification |
| **Criteria** | Inquiry received -> AI auto-reply generated via Claude API. Reply based on answer templates and inquiry content. Generated reply editable before sending. API failure gracefully handled. |
| **Pass Conditions** | (1) Auto-reply generated within 10 seconds. (2) Reply content relevant to inquiry topic. (3) Reply editable by staff before sending. (4) API timeout handled (error message, not crash). (5) API key absence shows configuration warning (not 500 error). |
| **Fail Conditions** | (1) Auto-reply generation crashes on API failure. (2) Reply content completely irrelevant. (3) API key exposed in error message. |
| **Method** | Manual - Inquiry auto-reply test with mock/real API |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### FUNC-025: Warranty Serial Number Verification Flow

| Item | Details |
|------|---------|
| **ID** | FUNC-025 |
| **Name** | Warranty Registration and Verification Workflow |
| **Criteria** | Product registered with serial number. QR code generated for verification. Public verification endpoint validates serial + shows warranty status. Expired warranty clearly indicated. Invalid serial returns appropriate message. |
| **Pass Conditions** | (1) Serial number registration succeeds with valid product. (2) QR code generated and downloadable. (3) Verification URL with valid serial returns warranty details. (4) Expired warranty shown as "Expired" with dates. (5) Invalid serial number returns "Not Found" message. |
| **Fail Conditions** | (1) Duplicate serial number accepted. (2) QR code generation fails. (3) Verification endpoint exposes internal data. |
| **Method** | Automated - Warranty registration + verification test |
| **Test Code** | `tests/verification/test_workflow.py::TestWarrantyFlow` |
| **Risk** | **Medium** |

### FUNC-026: Excel Export with Proper Formatting

| Item | Details |
|------|---------|
| **ID** | FUNC-026 |
| **Name** | Excel Export File Quality Verification |
| **Criteria** | Exported Excel files have proper column headers. Number columns formatted as numbers (not text). Date columns formatted as dates. Korean column headers preserved. File downloadable with correct MIME type. |
| **Pass Conditions** | (1) Column headers match model field verbose_name (Korean). (2) Amount fields formatted as number with comma separator. (3) Date fields formatted as YYYY-MM-DD. (4) Response Content-Type is `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. (5) File opens without corruption in Excel/LibreOffice. |
| **Fail Conditions** | (1) Column headers are field names instead of verbose names. (2) Numbers stored as text strings. (3) File corrupted or zero bytes. |
| **Method** | Automated - Export + file content verification |
| **Test Code** | `tests/verification/test_workflow.py::TestExcelExport` |
| **Risk** | **Low** |

### FUNC-027: PDF Generation for Tax Invoices

| Item | Details |
|------|---------|
| **ID** | FUNC-027 |
| **Name** | Tax Invoice PDF Content Accuracy Verification |
| **Criteria** | PDF contains: supplier info, buyer info, item details, supply amount, VAT amount, total amount. Korean font rendered correctly. Layout matches standard Korean tax invoice format. Amounts match database values exactly. |
| **Pass Conditions** | (1) PDF generated for each tax invoice without error. (2) Supplier/buyer names and registration numbers correct. (3) Item table matches database records. (4) Supply + VAT + Total amounts match calculations. (5) PDF is valid (passes PDF/A validation). |
| **Fail Conditions** | (1) PDF amounts differ from database. (2) Korean text unreadable. (3) Required fields missing from PDF. |
| **Method** | Manual - PDF generation + content cross-reference |
| **Test Code** | Manual test procedure |
| **Risk** | **Medium** |

### FUNC-028: Notification Creation on Key Events

| Item | Details |
|------|---------|
| **ID** | FUNC-028 |
| **Name** | Auto-Notification on Business Events Verification |
| **Criteria** | Notifications auto-created on: order status change, approval request, leave request submission, low stock alert, service request received. Notification delivered via WebSocket and stored in DB. |
| **Pass Conditions** | (1) Order SHIPPED creates notification for relevant users. (2) Approval request creates notification for next approver. (3) Leave request submission notifies manager. (4) Low stock threshold triggers notification. (5) All notifications stored in Notification model. |
| **Fail Conditions** | (1) Business event does not trigger notification. (2) Notification sent to wrong user. (3) Notification not persisted in database. |
| **Method** | Automated - Event trigger + notification verification |
| **Test Code** | `tests/verification/test_workflow.py::TestNotifications` |
| **Risk** | **Medium** |

### FUNC-029: Trash/Restore Cycle for Soft-Deleted Items

| Item | Details |
|------|---------|
| **ID** | FUNC-029 |
| **Name** | Trash View and Restore Functionality Verification |
| **Criteria** | Soft-deleted items appear in trash view (core:trash). Admin can restore items from trash. Restored items reappear in normal list views. Permanent deletion (if implemented) requires admin confirmation. |
| **Pass Conditions** | (1) Soft-deleted record appears in trash view. (2) Restore button re-activates record (is_active=True). (3) Restored record visible in normal list view. (4) Trash view shows deletion date and deleted-by user. (5) Non-admin cannot access trash view. |
| **Fail Conditions** | (1) Soft-deleted record not in trash view. (2) Restore fails. (3) Non-admin accesses trash. |
| **Method** | Automated - Soft delete + trash + restore cycle test |
| **Test Code** | `tests/verification/test_workflow.py::TestTrashRestore` |
| **Risk** | **Medium** |

### FUNC-030: Audit Trail Query and Display

| Item | Details |
|------|---------|
| **ID** | FUNC-030 |
| **Name** | Audit Dashboard and History Query Verification |
| **Criteria** | Audit dashboard (core:audit_dashboard) shows recent changes across all models. Filters by user, model, date range work. Individual record history shows field-level changes. Access restricted to admin/manager roles. |
| **Pass Conditions** | (1) Audit dashboard loads with recent change entries. (2) Filter by user shows only that user's changes. (3) Filter by model shows only that model's changes. (4) Date range filter works correctly. (5) Click on entry shows old value -> new value diff. |
| **Fail Conditions** | (1) Audit dashboard empty despite data changes. (2) Filters do not work. (3) Staff user can access audit dashboard. |
| **Method** | Automated - Audit dashboard access + query test |
| **Test Code** | `tests/verification/test_workflow.py::TestAuditDashboard` |
| **Risk** | **Medium** |

---

## 6. Active Directory Integration Verification (AD-001 ~ AD-010)

### AD-001: LDAP Connection

| Item | Details |
|------|---------|
| **ID** | AD-001 |
| **Name** | AD/LDAP Server Connection Verification |
| **Criteria** | LDAP connection to configured AD domain succeeds. SSL/StartTLS encryption works. Bind DN authentication succeeds. Base DN search returns results. Connection timeout and retry configured. |
| **Pass Conditions** | (1) Connection test returns success. (2) SSL/TLS handshake completes without error. (3) Base DN search returns domain info. (4) Invalid credentials produce clear error message. (5) Connection timeout after configured interval (not hanging indefinitely). |
| **Fail Conditions** | (1) Connection failure without clear error message. (2) Unencrypted connection accepted in production. (3) Connection hangs without timeout. |
| **Method** | Automated - ADService.test_connection() test |
| **Test Code** | `apps/ad/tests.py::ADServiceTest::test_connection_test_simulation` |
| **Risk** | **High** |

### AD-002: User Synchronization

| Item | Details |
|------|---------|
| **ID** | AD-002 |
| **Name** | AD -> ERP User Sync Verification |
| **Criteria** | Full sync imports all AD users into ERP. Incremental sync updates changed users only. New AD users create ERP accounts. Disabled AD users deactivate ERP accounts. User attributes (name, email, phone) synced. objectGUID used as stable identifier. |
| **Pass Conditions** | (1) New AD user creates ERP user account. (2) AD user attribute update syncs to ERP user. (3) AD user disabled -> ERP user deactivated. (4) objectGUID links survive DN changes (user moved between OUs). (5) Sync log records accurate create/update/disable counts. |
| **Fail Conditions** | (1) User not synced from AD. (2) Attribute mismatch after sync. (3) Orphaned mappings (AD user deleted, mapping remains). |
| **Method** | Automated - ADService.sync() test with mock LDAP |
| **Test Code** | `apps/ad/tests.py::ADServiceTest::test_sync_simulation` |
| **Risk** | **Critical** |

### AD-003: Group Synchronization

| Item | Details |
|------|---------|
| **ID** | AD-003 |
| **Name** | AD Group -> ERP Group Sync Verification |
| **Criteria** | Security and distribution groups synced. Group membership (memberOf) synced to ADUserMapping.ad_groups M2M. Nested group membership resolved. Group DN used as unique key. |
| **Pass Conditions** | (1) AD groups appear in ADGroup model. (2) User's group memberships match AD memberOf. (3) Group membership changes reflected on next sync. (4) Nested group resolution works. (5) Deleted AD group removed from ERP. |
| **Fail Conditions** | (1) Group missing from sync. (2) Membership mismatch. (3) Stale group data after sync. |
| **Method** | Automated - Group sync test |
| **Test Code** | `apps/ad/tests.py::ADGroupTest` |
| **Risk** | **High** |

### AD-004: OU (Organizational Unit) Sync

| Item | Details |
|------|---------|
| **ID** | AD-004 |
| **Name** | AD OU -> ERP Department Mapping Verification |
| **Criteria** | OU hierarchy synced from AD. OU -> Department mapping configurable. Nested OU parent-child relationships preserved. OU changes reflected on sync. |
| **Pass Conditions** | (1) OUs imported with correct hierarchy. (2) Mapped departments updated accordingly. (3) Parent-child relationships correct. (4) OU rename reflected on sync. (5) New OU auto-discovered. |
| **Fail Conditions** | (1) OU hierarchy broken. (2) Mapping incorrect. (3) New OU not detected. |
| **Method** | Automated - OU sync test |
| **Test Code** | `apps/ad/tests.py::ADOrganizationalUnitTest` |
| **Risk** | **Medium** |

### AD-005: Group Policy -> ERP Role Mapping

| Item | Details |
|------|---------|
| **ID** | AD-005 |
| **Name** | AD Group -> ERP Role Auto-Assignment Verification |
| **Criteria** | ADGroupPolicy rules apply ERP roles based on AD group membership. Priority ordering determines conflict resolution. ASSIGN_ROLE action sets User.role. ASSIGN_DEPARTMENT action links to HR department. Multiple policies resolve by priority (lower = higher priority). |
| **Pass Conditions** | (1) AD group member gets mapped ERP role. (2) Higher priority policy wins conflicts. (3) Role changes when group membership changes. (4) Department assignment works via policy. (5) Policy without matching group has no effect. |
| **Fail Conditions** | (1) Role not assigned from group policy. (2) Priority ignored in conflict. (3) Wrong role applied. |
| **Method** | Automated - Policy application test |
| **Test Code** | `apps/ad/tests.py::ADGroupPolicyTest` |
| **Risk** | **High** |

### AD-006: Sync Error Handling

| Item | Details |
|------|---------|
| **ID** | AD-006 |
| **Name** | AD Sync Error Resilience Verification |
| **Criteria** | Individual user sync failure doesn't abort entire sync. Error count and details logged in ADSyncLog. Partial success status reported. Sync error messages stored per user mapping. Network interruption handled gracefully. |
| **Pass Conditions** | (1) 1 user failure -> sync continues for remaining users. (2) ADSyncLog.status = PARTIAL with accurate error count. (3) Failed user's sync_status = ERROR with error message. (4) Retry succeeds for transient errors. (5) Network timeout doesn't corrupt partial sync data. |
| **Fail Conditions** | (1) Single failure aborts entire sync. (2) Errors not logged in sync log. (3) Partial data left in inconsistent state. |
| **Method** | Automated - Error injection test |
| **Test Code** | `apps/ad/tests.py::ADSyncErrorTest` |
| **Risk** | **High** |

### AD-007: ERP -> AD Bidirectional Sync

| Item | Details |
|------|---------|
| **ID** | AD-007 |
| **Name** | ERP User Deactivation -> AD Mapping Update Verification |
| **Criteria** | ERP user deactivation (is_active=False) updates ADUserMapping.sync_status to DISABLED via signal. Mapping status reflects current state. Manual mapping creation works for non-AD users. |
| **Pass Conditions** | (1) User deactivation sets mapping status to DISABLED. (2) Signal fires on pre_save for User model. (3) Reactivation allows re-sync. (4) Manual mapping creation for non-AD user works. (5) Mapping status queryable for reporting. |
| **Fail Conditions** | (1) Mapping status stale after user state change. (2) Signal not firing. (3) Manual mapping fails. |
| **Method** | Automated - Signal test |
| **Test Code** | `apps/ad/tests.py::ADSignalTest` |
| **Risk** | **Medium** |

### AD-008: AD Credential Security

| Item | Details |
|------|---------|
| **ID** | AD-008 |
| **Name** | AD Bind Password & Connection Security Verification |
| **Criteria** | LDAP bind password stored encrypted or in environment variables. SSL/StartTLS used for all AD connections. Password not logged or exposed in error messages. Admin-only access to AD configuration. |
| **Pass Conditions** | (1) Bind password not in application logs. (2) SSL/TLS verified on every connection. (3) Only admin role can access AD views. (4) Password field uses PasswordInput widget in admin. (5) Connection string does not appear in error tracebacks. |
| **Fail Conditions** | (1) Password in plaintext log entry. (2) Non-admin access to AD config views. (3) Unencrypted LDAP connection in production. |
| **Method** | Manual - Security review of AD configuration |
| **Test Code** | Manual security review |
| **Risk** | **Critical** |

### AD-009: Scheduled Sync (Celery Beat)

| Item | Details |
|------|---------|
| **ID** | AD-009 |
| **Name** | Automatic Periodic AD Sync Verification |
| **Criteria** | Celery Beat schedules `sync_all_domains` task at configured intervals. Only domains with `sync_enabled=True` are synced. Sync interval configurable per domain. Last sync timestamp updated. |
| **Pass Conditions** | (1) Task registered in Celery Beat schedule. (2) Only enabled domains synced. (3) `last_sync_at` updated after sync. (4) Sync log created for each execution. (5) Failed scheduled sync retried on next interval. |
| **Fail Conditions** | (1) Scheduled sync not running. (2) Disabled domains synced. (3) Timestamp not updated. |
| **Method** | Manual - Celery Beat schedule verification |
| **Test Code** | Manual verification |
| **Risk** | **Medium** |

### AD-010: AD Sync Log Audit

| Item | Details |
|------|---------|
| **ID** | AD-010 |
| **Name** | AD Sync Log Completeness Verification |
| **Criteria** | Every sync operation creates ADSyncLog. Log contains: domain, sync_type, status, user counts (created/updated/disabled), error count, error details, duration (started_at to finished_at), triggered_by user. Historical records maintained. |
| **Pass Conditions** | (1) All sync log fields populated correctly. (2) `total_processed` matches actual counts. (3) Duration calculable from timestamps. (4) Logs retained for audit period. (5) Log queryable by domain, date range, status. |
| **Fail Conditions** | (1) Log missing required fields. (2) Counts inaccurate. (3) Logs deleted before audit period. |
| **Method** | Automated - Sync log field verification |
| **Test Code** | `apps/ad/tests.py::ADSyncLogTest` |
| **Risk** | **Medium** |

---

## 7. Disaster Recovery Verification (DR-001 ~ DR-012)

### DR-001: Backup Creation & Restoration

| Item | Details |
|------|---------|
| **ID** | DR-001 |
| **Name** | Data Backup/Restore Verification |
| **Criteria** | `dumpdata` exports complete data. `loaddata` restores without loss. JSON serialization/deserialization lossless. Backup rotation keeps last 7 files. Celery Beat schedules automatic backups. |
| **Pass Conditions** | (1) Backup file created with all model data. (2) Restore to empty database matches original 100%. (3) Old backups cleaned up (>7 files). (4) Automated backup runs on Celery Beat schedule. (5) Backup file integrity verifiable (checksum). |
| **Fail Conditions** | (1) Restore failure or data loss. (2) Backup file corrupted. (3) Automatic backup not running. |
| **Method** | Automated - dumpdata/loaddata cycle test |
| **Test Code** | `tests/verification/test_disaster_recovery.py::TestBackupRestore` |
| **Risk** | **Critical** |

### DR-002: Server Restart Data Persistence

| Item | Details |
|------|---------|
| **ID** | DR-002 |
| **Name** | Service Restart Data Persistence Verification |
| **Criteria** | Docker container restart preserves: DB data (volume), uploaded files (volume), Redis sessions (persistence), static files. No data loss on graceful shutdown. |
| **Pass Conditions** | (1) All data accessible after `docker-compose restart`. (2) User sessions survive restart (Redis persistence or DB backend). (3) Uploaded files intact in volume. (4) Database transactions committed before shutdown. (5) Celery task queue resumes after restart. |
| **Fail Conditions** | (1) Data loss after restart. (2) Sessions invalidated. (3) Uploaded files missing. |
| **Method** | Manual - Docker restart + data verification |
| **Test Code** | Manual test procedure |
| **Risk** | **Critical** |

### DR-003: Transaction Rollback

| Item | Details |
|------|---------|
| **ID** | DR-003 |
| **Name** | Transaction Atomicity Verification |
| **Criteria** | `transaction.atomic()` blocks fully roll back on exception. No partial commits. Production signal code (stock updates) uses atomic transactions. Nested transactions (savepoints) work correctly. |
| **Pass Conditions** | (1) Exception mid-transaction -> all changes rolled back. (2) No orphaned records after rollback. (3) Stock remains consistent after failed operation. (4) Nested savepoint rollback doesn't affect outer transaction. (5) Signal handlers within atomic blocks roll back together. |
| **Fail Conditions** | (1) Partial commit after exception. (2) Orphaned stock movement without product update. (3) Savepoint rollback corrupts outer transaction. |
| **Method** | Automated - Transaction rollback scenario test |
| **Test Code** | `tests/verification/test_disaster_recovery.py::TestTransactionRollback` |
| **Risk** | **Critical** |

### DR-004: Concurrent Modification Conflict

| Item | Details |
|------|---------|
| **ID** | DR-004 |
| **Name** | Race Condition Prevention Verification |
| **Criteria** | Stock updates use F() expressions. 100 concurrent updates produce correct result. No deadlocks under contention. Optimistic locking or atomic operations for all financial data. |
| **Pass Conditions** | (1) 100 concurrent stock changes: final stock equals initial + sum of all changes. (2) No deadlock exceptions raised. (3) All operations complete within timeout. (4) F() expression used in all stock signal handlers. (5) Financial calculations (AR/AP) also use atomic operations. |
| **Fail Conditions** | (1) Lost updates (final stock incorrect). (2) Deadlock under contention. (3) Operation timeout. |
| **Method** | Automated - Multi-threaded concurrent update test |
| **Test Code** | `tests/verification/test_disaster_recovery.py::TestConcurrentModification` |
| **Risk** | **Critical** |

### DR-005: Health Check Endpoint

| Item | Details |
|------|---------|
| **ID** | DR-005 |
| **Name** | Service Health Check Verification |
| **Criteria** | Health check endpoint verifies: DB connectivity, Redis connectivity, disk space, service uptime. Returns 200 (healthy) or 503 (unhealthy). Prometheus metrics endpoint accessible. |
| **Pass Conditions** | (1) Healthy state returns 200 OK with component statuses. (2) DB down returns 503 with database status "unhealthy". (3) Prometheus `/metrics` returns valid Prometheus format. (4) Grafana dashboards load correctly. (5) Health check response time <100ms. |
| **Fail Conditions** | (1) Health check not implemented. (2) Returns 200 when DB is down. (3) Prometheus metrics endpoint inaccessible. |
| **Method** | Manual - Health check endpoint call + service down test |
| **Test Code** | Manual test procedure |
| **Risk** | **High** |

### DR-006: Data Corruption Recovery

| Item | Details |
|------|---------|
| **ID** | DR-006 |
| **Name** | Stock Recalculation & Data Repair Verification |
| **Criteria** | Management command available to recalculate all product stocks from StockMovement history. Recalculated stock matches expected values. Discrepancies logged and alertable. |
| **Pass Conditions** | (1) Recalculation command runs without error. (2) Post-recalculation: all stocks match movement history sums. (3) Discrepancy report generated listing affected products. (4) Recalculation idempotent (running twice produces same result). (5) Recalculation runs within acceptable time (< 5min for 10K products). |
| **Fail Conditions** | (1) Recalculation produces incorrect results. (2) No discrepancy report generated. (3) Command crashes mid-execution. |
| **Method** | Manual - Intentional corruption + recalculation test |
| **Test Code** | Manual test procedure |
| **Risk** | **High** |

### DR-007: Log Retention & Rotation

| Item | Details |
|------|---------|
| **ID** | DR-007 |
| **Name** | Log File Management Verification |
| **Criteria** | Application logs rotated (size or time-based). Backup files retain last 7. AD sync logs retained for audit period. Notification cleanup runs on schedule (90-day archive, 180-day delete). Disk usage monitored. |
| **Pass Conditions** | (1) Log rotation configured in Django LOGGING settings. (2) Old backups cleaned (>7 files removed). (3) Notification cleanup Celery task runs on schedule. (4) Disk usage below 80% threshold. (5) Log files accessible for debugging within retention period. |
| **Fail Conditions** | (1) Unbounded log growth filling disk. (2) Premature log deletion (within retention period). (3) No cleanup for old notifications/backups. |
| **Method** | Manual - Log/backup file inspection |
| **Test Code** | Manual inspection |
| **Risk** | **Medium** |

### DR-008: Redis Cache Failure Graceful Degradation

| Item | Details |
|------|---------|
| **ID** | DR-008 |
| **Name** | Redis Outage Handling Verification |
| **Criteria** | Application continues to function (degraded mode) when Redis is unavailable. Cache misses fall through to database queries. WebSocket features degrade gracefully (show "offline" status). Session backend fallback configured (or DB sessions). |
| **Pass Conditions** | (1) Application serves pages when Redis is down (slower but functional). (2) Cache.get() returns None (not exception) when Redis offline. (3) Dashboard loads from database instead of cache. (4) WebSocket shows "connection lost" message. (5) User sessions maintained via DB backend fallback. |
| **Fail Conditions** | (1) Application crashes when Redis unavailable. (2) Unhandled ConnectionError on cache access. (3) User logged out when Redis restarts. |
| **Method** | Manual - Stop Redis container + application behavior test |
| **Test Code** | Manual test procedure |
| **Risk** | **High** |

### DR-009: Celery Worker Crash Recovery

| Item | Details |
|------|---------|
| **ID** | DR-009 |
| **Name** | Celery Worker Restart and Task Recovery Verification |
| **Criteria** | Celery worker auto-restarts after crash (Docker restart policy). In-progress tasks re-queued or marked failed. Scheduled tasks (Beat) resume after worker recovery. No duplicate task execution on recovery. |
| **Pass Conditions** | (1) Docker restart policy restarts crashed worker within 30s. (2) Incomplete task state resolved (failed or retried). (3) Beat-scheduled tasks execute on next interval after recovery. (4) No duplicate task execution after restart. (5) Task queue depth returns to normal after recovery. |
| **Fail Conditions** | (1) Worker stays down after crash. (2) Tasks lost permanently. (3) Duplicate execution after restart. |
| **Method** | Manual - Kill Celery worker + recovery verification |
| **Test Code** | Manual test procedure |
| **Risk** | **Medium** |

### DR-010: WebSocket Reconnection Handling

| Item | Details |
|------|---------|
| **ID** | DR-010 |
| **Name** | WebSocket Client Reconnection Verification |
| **Criteria** | Client-side JavaScript automatically reconnects WebSocket after disconnection. Exponential backoff on reconnection attempts. Missed messages retrieved on reconnection. User notified of connection status. |
| **Pass Conditions** | (1) WebSocket reconnects within 5s after server restart. (2) Reconnection uses exponential backoff (1s, 2s, 4s, 8s). (3) Chat messages sent during disconnection retrieved on reconnect. (4) Connection status indicator shows offline/reconnecting/online. (5) Max reconnection attempts limited (no infinite loop). |
| **Fail Conditions** | (1) No automatic reconnection. (2) Immediate rapid-fire reconnection attempts (no backoff). (3) Messages lost during disconnection. |
| **Method** | Manual - Network interruption + reconnection test |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### DR-011: Database Connection Timeout Recovery

| Item | Details |
|------|---------|
| **ID** | DR-011 |
| **Name** | Database Connection Loss Recovery Verification |
| **Criteria** | Application recovers from temporary database outage. Connection pool refreshes stale connections. User sees appropriate error page during outage. Application auto-recovers when database returns. |
| **Pass Conditions** | (1) Database restart (30s outage): application recovers within 60s. (2) Stale connections purged from pool. (3) Custom 503 "Service Unavailable" page shown during outage. (4) First request after recovery succeeds (new connection). (5) No data corruption from connection drop. |
| **Fail Conditions** | (1) Application hangs permanently after DB restart. (2) Stale connection errors persist after DB recovery. (3) Data corruption from interrupted transaction. |
| **Method** | Manual - Database restart + application recovery test |
| **Test Code** | Manual test procedure |
| **Risk** | **High** |

### DR-012: Partial Migration Rollback Capability

| Item | Details |
|------|---------|
| **ID** | DR-012 |
| **Name** | Migration Rollback Safety Verification |
| **Criteria** | Critical migrations are reversible (`RunPython` operations have reverse functions). Migration rollback restores previous schema. Data migrations preserve data on rollback. Non-reversible migrations documented. |
| **Pass Conditions** | (1) `migrate app_name XXXX` (previous migration) rolls back schema successfully. (2) Data preserved after rollback. (3) Forward re-migration succeeds after rollback. (4) Non-reversible migrations listed in deployment checklist. (5) Pre-migration backup procedure documented. |
| **Fail Conditions** | (1) Migration rollback fails with error. (2) Data lost during rollback. (3) Schema in inconsistent state after rollback. |
| **Method** | Automated - Migration forward/backward test |
| **Test Code** | `tests/verification/test_disaster_recovery.py::TestMigrationRollback` |
| **Risk** | **High** |

---

## 8. Integration & Deployment Verification (DEPLOY-001 ~ DEPLOY-010)

### DEPLOY-001: Docker Compose Stack

| Item | Details |
|------|---------|
| **ID** | DEPLOY-001 |
| **Name** | Full Docker Stack Startup Verification |
| **Criteria** | `docker-compose up -d` starts all 7 services: web (Daphne), db (PostgreSQL 16), redis (Redis 7), celery_worker, celery_beat, prometheus, grafana. All services healthy. Inter-service communication works. |
| **Pass Conditions** | (1) All containers in "running" state. (2) Web responds on port 8000. (3) Prometheus scrapes metrics from web. (4) Grafana loads configured dashboards. (5) Celery worker connects to Redis broker and processes test task. |
| **Fail Conditions** | (1) Any container fails to start. (2) Inter-service network communication broken. (3) Health check fails for any service. |
| **Method** | Manual - Docker Compose full stack test |
| **Test Code** | Manual test procedure |
| **Risk** | **High** |

### DEPLOY-002: Database Migration

| Item | Details |
|------|---------|
| **ID** | DEPLOY-002 |
| **Name** | Migration Completeness & Safety Verification |
| **Criteria** | `python manage.py migrate` runs without error. No unapplied migrations. Migrations are reversible (where possible). No data loss during migration. |
| **Pass Conditions** | (1) `showmigrations` shows all applied (no `[ ]` unchecked). (2) `migrate` completes cleanly on fresh database. (3) Post-migration data intact on existing database. (4) No migration conflicts (multiple leaf nodes). (5) Migration time < 5 minutes for standard deployment. |
| **Fail Conditions** | (1) Migration error on any app. (2) Data loss during migration. (3) Conflicting migrations detected. |
| **Method** | Automated - Migration + data verification test |
| **Test Code** | CI/CD pipeline step |
| **Risk** | **Critical** |

### DEPLOY-003: Static File Collection

| Item | Details |
|------|---------|
| **ID** | DEPLOY-003 |
| **Name** | Static File Serving Verification |
| **Criteria** | `collectstatic` gathers all files. WhiteNoise serves compressed assets. CSS/JS/images load correctly in production mode. PWA manifest and service worker accessible. |
| **Pass Conditions** | (1) `collectstatic` completes without errors. (2) Static files accessible via browser (200 status). (3) No 404 on any referenced static asset. (4) PWA manifest.json accessible. (5) Service worker (sw.js) registerable. |
| **Fail Conditions** | (1) Missing static files. (2) Compression failure. (3) PWA assets inaccessible. |
| **Method** | Manual - Production mode static file check |
| **Test Code** | Manual test procedure |
| **Risk** | **Medium** |

### DEPLOY-004: Environment Variable Configuration

| Item | Details |
|------|---------|
| **ID** | DEPLOY-004 |
| **Name** | Required Environment Variable Verification |
| **Criteria** | All required env vars documented and validated: SECRET_KEY, DATABASE_URL, REDIS_URL, ALLOWED_HOSTS, DJANGO_SETTINGS_MODULE. Missing required var produces clear startup error. Sensitive vars not logged. |
| **Pass Conditions** | (1) Missing SECRET_KEY raises ImproperlyConfigured error with clear message. (2) All vars documented in .env.example. (3) Docker Compose sets all required vars. (4) Sensitive vars not in startup log output. (5) Default values only for non-sensitive settings. |
| **Fail Conditions** | (1) Silent failure on missing env var. (2) Secret value logged at startup. (3) Missing documentation for required var. |
| **Method** | Automated - Startup validation test |
| **Test Code** | CI/CD pipeline step |
| **Risk** | **High** |

### DEPLOY-005: CI/CD Pipeline

| Item | Details |
|------|---------|
| **ID** | DEPLOY-005 |
| **Name** | GitHub Actions Pipeline Verification |
| **Criteria** | Pipeline runs: lint, unit tests, verification tests, security scan, Docker build. All steps must pass before merge. Test coverage reported. Deployment only on main branch. |
| **Pass Conditions** | (1) Pipeline completes successfully on clean code. (2) Failed test blocks merge (branch protection). (3) Coverage >= 70%. (4) Docker image builds successfully. (5) Pipeline completes within 15 minutes. |
| **Fail Conditions** | (1) Pipeline can be bypassed. (2) Broken test doesn't block merge. (3) Coverage below threshold. |
| **Method** | Manual - Pipeline execution review |
| **Test Code** | `.github/workflows/` |
| **Risk** | **Medium** |

### DEPLOY-006: Zero-Downtime Deployment Procedure

| Item | Details |
|------|---------|
| **ID** | DEPLOY-006 |
| **Name** | Rolling Update Deployment Verification |
| **Criteria** | Deployment procedure minimizes downtime. Database migrations run before new code deployment. Health check gates traffic to new instances. Old instances drain connections gracefully. Rollback procedure documented and tested. |
| **Pass Conditions** | (1) Deployment completes with < 30s perceived downtime. (2) Migrations applied before code switch. (3) Health check prevents traffic to unhealthy instance. (4) Active requests complete before old instance shutdown. (5) Rollback to previous version executable within 5 minutes. |
| **Fail Conditions** | (1) Deployment causes > 5 minute downtime. (2) Requests dropped during deployment. (3) No rollback procedure. |
| **Method** | Manual - Deployment procedure dry run |
| **Test Code** | Deployment runbook |
| **Risk** | **High** |

### DEPLOY-007: Database Backup Before Migration

| Item | Details |
|------|---------|
| **ID** | DEPLOY-007 |
| **Name** | Pre-Migration Backup Procedure Verification |
| **Criteria** | Automated database backup executed before every migration. Backup verified (file exists, non-zero size). Backup retention matches policy. Restore from backup tested quarterly. |
| **Pass Conditions** | (1) Pre-migration backup created automatically. (2) Backup file size > 0 bytes. (3) Backup file named with timestamp for identification. (4) Restore from backup produces functional database. (5) Backup procedure documented in deployment checklist. |
| **Fail Conditions** | (1) Migration runs without backup. (2) Backup file corrupted or empty. (3) Restore from backup fails. |
| **Method** | Manual - Migration deployment procedure test |
| **Test Code** | Deployment runbook |
| **Risk** | **Critical** |

### DEPLOY-008: Health Check Endpoint Availability

| Item | Details |
|------|---------|
| **ID** | DEPLOY-008 |
| **Name** | Health Check Endpoint Configuration Verification |
| **Criteria** | Health check endpoint accessible without authentication. Returns JSON with component statuses. Docker health check configured. Load balancer health check compatible. Response time < 100ms. |
| **Pass Conditions** | (1) `/health/` endpoint returns 200 with JSON body. (2) JSON includes database, redis, disk status fields. (3) Dockerfile HEALTHCHECK directive configured. (4) Health check does not require authentication. (5) Response within 100ms under normal conditions. |
| **Fail Conditions** | (1) No health check endpoint. (2) Health check requires authentication. (3) Health check response time > 1000ms. |
| **Method** | Automated - Health endpoint response test |
| **Test Code** | CI/CD pipeline step |
| **Risk** | **Medium** |

### DEPLOY-009: Log Aggregation and Retention

| Item | Details |
|------|---------|
| **ID** | DEPLOY-009 |
| **Name** | Centralized Logging Configuration Verification |
| **Criteria** | Application logs written to stdout/stderr for Docker log collection. Log format structured (JSON) for parseability. Log levels appropriate (DEBUG in dev, WARNING+ in prod). Log retention period configured. Error logs trigger alerts. |
| **Pass Conditions** | (1) Docker logs show application output. (2) Log entries parseable as structured format. (3) Production log level = WARNING or above. (4) Error-level logs trigger Sentry alert. (5) Log retention configured in Docker/infrastructure. |
| **Fail Conditions** | (1) Logs only written to file (not stdout). (2) Unstructured log format. (3) DEBUG-level logging in production. |
| **Method** | Manual - Docker log inspection + log level verification |
| **Test Code** | Manual inspection |
| **Risk** | **Medium** |

### DEPLOY-010: Secret Rotation Procedure

| Item | Details |
|------|---------|
| **ID** | DEPLOY-010 |
| **Name** | Secret Key and Credential Rotation Verification |
| **Criteria** | Procedure documented for rotating: SECRET_KEY, database password, Redis password, API keys. Rotation causes minimal or no downtime. Old secrets invalidated after rotation. Rotation frequency defined. |
| **Pass Conditions** | (1) SECRET_KEY rotation procedure documented and tested. (2) Database password change propagated to all services. (3) Redis password rotation tested. (4) API key rotation does not break integrations. (5) Rotation runbook reviewed quarterly. |
| **Fail Conditions** | (1) No rotation procedure documented. (2) Rotation causes extended downtime. (3) Old secrets not invalidated. |
| **Method** | Manual - Secret rotation dry run |
| **Test Code** | Security runbook |
| **Risk** | **High** |

---

## 9. Compatibility Verification (COMPAT-001 ~ COMPAT-005)

### COMPAT-001: Browser Compatibility

| Item | Details |
|------|---------|
| **ID** | COMPAT-001 |
| **Name** | Cross-Browser Rendering & Functionality Verification |
| **Criteria** | Application renders correctly and all features function in: Chrome (latest 2 versions), Firefox (latest 2 versions), Safari (latest 2 versions), Edge (latest 2 versions). No browser-specific JavaScript errors. |
| **Pass Conditions** | (1) Dashboard renders correctly in all 4 browsers. (2) Forms submit and validate in all browsers. (3) HTMX partial page updates work in all browsers. (4) Alpine.js interactions (dropdowns, modals) function in all browsers. (5) No JavaScript console errors in any browser. |
| **Fail Conditions** | (1) Layout broken in any supported browser. (2) Form submission fails in specific browser. (3) JavaScript error blocks functionality. |
| **Method** | Manual - Cross-browser testing (BrowserStack or manual) |
| **Test Code** | `e2e/` (Playwright tests with multiple browsers) |
| **Risk** | **Medium** |

### COMPAT-002: Mobile Responsive Layout

| Item | Details |
|------|---------|
| **ID** | COMPAT-002 |
| **Name** | Mobile Device Responsive Design Verification |
| **Criteria** | Tailwind CSS responsive classes produce usable layout on mobile (320px-768px). Navigation accessible via hamburger menu. Tables scroll horizontally on small screens. Forms usable on touch devices. No horizontal overflow. |
| **Pass Conditions** | (1) Dashboard readable on 375px width (iPhone). (2) Sidebar collapses to hamburger menu on mobile. (3) Data tables horizontally scrollable without page overflow. (4) Form inputs have adequate touch target size (min 44px). (5) No content clipped or hidden on mobile. |
| **Fail Conditions** | (1) Layout broken on mobile viewport. (2) Navigation inaccessible on mobile. (3) Content requires pinch-zoom to read. |
| **Method** | Manual - Mobile device testing + Chrome DevTools responsive mode |
| **Test Code** | `e2e/` (Playwright with mobile viewport) |
| **Risk** | **Medium** |

### COMPAT-003: PWA Installability

| Item | Details |
|------|---------|
| **ID** | COMPAT-003 |
| **Name** | Progressive Web App Installation Verification |
| **Criteria** | `manifest.json` properly configured with name, icons, start_url, display mode. Service worker (`sw.js`) registers and caches static assets. App installable from Chrome "Add to Home Screen". Installed app opens in standalone mode. |
| **Pass Conditions** | (1) `manifest.json` accessible and valid JSON. (2) Service worker registers without error. (3) Chrome shows "Install" prompt (Lighthouse PWA audit passes). (4) Installed app opens in standalone window (no browser chrome). (5) App icon displayed correctly on home screen. |
| **Fail Conditions** | (1) manifest.json missing or malformed. (2) Service worker registration fails. (3) App not installable. |
| **Method** | Manual - PWA Lighthouse audit + installation test |
| **Test Code** | Lighthouse PWA audit |
| **Risk** | **Low** |

### COMPAT-004: i18n Language Switching

| Item | Details |
|------|---------|
| **ID** | COMPAT-004 |
| **Name** | Internationalization Language Toggle Verification |
| **Criteria** | Language switch between Korean (ko) and English (en) works. All `{% trans %}` tagged strings translated. Date/number formatting follows locale. Language preference persisted across sessions. `compilemessages` produces valid .mo files. |
| **Pass Conditions** | (1) Language switch from ko to en changes all UI text. (2) No untranslated `{% trans %}` strings in English mode. (3) Date format: ko = YYYY-MM-DD, en = MMM DD, YYYY (or configured). (4) Number format: ko = 1,000, en = 1,000 (comma separator). (5) Language preference saved in session/cookie. |
| **Fail Conditions** | (1) Language switch has no effect. (2) Mixed language content (some ko, some en). (3) Date/number format doesn't change with locale. |
| **Method** | Manual - Language switch + UI inspection |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### COMPAT-005: Timezone Handling (Asia/Seoul)

| Item | Details |
|------|---------|
| **ID** | COMPAT-005 |
| **Name** | Timezone Configuration and Display Verification |
| **Criteria** | `TIME_ZONE = 'Asia/Seoul'` in settings. All timestamps displayed in KST (UTC+9). Database stores timestamps in UTC (USE_TZ=True). Attendance check-in/out times in KST. Celery Beat schedules run in configured timezone. |
| **Pass Conditions** | (1) `TIME_ZONE = 'Asia/Seoul'` confirmed in settings. (2) `USE_TZ = True` confirmed. (3) Displayed timestamps match KST. (4) Database timestamps stored in UTC. (5) Celery Beat task execution times align with KST schedule. |
| **Fail Conditions** | (1) Times displayed in UTC instead of KST. (2) `USE_TZ = False` causing naive datetime issues. (3) Attendance times in wrong timezone. |
| **Method** | Automated - Timezone display verification test |
| **Test Code** | `tests/verification/test_workflow.py::TestTimezone` |
| **Risk** | **Medium** |

---

## 10. User Experience Verification (UX-001 ~ UX-005)

### UX-001: Form Validation Error Display

| Item | Details |
|------|---------|
| **ID** | UX-001 |
| **Name** | Form Error Message Display Quality Verification |
| **Criteria** | All form validation errors displayed inline next to the field. Error messages in Korean (user-friendly, not technical). Non-field errors displayed at form top. Form preserves user input on validation failure (no re-entry required). Error styling consistent across all forms. |
| **Pass Conditions** | (1) Required field left blank shows "이 필드는 필수입니다" below the field. (2) Invalid email format shows specific error message. (3) Form retains all entered values after validation error. (4) Error fields highlighted with red border (Tailwind `border-red-500`). (5) All forms use consistent error display pattern (BaseForm). |
| **Fail Conditions** | (1) Error message displayed in English on Korean locale. (2) Form clears all input on validation error. (3) Error displayed as raw Python exception. |
| **Method** | Manual - Form submission with invalid data across multiple forms |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### UX-002: Loading State Indicators

| Item | Details |
|------|---------|
| **ID** | UX-002 |
| **Name** | Loading and Processing State Feedback Verification |
| **Criteria** | HTMX requests show loading indicator. Form submit buttons disabled during processing (prevent double-submit). Long-running operations show progress feedback. Page transitions indicate loading state. |
| **Pass Conditions** | (1) HTMX request shows spinner or loading indicator. (2) Submit button disabled after click (prevents double-submit). (3) Excel export shows "Processing..." message. (4) HTMX indicator element configured for partial updates. (5) No "frozen" UI state during AJAX operations. |
| **Fail Conditions** | (1) No loading feedback on slow operations. (2) Double-submit possible (two orders created). (3) UI appears frozen during background operation. |
| **Method** | Manual - UI interaction with throttled network |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### UX-003: Pagination Consistency Across All List Views

| Item | Details |
|------|---------|
| **ID** | UX-003 |
| **Name** | List View Pagination UI Consistency Verification |
| **Criteria** | All list views use same pagination component. Page numbers, previous/next buttons displayed. Current page highlighted. Total record count shown. Consistent page size (20 items default). |
| **Pass Conditions** | (1) All list views show pagination when records > page_size. (2) Pagination UI component identical across all views. (3) Current page number highlighted/active. (4) "Showing X-Y of Z results" text present. (5) First/Last page navigation available. |
| **Fail Conditions** | (1) Some list views missing pagination. (2) Inconsistent pagination UI between views. (3) No record count displayed. |
| **Method** | Manual - Visual comparison of pagination across 10+ list views |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### UX-004: Sidebar Navigation Completeness

| Item | Details |
|------|---------|
| **ID** | UX-004 |
| **Name** | Navigation Menu Completeness & Structure Verification |
| **Criteria** | Sidebar navigation includes links to all 18 app modules. Menu items grouped logically. Active page highlighted in navigation. Sub-menus expandable/collapsible. Navigation accessible on all pages. |
| **Pass Conditions** | (1) All 18 apps represented in sidebar navigation. (2) Menu items grouped: ERP (inventory, production, sales, purchase, accounting), Groupware (HR, attendance, board, calendar, messenger), etc. (3) Current page's menu item highlighted. (4) Sub-menu expands on click/hover. (5) Navigation consistent across all pages. |
| **Fail Conditions** | (1) App module missing from navigation. (2) Dead link in navigation. (3) Active page not highlighted. |
| **Method** | Manual - Navigation walkthrough of all menu items |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

### UX-005: Keyboard Navigation Support

| Item | Details |
|------|---------|
| **ID** | UX-005 |
| **Name** | Keyboard Accessibility Verification |
| **Criteria** | Tab key navigates through interactive elements in logical order. Enter key activates buttons and links. Escape key closes modals and dropdowns. Focus indicators visible on all interactive elements. Skip navigation link for screen readers. |
| **Pass Conditions** | (1) Tab key traverses form fields in correct order. (2) Enter key submits focused form. (3) Escape key closes open modal/dropdown. (4) Focus ring visible on all buttons, links, and inputs. (5) No keyboard trap (can always Tab away from any element). |
| **Fail Conditions** | (1) Tab order illogical or skips elements. (2) Interactive element unreachable via keyboard. (3) Modal traps keyboard focus permanently. |
| **Method** | Manual - Keyboard-only navigation test |
| **Test Code** | Manual test procedure |
| **Risk** | **Low** |

---

## 11. Verification Results Template

### 11.1 Execution Summary

| Item | Value |
|------|-------|
| Verification Date | YYYY-MM-DD HH:MM |
| Environment | Development / Staging / Production |
| Executor | |
| Total Items | 165 |
| Pass | |
| Fail | |
| N/A | |
| Pass Rate | |

### 11.2 Results by Category

| Category | Items | Pass | Fail | N/A | Pass Rate |
|----------|-------|------|------|-----|-----------|
| Security (SEC-001~035) | 35 | | | | |
| Data Integrity (INT-001~030) | 30 | | | | |
| Performance (PERF-001~015) | 15 | | | | |
| Functional Workflow (FUNC-001~030) | 30 | | | | |
| AD Integration (AD-001~010) | 10 | | | | |
| Disaster Recovery (DR-001~012) | 12 | | | | |
| Deployment (DEPLOY-001~010) | 10 | | | | |
| Compatibility (COMPAT-001~005) | 5 | | | | |
| User Experience (UX-001~005) | 5 | | | | |
| **Total** | **165** | | | | |

### 11.3 Risk Distribution

| Risk Level | Count | Pass | Fail | Coverage |
|------------|-------|------|------|----------|
| Critical | 28 | | | |
| High | 52 | | | |
| Medium | 55 | | | |
| Low | 30 | | | |

### 11.4 Item-Level Results

#### Security (SEC-001 ~ SEC-035)

| ID | Name | Risk | Result | Date | Tester | Notes |
|----|------|------|--------|------|--------|-------|
| SEC-001 | SQL Injection Defense | Critical | | | | |
| SEC-002 | XSS Defense | Critical | | | | |
| SEC-003 | CSRF Token | High | | | | |
| SEC-004 | Auth Bypass Prevention | Critical | | | | |
| SEC-005 | RBAC Verification | Critical | | | | |
| SEC-006 | Password Policy Enforcement | High | | | | |
| SEC-007 | Session Management | High | | | | |
| SEC-008 | Brute-Force Prevention | High | | | | |
| SEC-009 | File Upload Validation | High | | | | |
| SEC-010 | Security Headers | Medium | | | | |
| SEC-011 | Error Disclosure Prevention | High | | | | |
| SEC-012 | API Authentication | Critical | | | | |
| SEC-013 | CORS Policy | Medium | | | | |
| SEC-014 | Sensitive Data Protection | Critical | | | | |
| SEC-015 | Audit Trail | Medium | | | | |
| SEC-016 | Access Logging | Medium | | | | |
| SEC-017 | Rate Limiting | Medium | | | | |
| SEC-018 | Dependency Vulnerability | High | | | | |
| SEC-019 | Container Security | High | | | | |
| SEC-020 | Input Validation | Medium | | | | |
| SEC-021 | Password History & Change | High | | | | |
| SEC-022 | Session Fixation Prevention | High | | | | |
| SEC-023 | Clickjacking Protection | Medium | | | | |
| SEC-024 | CSP Headers | Medium | | | | |
| SEC-025 | CORS Preflight Validation | Medium | | | | |
| SEC-026 | JWT Revocation on Password Change | High | | | | |
| SEC-027 | API Throttling Per Endpoint | Medium | | | | |
| SEC-028 | Malicious File Upload Scanning | High | | | | |
| SEC-029 | Search Parameter SQL Injection | Critical | | | | |
| SEC-030 | Mass Assignment Protection | High | | | | |
| SEC-031 | IDOR Prevention | Critical | | | | |
| SEC-032 | Account Enumeration Prevention | Medium | | | | |
| SEC-033 | Error Page Data Exposure | Medium | | | | |
| SEC-034 | HTTP Header Completeness | Medium | | | | |
| SEC-035 | Admin Panel Path Obfuscation | Low | | | | |

#### Data Integrity (INT-001 ~ INT-030)

| ID | Name | Risk | Result | Date | Tester | Notes |
|----|------|------|--------|------|--------|-------|
| INT-001 | Stock Consistency | Critical | | | | |
| INT-002 | Order Amount Calculation | Critical | | | | |
| INT-003 | Double-Entry Balance | Critical | | | | |
| INT-004 | BOM Effective Qty | High | | | | |
| INT-005 | Production Auto-Stock | Critical | | | | |
| INT-006 | Shipment Auto-Stock | Critical | | | | |
| INT-007 | AR Consistency | High | | | | |
| INT-008 | Soft Delete | High | | | | |
| INT-009 | Unique Constraints | High | | | | |
| INT-010 | FK Referential Integrity | Critical | | | | |
| INT-011 | Purchase Auto-Stock | Critical | | | | |
| INT-012 | Quote Conversion Integrity | High | | | | |
| INT-013 | Concurrent Stock Safety | Critical | | | | |
| INT-014 | AP Consistency | High | | | | |
| INT-015 | Commission Calculation | Medium | | | | |
| INT-016 | Voucher Double-Entry Balance | Critical | | | | |
| INT-017 | BOM Cost Rollup | High | | | | |
| INT-018 | Tax Invoice Amount | High | | | | |
| INT-019 | Leave Balance Calculation | Medium | | | | |
| INT-020 | Attendance Non-Overlap | Medium | | | | |
| INT-021 | Comment Tree Integrity | Low | | | | |
| INT-022 | Chat Message Ordering | Medium | | | | |
| INT-023 | Equity Percentage Validation | High | | | | |
| INT-024 | Warranty Expiry Calculation | Medium | | | | |
| INT-025 | Stock Transfer Atomicity | Critical | | | | |
| INT-026 | Multi-Currency Conversion | Medium | | | | |
| INT-027 | Soft Delete Cascade | Medium | | | | |
| INT-028 | HistoricalRecords Completeness | Medium | | | | |
| INT-029 | created_by Auto-Population | Medium | | | | |
| INT-030 | Code Uniqueness Enforcement | High | | | | |

#### Performance (PERF-001 ~ PERF-015)

| ID | Name | Risk | Result | Date | Tester | Notes |
|----|------|------|--------|------|--------|-------|
| PERF-001 | Page Response Time | Medium | | | | |
| PERF-002 | N+1 Query Prevention | High | | | | |
| PERF-003 | Concurrent User Load | Medium | | | | |
| PERF-004 | Large Dataset Pagination | Medium | | | | |
| PERF-005 | Cache Effectiveness | Low | | | | |
| PERF-006 | Index Coverage | Medium | | | | |
| PERF-007 | WebSocket Scalability | Low | | | | |
| PERF-008 | Dashboard Query Count | Medium | | | | |
| PERF-009 | Pagination Efficiency | Medium | | | | |
| PERF-010 | Excel Export Memory | Medium | | | | |
| PERF-011 | WebSocket + HTTP Load | Low | | | | |
| PERF-012 | Celery Queue Throughput | Medium | | | | |
| PERF-013 | Static File Serving | Low | | | | |
| PERF-014 | DB Connection Pooling | Medium | | | | |
| PERF-015 | Cache Hit Ratio | Low | | | | |

#### Functional Workflow (FUNC-001 ~ FUNC-030)

| ID | Name | Risk | Result | Date | Tester | Notes |
|----|------|------|--------|------|--------|-------|
| FUNC-001 | Order Lifecycle | Critical | | | | |
| FUNC-002 | Production Lifecycle | Critical | | | | |
| FUNC-003 | Purchase Lifecycle | Critical | | | | |
| FUNC-004 | Service Lifecycle | Medium | | | | |
| FUNC-005 | Approval Workflow | High | | | | |
| FUNC-006 | Quote->Order Conversion | High | | | | |
| FUNC-007 | Login/Logout/Lockout | Critical | | | | |
| FUNC-008 | Excel Import/Export | Low | | | | |
| FUNC-009 | PDF Generation | Low | | | | |
| FUNC-010 | Real-Time Notifications | Low | | | | |
| FUNC-011 | Attendance Check-In/Out | Medium | | | | |
| FUNC-012 | Board & Comments | Low | | | | |
| FUNC-013 | Calendar Events | Low | | | | |
| FUNC-014 | Messenger Chat | Low | | | | |
| FUNC-015 | Marketplace Sync | Medium | | | | |
| FUNC-016 | Purchase Full Flow | Critical | | | | |
| FUNC-017 | Accounting Approval | High | | | | |
| FUNC-018 | HR Personnel Action | Medium | | | | |
| FUNC-019 | Leave Request Lifecycle | Medium | | | | |
| FUNC-020 | Nested Comments (3 Levels) | Low | | | | |
| FUNC-021 | Calendar AJAX CRUD | Low | | | | |
| FUNC-022 | Messenger Chat Creation | Low | | | | |
| FUNC-023 | Marketplace Order Sync | Medium | | | | |
| FUNC-024 | AI Auto-Reply | Low | | | | |
| FUNC-025 | Warranty Verification | Medium | | | | |
| FUNC-026 | Excel Export Formatting | Low | | | | |
| FUNC-027 | Tax Invoice PDF | Medium | | | | |
| FUNC-028 | Auto-Notifications | Medium | | | | |
| FUNC-029 | Trash/Restore Cycle | Medium | | | | |
| FUNC-030 | Audit Trail Display | Medium | | | | |

#### AD Integration (AD-001 ~ AD-010)

| ID | Name | Risk | Result | Date | Tester | Notes |
|----|------|------|--------|------|--------|-------|
| AD-001 | LDAP Connection | High | | | | |
| AD-002 | User Synchronization | Critical | | | | |
| AD-003 | Group Synchronization | High | | | | |
| AD-004 | OU Sync | Medium | | | | |
| AD-005 | Group Policy Mapping | High | | | | |
| AD-006 | Sync Error Handling | High | | | | |
| AD-007 | Bidirectional Sync | Medium | | | | |
| AD-008 | Credential Security | Critical | | | | |
| AD-009 | Scheduled Sync | Medium | | | | |
| AD-010 | Sync Log Audit | Medium | | | | |

#### Disaster Recovery (DR-001 ~ DR-012)

| ID | Name | Risk | Result | Date | Tester | Notes |
|----|------|------|--------|------|--------|-------|
| DR-001 | Backup/Restore | Critical | | | | |
| DR-002 | Restart Persistence | Critical | | | | |
| DR-003 | Transaction Rollback | Critical | | | | |
| DR-004 | Concurrent Modification | Critical | | | | |
| DR-005 | Health Check | High | | | | |
| DR-006 | Data Corruption Recovery | High | | | | |
| DR-007 | Log Retention | Medium | | | | |
| DR-008 | Redis Failure Degradation | High | | | | |
| DR-009 | Celery Worker Recovery | Medium | | | | |
| DR-010 | WebSocket Reconnection | Low | | | | |
| DR-011 | DB Connection Recovery | High | | | | |
| DR-012 | Migration Rollback | High | | | | |

#### Deployment (DEPLOY-001 ~ DEPLOY-010)

| ID | Name | Risk | Result | Date | Tester | Notes |
|----|------|------|--------|------|--------|-------|
| DEPLOY-001 | Docker Stack | High | | | | |
| DEPLOY-002 | DB Migration | Critical | | | | |
| DEPLOY-003 | Static Files | Medium | | | | |
| DEPLOY-004 | Environment Variables | High | | | | |
| DEPLOY-005 | CI/CD Pipeline | Medium | | | | |
| DEPLOY-006 | Zero-Downtime Deploy | High | | | | |
| DEPLOY-007 | Pre-Migration Backup | Critical | | | | |
| DEPLOY-008 | Health Check Endpoint | Medium | | | | |
| DEPLOY-009 | Log Aggregation | Medium | | | | |
| DEPLOY-010 | Secret Rotation | High | | | | |

#### Compatibility (COMPAT-001 ~ COMPAT-005)

| ID | Name | Risk | Result | Date | Tester | Notes |
|----|------|------|--------|------|--------|-------|
| COMPAT-001 | Browser Compatibility | Medium | | | | |
| COMPAT-002 | Mobile Responsive | Medium | | | | |
| COMPAT-003 | PWA Installability | Low | | | | |
| COMPAT-004 | i18n Language Switch | Low | | | | |
| COMPAT-005 | Timezone Handling | Medium | | | | |

#### User Experience (UX-001 ~ UX-005)

| ID | Name | Risk | Result | Date | Tester | Notes |
|----|------|------|--------|------|--------|-------|
| UX-001 | Form Error Display | Low | | | | |
| UX-002 | Loading Indicators | Low | | | | |
| UX-003 | Pagination Consistency | Low | | | | |
| UX-004 | Navigation Completeness | Low | | | | |
| UX-005 | Keyboard Navigation | Low | | | | |

### 11.5 Failed Item Details

| ID | Failure Description | Reproduction Steps | Root Cause | Remediation Plan | Fix Date | Retest Result |
|----|--------------------|--------------------|------------|------------------|----------|---------------|
| | | | | | | |

### 11.6 Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Author | | | |
| Reviewer | | | |
| Approver | | | |

---

## 12. Appendix

### A. Test Execution Commands

```bash
# Unit tests (all apps)
python manage.py test apps/ -v 2

# Verification tests (security/integrity/performance/workflow/DR)
python manage.py test tests.verification -v 2

# Individual verification categories
python manage.py test tests.verification.test_security -v 2
python manage.py test tests.verification.test_data_integrity -v 2
python manage.py test tests.verification.test_performance -v 2
python manage.py test tests.verification.test_workflow -v 2
python manage.py test tests.verification.test_disaster_recovery -v 2

# AD app tests
python manage.py test apps.ad -v 2

# E2E tests (Playwright)
cd e2e && pytest -v

# E2E with specific browser
cd e2e && pytest -v --browser chromium
cd e2e && pytest -v --browser firefox

# Load tests (Locust)
cd loadtest && locust -f locustfile.py --host http://localhost:8000

# Dependency vulnerability scan
pip-audit
safety check

# Docker stack test
docker-compose up -d && docker-compose ps && docker-compose logs --tail=50

# Migration check
python manage.py showmigrations | grep '\[ \]'

# Static file check
python manage.py collectstatic --noinput --dry-run
```

### B. Related Standards
- OWASP Top 10 (2021) - https://owasp.org/Top10/
- ISO/IEC 27001:2022 - Information Security Management
- ISMS-P (Korea) - https://isms.kisa.or.kr/
- KISA Web Security Guide - https://www.kisa.or.kr/
- CWE (Common Weakness Enumeration) - https://cwe.mitre.org/
- NIST Cybersecurity Framework - https://www.nist.gov/cyberframework

### C. OWASP Top 10 (2021) Mapping

| OWASP Category | Verification Items |
|----------------|-------------------|
| A01: Broken Access Control | SEC-003, SEC-005, SEC-023, SEC-031 |
| A02: Cryptographic Failures | SEC-014 |
| A03: Injection | SEC-001, SEC-002, SEC-020, SEC-029 |
| A04: Insecure Design | SEC-009, SEC-017, SEC-027, SEC-028, SEC-030 |
| A05: Security Misconfiguration | SEC-010, SEC-011, SEC-013, SEC-019, SEC-024, SEC-025, SEC-033, SEC-034, SEC-035 |
| A06: Vulnerable Components | SEC-018 |
| A07: Auth Failures | SEC-004, SEC-006, SEC-007, SEC-008, SEC-012, SEC-021, SEC-022, SEC-026, SEC-032 |
| A08: Software/Data Integrity | INT-001~030 |
| A09: Logging/Monitoring | SEC-015, SEC-016 |
| A10: SSRF | (Not applicable - no outbound URL fetch from user input) |

### D. Risk Level Summary

| Risk Level | Total | Security | Integrity | Performance | Functional | AD | DR | Deploy | Compat | UX |
|------------|-------|----------|-----------|-------------|------------|----|----|--------|--------|-----|
| Critical | 28 | 7 | 9 | 0 | 5 | 2 | 4 | 2 | 0 | 0 |
| High | 52 | 12 | 8 | 1 | 3 | 4 | 4 | 4 | 0 | 0 |
| Medium | 55 | 10 | 8 | 9 | 9 | 3 | 2 | 3 | 3 | 0 |
| Low | 30 | 1 | 1 | 5 | 13 | 0 | 1 | 0 | 2 | 5 |

### E. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-17 | Dev Team | Initial 45-item criteria |
| 2.0 | 2026-03-17 | Dev Team | Expanded to 82 items: +5 SEC, +5 INT, +2 PERF, +5 FUNC, +10 AD, +2 DR, +5 DEPLOY |
| 3.0 | 2026-03-17 | Dev Team | Major expansion to 165 items: +15 SEC (021-035), +15 INT (016-030), +8 PERF (008-015), +15 FUNC (016-030), +5 DR (008-012), +5 DEPLOY (006-010), new COMPAT (001-005), new UX (001-005). Added detailed pass/fail conditions, OWASP mapping, risk distribution matrix. |