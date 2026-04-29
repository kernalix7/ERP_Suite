# Country Pack 가이드 (국가팩 개발자 가이드)

[English](country_pack_guide_en.md) | **한국어**

> Country Pack은 ERP Suite의 국가별 법규·세제·식별자·공휴일·계정과목·e-Invoice·사회보험
> 로직을 어댑터 패턴으로 추상화한 다국가 확장 기반이다.  
> KR(대한민국)이 Full 구현 기준이며, JP·US는 인터페이스 검증용 스텁으로 제공된다.

---

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [활성 국가 결정 우선순위](#2-활성-국가-결정-우선순위)
3. [신규 국가 추가 방법](#3-신규-국가-추가-방법)
4. [구현 수준 비교표](#4-구현-수준-비교표)
5. [자주 묻는 질문 (FAQ)](#5-자주-묻는-질문-faq)
6. [참고 파일 경로](#6-참고-파일-경로)

---

## 1. 아키텍처 개요

### 핵심 구조

```
apps/localizations/
├── __init__.py       ← public API (get_adapter, get_active_adapter, get_vat_rate 등)
├── base.py           ← 추상 베이스 (7개 sub-adapter 인터페이스)
├── registry.py       ← Adapter Registry (_REGISTRY dict + _autoload)
├── kr/               ← 대한민국 — Full 구현
├── jp/               ← 日本 — 스텁
└── us/               ← United States — 스텁
```

### Adapter Registry

`registry.py`의 `_REGISTRY`는 `{ 'KR': KRAdapter(), 'JP': JPAdapter(), ... }` 형태의
모듈 레벨 딕셔너리다. `get_adapter('KR')` 호출 시 이 딕셔너리를 조회하며,
미등록이면 `_autoload()`를 먼저 실행한다.

`_autoload()`는 `apps/localizations/<code>/__init__.py`를 `try/except`로 임포트하여
자동 등록을 유도한다. 파일이 없어도 ImportError를 무시하므로
**일부 국가 어댑터가 없어도 시스템이 계속 동작**한다.

### 7개 Sub-Adapter 인터페이스

| Sub-Adapter | 클래스 | 주요 메서드 |
|---|---|---|
| Tax | `TaxAdapter` | `vat_rate()`, `withholding_rates()`, `local_income_tax_rate()` |
| TaxCalendar | `TaxCalendarAdapter` | `vat_filing_due(year, quarter)`, `withholding_filing_due(year, month)`, `corporate_tax_filing_due(year)` |
| Identifier | `IdentifierAdapter` | `business_number_format()`, `validate_business_number(value)` |
| Calendar | `CalendarAdapter` | `is_holiday(date)`, `is_business_day(date)`, `add_business_days(start, days)` |
| ChartOfAccounts | `ChartOfAccountsAdapter` | `standard_name()`, `income_statement_format()` |
| ElectronicInvoice | `ElectronicInvoiceAdapter` | `is_supported()`, `submit_tax_invoice(invoice)` |
| SocialInsurance | `SocialInsuranceAdapter` | `insurance_types()`, `employee_rates()`, `employer_rates()` |

최상위 컨테이너 `LocalizationAdapter`는 위 7개 sub-adapter를 속성으로 포함하며
`country_code`, `country_name`, `currency_code`, `locale` 4개의 클래스 변수를 선언한다.

### 의존 흐름

```
apps/localizations/__init__.py
    └─ get_vat_rate()                 ← OrderItem/QuotationItem/POItem save 훅
    └─ get_default_currency_code()    ← Currency 모델 default, 환차손익 분기
    └─ get_local_income_tax_rate()    ← 급여/원천세 계산

apps/localizations/registry.py
    └─ get_active_adapter()           ← 활성 국가 어댑터 조회
    └─ get_adapter(code)              ← 특정 국가 어댑터 조회
    └─ _autoload()                    ← kr/jp/us/__init__.py 자동 임포트
```

---

## 2. 활성 국가 결정 우선순위

`get_active_adapter()`는 다음 순서로 활성 국가를 결정한다.

```
1. SystemConfig.get_value('GENERAL', 'active_country')   ← DB 설정 (최우선)
2. settings.ACTIVE_COUNTRY                                ← settings.py 변수
3. 'KR'                                                   ← 하드코딩 기본값
```

각 단계에서 값이 비어 있거나 예외가 발생하면 다음 단계로 폴백한다.

### DB에서 활성 국가 변경하기

```python
from apps.core.models import SystemConfig
SystemConfig.set_value('GENERAL', 'active_country', 'KR')
```

### settings.py에서 변경하기

```python
# config/settings/base.py 또는 local/.env
ACTIVE_COUNTRY = 'KR'
```

### 활성 국가 어댑터 사용 예

```python
from apps.localizations import get_active_adapter

adapter = get_active_adapter()
print(adapter.country_code)           # 'KR'
print(adapter.tax.vat_rate())         # Decimal('0.10')
print(adapter.currency_code)          # 'KRW'
```

### 특정 국가 어댑터 직접 조회

```python
from apps.localizations import get_adapter

kr = get_adapter('KR')
jp = get_adapter('JP')   # 스텁 — 메서드 호출 시 NotImplementedError
```

---

## 3. 신규 국가 추가 방법

### 3.1 파일 트리 생성

아래 파일 8개를 `apps/localizations/<code>/` 디렉터리에 생성한다.
`<code>`는 ISO-3166 alpha-2 소문자(예: `cn`, `de`, `sg`).

```
apps/localizations/<code>/
├── __init__.py           ← KRAdapter 패턴으로 CountryAdapter 정의 + register_adapter 호출
├── tax.py                ← TaxAdapter 구현
├── tax_calendar.py       ← TaxCalendarAdapter 구현
├── identifier.py         ← IdentifierAdapter 구현
├── calendar_<code>.py    ← CalendarAdapter 구현
├── coa.py                ← ChartOfAccountsAdapter 구현
├── e_invoice.py          ← ElectronicInvoiceAdapter 구현
└── social.py             ← SocialInsuranceAdapter 구현
```

### 3.2 `__init__.py` 작성 패턴

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

### 3.3 Sub-Adapter 구현 예 (TaxAdapter)

```python
from decimal import Decimal
from apps.localizations.base import TaxAdapter


class CNTaxAdapter(TaxAdapter):
    def vat_rate(self) -> Decimal:
        return Decimal('0.13')          # 중국 표준 VAT

    def withholding_rates(self) -> dict[str, Decimal]:
        return {
            'dividend': Decimal('0.10'),
            'interest': Decimal('0.10'),
        }
```

**스텁으로 빠르게 등록만 하려면** 각 추상 메서드에 `raise NotImplementedError`를 넣어도
시스템이 동작한다 (JP·US 스텁 참고).

### 3.4 `_autoload()` 자동 등록

`registry.py`의 `_autoload()`는 현재 `kr`, `us`, `jp`, `cn`을 자동 시도한다.
새 국가 코드가 이 목록에 없으면 `_autoload()` 내 루프에 추가해야 한다.

```python
# registry.py _autoload() — 신규 국가 추가 예
for code in ('us', 'jp', 'cn', 'de', 'sg'):   # ← 'de', 'sg' 추가
    try:
        __import__(f'apps.localizations.{code}')
    except ImportError:
        pass
```

또는 앱 초기화 시 명시적으로 임포트해도 된다:

```python
# config/settings/base.py 또는 apps/localizations/__init__.py 말미
try:
    from apps.localizations import de  # noqa
except ImportError:
    pass
```

### 3.5 파트너별 동적 분기

파트너(Partner) 모델의 `country` FK를 기반으로 거래처별 어댑터를 동적으로 분기할 수 있다.

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

## 4. 구현 수준 비교표

| code | 국가명 | 통화 | locale | 구현 수준 | 비고 |
|---|---|---|---|---|---|
| `KR` | 대한민국 | KRW | ko_KR | **Full** | K-GAAP·국세청·홈택스·4대보험·공휴일 |
| `JP` | 日本 | JPY | ja_JP | Stub | 메서드 호출 시 NotImplementedError |
| `US` | United States | USD | en_US | Stub | 메서드 호출 시 NotImplementedError |

### KR Full 구현 상세

| Sub-Adapter | 구현 내용 |
|---|---|
| Tax | VAT 10%, 원천세율 (사업소득 3.3%, 기타소득 8.8%), 지방소득세 10% |
| TaxCalendar | 부가세 신고기한 (분기 익월 25일), 원천세 (지급월 익월 10일), 법인세 (3개월) |
| Identifier | 사업자등록번호 형식 `###-##-#####` + 체크섬 검증 10자리 알고리즘 |
| Calendar | 한국 법정공휴일 + 대체공휴일, 영업일 계산, N영업일 후 일자 |
| ChartOfAccounts | K-GAAP 9단계 손익계산서 양식 |
| ElectronicInvoice | 홈택스/바로빌 API 연동 (`is_supported=True`), `submit_tax_invoice` |
| SocialInsurance | 4대보험 (국민연금·건강보험·고용보험·산재보험) 요율 (직원/회사 분리) |

---

## 5. 자주 묻는 질문 (FAQ)

### Q1. 어댑터 미로드 시 `get_vat_rate()`가 0.10을 반환하는 이유는?

`apps/localizations/__init__.py`의 `get_vat_rate()`는 내부적으로 `try/except` 블록으로
감싸져 있어, 어댑터 임포트에 실패하거나 `LookupError`가 발생해도 KR 기본값(`0.10`)을
반환한다.

이 패턴은 **마이그레이션 중간 단계** 또는 신규 환경 셋업 시 어댑터 파일이 아직 없어도
시스템이 정상 동작하도록 보호하기 위함이다. 운영 환경에서는 항상 KR 어댑터가 등록되므로
사실상 이 fallback 경로는 사용되지 않는다.

### Q2. Partner.country FK를 활용한 동적 분기는 어떻게 추가하나?

현재 `OrderItem.save()`는 `get_vat_rate()`로 활성 국가 VAT를 일괄 적용한다.
파트너별 다국가 세율 분기가 필요하면:

1. `OrderItem` 모델의 `save()`에서 `self.order.partner.country` FK를 조회한다.
2. `get_adapter(partner.country.code).tax.vat_rate()`를 호출한다.
3. `LookupError` 발생 시 `get_active_adapter()`로 fallback한다.

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

### Q3. 스텁 어댑터(JP/US)의 메서드를 호출하면 어떻게 되나?

현재 JP·US의 sub-adapter는 모두 `raise NotImplementedError`를 반환한다.
따라서 `get_adapter('JP').tax.vat_rate()` 호출 시 `NotImplementedError`가 발생한다.
운영에서 JP·US 기능을 사용하려면 해당 메서드를 실 구현해야 한다.

### Q4. `_autoload()`에 없는 국가 코드를 등록하는 가장 쉬운 방법은?

앱 AppConfig의 `ready()` 훅에서 명시적으로 임포트하는 것이 가장 확실하다:

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

또는 `registry._autoload()` 루프에 코드를 추가해도 된다 (위 §3.4 참고).

### Q5. 새 국가 추가 후 테스트 작성 기준은?

최소한 아래 케이스를 검증한다:

- `get_adapter('<code>')` 등록 확인 (LookupError 없음)
- `adapter.tax.vat_rate()` 값 검증
- `adapter.identifier.validate_business_number(valid)` True 반환
- `adapter.identifier.validate_business_number(invalid)` False 반환
- `adapter.calendar.is_holiday(공휴일)` True 반환
- `adapter.calendar.is_business_day(평일)` True 반환

---

## 6. 참고 파일 경로

| 파일 | 설명 |
|---|---|
| `apps/localizations/__init__.py` | Public API — `get_adapter`, `get_active_adapter`, `get_vat_rate` 등 헬퍼 |
| `apps/localizations/base.py` | 추상 베이스 — 7개 sub-adapter 인터페이스 정의 |
| `apps/localizations/registry.py` | Adapter Registry — `_REGISTRY`, `_autoload`, `get_adapter`, `get_active_adapter` |
| `apps/localizations/kr/__init__.py` | KRAdapter — Full 구현 참조 |
| `apps/localizations/kr/tax.py` | KRTaxAdapter — VAT·원천세 구현 |
| `apps/localizations/kr/tax_calendar.py` | KRTaxCalendarAdapter — 신고기한 계산 |
| `apps/localizations/kr/identifier.py` | KRIdentifierAdapter — 사업자번호 검증 |
| `apps/localizations/kr/calendar_kr.py` | KRCalendarAdapter — 한국 공휴일·영업일 |
| `apps/localizations/kr/coa.py` | KRChartOfAccountsAdapter — K-GAAP |
| `apps/localizations/kr/e_invoice.py` | KRElectronicInvoiceAdapter — 홈택스/바로빌 |
| `apps/localizations/kr/social.py` | KRSocialInsuranceAdapter — 4대보험 |
| `apps/localizations/jp/` | JPAdapter 스텁 (인터페이스 검증용) |
| `apps/localizations/us/` | USAdapter 스텁 (인터페이스 검증용) |
