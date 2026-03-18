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

### Commission Management
- Set commission rates per partner under **Sales Management > Commission Rates**.
- View generated commissions under **Sales Management > Commission Details**.
- Review settlement status by partner under **Sales Management > Settlement Summary**.

## 6. After-Sales Service (AS) Management

### AS Request Registration
1. Click the **Register** button under **AS Management > AS Requests**.
2. Enter customer information, product, and symptoms.
3. Whether the item is within the warranty period is automatically displayed.

### Repair Processing
1. Click on a registered AS case to go to the detail page.
2. Record repair details and change the status (Received -> Repairing -> Completed).
3. Repair history is automatically tracked.

## 7. Accounting Management

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

## 8. Investment Management

### Investor Registration
- Register investor information under **Investment Management > Investor Management**.

### Investment Rounds
- Create investment rounds and record investment details under **Investment Management > Investment Rounds**.

### Equity Overview
- View equity ratios in a donut chart under **Investment Management > Equity Overview**.

### Dividends / Distributions
- Record dividends and profit distributions under **Investment Management > Dividends / Distributions**.

## 9. Smart Store Integration

### Configuration
1. Enter Naver API authentication credentials under **Smart Store > Store Settings**.

### Order Synchronization
- Import orders using the sync button under **Smart Store > Store Dashboard**.
- View synchronized order lists under **Smart Store > Store Orders**.
- Check synchronization execution history under **Smart Store > Sync History**.

## 10. Inquiry Management

### Inquiry Registration / Management
1. Register inquiries by channel (Smart Store / Instagram / KakaoTalk) under **Inquiry Management > Inquiry List**.
2. Click the **Generate AI Reply** button in the inquiry detail to have Claude AI generate a draft reply.
3. Review/edit the generated draft, then register the reply.

### Reply Templates
- Register frequently used reply templates under **Inquiry Management > Reply Templates**.

## 11. Product Authentication

- Manage serial number-based product authentication under the **Product Authentication** menu.
- Warranty start and expiration dates are automatically calculated.
- You can look up product authenticity by serial number.

## 12. Excel Download

Excel download functionality is available on each list page.

1. Navigate to the relevant list page (e.g., Product Management, Order List).
2. Click the **Excel Download** button.
3. A styled `.xlsx` file will be downloaded.

## 13. Backup / Restore

> Administrator (admin) privileges are required.

### Backup
1. Click **System Management > Backup / Restore** in the sidebar.
2. Click the **Create Backup** button.
3. Download the generated backup file.

### Restore
1. Upload a backup file on the **Backup / Restore** page.
2. Click the **Restore** button.

> **Warning:** During restoration, current data will be replaced with data from the backup point in time. Be sure to back up your current data before restoring.
