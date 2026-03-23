# ERP Suite

중소기업을 위한 제조/판매 통합 ERP + 그룹웨어 시스템

[English](../README.md) | **한국어**

## 주요 기능

### ERP 모듈

| 모듈 | 설명 |
|------|------|
| **재고관리** | 제품(원자재/반제품/완제품), 창고, 재고이동, 창고간 이동, 바코드/QR 스캔, 안전재고 알림, StockLot(FIFO/LIFO 재고평가), WarehouseStock(창고별 재고), 재고예약(reserved_stock) |
| **생산관리** | BOM 관리, 생산계획, 작업지시, 생산실적(자동 재고 반영), MRP(자재소요량계획), StandardCost(표준원가), QualityInspection(품질검수) |
| **판매관리** | 거래처, 고객, 주문, 견적(원클릭 주문전환), ShipmentItem(부분출고), ShippingCarrier(택배사), ShipmentTracking(배송추적), 수수료 관리, 거래처 분석 |
| **구매관리** | 발주서, 입고확인, 입고 시 자동 재고반영, 발주 상태 추적, 발주 취소 역방향 연쇄 |
| **AS관리** | AS 요청, 수리이력 추적, 보증기간 확인 |
| **회계관리** | 세금계산서, 부가세, 고정비, 손익분기점, 월별 손익, 전표, 계정과목, 원천세, 다단계 결재, ClosingPeriod(결산마감), Budget(예산관리), Currency/ExchangeRate(다중통화), AR/AP Aging |
| **투자관리** | 투자자, 투자라운드, 지분추적(도넛차트), 배당/분배 기록 |
| **자산관리** | 고정자산 관리, 감가상각(정액법/정률법) |
| **외부스토어** | 네이버/쿠팡 스토어 연동, 주문 동기화, 동기화 이력 |
| **문의관리** | 멀티채널 문의 관리, Claude AI 자동답변 초안, 답변 템플릿 |
| **정품등록** | 시리얼번호 인증, 보증기간 관리, QR 인증 |
| **광고관리** | 광고 플랫폼(Google/Naver/Kakao/Meta), 캠페인, 소재, 성과 추적(ROAS/CTR/CPC), 예산 관리 |

### 그룹웨어 모듈

| 모듈 | 설명 |
|------|------|
| **인사관리** | 부서, 직급, 직원 프로필, 인사발령, 조직도, Payroll(급여관리), PayrollConfig(4대보험 설정) |
| **근태관리** | 출퇴근 기록, 휴가 신청/승인, 연차 잔여 |
| **게시판** | 공지/자유 게시판, 글, 댓글(대댓글) |
| **일정관리** | FullCalendar.js 기반 일정 관리, AJAX API |
| **메신저** | 사내 메신저(1:1/그룹 채팅), WebSocket 실시간 |

### 시스템 모듈

| 모듈 | 설명 |
|------|------|
| **공통** | 대시보드, 알림, Excel/PDF 내보내기, 바코드 생성, 백업/복원, 감사추적, 접근 로그 |
| **사용자** | 인증, RBAC(관리자/매니저/직원), 로그인 보호(django-axes) |
| **API** | REST API(DRF ViewSets), JWT 인증(SimpleJWT) |
| **Active Directory** | LDAP/AD 연동, 사용자/그룹 동기화, 그룹 정책 기반 역할 매핑 |

## 기술 스택

| 계층 | 기술 |
|------|------|
| 백엔드 | Django 5.x / Python 3.13 |
| 프론트엔드 | Django Templates + Tailwind CSS(로컬 빌드) + HTMX + Alpine.js + Chart.js + FullCalendar.js (전부 static/vendor/ 로컬) |
| 데이터베이스 | SQLite(개발) / PostgreSQL 16(운영) |
| 실시간 | Django Channels + WebSocket(Daphne ASGI) |
| 비동기 작업 | Celery + Redis(작업 큐, 예약 백업) |
| 캐싱 | Redis(django-redis) |
| API | Django REST Framework + JWT(SimpleJWT) |
| 보안 | django-axes(로그인 제한), RBAC, HSTS/CSP, django-prometheus |
| 모니터링 | Prometheus + Grafana + Sentry |
| 배포 | Docker Compose(7개 컨테이너) |
| CI/CD | GitHub Actions |
| 다국어 | 한국어 / 영어(django i18n) |
| 이력관리 | django-simple-history(전 모델) |

## 빠른 시작

### 사전 요구사항
- Python 3.13+
- pip

### 설치

```bash
# 저장소 클론
git clone https://github.com/your-org/ERP_Suite.git
cd ERP_Suite

# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 패키지 설치
pip install -r requirements/base.txt

# 프론트엔드 벤더 라이브러리 다운로드 (로컬 빌드)
bash scripts/download_vendor.sh

# 환경 설정
mkdir -p local
cp .env.example local/.env
# local/.env 편집 후 SECRET_KEY 설정

# 마이그레이션
python manage.py migrate

# 방법 A: 프로덕션 — 관리자 계정만 생성 (ID: admin / PW: Admin12#)
python manage.py init_prod

# 방법 B: 샌드박스 — 데모 데이터 포함 (사용자/제품/주문 등)
python manage.py seed_data

# 번역 컴파일
python manage.py compilemessages

# 개발 서버 시작
python manage.py runserver 0.0.0.0:8000
```

브라우저에서 http://localhost:8000 접속

### Docker 배포

