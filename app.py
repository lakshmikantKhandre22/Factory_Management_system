from contextlib import contextmanager
from datetime import date
import sqlite3
from pathlib import Path
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_PATH = Path(__file__).with_name("factory.db")

QUERY_DEMOS = {
    "raw_materials_all": (
        """SELECT rm.material_id, rm.material_name, rm.unit, rm.qty_in_stock, 
                  rm.min_stock_level, rm.unit_cost, s.supplier_name
           FROM raw_materials rm
           JOIN suppliers s ON s.supplier_id = rm.supplier_id
           ORDER BY rm.material_name;""",
        "1. All Raw Materials & Suppliers (1:N Join)"
    ),
    "low_stock_reorder": (
        """SELECT rm.material_id, rm.material_name, rm.qty_in_stock, rm.min_stock_level,
                  rm.unit, (rm.min_stock_level - rm.qty_in_stock) AS shortage_qty,
                  s.supplier_name, s.contact_no
           FROM raw_materials rm
           JOIN suppliers s ON s.supplier_id = rm.supplier_id
           WHERE rm.qty_in_stock <= rm.min_stock_level
           ORDER BY shortage_qty DESC;""",
        "2. Reorder Alerts (Business Rule WHERE filter)"
    ),
    "supplier_materials_count": (
        """SELECT s.supplier_id, s.supplier_name, s.city, s.contact_no, s.email,
                  COUNT(rm.material_id) AS total_materials_supplied,
                  COALESCE(GROUP_CONCAT(rm.material_name, ', '), 'None') AS supplied_materials
           FROM suppliers s
           LEFT JOIN raw_materials rm ON rm.supplier_id = s.supplier_id
           GROUP BY s.supplier_id
           ORDER BY total_materials_supplied DESC;""",
        "3. Supplier-Raw Material 1:N Relationship & Grouping"
    ),
    "production_orders_full": (
        """SELECT po.order_id, p.product_name, p.category, po.quantity AS target_qty,
                  po.produced_qty, po.status, po.start_date, po.end_date,
                  e.emp_name AS supervisor, m.machine_name
           FROM production_orders po
           JOIN products p ON p.product_id = po.product_id
           JOIN employees e ON e.emp_id = po.supervisor_id
           LEFT JOIN machines m ON m.machine_id = po.machine_id
           ORDER BY po.order_id DESC;""",
        "4. Production Orders with Product, Supervisor & Machine (Multi-table JOIN)"
    ),
    "order_materials_bom": (
        """SELECT om.order_id, p.product_name, po.status AS order_status,
                  rm.material_name, om.qty_used, rm.unit,
                  ROUND(om.qty_used * rm.unit_cost, 2) AS material_cost
           FROM order_materials om
           JOIN production_orders po ON po.order_id = om.order_id
           JOIN products p ON p.product_id = po.product_id
           JOIN raw_materials rm ON rm.material_id = om.material_id
           ORDER BY om.order_id ASC, material_cost DESC;""",
        "5. Bill of Materials (BOM) with Composite PK (order_id, material_id)"
    ),
    "employee_works_on": (
        """SELECT oa.order_id, p.product_name, e.emp_name, e.role,
                  d.dept_name, oa.role_in_order, oa.hours_logged
           FROM order_assignments oa
           JOIN production_orders po ON po.order_id = oa.order_id
           JOIN products p ON p.product_id = po.product_id
           JOIN employees e ON e.emp_id = oa.emp_id
           JOIN departments d ON d.dept_id = e.dept_id
           ORDER BY oa.order_id ASC, oa.hours_logged DESC;""",
        "6. Employee Participation ('Works On' Tracking N:M)"
    ),
    "storage_capacity_utilization": (
        """SELECT s.storage_id, s.location, d.dept_name AS managing_dept,
                  s.capacity, s.current_stock,
                  ROUND((s.current_stock * 100.0) / s.capacity, 1) AS utilization_pct,
                  (s.capacity - s.current_stock) AS available_capacity
           FROM storage s
           JOIN departments d ON d.dept_id = s.dept_id
           ORDER BY utilization_pct DESC;""",
        "7. Storage Entity Capacity & Stock Tracking"
    ),
    "machine_maintenance_costs": (
        """SELECT m.machine_id, m.machine_name, m.status, d.dept_name,
                  COUNT(mt.maint_id) AS maintenance_count,
                  COALESCE(SUM(mt.cost), 0) AS total_spent,
                  MAX(mt.next_due_date) AS upcoming_due_date
           FROM machines m
           JOIN departments d ON d.dept_id = m.dept_id
           LEFT JOIN maintenance mt ON mt.machine_id = m.machine_id
           GROUP BY m.machine_id
           ORDER BY total_spent DESC;""",
        "8. Machine Fleet Maintenance Costs (1:N Machine-Maintenance)"
    ),
    "upcoming_maintenance_due": (
        """SELECT mt.maint_id, m.machine_name, mt.description, mt.priority,
                  mt.status, mt.cost, mt.next_due_date
           FROM maintenance mt
           JOIN machines m ON m.machine_id = mt.machine_id
           WHERE mt.status != 'Resolved'
           ORDER BY mt.next_due_date ASC;""",
        "9. Pending Maintenance by Due Date"
    ),
    "department_budget_payroll": (
        """SELECT d.dept_id, d.dept_name, d.location, d.budget,
                  COUNT(e.emp_id) AS total_employees,
                  COALESCE(SUM(e.salary), 0) AS monthly_payroll,
                  ROUND((COALESCE(SUM(e.salary), 0) * 12 * 100.0) / d.budget, 1) AS annual_payroll_pct_of_budget
           FROM departments d
           LEFT JOIN employees e ON e.dept_id = d.dept_id
           GROUP BY d.dept_id
           ORDER BY d.budget DESC;""",
        "10. Department Budget vs Annual Payroll"
    ),
    "products_catalog_valuation": (
        """SELECT product_id, product_name, category, unit_price, stock_qty,
                  ROUND(unit_price * stock_qty, 2) AS total_inventory_value
           FROM products
           ORDER BY total_inventory_value DESC;""",
        "11. Product Catalog Valuation (Calculated Columns)"
    ),
    "subquery_expensive_materials": (
        """SELECT material_id, material_name, unit, unit_cost, qty_in_stock
           FROM raw_materials
           WHERE unit_cost > (SELECT AVG(unit_cost) FROM raw_materials)
           ORDER BY unit_cost DESC;""",
        "12. Above-Average Cost Materials (Subquery + AVG)"
    ),
    "product_category_aggregates": (
        """SELECT category, COUNT(*) AS product_count,
                  SUM(stock_qty) AS total_units_in_stock,
                  ROUND(AVG(unit_price), 2) AS avg_unit_price
           FROM products
           GROUP BY category
           ORDER BY total_units_in_stock DESC;""",
        "13. Category Aggregates (GROUP BY + Aggregations)"
    ),
    "departments_having_machines": (
        """SELECT d.dept_name, d.location, COUNT(m.machine_id) AS machine_count
           FROM departments d
           JOIN machines m ON m.dept_id = d.dept_id
           GROUP BY d.dept_id
           HAVING COUNT(m.machine_id) >= 1
           ORDER BY machine_count DESC;""",
        "14. Departments Housing Multiple Machines (HAVING Clause)"
    ),
    "update_with_trigger": (
        """UPDATE raw_materials
           SET qty_in_stock = qty_in_stock + 20
           WHERE material_name = 'Steel Sheets (Cold Rolled)';""",
        "15. UPDATE Raw Material Stock (Fires raw_material_stock_audit trigger)"
    ),
    "audit_log_records": (
        """SELECT sa.id, rm.material_name, sa.old_quantity, sa.new_quantity,
                  sa.action_type, sa.changed_at
           FROM stock_audit sa
           JOIN raw_materials rm ON rm.material_id = sa.material_id
           ORDER BY sa.id DESC;""",
        "16. Trigger Stock Audit Log (Audit Trail Verification)"
    ),
    "delete_maintenance_preview": (
        """DELETE FROM maintenance WHERE status = 'Resolved';""",
        "17. DELETE Preview (Safe Demo: Resolved Maintenance)"
    )
}

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def init_db(force_reset=False):
    if force_reset and DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except Exception:
            pass

    with get_db() as db:
        # Check if new schema exists
        table_check = db.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='raw_materials'"
        ).fetchone()[0]

        if table_check > 0 and not force_reset:
            return

        db.executescript("""
        DROP TABLE IF EXISTS stock_audit;
        DROP TABLE IF EXISTS maintenance;
        DROP TABLE IF EXISTS order_assignments;
        DROP TABLE IF EXISTS order_materials;
        DROP TABLE IF EXISTS production_orders;
        DROP TABLE IF EXISTS machines;
        DROP TABLE IF EXISTS raw_materials;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS storage;
        DROP TABLE IF EXISTS employees;
        DROP TABLE IF EXISTS departments;
        DROP TABLE IF EXISTS suppliers;

        -- 1. SUPPLIER
        CREATE TABLE suppliers (
            supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT NOT NULL,
            contact_no TEXT NOT NULL,
            city TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        );

        -- 2. DEPARTMENT
        CREATE TABLE departments (
            dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_name TEXT NOT NULL UNIQUE,
            manager TEXT NOT NULL,
            phone TEXT NOT NULL,
            location TEXT NOT NULL,
            budget REAL NOT NULL CHECK(budget >= 0)
        );

        -- 3. EMPLOYEE
        CREATE TABLE employees (
            emp_id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_name TEXT NOT NULL,
            role TEXT NOT NULL,
            dept_id INTEGER NOT NULL,
            salary REAL NOT NULL CHECK(salary >= 0),
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'On Leave', 'Inactive')),
            supervisor_id INTEGER,
            joined_on TEXT NOT NULL,
            FOREIGN KEY(dept_id) REFERENCES departments(dept_id) ON DELETE RESTRICT,
            FOREIGN KEY(supervisor_id) REFERENCES employees(emp_id) ON DELETE SET NULL
        );

        -- 4. STORAGE
        CREATE TABLE storage (
            storage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL UNIQUE,
            capacity INTEGER NOT NULL CHECK(capacity > 0),
            current_stock INTEGER NOT NULL DEFAULT 0 CHECK(current_stock >= 0),
            dept_id INTEGER NOT NULL,
            FOREIGN KEY(dept_id) REFERENCES departments(dept_id) ON DELETE RESTRICT
        );

        -- 5. RAW_MATERIAL (1:N with SUPPLIER)
        CREATE TABLE raw_materials (
            material_id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_name TEXT NOT NULL,
            unit TEXT NOT NULL,
            qty_in_stock INTEGER NOT NULL CHECK(qty_in_stock >= 0),
            min_stock_level INTEGER NOT NULL CHECK(min_stock_level >= 0),
            unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
            supplier_id INTEGER NOT NULL,
            storage_id INTEGER,
            FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id) ON DELETE RESTRICT,
            FOREIGN KEY(storage_id) REFERENCES storage(storage_id) ON DELETE SET NULL
        );

        -- 6. PRODUCT
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            stock_qty INTEGER NOT NULL DEFAULT 0 CHECK(stock_qty >= 0)
        );

        -- 7. MACHINE
        CREATE TABLE machines (
            machine_id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'Operational' CHECK(status IN ('Operational', 'Under Maintenance', 'Idle', 'Offline')),
            install_date TEXT NOT NULL,
            dept_id INTEGER NOT NULL,
            FOREIGN KEY(dept_id) REFERENCES departments(dept_id) ON DELETE RESTRICT
        );

        -- 8. PRODUCTION_ORDER
        CREATE TABLE production_orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            produced_qty INTEGER NOT NULL DEFAULT 0 CHECK(produced_qty >= 0),
            status TEXT NOT NULL CHECK(status IN ('Planned', 'In Progress', 'Completed', 'Delayed')),
            start_date TEXT NOT NULL,
            end_date TEXT,
            machine_id INTEGER,
            supervisor_id INTEGER NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(product_id) ON DELETE RESTRICT,
            FOREIGN KEY(machine_id) REFERENCES machines(machine_id) ON DELETE SET NULL,
            FOREIGN KEY(supervisor_id) REFERENCES employees(emp_id) ON DELETE RESTRICT
        );

        -- 9. ORDER_MATERIAL (Composite PK weak entity / junction table)
        CREATE TABLE order_materials (
            order_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            qty_used INTEGER NOT NULL CHECK(qty_used > 0),
            PRIMARY KEY (order_id, material_id),
            FOREIGN KEY(order_id) REFERENCES production_orders(order_id) ON DELETE CASCADE,
            FOREIGN KEY(material_id) REFERENCES raw_materials(material_id) ON DELETE RESTRICT
        );

        -- 10. ORDER_ASSIGNMENTS ("Works On" employee participation N:M)
        CREATE TABLE order_assignments (
            order_id INTEGER NOT NULL,
            emp_id INTEGER NOT NULL,
            role_in_order TEXT NOT NULL DEFAULT 'Operator',
            hours_logged REAL NOT NULL DEFAULT 0 CHECK(hours_logged >= 0),
            PRIMARY KEY (order_id, emp_id),
            FOREIGN KEY(order_id) REFERENCES production_orders(order_id) ON DELETE CASCADE,
            FOREIGN KEY(emp_id) REFERENCES employees(emp_id) ON DELETE CASCADE
        );

        -- 11. MAINTENANCE
        CREATE TABLE maintenance (
            maint_id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id INTEGER NOT NULL,
            maint_date TEXT NOT NULL,
            description TEXT NOT NULL,
            cost REAL NOT NULL CHECK(cost >= 0),
            next_due_date TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High')),
            status TEXT NOT NULL DEFAULT 'Scheduled' CHECK(status IN ('Scheduled', 'In Progress', 'Resolved')),
            FOREIGN KEY(machine_id) REFERENCES machines(machine_id) ON DELETE CASCADE
        );

        -- 12. STOCK_AUDIT (Audit log trigger target)
        CREATE TABLE stock_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            old_quantity INTEGER NOT NULL,
            new_quantity INTEGER NOT NULL,
            action_type TEXT NOT NULL DEFAULT 'UPDATE',
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(material_id) REFERENCES raw_materials(material_id) ON DELETE CASCADE
        );

        -- TRIGGERS
        CREATE TRIGGER IF NOT EXISTS raw_material_stock_audit
        AFTER UPDATE OF qty_in_stock ON raw_materials
        WHEN OLD.qty_in_stock != NEW.qty_in_stock
        BEGIN
            INSERT INTO stock_audit(material_id, old_quantity, new_quantity, action_type)
            VALUES (OLD.material_id, OLD.qty_in_stock, NEW.qty_in_stock, 'STOCK_UPDATE');
        END;

        CREATE TRIGGER IF NOT EXISTS order_material_deduct_stock
        AFTER INSERT ON order_materials
        BEGIN
            UPDATE raw_materials
            SET qty_in_stock = MAX(0, qty_in_stock - NEW.qty_used)
            WHERE material_id = NEW.material_id;
        END;

        CREATE TRIGGER IF NOT EXISTS order_material_update_deduct_stock
        AFTER UPDATE OF qty_used ON order_materials
        BEGIN
            UPDATE raw_materials
            SET qty_in_stock = MAX(0, qty_in_stock - (NEW.qty_used - OLD.qty_used))
            WHERE material_id = NEW.material_id;
        END;
        """)

        # SEED DATA
        # 1. Departments
        db.executemany("""
            INSERT INTO departments(dept_name, manager, phone, location, budget)
            VALUES(?,?,?,?,?)
        """, [
            ("Production", "Meera Kulkarni", "+91 20 4101 1001", "Plant Floor A", 1500000.0),
            ("Fabrication & Machining", "Vikram Joshi", "+91 20 4101 1002", "Plant Floor B", 1200000.0),
            ("Quality Control", "Rohan Patil", "+91 20 4101 1003", "Testing Lab", 600000.0),
            ("Maintenance", "Anand Verma", "+91 20 4101 1004", "Engineering Bay", 750000.0),
            ("Logistics & Warehouse", "Sana Shaikh", "+91 20 4101 1005", "Central Depot", 850000.0)
        ])

        # 2. Employees
        db.executemany("""
            INSERT INTO employees(emp_name, role, dept_id, salary, status, supervisor_id, joined_on)
            VALUES(?,?,?,?,?,?,?)
        """, [
            ("Aarav Deshmukh", "Production Supervisor", 1, 65000.0, "Active", None, "2023-04-12"),
            ("Kabir Shah", "Senior CNC Operator", 2, 42000.0, "Active", 1, "2022-09-19"),
            ("Priya Nair", "Quality Lead Analyst", 3, 52000.0, "Active", None, "2024-01-08"),
            ("Neel Joshi", "Senior Maintenance Engineer", 4, 58000.0, "Active", None, "2021-06-21"),
            ("Isha More", "Inventory Coordinator", 5, 45000.0, "On Leave", None, "2023-11-03"),
            ("Ananya Rao", "Precision Machinist", 2, 39500.0, "Active", 2, "2024-06-15"),
            ("Dev Kulkarni", "Assembly Technician", 1, 36000.0, "Active", 1, "2023-08-10"),
            ("Rajesh Shinde", "Maintenance Technician", 4, 38000.0, "Active", 4, "2022-11-05")
        ])

        # 3. Suppliers
        db.executemany("""
            INSERT INTO suppliers(supplier_name, contact_no, city, email)
            VALUES(?,?,?,?)
        """, [
            ("Apex Industrial Supply", "+91 20 4102 2210", "Pune", "sales@apexindustrial.in"),
            ("Metro Components Ltd", "+91 22 2881 0400", "Mumbai", "supply@metrocomponents.com"),
            ("Pragati Tools & Metal", "+91 21 3567 8812", "Nashik", "orders@pragatitools.co.in"),
            ("Omkar Raw Materials", "+91 20 6711 2040", "Pimpri", "contact@omkarraw.com"),
            ("Precision Fasteners Corp", "+91 26 5233 4410", "Vadodara", "info@precisionfasteners.in")
        ])

        # 4. Storage
        db.executemany("""
            INSERT INTO storage(location, capacity, current_stock, dept_id)
            VALUES(?,?,?,?)
        """, [
            ("Warehouse Bay A - Metals", 2500, 1820, 5),
            ("Warehouse Bay B - Electrical & Parts", 1500, 940, 5),
            ("Chemical & Lubricants Store", 800, 310, 4),
            ("Raw Material Silo 1", 5000, 3200, 1)
        ])

        # 5. Raw Materials (Supplier -> Raw Material 1:N)
        db.executemany("""
            INSERT INTO raw_materials(material_name, unit, qty_in_stock, min_stock_level, unit_cost, supplier_id, storage_id)
            VALUES(?,?,?,?,?,?,?)
        """, [
            ("Steel Sheets (Cold Rolled)", "sheets", 340, 150, 840.0, 1, 1),
            ("Copper Wire Spools", "spools", 45, 80, 1250.0, 2, 2),
            ("Bearing 6204-2RS", "pieces", 62, 80, 185.0, 2, 2),
            ("Hydraulic Oil ISO 46", "litres", 35, 25, 320.0, 4, 3),
            ("Aluminum Alloy Ingots", "kg", 1200, 500, 210.0, 4, 1),
            ("High-Tensile M8 Bolts", "packs", 80, 100, 95.0, 5, 2),
            ("Silicon Gaskets", "pieces", 420, 200, 45.0, 3, 2)
        ])

        # 6. Products
        db.executemany("""
            INSERT INTO products(product_name, category, unit_price, stock_qty)
            VALUES(?,?,?,?)
        """, [
            ("Industrial Centrifugal Pump", "Fluid Systems", 18500.0, 28),
            ("High-Pressure Valve Assembly", "Valves & Actuators", 6400.0, 65),
            ("Heavy-Duty Electric Motor", "Drive Units", 24000.0, 14),
            ("CNC Modular Control Panel", "Automation", 42000.0, 8)
        ])

        # 7. Machines
        db.executemany("""
            INSERT INTO machines(machine_name, status, install_date, dept_id)
            VALUES(?,?,?,?)
        """, [
            ("CNC Lathe 01 - Okuma Genos", "Operational", "2021-03-15", 2),
            ("CNC Lathe 02 - Haas ST-20", "Under Maintenance", "2022-08-10", 2),
            ("500-Ton Hydraulic Press", "Operational", "2020-01-20", 1),
            ("Automated Conveyor Line B", "Operational", "2021-11-05", 1),
            ("Robotic Welding Cell R1", "Idle", "2023-05-18", 2)
        ])

        # 8. Production Orders
        db.executemany("""
            INSERT INTO production_orders(order_id, product_id, quantity, produced_qty, status, start_date, end_date, machine_id, supervisor_id)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, [
            (1001, 1, 50, 42, "In Progress", "2026-10-12", "2026-10-28", 3, 1),
            (1002, 2, 120, 120, "Completed", "2026-10-02", "2026-10-14", 1, 1),
            (1003, 3, 30, 8, "Delayed", "2026-10-15", "2026-11-05", 2, 1),
            (1004, 4, 20, 0, "Planned", "2026-10-26", "2026-11-12", 5, 1)
        ])

        # 9. Order Materials (Composite PK order_id, material_id)
        # Note: Triggers would run on INSERT, so we insert directly with initial quantities
        db.executemany("""
            INSERT INTO order_materials(order_id, material_id, qty_used)
            VALUES(?,?,?)
        """, [
            (1001, 1, 60),  # Steel Sheets
            (1001, 5, 150), # Aluminum
            (1001, 7, 50),  # Silicon Gaskets
            (1001, 6, 20),  # Bolts
            (1002, 1, 40),  # Steel Sheets
            (1002, 7, 120), # Silicon Gaskets
            (1002, 3, 30),  # Bearing 6204
            (1003, 2, 25),  # Copper Wire
            (1003, 3, 60),  # Bearing 6204
            (1003, 1, 30),  # Steel Sheets
            (1004, 2, 15),  # Copper Wire
            (1004, 6, 10)   # Bolts
        ])

        # 10. Order Assignments ("Works On" employee participation)
        db.executemany("""
            INSERT INTO order_assignments(order_id, emp_id, role_in_order, hours_logged)
            VALUES(?,?,?,?)
        """, [
            (1001, 7, "Assembly Lead", 38.5),
            (1001, 2, "Machining Support", 16.0),
            (1002, 2, "Primary CNC Operator", 44.0),
            (1002, 6, "Precision Machinist", 32.0),
            (1003, 7, "Assembly Tech", 12.0),
            (1003, 8, "Tooling Specialist", 8.5)
        ])

        # 11. Maintenance
        db.executemany("""
            INSERT INTO maintenance(machine_id, maint_date, description, cost, next_due_date, priority, status)
            VALUES(?,?,?,?,?,?,?)
        """, [
            (2, "2026-10-20", "Spindle vibration diagnosis and high-speed bearing replacement", 14500.0, "2026-11-20", "High", "In Progress"),
            (3, "2026-10-18", "Hydraulic fluid flush and high-pressure seal pack overhaul", 8200.0, "2026-11-15", "Medium", "Scheduled"),
            (4, "2026-10-10", "Optical sensor realignment and drive belt tensioning", 2400.0, "2027-01-10", "Low", "Resolved"),
            (1, "2026-09-28", "Quarterly dynamic axis calibration and coolant pump servicing", 5600.0, "2026-12-28", "Medium", "Resolved")
        ])

        # 12. Stock Audit initial entry
        db.execute("""
            INSERT INTO stock_audit(material_id, old_quantity, new_quantity, action_type, changed_at)
            VALUES(1, 400, 340, 'ORDER_ALLOCATION', '2026-10-12 10:30:00')
        """)

@app.route("/")
def index():
    init_db()
    with get_db() as db:
        stats = {
            "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "active_orders": db.execute("SELECT COUNT(*) FROM production_orders WHERE status IN ('In Progress', 'Planned')").fetchone()[0],
            "raw_materials": db.execute("SELECT COUNT(*) FROM raw_materials").fetchone()[0],
            "low_stock_alerts": db.execute("SELECT COUNT(*) FROM raw_materials WHERE qty_in_stock <= min_stock_level").fetchone()[0],
            "machines": db.execute("SELECT COUNT(*) FROM machines").fetchone()[0],
            "maintenance_active": db.execute("SELECT COUNT(*) FROM maintenance WHERE status != 'Resolved'").fetchone()[0],
            "employees": db.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active'").fetchone()[0],
            "storage_utilization": db.execute("SELECT ROUND(AVG((current_stock * 100.0) / capacity), 1) FROM storage").fetchone()[0] or 0
        }

        recent_orders = db.execute("""
            SELECT po.order_id, p.product_name, po.quantity, po.produced_qty, po.status,
                   po.start_date, po.end_date, e.emp_name AS supervisor, m.machine_name
            FROM production_orders po
            JOIN products p ON p.product_id = po.product_id
            JOIN employees e ON e.emp_id = po.supervisor_id
            LEFT JOIN machines m ON m.machine_id = po.machine_id
            ORDER BY po.order_id DESC LIMIT 6
        """).fetchall()

        low_stock = db.execute("""
            SELECT rm.material_id, rm.material_name, rm.qty_in_stock, rm.min_stock_level,
                   rm.unit, s.supplier_name
            FROM raw_materials rm
            JOIN suppliers s ON s.supplier_id = rm.supplier_id
            WHERE rm.qty_in_stock <= rm.min_stock_level
            ORDER BY rm.qty_in_stock ASC
        """).fetchall()

        storage_units = db.execute("""
            SELECT s.*, d.dept_name
            FROM storage s
            JOIN departments d ON d.dept_id = s.dept_id
            ORDER BY s.storage_id ASC
        """).fetchall()

        pending_maintenance = db.execute("""
            SELECT mt.*, m.machine_name
            FROM maintenance mt
            JOIN machines m ON m.machine_id = mt.machine_id
            WHERE mt.status != 'Resolved'
            ORDER BY mt.next_due_date ASC LIMIT 4
        """).fetchall()

    today = date.today().strftime("%A, %d %B %Y").replace(" 0", " ")
    return render_template(
        "index.html",
        stats=stats,
        recent_orders=recent_orders,
        low_stock=low_stock,
        storage_units=storage_units,
        pending_maintenance=pending_maintenance,
        today=today
    )

@app.route("/api/lookups")
def get_lookups():
    with get_db() as db:
        departments = [dict(r) for r in db.execute("SELECT dept_id AS id, dept_name AS name FROM departments ORDER BY dept_name").fetchall()]
        suppliers = [dict(r) for r in db.execute("SELECT supplier_id AS id, supplier_name AS name FROM suppliers ORDER BY supplier_name").fetchall()]
        products = [dict(r) for r in db.execute("SELECT product_id AS id, product_name AS name FROM products ORDER BY product_name").fetchall()]
        machines = [dict(r) for r in db.execute("SELECT machine_id AS id, machine_name AS name FROM machines ORDER BY machine_name").fetchall()]
        employees = [dict(r) for r in db.execute("SELECT emp_id AS id, emp_name AS name, role FROM employees ORDER BY emp_name").fetchall()]
        supervisors = [dict(r) for r in db.execute("SELECT emp_id AS id, emp_name AS name FROM employees WHERE role LIKE '%Supervisor%' OR role LIKE '%Lead%' OR supervisor_id IS NULL ORDER BY emp_name").fetchall()]
        if not supervisors:
            supervisors = employees
        storage = [dict(r) for r in db.execute("SELECT storage_id AS id, location AS name FROM storage ORDER BY location").fetchall()]
        raw_materials = [dict(r) for r in db.execute("SELECT material_id AS id, material_name AS name, unit, qty_in_stock FROM raw_materials ORDER BY material_name").fetchall()]
        orders = [dict(r) for r in db.execute("SELECT po.order_id AS id, ('Order #' || po.order_id || ' - ' || p.product_name) AS name FROM production_orders po JOIN products p ON p.product_id = po.product_id ORDER BY po.order_id DESC").fetchall()]

        return jsonify(
            departments=departments,
            suppliers=suppliers,
            products=products,
            machines=machines,
            employees=employees,
            supervisors=supervisors,
            storage=storage,
            raw_materials=raw_materials,
            orders=orders
        )

@app.route("/api/order_details/<int:order_id>")
def order_details(order_id):
    with get_db() as db:
        order = db.execute("""
            SELECT po.*, p.product_name, p.category, e.emp_name AS supervisor, m.machine_name
            FROM production_orders po
            JOIN products p ON p.product_id = po.product_id
            JOIN employees e ON e.emp_id = po.supervisor_id
            LEFT JOIN machines m ON m.machine_id = po.machine_id
            WHERE po.order_id = ?
        """, (order_id,)).fetchone()

        if not order:
            return jsonify(error="Order not found"), 404

        materials = db.execute("""
            SELECT om.order_id, om.material_id, om.qty_used, rm.material_name, rm.unit, rm.unit_cost,
                   ROUND(om.qty_used * rm.unit_cost, 2) AS total_cost
            FROM order_materials om
            JOIN raw_materials rm ON rm.material_id = om.material_id
            WHERE om.order_id = ?
            ORDER BY rm.material_name
        """, (order_id,)).fetchall()

        assignments = db.execute("""
            SELECT oa.order_id, oa.emp_id, oa.role_in_order, oa.hours_logged,
                   e.emp_name, e.role, d.dept_name
            FROM order_assignments oa
            JOIN employees e ON e.emp_id = oa.emp_id
            JOIN departments d ON d.dept_id = e.dept_id
            WHERE oa.order_id = ?
            ORDER BY oa.hours_logged DESC
        """, (order_id,)).fetchall()

        return jsonify(
            order=dict(order),
            materials=[dict(m) for m in materials],
            assignments=[dict(a) for a in assignments]
        )

@app.route("/api/<entity>", methods=["GET", "POST"])
def api_entity(entity):
    allowed = {
        "production_orders", "raw_materials", "products", "machines",
        "maintenance", "employees", "departments", "suppliers",
        "storage", "order_materials", "order_assignments", "stock_audit"
    }
    if entity not in allowed:
        return jsonify(error="Unknown entity requested"), 404

    with get_db() as db:
        if request.method == "GET":
            search = request.args.get("search", "").strip()[:100]
            term = f"%{search}%"

            if entity == "production_orders":
                rows = db.execute("""
                    SELECT po.order_id, p.product_name, po.quantity, po.produced_qty,
                           po.status, po.start_date, po.end_date,
                           e.emp_name AS supervisor, m.machine_name
                    FROM production_orders po
                    JOIN products p ON p.product_id = po.product_id
                    JOIN employees e ON e.emp_id = po.supervisor_id
                    LEFT JOIN machines m ON m.machine_id = po.machine_id
                    WHERE p.product_name LIKE ? OR po.status LIKE ? OR e.emp_name LIKE ? OR m.machine_name LIKE ? OR CAST(po.order_id AS TEXT) LIKE ?
                    ORDER BY po.order_id DESC
                """, (term, term, term, term, term)).fetchall()

            elif entity == "raw_materials":
                rows = db.execute("""
                    SELECT rm.material_id, rm.material_name, rm.unit, rm.qty_in_stock,
                           rm.min_stock_level, rm.unit_cost, s.supplier_name, st.location AS storage_location,
                           CASE WHEN rm.qty_in_stock <= rm.min_stock_level THEN 'Low Stock' ELSE 'Sufficient' END AS stock_status
                    FROM raw_materials rm
                    JOIN suppliers s ON s.supplier_id = rm.supplier_id
                    LEFT JOIN storage st ON st.storage_id = rm.storage_id
                    WHERE rm.material_name LIKE ? OR s.supplier_name LIKE ? OR rm.unit LIKE ? OR st.location LIKE ?
                    ORDER BY rm.material_id ASC
                """, (term, term, term, term)).fetchall()

            elif entity == "products":
                rows = db.execute("""
                    SELECT product_id, product_name, category, unit_price, stock_qty,
                           ROUND(unit_price * stock_qty, 2) AS inventory_value
                    FROM products
                    WHERE product_name LIKE ? OR category LIKE ?
                    ORDER BY product_id ASC
                """, (term, term)).fetchall()

            elif entity == "machines":
                rows = db.execute("""
                    SELECT m.machine_id, m.machine_name, m.status, m.install_date,
                           d.dept_name AS department
                    FROM machines m
                    JOIN departments d ON d.dept_id = m.dept_id
                    WHERE m.machine_name LIKE ? OR m.status LIKE ? OR d.dept_name LIKE ?
                    ORDER BY m.machine_id ASC
                """, (term, term, term)).fetchall()

            elif entity == "maintenance":
                rows = db.execute("""
                    SELECT mt.maint_id, m.machine_name, mt.maint_date, mt.description,
                           mt.cost, mt.next_due_date, mt.priority, mt.status
                    FROM maintenance mt
                    JOIN machines m ON m.machine_id = mt.machine_id
                    WHERE m.machine_name LIKE ? OR mt.description LIKE ? OR mt.status LIKE ? OR mt.priority LIKE ?
                    ORDER BY mt.maint_id DESC
                """, (term, term, term, term)).fetchall()

            elif entity == "employees":
                rows = db.execute("""
                    SELECT e.emp_id, e.emp_name, e.role, d.dept_name AS department,
                           e.salary, e.status, e.joined_on, sup.emp_name AS supervisor
                    FROM employees e
                    JOIN departments d ON d.dept_id = e.dept_id
                    LEFT JOIN employees sup ON sup.emp_id = e.supervisor_id
                    WHERE e.emp_name LIKE ? OR e.role LIKE ? OR d.dept_name LIKE ? OR e.status LIKE ?
                    ORDER BY e.emp_id ASC
                """, (term, term, term, term)).fetchall()

            elif entity == "departments":
                rows = db.execute("""
                    SELECT d.dept_id, d.dept_name, d.manager, d.phone, d.location, d.budget,
                           COUNT(e.emp_id) AS employee_count
                    FROM departments d
                    LEFT JOIN employees e ON e.dept_id = d.dept_id
                    WHERE d.dept_name LIKE ? OR d.manager LIKE ? OR d.location LIKE ?
                    GROUP BY d.dept_id
                    ORDER BY d.dept_id ASC
                """, (term, term, term)).fetchall()

            elif entity == "suppliers":
                rows = db.execute("""
                    SELECT s.supplier_id, s.supplier_name, s.contact_no, s.city, s.email,
                           COUNT(rm.material_id) AS materials_supplied
                    FROM suppliers s
                    LEFT JOIN raw_materials rm ON rm.supplier_id = s.supplier_id
                    WHERE s.supplier_name LIKE ? OR s.city LIKE ? OR s.email LIKE ? OR s.contact_no LIKE ?
                    GROUP BY s.supplier_id
                    ORDER BY s.supplier_id ASC
                """, (term, term, term, term)).fetchall()

            elif entity == "storage":
                rows = db.execute("""
                    SELECT s.storage_id, s.location, s.capacity, s.current_stock,
                           d.dept_name AS department,
                           ROUND((s.current_stock * 100.0) / s.capacity, 1) AS utilization_pct
                    FROM storage s
                    JOIN departments d ON d.dept_id = s.dept_id
                    WHERE s.location LIKE ? OR d.dept_name LIKE ?
                    ORDER BY s.storage_id ASC
                """, (term, term)).fetchall()

            elif entity == "order_materials":
                order_id_filter = request.args.get("order_id")
                if order_id_filter:
                    rows = db.execute("""
                        SELECT om.order_id, om.material_id, om.qty_used, rm.material_name, rm.unit
                        FROM order_materials om
                        JOIN raw_materials rm ON rm.material_id = om.material_id
                        WHERE om.order_id = ?
                        ORDER BY rm.material_name
                    """, (order_id_filter,)).fetchall()
                else:
                    rows = db.execute("""
                        SELECT om.order_id, p.product_name, rm.material_name, om.qty_used, rm.unit
                        FROM order_materials om
                        JOIN production_orders po ON po.order_id = om.order_id
                        JOIN products p ON p.product_id = po.product_id
                        JOIN raw_materials rm ON rm.material_id = om.material_id
                        WHERE rm.material_name LIKE ? OR p.product_name LIKE ? OR CAST(om.order_id AS TEXT) LIKE ?
                        ORDER BY om.order_id DESC
                    """, (term, term, term)).fetchall()

            elif entity == "order_assignments":
                rows = db.execute("""
                    SELECT oa.order_id, p.product_name, e.emp_name, oa.role_in_order, oa.hours_logged
                    FROM order_assignments oa
                    JOIN production_orders po ON po.order_id = oa.order_id
                    JOIN products p ON p.product_id = po.product_id
                    JOIN employees e ON e.emp_id = oa.emp_id
                    WHERE e.emp_name LIKE ? OR oa.role_in_order LIKE ? OR CAST(oa.order_id AS TEXT) LIKE ?
                    ORDER BY oa.order_id DESC
                """, (term, term, term)).fetchall()

            elif entity == "stock_audit":
                rows = db.execute("""
                    SELECT sa.id, rm.material_name, sa.old_quantity, sa.new_quantity,
                           sa.action_type, sa.changed_at
                    FROM stock_audit sa
                    JOIN raw_materials rm ON rm.material_id = sa.material_id
                    ORDER BY sa.id DESC LIMIT 50
                """).fetchall()
            else:
                rows = []

            return jsonify([dict(r) for r in rows])

        # POST (Add Record)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Request body must be a valid JSON object."), 400

        try:
            if entity == "production_orders":
                db.execute("""
                    INSERT INTO production_orders(product_id, quantity, produced_qty, status, start_date, end_date, machine_id, supervisor_id)
                    VALUES(?,?,?,?,?,?,?,?)
                """, (
                    int(data["product_id"]),
                    int(data["quantity"]),
                    int(data.get("produced_qty", 0)),
                    data.get("status", "Planned"),
                    data["start_date"],
                    data.get("end_date") or None,
                    int(data["machine_id"]) if data.get("machine_id") else None,
                    int(data["supervisor_id"])
                ))

            elif entity == "raw_materials":
                db.execute("""
                    INSERT INTO raw_materials(material_name, unit, qty_in_stock, min_stock_level, unit_cost, supplier_id, storage_id)
                    VALUES(?,?,?,?,?,?,?)
                """, (
                    data["material_name"],
                    data["unit"],
                    int(data["qty_in_stock"]),
                    int(data["min_stock_level"]),
                    float(data["unit_cost"]),
                    int(data["supplier_id"]),
                    int(data["storage_id"]) if data.get("storage_id") else None
                ))

            elif entity == "products":
                db.execute("""
                    INSERT INTO products(product_name, category, unit_price, stock_qty)
                    VALUES(?,?,?,?)
                """, (
                    data["product_name"],
                    data["category"],
                    float(data["unit_price"]),
                    int(data.get("stock_qty", 0))
                ))

            elif entity == "machines":
                db.execute("""
                    INSERT INTO machines(machine_name, status, install_date, dept_id)
                    VALUES(?,?,?,?)
                """, (
                    data["machine_name"],
                    data.get("status", "Operational"),
                    data["install_date"],
                    int(data["dept_id"])
                ))

            elif entity == "maintenance":
                db.execute("""
                    INSERT INTO maintenance(machine_id, maint_date, description, cost, next_due_date, priority, status)
                    VALUES(?,?,?,?,?,?,?)
                """, (
                    int(data["machine_id"]),
                    data["maint_date"],
                    data["description"],
                    float(data["cost"]),
                    data["next_due_date"],
                    data.get("priority", "Medium"),
                    data.get("status", "Scheduled")
                ))

            elif entity == "employees":
                db.execute("""
                    INSERT INTO employees(emp_name, role, dept_id, salary, status, supervisor_id, joined_on)
                    VALUES(?,?,?,?,?,?,?)
                """, (
                    data["emp_name"],
                    data["role"],
                    int(data["dept_id"]),
                    float(data["salary"]),
                    data.get("status", "Active"),
                    int(data["supervisor_id"]) if data.get("supervisor_id") else None,
                    data["joined_on"]
                ))

            elif entity == "departments":
                db.execute("""
                    INSERT INTO departments(dept_name, manager, phone, location, budget)
                    VALUES(?,?,?,?,?)
                """, (
                    data["dept_name"],
                    data["manager"],
                    data["phone"],
                    data["location"],
                    float(data["budget"])
                ))

            elif entity == "suppliers":
                db.execute("""
                    INSERT INTO suppliers(supplier_name, contact_no, city, email)
                    VALUES(?,?,?,?)
                """, (
                    data["supplier_name"],
                    data["contact_no"],
                    data["city"],
                    data["email"]
                ))

            elif entity == "storage":
                db.execute("""
                    INSERT INTO storage(location, capacity, current_stock, dept_id)
                    VALUES(?,?,?,?)
                """, (
                    data["location"],
                    int(data["capacity"]),
                    int(data.get("current_stock", 0)),
                    int(data["dept_id"])
                ))

            elif entity == "order_materials":
                db.execute("""
                    INSERT INTO order_materials(order_id, material_id, qty_used)
                    VALUES(?,?,?)
                    ON CONFLICT(order_id, material_id) DO UPDATE SET
                        qty_used = qty_used + excluded.qty_used
                """, (
                    int(data["order_id"]),
                    int(data["material_id"]),
                    int(data["qty_used"])
                ))

            elif entity == "order_assignments":
                db.execute("""
                    INSERT INTO order_assignments(order_id, emp_id, role_in_order, hours_logged)
                    VALUES(?,?,?,?)
                    ON CONFLICT(order_id, emp_id) DO UPDATE SET
                        hours_logged = hours_logged + excluded.hours_logged,
                        role_in_order = excluded.role_in_order
                """, (
                    int(data["order_id"]),
                    int(data["emp_id"]),
                    data.get("role_in_order", "Operator"),
                    float(data.get("hours_logged", 0))
                ))
            else:
                return jsonify(error="Adding records to this table is not supported."), 400

            db.commit()
            return jsonify(message="Record saved successfully to factory database."), 201
        except sqlite3.IntegrityError as ie:
            return jsonify(error=f"Integrity Error: {ie}"), 400
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify(error=f"Invalid field data: {exc}"), 400

@app.route("/api/<entity>/delete", methods=["POST"])
def delete_entity_record(entity):
    pk_map = {
        "production_orders": "order_id",
        "raw_materials": "material_id",
        "products": "product_id",
        "machines": "machine_id",
        "maintenance": "maint_id",
        "employees": "emp_id",
        "departments": "dept_id",
        "suppliers": "supplier_id",
        "storage": "storage_id"
    }

    data = request.get_json(silent=True) or {}
    with get_db() as db:
        try:
            if entity in pk_map:
                record_id = data.get("id")
                if not record_id:
                    return jsonify(error="Record ID is required for deletion."), 400
                col = pk_map[entity]
                db.execute(f"DELETE FROM {entity} WHERE {col} = ?", (record_id,))
            elif entity == "order_materials":
                order_id = data.get("order_id")
                material_id = data.get("material_id")
                if not order_id or not material_id:
                    return jsonify(error="order_id and material_id are required."), 400
                db.execute("DELETE FROM order_materials WHERE order_id = ? AND material_id = ?", (order_id, material_id))
            elif entity == "order_assignments":
                order_id = data.get("order_id")
                emp_id = data.get("emp_id")
                if not order_id or not emp_id:
                    return jsonify(error="order_id and emp_id are required."), 400
                db.execute("DELETE FROM order_assignments WHERE order_id = ? AND emp_id = ?", (order_id, emp_id))
            else:
                return jsonify(error="Delete not supported for this table."), 400

            db.commit()
            return jsonify(message="Record deleted successfully from database.")
        except sqlite3.IntegrityError as ie:
            return jsonify(error=f"Cannot delete record: foreign key constraint in use ({ie})"), 400
        except Exception as exc:
            return jsonify(error=str(exc)), 400

@app.route("/api/query-demo")
def query_demo():
    key = request.args.get("q", "raw_materials_all")
    if key not in QUERY_DEMOS:
        return jsonify(error="Unknown query example selected."), 400

    sql, label = QUERY_DEMOS[key]
    with get_db() as db:
        if key == "update_with_trigger":
            db.execute(sql)
            db.commit()
            rows = db.execute("""
                SELECT rm.material_id, rm.material_name, rm.qty_in_stock, rm.unit
                FROM raw_materials rm
                WHERE rm.material_name = 'Steel Sheets (Cold Rolled)';
            """).fetchall()
            note = "Executed safely. Added 20 sheets to Steel Sheets. The 'raw_material_stock_audit' trigger wrote to 'stock_audit'."
        elif key == "delete_maintenance_preview":
            rows = db.execute("""
                SELECT maint_id, machine_id, maint_date, description, status
                FROM maintenance WHERE status = 'Resolved';
            """).fetchall()
            note = "Preview only. The DELETE statement was not executed to preserve demo data."
        else:
            rows = db.execute(sql).fetchall()
            note = "Executed live on factory database."

    return jsonify(
        label=label,
        sql=sql.strip(),
        rows=[dict(r) for r in rows],
        row_count=len(rows),
        note=note
    )

@app.route("/api/reset-db", methods=["POST"])
def reset_db_endpoint():
    try:
        init_db(force_reset=True)
        return jsonify(message="Factory database successfully reseeded to clean default state.")
    except Exception as exc:
        return jsonify(error=str(exc)), 500

@app.route("/api/db_tables")
def get_db_tables():
    with get_db() as db:
        tables = db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        result = []
        for t in tables:
            t_name = t["name"]
            count = db.execute(f"SELECT COUNT(*) FROM {t_name}").fetchone()[0]
            columns = db.execute(f"PRAGMA table_info({t_name})").fetchall()
            fks = db.execute(f"PRAGMA foreign_key_list({t_name})").fetchall()
            result.append({
                "name": t_name,
                "count": count,
                "sql": t["sql"],
                "columns": [dict(c) for c in columns],
                "foreign_keys": [dict(f) for f in fks]
            })
        return jsonify(result)

@app.route("/api/db_table/<table_name>")
def get_db_table_data(table_name):
    allowed_tables = {
        "departments", "employees", "suppliers", "storage",
        "raw_materials", "products", "machines", "production_orders",
        "order_materials", "order_assignments", "maintenance", "stock_audit"
    }
    if table_name not in allowed_tables:
        return jsonify(error="Table not found"), 404
    with get_db() as db:
        rows = db.execute(f"SELECT * FROM {table_name}").fetchall()
        columns = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        return jsonify(
            name=table_name,
            count=len(rows),
            columns=[dict(c) for c in columns],
            rows=[dict(r) for r in rows]
        )

@app.route("/api/custom_sql", methods=["POST"])
def run_custom_sql():
    data = request.get_json(silent=True) or {}
    query = (data.get("sql") or "").strip()
    if not query:
        return jsonify(error="Query is empty"), 400
    cleaned = query.rstrip(";").strip()
    first_word = cleaned.split()[0].upper() if cleaned.split() else ""
    if first_word not in ("SELECT", "PRAGMA", "EXPLAIN"):
        return jsonify(error="Only read-only queries (SELECT, PRAGMA) are allowed in the database watcher."), 400
    with get_db() as db:
        try:
            rows = db.execute(cleaned).fetchall()
            return jsonify(
                query=cleaned,
                count=len(rows),
                rows=[dict(r) for r in rows]
            )
        except Exception as exc:
            return jsonify(error=str(exc)), 400

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
