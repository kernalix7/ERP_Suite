# ERP Suite User Guide

## 1. Login / Logout

### Login
1. Access the system URL in your browser.
2. Enter the username and password issued by the administrator.
3. Click the **Login** button.

> **Warning:** If you enter an incorrect password 5 consecutive times, your account will be locked for 1 hour. To unlock your account, contact the administrator.

### Logout
- Click the **Logout icon** next to the user info at the bottom of the left sidebar.

## 2. Dashboard

This is the first screen you see after logging in.

- View key metrics (sales, inventory status, recent orders, etc.) at a glance.
- Navigate to each module via the left sidebar.
- The sidebar can be collapsed/expanded using the hamburger menu icon at the top.

## 3. Inventory Management

### Product Registration
1. Click **Inventory Management > Product Management** in the sidebar.
2. Click the **Register** button in the upper right.
3. Fill in the required fields:
   - **Product Code**: A unique code (e.g., `FD-001`)
   - **Product Name**: The name of the product
   - **Product Type**: Select from Raw Material / Semi-finished / Finished Product
   - **Unit**: Default is `EA`
   - **Selling Price / Cost**: Enter amounts
   - **Safety Stock**: Minimum quantity to maintain
4. Click the **Register** button to save.

### Category Management
- Manage product classifications under **Inventory Management > Categories**.
- You can create a hierarchical structure by assigning parent categories.

### Warehouse Management
- Register warehouses under **Inventory Management > Warehouse Management**.
- Enter the warehouse code, warehouse name, and location.

### Stock In/Out Registration
1. Click the **Register** button under **Inventory Management > Stock In/Out**.
2. Select the movement type:
   - **Stock In**: Goods received from external sources
   - **Stock Out**: Goods shipped to external destinations
   - **Inventory Adjustment (+/-)**: Stock correction after physical count
   - **Production In/Out**: Automatically generated during production
   - **Return**: Return processing
3. Enter the product, warehouse, quantity, and date, then save.

> When registering stock movements, the current stock of the corresponding product is automatically updated.

### Inter-Warehouse Transfer
1. Click the **Register** button under **Inventory Management > Inter-Warehouse Transfer**.
2. Enter the source warehouse, destination warehouse, product, quantity, and transfer date.
3. Upon saving, stock out from the source warehouse and stock in to the destination warehouse are processed automatically.

### Stock Status
- Check the current stock and safety stock status for all products under **Inventory Management > Stock Status**.
- Products below safety stock levels are highlighted in red.

### Barcode Scan
- Scan product barcodes for quick lookup under **Inventory Management > Barcode Scan**.

### Warehouse Stock
- View stock quantities broken down by warehouse under **Inventory Management > Warehouse Stock**.

### Stock Count (Physical Inventory)
- Conduct periodic physical inventory checks under **Inventory Management > Stock Count**.
- Compare system stock vs. actual stock and record differences.
- Apply adjustments to reconcile discrepancies.

### Inventory Valuation
- View inventory valuation using FIFO, LIFO, or weighted average methods under **Inventory Management > Inventory Valuation**.
- Products can be configured with different valuation methods (AVG / FIFO / LIFO).

### Stock Reservation
- Products have a reserved stock field. Available stock = Current Stock - Reserved Stock.
- Safety stock and lead time tracking are built in.

## 4. Production Management

### BOM (Bill of Materials) Registration
1. Click the **Register** button under **Production Management > BOM Management**.
2. Register the finished product and the list of raw materials/semi-finished products required to produce it.
3. Enter the required quantity for each material.

### Production Planning
1. Register a new plan under **Production Management > Production Plans**.
2. Enter the product to produce, planned quantity, and planned date.

### Work Orders
1. Create work orders based on production plans under **Production Management > Work Orders**.
2. Manage work order status (Pending -> In Progress -> Completed).

### Production Records
1. Record actual production results under **Production Management > Production Records**.
2. Upon production completion:
   - The finished product is automatically registered as stock in.
   - Raw materials are automatically registered as stock out according to the BOM.

### Quality Inspection
- Record inspection results for production and incoming goods under **Production Management > Quality Inspection**.
- Track pass/fail quantities and corrective actions.

### MRP (Material Requirements Planning)
- Analyze material availability based on BOM under **Production Management > MRP**.
- Identify material shortages before starting production.

### Standard Cost
- Define standard costs (material + labor + overhead) per product under **Production Management > Standard Cost**.
- Automatically calculates labor cost and overhead based on rates.

### Cost Variance Analysis
- Compare standard cost vs. actual cost under **Production Management > Cost Variance Analysis**.

## 5. Sales Management

### Partner Registration
1. Register partner (business) information under **Sales Management > Partners**.
2. Enter business registration number, representative name, contact information, etc.

### Customer Registration
- Manage individual customer information under **Sales Management > Customers**.

