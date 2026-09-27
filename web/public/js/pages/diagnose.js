// SVM diagnosis page: load a held-out test sample (or type the 30 values), POST /predict and show the
// thresholded result, the cytology image of the predicted class and the true label when known.
// Links such as /?sample=malignant&auto=1 load a sample and predict at once (demo, screenshots).
import { dbApi, MODEL_API, modelApi, modelAsset } from "../api.js";
import { getAuth } from "../auth.js";
import { icon } from "../icons.js";
import { CLASS_VI, errorState, esc, num, toast } from "../ui.js";

const MEASURES = [
  ["radius", "Bán kính"], ["texture", "Kết cấu"], ["perimeter", "Chu vi"], ["area", "Diện tích"],
  ["smoothness", "Độ trơn"], ["compactness", "Độ đặc"], ["concavity", "Độ lõm"],
  ["concave points", "Số điểm lõm"], ["symmetry", "Độ đối xứng"], ["fractal dimension", "Chiều fractal"],
];
const GROUPS = [
  { key: "mean", title: "Trung bình", hint: "trung bình trên các nhân tế bào", name: m => `mean ${m}` },
  { key: "error", title: "Sai số chuẩn", hint: "độ biến thiên giữa các nhân", name: m => `${m} error` },
  { key: "worst", title: "Xấu nhất", hint: "trung bình 3 giá trị lớn nhất", name: m => `worst ${m}` },
];

function fields() {
  return GROUPS.map(g => `
    <fieldset>
      <legend>${g.title} <small>(${g.key} — ${g.hint})</small></legend>
      <div class="feature-fields">
        ${MEASURES.map(([m, vi]) => {
          const name = g.name(m);
          return `<label>${vi}<small>${name}</small>
            <input class="input" type="number" step="any" min="0" inputmode="decimal" name="${name}" required></label>`;
        }).join("")}
      </div>
    </fieldset>`).join("");
}

