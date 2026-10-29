// FORGEWORKS FACTORY MANAGEMENT SYSTEM - ADVANCED CONTROLLER
let currentPage = "overview";
let cachedLookups = null;
let searchTimer = null;
let currentWatcherTable = "raw_materials";
let cachedDbTables = [];

const pageMetadata = {
  overview: { title: "Factory Overview & Real-time Operations", crumb: "OVERVIEW" },
  production_orders: { title: "Production Orders & Routing", crumb: "PRODUCTION ORDERS" },
  order_materials: { title: "Order Materials (Bill of Materials BOM)", crumb: "ORDER MATERIALS" },
  order_assignments: { title: "Worker Order Assignments (Works On)", crumb: "ORDER ASSIGNMENTS" },
  products: { title: "Finished Goods & Product Catalog", crumb: "PRODUCTS" },
  raw_materials: { title: "Raw Materials & Stock Levels", crumb: "RAW MATERIALS" },
  storage: { title: "Storage Warehouses & Silo Capacities", crumb: "STORAGE" },
  machines: { title: "Machine Fleet & Operational Status", crumb: "MACHINES" },
  maintenance: { title: "Equipment Maintenance & Service Logs", crumb: "MAINTENANCE" },
  employees: { title: "Workforce Directory & Roles", crumb: "EMPLOYEES" },
  departments: { title: "Factory Departments & Budgets", crumb: "DEPARTMENTS" },
  suppliers: { title: "Industrial Suppliers & Vendor Network", crumb: "SUPPLIERS" },
  db_watcher: { title: "Live Database Watcher & Table Explorer", crumb: "WATCH DATABASE" },
  er_diagram: { title: "Updated Relational Schema Architecture", crumb: "ER DIAGRAM" },
  sql_lab: { title: "DBMS SQL Query Laboratory", crumb: "SQL QUERY LAB" },
  stock_audit: { title: "Stock Audit Trail (Trigger Log)", crumb: "STOCK AUDIT" }
};