### Order Creation
1. Click the **Register** button under **Sales Management > Orders**.
2. Enter the customer/partner, order products, and quantities.
3. VAT (10%) is automatically calculated.
4. Upon order confirmation, stock out is automatically linked.

### Quotation
- Create quotations and convert them to orders with one click under **Sales Management > Quotations**.
- Quotation items are automatically copied to the order upon conversion.

### Commission Management
- Set commission rates per partner under **Sales Management > Commission Management**.
- Supports percentage-based and fixed-amount commission types.

### Partner Analysis
- View partner-level analytics under **Sales Management > Partner Analysis**.

### Shipping Carrier Management
- Register shipping carriers and tracking URL templates under **Sales Management > Carrier Management**.

### Shipment Tracking
- Create and track shipments under **Sales Management > Shipment Tracking**.
- Supports partial shipments with per-item tracking.
- Automatic tracking URL generation per carrier (CJ, Hanjin, Lotte, Logen, Korea Post).

## 6. After-Sales Service (AS) Management

### AS Request Registration
1. Click the **Register** button under **AS Management > AS Requests**.
2. Enter customer information, product, and symptoms.
3. Whether the item is within the warranty period is automatically displayed.

### Repair Processing
1. Click on a registered AS case to go to the detail page.
2. Record repair details and change the status (Received -> Repairing -> Completed).
3. Repair history is automatically tracked.

## 7. Purchase Management

### Purchase Order Creation
1. Click the **Register** button under **Purchase Management > Purchase Orders**.
2. Enter the supplier (partner), order items, quantities, and unit prices.
3. VAT is automatically calculated when applicable.

### Goods Receipt
1. Register received goods under **Purchase Management > Goods Receipts**.
2. Upon receipt confirmation, stock in is automatically processed for each item.
3. The purchase order status is automatically updated.

### Purchase Order Cancellation
- Cancelling a purchase order will automatically soft delete related AP records and tax invoices.
- If goods have already been received, cancellation is blocked.

## 8. Accounting Management

### Tax Invoices
- Register sales/purchase tax invoices under **Accounting Management > Tax Invoices**.
- Supply amount and tax amount are automatically calculated.

### VAT Summary
- View quarterly VAT status under **Accounting Management > VAT Summary**.

### Fixed Cost Management
- Register fixed expenses such as rent, labor costs, and equipment lease fees under **Accounting Management > Fixed Cost Management**.

### Break-Even Point
- Analyze the break-even point using Chart.js-based charts under **Accounting Management > Break-Even Point**.

### Monthly Profit & Loss
- View the monthly income statement under **Accounting Management > Monthly Profit & Loss**.

### Voucher Entry
1. Click the **Register** button under **Accounting Management > Vouchers**.
2. Select the voucher type (Receipt / Payment / Transfer).
3. Enter the account code, amount, and description.

### Withholding Tax
- Manage withholding tax records under **Accounting Management > Withholding Tax**.

### Account Ledger & Trial Balance
- View account-level ledgers under **Accounting Management > Account Ledger**.
- View the trial balance under **Accounting Management > Trial Balance**.

### Budget Management
- Set monthly budgets per account code under **Accounting Management > Budget Management**.
- Compare budgets vs. actuals under **Accounting Management > Budget Report**.

### Closing Period
- Manage monthly accounting closings under **Accounting Management > Closing Period**.

### Bank Reconciliation
- Reconcile bank transactions under **Accounting Management > Bank Reconciliation**.

### Bank Accounts & Transfers
- Manage payment accounts under **Accounting Management > Bank Accounts**.
- View account balance dashboard under **Accounting Management > Account Status**.
- Record inter-account transfers under **Accounting Management > Account Transfer**.

### Accounts Receivable / Payable
- Track receivables under **Accounting Management > Accounts Receivable**.
- Track payables under **Accounting Management > Accounts Payable**.
- View aging analysis under **Accounting Management > AR Aging** and **AP Aging**.

### Cost Settlement & Sales Settlement
- Run periodic cost settlements under **Accounting Management > Cost Settlement**.
- Manage order-level sales settlements under **Accounting Management > Sales Settlement**.

### Multi-Currency
- Manage currencies under **Accounting Management > Currency Management**.
- Track exchange rates under **Accounting Management > Exchange Rate Management**.
- Orders and purchase orders can specify currency and exchange rate.

### Tax Rate Management
- Manage tax rates under **Accounting Management > Tax Rates**.

### Account Codes
- Manage chart of accounts (asset/liability/equity/revenue/expense) under **Accounting Management > Account Codes**.

## 9. Investment Management

### Investor Registration
- Register investor information under **Investment Management > Investor Management**.

### Investment Rounds
- Create investment rounds and record investment details under **Investment Management > Investment Rounds**.

