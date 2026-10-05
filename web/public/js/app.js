// Shell of the single-page app: hash router, navy sidebar, top bar (theme switch, user menu) and page header.
import { modelApi } from "./api.js?v=20261005";
import { clearAuth, getAuth, onAuthChange } from "./auth.js?v=20261005";
import { applyChartTheme, destroyAll } from "./charts.js?v=20261005";
import { icon } from "./icons.js?v=20261005";
import { CLASS_KEYS, esc, toast } from "./ui.js?v=20261005";

// Sidebar order follows docs/mockup/bt2-chan-doan-svm-threshold.png.
const ROUTES = {
  "tong-quan": { module: "./pages/overview.js?v=20261005", label: "Tổng quan", icon: "house" },
  "chan-doan": { module: "./pages/diagnose.js?v=20261005", label: "Chẩn đoán SVM", icon: "brain" },
  "so-sanh": { module: "./pages/compare.js?v=20261005", label: "So sánh mô hình", icon: "chart-no-axes-column" },
  "phan-tich": { module: "./pages/analysis.js?v=20261005", label: "Phân tích nâng cao", icon: "trending-up" },
  "lich-su": { module: "./pages/history.js?v=20261005", label: "Lịch sử", icon: "clock" },
  "du-lieu-sql": { module: "./pages/sql.js?v=20261005", label: "Dữ liệu SQL", icon: "database", badge: "SQL" },
  "diem-noi-bat": { module: "./pages/highlights.js?v=20261005", label: "Điểm nổi bật", icon: "star" },
  "dang-nhap": { module: "./pages/login.js?v=20261005", label: "Đăng nhập", icon: "log-in", hidden: true },
};
const DEFAULT_ROUTE = "tong-quan";
const CLASS_KEY = "bc-class";
const THEME_KEY = "bc-theme";

const view = document.getElementById("view");
const state = {
  cls: readClass(),
  classInfo: {},   // from GET /classes on the model API
  health: null,    // last GET /health result (sidebar status)
  renderId: 0,
  route: null,
};

function readClass() {
  try {
    const c = localStorage.getItem(CLASS_KEY);
    return CLASS_KEYS.includes(c) ? c : "malignant";
  } catch (_) {
    return "malignant";
  }
}

