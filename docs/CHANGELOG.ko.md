# 변경 이력

[English](../CHANGELOG.md) | **한국어**

이 프로젝트의 주요 변경 사항은 이 문서에 기록됩니다.

형식은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 기반으로 하며,
버전 정책은 [Semantic Versioning](https://semver.org/lang/ko/)을 지향합니다.

## [Unreleased]

### 추가됨
- Django 앱 20개 (재고, 생산, 판매, 구매, AS, 회계, 투자, 외부스토어, 문의, 정품등록, 광고, 인사, 근태, 게시판, 일정, 메신저, 공통, 사용자, AD, API)
- 82+ 모델 (django-simple-history 감사 추적 포함)
- 265+ 뷰 (RBAC 관리자/매니저/직원 접근 제어)
- 190+ 반응형 HTML 템플릿 (Tailwind CSS + HTMX + Alpine.js)
- REST API (13+ ViewSet, JWT 인증 SimpleJWT)
- 실시간 메신저 (Django Channels + WebSocket)
- Celery 비동기 작업 처리 (Redis 브로커)
- Docker Compose 배포 (7개 컨테이너: web, db, redis, celery_worker, celery_beat, prometheus, grafana)
- GitHub Actions CI 파이프라인 (test + lint + docker build)
- 440+ 테스트 (단위 + 검증) — 보안, 무결성, 성능, 워크플로, 재해복구
- E2E 테스트 (Playwright) 및 부하 테스트 (Locust)
- 한국어/영어 다국어 지원
- PWA manifest 및 서비스 워커

### 수정됨
- F() 표현식을 통한 재고/금액 원자적 무결성 (경쟁조건 방지)
- 다단계 결재 워크플로 체인 일관성
