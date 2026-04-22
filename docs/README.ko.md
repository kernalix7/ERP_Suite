# ERP Suite

중소기업을 위한 제조/판매 통합 ERP + 그룹웨어 시스템

[English](../README.md) | **한국어**

## 주요 기능

### ERP 모듈

| 모듈 | 설명 |
|------|------|
| **재고관리(Inventory)** | 제품(원자재/반제품/완제품), 카테고리, 창고, 재고이동, 창고간 이동, 바코드/QR 스캔, 안전재고 알림, 재주문점 모니터링, StockLot(FIFO/LIFO 재고평가), WarehouseStock(창고별 재고), reserved_stock(재고예약), SerialNumber(제품별 옵션, 생산 시 자동생성, 출고 시 FIFO 할당) |
| **생산관리(Production)** | BOM 관리(반제품 재귀 전개), 생산계획, 작업지시, 생산실적(자동 재고반영), 불량수량 추적, MRP(자재소요량계획·재주문점 기반 발주 제안), StandardCost(표준원가·자동 버전 생성), QualityInspection(조건부 승인 워크플로), WorkCenter(작업장 가동률), ProductionSchedule(간트 데이터), CostVariance(실제 vs 표준원가 분석), ProductionBatch(3단계 Traceability) |
| **판매관리(Sales)** | 거래처, 고객, 주문(확정 후 수정 가능), 견적(원클릭 주문전환·PriceRule 자동적용), 반품/교환 주문, ShipmentItem(부분출고·시리얼 범위 추적·자동 PARTIAL_SHIPPED 전환), ShippingCarrier(택배사), ShipmentTracking(배송추적), PriceRule(최소수량 검증), 수수료, 거래처 분석, CustomerTier(고객등급), SalesTarget(쿼터), SalesLead(CRM 파이프라인 7단계), CustomerSatisfaction(NPS), 신용한도 |
| **구매관리(Purchase)** | 발주서, 입고확인, 입고 시 자동 재고반영, 발주 상태 추적, 발주 취소 역방향 연쇄, RFQ(견적요청·공급처 비교·PO 전환), VendorScore(공급처 4항목 평가) |
| **AS관리(Service)** | AS 요청, 수리이력, 보증기간 자동 확인(시리얼 기반), 유상수리 AR 자동생성, 취소 시 AR 역방향 처리 |
| **회계관리(Accounting)** | 세금계산서, 부가세 요약(VAT 신고 리포트), CashReceipt(현금영수증 발행·국세청 포맷 내보내기), 고정비, 손익분기점, 월별 손익계산서, 재무상태표, 현금흐름표(계정 분류), 전표, 계정과목, 원천세, ClosingPeriod(결산마감), Budget(예산·초과 경고), Currency/ExchangeRate(다중통화), 외환손익, AR/AP Aging(자동 연체전환·연령별 시산표), 은행대사, SalesSettlement(배송비/플랫폼수수료 자동 전표), CostCenter/ProfitCenter(부서별 손익), DashboardWidget, 고급 리포트(YoY/MoM, 제품별 수익성) |
| **투자관리(Investment)** | 투자자, 투자라운드, 지분추적(도넛차트), 배당/분배 |
| **자산관리(Asset)** | 고정자산(취득가/잔존가/내용연수 검증), 감가상각(정액법/정률법), 이동, 인증(KC/CE/FCC/ISO/RoHS), 리스계약(운영/금융), 실사, 바코드/QR 태그 |
| **외부스토어(Marketplace)** | 네이버/쿠팡 연동, 주문 양방향 동기화(ERP→마켓플레이스 배송상태 푸시), 6단계 Import Wizard, 정산 자동매칭, 동기화 이력 |
| **문의관리(Inquiry)** | 멀티채널 문의, Claude AI 자동답변 초안, 답변 템플릿 |
| **정품등록(Warranty)** | 시리얼번호 인증, 보증기간 관리, QR 인증 |
| **결재(Approval)** | 다단계 결재 워크플로(순차/**병렬**/**조건부 분기**), **위임 결재**(부재 시 대체 결재자), 단계별 결재자, 문서 분류(구매/경비/예산/계약/휴가/출장/IT), 파일 첨부 |
| **광고관리(Advertising)** | 광고 플랫폼(Google/Naver/Kakao/Meta), 캠페인, 소재, 성과 추적(ROAS/CTR/CPC), 예산 |
| **WMS(창고관리)** | Zone/Bin, 입고배치, 피킹 리스트, 웨이브 피킹, 순환재고실사, 포장, 배송라벨 |
| **CMMS(설비보전)** | 설비등록, 예방/사후 정비, 작업지시, 예비부품, 가동중단, MTBF/MTTR 분석 |
| **PLM(제품수명관리)** | 버전관리, ECN(설계변경서), 도면/리비전, BOM 수명주기 |
| **QMS(품질관리)** | 품질계획, 수입/공정/출하검사, NCR(부적합), CAPA(시정/예방조치), SPC 분석 |
| **Forecast(수요예측/S&OP)** | 이동평균/가중평균/지수평활법, S&OP 미팅, 시나리오, 정확도 |
| **Helpdesk(헬프데스크)** | 멀티채널 티켓팅, SLA, 지식베이스, 담당자 배정, 에스컬레이션, 만족도 조사 |
| **Portal(포털)** | 고객/공급처 셀프서비스, PO 확인, 인보이스 조회, 배송추적 |
| **Logistics(물류/배송)** | 운송사, 배송추적, 운송비, 경로 최적화, 라스트마일 |
| **EDI(전자문서교환)** | PO/인보이스/ASN 메시지, 파트너 매핑, 큐, 자동처리 |
| **Subscription(구독)** | 정기과금 플랜, 사용량 미터링, 구독 수명주기(trial→active→cancelled), 결제 스케줄 |
| **Document(문서/계약)** | 버전관리, 카테고리, 보존정책, 계약 마일스톤, 자동갱신, 결재 연동 |
| **Expense(경비)** | 경비 보고서, 영수증 스캔, 정책 준수, 다단계 결재, 지급, 법인카드 |
| **ESG(컴플라이언스)** | 탄소배출, 지속가능성 지표(GHG Protocol), 체크리스트(ISO 14001/K-ESG), 실행계획 |
| **BI(비즈니스 인텔리전스)** | 리포트 빌더(7종 데이터 소스), 차트/테이블/KPI 대시보드, 드래그앤드롭 패널, 스케줄 내보내기, 드릴다운 |
| **RPA(자동화)** | 룰 기반 자동화 엔진, 이벤트/스케줄/조건 트리거, 알림/필드업데이트/웹훅 액션, 실행 로그 |