```bash
# 환경 변수 설정
export DB_PASSWORD=your-secure-password
export SECRET_KEY=your-secret-key
export ALLOWED_HOSTS=your-domain.com

# 전체 서비스 빌드 및 시작
docker-compose up -d
```

**Docker 서비스 (7개 컨테이너):**

| 서비스 | 포트 | 설명 |
|--------|------|------|
| web | 8000 | Django 앱 (Daphne ASGI) |
| db | 5432 | PostgreSQL 16 |
| redis | 6379 | 캐시 + 메시지 브로커 |
| celery_worker | - | 비동기 작업 처리 |
| celery_beat | - | 주기적 작업 스케줄러 |
| prometheus | 9090 | 메트릭 수집 |
| grafana | 3000 | 모니터링 대시보드 |

## 테스트

```bash
# 단위 테스트 (592 테스트, --parallel로 병렬 실행)
python manage.py test apps/ -v 2 --parallel

# 검증 테스트 (보안/무결성/성능/워크플로/재해복구)
python manage.py test tests.verification -v 2 --parallel

# 전체 테스트 한번에 실행
python manage.py test apps/ tests.verification -v 0 --parallel

# E2E 테스트 (Playwright)
cd e2e && pytest -v

# 부하 테스트 (Locust)
cd loadtest && locust -f locustfile.py --host http://localhost:8000
```

**테스트 커버리지: 592 테스트 (단위 + 검증)**

검증 기준 152개 항목, 9개 카테고리:
- SEC-001~020: 보안 검증 (OWASP Top 10)
- INT-001~015: 데이터 무결성 검증
- PERF-001~007: 성능 검증
- FUNC-001~015: 기능 워크플로 검증
- AD-001~010: Active Directory 연동 검증
- DR-001~007: 재해복구 검증
- DEPLOY-001~005: 배포/통합 검증

## 핵심 데이터 흐름

- **재고 관리**: `StockMovement` 시그널이 `F()` 표현식으로 `Product.current_stock` 원자적 업데이트 (경쟁조건 방지)
- **주문 확정**: 주문 CONFIRMED → reserved_stock 예약 + 매출채권 자동 생성 + 세금계산서 발행
- **주문 이행**: 주문 출하(SHIPPED) → 시그널로 자동 재고 OUT
- **FIFO/LIFO**: 입고 시 StockLot 자동 생성, 출고 시 자동 소진 (FIFO/LIFO 재고평가)
- **생산**: 생산실적 → 완제품 자동 IN + 원자재 자동 OUT (트랜잭션)
- **MRP**: MRP 실행 → BOM 전개 + 부족분 자동 발주서 생성
- **생산 취소**: ProductionPlan/WorkOrder CANCELLED → 재고이동 자동 복원
- **구매**: 입고확인 → 자동 재고 IN + 발주 상태 전환
- **구매 취소**: PurchaseOrder CANCELLED → 매입채무/세금계산서 soft delete (역방향 연쇄)
- **견적**: 원클릭 견적→주문 전환 (항목 자동 복사)
- **세금**: `OrderItem.save()` → 10% 부가세 자동 계산
- **결재**: 다단계 결재 워크플로 (초안 → 1단계 → 2단계 → ... → 최종 승인)
- **매출채권/매입채무**: 결제 등록 → 잔액 자동 재계산
- **결산마감**: ClosingPeriod → 마감 월 전표 수정 차단
- **급여**: `Payroll.save()` → 4대보험/세금 자동 공제

## 보안

- RBAC: `AdminRequiredMixin`(사용자관리, 백업), `ManagerRequiredMixin`(회계, 투자, 인사)
- 로그인 보호: django-axes (5회 실패 → 1시간 잠금)
- API: JWT Bearer 토큰 (1시간 만료) + 세션 이중 인증
- 재고 업데이트: `F()` 표현식으로 경쟁조건 방지
- 파일 업로드: 확장자 화이트리스트 + 10MB 제한
- 운영: HSTS, SSL 리다이렉트, HttpOnly 쿠키, 8시간 세션 만료
- CSP: `unsafe-eval` 제거 완료, 엄격한 Content Security Policy 적용
- OWASP: OWASP Top 10 감사 통과
- 오프라인: 100% 오프라인 동작 가능 (모든 벤더 에셋 로컬 제공)
- 감사추적: django-simple-history (전 모델), ISMS 감사 증적 대시보드 (접근 로그, 데이터 변경, 로그인 이력, 메타 감사)
- 접근 로그: `AccessLogMiddleware` (사용자/경로/응답시간)
- 감사 접근통제: `is_auditor` 역할 기반 접근, 모든 감사 뷰 열람 기록
- 모니터링: Prometheus 메트릭 + Sentry 에러 추적

## 기여

개발 환경 설정과 작업 흐름은 [CONTRIBUTING.ko.md](CONTRIBUTING.ko.md)를 참조하세요.

## 보안 정책

보안 이슈는 [SECURITY.ko.md](SECURITY.ko.md)의 제보 절차를 따라 주세요.

## 현재 규모

- **22개 앱**, **106개 모델** (전체 이력 추적)
- **300+ 뷰**, **250+ 템플릿**, **320+ URL 엔드포인트**
- **~30,000줄** Python 코드 (마이그레이션 제외)
- **592 테스트** (단위 + 검증)
- **110+ 마이그레이션**, **25+ 패키지**

## 라이선스

Proprietary
