# ERP Suite API/URL Reference

A document listing all URL endpoints organized by app.

## Core (core)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/` | `core:dashboard` | Main dashboard |
| `/backup/` | `core:backup` | Data backup/restore page |
| `/backup/download/` | `core:backup_download` | Backup file download |
| `/trash/` | `core:trash` | Soft-deleted item trash |
| `/attachments/` | `core:attachment_list` | Attachment management |
| `/data-report/` | `core:data_report` | Data guide/report |
| `/audit/` | `core:audit_dashboard` | Audit dashboard |
| `/audit/access-log/` | `core:audit_access_log` | System access log |
| `/audit/data-changes/` | `core:audit_data_changes` | Data change history |
| `/audit/login-history/` | `core:audit_login_history` | Login/security events |
| `/audit/audit-log/` | `core:audit_audit_log` | Audit access log |

## Accounts (accounts)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounts/login/` | `accounts:login` | Login page |
| `/accounts/logout/` | `accounts:logout` | Logout |
| `/accounts/users/` | `accounts:user_list` | User list (admin only) |
| `/accounts/users/create/` | `accounts:user_create` | Create user |
| `/accounts/users/<id>/edit/` | `accounts:user_update` | Edit user |

## Inventory (inventory)

### Products

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/inventory/products/` | `inventory:product_list` | Product list |
| `/inventory/products/create/` | `inventory:product_create` | Create product |
| `/inventory/products/<id>/` | `inventory:product_detail` | Product detail |
| `/inventory/products/<id>/edit/` | `inventory:product_update` | Edit product |
| `/inventory/products/<id>/delete/` | `inventory:product_delete` | Delete product |
| `/inventory/products/excel/` | `inventory:product_excel` | Product list Excel download |

### Categories

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/inventory/categories/` | `inventory:category_list` | Category list |
| `/inventory/categories/create/` | `inventory:category_create` | Create category |
| `/inventory/categories/<id>/edit/` | `inventory:category_update` | Edit category |

### Warehouses

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/inventory/warehouses/` | `inventory:warehouse_list` | Warehouse list |
| `/inventory/warehouses/create/` | `inventory:warehouse_create` | Create warehouse |
| `/inventory/warehouses/<id>/edit/` | `inventory:warehouse_update` | Edit warehouse |

### Stock Movements

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/inventory/movements/` | `inventory:movement_list` | Stock movement list |
| `/inventory/movements/create/` | `inventory:movement_create` | Create stock movement |
| `/inventory/movements/<id>/` | `inventory:movement_detail` | Stock movement detail |

### Stock Status & Tools

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/inventory/stock/` | `inventory:stock_status` | Stock status overview |
| `/inventory/barcode/` | `inventory:barcode_scan` | Barcode scan |
| `/inventory/warehouse-stock/` | `inventory:warehouse_stock` | Warehouse-level stock |
| `/inventory/stock-count/` | `inventory:stockcount_list` | Stock count list |
| `/inventory/valuation/` | `inventory:valuation` | Inventory valuation |

### Warehouse Transfers

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/inventory/transfers/` | `inventory:transfer_list` | Warehouse transfer list |
| `/inventory/transfers/create/` | `inventory:transfer_create` | Create warehouse transfer |

## Production (production)

### BOM

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/production/bom/` | `production:bom_list` | BOM list |
| `/production/bom/create/` | `production:bom_create` | Create BOM |
| `/production/bom/<id>/` | `production:bom_detail` | BOM detail |
| `/production/bom/<id>/edit/` | `production:bom_update` | Edit BOM |

### Production Plans

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/production/plans/` | `production:plan_list` | Production plan list |
| `/production/plans/create/` | `production:plan_create` | Create production plan |
| `/production/plans/<id>/` | `production:plan_detail` | Production plan detail |
| `/production/plans/<id>/edit/` | `production:plan_update` | Edit production plan |

### Work Orders

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/production/work-orders/` | `production:workorder_list` | Work order list |
| `/production/work-orders/create/` | `production:workorder_create` | Create work order |
| `/production/work-orders/<id>/` | `production:workorder_detail` | Work order detail |
| `/production/work-orders/<id>/edit/` | `production:workorder_update` | Edit work order |

### Production Records

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/production/records/` | `production:record_list` | Production record list |
| `/production/records/create/` | `production:record_create` | Create production record |

### Quality Inspection

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/production/qc/` | `production:qc_list` | Quality inspection list |

### MRP & Cost

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/production/mrp/` | `production:mrp` | MRP (Material Requirements Planning) |
| `/production/standard-cost/` | `production:stdcost_list` | Standard cost list |
| `/production/cost-variance/` | `production:cost_variance` | Cost variance analysis |

## Sales (sales)

