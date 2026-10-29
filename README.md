# ForgeWorks — Advanced Factory Management System (DBMS Project)

An enterprise-grade, runnable Flask + SQLite Factory Management System engineered for comprehensive DBMS academic demonstrations and portfolio presentation.

The project strictly implements the **Updated ER Diagram Architecture** with normalized schemas, 1:N & N:M cardinalities, composite primary keys, triggers, stored integrity constraints, and live SQL query laboratory.

---

## 🌟 What's New & Architecture Improvements (ER Diagram Match)

1. **Supplier–Raw Material (1:N):** One supplier can supply multiple raw materials with vendor details and direct foreign key referencing.
2. **Dedicated PRODUCT Catalog:** Finished goods catalog separated from production orders with unit prices, categories, and inventory valuation.
3. **ORDER_MATERIAL (Weak Entity / Junction):** Composite primary key `(order_id, material_id)` representing precise Bill of Materials (BOM) consumption per production batch.
4. **Machine Multi-Routing:** Production orders map to industrial machinery (`machines`), tracking equipment health and downtime.
5. **Employee Participation ("Works On" N:M):** Multi-employee assignments per production batch (`order_assignments`) with specific roles and hours logged.
6. **STORAGE Warehouses:** Dedicated storage tracking warehouse bays/silos, maximum capacities, current stock loads, and managing departments.
7. **MAINTENANCE Entity:** Tracks preventative schedules, breakdown service costs, and next due inspection dates for the machine fleet.
8. **Automated Triggers & Stock Audit:**
   - `raw_material_stock_audit`: Automatically captures all stock level adjustments into `stock_audit`.
   - `order_material_deduct_stock`: Automatically deducts raw material stock upon order allocation.

---

## 🗄️ Relational Schema & Tables

| Entity Table | Primary Key | Foreign Keys / Constraints | Description |
|---|---|---|---|
| `departments` | `dept_id` | Unique `dept_name`, `budget >= 0` | Factory divisions & budgets |
| `employees` | `emp_id` | `dept_id` → `departments`, `supervisor_id` → `employees` | Factory personnel & hierarchy |
| `suppliers` | `supplier_id` | Unique `email` | Industrial vendor network |
| `storage` | `storage_id` | `dept_id` → `departments`, `capacity > 0` | Warehouses, silos & capacities |
| `raw_materials` | `material_id` | `supplier_id` → `suppliers`, `storage_id` → `storage` | Raw stocks & reorder thresholds |
| `products` | `product_id` | Unique `product_name`, `unit_price >= 0` | Finished manufactured goods |
| `machines` | `machine_id` | `dept_id` → `departments` | Machine fleet & operating status |
| `production_orders`| `order_id` | `product_id`, `machine_id`, `supervisor_id` | Batch orders & schedules |
| `order_materials` | Composite `(order_id, material_id)` | `order_id` → `production_orders`, `material_id` → `raw_materials` | Bill of materials (BOM) |
| `order_assignments`| Composite `(order_id, emp_id)` | `order_id` → `production_orders`, `emp_id` → `employees` | "Works On" worker tracking |
| `maintenance` | `maint_id` | `machine_id` → `machines` | Machine service & overhaul logs |
| `stock_audit` | `id` | `material_id` → `raw_materials` | Historic audit trail from triggers |

---

## ⚡ SQL Query Lab & Features Included

- **17 Pre-configured DBMS Demo Queries:**
  - Multi-table JOINs (Product + Order + Machine + Supervisor)
  - Bill of Materials with composite PK `(order_id, material_id)`
  - Reorder alerts with `WHERE qty_in_stock <= min_stock_level`
  - Supplier scorecards & 1:N aggregations
  - Storage warehouse utilization percentage calculations
  - Machine maintenance cost aggregation and next due inspection dates
  - Department budget vs annual payroll analysis
  - Subqueries with `AVG(unit_cost)` and `HAVING` filters
  - Safe UPDATE demonstrating live SQLite trigger firing into `stock_audit`
  - Safe DELETE preview for resolved maintenance tasks
- **Interactive ER Diagram Viewer Tab:** Built directly inside the web interface with visual entity cards, PK/FK indicators, relationships, and architecture notes.
- **Full CRUD Capabilities:** Add and search records across all 10+ entities via the UI with relational foreign key dropdowns.
- **Bill of Materials (BOM) Explorer:** Click "View BOM" on any production order to see exact materials consumed, costs, and assigned team members.

---

## 🚀 How to Run Locally

### 1. Prerequisites
- Python 3.10+ installed

### 2. Setup Virtual Environment (Recommended)
```bash
python -m venv .venv
# On Windows Command Prompt:
.venv\Scripts\activate
# On PowerShell:
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the Application
```bash
python app.py
```

### 5. Open in Browser
Navigate to:
```
http://127.0.0.1:5000
```

> **Note on Resetting Database:** To restore the database to its pristine sample data at any time, click the **"↺ Reseed DB"** button in the sidebar or send a POST request to `/api/reset-db`.
