# Security Policy

**English** | [한국어](docs/SECURITY.ko.md)

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| latest  | :white_check_mark: |

As ERP Suite is in active development, security updates are applied to the latest version on the `main` branch.

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them through [GitHub Security Advisories](https://github.com/kernalix7/ERP_Suite/security/advisories/new).

### What to Include

When reporting a vulnerability, please include:

1. **Description** — A clear description of the vulnerability
2. **Steps to Reproduce** — Detailed steps to reproduce the issue
3. **Impact** — The potential impact of the vulnerability (e.g., data exposure, privilege escalation)
4. **Affected Components** — Which parts of ERP Suite are affected (e.g., authentication, API, file upload)
5. **Environment** — OS, Python version, Django version, deployment method

### Response Timeline

- **Acknowledgment** — Within 48 hours of the report
- **Initial Assessment** — Within 7 days
- **Fix & Disclosure** — Coordinated with the reporter; typically within 30 days for critical issues

### Scope

The following areas are considered in-scope for security reports:

- Authentication and authorization bypass (RBAC, JWT)
- SQL injection, XSS, CSRF vulnerabilities
- Sensitive data exposure (API keys, credentials, PII)
- File upload vulnerabilities (path traversal, unrestricted upload)
- Session management issues
- Insecure direct object references (IDOR)
- Server-side request forgery (SSRF)
- Privilege escalation between roles (staff/manager/admin)

### Out of Scope

- Bugs that require physical access to the server
- Social engineering attacks
- Issues in third-party dependencies (please report these upstream, but let us know)
- Denial of service through brute-force (mitigated by django-axes)

## Security Best Practices

ERP Suite follows these security practices:

- **RBAC enforcement** — Three-tier role system with mixin-based access control
- **Brute-force protection** — django-axes with account lockout after 5 failed attempts
- **Atomic operations** — F() expressions for race-condition-safe stock updates
- **Audit trail** — django-simple-history on all models + AccessLogMiddleware
- **Input validation** — File upload whitelist, 10MB size limit, form validation
- **Production hardening** — HSTS, SSL redirect, HttpOnly cookies, 8-hour session expiry

## Acknowledgments

We appreciate the security research community's efforts in responsibly disclosing vulnerabilities. Contributors who report valid security issues will be acknowledged (with permission) in our release notes.

---

*This security policy is subject to change as the project matures.*