### Equity Overview
- View equity ratios in a donut chart under **Investment Management > Equity Overview**.

### Dividends / Distributions
- Record dividends and profit distributions under **Investment Management > Dividends / Distributions**.

## 10. Fixed Asset Management

### Asset Registration
- Register fixed assets under **Fixed Assets > Asset List**.
- Track acquisition cost, residual value, useful life, and depreciation method (straight-line or declining balance).

### Depreciation
- Run monthly depreciation under **Fixed Assets > Run Depreciation**.
- View accumulated depreciation and book value per asset.

### Asset Summary
- View asset summary statistics under **Fixed Assets > Asset Summary**.

### Asset Categories
- Manage asset classifications under **Fixed Assets > Asset Categories**.

## 11. Advertising Management

### Campaigns
- Manage ad campaigns across platforms under **Advertising > Campaigns**.
- Track budget, spending, and status per campaign.

### Ad Creatives
- Manage ad creatives (image, video, text, carousel) under **Advertising > Creatives**.

### Performance Analysis
- View impressions, clicks, conversions, CTR, CPC, and ROAS under **Advertising > Performance Analysis**.

### Ad Budget
- Plan and track monthly advertising budgets per platform under **Advertising > Ad Budget**.

## 12. Approval / Request Workflow

### Approval Requests
- Create approval requests under **Approval** in the sidebar.
- Supports multiple document categories: Purchase, Expense, Budget, Contract, General, Leave, Overtime, Travel, IT Request.
- Multi-step approval chain with per-step approver and comments.
- Attach files to approval requests.

## 13. HR / Payroll

### Organization
- View the org chart under **HR/Attendance > Org Chart**.
- Manage departments and positions.

### Employee Management
- Manage employee profiles (hire date, contract type, status, salary) under **HR/Attendance > Employees**.
- Track personnel actions (hire, promotion, transfer, resignation) under **HR/Attendance > Personnel Actions**.

### Payroll
- Generate monthly payroll under **HR/Attendance > Payroll Management**.
- Automatic calculation of 4 major insurance deductions and taxes.
- Configure yearly payroll parameters under **HR/Attendance > Payroll Config**.

### Attendance
- Clock in/out under **HR/Attendance > Attendance Records**.
- Submit and approve leave requests under **HR/Attendance > Leave**.
- View attendance dashboard under **HR/Attendance > Attendance Status**.

## 14. Marketplace Integration

### Configuration
1. Enter marketplace API authentication credentials under **Marketplace > Store Settings**.
2. Supports Naver Smart Store and Coupang integration.

### Order Synchronization
- Import orders using the sync button under **Marketplace > Dashboard**.
- View synchronized order lists under **Marketplace > Store Orders**.
- Check synchronization execution history under **Marketplace > Sync History**.

## 15. Inquiry Management

### Inquiry Registration / Management
1. Register inquiries by channel (Smart Store / Instagram / KakaoTalk) under **Inquiry Management > Inquiry List**.
2. Click the **Generate AI Reply** button in the inquiry detail to have Claude AI generate a draft reply.
3. Review/edit the generated draft, then register the reply.

### Reply Templates
- Register frequently used reply templates under **Inquiry Management > Reply Templates**.

## 16. Product Authentication

- Manage serial number-based product authentication under the **Product Authentication** menu.
- Warranty start and expiration dates are automatically calculated.
- You can look up product authenticity by serial number.

## 17. Groupware

### Board
- Post notices and general messages under the **Board** menu.
- Supports threaded comments and pinned posts.

### Calendar
- Manage personal, team, company, and meeting events under the **Calendar** menu.
- Integrated with FullCalendar.js.

### Messenger
- Real-time 1:1 and group chat under the **Messenger** menu.
- Supports text, file, and image messages via WebSocket.

### Audit Trail (Auditor Only)
- View the audit dashboard, access logs, data change history, login/security events, and audit access records under the **Audit Trail** menu.
- Requires auditor permission (`is_auditor`).

## 18. System Administration (Admin Only)

### User Management
- Manage user accounts and roles under **System Administration > User Management**.

### Data Guide
- View system data overview under **System Administration > Data Guide**.

### Backup / Restore
- Create and restore database backups under **System Administration > Backup / Restore**.

### Trash
- View and restore soft-deleted items under **System Administration > Trash**.

### Attachments
- Manage evidence/document attachments under **System Administration > Attachments**.

### AD Integration
- Configure Active Directory domains, groups, user mappings, and sync policies under **System Administration > AD Integration**.

## 19. Excel Download

Excel download functionality is available on each list page.

1. Navigate to the relevant list page (e.g., Product Management, Order List).
2. Click the **Excel Download** button.
3. A styled `.xlsx` file will be downloaded.

## 20. Backup / Restore

> Administrator (admin) privileges are required. See also "System Administration" above.
