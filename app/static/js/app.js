/* Price Monitor — vanilla JS frontend */

const BASE = "";
let apiKey = localStorage.getItem("pm_api_key") || "";
let currentPage = 0;
const PAGE_SIZE = 50;

// ── Key management ────────────────────────────────────────────
function saveKey() {
  apiKey = document.getElementById("api-key-input").value.trim();
  localStorage.setItem("pm_api_key", apiKey);
  document.getElementById("api-key-input").value = "";
  init();
}

function headers() {
  return { "X-API-Key": apiKey, "Content-Type": "application/json" };
}

async function apiFetch(url, opts = {}) {
  const res = await fetch(BASE + url, { ...opts, headers: headers() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// ── Tabs ──────────────────────────────────────────────────────
function showTab(name) {
  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".tab").forEach(el => el.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");
  event.target.classList.add("active");
  if (name === "dashboard") loadAnalytics();
  if (name === "products") loadProducts();
  if (name === "events") loadEvents();
}

// ── Dashboard ─────────────────────────────────────────────────
async function loadAnalytics() {
  try {
    const d = await apiFetch("/analytics");
    document.getElementById("stat-total").textContent = d.total_products;
    document.getElementById("stat-changes").textContent = d.total_price_changes_24h;
    document.getElementById("stat-grailed").textContent = d.by_source["grailed"] ?? 0;
    document.getElementById("stat-fashionphile").textContent = d.by_source["fashionphile"] ?? 0;
    document.getElementById("stat-1stdibs").textContent = d.by_source["1stdibs"] ?? 0;

    const cats = d.avg_price_by_category;
    const keys = Object.keys(cats);
    if (keys.length === 0) {
      document.getElementById("cat-table-wrap").innerHTML = '<p class="empty">No data yet — trigger a refresh.</p>';
      return;
    }
    const rows = keys.map(k =>
      `<tr><td>${k}</td><td>$${cats[k].toLocaleString(undefined, {minimumFractionDigits: 2})}</td></tr>`
    ).join("");
    document.getElementById("cat-table-wrap").innerHTML =
      `<table><thead><tr><th>Category</th><th>Avg Price (USD)</th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch (e) {
    showError("cat-table-wrap", e.message);
  }
}

// ── Refresh ───────────────────────────────────────────────────
async function triggerRefresh() {
  const btn = document.getElementById("refresh-btn");
  const status = document.getElementById("refresh-status");
  btn.disabled = true;
  status.textContent = "Refreshing…";
  try {
    const r = await apiFetch("/refresh", { method: "POST" });
    status.textContent = `✓ Loaded ${r.loaded} · Updated ${r.updated} · Changes ${r.price_changes} · Errors ${r.errors}`;
    loadAnalytics();
  } catch (e) {
    status.textContent = "✗ " + e.message;
  } finally {
    btn.disabled = false;
  }
}

// ── Products ──────────────────────────────────────────────────
async function loadProducts() {
  const params = buildProductParams();
  document.getElementById("products-list").innerHTML = "<p>Loading…</p>";
  try {
    const items = await apiFetch("/products?" + params.toString());
    renderProducts(items);
    document.getElementById("page-info").textContent = `Page ${currentPage + 1}`;
    document.getElementById("prev-btn").disabled = currentPage === 0;
    document.getElementById("next-btn").disabled = items.length < PAGE_SIZE;
  } catch (e) {
    showError("products-list", e.message);
  }
}

function buildProductParams() {
  const p = new URLSearchParams();
  const source = document.getElementById("f-source").value;
  const brand = document.getElementById("f-brand").value.trim();
  const cat = document.getElementById("f-category").value.trim();
  const min = document.getElementById("f-min").value;
  const max = document.getElementById("f-max").value;
  const sold = document.getElementById("f-sold").value;
  if (source) p.set("source", source);
  if (brand) p.set("brand", brand);
  if (cat) p.set("category", cat);
  if (min) p.set("min_price", min);
  if (max) p.set("max_price", max);
  if (sold !== "") p.set("is_sold", sold);
  p.set("limit", PAGE_SIZE);
  p.set("offset", currentPage * PAGE_SIZE);
  return p;
}

function renderProducts(items) {
  const wrap = document.getElementById("products-list");
  if (items.length === 0) { wrap.innerHTML = '<p class="empty">No products found.</p>'; return; }
  wrap.innerHTML = `<div class="product-grid">${items.map(productCard).join("")}</div>`;
}

function productCard(p) {
  const img = p.image_url
    ? `<img src="${esc(p.image_url)}" alt="${esc(p.model || '')}" loading="lazy" onerror="this.style.display='none'" />`
    : `<div style="height:180px;background:#eee;display:flex;align-items:center;justify-content:center;color:#aaa">No image</div>`;
  const sold = p.is_sold ? '<span class="card-badge sold-badge">Sold</span>' : '<span class="card-badge">Available</span>';
  return `<div class="product-card" onclick="openProduct(${p.id})">
    ${img}
    <div class="card-body">
      <div class="card-source">${esc(p.source)}</div>
      <div class="card-title">${esc(p.model || p.brand || 'Unknown')}</div>
      <div class="card-price">$${Number(p.current_price).toLocaleString()}</div>
      ${sold}
    </div>
  </div>`;
}

function changePage(dir) {
  currentPage = Math.max(0, currentPage + dir);
  loadProducts();
}

// ── Product detail modal ──────────────────────────────────────
async function openProduct(id) {
  document.getElementById("modal-overlay").classList.remove("hidden");
  document.getElementById("modal-content").innerHTML = "<p>Loading…</p>";
  try {
    const p = await apiFetch(`/products/${id}`);
    renderProductDetail(p);
  } catch (e) {
    document.getElementById("modal-content").innerHTML = `<p style="color:red">${e.message}</p>`;
  }
}

function renderProductDetail(p) {
  const img = p.image_url
    ? `<img class="modal-img" src="${esc(p.image_url)}" alt="${esc(p.model || '')}" onerror="this.style.display='none'" />`
    : "";

  const history = (p.price_history || [])
    .sort((a, b) => new Date(b.recorded_at) - new Date(a.recorded_at))
    .slice(0, 20);

  const histRows = history.length
    ? history.map(h =>
        `<tr><td>${fmtDate(h.recorded_at)}</td><td>$${Number(h.price).toLocaleString()}</td></tr>`
      ).join("")
    : `<tr><td colspan="2" style="color:#888">No history yet</td></tr>`;

  document.getElementById("modal-content").innerHTML = `
    ${img}
    <h2 style="margin-bottom:14px">${esc(p.model || p.brand || 'Product')}</h2>
    <div class="detail-row"><span class="detail-label">Source</span><span class="detail-val">${esc(p.source)}</span></div>
    <div class="detail-row"><span class="detail-label">Brand</span><span class="detail-val">${esc(p.brand || '—')}</span></div>
    <div class="detail-row"><span class="detail-label">Category</span><span class="detail-val">${esc(p.category || '—')}</span></div>
    <div class="detail-row"><span class="detail-label">Condition</span><span class="detail-val">${esc(p.condition || '—')}</span></div>
    <div class="detail-row"><span class="detail-label">Price</span><span class="detail-val" style="color:#e94560;font-size:1.1rem">$${Number(p.current_price).toLocaleString()}</span></div>
    <div class="detail-row"><span class="detail-label">Currency</span><span class="detail-val">${esc(p.currency)}</span></div>
    <div class="detail-row"><span class="detail-label">Status</span><span class="detail-val">${p.is_sold ? '🔴 Sold' : '🟢 Available'}</span></div>
    <div class="detail-row"><span class="detail-label">First Seen</span><span class="detail-val">${fmtDate(p.first_seen_at)}</span></div>
    ${p.product_url ? `<div class="detail-row"><span class="detail-label">Link</span><a href="${esc(p.product_url)}" target="_blank" style="color:#e94560">View Listing ↗</a></div>` : ""}
    <h2 style="margin-top:20px;margin-bottom:12px">Price History</h2>
    <table>
      <thead><tr><th>Date</th><th>Price</th></tr></thead>
      <tbody>${histRows}</tbody>
    </table>
  `;
}

function closeModal() {
  document.getElementById("modal-overlay").classList.add("hidden");
}

// ── Events ────────────────────────────────────────────────────
async function loadEvents() {
  const delivered = document.getElementById("f-delivered").value;
  const params = new URLSearchParams({ limit: 100 });
  if (delivered !== "") params.set("delivered", delivered);
  document.getElementById("events-list").innerHTML = "<p>Loading…</p>";
  try {
    const events = await apiFetch("/events?" + params.toString());
    renderEvents(events);
  } catch (e) {
    showError("events-list", e.message);
  }
}

function renderEvents(events) {
  const wrap = document.getElementById("events-list");
  if (events.length === 0) { wrap.innerHTML = '<p class="empty">No events.</p>'; return; }
  const rows = events.map(e => {
    const dir = e.new_price > (e.old_price || 0) ? "up" : "down";
    const arrow = dir === "up" ? "▲" : "▼";
    const pct = e.change_pct != null ? `(${e.change_pct > 0 ? "+" : ""}${e.change_pct.toFixed(1)}%)` : "";
    return `<tr>
      <td>${fmtDate(e.created_at)}</td>
      <td>#${e.product_id}</td>
      <td>$${e.old_price != null ? Number(e.old_price).toLocaleString() : "—"}</td>
      <td class="${dir}">${arrow} $${Number(e.new_price).toLocaleString()} ${pct}</td>
      <td>${e.delivered ? "✓" : "⏳"}</td>
    </tr>`;
  }).join("");
  wrap.innerHTML = `<table>
    <thead><tr><th>Time</th><th>Product</th><th>Old Price</th><th>New Price</th><th>Delivered</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

// ── Helpers ───────────────────────────────────────────────────
function esc(s) {
  if (s == null) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function showError(id, msg) {
  document.getElementById(id).innerHTML = `<p style="color:#c00">Error: ${esc(msg)}</p>`;
}

// ── Init ──────────────────────────────────────────────────────
function init() {
  if (apiKey) document.getElementById("api-key-input").placeholder = "Key saved ✓";
  loadAnalytics();
}

init();
