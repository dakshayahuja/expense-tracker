const API = "";

const fmt = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const formatINR = (n) => fmt.format(n);
const formatDate = (d) => { const [y,m,dd] = d.split("-"); return `${dd}/${m}/${y.slice(2)}`; };
const escHtml = (s) => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

// ── Palette — read live from CSS custom properties ─
function getCSSVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
function getChartColors() {
  return [
    getCSSVar("--ch1"), getCSSVar("--ch2"), getCSSVar("--ch3"),
    getCSSVar("--ch4"), getCSSVar("--ch5"), getCSSVar("--ch6"),
    getCSSVar("--ch7"), getCSSVar("--ch8"), getCSSVar("--ch9"), getCSSVar("--ch10"),
  ];
}

// Categories classified as "wealth-building" (good outflow)
const WEALTH_CATS = new Set(["Investments/SIP","Emergency Fund","Stocks/IPO","Insurance"]);

// ── State ─────────────────────────────────────────
let currentMonth = (() => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
})();

let donutChart = null;
let splitChart = null;
let trendChart = null;
let categories = [];
let allTxns = [];
let txnPage = 1;
const TXN_PAGE_SIZE = 10;

// ── Boot ──────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("dash-month").value = currentMonth;
  categories = await fetch(`${API}/api/categories`).then(r => r.json());
  populateCategorySelect("edit-category");

  await loadDashboard();
  bindControls();
  bindModal();
});

// ── Controls ──────────────────────────────────────
function bindControls() {
  document.getElementById("dash-month").addEventListener("change", (e) => {
    currentMonth = e.target.value;
    loadDashboard();
  });

  document.getElementById("prev-month").addEventListener("click", () => {
    const [y, m] = currentMonth.split("-").map(Number);
    const d = new Date(y, m - 2, 1);
    currentMonth = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
    document.getElementById("dash-month").value = currentMonth;
    loadDashboard();
  });

  document.getElementById("next-month").addEventListener("click", () => {
    const [y, m] = currentMonth.split("-").map(Number);
    const d = new Date(y, m, 1);
    currentMonth = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
    document.getElementById("dash-month").value = currentMonth;
    loadDashboard();
  });

  document.getElementById("refresh-btn").addEventListener("click", loadDashboard);
  document.getElementById("filter-type").addEventListener("change", () => loadTransactions());

  document.getElementById("export-btn").addEventListener("click", () => {
    window.location.href = `${API}/api/transactions/export?month=${currentMonth}`;
  });

  document.getElementById("rb-dismiss").addEventListener("click", () => {
    document.getElementById("rollover-banner").classList.add("hidden");
  });
}

// ── Main load ─────────────────────────────────────
async function loadDashboard() {
  document.querySelectorAll(".hcard").forEach(c => c.classList.add("loading"));

  const [summary, trends] = await Promise.all([
    fetch(`${API}/api/summary?month=${currentMonth}`).then(r => r.json()),
    fetch(`${API}/api/trends?months=6`).then(r => r.json()),
  ]);

  document.querySelectorAll(".hcard").forEach(c => c.classList.remove("loading"));
  renderHeadlineCards(summary);
  renderBudgetBars(summary.categories);
  renderDonut(summary.categories);
  renderSplit(summary.categories);
  renderTrends(trends);
  renderSuggestions(summary.categories);
  checkRollover();
  loadTransactions();
}