### Partners

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/sales/partners/` | `sales:partner_list` | Partner list |
| `/sales/partners/create/` | `sales:partner_create` | Create partner |
| `/sales/partners/<id>/edit/` | `sales:partner_update` | Edit partner |

### Customers

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/sales/customers/` | `sales:customer_list` | Customer list |
| `/sales/customers/create/` | `sales:customer_create` | Create customer |
| `/sales/customers/<id>/` | `sales:customer_detail` | Customer detail |
| `/sales/customers/<id>/edit/` | `sales:customer_update` | Edit customer |

### Orders

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/sales/orders/` | `sales:order_list` | Order list |
| `/sales/orders/create/` | `sales:order_create` | Create order |
| `/sales/orders/excel/` | `sales:order_excel` | Order list Excel download |
| `/sales/orders/<id>/` | `sales:order_detail` | Order detail |
| `/sales/orders/<id>/edit/` | `sales:order_update` | Edit order |

### Quotations

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/sales/quotes/` | `sales:quote_list` | Quotation list |

### Shipments & Carriers

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/sales/shipments/` | `sales:shipment_list` | Shipment list |
| `/sales/carriers/` | `sales:carrier_list` | Carrier list |
| `/sales/sold-products/` | `sales:sold_product_list` | Sold product list |

### Partner Analysis

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/sales/partner-analysis/` | `sales:partner_analysis` | Partner analysis |

### Commissions

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/sales/commissions/rates/` | `sales:commission_rate_list` | Commission rate list |
| `/sales/commissions/rates/create/` | `sales:commission_rate_create` | Create commission rate |
| `/sales/commissions/rates/<id>/edit/` | `sales:commission_rate_update` | Edit commission rate |
| `/sales/commissions/` | `sales:commission_list` | Commission record list |
| `/sales/commissions/create/` | `sales:commission_create` | Create commission record |
| `/sales/commissions/summary/` | `sales:commission_summary` | Settlement summary |

## Purchase (purchase)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/purchase/orders/` | `purchase:po_list` | Purchase order list |
| `/purchase/orders/create/` | `purchase:po_create` | Create purchase order |
| `/purchase/orders/<id>/` | `purchase:po_detail` | Purchase order detail |
| `/purchase/receipts/` | `purchase:receipt_list` | Receipt list |
| `/purchase/receipts/create/` | `purchase:receipt_create` | Create receipt |

## After-Sales Service (service)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/service/requests/` | `service:request_list` | Service request list |
| `/service/requests/create/` | `service:request_create` | Create service request |
| `/service/requests/<id>/` | `service:request_detail` | Service request detail |
| `/service/requests/<id>/edit/` | `service:request_update` | Edit service request |
| `/service/repairs/create/` | `service:repair_create` | Create repair record |

## Accounting (accounting)

### Dashboard

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/` | `accounting:dashboard` | Financial dashboard |

### Tax Rates

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/tax-rates/` | `accounting:taxrate_list` | Tax rate list |
| `/accounting/tax-rates/create/` | `accounting:taxrate_create` | Create tax rate |
| `/accounting/tax-rates/<id>/edit/` | `accounting:taxrate_update` | Edit tax rate |

### Tax Invoices

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/invoices/` | `accounting:taxinvoice_list` | Tax invoice list |
| `/accounting/invoices/create/` | `accounting:taxinvoice_create` | Create tax invoice |
| `/accounting/invoices/<id>/` | `accounting:taxinvoice_detail` | Tax invoice detail |
| `/accounting/invoices/<id>/edit/` | `accounting:taxinvoice_update` | Edit tax invoice |

### VAT

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/vat-summary/` | `accounting:vat_summary` | Quarterly VAT summary |

### Fixed Costs

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/fixed-costs/` | `accounting:fixedcost_list` | Fixed cost list |
| `/accounting/fixed-costs/create/` | `accounting:fixedcost_create` | Create fixed cost |
| `/accounting/fixed-costs/<id>/edit/` | `accounting:fixedcost_update` | Edit fixed cost |

### Analysis

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/breakeven/` | `accounting:breakeven` | Break-even point analysis |
| `/accounting/monthly-pl/` | `accounting:monthly_pl` | Monthly profit & loss statement |

### Withholding Tax

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/withholding/` | `accounting:withholding_list` | Withholding tax list |
| `/accounting/withholding/create/` | `accounting:withholding_create` | Create withholding tax |
| `/accounting/withholding/<id>/edit/` | `accounting:withholding_update` | Edit withholding tax |

### Account Codes

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/accounts/` | `accounting:accountcode_list` | Account code list |
| `/accounting/accounts/create/` | `accounting:accountcode_create` | Create account code |
| `/accounting/accounts/<id>/edit/` | `accounting:accountcode_update` | Edit account code |

