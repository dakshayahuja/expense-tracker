const API = "";  // same origin

const fmt = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const formatINR = (n) => fmt.format(n);

let _pendingDelBtn = null;
let _pendingDelTimer = null;
function clearPendingDel() {
  if (_pendingDelBtn) {
    _pendingDelBtn.dataset.confirm = "";
    _pendingDelBtn.textContent = "Del";
    _pendingDelBtn.style.borderColor = "";
    _pendingDelBtn.style.color = "";
    _pendingDelBtn = null;
  }
  clearTimeout(_pendingDelTimer);
  _pendingDelTimer = null;
}

// ── State ─────────────────────────────────────────
let categories = [];
let currentMonth = (() => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
})();
let allTxns = [];
let txnPage = 1;
const TXN_PAGE_SIZE = 10;

// ── Init ──────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  setDefaultDate();
  await loadCategories();
  loadTransactions();
  bindFilters();
  bindForm();
  bindModal();
  bindExport();
  bindImport();
});

function setDefaultDate() {
  const dateInput = document.getElementById("txn_date");
  if (dateInput) dateInput.value = new Date().toISOString().split("T")[0];

  const monthFilter = document.getElementById("filter-month");
  if (monthFilter) monthFilter.value = currentMonth;
}

// ── Categories ────────────────────────────────────
async function loadCategories() {
  const res = await fetch(`${API}/api/categories`);
  categories = await res.json();

  populateCategorySelect("category");
  populateCategorySelect("edit-category");
}

function populateCategorySelect(id) {
  const sel = document.getElementById(id);
  if (!sel) return;
  sel.innerHTML = categories
    .map((c) => `<option value="${c.name}">${c.name}</option>`)
    .join("");
}

// ── Transactions ──────────────────────────────────
async function loadTransactions() {
  const month = document.getElementById("filter-month")?.value || currentMonth;
  const type = document.getElementById("filter-type")?.value || "";

  const params = new URLSearchParams({ month });
  if (type) params.set("type", type);

  const res = await fetch(`${API}/api/transactions?${params}`);
  allTxns = await res.json();
  txnPage = 1;
  renderTransactions();
}

function renderTransactions() {
  const tbody = document.getElementById("txn-tbody");
  const pagEl = document.getElementById("txn-pagination");
  if (!tbody) return;

  if (allTxns.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading">No transactions for this period.</td></tr>`;
    if (pagEl) pagEl.innerHTML = "";
    return;
  }

  const totalPages = Math.ceil(allTxns.length / TXN_PAGE_SIZE);
  txnPage = Math.max(1, Math.min(txnPage, totalPages));
  const slice = allTxns.slice((txnPage - 1) * TXN_PAGE_SIZE, txnPage * TXN_PAGE_SIZE);

  tbody.innerHTML = slice.map((t) => `
    <tr data-id="${t.id}">
      <td>${formatDate(t.txn_date)}</td>
      <td>${escHtml(t.description || t.subcategory || "-")}</td>
      <td>${escHtml(t.category)}</td>
      <td><span class="badge badge-${t.type}">${t.type}</span></td>
      <td class="amount-${t.type}">${formatINR(t.amount)}</td>
      <td><span class="badge badge-${t.source}">${t.source}</span></td>
      <td class="actions">
        <button class="btn btn-edit" onclick="openEdit(${t.id})">Edit</button>
        <button class="btn btn-danger" onclick="deleteTxn(${t.id}, this)">Del</button>
      </td>
    </tr>
  `).join("");

  if (pagEl) renderPagination(pagEl, totalPages);
}

function renderPagination(el, totalPages) {
  if (totalPages <= 1) { el.innerHTML = ""; return; }

  const mkBtn = (label, page, disabled, active) => {
    const cls = ["pg-btn", active ? "active" : ""].filter(Boolean).join(" ");
    return `<button class="${cls}" ${disabled ? "disabled" : ""} onclick="goTxnPage(${page})">${label}</button>`;
  };

  let html = mkBtn("&#8592;", txnPage - 1, txnPage === 1, false);
  html += `<span class="pg-info">Page ${txnPage} / ${totalPages}</span>`;

  const start = Math.max(1, Math.min(txnPage - 2, totalPages - 4));
  const end   = Math.min(totalPages, start + 4);
  if (start > 1) html += mkBtn("1", 1, false, false) + (start > 2 ? `<span class="pg-info">…</span>` : "");
  for (let p = start; p <= end; p++) html += mkBtn(p, p, false, p === txnPage);
  if (end < totalPages) html += (end < totalPages - 1 ? `<span class="pg-info">…</span>` : "") + mkBtn(totalPages, totalPages, false, false);

  html += mkBtn("&#8594;", txnPage + 1, txnPage === totalPages, false);
  el.innerHTML = html;
}

