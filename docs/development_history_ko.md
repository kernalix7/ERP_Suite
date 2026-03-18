# ERP Suite 개발 이력 및 세션 정리

> 작성일: 2026-03-16
> 목적: 로컬 환경 이전을 위한 전체 개발 맥락 및 프롬프트 이력 정리

---

## 1. 프로젝트 배경

**제품**: 프리다이빙 이퀄라이징 연습용 디바이스 제조/판매
**목표**: 생산관리, 재고관리, AS관리, 판매관리, 회계관리를 포괄하는 자체 ERP 구축
**선택 스택**: Django 5.x + Tailwind CSS + HTMX + Alpine.js + SQLite(개발)/PostgreSQL(운영)
**배포**: Docker Compose (자택 서버)

---

## 2. 세션별 개발 이력

### Session 1 — 프로젝트 초기 구조 설계

**주요 프롬프트:**
```
프리다이빙 이퀄라이징 연습용 디바이스를 만들었어. 이걸 판매할거야.
그래서 제품의 생산 관리 입출고 AS 등에 대해서 프로그램으로 관리하려 하거든?

github에 올라가는거라 테스트용 데이터 등 보안상 민감한 사항은
별도 폴더를 만들어서 저장해.
```

**구현 내용:**
- 프로젝트 전체 구조 설계
- `local/` 폴더 (gitignore 처리) — `.env`, `db.sqlite3`, `erp.log` 분리
- `config/settings/` — base/development/production 분리
- `.env.example` 작성
- `.gitignore` 작성
- `CLAUDE.md` 작성 (개발 규칙)
- `Dockerfile` + `docker-compose.yml` 작성

**핵심 결정:**
- 민감 파일은 `local/` 폴더로 분리 (gitignore)
- `django-environ`으로 환경변수 관리
- `BaseModel` 추상 모델로 공통 필드 통일

---

### Session 2 — 11개 앱 전체 구현 (v1)

**주요 프롬프트:**
```
음 좀 더 잘 만들어봐 손익분기점도 만들고 세금 처리도 편하게
```

**구현 내용 (병렬 에이전트 5개):**

| 에이전트 | 구현 앱 | 주요 기능 |
|---------|--------|---------|
| core+accounts | `core`, `accounts` | BaseModel, RBAC, 로그인, 대시보드 |
| inventory | `inventory` | 제품, 카테고리, 창고, 입출고, 재고현황, 바코드 |
| production | `production` | BOM, 생산계획, 작업지시, 생산실적 |
| sales+service | `sales`, `service` | 거래처, 고객, 주문(VAT), AS요청, 수리이력 |
| accounting+investment | `accounting`, `investment` | 세금계산서, 부가세, BEP, 손익, 전표, 투자자, 지분 |

**주요 모델 (40개):**
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

### Session 3 — 보안 점검 및 취약점 수정

**주요 프롬프트:**
```
더 할 부분 없나
보안상 취약점찾아봐
좀 더 찾아서 개선해봐
```

**수정 내용:**
- 템플릿 변수명 불일치 8개 수정 (product_name → product.name 등)
- `ServiceRequestDetailView`에 `total_repair_cost` 컨텍스트 추가
- 재고 업데이트 F() 표현식 적용 (레이스 컨디션 방지 확인)
- `created_by` 자동 저장 미들웨어 확인

---

### Session 4 — 추가 기능 구현 (v2)

**주요 프롬프트:**
```
모두 다 진행해
```

**구현 내용:**
- `apps/sales/commission.py` — CommissionRate, CommissionRecord 모델
- `apps/core/backup.py` — JSON 백업/다운로드 (AdminRequiredMixin)
- `apps/accounting/` — AccountCode, Voucher, VoucherLine 모델+뷰 추가
- `apps/smartstore/` → `apps/marketplace/` 리네이밍 (범용화)
- `apps/warranty/` — ProductRegistration, 시리얼번호 인증
- `apps/inquiry/` — Inquiry, InquiryReply, LLM(Claude) 자동답변
- `apps/core/trash.py` — 소프트 삭제 항목 휴지통/복원
- `apps/core/attachment.py` — 증빙 첨부파일 (GenericForeignKey)
- `docs/` — 사용자/개발자/API/배포 가이드 4개 작성
- `README.md` 전면 업데이트