### 그룹웨어 모듈

| 모듈 | 설명 |
|------|------|
| **인사(HR)** | 부서, 직급, 직원 프로필, 인사발령, 조직도, Payroll(급여), PayrollConfig(4대보험 설정), SeverancePay(퇴직금), YearEndSettlement(연말정산), LaborConfig(근로기준법 준수: 연장근로·최저임금·연차), 주간 준수 배치 |
| **근태(Attendance)** | 출퇴근, 휴가 신청/승인, 연차 잔여 |
| **게시판(Board)** | 공지/자유 게시판, 글, 대댓글 |
| **일정(Calendar)** | FullCalendar.js, AJAX API |
| **메신저(Messenger)** | 사내 메신저(1:1/그룹), WebSocket 실시간 |
| **LMS(학습관리)** | 코스, 레슨, 수강신청, 진도, 수료증 |
| **Wiki(지식베이스)** | 카테고리, 아티클 버전, 검색 |
| **Project(프로젝트)** | 마일스톤, 태스크(칸반), 시간추적, 간트 |
| **Visitor(방문자)** | 방문 신청, 승인, 체크인/아웃, NDA, 배지 출력 |

### 시스템 모듈

| 모듈 | 설명 |
|------|------|
| **Core(공통)** | 대시보드(KPI 위젯, 자산/인증/리스 요약), 실시간 알림(WebSocket 푸시), Excel/PDF 내보내기, 바코드 생성, 백업/복원, 감사추적, 접근 로그 |
| **Accounts(사용자)** | 인증, RBAC(관리자/매니저/직원), 로그인 보호(django-axes) |
| **API** | REST API(79개 DRF ViewSet), JWT 인증(SimpleJWT), OpenAPI/Swagger |
| **Module Manager** | 플러그인 방식 모듈 아키텍처(설치별 기능 활성/비활성), 카테고리(규정준수/생산/구매/판매/회계/인사/시스템), 국가코드 필터(KR/US/universal), 의존성 체크, 요청 단위 태그 캐시, 관리자 토글 UI, **23개 등록 모듈** |
| **Store Modules** | 채널별 플러그인 스토어(네이버 스마트스토어/쿠팡/자사몰) |
| **Active Directory** | LDAP/AD 연동, 사용자/그룹 동기화, 그룹 정책 기반 역할 매핑 |

