// Shell of the single-page app: hash router, sidebar, header pill and user menu.
import { modelApi, modelAsset } from "./api.js";
import { clearAuth, getAuth, onAuthChange } from "./auth.js";
import { destroyAll } from "./charts.js";
import { icon } from "./icons.js";
import { CLASS_KEYS, CLASS_VI, esc, toast } from "./ui.js";

const ROUTES = {
  "tong-quan": { module: "./pages/overview.js", label: "Tổng quan", icon: "layout-dashboard", group: "main" },
  "chan-doan": { module: "./pages/diagnose.js", label: "Chẩn đoán SVM", icon: "microscope", group: "main" },
  "so-sanh": { module: "./pages/compare.js", label: "So sánh mô hình", icon: "chart-column", group: "main" },
  "lich-su": { module: "./pages/history.js", label: "Lịch sử", icon: "history", group: "main" },
  "phan-tich": { module: "./pages/analysis.js", label: "Phân tích nâng cao", icon: "chart-scatter", group: "highlight" },
  "dang-nhap": { module: "./pages/login.js", label: "Đăng nhập", icon: "log-in", group: "hidden" },
};
const DEFAULT_ROUTE = "tong-quan";
const CLASS_KEY = "bc-class";

const view = document.getElementById("view");
const state = {
  cls: readClass(),
  classInfo: {},   // from GET /classes on the model API
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

const LINEART = `
<svg class="lineart" viewBox="0 0 180 90" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" aria-hidden="true">
  <circle cx="42" cy="46" r="17"/><circle cx="42" cy="46" r="6"/>
  <circle cx="92" cy="38" r="13"/><circle cx="93" cy="37" r="4.5"/>
  <circle cx="136" cy="52" r="19"/><path d="M129 47c3-4 9-5 13-2 4 3 4 9 0 12-4 3-10 2-13-2"/>
  <circle cx="70" cy="74" r="9"/><circle cx="70" cy="74" r="3"/>
  <circle cx="160" cy="22" r="7"/><circle cx="18" cy="18" r="6"/>
</svg>`;

function navItem(name) {
  const r = ROUTES[name];
  const active = state.route === name ? " active" : "";
  return `<a class="nav-item${active}" href="#/${name}">${icon(r.icon, 18)}<span>${esc(r.label)}</span></a>`;
}

function renderSidebar() {
  const classes = CLASS_KEYS.map(key => {
    const info = state.classInfo[key];
    const active = state.cls === key && state.route === "tong-quan" ? " active" : "";
    const thumb = info
      ? `<img class="thumb" src="${esc(modelAsset(info.image_url))}" alt="" title="Ảnh: ${esc(info.author)} (${esc(info.license)})" loading="lazy">`
      : `<span class="thumb"></span>`;
    return `<button class="nav-item${active}" type="button" data-class="${key}">${thumb}<span>${CLASS_VI[key]}</span></button>`;
  }).join("");

  document.getElementById("sidebar").innerHTML = `
    <div class="side-group">
      <div class="side-title">Trang</div>
      ${Object.keys(ROUTES).filter(n => ROUTES[n].group === "main").map(navItem).join("")}
    </div>
    <div class="side-group">
      <div class="side-title"><span class="star">${icon("sparkles", 14)}</span>Điểm nổi bật</div>
      ${Object.keys(ROUTES).filter(n => ROUTES[n].group === "highlight").map(navItem).join("")}
    </div>
    <div class="side-group">
      <div class="side-title">Loại khối u</div>
      ${classes}
      <p class="side-credit">Ảnh tế bào học: Wikimedia Commons — nguồn đầy đủ dưới ảnh lớn và trong CREDITS.md.</p>
    </div>
    <div class="side-foot">
      ${LINEART}
      <p class="quote">Phát hiện sớm là chìa khoá của điều trị ♥</p>
      <div class="student">Sinh viên thực hiện<b>La Thị Mỹ Hoà</b>Lớp 24CKDL · Học máy nâng cao</div>
    </div>`;

  document.querySelectorAll("[data-class]").forEach(btn => {
    btn.addEventListener("click", () => setClass(btn.dataset.class));
  });
}

function setClass(key) {
  state.cls = key;
  try { localStorage.setItem(CLASS_KEY, key); } catch (_) { /* storage blocked */ }
  renderPill();
  if (state.route === "tong-quan") render();
  else location.hash = "#/tong-quan";
}

function renderPill() {
  document.getElementById("viewingPill").innerHTML =
    `${icon("microscope", 16)}<span>Đang xem: <b>${CLASS_VI[state.cls]}</b></span>`;
}

// ------------------------------------------------------------------ user menu

function renderUserMenu() {
  const auth = getAuth();
  const box = document.getElementById("userMenu");
  if (!auth) {
    box.innerHTML = `<a class="btn ghost small" href="#/dang-nhap">${icon("log-in", 16)}Đăng nhập</a>`;
    return;
  }
  const name = auth.user.username;
  box.innerHTML = `
    <button class="user-btn" type="button" aria-haspopup="true" aria-expanded="false">
      <span class="avatar">${esc(name.charAt(0).toUpperCase())}</span><span>${esc(name)}</span>
    </button>
    <div class="menu" role="menu">
      <div class="meta">Đã đăng nhập bằng JWT</div>
      <a href="#/lich-su" role="menuitem">${icon("history", 16)}Lịch sử của tôi</a>
      <button type="button" data-logout role="menuitem">${icon("log-out", 16)}Đăng xuất</button>
    </div>`;
  const btn = box.querySelector(".user-btn");
  const menu = box.querySelector(".menu");
  btn.addEventListener("click", e => {
    e.stopPropagation();
    const open = menu.classList.toggle("open");
    btn.setAttribute("aria-expanded", String(open));
  });
  box.querySelector("[data-logout]").addEventListener("click", () => {
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
  renderPill();

  const route = ROUTES[name];
  let page;
  try {
    page = (await import(route.module)).default;
  } catch (err) {
    view.innerHTML = `<div class="card"><div class="state error">${icon("circle-alert", 34)}<b>Lỗi tải trang</b><p>${esc(err.message)}</p></div></div>`;
    return;
  }
  if (id !== state.renderId) return;

  document.getElementById("pageIcon").innerHTML = icon(page.icon || route.icon, 28);
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
    renderSidebar();
  } catch (_) {
    /* thumbnails stay empty; each page shows its own error state */
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
renderUserMenu();
render();
loadClasses();
