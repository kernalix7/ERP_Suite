# ERP Suite API/URL 레퍼런스

모든 URL 엔드포인트를 앱별로 정리한 문서입니다.

## 코어 (core)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/` | `core:dashboard` | 메인 대시보드 |
| `/backup/` | `core:backup` | 데이터 백업/복원 페이지 |
| `/backup/download/` | `core:backup_download` | 백업 파일 다운로드 |
| `/trash/` | `core:trash` | 휴지통 (소프트 삭제 항목) |
| `/attachments/` | `core:attachment_list` | 증빙관리 |
| `/data-report/` | `core:data_report` | 데이터 가이드 |
| `/audit/` | `core:audit_dashboard` | 감사 대시보드 |
| `/audit/access-log/` | `core:audit_access_log` | 시스템 접근 로그 |
| `/audit/data-changes/` | `core:audit_data_changes` | 데이터 변경 이력 |
| `/audit/login-history/` | `core:audit_login_history` | 로그인/보안 이벤트 |
| `/audit/audit-log/` | `core:audit_audit_log` | 감사 열람 기록 |

## 계정관리 (accounts)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounts/login/` | `accounts:login` | 로그인 페이지 |
| `/accounts/logout/` | `accounts:logout` | 로그아웃 처리 |
| `/accounts/users/` | `accounts:user_list` | 사용자 목록 (관리자 전용) |
| `/accounts/users/create/` | `accounts:user_create` | 사용자 등록 |
| `/accounts/users/<id>/edit/` | `accounts:user_update` | 사용자 수정 |

## 재고관리 (inventory)

### 제품

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/inventory/products/` | `inventory:product_list` | 제품 목록 |
| `/inventory/products/create/` | `inventory:product_create` | 제품 등록 |
| `/inventory/products/<id>/` | `inventory:product_detail` | 제품 상세 |
| `/inventory/products/<id>/edit/` | `inventory:product_update` | 제품 수정 |
| `/inventory/products/<id>/delete/` | `inventory:product_delete` | 제품 삭제 |
| `/inventory/products/excel/` | `inventory:product_excel` | 제품 목록 Excel 다운로드 |

### 카테고리

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/inventory/categories/` | `inventory:category_list` | 카테고리 목록 |
| `/inventory/categories/create/` | `inventory:category_create` | 카테고리 등록 |
| `/inventory/categories/<id>/edit/` | `inventory:category_update` | 카테고리 수정 |

### 창고

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/inventory/warehouses/` | `inventory:warehouse_list` | 창고 목록 |
| `/inventory/warehouses/create/` | `inventory:warehouse_create` | 창고 등록 |
| `/inventory/warehouses/<id>/edit/` | `inventory:warehouse_update` | 창고 수정 |

### 입출고

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/inventory/movements/` | `inventory:movement_list` | 입출고 목록 |
| `/inventory/movements/create/` | `inventory:movement_create` | 입출고 등록 |
| `/inventory/movements/<id>/` | `inventory:movement_detail` | 입출고 상세 |

### 재고현황 및 도구

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/inventory/stock/` | `inventory:stock_status` | 재고현황 조회 |
| `/inventory/barcode/` | `inventory:barcode_scan` | 바코드 스캔 |
| `/inventory/warehouse-stock/` | `inventory:warehouse_stock` | 창고별 재고 |
| `/inventory/stock-count/` | `inventory:stockcount_list` | 재고실사 목록 |
| `/inventory/valuation/` | `inventory:valuation` | 재고평가 |

### 창고간 이동

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/inventory/transfers/` | `inventory:transfer_list` | 창고간이동 목록 |
| `/inventory/transfers/create/` | `inventory:transfer_create` | 창고간이동 등록 |

## 생산관리 (production)

### BOM

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/production/bom/` | `production:bom_list` | BOM 목록 |
| `/production/bom/create/` | `production:bom_create` | BOM 등록 |
| `/production/bom/<id>/` | `production:bom_detail` | BOM 상세 |
| `/production/bom/<id>/edit/` | `production:bom_update` | BOM 수정 |

### 생산계획

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/production/plans/` | `production:plan_list` | 생산계획 목록 |
| `/production/plans/create/` | `production:plan_create` | 생산계획 등록 |
| `/production/plans/<id>/` | `production:plan_detail` | 생산계획 상세 |
| `/production/plans/<id>/edit/` | `production:plan_update` | 생산계획 수정 |

