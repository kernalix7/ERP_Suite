# Country Pack Developer Guide

**English** | [한국어](country_pack_guide.md)

> The Country Pack abstracts Korea-specific legal, tax, identifier, holiday, chart-of-accounts,
> e-Invoice, and social-insurance logic into an adapter pattern, forming the multi-country
> extension foundation of ERP Suite.  
> KR (South Korea) is the full reference implementation; JP and US are provided as stubs for
> interface validation.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Active Country Resolution Priority](#2-active-country-resolution-priority)
3. [Adding a New Country](#3-adding-a-new-country)
4. [Implementation Level Comparison](#4-implementation-level-comparison)
5. [FAQ](#5-faq)
6. [Reference File Paths](#6-reference-file-paths)

---

## 1. Architecture Overview

### Core Structure

```
apps/localizations/
├── __init__.py       ← public API (get_adapter, get_active_adapter, get_vat_rate, …)
├── base.py           ← abstract base (7 sub-adapter interfaces)
├── registry.py       ← Adapter Registry (_REGISTRY dict + _autoload)
├── kr/               ← South Korea — full implementation
├── jp/               ← Japan — stub
└── us/               ← United States — stub
```

### Adapter Registry

`_REGISTRY` in `registry.py` is a module-level dict of the form
`{ 'KR': KRAdapter(), 'JP': JPAdapter(), … }`. When `get_adapter('KR')` is called it
looks up this dict; if the code is not yet registered, `_autoload()` is invoked first.

`_autoload()` attempts to import `apps/localizations/<code>/__init__.py` inside
`try/except` blocks, which triggers each adapter's `register_adapter()` call on import.
Because `ImportError` is silently ignored, **missing adapters never crash the system**.

### 7 Sub-Adapter Interfaces

| Sub-Adapter | Class | Key Methods |
|---|---|---|
| Tax | `TaxAdapter` | `vat_rate()`, `withholding_rates()`, `local_income_tax_rate()` |
| TaxCalendar | `TaxCalendarAdapter` | `vat_filing_due(year, quarter)`, `withholding_filing_due(year, month)`, `corporate_tax_filing_due(year)` |
| Identifier | `IdentifierAdapter` | `business_number_format()`, `validate_business_number(value)` |
| Calendar | `CalendarAdapter` | `is_holiday(date)`, `is_business_day(date)`, `add_business_days(start, days)` |
| ChartOfAccounts | `ChartOfAccountsAdapter` | `standard_name()`, `income_statement_format()` |
| ElectronicInvoice | `ElectronicInvoiceAdapter` | `is_supported()`, `submit_tax_invoice(invoice)` |
| SocialInsurance | `SocialInsuranceAdapter` | `insurance_types()`, `employee_rates()`, `employer_rates()` |

The top-level container `LocalizationAdapter` holds the 7 sub-adapters as attributes and
declares 4 class variables: `country_code`, `country_name`, `currency_code`, `locale`.

### Dependency Flow

```
apps/localizations/__init__.py
    └─ get_vat_rate()                 ← OrderItem / QuotationItem / POItem save hook
    └─ get_default_currency_code()    ← Currency model default, FX gain/loss branching
    └─ get_local_income_tax_rate()    ← Payroll / withholding tax calculation

apps/localizations/registry.py
    └─ get_active_adapter()           ← Fetch active-country adapter
    └─ get_adapter(code)              ← Fetch adapter for a specific country
    └─ _autoload()                    ← Auto-import kr/jp/us/__init__.py
```

---

## 2. Active Country Resolution Priority

`get_active_adapter()` resolves the active country in this order:

```
1. SystemConfig.get_value('GENERAL', 'active_country')   ← DB setting (highest priority)
2. settings.ACTIVE_COUNTRY                                ← settings.py variable
3. 'KR'                                                   ← hard-coded fallback
```

Each step falls back to the next if the value is empty or an exception is raised.

### Change Active Country via DB

```python
from apps.core.models import SystemConfig
SystemConfig.set_value('GENERAL', 'active_country', 'KR')
```

### Change Active Country via settings.py

```python
# config/settings/base.py or local/.env
ACTIVE_COUNTRY = 'KR'
```

### Example: Using the Active Adapter

```python
from apps.localizations import get_active_adapter

adapter = get_active_adapter()
print(adapter.country_code)           # 'KR'
print(adapter.tax.vat_rate())         # Decimal('0.10')
print(adapter.currency_code)          # 'KRW'
```

### Example: Fetching a Specific Adapter Directly

```python
from apps.localizations import get_adapter

kr = get_adapter('KR')
jp = get_adapter('JP')   # stub — calling methods raises NotImplementedError
```

---

## 3. Adding a New Country

### 3.1 Create the File Tree

Create 8 files under `apps/localizations/<code>/`.
`<code>` must be lowercase ISO-3166 alpha-2 (e.g. `cn`, `de`, `sg`).

```
apps/localizations/<code>/
├── __init__.py           ← CountryAdapter definition + register_adapter call
├── tax.py                ← TaxAdapter implementation
├── tax_calendar.py       ← TaxCalendarAdapter implementation
├── identifier.py         ← IdentifierAdapter implementation
├── calendar_<code>.py    ← CalendarAdapter implementation
├── coa.py                ← ChartOfAccountsAdapter implementation
├── e_invoice.py          ← ElectronicInvoiceAdapter implementation
└── social.py             ← SocialInsuranceAdapter implementation
```

### 3.2 `__init__.py` Pattern

```python
from apps.localizations.base import LocalizationAdapter
from apps.localizations.registry import register_adapter

from .tax import CNTaxAdapter
from .tax_calendar import CNTaxCalendarAdapter
from .identifier import CNIdentifierAdapter
from .calendar_cn import CNCalendarAdapter
from .coa import CNChartOfAccountsAdapter
from .e_invoice import CNElectronicInvoiceAdapter
from .social import CNSocialInsuranceAdapter


class CNAdapter(LocalizationAdapter):
    country_code = 'CN'
    country_name = '中国'
    currency_code = 'CNY'
    locale = 'zh_CN'

    def __init__(self):
        self.tax = CNTaxAdapter()
        self.tax_calendar = CNTaxCalendarAdapter()
        self.identifier = CNIdentifierAdapter()
        self.calendar = CNCalendarAdapter()
        self.coa = CNChartOfAccountsAdapter()
        self.e_invoice = CNElectronicInvoiceAdapter()
        self.social_insurance = CNSocialInsuranceAdapter()


register_adapter('CN', CNAdapter())
```

### 3.3 Sub-Adapter Implementation Example (TaxAdapter)

```python
from decimal import Decimal
from apps.localizations.base import TaxAdapter


class CNTaxAdapter(TaxAdapter):
    def vat_rate(self) -> Decimal:
        return Decimal('0.13')          # China standard VAT

    def withholding_rates(self) -> dict[str, Decimal]:
        return {
            'dividend': Decimal('0.10'),
            'interest': Decimal('0.10'),
        }
```

To register quickly as a stub, put `raise NotImplementedError` in each abstract method
(see the JP/US stubs for reference).

### 3.4 Auto-Registration via `_autoload()`

`_autoload()` in `registry.py` currently iterates over `('us', 'jp', 'cn')`.
If your new country code is not in this list, add it to the loop:

```python
# registry.py _autoload() — example with 'de' and 'sg' added
for code in ('us', 'jp', 'cn', 'de', 'sg'):
    try:
        __import__(f'apps.localizations.{code}')
    except ImportError:
        pass
```

Alternatively, explicitly import in an `AppConfig.ready()` hook:

```python
# apps/localizations/apps.py
class LocalizationsConfig(AppConfig):
    name = 'apps.localizations'

    def ready(self):
        try:
            from apps.localizations import de  # noqa
        except ImportError:
            pass
```

### 3.5 Per-Partner Dynamic Dispatch

Use the `Partner.country` FK to dispatch to the correct adapter per business partner:

```python
from apps.localizations import get_adapter

def get_partner_vat_rate(partner):
    code = partner.country.code if partner.country else 'KR'
    try:
        return get_adapter(code).tax.vat_rate()
    except LookupError:
        return get_adapter('KR').tax.vat_rate()   # fallback
```

---

## 4. Implementation Level Comparison

| code | Country | Currency | locale | Level | Notes |
|---|---|---|---|---|---|
| `KR` | South Korea | KRW | ko_KR | **Full** | K-GAAP, NTS, Hometax, 4 social insurances, public holidays |
| `JP` | Japan | JPY | ja_JP | Stub | Calling any method raises `NotImplementedError` |
| `US` | United States | USD | en_US | Stub | Calling any method raises `NotImplementedError` |

### KR Full Implementation Detail

| Sub-Adapter | What is Implemented |
|---|---|
| Tax | VAT 10%, withholding rates (business income 3.3%, other income 8.8%), local income tax 10% |
| TaxCalendar | VAT filing deadline (25th of month after quarter end), withholding (10th of following month), corporate tax (3 months after fiscal year end) |
| Identifier | Business registration number format `###-##-#####` + 10-digit checksum validation |
| Calendar | Korean statutory holidays + substitute holidays, business day calculation, N-business-day offset |
| ChartOfAccounts | K-GAAP 9-step income statement format |
| ElectronicInvoice | Hometax/Barobill API integration (`is_supported=True`), `submit_tax_invoice` |
| SocialInsurance | 4 social insurance types (National Pension, Health Insurance, Employment Insurance, Industrial Accident), employee/employer rates separated |

---

## 5. FAQ

### Q1. Why does `get_vat_rate()` return 0.10 when no adapter is loaded?

`get_vat_rate()` in `apps/localizations/__init__.py` wraps the adapter call in a
`try/except` block. If the adapter import fails or `LookupError` is raised, it falls back
to the KR default (`0.10`).

This protects the system during **migration intermediate states** or fresh environment
setups where adapter files may not yet exist. In production, the KR adapter is always
registered, so this fallback path is effectively never taken.

### Q2. How do I add per-partner dispatch based on `Partner.country` FK?

Currently `OrderItem.save()` calls `get_vat_rate()` which applies the active-country VAT
uniformly. To support per-partner rates:

1. In `OrderItem.save()`, resolve `self.order.partner.country` FK.
2. Call `get_adapter(partner.country.code).tax.vat_rate()`.
3. Catch `LookupError` and fall back to `get_active_adapter()`.

```python
def save(self, *args, **kwargs):
    try:
        code = self.order.partner.country.code
        from apps.localizations import get_adapter
        rate = get_adapter(code).tax.vat_rate()
    except Exception:
        from apps.localizations import get_vat_rate
        rate = get_vat_rate()
    self.vat_amount = self.supply_amount * rate
    super().save(*args, **kwargs)
```

### Q3. What happens if I call a method on a stub adapter (JP/US)?

All sub-adapters in JP and US currently raise `NotImplementedError`. Calling
`get_adapter('JP').tax.vat_rate()` will raise `NotImplementedError`. You must provide
real implementations before using those adapters in production.

### Q4. What is the easiest way to register a country code not in `_autoload()`?

The most reliable approach is to import it explicitly in the `AppConfig.ready()` hook
of `apps/localizations`:

```python
# apps/localizations/apps.py
class LocalizationsConfig(AppConfig):
    name = 'apps.localizations'

    def ready(self):
        try:
            from apps.localizations import de  # noqa
        except ImportError:
            pass
```

You can also add the code to the loop in `registry._autoload()` (see §3.4).

### Q5. What is the minimum test coverage for a new country adapter?

At minimum, cover these cases:

- `get_adapter('<code>')` registers without `LookupError`
- `adapter.tax.vat_rate()` returns expected value
- `adapter.identifier.validate_business_number(valid_value)` returns `True`
- `adapter.identifier.validate_business_number(invalid_value)` returns `False`
- `adapter.calendar.is_holiday(<known_holiday>)` returns `True`
- `adapter.calendar.is_business_day(<weekday>)` returns `True`

---

## 6. Reference File Paths

| File | Description |
|---|---|
| `apps/localizations/__init__.py` | Public API — `get_adapter`, `get_active_adapter`, `get_vat_rate`, etc. |
| `apps/localizations/base.py` | Abstract base — 7 sub-adapter interface definitions |
| `apps/localizations/registry.py` | Adapter Registry — `_REGISTRY`, `_autoload`, `get_adapter`, `get_active_adapter` |
| `apps/localizations/kr/__init__.py` | KRAdapter — full implementation reference |
| `apps/localizations/kr/tax.py` | KRTaxAdapter — VAT and withholding tax |
| `apps/localizations/kr/tax_calendar.py` | KRTaxCalendarAdapter — filing deadline calculation |
| `apps/localizations/kr/identifier.py` | KRIdentifierAdapter — business number validation |
| `apps/localizations/kr/calendar_kr.py` | KRCalendarAdapter — Korean public holidays and business days |
| `apps/localizations/kr/coa.py` | KRChartOfAccountsAdapter — K-GAAP |
| `apps/localizations/kr/e_invoice.py` | KRElectronicInvoiceAdapter — Hometax / Barobill |
| `apps/localizations/kr/social.py` | KRSocialInsuranceAdapter — 4 social insurances |
| `apps/localizations/jp/` | JPAdapter stub (interface validation only) |
| `apps/localizations/us/` | USAdapter stub (interface validation only) |