function goTxnPage(page) {
  txnPage = page;
  renderTransactions();
}

function formatDate(isoDate) {
  const [y, m, d] = isoDate.split("-");
  return `${d}/${m}/${y.slice(2)}`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Add transaction ───────────────────────────────
function bindForm() {
  const form = document.getElementById("txn-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = document.getElementById("form-status");
    status.textContent = "";
    status.className = "form-status";

    const data = {
      amount: parseFloat(form.amount.value),
      type: form.type.value,
      category: form.category.value,
      subcategory: form.subcategory.value,
      description: form.description.value,
      txn_date: form.txn_date.value,
      source: "web",
      account: form.account.value,
    };

    const res = await fetch(`${API}/api/transactions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (res.ok) {
      status.textContent = "Transaction added.";
      status.className = "form-status success";
      form.reset();
      setDefaultDate();
      loadTransactions();
    } else {
      const err = await res.json();
      status.textContent = `Error: ${JSON.stringify(err.detail)}`;
      status.className = "form-status error";
    }
  });
}

// ── Filters ───────────────────────────────────────
function bindFilters() {
  document.getElementById("filter-month")?.addEventListener("change", loadTransactions);
  document.getElementById("filter-type")?.addEventListener("change", loadTransactions);
}

// ── Delete ────────────────────────────────────────
function deleteTxn(id, btn) {
  if (btn.dataset.confirm !== "1") {
    clearPendingDel();
    btn.dataset.confirm = "1";
    btn.textContent = "Sure?";
    btn.style.borderColor = "var(--red)";
    btn.style.color = "var(--red)";
    _pendingDelBtn = btn;
    _pendingDelTimer = setTimeout(clearPendingDel, 3000);
    return;
  }
  clearPendingDel();
  const row = btn.closest("tr");
  if (row) row.remove();
  fetch(`${API}/api/transactions/${id}`, { method: "DELETE" })
    .then(res => { if (res.ok || res.status === 204) loadTransactions(); });
}

// ── Edit modal ────────────────────────────────────
function bindModal() {
  document.getElementById("modal-close")?.addEventListener("click", () => {
    document.getElementById("edit-modal").classList.add("hidden");
  });

  document.getElementById("edit-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("edit-id").value;
    const data = {
      amount: parseFloat(document.getElementById("edit-amount").value),
      category: document.getElementById("edit-category").value,
      description: document.getElementById("edit-description").value,
      txn_date: document.getElementById("edit-date").value,
    };
    const res = await fetch(`${API}/api/transactions/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (res.ok) {
      document.getElementById("edit-modal").classList.add("hidden");
      loadTransactions();
    }
  });
}

// ── Export ────────────────────────────────────────
function bindExport() {
  document.getElementById("export-btn")?.addEventListener("click", () => {
    const month = document.getElementById("filter-month")?.value || currentMonth;
    window.location.href = `${API}/api/transactions/export?month=${month}`;
  });
}

// ── Statement Import (PDF + CSV) ──────────────────
let parsedRows = [];

const BANK_LABELS = { au: "AU Bank", yes: "Yes Bank", hdfc: "HDFC Bank", csv: "CSV" };

function bindImport() {
  const fileInput  = document.getElementById("import-file");
  const bankSel    = document.getElementById("import-bank");
  const pickBtn    = document.getElementById("import-pick-btn");
  const confirmBtn = document.getElementById("import-confirm-btn");
  const cancelBtn  = document.getElementById("import-cancel-btn");
  if (!fileInput) return;

  pickBtn.addEventListener("click", () => {
    const bank = bankSel?.value;
    if (!bank) { setImportStatus("error", "Select a statement type first."); return; }
    fileInput.accept = bank === "csv" ? ".csv" : ".pdf";
    fileInput.click();
  });

  fileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    fileInput.value = "";
    const bank = bankSel?.value || "";
    if (bank === "csv") {
      handleCSVImport(file);
    } else if (bank) {
      await handlePDFImport(file, bank);
    } else {
      setImportStatus("error", "Select a statement type first.");
    }
  });

  confirmBtn?.addEventListener("click", async () => {
    if (!parsedRows.length) return;
    const rows = collectImportRows();
    if (!rows.length) return;
    const res = await fetch(`${API}/api/transactions/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rows),
    });
    if (res.ok) {
      const { imported } = await res.json();
      setImportStatus("success", `${imported} transaction${imported !== 1 ? "s" : ""} imported.`);
      document.getElementById("import-preview").classList.add("hidden");
      parsedRows = [];
      loadTransactions();
    } else {
      const err = await res.json();
      setImportStatus("error", `Import failed: ${JSON.stringify(err.detail)}`);
    }
  });

  cancelBtn?.addEventListener("click", () => {
    document.getElementById("import-preview").classList.add("hidden");
    parsedRows = [];
    setImportStatus("", "");
  });
}

async function handlePDFImport(file, bank) {
  const btn = document.getElementById("import-pick-btn");
  if (btn) btn.disabled = true;
  setImportStatus("", "Parsing PDF…");
  try {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("bank", bank);
    const res = await fetch(`${API}/api/import/parse`, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) {
      setImportStatus("error", `Parse error: ${data.detail || "Unknown error"}`);
      return;
    }
    parsedRows = data.rows;
    renderImportPreview(parsedRows);
    const label = BANK_LABELS[bank] || bank;
    setImportStatus("success", `${label} — ${data.count} transactions ready. Review above — edit descriptions, fix categories, remove unwanted rows, then confirm.`);
  } catch (err) {
    setImportStatus("error", `Network error: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function handleCSVImport(file) {
  const reader = new FileReader();
  reader.onload = (ev) => {
    try {
      parsedRows = parseCSV(ev.target.result);
      renderImportPreview(parsedRows);
      setImportStatus("success", `${parsedRows.length} rows ready. Review above — edit descriptions, fix categories, remove unwanted rows, then confirm.`);
    } catch (err) {
      setImportStatus("error", `Parse error: ${err.message}`);
    }
  };
  reader.readAsText(file, "utf-8");
}

function parseCSV(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) throw new Error("CSV has no data rows");

  const headers = splitCSVLine(lines[0]).map(h => h.trim().toLowerCase().replace(/[^a-z0-9]/g, ""));

  // Detect HDFC format: has "narration" or "transactionremarks" column
  const isHDFC = headers.some(h => h === "narration" || h === "transactionremarks");

  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = splitCSVLine(lines[i]);
    if (cols.every(c => !c.trim())) continue; // skip blank lines

    let row;
    if (isHDFC) {
      row = parseHDFCRow(headers, cols);
    } else {
      row = parseGenericRow(headers, cols);
    }
    if (row) rows.push(row);
  }
  if (rows.length === 0) throw new Error("No valid rows found in CSV");
  return rows;
}

function parseHDFCRow(headers, cols) {
  const get = (names) => {
    for (const n of names) {
      const idx = headers.findIndex(h => h.includes(n));
      if (idx !== -1) return (cols[idx] || "").trim();
    }
    return "";
  };

  const rawDate = get(["date", "valuedate", "transactiondate"]);
  const narration = get(["narration", "transactionremarks"]);
  const withdrawal = parseFloat(get(["withdrawalamtinr", "withdrawalamt", "withdrawal"]).replace(/,/g, "")) || 0;
  const deposit    = parseFloat(get(["depositamtinr", "depositamt", "deposit"]).replace(/,/g, "")) || 0;

  if (!rawDate || (!withdrawal && !deposit)) return null;

  // HDFC date: DD/MM/YY or DD/MM/YYYY
  const txn_date = parseHDFCDate(rawDate);
  if (!txn_date) return null;

  const amount = withdrawal > 0 ? withdrawal : deposit;
  const type   = withdrawal > 0 ? "expense" : "income";
  const category = autoCategory(narration, categories);

  return { txn_date, description: narration, category, type, amount, source: "web", subcategory: "" };
}

function parseGenericRow(headers, cols) {
  const get = (name) => {
    const idx = headers.indexOf(name);
    return idx !== -1 ? (cols[idx] || "").trim() : "";
  };

  const txn_date   = get("date");
  const amount_raw = parseFloat(get("amount").replace(/,/g, ""));
  const type       = get("type") || "expense";
  const description = get("description") || get("narration") || "";
  const category   = get("category") || autoCategory(description, categories);
  const subcategory = get("subcategory") || "";
  const account    = get("account") || "";

  if (!txn_date || isNaN(amount_raw)) return null;
  return { txn_date, description, category, subcategory, type, amount: amount_raw, source: "web", account };
}

function parseHDFCDate(raw) {
  // DD/MM/YY or DD/MM/YYYY
  const parts = raw.split("/");
  if (parts.length !== 3) return null;
  let [dd, mm, yy] = parts;
  if (yy.length === 2) yy = "20" + yy;
  if (!dd || !mm || !yy) return null;
  return `${yy}-${mm.padStart(2,"0")}-${dd.padStart(2,"0")}`;
}

function autoCategory(description, cats) {
  const desc = description.toLowerCase();
  for (const cat of cats) {
    if (!cat.keywords) continue;
    const keywords = cat.keywords.split(",").map(k => k.trim().toLowerCase()).filter(Boolean);
    if (keywords.some(kw => desc.includes(kw))) return cat.name;
  }
  return "Miscellaneous";
}

// Handles quoted fields with commas inside
function splitCSVLine(line) {
  const result = [];
  let cur = "", inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { inQ = !inQ; }
    else if (ch === "," && !inQ) { result.push(cur); cur = ""; }
    else { cur += ch; }
  }
  result.push(cur);
  return result;
}