const entityConfigs = {
  production_orders: {
    title: "Production Orders",
    desc: "Batches scheduled and running across plant machinery with assigned supervisors.",
    cols: ["order_id", "product_name", "quantity", "produced_qty", "status", "start_date", "end_date", "supervisor", "machine_name"],
    fields: [
      { name: "product_id", label: "Product", type: "lookup", lookup: "products", required: true },
      { name: "quantity", label: "Target Batch Quantity", type: "number", min: 1, required: true },
      { name: "produced_qty", label: "Already Produced Quantity", type: "number", min: 0, default: 0 },
      { name: "status", label: "Order Status", type: "select", options: ["Planned", "In Progress", "Completed", "Delayed"], required: true },
      { name: "start_date", label: "Scheduled Start Date", type: "date", required: true },
      { name: "end_date", label: "Target End Date", type: "date" },
      { name: "supervisor_id", label: "Supervisor", type: "lookup", lookup: "supervisors", required: true },
      { name: "machine_id", label: "Assigned Machine", type: "lookup", lookup: "machines" }
    ]
  },
  order_materials: {
    title: "Order Materials (Bill of Materials BOM)",
    desc: "Materials consumed by each batch order (Composite PK: order_id, material_id).",
    cols: ["order_id", "product_name", "material_name", "qty_used", "unit"],
    fields: [
      { name: "order_id", label: "Production Order", type: "lookup", lookup: "orders", required: true },
      { name: "material_id", label: "Raw Material", type: "lookup", lookup: "raw_materials", required: true },
      { name: "qty_used", label: "Quantity Used", type: "number", min: 1, required: true }
    ]
  },
  order_assignments: {
    title: "Worker Order Assignments (Works On)",
    desc: "Employee participation across active and scheduled production orders (N:M).",
    cols: ["order_id", "product_name", "emp_name", "role_in_order", "hours_logged"],
    fields: [
      { name: "order_id", label: "Production Order", type: "lookup", lookup: "orders", required: true },
      { name: "emp_id", label: "Employee / Worker", type: "lookup", lookup: "employees", required: true },
      { name: "role_in_order", label: "Role in this Order (e.g. Lead, Operator, Quality)", type: "text", required: true },
      { name: "hours_logged", label: "Hours Logged", type: "number", step: "0.5", min: 0, default: 0, required: true }
    ]
  },
  products: {
    title: "Finished Products Catalog",
    desc: "Manufactured assemblies and catalog products with unit prices and stock levels.",
    cols: ["product_id", "product_name", "category", "unit_price", "stock_qty", "inventory_value"],
    fields: [
      { name: "product_name", label: "Product Name", type: "text", required: true },
      { name: "category", label: "Category", type: "text", required: true },
      { name: "unit_price", label: "Unit Price (₹)", type: "number", step: "0.01", min: 0, required: true },
      { name: "stock_qty", label: "Current Finished Stock", type: "number", min: 0, default: 0 }
    ]
  },
  raw_materials: {
    title: "Raw Materials Inventory",
    desc: "Raw stock items with supplier assignments (1:N), reorder levels, and storage locations.",
    cols: ["material_id", "material_name", "unit", "qty_in_stock", "min_stock_level", "unit_cost", "supplier_name", "storage_location", "stock_status"],
    fields: [
      { name: "material_name", label: "Raw Material Name", type: "text", required: true },
      { name: "unit", label: "Measurement Unit (e.g. kg, sheets, litres)", type: "text", required: true },
      { name: "qty_in_stock", label: "Quantity In Stock", type: "number", min: 0, required: true },
      { name: "min_stock_level", label: "Minimum Reorder Level", type: "number", min: 0, required: true },
      { name: "unit_cost", label: "Unit Cost (₹)", type: "number", step: "0.01", min: 0, required: true },
      { name: "supplier_id", label: "Supplier (1:N)", type: "lookup", lookup: "suppliers", required: true },
      { name: "storage_id", label: "Storage Bay Location", type: "lookup", lookup: "storage" }
    ]
  },
  storage: {
    title: "Storage Bays & Warehouses",
    desc: "Tracking warehouse locations, capacities, and departments managing them.",
    cols: ["storage_id", "location", "capacity", "current_stock", "department", "utilization_pct"],
    fields: [
      { name: "location", label: "Storage Bay / Silo Name", type: "text", required: true },
      { name: "capacity", label: "Maximum Capacity (Units)", type: "number", min: 1, required: true },
      { name: "current_stock", label: "Initial Current Stock", type: "number", min: 0, default: 0 },
      { name: "dept_id", label: "Managing Department", type: "lookup", lookup: "departments", required: true }
    ]
  },
  machines: {
    title: "Machine Fleet",
    desc: "Industrial machinery, production status, and department ownership.",
    cols: ["machine_id", "machine_name", "status", "install_date", "department"],
    fields: [
      { name: "machine_name", label: "Machine Make & Model", type: "text", required: true },
      { name: "status", label: "Operating Status", type: "select", options: ["Operational", "Under Maintenance", "Idle", "Offline"], required: true },
      { name: "install_date", label: "Installation Date", type: "date", required: true },
      { name: "dept_id", label: "Department", type: "lookup", lookup: "departments", required: true }
    ]
  },
  maintenance: {
    title: "Maintenance Logs",
    desc: "Machine service history, breakdown fixes, overhaul costs, and next scheduled dates.",
    cols: ["maint_id", "machine_name", "maint_date", "description", "cost", "next_due_date", "priority", "status"],
    fields: [
      { name: "machine_id", label: "Serviced Machine", type: "lookup", lookup: "machines", required: true },
      { name: "maint_date", label: "Service / Breakdown Date", type: "date", required: true },
      { name: "description", label: "Work Carried Out / Issue", type: "text", required: true },
      { name: "cost", label: "Service Cost (₹)", type: "number", step: "0.01", min: 0, required: true },
      { name: "next_due_date", label: "Next Scheduled Due Date", type: "date", required: true },
      { name: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High"], required: true },
      { name: "status", label: "Status", type: "select", options: ["Scheduled", "In Progress", "Resolved"], required: true }
    ]
  },
  employees: {
    title: "Personnel Directory",
    desc: "Factory workforce, operational roles, salaries, and supervisor hierarchy.",
    cols: ["emp_id", "emp_name", "role", "department", "salary", "supervisor", "status", "joined_on"],
    fields: [
      { name: "emp_name", label: "Employee Full Name", type: "text", required: true },
      { name: "role", label: "Job Title / Role", type: "text", required: true },
      { name: "dept_id", label: "Department", type: "lookup", lookup: "departments", required: true },
      { name: "salary", label: "Monthly Salary (₹)", type: "number", min: 0, required: true },
      { name: "status", label: "Employment Status", type: "select", options: ["Active", "On Leave", "Inactive"], required: true },
      { name: "supervisor_id", label: "Supervisor (Self-referencing)", type: "lookup", lookup: "supervisors" },
      { name: "joined_on", label: "Date Joined", type: "date", required: true }
    ]
  },
  departments: {
    title: "Factory Departments",
    desc: "Plant divisions, managers, contact numbers, and operational budgets.",
    cols: ["dept_id", "dept_name", "manager", "phone", "location", "budget", "employee_count"],
    fields: [
      { name: "dept_name", label: "Department Name", type: "text", required: true },
      { name: "manager", label: "Department Head / Manager", type: "text", required: true },
      { name: "phone", label: "Direct Phone Extension", type: "text", required: true },
      { name: "location", label: "Plant Location / Floor", type: "text", required: true },
      { name: "budget", label: "Allocated Annual Budget (₹)", type: "number", min: 0, required: true }
    ]
  },
  suppliers: {
    title: "Suppliers Network",
    desc: "Industrial vendors supplying raw materials with 1:N cardinality.",
    cols: ["supplier_id", "supplier_name", "contact_no", "city", "email", "materials_supplied"],
    fields: [
      { name: "supplier_name", label: "Supplier Company Name", type: "text", required: true },
      { name: "contact_no", label: "Contact Number", type: "text", required: true },
      { name: "city", label: "City", type: "text", required: true },
      { name: "email", label: "Business Email", type: "email", required: true }
    ]
  },
  stock_audit: {
    title: "Stock Audit Trail (Trigger Log)",
    desc: "Immutable change history recorded automatically by SQLite trigger 'raw_material_stock_audit'.",
    cols: ["id", "material_name", "old_quantity", "new_quantity", "action_type", "changed_at"],
    fields: []
  }
};

// INITIALIZATION
document.addEventListener("DOMContentLoaded", () => {
  // Navigation button listeners
  document.querySelectorAll(".nav").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetPage = btn.getAttribute("data-page");
      showPage(targetPage);
    });
  });

  // Table search input debounce
  const searchInput = document.getElementById("entity-search");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(loadEntityTable, 250);
    });
  }

  // Database reset button
  const resetBtn = document.getElementById("btn-reset-db");
  if (resetBtn) {
    resetBtn.addEventListener("click", async () => {
      if (confirm("Reset factory database to clean default state with all ER diagram demo data?")) {
        try {
          const res = await fetch("/api/reset-db", { method: "POST" });
          const json = await res.json();
          alert(json.message || "Database successfully reseeded.");
          window.location.reload();
        } catch (e) {
          alert("Error resetting database: " + e.message);
        }
      }
    });
  }

  // Custom SQL enter key
  const customSqlInput = document.getElementById("custom-sql-input");
  if (customSqlInput) {
    customSqlInput.addEventListener("keydown", e => {
      if (e.key === "Enter") executeCustomSql();
    });
  }

  // Initial runs
  runSelectedQuickQuery();
  runFullQueryLab();
});