---

### Session 5 — 전체 점검 및 누락 항목 보완

**주요 프롬프트:**
```
없는데? 만들어놓고 안집어넣은거 있는지 점검해봐
```

**수정 내용:**
- 사이드바 누락 메뉴 확인 (전체 URL vs 사이드바 비교)
- 수수료 메뉴 3개 누락 확인 (`commission_rate_list`, `commission_list`, `commission_summary`)
- 계정과목 (`accountcode_list`), 전표 (`voucher_list`) 누락 확인

---

### Session 6 — 종합 감사 시스템 + 보안 강화 + 보고서 (진행중)

**주요 프롬프트:**
```
전체적으로 싹 다 분석해서 개선할 점 있는지 확인해봐
삭제된 항목 별도로 볼 수 있게 하자.
그리고 증빙 등 증적 관리도 하고

ERP로써 어느정도 구현이 되었는지 부족한건 뭔지 개선할 건 뭔지 알려줘
문서도 정리하고 보안기능도 충분한지 보고 보고서 한번 만들어봐.
그리고 감사는 따로 메뉴 만들고
```

**구현 중:**
- 감사 추적 시스템 (`/audit/`, `/audit/log/`, `/audit/logins/`)
- 보안 미들웨어 (`SecurityHeadersMiddleware`, `RequestLoggingMiddleware`)
- 알림 시스템 뷰/템플릿 (`/notifications/`)
- 사이드바 누락 메뉴 전체 추가
- 종합 보고서 작성

---

## 3. 로컬 환경 이전 가이드

### 3-1. 사전 요구사항

```
Python 3.13+
Git
(선택) Docker Desktop
```

### 3-2. 클론 및 초기 설정

```bash
# 1. 저장소 클론
git clone https://github.com/YOUR_USERNAME/ERP_Suite.git
cd ERP_Suite

# 2. 가상환경 생성
python -m venv venv
source venv/bin/activate          # macOS/Linux
venv\Scripts\activate             # Windows

# 3. 패키지 설치
pip install -r requirements/dev.txt

# 4. 환경변수 설정
mkdir -p local
cp .env.example local/.env
# local/.env 열어서 SECRET_KEY 값 변경 (필수!)
# SECRET_KEY=django-insecure-your-random-50-char-key-here

# 5. SECRET_KEY 생성하는 법:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 6. DB 생성 및 마이그레이션
python manage.py migrate

# 7. 관리자 계정 생성
python manage.py createsuperuser
# username: admin
# email: admin@yourdomain.com
# password: (8자리 이상, 영문+숫자)

# 8. 계정 역할 설정
python manage.py shell
>>> from apps.accounts.models import User
>>> u = User.objects.get(username='admin')
>>> u.role = 'admin'
>>> u.name = '관리자'
>>> u.save()
>>> exit()

# 9. 개발 서버 실행
python manage.py runserver 0.0.0.0:8000
# 브라우저: http://localhost:8000
```

### 3-3. Docker Compose로 실행 (운영 환경)

```bash
# .env 파일 준비 (프로젝트 루트에 별도로)
cat > .env << 'EOF'
SECRET_KEY=your-production-secret-key-here
DB_PASSWORD=strong-db-password-here
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
EOF

# 실행
docker compose up -d

# 최초 마이그레이션
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser

# 로그 확인
docker compose logs -f web
```

### 3-4. Claude API 설정 (LLM 자동답변 기능)

`local/.env`에 추가:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

문의관리 → 문의 상세에서 "AI 답변 생성" 버튼 사용 가능.

---

## 4. 현재 프로젝트 구조 (최종)