### 작업지시

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/production/work-orders/` | `production:workorder_list` | 작업지시 목록 |
| `/production/work-orders/create/` | `production:workorder_create` | 작업지시 등록 |
| `/production/work-orders/<id>/` | `production:workorder_detail` | 작업지시 상세 |
| `/production/work-orders/<id>/edit/` | `production:workorder_update` | 작업지시 수정 |

### 생산실적

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/production/records/` | `production:record_list` | 생산실적 목록 |
| `/production/records/create/` | `production:record_create` | 생산실적 등록 |

### 품질검수

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/production/qc/` | `production:qc_list` | 품질검수 목록 |

### MRP 및 원가

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/production/mrp/` | `production:mrp` | MRP (소요량계획) |
| `/production/standard-cost/` | `production:stdcost_list` | 표준원가 목록 |
| `/production/cost-variance/` | `production:cost_variance` | 원가차이 분석 |

## 판매관리 (sales)

### 거래처

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/sales/partners/` | `sales:partner_list` | 거래처 목록 |
| `/sales/partners/create/` | `sales:partner_create` | 거래처 등록 |
| `/sales/partners/<id>/edit/` | `sales:partner_update` | 거래처 수정 |

### 고객

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/sales/customers/` | `sales:customer_list` | 고객 목록 |
| `/sales/customers/create/` | `sales:customer_create` | 고객 등록 |
| `/sales/customers/<id>/` | `sales:customer_detail` | 고객 상세 |
| `/sales/customers/<id>/edit/` | `sales:customer_update` | 고객 수정 |

### 주문

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/sales/orders/` | `sales:order_list` | 주문 목록 |
| `/sales/orders/create/` | `sales:order_create` | 주문 등록 |
| `/sales/orders/excel/` | `sales:order_excel` | 주문 목록 Excel 다운로드 |
| `/sales/orders/<id>/` | `sales:order_detail` | 주문 상세 |
| `/sales/orders/<id>/edit/` | `sales:order_update` | 주문 수정 |

### 견적

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/sales/quotes/` | `sales:quote_list` | 견적 목록 |

### 배송 및 택배사

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/sales/shipments/` | `sales:shipment_list` | 배송 목록 |
| `/sales/carriers/` | `sales:carrier_list` | 택배사 목록 |
| `/sales/sold-products/` | `sales:sold_product_list` | 판매기기 목록 |

### 거래처 분석

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/sales/partner-analysis/` | `sales:partner_analysis` | 거래처 분석 |

### 수수료

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/sales/commissions/rates/` | `sales:commission_rate_list` | 수수료율 목록 |
| `/sales/commissions/rates/create/` | `sales:commission_rate_create` | 수수료율 등록 |
| `/sales/commissions/rates/<id>/edit/` | `sales:commission_rate_update` | 수수료율 수정 |
| `/sales/commissions/` | `sales:commission_list` | 수수료내역 목록 |
| `/sales/commissions/create/` | `sales:commission_create` | 수수료내역 등록 |
| `/sales/commissions/summary/` | `sales:commission_summary` | 정산 요약 |

## AS관리 (service)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/service/requests/` | `service:request_list` | AS 접수 목록 |
| `/service/requests/create/` | `service:request_create` | AS 접수 등록 |
| `/service/requests/<id>/` | `service:request_detail` | AS 접수 상세 |
| `/service/requests/<id>/edit/` | `service:request_update` | AS 접수 수정 |
| `/service/repairs/create/` | `service:repair_create` | 수리 기록 등록 |

## 회계관리 (accounting)

### 대시보드

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/` | `accounting:dashboard` | 재무 대시보드 |

### 세율

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/tax-rates/` | `accounting:taxrate_list` | 세율 목록 |
| `/accounting/tax-rates/create/` | `accounting:taxrate_create` | 세율 등록 |
| `/accounting/tax-rates/<id>/edit/` | `accounting:taxrate_update` | 세율 수정 |

