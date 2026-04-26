# Data Migration Guide (other solutions → ERP Suite)

**English** | [한국어](data_migration_guide_ko.md)

> Procedure for migrating data from other ERPs / spreadsheets / MES / POS into ERP Suite.
> Covers data-handling rules, model mappings, and validation steps.

## 1. Data-Handling Rules (must-know)

### 1.1 Common to all models

| Rule | Description |
|---|---|
| **BaseModel inheritance** | Every model inherits `apps.core.models.BaseModel` → auto-fills `created_at`, `updated_at`, `created_by`, `is_active`, `notes` |
| **Soft delete only** | Never call `delete()` — use `is_active=False`. Default manager `objects` returns only active rows; `all_objects` for everything |
| **simple_history** | Auto-tracks changes (`HistoricalRecords()`). Disable temporarily for one-shot imports if DB size is a concern |
| **Korean verbose_name** | Field labels in Korean |

### 1.2 Money / quantity

| Rule | Description |
|---|---|
| **KRW integer** | `DecimalField(max_digits=15, decimal_places=0)` — no decimals |
| **Quantities allow decimals** | `decimal_places=3` — kg, m³, etc. |
| **Exchange rate** | `decimal_places=4` |
| **Tax rate %** | `decimal_places=2` |

### 1.3 Concurrency / integrity

| Rule | Description |
|---|---|
| **F() atomic update** | Use `F('field') + value` for stock/balances — race-safe |
| **transaction.atomic** | Wrap multi-step ops |
| **Auto signals** | StockMovement / Order.status changes trigger auto side-effects (stock, AR, tax invoice). Decide upfront how migration handles them |

### 1.4 ClosingPeriod

- Months locked (`is_closed=True`) reject voucher/order edits
- Migrate historical data **before** locking, or temporarily disable

### 1.5 Auto side-effects from signals (caution)

| Trigger | Auto-creates |
|---|---|
| `Order.status='CONFIRMED'` | reserved_stock + AR + TaxInvoice |
| `Order.status='SHIPPED'` | OUT StockMovement + release reserved_stock |
| `OrderItem.save()` | VAT auto-compute by tax_type |
| `Payment` create | BankAccount.balance update + auto voucher (double entry) |
| `DepreciationRecord` create | FixedAsset.book_value update + auto voucher |
| `WithholdingTax` create | Auto voucher (commission expense / withholding payable / cash) |

→ Two import modes:
1. **Signals ON**: side-effects auto-created. Conflicts if source already has them.
2. **Signals OFF**: must import side-effect data separately. Integrity is your responsibility.

Recommended: master data ON; transaction data — case-by-case.

## 2. Migration Order (dependency chain)

```
[Phase 0] Environment prep
  └─ migrate, maintenance ON, backup

[Phase 1] System masters
  ├─ AccountCode, TaxRate, Currency/ExchangeRate
  ├─ BankAccount
  ├─ Department/Position
  └─ ClosingPeriod (optional)

[Phase 2] Domain masters
  ├─ Category, Warehouse
  ├─ Partner, Customer
  ├─ Product (current_stock=0; populate in Phase 4)
  ├─ User/EmployeeProfile
  ├─ AssetCategory
  └─ PlatformFinancialConfig

[Phase 3] Operational config
  ├─ CommissionRate, PriceRule
  ├─ BOM, StandardCost
  └─ PayrollConfig, LaborConfig

[Phase 4] Opening balances
  ├─ Product stock via StockMovement(IN)
  ├─ StockLot (if FIFO/LIFO)
  ├─ AR / AP
  ├─ BankAccount.balance
  └─ FixedAsset

[Phase 5] Historical transactions (optional)
  ├─ Quotations, Orders, OrderItems
  ├─ PurchaseOrders, GoodsReceipts
  ├─ TaxInvoices, CashReceipts
  ├─ Payments
  ├─ Vouchers, VoucherLines
  └─ ProductionRecords

[Phase 6] Validate
  └─ checklist (§5)
```

## 3. Tool Choice

### 3.1 django-import-export (Excel/CSV)

```python
from import_export import resources
class PartnerResource(resources.ModelResource):
    class Meta:
        model = Partner
        import_id_fields = ('code',)
        fields = ('code', 'name', 'partner_type', 'entity_type', ...)
```

Use admin `/admin/<app>/<model>/import/` or scripts.

### 3.2 Management commands (10K+ rows)

```python
class Command(BaseCommand):
    def handle(self, csv_path, dry_run=False, **opts):
        with open(csv_path) as f, transaction.atomic():
            for row in csv.DictReader(f):
                ...
            if dry_run:
                transaction.set_rollback(True)
```

### 3.3 Raw SQL (100K+ rows, signal bypass)

```python
with connection.cursor() as cursor:
    cursor.executemany("INSERT INTO inventory_product (...) VALUES (...)", rows)
```

⚠ Bypasses signals — must INSERT side-effect data manually.

### 3.4 bulk_create (mid-size, no signals)

```python
Product.objects.bulk_create([Product(...) for r in rows], batch_size=1000)
```

## 4. Key Model Mappings

### 4.1 Partner
- `code` (unique, autogen if blank)
- `entity_type` BUSINESS/INDIVIDUAL/FOREIGN
- `business_number` `123-45-67890`
- `phone`/`email`/`address` are EncryptedCharField/TextField (`max_length=500`)
- `default_sales_channel`/`default_payment_method` for new orders