```
ERP_Suite/
├── .env.example              # 환경변수 템플릿
├── .gitignore                # local/, __pycache__, .env 등 제외
├── CLAUDE.md                 # AI 개발 지침
├── README.md                 # 프로젝트 소개
├── Dockerfile                # Docker 이미지
├── docker-compose.yml        # 서비스 오케스트레이션
├── manage.py
├── requirements/
│   ├── base.txt              # Django, 공통 패키지
│   ├── dev.txt               # debug-toolbar 추가
│   └── prod.txt              # gunicorn, psycopg2 추가
├── config/
│   ├── settings/
│   │   ├── base.py           # 공통 설정
│   │   ├── development.py    # 개발 설정 (DEBUG=True, SQLite)
│   │   └── production.py     # 운영 설정 (보안 헤더, PostgreSQL)
│   ├── urls.py               # 루트 URL
│   └── wsgi.py
├── apps/
│   ├── core/                 # BaseModel, 알림, 백업, 휴지통, 증빙, 감사
│   ├── accounts/             # 사용자, 역할(admin/manager/staff)
│   ├── inventory/            # 제품, 카테고리, 창고, 입출고, 재고
│   ├── production/           # BOM, 생산계획, 작업지시, 생산실적
│   ├── sales/                # 거래처, 고객, 주문, 수수료
│   ├── service/              # AS요청, 수리이력
│   ├── accounting/           # 세금계산서, 부가세, 손익분기점, 전표
│   ├── investment/           # 투자자, 라운드, 지분, 배당
│   ├── warranty/             # 정품등록, 시리얼번호 인증
│   ├── marketplace/          # 외부스토어 연동(네이버/쿠팡 등)
│   └── inquiry/              # 문의관리, LLM 자동답변
├── templates/
│   ├── base.html             # 공통 레이아웃 (사이드바, 헤더)
│   ├── accounts/             # 로그인, 사용자관리 (3개)
│   ├── core/                 # 대시보드, 백업, 휴지통, 증빙, 감사, 알림 (9개)
│   ├── inventory/            # 제품, 창고, 입출고 등 (12개)
│   ├── production/           # BOM, 생산계획 등 (11개)
│   ├── sales/                # 거래처, 고객, 주문, 수수료 (13개)
│   ├── service/              # AS, 수리 (4개)
│   ├── accounting/           # 세금계산서, 전표 등 (13개)
│   ├── investment/           # 투자자, 지분 등 (11개)
│   ├── warranty/             # 정품등록 (3개)
│   ├── marketplace/          # 외부스토어 (5개)
│   └── inquiry/              # 문의관리 (6개)
├── docs/
│   ├── 사용자_가이드.md
│   ├── 개발자_가이드.md
│   ├── API_레퍼런스.md
│   ├── 배포_가이드.md
│   └── 개발이력_및_세션정리.md  ← 이 파일
└── local/                    # gitignore — 민감 파일
    ├── .env                  # 환경변수 (직접 생성)
    ├── db.sqlite3            # 개발 DB (migrate 후 생성)
    └── erp.log               # 로그 (서버 실행 후 생성)
```

---

## 5. 주요 URL 목록

| 경로 | 설명 |
|------|------|
| `/` | 대시보드 |
| `/accounts/login/` | 로그인 |
| `/inventory/products/` | 제품 목록 |
| `/inventory/stock/` | 재고 현황 |
| `/production/bom/` | BOM 목록 |
| `/production/plans/` | 생산계획 |
| `/sales/orders/` | 주문 목록 |
| `/sales/commissions/` | 수수료 내역 |
| `/service/requests/` | AS 요청 |
| `/accounting/` | 재무 대시보드 |
| `/accounting/breakeven/` | 손익분기점 |
| `/accounting/monthly-pl/` | 월별 손익 |
| `/accounting/vouchers/` | 전표 |
| `/investment/` | 투자 대시보드 |
| `/warranty/` | 정품등록 |
| `/marketplace/` | 외부스토어 |
| `/inquiry/` | 문의관리 |
| `/audit/` | 감사 대시보드 |
| `/audit/log/` | 감사 로그 |
| `/audit/logins/` | 로그인 이력 |
| `/trash/` | 휴지통 |
| `/attachments/` | 증빙 관리 |
| `/backup/` | 백업 |
| `/mgmt-console-x/` | Django Admin |