### 세금계산서

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/invoices/` | `accounting:taxinvoice_list` | 세금계산서 목록 |
| `/accounting/invoices/create/` | `accounting:taxinvoice_create` | 세금계산서 등록 |
| `/accounting/invoices/<id>/` | `accounting:taxinvoice_detail` | 세금계산서 상세 |
| `/accounting/invoices/<id>/edit/` | `accounting:taxinvoice_update` | 세금계산서 수정 |

### 부가세

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/vat-summary/` | `accounting:vat_summary` | 부가세 분기 집계 |

### 고정비

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/fixed-costs/` | `accounting:fixedcost_list` | 고정비 목록 |
| `/accounting/fixed-costs/create/` | `accounting:fixedcost_create` | 고정비 등록 |
| `/accounting/fixed-costs/<id>/edit/` | `accounting:fixedcost_update` | 고정비 수정 |

### 분석

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/breakeven/` | `accounting:breakeven` | 손익분기점 분석 |
| `/accounting/monthly-pl/` | `accounting:monthly_pl` | 월별 손익계산서 |

### 원천징수

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/withholding/` | `accounting:withholding_list` | 원천징수 목록 |
| `/accounting/withholding/create/` | `accounting:withholding_create` | 원천징수 등록 |
| `/accounting/withholding/<id>/edit/` | `accounting:withholding_update` | 원천징수 수정 |

### 계정과목

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/accounts/` | `accounting:accountcode_list` | 계정과목 목록 |
| `/accounting/accounts/create/` | `accounting:accountcode_create` | 계정과목 등록 |
| `/accounting/accounts/<id>/edit/` | `accounting:accountcode_update` | 계정과목 수정 |

### 전표

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/vouchers/` | `accounting:voucher_list` | 전표 목록 |
| `/accounting/vouchers/create/` | `accounting:voucher_create` | 전표 등록 |
| `/accounting/vouchers/<id>/` | `accounting:voucher_detail` | 전표 상세 |
| `/accounting/vouchers/<id>/edit/` | `accounting:voucher_update` | 전표 수정 |

### 장부/분석

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/ledger/` | `accounting:account_ledger` | 계정별 원장 |
| `/accounting/trial-balance/` | `accounting:trial_balance` | 시산표 |

### 예산

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/budgets/` | `accounting:budget_list` | 예산 목록 |
| `/accounting/budgets/report/` | `accounting:budget_report` | 예산 보고서 |

### 결산 마감

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/closing/` | `accounting:closing_list` | 결산 마감 목록 |

### 은행 대사

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/bank-reconciliation/` | `accounting:bank_reconciliation` | 은행 대사 |

### 계좌 및 이체

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/bank-accounts/` | `accounting:bankaccount_list` | 결제계좌 목록 |
| `/accounting/bank-accounts/dashboard/` | `accounting:bankaccount_dashboard` | 계좌 현황 |
| `/accounting/transfers/` | `accounting:transfer_list` | 계좌이체 목록 |

### 정산

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/settlements/` | `accounting:settlement_list` | 원가정산 목록 |
| `/accounting/sales-settlements/` | `accounting:sales_settlement_list` | 매출정산 목록 |

### 통화 및 환율

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/currencies/` | `accounting:currency_list` | 통화 목록 |
| `/accounting/exchange-rates/` | `accounting:exchangerate_list` | 환율 목록 |

### 미수금

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/ar/` | `accounting:ar_list` | 미수금 목록 |
| `/accounting/ar/aging/` | `accounting:ar_aging` | AR Aging 분석 |

### 미지급금

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/accounting/ap/` | `accounting:ap_list` | 미지급금 목록 |
| `/accounting/ap/aging/` | `accounting:ap_aging` | AP Aging 분석 |

## 결재 (approval)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/approval/` | `approval:approval_list` | 결재/품의 목록 |

## 고정자산 (asset)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/asset/` | `asset:asset_list` | 자산 목록 |
| `/asset/create/` | `asset:asset_create` | 자산 등록 |
| `/asset/depreciation/` | `asset:depreciation_run` | 감가상각 실행 |
| `/asset/summary/` | `asset:summary` | 자산 현황 |
| `/asset/categories/` | `asset:category_list` | 자산 분류 목록 |