## 기술 스택

| 계층 | 기술 |
|------|------|
| 백엔드 | Django 5.x / Python 3.13 |
| 프론트엔드 | Django Templates + Tailwind CSS(로컬 빌드) + HTMX + Alpine.js + Chart.js + FullCalendar.js (전부 static/vendor/ 로컬) |
| 데이터베이스 | SQLite(개발) / PostgreSQL 16(운영) |
| 실시간 | Django Channels + WebSocket(Daphne ASGI) |
| 비동기 | Celery + Redis(작업 큐, 예약 백업, 인증 만료 알림, 리스 전표 자동생성, 월별 감가상각, 견적 만료, 안전재고·재주문점 알림, 입고지연, AR 연체 전환) |
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
# ⚠ 보안 경고: 최초 로그인 직후 이 기본 비밀번호를 반드시 변경하세요.
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
export DB_PASSWORD=your-secure-password
export SECRET_KEY=your-secret-key
export ALLOWED_HOSTS=your-domain.com

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
# 단위 테스트 (1800+ 테스트, --parallel)
python manage.py test apps/ -v 2 --parallel

# 검증 테스트 (보안/무결성/성능/워크플로/재해복구)
python manage.py test tests.verification -v 2 --parallel

# 전체 테스트
python manage.py test apps/ tests.verification -v 0 --parallel

# E2E (Playwright)
cd e2e && pytest -v