---

## 6. 역할별 접근 권한

| 역할 | 설명 | 접근 가능 메뉴 |
|------|------|--------------|
| `admin` | 시스템 관리자 | 전체 + 사용자관리 + 백업 |
| `manager` | 부서 관리자 | 전체 (사용자관리, 백업 제외) |
| `staff` | 일반 직원 | 재고, 생산, 판매, AS |

---

## 7. 보안 구성

| 항목 | 내용 |
|------|------|
| 로그인 보호 | django-axes (5회 실패 → 1시간 잠금) |
| RBAC | AdminRequiredMixin, ManagerRequiredMixin |
| 재고 동시성 | F() 표현식 (레이스 컨디션 방지) |
| 파일 업로드 | 확장자 화이트리스트 + 10MB 제한 |
| 소프트 삭제 | is_active=False (물리 삭제 금지) |
| 변경 이력 | simple_history (전 모델 82개+) |
| 운영 보안 | HSTS, SSL Redirect, HttpOnly 쿠키 |
| 감사 추적 | /audit/ — 전 모델 변경이력 통합 조회 |
| 요청 로깅 | 민감 경로 접근 자동 로깅 |

---

## 8. 다음 개선 과제 (우선순위 순)

### 높음 (기능 완성도)
1. **실제 API 연동** — 네이버 커머스 API (스마트스토어), 쿠팡 파트너스 API
2. **바코드/QR 스캔** — 입출고 시 바코드 스캐너 지원
3. **Excel 가져오기** — 제품/주문/재고 일괄 업로드
4. **PDF 출력** — 세금계산서, 거래명세서, 납품서

### 중간 (UX 개선)
5. **대시보드 KPI 강화** — 실시간 재고 알림, 납기 임박 알림
6. **모바일 반응형** — 현재 데스크톱 위주, 모바일 최적화
7. **다크 모드** — Tailwind CSS dark: 클래스 적용
8. **검색 강화** — 전체 검색 기능

### 낮음 (확장)
9. **멀티 사업장** — 지점별 재고/생산 분리 관리
10. **REST API** — 외부 연동용 DRF API
11. **PWA** — 오프라인 지원

---

## 9. 자주 쓰는 관리 명령어

```bash
# 개발 서버 실행
python manage.py runserver 0.0.0.0:8000

# 마이그레이션
python manage.py makemigrations
python manage.py migrate

# 슈퍼유저 생성
python manage.py createsuperuser

# Django shell
python manage.py shell

# 정적 파일 수집 (운영)
python manage.py collectstatic

# 테스트
python manage.py test

# DB 초기화 (개발 중)
rm local/db.sqlite3
python manage.py migrate
DJANGO_SUPERUSER_PASSWORD=admin123 python manage.py createsuperuser --username admin --email admin@example.com --noinput
python manage.py shell -c "from apps.accounts.models import User; u=User.objects.get(username='admin'); u.name='관리자'; u.role='admin'; u.save()"
```

---

## 10. 알려진 이슈 및 TODO

| 항목 | 상태 | 내용 |
|------|------|------|
| 감사 메뉴 | 구현중 | /audit/ 경로, 사이드바 추가 작업 중 |
| 알림 읽음 처리 | 구현중 | 상단 벨 아이콘 알림 카운트 연동 |
| 마켓플레이스 API | 미구현 | 실제 네이버/쿠팡 API 연동 필요 |
| PDF 출력 | 미구현 | reportlab 또는 weasyprint 도입 필요 |
| Excel 가져오기 | 미구현 | django-import-export 활용 |
| 단위 테스트 | 미작성 | 핵심 모델/뷰 테스트 코드 필요 |