function renderImportPreview(rows) {
  const preview = document.getElementById("import-preview");
  const tbody   = document.getElementById("import-tbody");

  const activeCount = rows.filter(r => !r.skip).length;
  document.getElementById("import-count").textContent = `${activeCount} of ${rows.length} rows selected to import`;

  tbody.innerHTML = rows.map((r, i) => `
    <tr data-import-idx="${i}" class="${r.skip ? "import-row-skipped" : ""}">
      <td>${r.txn_date}</td>
      <td><input class="import-desc-input" data-idx="${i}" value="${escHtml(r.description)}" title="${escHtml(r.description)}"></td>
      <td>
        <select class="filter-input import-type-sel" data-idx="${i}" style="width:auto;font-size:.8rem;padding:.25rem .5rem">
          <option value="expense"   ${r.type==="expense"    ? "selected" : ""}>Expense</option>
          <option value="income"    ${r.type==="income"     ? "selected" : ""}>Income</option>
          <option value="investment"${r.type==="investment" ? "selected" : ""}>Investment</option>
        </select>
      </td>
      <td>
        <select class="filter-input import-cat-sel" data-idx="${i}" style="width:auto;font-size:.8rem;padding:.25rem .5rem">
          ${categories.map(c => `<option value="${escHtml(c.name)}" ${c.name === r.category ? "selected" : ""}>${escHtml(c.name)}</option>`).join("")}
        </select>
      </td>
      <td>${formatINR(r.amount)}</td>
      <td><button class="btn btn-danger import-row-toggle" data-idx="${i}" title="${r.skip ? "Include row" : "Skip row"}">${r.skip ? "+" : "✕"}</button></td>
    </tr>
  `).join("");

  tbody.querySelectorAll(".import-row-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      parsedRows[idx].skip = !parsedRows[idx].skip;
      renderImportPreview(parsedRows);
    });
  });

  preview.classList.remove("hidden");
}