// ── Rollover banner ───────────────────────────────
async function checkRollover() {
  const banner = document.getElementById("rollover-banner");
  const now = new Date();
  const nowMonth = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}`;

  // Only show when viewing the current month
  if (currentMonth !== nowMonth) { banner.classList.add("hidden"); return; }

  const [y, m] = currentMonth.split("-").map(Number);
  const prev = new Date(y, m - 2, 1);
  const prevMonth = `${prev.getFullYear()}-${String(prev.getMonth()+1).padStart(2,"0")}`;

  const summary = await fetch(`${API}/api/summary?month=${prevMonth}`).then(r => r.json());
  const over = summary.categories.filter(c => c.over_budget && !c.pre_deducted);

  if (over.length === 0) { banner.classList.add("hidden"); return; }

  const monthLabel = new Date(prev.getFullYear(), prev.getMonth()).toLocaleString("en-IN", { month: "long", year: "numeric" });
  document.getElementById("rb-title").textContent = `${monthLabel} had ${over.length} over-budget ${over.length === 1 ? "category" : "categories"}`;
  document.getElementById("rb-list").innerHTML = over.map(c =>
    `<li>${escHtml(c.name)} <span>+${formatINR(c.actual - c.budget)}</span></li>`
  ).join("");
  banner.classList.remove("hidden");
}

// ── 6. Suggestions panel ──────────────────────────
function renderSuggestions(cats) {
  const card = document.getElementById("suggestions-card");
  const grid = document.getElementById("suggestions-grid");

  const over = cats
    .filter(c => c.over_budget && !c.pre_deducted && c.type === "expense")
    .sort((a, b) => (b.actual - b.budget) - (a.actual - a.budget))
    .slice(0, 3);

  if (over.length === 0) { card.style.display = "none"; return; }
  card.style.display = "";

  grid.innerHTML = over.map(c => {
    const gap = c.actual - c.budget;
    const pct = Math.min((c.actual / c.budget) * 100, 200);
    return `
      <div class="suggestion-item">
        <div class="si-name">${escHtml(c.name)}</div>
        <div class="si-over">+${formatINR(gap)} over</div>
        <div class="si-meta">Budgeted ${formatINR(c.budget)} · Spent ${formatINR(c.actual)}</div>
        <div class="si-bar"><div class="si-bar-fill" style="width:${Math.min(pct - 100, 100)}%"></div></div>
      </div>
    `;
  }).join("");
}

// ── 1. Headline cards ─────────────────────────────
function renderHeadlineCards(s) {
  document.getElementById("hc-income").textContent = formatINR(s.total_income);
  document.getElementById("hc-expense").textContent = formatINR(s.total_expense);
  document.getElementById("hc-invest").textContent = formatINR(s.total_investment);
  document.getElementById("hc-net").textContent = formatINR(s.net_saved);
  document.getElementById("hc-savings").textContent = `${s.savings_rate}%`;

  const card = document.getElementById("hc-savings-card");
  card.classList.remove("savings-green","savings-amber","savings-red");
  if (s.savings_rate >= 21.5) card.classList.add("savings-green");
  else if (s.savings_rate >= 10) card.classList.add("savings-amber");
  else card.classList.add("savings-red");
}

// ── 2. Budget vs Actual bars ──────────────────────
function renderBudgetBars(cats) {
  const container = document.getElementById("budget-bars");
  container.innerHTML = cats.map(cat => {
    const pct = Math.min(cat.pct_used, 100);
    const isPreDeducted = cat.pre_deducted;
    const isOver = cat.over_budget && !isPreDeducted;
    const isInvest = cat.type === "investment";

    let fillClass = "bar-fill";
    if (isPreDeducted) fillClass += " muted-fill";
    else if (isOver) fillClass += " over";
    else if (isInvest) fillClass += " invest-fill";

    const amountClass = isOver ? "budget-amounts over" : "budget-amounts";
    const pctClass = isOver ? "budget-pct over" : "budget-pct";
    const nameClass = isPreDeducted ? "budget-name muted" : "budget-name";

    const tag = isPreDeducted ? " <span style='font-size:.7rem;color:var(--text-muted)'>(auto)</span>" : "";

    return `
      <div class="budget-row">
        <div class="${nameClass}">${escHtml(cat.name)}${tag}</div>
        <div class="bar-track">
          <div class="${fillClass}" style="width:${pct}%"></div>
        </div>
        <div class="${amountClass}">
          ${formatINR(cat.actual)} <span style="color:var(--text-muted)">/ ${formatINR(cat.budget)}</span>
        </div>
        <div class="${pctClass}">${cat.pct_used.toFixed(0)}%</div>
      </div>
    `;
  }).join("");
}

// ── 3. Outflow donut ──────────────────────────────
function renderDonut(cats) {
  const COLORS = getChartColors();
  const data = cats.filter(c => c.actual > 0 && !c.pre_deducted);
  const labels = data.map(c => c.name);
  const values = data.map(c => c.actual);

  if (donutChart) donutChart.destroy();

  const ctx = document.getElementById("donut-chart").getContext("2d");
  donutChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: COLORS.slice(0, data.length).map(c => c + "cc"),
        borderWidth: 2,
        borderColor: getCSSVar("--chart-border"),
        hoverBorderColor: COLORS.slice(0, data.length),
        hoverBorderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: getCSSVar("--chart-tick"), font: { size: 11 }, boxWidth: 10, padding: 12, usePointStyle: true, pointStyleWidth: 10 },
        },
        tooltip: {
          backgroundColor: getCSSVar("--chart-tooltip-bg"),
          borderColor: getCSSVar("--chart-tooltip-border"),
          borderWidth: 1,
          titleColor: getCSSVar("--chart-tooltip-title"),
          bodyColor: getCSSVar("--chart-tooltip-body"),
          callbacks: { label: (ctx) => ` ${formatINR(ctx.parsed)}` },
        },
      },
      cutout: "68%",
    },
  });
}

// ── 4. Good vs Lifestyle split ────────────────────
function renderSplit(cats) {
  const wealthCats = cats.filter(c => WEALTH_CATS.has(c.name) && (c.actual > 0 || c.pre_deducted));
  const lifeCats = cats.filter(c => !WEALTH_CATS.has(c.name) && c.actual > 0);

  const wealthTotal = wealthCats.reduce((s, c) => s + c.actual, 0);
  const lifeTotal = lifeCats.reduce((s, c) => s + c.actual, 0);

  // Legend
  const legend = document.getElementById("split-legend");
  legend.innerHTML = `
    <span><span class="split-dot" style="background:${getCSSVar('--ch1')}"></span>Wealth-building <strong style="color:var(--text)">${formatINR(wealthTotal)}</strong></span>
    <span><span class="split-dot" style="background:${getCSSVar('--ch3')}"></span>Lifestyle <strong style="color:var(--text)">${formatINR(lifeTotal)}</strong></span>
  `;

  const labels = ["Wealth-building", "Lifestyle"];
  const values = [wealthTotal, lifeTotal];

  if (splitChart) splitChart.destroy();

  const ctx = document.getElementById("split-chart").getContext("2d");
  splitChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: [getCSSVar("--ch1") + "bf", getCSSVar("--ch3") + "a8"],
        borderWidth: 2,
        borderColor: getCSSVar("--chart-border"),
        hoverBorderColor: [getCSSVar("--ch1"), getCSSVar("--ch3")],
        hoverBorderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: getCSSVar("--chart-tooltip-bg"),
          borderColor: getCSSVar("--chart-tooltip-border"),
          borderWidth: 1,
          titleColor: getCSSVar("--chart-tooltip-title"),
          bodyColor: getCSSVar("--chart-tooltip-body"),
          callbacks: { label: (ctx) => ` ${formatINR(ctx.parsed)}` },
        },
      },
      cutout: "68%",
    },
  });
}

// ── 5. Trend line ─────────────────────────────────
function renderTrends(trends) {
  // Pick top 5 categories by total spend across all months
  const catTotals = {};
  for (const month of trends) {
    for (const [cat, val] of Object.entries(month.categories)) {
      catTotals[cat] = (catTotals[cat] || 0) + val;
    }
  }
  const topCats = Object.entries(catTotals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name]) => name);

  const labels = trends.map(t => {
    const [y, m] = t.month.split("-");
    return new Date(+y, +m - 1).toLocaleString("en-IN", { month: "short", year: "2-digit" });
  });

  const COLORS = getChartColors();
  const chartBorder = getCSSVar("--chart-border");
  const chartGrid   = getCSSVar("--chart-grid");
  const chartTick   = getCSSVar("--chart-tick");

  const datasets = topCats.map((cat, i) => ({
    label: cat,
    data: trends.map(t => t.categories[cat] || 0),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length] + "18",
    tension: 0.4,
    fill: true,
    pointRadius: 4,
    pointHoverRadius: 6,
    pointBackgroundColor: COLORS[i % COLORS.length],
    pointBorderColor: chartBorder,
    pointBorderWidth: 2,
    borderWidth: 2,
  }));

  if (trendChart) trendChart.destroy();

  const ctx = document.getElementById("trend-chart").getContext("2d");
  trendChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          ticks: { color: chartTick, font: { size: 11 } },
          grid: { color: chartGrid },
          border: { color: chartGrid },
        },
        y: {
          ticks: { color: chartTick, font: { size: 11 }, callback: (v) => formatINR(v) },
          grid: { color: chartGrid },
          border: { color: chartGrid },
        },
      },
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: chartTick, font: { size: 11 }, boxWidth: 10, padding: 12, usePointStyle: true, pointStyleWidth: 10 },
        },
        tooltip: {
          backgroundColor: getCSSVar("--chart-tooltip-bg"),
          borderColor: getCSSVar("--chart-tooltip-border"),
          borderWidth: 1,
          titleColor: getCSSVar("--chart-tooltip-title"),
          bodyColor: getCSSVar("--chart-tooltip-body"),
          callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${formatINR(ctx.parsed.y)}` },
        },
      },
    },
  });
}