# 부하 테스트 (Locust)
cd loadtest && locust -f locustfile.py --host http://localhost:8000
```

**테스트 커버리지: 1844 테스트 (단위)**

검증 기준 152개 항목, 10개 카테고리:
- SEC-001~035: 보안 (OWASP Top 10)
- INT-001~030: 데이터 무결성
- PERF-001~015: 성능
- FUNC-001~030: 기능 워크플로
- AD-001~010: Active Directory 연동
- DR-001~012: 재해복구
- DEPLOY-001~010: 배포/통합
- COMPAT-001~005: 호환성
- UX-001~005: 사용자 경험

## 핵심 데이터 흐름

- **재고**: `StockMovement` 시그널이 `F()` 표현식으로 `Product.current_stock` 원자적 업데이트(경쟁조건 방지)
- **주문 확정**: 주문 CONFIRMED → reserved_stock 예약 + AR 자동생성 + 세금계산서 발행
- **주문 출하**: 주문 SHIPPED → 시그널 자동 OUT + reserved_stock 해제
- **FIFO/LIFO**: 입고 시 StockLot 자동생성, 출고 시 자동 소진(FIFO/LIFO)
- **생산**: 생산실적 → 완제품 IN + 원자재 OUT(트랜잭션)
- **MRP**: BOM 전개 + 부족분 자동 발주서
- **생산 취소**: ProductionPlan/WorkOrder CANCELLED → 재고이동 자동 복원
- **구매**: 입고확인 → 자동 재고 IN + PO 상태 전환
- **구매 취소**: PurchaseOrder CANCELLED → AP/세금계산서 soft delete(역방향 연쇄)
- **견적**: 원클릭 견적→주문 전환(항목 자동 복사)
- **세금**: `OrderItem.save()` → 10% 부가세 자동 계산
- **결재**: 다단계 결재(순차/병렬/조건부 분기) + 위임 결재 지원
- **AR/AP**: 결제 등록 → 잔액 자동 재계산
- **결산마감**: ClosingPeriod → 마감 월 전표 수정 차단
- **급여**: `Payroll.save()` → 4대보험/세금 자동 공제
- **자산 이동**: 자산 이동 → 부서/위치/담당자 갱신, 이력 기록
- **감가상각**: 월별 배치 → `F()` 원자적 장부가액 갱신
- **리스**: `LeaseContract.save()` → total_amount 자동 계산
- **마켓플레이스 정산**: 정산 자동매칭(금액/날짜/채널)
- **재무제표**: 손익계산서 + 재무상태표 + 현금흐름표 생성
- **시리얼**: 생산실적 → 자동 생성(제품 옵션) → 출고 시 FIFO 할당 → 출고별 시리얼 범위
- **반품 주문**: 반품 CONFIRMED → AR 환불 + SHIPPED → RETURN 재입고
- **교환 주문**: 반품 입고 + 신규 출고 + 차액 정산
- **주문 수정**: 확정된 주문 수량/가격 변경 → reserved_stock + AR + 세금계산서 재계산
- **AS AR**: 유상 AS COMPLETED → AR 자동생성, CANCELLED → AR soft delete
- **예산 경고**: VoucherLine 저장 → 예산 초과 경고 알림
- **외환손익**: 외화 AR/AP → 결산 시 환율 차액
- **안전재고**: 일일 배치 → safety_stock 미달 제품 알림
- **마켓플레이스 푸시**: Shipment SHIPPED → 네이버/쿠팡 배송상태 전송
- **부분출고**: ShipmentItem 생성 → shipped vs total 비교 → PARTIAL_SHIPPED/SHIPPED 자동 전환
- **정산 전표**: SalesSettlement 확정 → 배송비/플랫폼수수료 자동 복식부기 전표
- **보증 확인**: AS 요청 시리얼 입력 → ProductRegistration 자동 조회 → 보증 상태 자동 설정
- **자산 검증**: FixedAsset 생성 → 취득가/잔존가/내용연수 검증, 카테고리 기본값 적용
- **가격 규칙**: OrderItem/QuotationItem 저장 → PriceRule 자동 적용, 최소수량 검증
- **조건부 QC**: QualityInspection CONDITIONAL → 매니저 알림 → 승인(PASS)/거부(FAIL)
- **재주문점**: 일일 배치 → reorder_point 미달 제품 알림 + MRP 제안 수량
- **생산 Traceability**: ProductionRecord → ProductionBatch 자동 생성 → 정방향(배치→출고)/역방향(배치→BOM 원자재→StockLot) FIFO 기반 3단계 추적
- **병렬/조건부/위임 결재**: ApprovalStep mode=parallel → 전원 동시 처리, mode=conditional → 금액 기반 분기, mode=delegate → 부재 시 대체자 자동 위임
- **현금영수증**: 결제 시 CashReceipt 자동 발행(개인/법인, 공급가액/부가세 분리, 국세청 포맷 내보내기)
- **로트 안전 하한**: StockLot/WarehouseStock 갱신 시 `Greatest(F('qty') - 소진, 0)`으로 SQLite NUMERIC/REAL float drift 대응

## 보안

- RBAC: `AdminRequiredMixin`(사용자관리, 백업), `ManagerRequiredMixin`(회계, 투자, 인사)
- 로그인 보호: django-axes (5회 실패 → 1시간 잠금)
- API: JWT Bearer 토큰 (1시간 만료) + 세션 이중 인증
- 재고 업데이트: `F()` 표현식으로 경쟁조건 방지
- 파일 업로드: 확장자 화이트리스트 + 10MB 제한
- 운영: HSTS, SSL 리다이렉트, HttpOnly 쿠키, 8시간 세션 만료
- CSP: `unsafe-eval` 제거, 엄격한 Content Security Policy
- OWASP: OWASP Top 10 감사 통과
- 오프라인: 100% 오프라인 동작 가능 (모든 벤더 에셋 로컬)
- 감사추적: django-simple-history (전 모델), ISMS 감사 증적 대시보드 (접근 로그, 데이터 변경, 로그인 이력, 메타 감사)
- 접근 로그: `AccessLogMiddleware` (사용자/경로/응답시간)
- 감사 접근통제: `is_auditor` 역할 기반, 모든 감사 뷰 열람 기록
- 모니터링: Prometheus 메트릭 + Sentry 에러 추적

## 현재 규모

- **44개 앱**, **300+ 모델** (전체 이력 추적)
- **700+ 뷰**, **600+ 템플릿**, **600+ URL 엔드포인트**
- **~65,000줄** Python 코드 (마이그레이션 제외)
- **1844 테스트** (단위), **17개 E2E 파일**, **부하 테스트 스위트**
- **250+ 마이그레이션**, **25+ 패키지**
- **79개 REST API ViewSet** + JWT 인증
- **23개 등록 모듈** (InstalledModule, Phase 1 모듈식 아키텍처)

## 기여

개발 환경 설정과 작업 흐름은 [CONTRIBUTING.ko.md](CONTRIBUTING.ko.md)를 참조하세요.

## 보안 정책

보안 이슈는 [SECURITY.ko.md](SECURITY.ko.md)의 제보 절차를 따라 주세요.

## 라이선스

Proprietary