### 4.2 Product
- `code` autogen by `product_type` if blank
- `product_type` RAW/SEMI/FINISHED/SERVICE/INTANGIBLE
- `valuation_method` AVG/FIFO/LIFO
- `net_realizable_value` for end-of-period lower-of-cost-or-NRV
- `current_stock` — populate via StockMovement(IN), not direct INSERT

### 4.3 Order
- `accounting_date` for platform/card timing differences
- `sales_channel` DIRECT/NAVER/COUPANG/OFFLINE/PHONE/OTHER
- `payment_method` CARD/BANK_TRANSFER/CASH/VIRTUAL_ACCOUNT/NAVER_PAY/KAKAO_PAY/PLATFORM/OTHER
- `tax_type` TAXABLE/ZERO_RATE/EXEMPT
- `revenue_recognition_method` DELIVERY/PROGRESS/COMPLETION

### 4.4 Voucher + VoucherLine
Double-entry — debits == credits (`is_balanced` enforced).

```python
with transaction.atomic():
    v = Voucher.objects.create(voucher_number=..., voucher_date=..., approval_status='APPROVED')
    VoucherLine.objects.create(voucher=v, account=cash, debit=1_000_000, credit=0)
    VoucherLine.objects.create(voucher=v, account=capital, debit=0, credit=1_000_000)
```

### 4.5 AR / AP
Create one record per outstanding balance with `amount - paid_amount = balance`.

### 4.6 Stock opening balance
```python
StockMovement.objects.create(
    movement_type='IN', product=p, warehouse=w,
    quantity=100, unit_price=p.cost_price,
    movement_date=date(2026, 1, 1), reference='Opening',
)
```
Signals auto-update `Product.current_stock` and create `StockLot`.

## 5. Validation Checklist

```
[ ] 1. Record counts match source (sample)
[ ] 2. Sum of Product.current_stock == source stock total
[ ] 3. Sum of AR open balance == source AR
[ ] 4. Sum of AP open balance == source AP
[ ] 5. Sum of BankAccount.balance == source bank balances
[ ] 6. Trial Balance debit == credit (`/accounting/trial-balance/`)
[ ] 7. ClosingPeriod state correct
[ ] 8. simple_history active
[ ] 9. No duplicate signal-generated rows
[ ] 10. Index/permission/cache rebuilds (`manage.py rebuild_index`)
[ ] 11. Celery beat schedule running
[ ] 12. PWA cache / static refreshed (`manage.py collectstatic`)
```

### Quick trial-balance check
```python
agg = VoucherLine.objects.filter(
    is_active=True, voucher__is_active=True,
    voucher__approval_status='APPROVED',
).aggregate(d=Sum('debit'), c=Sum('credit'))
assert agg['d'] == agg['c']
```

## 6. Common Pitfalls

| Pitfall | Mitigation |
|---|---|
| Plain phone too long for encryption | EncryptedCharField needs `max_length=500` |
| Direct stock INSERT | Use StockMovement(IN) instead |
| Bulk Order CONFIRMED | Signals trigger 1 AR + 1 TaxInvoice each — paginate |
| simple_history missing | bulk_create skips history; backfill needed |
| ClosingPeriod blocks | Disable lock during migration |
| FX rate missing | Pre-load ExchangeRate before order import |
| Negative stock | CheckConstraint blocks; clean source first |

## 7. Domain-Specific Tips

- **SAP/Oracle → ERP Suite**: hardest part is account-code mapping to K-GAAP codes (4xx revenue, 501-509 COGS, 52x SG&A, etc.). Verify trial balance first.
- **Excel → ERP Suite**: import_export covers partners/products. Roll up history into one opening voucher.
- **POS / Marketplace → ERP Suite**: use Marketplace Wizard (`/marketplace/wizard/fetch/`) for Naver/Coupang. POS daily sales can collapse into one Order/day.
- **WMS → ERP Suite**: insert WarehouseStock directly per warehouse; StockLot only if using FIFO/LIFO.

## 8. Example Run

```bash
python manage.py maintenance on --settings=config.settings.beta
python manage.py loaddata fixtures/master_accounts.json --settings=config.settings.beta
python manage.py loaddata fixtures/master_partners.json --settings=config.settings.beta
python manage.py migrate_products data/products.csv --settings=config.settings.beta
python manage.py migrate_opening_balance data/opening.json --settings=config.settings.beta
python manage.py validate_migration --settings=config.settings.beta
python manage.py maintenance off --settings=config.settings.beta
```

## 9. Rollback Strategy

Always rehearse on **beta DB** before prod:

```bash
sqlite3 local/db_prod.sqlite3 .dump > backup_$(date +%Y%m%d).sql
# or
pg_dump erp_prod > backup_$(date +%Y%m%d).sql
```

## 10. Reference Files

- `apps/core/models.py` — BaseModel
- `apps/sales/resources.py` — import_export Resource example
- `tests/verification/` — integrity tests (run after migration)
- `apps/<app>/management/commands/seed_*.py` — seed patterns

## 11. Built-in Helpers

- `seed_platform_configs` — platform financial config seed
- Marketplace Wizard — Naver/Coupang auto import
- import_export Resources for many models (per-app `resources.py`)
