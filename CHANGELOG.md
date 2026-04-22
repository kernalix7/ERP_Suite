# Changelog

**English** | [한국어](docs/CHANGELOG.ko.md)

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Phase 19 (2026-04)
- Parallel / conditional / delegated approval workflow — ApprovalStep modes (sequential / parallel / conditional) + absence delegation
- CashReceipt module — cash receipt issuance (soldier/business type), supply/VAT split, National Tax Service format export
- ProductionBatch (3-tier traceability) — forward (batch→shipments), backward (batch→BOM materials→StockLots) via FIFO linkage
- Modular architecture Phase 1 — 23 independent InstalledModule gates with category/country-code filtering, dependency checker UI, request-scoped tag cache
- Production record hotfix — warehouse-scoped BOM availability pre-check in ProductionRecordForm.clean + `Greatest(F(...) - x, 0)` guard on StockLot/WarehouseStock updates to defend against SQLite NUMERIC/REAL float drift on CHECK constraints

### Added — Phase 5–18 (2026-01 ~ 2026-04)
- FIFO/LIFO inventory valuation — StockLot auto-creation on receipt, auto-consumption on outbound with `select_for_update()`
- WarehouseStock — per-warehouse stock separate from `Product.current_stock`
- Reserved stock management — auto-reservation on order CONFIRMED, auto-release on shipment/cancellation
- Partial shipment — ShipmentItem with serial range tracking, auto PARTIAL_SHIPPED/SHIPPED status transition
- SerialNumber tracking — per-product opt-in, auto-generation on production, FIFO shipment assignment
- StandardCost — standard costing with auto version generation and cost cascade
- QualityInspection — quality control with conditional approval workflow
- MRP — Material Requirements Planning with reorder point and multi-level BOM explosion
- WorkCenter + ProductionSchedule — capacity planning and Gantt data
- CostVariance — actual vs standard cost analysis
- Order modification on CONFIRMED — qty/price change triggers reserved_stock + AR + tax invoice recalculation
- Return / exchange order workflow — AR refund + RETURN stock movement + price-difference settlement
- PriceRule — min-quantity-enforced pricing, auto-applied on OrderItem/QuotationItem save
- CustomerTier, SalesTarget, SalesLead (CRM pipeline), CustomerSatisfaction (NPS), credit limit management
- RFQ (Request for Quotation) — response comparison, winner selection, PO conversion
- VendorScore — 4-axis supplier evaluation (delivery / quality / price / service)
- ShippingCarrier + ShipmentTracking — delivery tracking
- Marketplace push — Shipment SHIPPED auto-pushes tracking info to Naver/Coupang APIs
- 6-stage Marketplace Import Wizard + settlement auto-matching
- Fixed asset module — acquisition/residual/useful-life validation, straight-line/declining-balance depreciation, transfers, certifications (KC/CE/FCC/ISO/RoHS), lease contracts (operating/finance), audits, barcode/QR tags
- ClosingPeriod — period closing blocks voucher modifications for closed month
- Budget — budget management with overspend warning on VoucherLine post_save
- Currency/ExchangeRate — multi-currency support with foreign-exchange gain/loss reporting
- AR/AP Aging — auto-overdue transition (daily batch), aged trial balance
- Bank reconciliation — statement matching
- VAT return report — quarterly TaxInvoice sales/purchase aggregation
- SalesSettlement — auto-voucher for shipping costs + platform commissions (double-entry)
- CostCenter / ProfitCenter — departmental P&L via VoucherLine allocation
- DashboardWidget — customizable dashboard, advanced reports (YoY/MoM comparison, product profitability)
- Payroll — 4 major insurance + tax auto-deduction on save
- SeverancePay — last-3-months average wage × 30 × years-of-service calculation
- YearEndSettlement — progressive tax rate, income deduction by category
- LaborConfig — labor law compliance checks (overtime / minimum wage / annual leave), weekly batch
- 23 new apps — wms, cmms, plm, qms, forecast, helpdesk, portal, logistics, edi, subscription, document, expense, esg, bi, rpa, lms, wiki, project, visitor, advertising, approval (standalone), module_manager, store_modules
- ISMS-level audit dashboard — access logs, data changes, login history, meta-audit
- Warranty auto-verification — service request with serial auto-looks-up ProductRegistration

### Changed
- App count: 22 → **44**
- Model count: 107 → **300+**
- Template count: 250 → **600+**
- Test count: 988 → **1844**
- REST API ViewSets: 28 → **79**
- Migration count: 110 → **250+**

### Fixed
- Atomic stock/amount integrity via F() expressions (race-condition safe)
- Multi-step approval workflow chain consistency
- SQLite NUMERIC/REAL affinity drift on StockLot.remaining_quantity and WarehouseStock.quantity — floored with `Greatest(F(...) - consume, 0)`
- Production record registration incorrectly blocked when materials existed only in a non-selected warehouse — now shows per-material warehouse-scoped shortage before save
