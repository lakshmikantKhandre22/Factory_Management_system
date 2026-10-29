-- ====================================================================
-- FORGEWORKS FACTORY MANAGEMENT SYSTEM — SQL QUERY REFERENCE
-- Matches Updated ER Diagram with 1:N & N:M Cardinalities, Composite PKs & Triggers
-- ====================================================================

-- 1. All Raw Materials with Supplier Details (1:N Join)
SELECT rm.material_id, rm.material_name, rm.unit, rm.qty_in_stock, 
       rm.min_stock_level, rm.unit_cost, s.supplier_name
FROM raw_materials rm
JOIN suppliers s ON s.supplier_id = rm.supplier_id
ORDER BY rm.material_name;

-- 2. Reorder Alerts (WHERE filter on Business Rule: stock <= min_stock_level)
SELECT rm.material_id, rm.material_name, rm.qty_in_stock, rm.min_stock_level,
       rm.unit, (rm.min_stock_level - rm.qty_in_stock) AS shortage_qty,
       s.supplier_name, s.contact_no
FROM raw_materials rm
JOIN suppliers s ON s.supplier_id = rm.supplier_id
WHERE rm.qty_in_stock <= rm.min_stock_level
ORDER BY shortage_qty DESC;

-- 3. Supplier-Raw Material 1:N Cardinality & Aggregation
SELECT s.supplier_id, s.supplier_name, s.city, s.contact_no, s.email,
       COUNT(rm.material_id) AS total_materials_supplied,
       COALESCE(GROUP_CONCAT(rm.material_name, ', '), 'None') AS supplied_materials
FROM suppliers s
LEFT JOIN raw_materials rm ON rm.supplier_id = s.supplier_id
GROUP BY s.supplier_id
ORDER BY total_materials_supplied DESC;

-- 4. Production Orders with Product, Machine & Supervisor (Multi-table JOIN)
SELECT po.order_id, p.product_name, p.category, po.quantity AS target_qty,
       po.produced_qty, po.status, po.start_date, po.end_date,
       e.emp_name AS supervisor, m.machine_name
FROM production_orders po
JOIN products p ON p.product_id = po.product_id
JOIN employees e ON e.emp_id = po.supervisor_id
LEFT JOIN machines m ON m.machine_id = po.machine_id
ORDER BY po.order_id DESC;

-- 5. Bill of Materials (BOM) with Composite PK (order_id, material_id)
SELECT om.order_id, p.product_name, po.status AS order_status,
       rm.material_name, om.qty_used, rm.unit,
       ROUND(om.qty_used * rm.unit_cost, 2) AS material_cost
FROM order_materials om
JOIN production_orders po ON po.order_id = om.order_id
JOIN products p ON p.product_id = po.product_id
JOIN raw_materials rm ON rm.material_id = om.material_id
ORDER BY om.order_id ASC, material_cost DESC;

-- 6. Employee Participation Tracking ("Works On" N:M Relationship)
SELECT oa.order_id, p.product_name, e.emp_name, e.role,
       d.dept_name, oa.role_in_order, oa.hours_logged
FROM order_assignments oa
JOIN production_orders po ON po.order_id = oa.order_id
JOIN products p ON p.product_id = po.product_id
JOIN employees e ON e.emp_id = oa.emp_id
JOIN departments d ON d.dept_id = e.dept_id
ORDER BY oa.order_id ASC, oa.hours_logged DESC;

-- 7. Storage Warehouses Capacity & Utilization Percentage
SELECT s.storage_id, s.location, d.dept_name AS managing_dept,
       s.capacity, s.current_stock,
       ROUND((s.current_stock * 100.0) / s.capacity, 1) AS utilization_pct,
       (s.capacity - s.current_stock) AS available_capacity
FROM storage s
JOIN departments d ON d.dept_id = s.dept_id
ORDER BY utilization_pct DESC;

-- 8. Machine Fleet Maintenance Costs (1:N Machine-Maintenance)
SELECT m.machine_id, m.machine_name, m.status, d.dept_name,
       COUNT(mt.maint_id) AS maintenance_count,
       COALESCE(SUM(mt.cost), 0) AS total_spent,
       MAX(mt.next_due_date) AS upcoming_due_date
FROM machines m
JOIN departments d ON d.dept_id = m.dept_id
LEFT JOIN maintenance mt ON mt.machine_id = m.machine_id
GROUP BY m.machine_id
ORDER BY total_spent DESC;

-- 9. Upcoming Maintenance Deadlines (Pending Service)
SELECT mt.maint_id, m.machine_name, mt.description, mt.priority,
       mt.status, mt.cost, mt.next_due_date
FROM maintenance mt
JOIN machines m ON m.machine_id = mt.machine_id
WHERE mt.status != 'Resolved'
ORDER BY mt.next_due_date ASC;

-- 10. Department Budget vs Annual Payroll
SELECT d.dept_id, d.dept_name, d.location, d.budget,
       COUNT(e.emp_id) AS total_employees,
       COALESCE(SUM(e.salary), 0) AS monthly_payroll,
       ROUND((COALESCE(SUM(e.salary), 0) * 12 * 100.0) / d.budget, 1) AS annual_payroll_pct_of_budget
FROM departments d
LEFT JOIN employees e ON e.dept_id = d.dept_id
GROUP BY d.dept_id
ORDER BY d.budget DESC;

-- 11. Finished Products Inventory Valuation (Calculated Column)
SELECT product_id, product_name, category, unit_price, stock_qty,
       ROUND(unit_price * stock_qty, 2) AS total_inventory_value
FROM products
ORDER BY total_inventory_value DESC;

-- 12. Above-Average Cost Materials (Subquery + AVG)
SELECT material_id, material_name, unit, unit_cost, qty_in_stock
FROM raw_materials
WHERE unit_cost > (SELECT AVG(unit_cost) FROM raw_materials)
ORDER BY unit_cost DESC;

-- 13. Category Aggregates (GROUP BY + Aggregations)
SELECT category, COUNT(*) AS product_count,
       SUM(stock_qty) AS total_units_in_stock,
       ROUND(AVG(unit_price), 2) AS avg_unit_price
FROM products
GROUP BY category
ORDER BY total_units_in_stock DESC;

-- 14. Departments Housing Multiple Machines (HAVING Clause)
SELECT d.dept_name, d.location, COUNT(m.machine_id) AS machine_count
FROM departments d
JOIN machines m ON m.dept_id = d.dept_id
GROUP BY d.dept_id
HAVING COUNT(m.machine_id) >= 1
ORDER BY machine_count DESC;

-- 15. Safe UPDATE (Fires raw_material_stock_audit trigger)
UPDATE raw_materials
SET qty_in_stock = qty_in_stock + 20
WHERE material_name = 'Steel Sheets (Cold Rolled)';

-- 16. Audit Log Records (Trigger Verification)
SELECT sa.id, rm.material_name, sa.old_quantity, sa.new_quantity,
       sa.action_type, sa.changed_at
FROM stock_audit sa
JOIN raw_materials rm ON rm.material_id = sa.material_id
ORDER BY sa.id DESC;

-- 17. Safe DELETE Preview (Maintenance Resolved records preview)
DELETE FROM maintenance WHERE status = 'Resolved';