function collectImportRows() {
  return parsedRows
    .map((r, i) => {
      if (r.skip) return null;
      const catSel  = document.querySelector(`.import-cat-sel[data-idx="${i}"]`);
      const typeSel = document.querySelector(`.import-type-sel[data-idx="${i}"]`);
      const descEl  = document.querySelector(`.import-desc-input[data-idx="${i}"]`);
      return {
        ...r,
        description: descEl ? descEl.value.trim() || r.description : r.description,
        category: catSel ? catSel.value : r.category,
        type: typeSel ? typeSel.value : r.type,
      };
    })
    .filter(Boolean);
}

function setImportStatus(cls, msg) {
  const el = document.getElementById("import-status");
  if (!el) return;
  el.textContent = msg;
  el.className = cls ? `form-status ${cls}` : "form-status";
}

function openEdit(id) {
  const row = document.querySelector(`tr[data-id="${id}"]`);
  if (!row) return;

  // Pull data from existing fetch state
  fetch(`${API}/api/transactions?month=${document.getElementById("filter-month")?.value || currentMonth}`)
    .then((r) => r.json())
    .then((txns) => {
      const t = txns.find((x) => x.id === id);
      if (!t) return;
      document.getElementById("edit-id").value = t.id;
      document.getElementById("edit-amount").value = t.amount;
      document.getElementById("edit-description").value = t.description || "";
      document.getElementById("edit-date").value = t.txn_date;
      populateCategorySelect("edit-category");
      document.getElementById("edit-category").value = t.category;
      document.getElementById("edit-modal").classList.remove("hidden");
    });
}
