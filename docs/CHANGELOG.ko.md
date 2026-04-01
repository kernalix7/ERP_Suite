# 변경 이력

[English](../CHANGELOG.md) | **한국어**

이 프로젝트의 주요 변경 사항은 이 문서에 기록됩니다.

형식은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 기반으로 하며,
버전 정책은 [Semantic Versioning](https://semver.org/lang/ko/)을 지향합니다.

## [Unreleased]

### 추가됨
- Django 앱 22개 (accounting, accounts, ad, advertising, api, approval, asset, attendance, board, calendar_app, core, hr, inquiry, inventory, investment, marketplace, messenger, production, purchase, sales, service, warranty)
- 110개 모델 (django-simple-history 감사 추적 포함)
- 260개 반응형 HTML 템플릿 (Tailwind CSS 로컬 빌드 + HTMX + Alpine.js)
- REST API (28 ViewSet, JWT 인증 SimpleJWT)
- 실시간 메신저 (Django Channels + WebSocket)
- Celery 비동기 작업 처리 (Redis 브로커)
- Docker Compose 배포 (7개 컨테이너: web, db, redis, celery_worker, celery_beat, prometheus, grafana)
- GitHub Actions CI 파이프라인 (test + lint + docker build)
- 988개 테스트 (877 단위 + 111 검증) -- 보안, 무결성, 성능, 워크플로, 재해복구
- E2E 테스트 (Playwright) 및 부하 테스트 (Locust)
- 한국어/영어 다국어 지원
- PWA manifest 및 서비스 워커
- 결재/품의 시스템 (다단계 결재, 첨부파일, GenericFK 문서 연결)
- 고정자산 관리 (자산 대장, 감가상각 정액법/정률법, 자산 분류)
- 광고 관리 (플랫폼, 캠페인, 소재, 성과 분석, 예산)
- Active Directory 연동 (도메인, OU, 그룹, 사용자 매핑, 동기화, 정책)
- MRP (소요량계획) — BOM 기반 자재 가용성 분석
- FIFO/LIFO/이동평균 재고평가법
- 표준원가 관리 (자재원가 + 노무비 + 간접비)
- 품질검수 (생산/입고 검수, 합격률 관리)
- 급여 관리 (4대 보험 자동 계산, 급여 설정)
- 다중통화 지원 (통화, 환율 관리)
- 배송추적 (택배사 관리, 운송장 추적, 배송 이력)
- 결산 마감 (월별 회계 마감)
- AR/AP Aging 분석
- 재고예약 (예약재고, 가용재고)
- 거래처 분석
- 예산 관리 (계정과목별 월 예산, 실적 대비, 집행율)
- 매출정산 (주문별 선택 정산, 수수료 지급 관리)
- 재고 LOT 추적 (배치별 수량/원가/유효기한)
- 재고실사 (실사번호, 차이 조정)
- 감사 증적 시스템 (ISMS 준거, 접근 로그, 변경 이력, 로그인 기록, 열람 기록)
- 증빙/첨부파일 시스템 (GenericFK 기반, MIME 검증)

### 수정됨
- F() 표현식을 통한 재고/금액 원자적 무결성 (경쟁조건 방지)
- 다단계 결재 워크플로 체인 일관성
