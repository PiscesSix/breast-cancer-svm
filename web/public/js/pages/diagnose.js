// SVM diagnosis page: load a held-out test sample (or type the 30 values), POST /predict once, then
// label the result with the decision threshold chosen on the slider. Moving the slider re-labels the
// result, recolours the card and the donut and recomputes the test-set metrics in the browser from
// GET /analysis/test-scores — it never calls /predict again. The default threshold is the one locked at
// training time (out-of-fold CV probabilities, sensitivity target); the slider value is shared with the
// analysis page. Links such as /?sample=malignant&auto=1 load a sample and predict at once (demo, screenshots).
import { dbApi, MODEL_API, modelApi, modelAsset } from "../api.js";
import { getAuth } from "../auth.js";
import { chart } from "../charts.js";
import { icon } from "../icons.js";
import { confusion, currentThreshold, labelAt, saveThreshold, testScores } from "../threshold.js";
import { CLASS_COLORS, CLASS_VI, duration, errorState, esc, num, toast } from "../ui.js";

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
// Slider range from the brief; widened if the locked or the shared threshold lies outside it.
const RANGE = [0.3, 0.7];
const CLASS_EN = { malignant: "Malignant", benign: "Benign" };
const CALIBRATION = {
  calibrated_sigmoid_single: "CalibratedClassifierCV (sigmoid)",
  calibrated_sigmoid: "CalibratedClassifierCV (sigmoid, ensemble)",
  calibrated_isotonic: "CalibratedClassifierCV (isotonic)",
  svc_probability: "SVC(probability=True)",
};
const pct = v => `${num(v * 100, 2)}%`;

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
  subtitle: "Lấy một mẫu của tập kiểm tra hoặc nhập 30 đặc trưng — kéo ngưỡng để xem nhãn và hiệu suất thay đổi",
  icon: "microscope",

  async render(view, ctx) {
    view.innerHTML = `
      <div class="grid diagnose-layout">
        <div class="stack">
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
          <div class="grid cols-2">
            <section class="card">
              <div class="card-head"><h2 class="h-icon">${icon("braces", 18)}Thông tin mô hình</h2></div>
              <div id="facts"><p class="sub">Đang tải /metadata…</p></div>
              <p class="caption"><a href="${MODEL_API}/docs" target="_blank" rel="noopener">Swagger</a> ·
                <a href="${MODEL_API}/metadata" target="_blank" rel="noopener">Metadata</a></p>
            </section>
            <section class="card">
              <div class="card-head"><h2 class="h-icon">${icon("chart-pie", 18)}Phân bố xác suất dự đoán</h2></div>
              <div id="donut"><div class="state">${icon("chart-pie", 30)}<p>Chưa có dự đoán.</p></div></div>
            </section>
          </div>
        </div>

        <aside class="stack">
          <section class="card">
            <div class="card-head">
              <div><h2 class="h-icon">${icon("gauge", 18)}Ngưỡng dự đoán (Threshold)</h2>
                <p class="sub">Điều chỉnh ngưỡng để cân bằng giữa sensitivity và specificity.</p></div>
              <span class="t-pill" id="tPill">—</span>
            </div>
            <div id="tBody"><div class="skeleton sk-line" style="width:90%"></div></div>
          </section>
          <section class="card" id="result" aria-live="polite">
            <div class="card-head"><h2 class="h-icon">${icon("scan-eye", 18)}Kết quả dự đoán</h2></div>
            <div class="state">${icon("microscope", 34)}<b>Chưa có kết quả</b><p>Bấm “Mẫu ác tính ngẫu nhiên” hoặc “Mẫu lành tính ngẫu nhiên”, rồi “Dự đoán”.</p></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2 class="h-icon">${icon("activity", 18)}Hiệu suất mô hình <small>(trên tập test)</small></h2>
              <p class="sub" id="perfSub"></p></div></div>
            <div id="perf"><div class="skeleton sk-block"></div></div>
          </section>
          <section class="card">
            <div class="card-head"><h2 class="h-icon">${icon("timer", 18)}Thời gian dự đoán</h2></div>
            <div id="timing"><p class="sub">Chưa có dự đoán.</p></div>
          </section>
        </aside>
      </div>`;

    const form = view.querySelector("#form");
    const box = view.querySelector("#result");
    const inputs = () => [...form.querySelectorAll("input")];
    let sample = null;   // {id, label} of the loaded test sample; cleared once a value is edited
    let last = null;     // last successful prediction: {r, ms, payload, sample}
    let shownLabel = null;
    let scores = null;   // test-split scores of the deployed model
    let t = null;        // threshold currently on the slider
    let donut = null;

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

    // ---------------------------------------------------------------- model facts

    const facts = async () => {
      try {
        const h = await modelApi("/health");
        view.querySelector("#dot").className = "dot-status ok";
        view.querySelector("#status").textContent = `Sẵn sàng · v${h.model_version}`;
        const m = await modelApi("/metadata");
        if (!ctx.alive()) return;
        const rows = [
          ["Thuật toán", "SVM (kernel RBF)"],
          ["C", String(m.best_params.svc__C)],
          ["Gamma (γ)", String(m.best_params.svc__gamma)],
          ["Pipeline", "StandardScaler + SVC"],
          ["Xác suất", CALIBRATION[m.calibration] || m.calibration],
          ["Ngưỡng mặc định", `${num(m.threshold_malignant, 4)} (sensitivity ≥ ${num(m.target_sensitivity, 2)})`],
          ["ROC-AUC (test)", num(m.test_metrics.roc_auc, 4)],
          ["Dữ liệu", `${m.n_train} mẫu train · ${m.n_test} mẫu test`],
        ];
        view.querySelector("#facts").innerHTML = `<table class="data info-table"><tbody>${rows.map(([k, v]) =>
          `<tr><th scope="row">${k}</th><td>${esc(v)}</td></tr>`).join("")}</tbody></table>`;
      } catch (err) {
        if (!ctx.alive()) return;
        view.querySelector("#dot").className = "dot-status bad";
        view.querySelector("#status").textContent = err.status === 503 ? "Mô hình chưa nạp được" : "Không kết nối được dịch vụ";
        view.querySelector("#facts").innerHTML = errorState(err.message);
      }
    };

    // ---------------------------------------------------------------- threshold slider + test metrics

    const renderPerf = () => {
      const c = confusion(scores.items, t);
      const target = scores.target_sensitivity;
      const reached = c.sens >= target;
      view.querySelector("#perfSub").textContent =
        `${scores.items.length} mẫu · ${c.tp} TP · ${c.fn} FN · ${c.fp} FP · ${c.tn} TN tại ngưỡng ${num(t, 4)}`;
      view.querySelector("#perf").innerHTML = `
        <div class="metric-tiles">
          <div class="metric-tile sens"><span>Sensitivity (Recall)</span><b>${pct(c.sens)}</b></div>
          <div class="metric-tile spec"><span>Specificity</span><b>${pct(c.spec)}</b></div>
          <div class="metric-tile prec"><span>Precision</span><b>${pct(c.prec)}</b></div>
          <div class="metric-tile f1"><span>F1-score</span><b>${pct(c.f1)}</b></div>
        </div>
        <div class="target-row">
          ${icon("target", 20)}
          <div><b>Mục tiêu</b><code>Sensitivity ≥ ${num(target, 2)}</code></div>
          <span class="badge ${reached ? "fast" : "slow"}">${icon(reached ? "circle-check" : "triangle-alert", 12)}${reached ? "Đạt được" : "Chưa đạt"}</span>
        </div>`;
    };

    const renderDonut = () => {
      if (!last) return;
      const r = last.r;
      const label = labelAt(r.probability_malignant, t);
      const p = { malignant: r.probability_malignant, benign: r.probability_benign };
      const host = view.querySelector("#donut");
      if (!donut) {
        host.innerHTML = `
          <div class="donut-wrap compact">
            <div class="donut-box"><canvas id="donutCanvas" role="img" aria-label="Xác suất lành tính và ác tính của mẫu vừa dự đoán"></canvas>
              <div class="donut-center"><div><b id="donutPct"></b><span id="donutLabel"></span></div></div></div>
            <ul class="legend" id="donutLegend"></ul>
          </div>`;
        donut = chart(host.querySelector("#donutCanvas"), {
          type: "doughnut",
          data: { labels: [CLASS_VI.benign, CLASS_VI.malignant],
            datasets: [{ data: [p.benign, p.malignant], backgroundColor: [CLASS_COLORS.benign, CLASS_COLORS.malignant], borderWidth: 2, borderColor: "#fff" }] },
          options: { cutout: "68%", plugins: { legend: { display: false },
            tooltip: { callbacks: { label: c => ` ${c.label}: ${num(c.parsed, 4)}` } } } },
        });
      } else {
        donut.data.datasets[0].data = [p.benign, p.malignant];
        donut.update("none");
      }
      host.querySelector("#donutPct").textContent = pct(p[label]);
      host.querySelector("#donutPct").style.color = CLASS_COLORS[label];
      host.querySelector("#donutLabel").textContent = CLASS_VI[label].toLowerCase();
      host.querySelector("#donutLegend").innerHTML = ["benign", "malignant"].map(k => `
        <li><span class="dot" style="background:${CLASS_COLORS[k]}"></span><span>${CLASS_VI[k]}</span><b>${num(p[k], 4)}</b></li>`).join("");
    };

    const ruleText = r => {
      const op = r.probability_malignant >= t ? "≥" : "<";
      return `P(ác tính) = <b>${num(r.probability_malignant, 4)}</b> ${op} ngưỡng ${num(t, 4)} → <b>${CLASS_VI[labelAt(r.probability_malignant, t)]}</b>`;
    };

    const renderResult = () => {
      const { r, ms, sample: s } = last;
      const label = labelAt(r.probability_malignant, t);
      shownLabel = label;
      const info = ctx.classInfo[label];
      const truth = s ? `<div class="compare-truth ${s.label === label ? "match" : "mismatch"}">
          Nhãn thật của ${esc(s.id)}: <b>${CLASS_VI[s.label]}</b> —
          ${s.label === label ? "mô hình dự đoán <b>đúng</b>." : "mô hình dự đoán <b>sai</b> ở mẫu này."}</div>` : "";
      const bar = (k, p) => `
        <div class="bar-label"><span>Xác suất ${CLASS_VI[k].toLowerCase()}</span><span style="color:${CLASS_COLORS[k]}">${num(p, 4)}</span></div>
        <div class="track"><div class="fill" style="width:${p * 100}%;background:${CLASS_COLORS[k]}"></div></div>`;
      box.innerHTML = `
        <div class="card-head"><h2 class="h-icon">${icon("scan-eye", 18)}Kết quả dự đoán</h2></div>
        <div class="result-split">
          <div class="verdict ${label}">
            ${icon(label === "benign" ? "circle-check" : "triangle-alert", 30)}
            <div><div class="value">${CLASS_VI[label]}</div><div class="sub">(${CLASS_EN[label]})</div></div>
          </div>
          <div class="prob-rows">${bar("benign", r.probability_benign)}${bar("malignant", r.probability_malignant)}</div>
        </div>
        <p style="margin:12px 0 0;font-size:13.5px" id="rule">${ruleText(r)}</p>
        ${truth}
        ${info ? `<img class="cell-photo" style="margin-top:12px" src="${esc(modelAsset(info.image_url))}" alt="${esc(info.alt_text)}">
          <p class="caption">Ảnh minh hoạ nhóm ${esc(info.label_vi.toLowerCase())} — Nguồn: ${esc(info.author)}, ${esc(info.license)},
          <a href="${esc(info.source_url)}" target="_blank" rel="noopener">${esc(info.source_url.replace("https://", ""))}</a></p>` : ""}
        <div class="btn-row" style="margin-top:10px">
          <button class="btn small" type="button" id="save">${icon("save", 14)}Lưu vào lịch sử</button>
          <span class="sub">Phản hồi ${ms} ms · v${esc(r.model_version)}</span>
        </div>`;
      box.querySelector("#save").addEventListener("click", async e => {
        if (!getAuth()) { toast("Hãy đăng nhập để lưu lịch sử"); location.hash = "#/dang-nhap"; return; }
        e.currentTarget.disabled = true;
        // The saved label and threshold are the ones on screen (slider value), so they always agree.
        const saved = labelAt(last.r.probability_malignant, t);
        try {
          await dbApi("/predictions", {
            method: "POST", auth: true,
            body: { items: [{
              model: "svm_rbf", input: last.payload, predicted_label: saved,
              probability_malignant: last.r.probability_malignant, threshold: Number(t.toFixed(4)),
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

    // Called on every slider move: everything is recomputed here, no request is sent.
    const applyThreshold = value => {
      t = value;
      saveThreshold(t, scores.threshold);
      view.querySelector("#tPill").textContent = num(t, 4);
      const reset = view.querySelector("#tReset");
      reset.disabled = Math.abs(t - scores.threshold) < 1e-9;
      renderPerf();
      if (last) {
        if (labelAt(last.r.probability_malignant, t) !== shownLabel) renderResult();
        else box.querySelector("#rule").innerHTML = ruleText(last.r);
        renderDonut();
      }
    };

    const setupThreshold = async () => {
      try {
        scores = await testScores();
      } catch (err) {
        if (!ctx.alive()) return;
        view.querySelector("#tBody").innerHTML = errorState(err.message);
        view.querySelector("#perf").innerHTML = errorState(err.message);
        return;
      }
      if (!ctx.alive()) return;
      const locked = scores.threshold;
      t = currentThreshold(locked);
      const lo = Math.min(RANGE[0], locked, t);
      const hi = Math.max(RANGE[1], locked, t);
      view.querySelector("#tBody").innerHTML = `
        <input type="range" id="t" min="${lo}" max="${hi}" step="0.0001" value="${t}" aria-label="Ngưỡng trên P(ác tính)">
        <div class="range-ends"><span>${num(lo, 2)}</span><span>${num(hi, 2)}</span></div>
        <div class="notice info" style="margin-top:10px">${icon("info", 18)}<span>Ngưỡng mặc định <b>${num(locked, 4)}</b> được chọn
          dựa trên xác suất out-of-fold từ quá trình cross-validation (sensitivity ≥ ${num(scores.target_sensitivity, 2)}).
          Nhãn = Ác tính khi P(ác tính) ≥ ngưỡng.</span></div>
        <div class="btn-row" style="margin-top:10px">
          <button class="btn ghost small" type="button" id="tReset">${icon("refresh-cw", 14)}Về ngưỡng mặc định</button>
        </div>`;
      const slider = view.querySelector("#t");
      slider.addEventListener("input", () => applyThreshold(parseFloat(slider.value)));
      view.querySelector("#tReset").addEventListener("click", () => {
        slider.value = locked;
        applyThreshold(locked);
      });
      applyThreshold(t);
    };

    // ---------------------------------------------------------------- predict

    const showPrediction = (r, ms, payload) => {
      last = { r, ms, payload, sample: sample && { ...sample } };
      if (t === null) t = r.threshold_malignant;  // test scores not loaded: fall back to the server's threshold
      renderResult();
      renderDonut();
      view.querySelector("#timing").innerHTML = `
        <div class="timing"><b>~ ${duration(r.inference_ms)}</b><span>(trên 1 mẫu, predict_proba phía server)</span></div>
        <p class="sub">Phản hồi toàn trình (mạng + API): ${ms} ms.</p>
        <p class="caption">Thời gian có thể thay đổi tùy theo môi trường triển khai và cấu hình phần cứng.</p>`;
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
        showPrediction(r, Math.round(performance.now() - started), values);
        if (window.matchMedia("(max-width: 1100px)").matches) box.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (err) {
        if (!ctx.alive()) return;
        // Forget the previous prediction so the slider does not re-label a result that is no longer shown.
        last = null;
        shownLabel = null;
        donut = null;
        view.querySelector("#donut").innerHTML = `<div class="state">${icon("chart-pie", 30)}<p>Chưa có dự đoán.</p></div>`;
        view.querySelector("#timing").innerHTML = `<p class="sub">Chưa có dự đoán.</p>`;
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
    await setupThreshold();
    if (!ctx.alive()) return;

    const q = new URLSearchParams(location.search);
    const wanted = q.get("sample");
    if ((wanted === "malignant" || wanted === "benign") && await loadSample(wanted) && q.get("auto") === "1") predict();
  },
};
