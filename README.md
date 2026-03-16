# ERP Suite

제조업 기반 중소기업을 위한 범용 통합 ERP 시스템

## 주요 기능

### 재고관리
- 제품/원자재/반제품 마스터 관리
- 입출고 자동 재고 반영 (시그널 기반)
- 창고간 이동, 안전재고 알림
- 바코드 지원, Excel 다운로드

### 생산관리
- BOM(자재명세서) 관리
- 생산계획 → 작업지시 → 생산실적 워크플로우
- 생산 완료 시 완제품 입고 + 원자재 출고 자동 처리

### 판매관리
- 거래처/고객 관리
- 주문 생성 → 출고 자동 연동
- 부가세 10% 자동 계산
- 파트너 수수료율 설정 및 정산

### AS관리
- AS 접수/수리 워크플로우
- 보증기간 자동 확인
- 수리이력 추적

### 회계관리
- 세금계산서 (매출/매입)
- 부가세 분기 집계
- 고정비 관리 (임대/인건비/장비 등)
- 손익분기점 분석 (Chart.js)
- 월별 손익계산서
- 전표 작성 (입금/출금/대체)
- 계정과목 관리
- 원천징수 관리

### 투자관리
- 투자자/투자라운드 관리
- 지분율 추적 (도넛차트)
- 배당/수익분배 기록

### 스마트스토어 연동
- 네이버 스마트스토어 주문 동기화
- 동기화 이력 관리

### 문의관리
- 채널별 문의 통합 관리 (스마트스토어/인스타/카카오)
- Claude AI 기반 답변 초안 자동 생성
- 답변 템플릿 관리

### 정품등록
- 시리얼번호 기반 정품 인증
- 보증기간 관리
- API 조회 지원

### 시스템관리
- 역할기반 접근제어 (관리자/매니저/직원)
- 로그인 보호 (5회 실패 시 1시간 잠금)
- 데이터 백업/복원
- Excel 내보내기

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Django 5.x / Python 3.12 |
| Frontend | Django Templates + Tailwind CSS + HTMX + Alpine.js + Chart.js |
| Database | SQLite (개발) / PostgreSQL (운영) |
| 보안 | django-axes, RBAC, HSTS, CSP |
| 배포 | Docker Compose |

## 시작하기

### 사전 요구사항
- Python 3.12+
- pip

### 설치

```bash
# 저장소 복제
git clone https://github.com/your-org/ERP_Suite.git
cd ERP_Suite

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements/dev.txt

# 환경변수 설정
mkdir -p local
cp .env.example local/.env
# local/.env 파일을 편집하여 SECRET_KEY 등 설정

# 데이터베이스 마이그레이션
python manage.py migrate

# 관리자 계정 생성
python manage.py createsuperuser

# 개발 서버 실행
python manage.py runserver
```

브라우저에서 http://localhost:8000 으로 접속합니다.

### Docker 배포

```bash
# 환경변수 설정
export DB_PASSWORD=your-secure-password
export SECRET_KEY=your-secret-key
export ALLOWED_HOSTS=your-domain.com

# 컨테이너 빌드 및 실행
docker-compose up -d

# 데이터베이스 마이그레이션
docker-compose exec web python manage.py migrate

# 관리자 계정 생성
docker-compose exec web python manage.py createsuperuser
```

## 프로젝트 구조

```
ERP_Suite/
├── apps/
│   ├── core/          # 공통 모델, 믹스인, 유틸리티, 대시보드
│   ├── accounts/      # 사용자 인증, 역할 관리
│   ├── inventory/     # 재고관리 (제품, 창고, 입출고, 이동)
│   ├── production/    # 생산관리 (BOM, 생산계획, 작업지시, 실적)
│   ├── sales/         # 판매관리 (거래처, 고객, 주문, 수수료)
│   ├── service/       # AS관리 (접수, 수리이력)
│   ├── accounting/    # 회계관리 (세금계산서, 부가세, 고정비, 전표)
│   ├── investment/    # 투자관리 (투자자, 라운드, 지분, 배당)
│   ├── smartstore/    # 스마트스토어 연동
│   ├── inquiry/       # 문의관리 (문의, AI 답변, 템플릿)
│   └── warranty/      # 정품등록 (시리얼번호, 보증)
├── config/            # Django 설정 (base, development, production)
├── templates/         # HTML 템플릿 (앱별 하위 폴더)
├── static/            # 정적 파일 (CSS, JS, 이미지)
├── locale/            # 다국어 번역 파일
├── requirements/      # pip 의존성 (dev.txt, prod.txt)
├── docker-compose.yml # Docker Compose 설정
├── Dockerfile         # Docker 이미지 빌드
└── manage.py          # Django 관리 명령어
```

## 라이선스

Apache 2.0