export default {
  title: "Chẩn đoán bằng SVM",
  subtitle: "Lấy một mẫu của tập kiểm tra hoặc nhập 30 đặc trưng — mô hình trả nhãn theo ngưỡng đã khoá",
  icon: "microscope",

  async render(view, ctx) {
    view.innerHTML = `
      <div class="grid diagnose-layout">
        <section class="card">
          <div class="card-head">
            <div><h2>30 đặc trưng tế bào</h2><p class="sub">Đo từ ảnh chọc hút kim nhỏ (FNA)</p></div>
            <p class="status-line"><span class="dot-status" id="dot"></span><span id="status">Đang kiểm tra dịch vụ…</span></p>
          </div>
          <div class="btn-row" style="margin-bottom:12px">
            <button class="btn ghost" type="button" data-sample="malignant">${icon("sparkles", 16)}Mẫu ác tính ngẫu nhiên</button>
            <button class="btn ghost" type="button" data-sample="benign">${icon("sparkles", 16)}Mẫu lành tính ngẫu nhiên</button>
            <button class="btn ghost small" type="button" id="clear">Xoá form</button>
          </div>
          <div class="notice info" id="sampleInfo" hidden style="margin-bottom:12px"></div>
          <form id="form" class="feature-groups" novalidate>
            ${fields()}
            <div class="btn-row">
              <button class="btn" type="submit" id="predictBtn">${icon("scan-eye", 16)}Dự đoán</button>
              <span class="sub" id="formHint">Cần đủ 30 giá trị số.</span>
            </div>
          </form>
        </section>
        <aside class="sticky-side">
          <section class="card" id="result" aria-live="polite">
            <div class="state">${icon("microscope", 34)}<b>Chưa có kết quả</b><p>Bấm “Mẫu ác tính ngẫu nhiên” hoặc “Mẫu lành tính ngẫu nhiên”, rồi “Dự đoán”.</p></div>
          </section>
          <section class="card">
            <div class="band-title">Mô hình đang chạy</div>
            <div class="kv" id="facts"><p class="sub">Đang tải /metadata…</p></div>
            <p class="caption"><a href="${MODEL_API}/docs" target="_blank" rel="noopener">Swagger</a> ·
              <a href="${MODEL_API}/metadata" target="_blank" rel="noopener">Metadata</a></p>
          </section>
        </aside>
      </div>`;

    const form = view.querySelector("#form");
    const box = view.querySelector("#result");
    const inputs = () => [...form.querySelectorAll("input")];
    let sample = null;   // {id, label} of the loaded test sample; cleared once a value is edited
    let last = null;     // last successful prediction, for "save to history"

    inputs().forEach(el => el.addEventListener("input", () => {
      el.classList.remove("invalid");
      if (sample) {
        sample = null;
        view.querySelector("#sampleInfo").textContent = "Đã sửa giá trị — không còn so sánh với nhãn thật của mẫu.";
      }
    }));

    const fill = values => inputs().forEach(el => { el.value = values[el.name] ?? ""; el.classList.remove("invalid"); });

    const loadSample = async label => {
      try {
        const data = await modelApi(`/samples?n=1&label=${label}`);
        const s = data.items[0];
        fill(s.features);
        sample = { id: s.id, label: s.label };
        const info = view.querySelector("#sampleInfo");
        info.hidden = false;
        info.innerHTML = `${icon("info", 18)}Mẫu <b>${esc(s.id)}</b> của tập kiểm tra · nhãn thật: <b>${CLASS_VI[s.label]}</b>`;
        return true;
      } catch (err) {
        toast(err.message);
        return false;
      }
    };

    const facts = async () => {
      try {
        const h = await modelApi("/health");
        view.querySelector("#dot").className = "dot-status ok";
        view.querySelector("#status").textContent = `Sẵn sàng · v${h.model_version}`;
        const m = await modelApi("/metadata");
        if (!ctx.alive()) return;
        const t = m.test_metrics;
        const rows = [
          ["microscope", "Mô hình", `SVM RBF · C = ${m.best_params.svc__C}, γ = ${m.best_params.svc__gamma}`],
          ["gauge", "Ngưỡng P(ác tính)", `${num(m.threshold_malignant, 4)} (sensitivity mục tiêu ≥ ${num(m.target_sensitivity, 2)})`],
          ["target", "Tập kiểm tra", `sensitivity ${num(t.sensitivity, 4)} · specificity ${num(t.specificity, 4)}`],
          ["activity", "ROC-AUC / PR-AUC (test)", `${num(t.roc_auc, 4)} / ${num(t.pr_auc, 4)}`],
        ];
        view.querySelector("#facts").innerHTML = rows.map(([ic, k, v]) =>
          `<div class="kv-row">${icon(ic, 22)}<div><div class="kv-label">${k}</div><div class="kv-value" style="font-size:13.5px">${esc(v)}</div></div></div>`).join("");
      } catch (err) {
        if (!ctx.alive()) return;
        view.querySelector("#dot").className = "dot-status bad";
        view.querySelector("#status").textContent = err.status === 503 ? "Mô hình chưa nạp được" : "Không kết nối được dịch vụ";
        view.querySelector("#facts").innerHTML = errorState(err.message);
      }
    };

    const showResult = (r, ms, payload) => {
      const info = ctx.classInfo[r.predicted_label];
      const pct = r.probability_malignant * 100;
      const op = r.probability_malignant >= r.threshold_malignant ? "≥" : "<";
      const truth = sample ? `<div class="compare-truth ${sample.label === r.predicted_label ? "match" : "mismatch"}">
          Nhãn thật của ${esc(sample.id)}: <b>${CLASS_VI[sample.label]}</b> —
          ${sample.label === r.predicted_label ? "mô hình dự đoán <b>đúng</b>." : "mô hình dự đoán <b>sai</b> ở mẫu này."}</div>` : "";
      box.innerHTML = `
        <div class="verdict ${r.predicted_label}">
          <div class="label">Kết quả dự đoán</div>
          <div class="value">${r.predicted_label_vi}</div>
          <div class="sub">${r.predicted_label} · lớp ${r.predicted_class}</div>
        </div>
        <div class="bar-label"><span>Ác tính ${num(pct, 1)}%</span><span>Lành tính ${num(100 - pct, 1)}%</span></div>
        <div class="prob-bar" role="img" aria-label="Xác suất ác tính ${num(pct, 1)} phần trăm">
          <div class="fill" style="width:${pct}%"></div>
          <div class="mark" style="left:calc(${r.threshold_malignant * 100}% - 1px)"><span>ngưỡng ${num(r.threshold_malignant, 4)}</span></div>
        </div>
        <p style="margin:0;font-size:13.5px">P(ác tính) = <b>${num(r.probability_malignant, 4)}</b> ${op} ngưỡng ${num(r.threshold_malignant, 4)} → <b>${r.predicted_label_vi}</b></p>
        ${truth}
        ${info ? `<img class="cell-photo" style="margin-top:12px" src="${esc(modelAsset(info.image_url))}" alt="${esc(info.alt_text)}">
          <p class="caption">Ảnh minh hoạ nhóm ${esc(info.label_vi.toLowerCase())} — Nguồn: ${esc(info.author)}, ${esc(info.license)},
          <a href="${esc(info.source_url)}" target="_blank" rel="noopener">${esc(info.source_url.replace("https://", ""))}</a></p>` : ""}
        <div class="btn-row" style="margin-top:10px">
          <button class="btn small" type="button" id="save">${icon("save", 14)}Lưu vào lịch sử</button>
          <span class="sub">Phản hồi ${ms} ms · v${esc(r.model_version)}</span>
        </div>`;
      last = { r, ms, payload, sample: sample && { ...sample } };
      box.querySelector("#save").addEventListener("click", async e => {
        if (!getAuth()) { toast("Hãy đăng nhập để lưu lịch sử"); location.hash = "#/dang-nhap"; return; }
        e.currentTarget.disabled = true;
        try {
          await dbApi("/predictions", {
            method: "POST", auth: true,
            body: { items: [{
              model: "svm_rbf", input: last.payload, predicted_label: last.r.predicted_label,
              probability_malignant: last.r.probability_malignant, threshold: last.r.threshold_malignant,
              actual_label: last.sample ? last.sample.label : null, sample_id: last.sample ? last.sample.id : null,
              runtime_ms: last.ms,
            }] },
          });
          toast("Đã lưu dự đoán vào lịch sử");
        } catch (err) {
          toast(err.message);
          e.currentTarget.disabled = false;
        }
      });
    };

    const predict = async event => {
      if (event) event.preventDefault();
      const values = {};
      const bad = [];
      inputs().forEach(el => {
        const v = el.value.trim() === "" ? NaN : Number(el.value);
        if (!Number.isFinite(v)) { bad.push(el.name); el.classList.add("invalid"); }
        values[el.name] = v;
      });
      if (bad.length) { view.querySelector("#formHint").textContent = `Còn ${bad.length} ô trống hoặc không phải số.`; return; }
      view.querySelector("#formHint").textContent = "Cần đủ 30 giá trị số.";
      const btn = view.querySelector("#predictBtn");
      btn.disabled = true;
      const started = performance.now();
      try {
        const r = await modelApi("/predict", { method: "POST", body: values });
        if (!ctx.alive()) return;
        showResult(r, Math.round(performance.now() - started), values);
        if (window.matchMedia("(max-width: 1100px)").matches) box.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (err) {
        if (!ctx.alive()) return;
        const detail = err.body && err.body.detail;
        const list = detail && detail.out_of_range
          ? detail.out_of_range.map(f => `${f.feature} = ${f.value} (tối đa ${num(f.upper_bound, 2)})`)
          : [];
        box.innerHTML = `${errorState(err.message)}${list.length ? `<ul class="bullets">${list.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`;
      } finally {
        btn.disabled = false;
      }
    };

    form.addEventListener("submit", predict);
    view.querySelectorAll("[data-sample]").forEach(b => b.addEventListener("click", () => loadSample(b.dataset.sample)));
    view.querySelector("#clear").addEventListener("click", () => {
      fill({});
      sample = null;
      view.querySelector("#sampleInfo").hidden = true;
    });
    facts();

    const q = new URLSearchParams(location.search);
    const wanted = q.get("sample");
    if ((wanted === "malignant" || wanted === "benign") && await loadSample(wanted) && q.get("auto") === "1") predict();
  },
};