// PAGE SWITCHING
function showPage(page) {
  currentPage = page;

  // Update nav active states
  document.querySelectorAll(".nav").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-page") === page);
  });

  // Update header text
  const meta = pageMetadata[page] || { title: page, crumb: page.toUpperCase() };
  document.getElementById("page-title").textContent = meta.title;
  document.getElementById("crumb").textContent = meta.crumb;

  // Toggle pages
  const isOverview = page === "overview";
  const isErDiagram = page === "er_diagram";
  const isSqlLab = page === "sql_lab";
  const isDbWatcher = page === "db_watcher";
  const isDataPage = !isOverview && !isErDiagram && !isSqlLab && !isDbWatcher;

  document.getElementById("overview-page").classList.toggle("active", isOverview);
  document.getElementById("er-diagram-page").classList.toggle("active", isErDiagram);
  document.getElementById("sql-lab-page").classList.toggle("active", isSqlLab);
  document.getElementById("db-watcher-page").classList.toggle("active", isDbWatcher);
  document.getElementById("data-page").classList.toggle("active", isDataPage);

  if (isDataPage) {
    const searchInput = document.getElementById("entity-search");
    if (searchInput) searchInput.value = "";
    loadEntityTable();
  } else if (isSqlLab) {
    runFullQueryLab();
  } else if (isDbWatcher) {
    loadDbWatcher();
  }
}

// FETCH LOOKUPS CACHE
async function getLookups() {
  if (!cachedLookups) {
    const res = await fetch("/api/lookups");
    cachedLookups = await res.json();
  }
  return cachedLookups;
}