## 광고관리 (advertising)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/advertising/` | `advertising:dashboard` | 광고 현황 |
| `/advertising/campaigns/` | `advertising:campaign_list` | 캠페인 목록 |
| `/advertising/creatives/` | `advertising:creative_list` | 광고소재 목록 |
| `/advertising/performance/` | `advertising:performance_list` | 성과분석 |
| `/advertising/budgets/` | `advertising:budget_list` | 광고예산 목록 |

## 투자관리 (investment)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/investment/` | `investment:dashboard` | 투자 대시보드 |
| `/investment/investors/` | `investment:investor_list` | 투자자 목록 |
| `/investment/investors/create/` | `investment:investor_create` | 투자자 등록 |
| `/investment/investors/<id>/` | `investment:investor_detail` | 투자자 상세 |
| `/investment/investors/<id>/edit/` | `investment:investor_update` | 투자자 수정 |
| `/investment/rounds/` | `investment:round_list` | 투자 라운드 목록 |
| `/investment/rounds/create/` | `investment:round_create` | 투자 라운드 등록 |
| `/investment/rounds/<id>/` | `investment:round_detail` | 투자 라운드 상세 |
| `/investment/rounds/<id>/edit/` | `investment:round_update` | 투자 라운드 수정 |
| `/investment/investments/create/` | `investment:investment_create` | 투자 내역 등록 |
| `/investment/equity/` | `investment:equity_overview` | 지분 현황 |
| `/investment/distributions/` | `investment:distribution_list` | 배당/분배 목록 |
| `/investment/distributions/create/` | `investment:distribution_create` | 배당/분배 등록 |
| `/investment/distributions/<id>/edit/` | `investment:distribution_update` | 배당/분배 수정 |

## 마켓플레이스 (marketplace)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/marketplace/` | `marketplace:dashboard` | 마켓플레이스 대시보드 |
| `/marketplace/orders/` | `marketplace:order_list` | 마켓플레이스 주문 목록 |
| `/marketplace/orders/<id>/` | `marketplace:order_detail` | 마켓플레이스 주문 상세 |
| `/marketplace/config/` | `marketplace:config` | 마켓플레이스 API 설정 |
| `/marketplace/sync-logs/` | `marketplace:sync_log_list` | 동기화 이력 목록 |
| `/marketplace/sync/` | `marketplace:manual_sync` | 수동 동기화 실행 |

## 문의관리 (inquiry)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/inquiry/` | `inquiry:dashboard` | 문의 대시보드 |
| `/inquiry/list/` | `inquiry:inquiry_list` | 문의 목록 |
| `/inquiry/create/` | `inquiry:inquiry_create` | 문의 등록 |
| `/inquiry/<id>/` | `inquiry:inquiry_detail` | 문의 상세 |
| `/inquiry/<id>/edit/` | `inquiry:inquiry_update` | 문의 수정 |
| `/inquiry/<id>/reply/` | `inquiry:reply_create` | 답변 등록 |
| `/inquiry/<id>/generate/` | `inquiry:llm_generate` | AI 답변 초안 생성 |
| `/inquiry/templates/` | `inquiry:template_list` | 답변 템플릿 목록 |
| `/inquiry/templates/create/` | `inquiry:template_create` | 답변 템플릿 등록 |
| `/inquiry/templates/<id>/edit/` | `inquiry:template_update` | 답변 템플릿 수정 |

## 정품등록 (warranty)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/warranty/` | `warranty:registration_list` | 정품등록 목록 |
| `/warranty/create/` | `warranty:registration_create` | 정품등록 등록 |
| `/warranty/<id>/` | `warranty:registration_detail` | 정품등록 상세 |
| `/warranty/<id>/edit/` | `warranty:registration_update` | 정품등록 수정 |
| `/warranty/check/` | `warranty:serial_check` | 시리얼번호 조회 (API) |
| `/warranty/verify/` | `warranty:warranty_verify` | 정품인증 (QR) |