// ── 6. Transactions table ─────────────────────────
async function loadTransactions() {
  const type = document.getElementById("filter-type")?.value || "";
  const params = new URLSearchParams({ month: currentMonth });
  if (type) params.set("type", type);

  allTxns = await fetch(`${API}/api/transactions?${params}`).then(r => r.json());
  txnPage = 1;
  renderTransactions();
}

function renderTransactions() {
  const tbody = document.getElementById("txn-tbody");
  const pagEl = document.getElementById("txn-pagination");

  if (allTxns.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading">No transactions for this period.</td></tr>`;
    if (pagEl) pagEl.innerHTML = "";
    return;
  }

  const totalPages = Math.ceil(allTxns.length / TXN_PAGE_SIZE);
  txnPage = Math.max(1, Math.min(txnPage, totalPages));
  const slice = allTxns.slice((txnPage - 1) * TXN_PAGE_SIZE, txnPage * TXN_PAGE_SIZE);

  tbody.innerHTML = slice.map(t => `
    <tr data-id="${t.id}">
      <td>${formatDate(t.txn_date)}</td>
      <td>${escHtml(t.description || t.subcategory || "-")}</td>
      <td>${escHtml(t.category)}</td>
      <td><span class="badge badge-${t.type}">${t.type}</span></td>
      <td class="amount-${t.type}">${formatINR(t.amount)}</td>
      <td><span class="badge badge-${t.source}">${t.source}</span></td>
      <td class="actions">
        <button class="btn btn-edit" onclick="openEdit(${t.id})">Edit</button>
        <button class="btn btn-danger" onclick="deleteTxn(${t.id})">Del</button>
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

  // show up to 5 page numbers centred on current page
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

// ── Edit + Delete ─────────────────────────────────
async function deleteTxn(id) {
  if (!confirm(`Delete transaction #${id}?`)) return;
  const res = await fetch(`${API}/api/transactions/${id}`, { method: "DELETE" });
  if (res.ok || res.status === 204) loadDashboard();
}

function populateCategorySelect(id) {
  const sel = document.getElementById(id);
  if (!sel) return;
  sel.innerHTML = categories.map(c => `<option value="${c.name}">${c.name}</option>`).join("");
}

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
      loadDashboard();
    }
  });
}

function openEdit(id) {
  fetch(`${API}/api/transactions?month=${currentMonth}`)
    .then(r => r.json())
    .then(txns => {
      const t = txns.find(x => x.id === id);
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