// ==========================================================================
// LIVE DATABASE WATCHER
// ==========================================================================
async function loadDbWatcher() {
  const pillsContainer = document.getElementById("db-tables-pills");
  pillsContainer.innerHTML = '<div class="table-loader">Fetching database tables…</div>';

  try {
    const res = await fetch("/api/db_tables");
    cachedDbTables = await res.json();

    if (!cachedDbTables.length) {
      pillsContainer.innerHTML = '<p class="empty-state">No tables found in database.</p>';
      return;
    }

    let pillsHtml = '';
    cachedDbTables.forEach(t => {
      const activeClass = (t.name === currentWatcherTable) ? ' active' : '';
      pillsHtml += `<button class="db-table-pill${activeClass}" onclick="selectWatcherTable('${t.name}')">
        <span>${t.name}</span>
        <span class="count">${t.count}</span>
      </button>`;
    });
    pillsContainer.innerHTML = pillsHtml;

    // Load active table
    selectWatcherTable(currentWatcherTable || cachedDbTables[0].name);
  } catch (err) {
    pillsContainer.innerHTML = `<p style="color: #fb7185;">Error loading tables: ${err.message}</p>`;
  }
}

function selectWatcherTable(tableName) {
  currentWatcherTable = tableName;
  document.querySelectorAll(".db-table-pill").forEach(p => {
    p.classList.toggle("active", p.textContent.includes(tableName));
  });

  loadDbTableData(tableName);
}

async function loadDbTableData(tableName) {
  const title = document.getElementById("watcher-table-title");
  const meta = document.getElementById("watcher-table-meta");
  const ddlBlock = document.getElementById("watcher-table-ddl");
  const dataContainer = document.getElementById("watcher-table-data");

  title.textContent = `Table: ${tableName}`;
  dataContainer.innerHTML = '<div class="table-loader">Loading live records…</div>';

  const tableMeta = cachedDbTables.find(t => t.name === tableName);
  if (tableMeta && tableMeta.sql) {
    ddlBlock.textContent = tableMeta.sql;
  }

  try {
    const res = await fetch(`/api/db_table/${tableName}`);
    const data = await res.json();

    meta.textContent = `${data.count} live rows stored in SQLite · ${data.columns.length} columns`;

    if (!data.rows || !data.rows.length) {
      dataContainer.innerHTML = '<p class="empty-state" style="padding: 24px; text-align: center;">No records in this table yet.</p>';
      return;
    }

    const cols = data.columns.map(c => c.name);
    let html = '<table><thead><tr>';
    cols.forEach(col => {
      const isPk = data.columns.find(c => c.name === col && c.pk);
      html += `<th>${isPk ? '🔑 ' : ''}${esc(col.toUpperCase())}</th>`;
    });
    html += '<th>ACTIONS</th>';
    html += '</tr></thead><tbody>';

    data.rows.forEach(row => {
      html += '<tr>';
      cols.forEach(col => {
        let val = row[col];
        if (val === null || val === undefined) val = '—';
        html += `<td>${esc(val)}</td>`;
      });
      // Delete button
      const idVal = row[cols[0]];
      html += `<td><button class="delete-row-btn" onclick="deleteFromWatcher('${tableName}', '${esc(idVal)}')">✕ Delete</button></td>`;
      html += '</tr>';
    });
    html += '</tbody></table>';
    dataContainer.innerHTML = html;
  } catch (err) {
    dataContainer.innerHTML = `<p style="color: #fb7185; padding: 20px;">Error: ${err.message}</p>`;
  }
}

function toggleWatcherSchema() {
  const block = document.getElementById("watcher-schema-block");
  const btn = document.getElementById("watcher-toggle-schema-btn");
  if (block.style.display === "none") {
    block.style.display = "block";
    btn.textContent = "Hide DDL / Schema";
  } else {
    block.style.display = "none";
    btn.textContent = "Toggle DDL / Schema";
  }
}

function setCustomSql(query) {
  document.getElementById("custom-sql-input").value = query;
  executeCustomSql();
}

async function executeCustomSql() {
  const query = document.getElementById("custom-sql-input").value;
  const feedback = document.getElementById("custom-sql-feedback");
  const resultsContainer = document.getElementById("custom-sql-results");

  feedback.textContent = "Executing query…";
  feedback.style.color = "var(--accent-cyan)";
  resultsContainer.innerHTML = "";

  try {
    const res = await fetch("/api/custom_sql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql: query })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Query failed");

    feedback.textContent = `✓ Returned ${data.count} rows from database.`;
    feedback.style.color = "var(--accent-emerald)";
    renderResultsTable(resultsContainer, data.rows);
  } catch (e) {
    feedback.textContent = "⚠ " + e.message;
    feedback.style.color = "var(--accent-rose)";
  }
}