### Vouchers

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/vouchers/` | `accounting:voucher_list` | Voucher list |
| `/accounting/vouchers/create/` | `accounting:voucher_create` | Create voucher |
| `/accounting/vouchers/<id>/` | `accounting:voucher_detail` | Voucher detail |
| `/accounting/vouchers/<id>/edit/` | `accounting:voucher_update` | Edit voucher |

### Account Ledger & Trial Balance

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/ledger/` | `accounting:account_ledger` | Account ledger |
| `/accounting/trial-balance/` | `accounting:trial_balance` | Trial balance |

### Budget

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/budgets/` | `accounting:budget_list` | Budget list |
| `/accounting/budgets/report/` | `accounting:budget_report` | Budget report |

### Closing Period

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/closing/` | `accounting:closing_list` | Closing period list |

### Bank Reconciliation

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/bank-reconciliation/` | `accounting:bank_reconciliation` | Bank reconciliation |

### Bank Accounts & Transfers

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/bank-accounts/` | `accounting:bankaccount_list` | Bank account list |
| `/accounting/bank-accounts/dashboard/` | `accounting:bankaccount_dashboard` | Bank account dashboard |
| `/accounting/transfers/` | `accounting:transfer_list` | Account transfer list |

### Settlements

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/settlements/` | `accounting:settlement_list` | Cost settlement list |
| `/accounting/sales-settlements/` | `accounting:sales_settlement_list` | Sales settlement list |

### Currency & Exchange Rate

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/currencies/` | `accounting:currency_list` | Currency list |
| `/accounting/exchange-rates/` | `accounting:exchangerate_list` | Exchange rate list |

### Accounts Receivable

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/ar/` | `accounting:ar_list` | Accounts receivable list |
| `/accounting/ar/aging/` | `accounting:ar_aging` | AR aging analysis |

### Accounts Payable

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/ap/` | `accounting:ap_list` | Accounts payable list |
| `/accounting/ap/aging/` | `accounting:ap_aging` | AP aging analysis |

### Payments

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/accounting/payments/` | `accounting:payment_list` | Payment list |

## Approval (approval)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/approval/` | `approval:approval_list` | Approval request list |

## Fixed Assets (asset)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/asset/` | `asset:asset_list` | Asset list |
| `/asset/create/` | `asset:asset_create` | Create asset |
| `/asset/depreciation/` | `asset:depreciation_run` | Run depreciation |
| `/asset/summary/` | `asset:summary` | Asset summary |
| `/asset/categories/` | `asset:category_list` | Asset category list |

## Advertising (advertising)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/advertising/` | `advertising:dashboard` | Advertising dashboard |
| `/advertising/campaigns/` | `advertising:campaign_list` | Campaign list |
| `/advertising/creatives/` | `advertising:creative_list` | Creative list |
| `/advertising/performance/` | `advertising:performance_list` | Performance list |
| `/advertising/budgets/` | `advertising:budget_list` | Ad budget list |

## Investment (investment)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/investment/` | `investment:dashboard` | Investment dashboard |
| `/investment/investors/` | `investment:investor_list` | Investor list |
| `/investment/investors/create/` | `investment:investor_create` | Create investor |
| `/investment/investors/<id>/` | `investment:investor_detail` | Investor detail |
| `/investment/investors/<id>/edit/` | `investment:investor_update` | Edit investor |
| `/investment/rounds/` | `investment:round_list` | Investment round list |
| `/investment/rounds/create/` | `investment:round_create` | Create investment round |
| `/investment/rounds/<id>/` | `investment:round_detail` | Investment round detail |
| `/investment/rounds/<id>/edit/` | `investment:round_update` | Edit investment round |
| `/investment/investments/create/` | `investment:investment_create` | Create investment record |
| `/investment/equity/` | `investment:equity_overview` | Equity overview |
| `/investment/distributions/` | `investment:distribution_list` | Dividend/distribution list |
| `/investment/distributions/create/` | `investment:distribution_create` | Create dividend/distribution |
| `/investment/distributions/<id>/edit/` | `investment:distribution_update` | Edit dividend/distribution |

## Marketplace (marketplace)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/marketplace/` | `marketplace:dashboard` | Marketplace dashboard |
| `/marketplace/orders/` | `marketplace:order_list` | Marketplace order list |
| `/marketplace/orders/<id>/` | `marketplace:order_detail` | Marketplace order detail |
| `/marketplace/config/` | `marketplace:config` | Marketplace API configuration |
| `/marketplace/sync-logs/` | `marketplace:sync_log_list` | Sync log list |
| `/marketplace/sync/` | `marketplace:manual_sync` | Manual sync execution |