## 인사관리 (hr)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/hr/org-chart/` | `hr:org_chart` | 조직도 |
| `/hr/departments/` | `hr:department_list` | 부서 목록 |
| `/hr/positions/` | `hr:position_list` | 직급 목록 |
| `/hr/employees/` | `hr:employee_list` | 직원 목록 |
| `/hr/actions/` | `hr:action_list` | 인사발령 목록 |
| `/hr/payroll/` | `hr:payroll_list` | 급여 목록 |
| `/hr/payroll/config/` | `hr:payroll_config` | 급여 설정 |

## 근태관리 (attendance)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/attendance/` | `attendance:dashboard` | 근태 현황 |
| `/attendance/check-in/` | `attendance:check_in` | 출근 |
| `/attendance/check-out/` | `attendance:check_out` | 퇴근 |
| `/attendance/records/` | `attendance:record_list` | 출퇴근 기록 목록 |
| `/attendance/leaves/` | `attendance:leave_list` | 휴가 신청 목록 |
| `/attendance/leave-balance/` | `attendance:leave_balance` | 연차 잔여 |

## 게시판 (board)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/board/` | `board:board_list` | 게시판 목록 |
| `/board/<slug>/` | `board:post_list` | 게시글 목록 |
| `/board/<slug>/<id>/` | `board:post_detail` | 게시글 상세 |
| `/board/<slug>/create/` | `board:post_create` | 게시글 작성 |

## 일정 (calendar_app)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/calendar/` | `calendar_app:calendar_view` | 캘린더 뷰 |
| `/calendar/events/` | `calendar_app:event_list` | 일정 목록 |
| `/calendar/events/create/` | `calendar_app:event_create` | 일정 등록 |
| `/calendar/api/events/` | `calendar_app:event_api` | 일정 API (JSON) |

## 메신저 (messenger)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/messenger/` | `messenger:chat_list` | 대화방 목록 |
| `/messenger/room/<id>/` | `messenger:chat_room` | 대화방 |
| `/messenger/direct/` | `messenger:create_direct` | 1:1 대화 생성 |
| `/messenger/group/` | `messenger:create_group` | 그룹 대화 생성 |

## Active Directory (ad)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/ad/` | `ad:dashboard` | AD 대시보드 |
| `/ad/domains/` | `ad:domain_list` | 도메인 목록 |
| `/ad/domains/create/` | `ad:domain_create` | 도메인 등록 |
| `/ad/domains/<id>/` | `ad:domain_detail` | 도메인 상세 |
| `/ad/domains/<id>/edit/` | `ad:domain_update` | 도메인 수정 |
| `/ad/groups/` | `ad:group_list` | AD 그룹 목록 |
| `/ad/groups/create/` | `ad:group_create` | AD 그룹 등록 |
| `/ad/groups/<id>/edit/` | `ad:group_update` | AD 그룹 수정 |
| `/ad/mappings/` | `ad:usermapping_list` | 사용자 매핑 목록 |
| `/ad/mappings/create/` | `ad:usermapping_create` | 사용자 매핑 등록 |
| `/ad/mappings/<id>/edit/` | `ad:usermapping_update` | 사용자 매핑 수정 |
| `/ad/sync-logs/` | `ad:synclog_list` | 동기화 로그 목록 |
| `/ad/policies/` | `ad:policy_list` | 그룹 정책 목록 |
| `/ad/policies/create/` | `ad:policy_create` | 그룹 정책 등록 |
| `/ad/policies/<id>/edit/` | `ad:policy_update` | 그룹 정책 수정 |
| `/ad/test-connection/` | `ad:test_connection` | AD 연결 테스트 |
| `/ad/manual-sync/` | `ad:manual_sync` | 수동 동기화 |

## REST API (api)

| URL 패턴 | 이름 | 설명 |
|----------|------|------|
| `/api/` | — | DRF Router (API 루트) |
| `/api/token/` | `token_obtain_pair` | JWT 토큰 발급 (POST) |
| `/api/token/refresh/` | `token_refresh` | JWT 토큰 갱신 (POST) |
| `/api/token/verify/` | `token_verify` | JWT 토큰 검증 (POST) |
