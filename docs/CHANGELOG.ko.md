# 변경 이력

[English](../CHANGELOG.md) | **한국어**

이 프로젝트의 주요 변경 사항은 이 문서에 기록됩니다.

형식은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 기반으로 하며,
버전 정책은 [Semantic Versioning](https://semver.org/lang/ko/)을 지향합니다.

## [Unreleased]

### 추가됨 — Phase 19 (2026-04)
- 병렬/조건부/위임 결재 — ApprovalStep mode (sequential / parallel / conditional) + 부재 시 위임
- CashReceipt(현금영수증) 모듈 — 개인/법인 발행, 공급가액/부가세 분리, 국세청 포맷 내보내기
- ProductionBatch(3단계 Traceability) — 정방향(배치→출고), 역방향(배치→BOM 원자재→StockLot) FIFO 기반 연결
- 모듈식 아키텍처 Phase 1 — 23개 InstalledModule 게이팅, 카테고리/국가코드 필터, 의존성 체크 UI, 요청 단위 태그 캐시
- 생산실적 등록 핫픽스 — ProductionRecordForm.clean에 창고별 BOM 가용성 사전검증 추가, StockLot/WarehouseStock 갱신에 `Greatest(F(...) - x, 0)` 가드로 SQLite NUMERIC/REAL float drift 방어

### 추가됨 — Phase 5–18 (2026-01 ~ 2026-04)
- FIFO/LIFO 재고평가 — 입고 시 StockLot 자동 생성, 출고 시 `select_for_update()` 기반 자동 소진
- WarehouseStock — `Product.current_stock`과 별개의 창고별 재고
- 재고예약 — 주문 CONFIRMED 시 자동 예약, 출고/취소 시 자동 해제
- 부분출고 — ShipmentItem 시리얼 범위 추적, PARTIAL_SHIPPED/SHIPPED 자동 전환
- SerialNumber 추적 — 제품별 옵션, 생산 시 자동 생성, 출고 시 FIFO 할당
- StandardCost — 표준원가 자동 버전 생성 + 원가 캐스케이드
- QualityInspection — 조건부 승인 워크플로 품질 관리
- MRP — 재주문점 기반, 다단계 BOM 전개
- WorkCenter + ProductionSchedule — 가동률 계획 및 간트 데이터
- CostVariance — 실제 vs 표준원가 분석
- 확정된 주문 수정 — 수량/가격 변경 시 reserved_stock + AR + 세금계산서 재계산
- 반품/교환 주문 워크플로 — AR 환불 + RETURN 재입고 + 차액 정산
- PriceRule — 최소수량 검증, OrderItem/QuotationItem 저장 시 자동 적용
- CustomerTier, SalesTarget, SalesLead(CRM 파이프라인), CustomerSatisfaction(NPS), 신용한도 관리
- RFQ(견적요청) — 공급처 응답 비교, 낙찰, PO 전환
- VendorScore — 4항목(납기/품질/가격/서비스) 공급처 평가
- ShippingCarrier + ShipmentTracking — 배송 추적
- 마켓플레이스 푸시 — Shipment SHIPPED → 네이버/쿠팡 API 배송상태 전송
- 6단계 마켓플레이스 Import Wizard + 정산 자동매칭
- 고정자산 모듈 — 취득가/잔존가/내용연수 검증, 정액법/정률법 감가상각, 이동, 인증(KC/CE/FCC/ISO/RoHS), 리스계약(운영/금융), 실사, 바코드/QR 태그
- ClosingPeriod — 결산 마감 시 해당 월 전표 수정 차단
- Budget — 예산 관리, VoucherLine post_save 시 초과 경고
- Currency/ExchangeRate — 다중통화 + 외환손익 리포트
- AR/AP Aging — 자동 연체 전환(일일 배치), 연령별 시산표
- 은행대사 — 거래내역 매칭
- 부가세 신고 리포트 — 분기별 TaxInvoice 매출/매입 집계
- SalesSettlement — 배송비 + 플랫폼 수수료 복식부기 자동 전표
- CostCenter / ProfitCenter — VoucherLine 배부를 통한 부서별 손익
- DashboardWidget — 커스터마이즈 대시보드, 고급 리포트(YoY/MoM, 제품별 수익성)
- Payroll — 저장 시 4대보험 + 세금 자동 공제
- SeverancePay — 최근 3개월 평균임금 × 30 × 근속일수/365
- YearEndSettlement — 누진세율, 소득공제 항목별 계산
- LaborConfig — 근로기준법 준수 점검(연장근로/최저임금/연차), 주간 배치
- 신규 앱 23개 — wms, cmms, plm, qms, forecast, helpdesk, portal, logistics, edi, subscription, document, expense, esg, bi, rpa, lms, wiki, project, visitor, advertising, approval(독립), module_manager, store_modules
- ISMS 감사 증적 대시보드 — 접근 로그, 데이터 변경, 로그인 이력, 메타 감사
- 보증 자동 확인 — AS 요청 시리얼 입력 시 ProductRegistration 자동 조회

### 변경됨
- 앱 수: 22 → **44**
- 모델 수: 107 → **300+**
- 템플릿 수: 250 → **600+**
- 테스트 수: 988 → **1844**
- REST API ViewSet: 28 → **79**
- 마이그레이션 수: 110 → **250+**

### 수정됨
- F() 표현식을 통한 재고/금액 원자적 무결성 (경쟁조건 방지)
- 다단계 결재 워크플로 체인 일관성
- SQLite NUMERIC/REAL affinity drift 방어 — StockLot.remaining_quantity, WarehouseStock.quantity 갱신에 `Greatest(F(...) - 소진, 0)` 하한
- 생산실적 등록이 선택 창고에 자재 없을 때 부정확하게 차단되던 문제 — 저장 전에 창고별 자재별 부족분을 표시