## Inquiry (inquiry)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/inquiry/` | `inquiry:dashboard` | Inquiry dashboard |
| `/inquiry/list/` | `inquiry:inquiry_list` | Inquiry list |
| `/inquiry/create/` | `inquiry:inquiry_create` | Create inquiry |
| `/inquiry/<id>/` | `inquiry:inquiry_detail` | Inquiry detail |
| `/inquiry/<id>/edit/` | `inquiry:inquiry_update` | Edit inquiry |
| `/inquiry/<id>/reply/` | `inquiry:reply_create` | Create reply |
| `/inquiry/<id>/generate/` | `inquiry:llm_generate` | Generate AI reply draft |
| `/inquiry/templates/` | `inquiry:template_list` | Reply template list |
| `/inquiry/templates/create/` | `inquiry:template_create` | Create reply template |
| `/inquiry/templates/<id>/edit/` | `inquiry:template_update` | Edit reply template |

## Warranty (warranty)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/warranty/` | `warranty:registration_list` | Product registration list |
| `/warranty/create/` | `warranty:registration_create` | Create product registration |
| `/warranty/<id>/` | `warranty:registration_detail` | Product registration detail |
| `/warranty/<id>/edit/` | `warranty:registration_update` | Edit product registration |
| `/warranty/check/` | `warranty:serial_check` | Serial number lookup (API) |
| `/warranty/verify/` | `warranty:warranty_verify` | Warranty QR verification |

## HR (hr)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/hr/org-chart/` | `hr:org_chart` | Organization chart |
| `/hr/departments/` | `hr:department_list` | Department list |
| `/hr/positions/` | `hr:position_list` | Position list |
| `/hr/employees/` | `hr:employee_list` | Employee list |
| `/hr/actions/` | `hr:action_list` | Personnel action list |
| `/hr/payroll/` | `hr:payroll_list` | Payroll list |
| `/hr/payroll/config/` | `hr:payroll_config` | Payroll configuration |

## Attendance (attendance)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/attendance/` | `attendance:dashboard` | Attendance dashboard |
| `/attendance/check-in/` | `attendance:check_in` | Clock in |
| `/attendance/check-out/` | `attendance:check_out` | Clock out |
| `/attendance/records/` | `attendance:record_list` | Attendance record list |
| `/attendance/leaves/` | `attendance:leave_list` | Leave request list |
| `/attendance/leave-balance/` | `attendance:leave_balance` | Leave balance |

## Board (board)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/board/` | `board:board_list` | Board list |
| `/board/<slug>/` | `board:post_list` | Post list |
| `/board/<slug>/<id>/` | `board:post_detail` | Post detail |
| `/board/<slug>/create/` | `board:post_create` | Create post |

## Calendar (calendar_app)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/calendar/` | `calendar_app:calendar_view` | Calendar view |
| `/calendar/events/` | `calendar_app:event_list` | Event list |
| `/calendar/events/create/` | `calendar_app:event_create` | Create event |
| `/calendar/api/events/` | `calendar_app:event_api` | Event API (JSON) |

## Messenger (messenger)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/messenger/` | `messenger:chat_list` | Chat list |
| `/messenger/room/<id>/` | `messenger:chat_room` | Chat room |
| `/messenger/direct/` | `messenger:create_direct` | Create direct message |
| `/messenger/group/` | `messenger:create_group` | Create group chat |

## Active Directory (ad)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/ad/` | `ad:dashboard` | AD Dashboard |
| `/ad/domains/` | `ad:domain_list` | Domain list |
| `/ad/domains/create/` | `ad:domain_create` | Create domain |
| `/ad/domains/<id>/` | `ad:domain_detail` | Domain detail |
| `/ad/domains/<id>/edit/` | `ad:domain_update` | Edit domain |
| `/ad/groups/` | `ad:group_list` | AD group list |
| `/ad/groups/create/` | `ad:group_create` | Create AD group |
| `/ad/groups/<id>/edit/` | `ad:group_update` | Edit AD group |
| `/ad/mappings/` | `ad:usermapping_list` | User mapping list |
| `/ad/mappings/create/` | `ad:usermapping_create` | Create user mapping |
| `/ad/mappings/<id>/edit/` | `ad:usermapping_update` | Edit user mapping |
| `/ad/sync-logs/` | `ad:synclog_list` | Sync log list |
| `/ad/policies/` | `ad:policy_list` | Group policy list |
| `/ad/policies/create/` | `ad:policy_create` | Create group policy |
| `/ad/policies/<id>/edit/` | `ad:policy_update` | Edit group policy |
| `/ad/test-connection/` | `ad:test_connection` | Test AD connection |
| `/ad/manual-sync/` | `ad:manual_sync` | Manual sync |

## REST API (api)

| URL Pattern | Name | Description |
|-------------|------|-------------|
| `/api/` | — | DRF Router (browsable API root) |
| `/api/token/` | `token_obtain_pair` | JWT token obtain (POST) |
| `/api/token/refresh/` | `token_refresh` | JWT token refresh (POST) |
| `/api/token/verify/` | `token_verify` | JWT token verify (POST) |