function currentRoute() {
  const name = location.hash.replace(/^#\/?/, "").split("?")[0];
  return ROUTES[name] ? name : null;
}

// ------------------------------------------------------------------ sidebar

function navItem(name) {
  const r = ROUTES[name];
  const active = state.route === name ? " active" : "";
  const badge = r.badge ? `<span class="nav-badge">${esc(r.badge)}</span>` : "";
  const current = active ? ' aria-current="page"' : "";
  return `<a class="nav-item${active}" href="#/${name}"${current}>${icon(r.icon, 20)}<span>${esc(r.label)}</span>${badge}</a>`;
}

function renderSidebar() {
  const h = state.health;
  const status = h === null ? ["", "Đang kiểm tra API…", ""]
    : h.ok ? ["ok", "API Online", `v${h.version}`] : ["bad", "API Offline", ""];
  document.getElementById("sidebar").innerHTML = `
    <div class="side-brand">${icon("ribbon", 40, "ribbon")}
      <div><b>Chẩn đoán ung thư vú</b><span>SVM - Machine Learning</span></div></div>
    <div class="side-nav">${Object.keys(ROUTES).filter(n => !ROUTES[n].hidden).map(navItem).join("")}</div>
    <div class="side-bottom">
      <div class="side-card">
        <div class="side-card-head">${icon("shield", 20)}SVM - Breast Cancer</div>
        <p>Ứng dụng Machine Learning chẩn đoán ung thư vú dựa trên bộ dữ liệu Wisconsin.</p>
      </div>
      <div class="side-status"><span><span class="dot ${status[0]}"></span>${status[1]}</span><span>${esc(status[2])}</span></div>
      <div class="side-tech">FastAPI · Render</div>
    </div>`;
}

async function checkHealth() {
  try {
    const h = await modelApi("/health");
    state.health = { ok: true, version: h.model_version };
  } catch (_) {
    state.health = { ok: false };
  }
  renderSidebar();
}

function setClass(key) {
  state.cls = key;
  try { localStorage.setItem(CLASS_KEY, key); } catch (_) { /* storage blocked */ }
  if (state.route === "tong-quan") render();
  else location.hash = "#/tong-quan";
}

// ------------------------------------------------------------------ theme

function isDark() {
  return document.documentElement.dataset.theme === "dark";
}

function renderThemeButton() {
  const btn = document.getElementById("themeBtn");
  btn.innerHTML = icon(isDark() ? "moon" : "sun", 20);
  btn.title = isDark() ? "Đang dùng giao diện tối — bấm để chuyển sang sáng" : "Đang dùng giao diện sáng — bấm để chuyển sang tối";
}

document.getElementById("themeBtn").addEventListener("click", () => {
  const dark = !isDark();
  if (dark) document.documentElement.dataset.theme = "dark";
  else delete document.documentElement.dataset.theme;
  try { localStorage.setItem(THEME_KEY, dark ? "dark" : "light"); } catch (_) { /* storage blocked */ }
  renderThemeButton();
  applyChartTheme();
  render();  // charts take their colours when created
});

// ------------------------------------------------------------------ user menu

function renderUserMenu() {
  const auth = getAuth();
  const box = document.getElementById("userMenu");
  const name = auth ? auth.user.username : "Khách";
  const items = auth
    ? `<div class="meta">Đã đăng nhập bằng JWT</div>
       <a href="#/lich-su" role="menuitem">${icon("history", 16)}Lịch sử của tôi</a>
       <button type="button" data-logout role="menuitem">${icon("log-out", 16)}Đăng xuất</button>`
    : `<div class="meta">Chưa đăng nhập</div>
       <a href="#/dang-nhap" role="menuitem">${icon("log-in", 16)}Đăng nhập / Đăng ký</a>`;
  box.innerHTML = `
    <button class="user-btn" type="button" aria-haspopup="true" aria-expanded="false">
      <span class="avatar">${auth ? esc(name.charAt(0).toUpperCase()) : icon("user-round", 18)}</span>
      <span>${esc(name)}</span>${icon("chevron-down", 16)}
    </button>
    <div class="menu" role="menu">${items}</div>`;
  const btn = box.querySelector(".user-btn");
  const menu = box.querySelector(".menu");
  btn.addEventListener("click", e => {
    e.stopPropagation();
    const open = menu.classList.toggle("open");
    btn.setAttribute("aria-expanded", String(open));
  });
  const logout = box.querySelector("[data-logout]");
  if (logout) logout.addEventListener("click", () => {
    clearAuth();
    toast("Đã đăng xuất");
  });
}
document.addEventListener("click", () => document.querySelectorAll(".menu.open").forEach(m => m.classList.remove("open")));

// ------------------------------------------------------------------ routing

async function render() {
  const name = currentRoute() || DEFAULT_ROUTE;
  state.route = name;
  const id = ++state.renderId;
  destroyAll();
  renderSidebar();

  const route = ROUTES[name];
  let page;
  try {
    page = (await import(route.module)).default;
  } catch (err) {
    view.innerHTML = `<div class="card"><div class="state error">${icon("circle-alert", 34)}<b>Lỗi tải trang</b><p>${esc(err.message)}</p></div></div>`;
    return;
  }
  if (id !== state.renderId) return;

  document.getElementById("pageIcon").innerHTML = icon(page.icon || route.icon, 44);
  document.getElementById("pageTitle").textContent = page.title;
  document.getElementById("pageSub").textContent = page.subtitle;
  document.title = `${page.title} · Chẩn đoán ung thư vú`;

  const ctx = {
    cls: state.cls,
    classInfo: state.classInfo,
    setClass,
    alive: () => id === state.renderId,
  };
  view.innerHTML = "";
  try {
    await page.render(view, ctx);
  } catch (err) {
    if (ctx.alive()) {
      view.innerHTML = `<div class="card"><div class="state error">${icon("circle-alert", 34)}<b>Có lỗi khi hiển thị trang</b><p>${esc(err.message)}</p></div></div>`;
    }
  }
}

async function loadClasses() {
  try {
    const data = await modelApi("/classes");
    data.classes.forEach(c => { state.classInfo[c.key] = c; });
  } catch (_) {
    /* each page shows its own error state */
  }
}

// Demo links (/?sample=malignant&auto=1, or the old /ui?...) open the diagnosis page.
if (!location.hash && /[?&]sample=/.test(location.search)) {
  history.replaceState(null, "", `${location.pathname}${location.search}#/chan-doan`);
}

window.addEventListener("hashchange", render);
onAuthChange(() => {
  renderUserMenu();
  render();
});
renderThemeButton();
renderUserMenu();
render();
loadClasses();
checkHealth();