async function deleteFromWatcher(tableName, recordId) {
  if (!confirm(`Delete record #${recordId} from table '${tableName}' in database?`)) return;
  try {
    const res = await fetch(`/api/${tableName}/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: recordId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not delete record.");
    alert(data.message);
    loadDbWatcher();
  } catch (err) {
    alert("Error: " + err.message);
  }
}

// ==========================================================================
// ENTITY TABLE LOADER
// ==========================================================================
async function loadEntityTable() {
  const cfg = entityConfigs[currentPage];
  if (!cfg) return;

  document.getElementById("table-heading").textContent = cfg.title;
  document.getElementById("table-description").textContent = cfg.desc;

  const container = document.getElementById("entity-table-container");
  container.innerHTML = '<div class="table-loader">Fetching live records…</div>';

  const search = document.getElementById("entity-search").value || "";
  try {
    const res = await fetch(`/api/${currentPage}?search=${encodeURIComponent(search)}`);
    const rows = await res.json();

    if (!rows.length) {
      container.innerHTML = '<p class="empty-state" style="padding: 24px; text-align: center;">No matching records found.</p>';
      return;
    }

    const cols = cfg.cols;
    let html = '<table><thead><tr>';
    cols.forEach(col => {
      html += `<th>${esc(col.replace(/_/g, " ").toUpperCase())}</th>`;
    });
    html += '<th>ACTIONS</th>';
    html += '</tr></thead><tbody>';

    rows.forEach(row => {
      html += '<tr>';
      cols.forEach(col => {
        let val = row[col];
        if (val === null || val === undefined) {
          val = '—';
        }

        if (col === "status" || col === "stock_status") {
          const statusClass = String(val).toLowerCase().replace(/\s+/g, "-");
          html += `<td><span class="status-pill status-${statusClass}">${esc(val)}</span></td>`;
        } else if (col === "utilization_pct") {
          html += `<td><b>${val}%</b></td>`;
        } else if (col === "unit_price" || col === "unit_cost" || col === "salary" || col === "budget" || col === "cost" || col === "inventory_value") {
          html += `<td>₹${Number(val).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}</td>`;
        } else if (col === "order_id" || col === "material_id" || col === "product_id" || col === "machine_id" || col === "emp_id" || col === "storage_id" || col === "supplier_id") {
          html += `<td><b>#${esc(val)}</b></td>`;
        } else {
          html += `<td>${esc(val)}</td>`;
        }
      });

      html += '<td>';
      if (currentPage === "production_orders") {
        html += `<button class="mini-btn" onclick="openOrderModal(${row.order_id})" style="margin-right: 6px;">View BOM</button>`;
      }
      const primaryKeyCol = cols[0];
      const pkVal = row[primaryKeyCol];
      if (primaryKeyCol && pkVal !== undefined && currentPage !== "stock_audit") {
        html += `<button class="delete-row-btn" onclick="deleteEntityRecord('${currentPage}', '${esc(pkVal)}')">✕</button>`;
      }
      html += '</td>';
      html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<p class="empty-state" style="color: #fb7185; padding: 20px;">Failed to load data: ${err.message}</p>`;
  }
}

async function deleteEntityRecord(entity, id) {
  if (!confirm(`Delete record #${id} from ${entity} in database?`)) return;
  try {
    const res = await fetch(`/api/${entity}/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not delete record.");
    alert(data.message);
    loadEntityTable();
  } catch (err) {
    alert("Error: " + err.message);
  }
}

// QUICK QUERY RUNNER (OVERVIEW)
async function runSelectedQuickQuery() {
  const select = document.getElementById("quick-query-select");
  if (!select) return;
  const key = select.value;
  const btn = document.getElementById("btn-quick-run");
  if (btn) btn.disabled = true;

  try {
    const res = await fetch(`/api/query-demo?q=${encodeURIComponent(key)}`);
    const data = await res.json();
    document.getElementById("quick-sql-code").textContent = data.sql;
    renderResultsTable(document.getElementById("quick-query-results"), data.rows);
  } catch (e) {
    document.getElementById("quick-sql-code").textContent = "-- Error: " + e.message;
  } finally {
    if (btn) btn.disabled = false;
  }
}

// FULL QUERY LAB RUNNER
async function runFullQueryLab() {
  const select = document.getElementById("full-query-select");
  if (!select) return;
  const key = select.value;
  const btn = document.getElementById("btn-full-run");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Running…";
  }

  try {
    const res = await fetch(`/api/query-demo?q=${encodeURIComponent(key)}`);
    const data = await res.json();
    document.getElementById("full-query-label").textContent = data.label;
    document.getElementById("full-query-count").textContent = `${data.row_count} rows`;
    document.getElementById("full-sql-code").textContent = data.sql;
    document.getElementById("full-query-note").textContent = data.note ? "✓ " + data.note : "";
    renderResultsTable(document.getElementById("full-query-results"), data.rows);
  } catch (e) {
    document.getElementById("full-query-note").textContent = "⚠ " + e.message;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Execute Query ⚡";
    }
  }
}

async function copyFullQuerySql() {
  const code = document.getElementById("full-sql-code").textContent;
  const btn = document.getElementById("btn-copy-sql");
  try {
    await navigator.clipboard.writeText(code);
    btn.textContent = "Copied ✓";
    setTimeout(() => { btn.textContent = "Copy SQL"; }, 2000);
  } catch (err) {
    alert("Could not access clipboard.");
  }
}

// HELPER: RENDER RESULTS TABLE
function renderResultsTable(container, rows) {
  if (!rows || !rows.length) {
    container.innerHTML = '<p class="empty-state" style="padding: 16px; text-align: center; color: var(--text-muted);">No records returned for this query.</p>';
    return;
  }
  const cols = Object.keys(rows[0]);
  let html = '<table><thead><tr>';
  cols.forEach(c => {
    html += `<th>${esc(c.replace(/_/g, " ").toUpperCase())}</th>`;
  });
  html += '</tr></thead><tbody>';
  rows.forEach(r => {
    html += '<tr>';
    cols.forEach(c => {
      const v = r[c];
      html += `<td>${v === null || v === undefined ? '—' : esc(v)}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

// ==========================================================================
// MODAL ADD RECORD
// ==========================================================================
async function openAddModal() {
  let targetEntity = currentPage;
  if (!entityConfigs[targetEntity] || targetEntity === "stock_audit") {
    targetEntity = "production_orders";
  }

  const cfg = entityConfigs[targetEntity];
  document.getElementById("modal-title").textContent = `Add Record to ${cfg.title}`;
  document.getElementById("modal-desc").textContent = `Create a new record in table: ${targetEntity.toUpperCase()}`;

  const fieldsContainer = document.getElementById("modal-fields-container");
  fieldsContainer.innerHTML = '<div style="grid-column: span 2; text-align: center;">Preparing form…</div>';
  document.getElementById("modal-form-feedback").textContent = "";

  const lookups = await getLookups();
  fieldsContainer.innerHTML = "";

  cfg.fields.forEach(field => {
    const wrap = document.createElement("div");
    wrap.className = "field-group" + (field.fullWidth ? " full-width" : "");

    const label = document.createElement("label");
    label.textContent = field.label + (field.required ? " *" : "");
    label.htmlFor = "field-" + field.name;
    wrap.appendChild(label);

    let input;
    if (field.type === "lookup") {
      input = document.createElement("select");
      input.name = field.name;
      input.id = "field-" + field.name;
      input.required = !!field.required;

      const defaultOpt = document.createElement("option");
      defaultOpt.value = "";
      defaultOpt.textContent = `Select ${field.label}…`;
      input.appendChild(defaultOpt);

      const items = lookups[field.lookup] || [];
      items.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item.id;
        opt.textContent = item.name + (item.role ? ` (${item.role})` : "");
        input.appendChild(opt);
      });
    } else if (field.type === "select") {
      input = document.createElement("select");
      input.name = field.name;
      input.id = "field-" + field.name;
      input.required = !!field.required;

      field.options.forEach(optVal => {
        const opt = document.createElement("option");
        opt.value = optVal;
        opt.textContent = optVal;
        input.appendChild(opt);
      });
    } else {
      input = document.createElement("input");
      input.type = field.type;
      input.name = field.name;
      input.id = "field-" + field.name;
      if (field.step) input.step = field.step;
      if (field.min !== undefined) input.min = field.min;
      if (field.default !== undefined) input.value = field.default;
      input.required = !!field.required;
    }

    wrap.appendChild(input);
    fieldsContainer.appendChild(wrap);
  });

  const modalForm = document.getElementById("modal-add-form");
  modalForm.onsubmit = async ev => {
    ev.preventDefault();
    const btn = document.getElementById("btn-save-record");
    btn.disabled = true;
    btn.textContent = "Saving…";

    const feedback = document.getElementById("modal-form-feedback");
    feedback.className = "form-feedback";
    feedback.textContent = "";

    const formData = new FormData(modalForm);
    const data = Object.fromEntries(formData.entries());

    Object.keys(data).forEach(k => {
      if (data[k] === "") delete data[k];
    });

    try {
      const res = await fetch(`/api/${targetEntity}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Could not save record.");

      feedback.className = "form-feedback success";
      feedback.textContent = "✓ " + json.message;

      cachedLookups = null;

      setTimeout(() => {
        closeAddModal();
        if (entityConfigs[currentPage]) {
          loadEntityTable();
        } else {
          window.location.reload();
        }
      }, 700);
    } catch (err) {
      feedback.className = "form-feedback error";
      feedback.textContent = "⚠ " + err.message;
    } finally {
      btn.disabled = false;
      btn.textContent = "Save Record +";
    }
  };

  document.getElementById("add-modal").classList.add("active");
}

function closeAddModal() {
  document.getElementById("add-modal").classList.remove("active");
}

// ==========================================================================
// MODAL ORDER DETAILS, BOM & INLINE FORMS
// ==========================================================================
let currentModalOrderId = null;

async function openOrderModal(orderId) {
  currentModalOrderId = orderId;
  const modal = document.getElementById("order-details-modal");
  modal.classList.add("active");

  document.getElementById("inline-mat-order-id").value = orderId;
  document.getElementById("inline-assign-order-id").value = orderId;

  // Populate raw materials and employees dropdowns
  const lookups = await getLookups();
  const matSelect = document.getElementById("inline-mat-id");
  matSelect.innerHTML = '<option value="">Select Raw Material…</option>';
  (lookups.raw_materials || []).forEach(m => {
    matSelect.innerHTML += `<option value="${m.id}">${esc(m.name)} (Stock: ${m.qty_in_stock} ${m.unit})</option>`;
  });

  const empSelect = document.getElementById("inline-assign-emp-id");
  empSelect.innerHTML = '<option value="">Select Employee…</option>';
  (lookups.employees || []).forEach(e => {
    empSelect.innerHTML += `<option value="${e.id}">${esc(e.name)} — ${esc(e.role)}</option>`;
  });

  reloadOrderModalData();
}

async function reloadOrderModalData() {
  const orderId = currentModalOrderId;
  const metaBox = document.getElementById("order-meta-box");
  const matBox = document.getElementById("order-materials-container");
  const assignBox = document.getElementById("order-assignments-container");

  metaBox.innerHTML = "Loading order overview…";
  matBox.innerHTML = "Loading bill of materials…";
  assignBox.innerHTML = "Loading staff assignments…";

  try {
    const res = await fetch(`/api/order_details/${orderId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not load order details.");

    const ord = data.order;
    document.getElementById("order-modal-title").textContent = `Production Order #${ord.order_id} — ${ord.product_name}`;

    metaBox.innerHTML = `
      <div><span>PRODUCT</span><strong>${esc(ord.product_name)}</strong></div>
      <div><span>BATCH QUANTITY</span><strong>${ord.produced_qty} / ${ord.quantity}</strong></div>
      <div><span>SUPERVISOR</span><strong>${esc(ord.supervisor)}</strong></div>
      <div><span>MACHINE</span><strong>${esc(ord.machine_name || 'Unassigned')}</strong></div>
    `;

    // Materials table (Composite PK order_id, material_id)
    if (!data.materials.length) {
      matBox.innerHTML = '<p class="empty-state">No materials registered for this order yet.</p>';
    } else {
      let matHtml = '<table><thead><tr><th>MATERIAL ID</th><th>MATERIAL NAME</th><th>QTY USED</th><th>UNIT COST</th><th>TOTAL COST</th><th>ACTION</th></tr></thead><tbody>';
      let totalBOMCost = 0;
      data.materials.forEach(m => {
        totalBOMCost += m.total_cost || 0;
        matHtml += `<tr>
          <td><b>#${m.material_id}</b></td>
          <td><b>${esc(m.material_name)}</b></td>
          <td>${m.qty_used} ${esc(m.unit)}</td>
          <td>₹${Number(m.unit_cost).toLocaleString('en-IN')}</td>
          <td>₹${Number(m.total_cost).toLocaleString('en-IN')}</td>
          <td><button class="delete-row-btn" onclick="deleteMaterialFromOrder(${m.order_id}, ${m.material_id})">✕ Remove</button></td>
        </tr>`;
      });
      matHtml += `<tr style="background: rgba(255,255,255,0.04); font-weight: bold;">
        <td colspan="4" style="text-align: right;">Total Material Cost:</td>
        <td colspan="2" style="color: var(--accent-cyan);">₹${Number(totalBOMCost).toLocaleString('en-IN')}</td>
      </tr>`;
      matHtml += '</tbody></table>';
      matBox.innerHTML = matHtml;
    }

    // Assignments table (Works On)
    if (!data.assignments.length) {
      assignBox.innerHTML = '<p class="empty-state">No specific workers assigned to this batch order yet.</p>';
    } else {
      let assignHtml = '<table><thead><tr><th>EMPLOYEE</th><th>TITLE</th><th>DEPARTMENT</th><th>ORDER ROLE</th><th>HOURS LOGGED</th><th>ACTION</th></tr></thead><tbody>';
      data.assignments.forEach(a => {
        assignHtml += `<tr>
          <td><b>${esc(a.emp_name)}</b></td>
          <td>${esc(a.role)}</td>
          <td>${esc(a.dept_name)}</td>
          <td><span class="status-pill status-in-progress">${esc(a.role_in_order)}</span></td>
          <td><b>${a.hours_logged} hrs</b></td>
          <td><button class="delete-row-btn" onclick="deleteWorkerFromOrder(${a.order_id}, ${a.emp_id})">✕ Remove</button></td>
        </tr>`;
      });
      assignHtml += '</tbody></table>';
      assignBox.innerHTML = assignHtml;
    }
  } catch (err) {
    metaBox.innerHTML = `<p style="color: #fb7185;">${err.message}</p>`;
  }
}

function toggleAddMaterialInline() {
  const form = document.getElementById("inline-add-material-form");
  form.style.display = form.style.display === "none" ? "block" : "none";
}

async function saveMaterialToOrder(ev) {
  ev.preventDefault();
  const orderId = document.getElementById("inline-mat-order-id").value;
  const matId = document.getElementById("inline-mat-id").value;
  const qty = document.getElementById("inline-mat-qty").value;
  const feedback = document.getElementById("inline-mat-feedback");

  feedback.textContent = "Allocating material to database…";
  try {
    const res = await fetch("/api/order_materials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_id: orderId, material_id: matId, qty_used: qty })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not allocate material");
    feedback.textContent = "✓ Allocated successfully to database.";
    document.getElementById("inline-mat-qty").value = "";
    cachedLookups = null;
    reloadOrderModalData();
  } catch (err) {
    feedback.textContent = "⚠ " + err.message;
  }
}

function toggleAssignWorkerInline() {
  const form = document.getElementById("inline-assign-worker-form");
  form.style.display = form.style.display === "none" ? "block" : "none";
}

async function saveWorkerToOrder(ev) {
  ev.preventDefault();
  const orderId = document.getElementById("inline-assign-order-id").value;
  const empId = document.getElementById("inline-assign-emp-id").value;
  const role = document.getElementById("inline-assign-role").value;
  const hours = document.getElementById("inline-assign-hours").value;
  const feedback = document.getElementById("inline-assign-feedback");

  feedback.textContent = "Assigning worker to database…";
  try {
    const res = await fetch("/api/order_assignments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_id: orderId, emp_id: empId, role_in_order: role, hours_logged: hours })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not assign worker");
    feedback.textContent = "✓ Assigned successfully to database.";
    reloadOrderModalData();
  } catch (err) {
    feedback.textContent = "⚠ " + err.message;
  }
}

async function deleteMaterialFromOrder(orderId, matId) {
  if (!confirm("Remove this raw material allocation from database?")) return;
  try {
    const res = await fetch("/api/order_materials/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_id: orderId, material_id: matId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not delete");
    reloadOrderModalData();
  } catch (e) {
    alert("Error: " + e.message);
  }
}

async function deleteWorkerFromOrder(orderId, empId) {
  if (!confirm("Remove this worker assignment from database?")) return;
  try {
    const res = await fetch("/api/order_assignments/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_id: orderId, emp_id: empId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not delete");
    reloadOrderModalData();
  } catch (e) {
    alert("Error: " + e.message);
  }
}

function closeOrderModal() {
  document.getElementById("order-details-modal").classList.remove("active");
}

function esc(str) {
  return String(str).replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[c]));
}
