// Demo UI: fetch a test sample, edit the 30 inputs, POST /predict and show the thresholded result.
"use strict";

const MEASURES = [
  ["radius", "Bán kính"],
  ["texture", "Kết cấu (độ lệch mức xám)"],
  ["perimeter", "Chu vi"],
  ["area", "Diện tích"],
  ["smoothness", "Độ trơn"],
  ["compactness", "Độ đặc"],
  ["concavity", "Độ lõm"],
  ["concave points", "Số điểm lõm"],
  ["symmetry", "Độ đối xứng"],
  ["fractal dimension", "Chiều fractal"],
];
const GROUPS = [
  { key: "mean", title: "Trung bình", hint: "giá trị trung bình trên các nhân tế bào", name: m => `mean ${m}` },
  { key: "error", title: "Sai số chuẩn", hint: "độ biến thiên giữa các nhân", name: m => `${m} error` },
  { key: "worst", title: "Xấu nhất", hint: "trung bình 3 giá trị lớn nhất", name: m => `worst ${m}` },
];
const LABEL_VI = { malignant: "Ác tính", benign: "Lành tính" };

const $ = sel => document.querySelector(sel);
const fmt = (v, d = 4) => Number(v).toLocaleString("vi-VN", { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let metadata = null;
let currentSample = null;   // {id, label} of the loaded test sample, cleared once the user edits a value

function buildForm() {
  $("#groups").innerHTML = GROUPS.map(g => `
    <fieldset>
      <legend>${g.title} <small>(${g.key} — ${g.hint})</small></legend>
      <div class="fields">
        ${MEASURES.map(([m, vi]) => {
          const name = g.name(m);
          return `<label class="field"><span>${vi}</span><small>${name}</small>
            <input type="number" step="any" min="0" inputmode="decimal" name="${name}" required></label>`;
        }).join("")}
      </div>
    </fieldset>`).join("");
  document.querySelectorAll("#groups input").forEach(input => {
    input.addEventListener("input", () => {
      input.classList.remove("invalid");
      if (currentSample) {
        currentSample = null;
        $("#sampleInfo").textContent = "Đã sửa giá trị — không còn so sánh với nhãn thật của mẫu.";
      }
    });
  });
}

function fill(features) {
  Object.entries(features).forEach(([name, value]) => {
    const input = document.querySelector(`input[name="${CSS.escape(name)}"]`);
    if (input) { input.value = value; input.classList.remove("invalid"); }
  });
}

function readForm() {
  const values = {};
  const bad = [];
  document.querySelectorAll("#groups input").forEach(input => {
    const v = input.value.trim() === "" ? NaN : Number(input.value);
    if (!Number.isFinite(v)) { bad.push(input.name); input.classList.add("invalid"); }
    values[input.name] = v;
  });
  return { values, bad };
}

async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  let body = null;
  try { body = await res.json(); } catch (_) { /* not JSON */ }
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

async function loadSample(label) {
  const buttons = document.querySelectorAll("[data-sample]");
  buttons.forEach(b => { b.disabled = true; });
  try {
    const data = await api(`/samples?n=1&label=${label}`);
    const s = data.items[0];
    fill(s.features);
    currentSample = { id: s.id, label: s.label };
    const info = $("#sampleInfo");
    info.hidden = false;
    info.innerHTML = `Đang dùng mẫu <b>${esc(s.id)}</b> của tập kiểm tra · nhãn thật: <b>${LABEL_VI[s.label]}</b>. Bấm “Dự đoán”.`;
  } catch (err) {
    showError(err);
  } finally {
    buttons.forEach(b => { b.disabled = false; });
  }
}

function showError(err) {
  let html = `<b>Không dự đoán được</b> (${esc(err.message)}).`;
  const body = err.body || {};
  if (err.status === 422) {
    const detail = body.detail;
    if (detail && detail.out_of_range) {
      html += `<p>${esc(detail.message)}:</p><ul>${detail.out_of_range.map(f =>
        `<li>${esc(f.feature)} = ${esc(f.value)} (tối đa ${fmt(f.upper_bound, 2)})</li>`).join("")}</ul>`;
    } else if (Array.isArray(detail)) {
      html += `<ul>${detail.slice(0, 8).map(d => `<li>${esc((d.loc || []).slice(-1)[0])}: ${esc(d.msg)}</li>`).join("")}</ul>`;
    }
  } else if (err.status === 503) {
    html += "<p>Dịch vụ chưa nạp được mô hình — xem /health.</p>";
  } else if (!err.status) {
    html += "<p>Không kết nối được máy chủ. Trên gói Render Free, lần gọi đầu có thể mất 30–60 giây.</p>";
  }
  $("#result").innerHTML = `<div class="error-box">${html}</div>`;
}

function showResult(r, ms) {
  const label = r.predicted_label;
  const pct = r.probability_malignant * 100;
  const thr = r.threshold_malignant * 100;
  const op = r.probability_malignant >= r.threshold_malignant ? "≥" : "<";
  let compare = "";
  if (currentSample) {
    const ok = currentSample.label === label;
    compare = `<div class="compare ${ok ? "match" : "mismatch"}">Nhãn thật của ${esc(currentSample.id)}: <b>${LABEL_VI[currentSample.label]}</b>
      — ${ok ? "mô hình dự đoán <b>đúng</b>." : "mô hình dự đoán <b>sai</b> ở mẫu này."}</div>`;
  }
  $("#result").innerHTML = `
    <div class="verdict ${label}">
      <div class="label">Kết quả dự đoán</div>
      <div class="value">${LABEL_VI[label]}</div>
      <div class="en">${label} · lớp ${r.predicted_class}</div>
    </div>
    <div class="bar-wrap">
      <div class="bar-labels"><span>Ác tính ${fmt(pct, 1)}%</span><span>Lành tính ${fmt(100 - pct, 1)}%</span></div>
      <div class="bar" role="img" aria-label="Xác suất ác tính ${fmt(pct, 1)} phần trăm, ngưỡng ${fmt(thr, 2)} phần trăm">
        <div class="fill" style="width:${pct}%"></div>
        <div class="mark" style="left:calc(${thr}% - 1px)"><span>ngưỡng ${fmt(r.threshold_malignant, 4)}</span></div>
      </div>
    </div>
    <p class="rule">P(ác tính) = <b>${fmt(r.probability_malignant, 4)}</b> ${op} ngưỡng ${fmt(r.threshold_malignant, 4)}
      → <b>${LABEL_VI[label]}</b></p>
    ${compare}
    <p class="meta-line">Mô hình v${esc(r.model_version)} · phản hồi ${ms} ms · ${esc(r.warning)}</p>`;
}

async function predict(event) {
  event.preventDefault();
  const { values, bad } = readForm();
  if (bad.length) {
    $("#formHint").textContent = `Còn ${bad.length} ô trống hoặc không phải số.`;
    return;
  }
  $("#formHint").textContent = "Cần đủ 30 giá trị số.";
  const btn = $("#predictBtn");
  btn.disabled = true;
  btn.textContent = "Đang dự đoán…";
  const started = performance.now();
  try {
    const r = await api("/predict", { method: "POST", body: JSON.stringify(values) });
    showResult(r, Math.round(performance.now() - started));
    // On a single-column layout the result sits below the form: bring it into view.
    if (window.matchMedia("(max-width: 900px)").matches) $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showError(err);
  } finally {
    btn.disabled = false;
    btn.textContent = "Dự đoán";
  }
}

async function loadStatus() {
  const pill = $("#health");
  try {
    const h = await api("/health");
    pill.className = "health ok";
    $("#healthText").textContent = `Dịch vụ sẵn sàng · v${h.model_version}`;
    metadata = await api("/metadata");
    const m = metadata.test_metrics;
    const rows = [
      ["Phiên bản", `${metadata.model_name} v${metadata.model_version}`],
      ["Tham số tốt nhất", `C = ${metadata.best_params.svc__C}, γ = ${metadata.best_params.svc__gamma}`],
      ["Hiệu chỉnh xác suất", metadata.calibration],
      ["Ngưỡng P(ác tính)", fmt(metadata.threshold_malignant, 4)],
      ["Mục tiêu sensitivity", fmt(metadata.target_sensitivity, 2)],
      ["Sensitivity (test)", fmt(m.sensitivity, 4)],
      ["Specificity (test)", fmt(m.specificity, 4)],
      ["ROC-AUC (test)", fmt(m.roc_auc, 4)],
      ["Huấn luyện", `${metadata.n_train} mẫu · test ${metadata.n_test} mẫu`],
    ];
    $("#facts").innerHTML = rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("");
  } catch (err) {
    pill.className = "health bad";
    $("#healthText").textContent = err.status === 503 ? "Mô hình chưa nạp được" : "Không kết nối được dịch vụ";
    $("#facts").innerHTML = `<div><dt>Trạng thái</dt><dd>Không tải được metadata</dd></div>`;
  }
}

buildForm();
document.querySelectorAll("[data-sample]").forEach(b => b.addEventListener("click", () => loadSample(b.dataset.sample)));
$("#clear").addEventListener("click", () => {
  document.querySelectorAll("#groups input").forEach(i => { i.value = ""; i.classList.remove("invalid"); });
  currentSample = null;
  $("#sampleInfo").hidden = true;
});
$("#form").addEventListener("submit", predict);
loadStatus();

// Demo links and screenshots: /ui?sample=malignant&auto=1 loads a test sample and predicts at once.
(async () => {
  const q = new URLSearchParams(location.search);
  const label = q.get("sample");
  if (label !== "malignant" && label !== "benign") return;
  await loadSample(label);
  if (q.get("auto") === "1" && currentSample) $("#form").requestSubmit();
})();
