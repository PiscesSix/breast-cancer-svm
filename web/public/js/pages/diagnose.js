// SVM diagnosis page, laid out after docs/mockup/bt2-chan-doan-svm-threshold.png: the 30 inputs on the left
// (mean / se / worst columns) with the model facts and the probability donut below; on the right the
// threshold slider, the result with the test-set metrics, and the inference time.
// POST /predict runs once per prediction; moving the slider re-labels the result, recolours the card and
// the donut and recomputes the test-set metrics in the browser from GET /analysis/test-scores — it never
// calls /predict again. The default threshold is the one locked at training time (out-of-fold CV
// probabilities, sensitivity target); the slider value is shared with the analysis page.
// The form opens pre-filled with the default record from GET /samples/default (WDBC ID 842302) and its
// prediction; "Đặt lại" brings that record back. Links such as /?sample=malignant&auto=1 load a random
// test sample instead and predict at once (demo, screenshots).
import { dbApi, modelApi } from "../api.js?v=20261005";
import { getAuth } from "../auth.js?v=20261005";
import { chart, cssVar } from "../charts.js?v=20261005";
import { icon } from "../icons.js?v=20261005";
import { confusion, currentThreshold, labelAt, saveThreshold, testScores } from "../threshold.js?v=20261005";
import { CLASS_COLORS, CLASS_VI, errorState, esc, toast } from "../ui.js?v=20261005";

// Kaggle / UCI column stems (as in the mockup) and the Vietnamese name shown as a tooltip.
const MEASURES = [
  ["radius", "radius", "Bán kính"], ["texture", "texture", "Kết cấu"], ["perimeter", "perimeter", "Chu vi"],
  ["area", "area", "Diện tích"], ["smoothness", "smoothness", "Độ trơn"], ["compactness", "compactness", "Độ đặc"],
  ["concavity", "concavity", "Độ lõm"], ["concave points", "concave points", "Số điểm lõm"],
  ["symmetry", "symmetry", "Độ đối xứng"], ["fractal dimension", "fractal_dimension", "Chiều fractal"],
];
const GROUPS = [
  { suffix: "mean", vi: "trung bình", name: m => `mean ${m}` },
  { suffix: "se", vi: "sai số chuẩn", name: m => `${m} error` },
  { suffix: "worst", vi: "xấu nhất", name: m => `worst ${m}` },
];
// Slider range from the brief; widened if the locked or the shared threshold lies outside it.
const RANGE = [0.3, 0.7];
const CLASS_EN = { malignant: "Malignant", benign: "Benign" };
// The mockup writes numbers with a decimal point, so this page does too.
const fx = (v, d) => Number(v).toFixed(d);
const pct = v => `${(v * 100).toFixed(2)}%`;

function fields() {
  return GROUPS.map((g, gi) => `
    <div class="feat-col">
      ${MEASURES.map(([dataset, kaggle, vi], mi) => {
        const name = g.name(dataset);
        return `<label class="feat" title="${vi} (${g.vi}) — ${name}">
          <span>${gi * 10 + mi + 1}. ${kaggle}_${g.suffix}</span>
          <input type="number" step="any" min="0" inputmode="decimal" name="${name}" required></label>`;
      }).join("")}
    </div>`).join("");
}

export default {
  title: "Chẩn đoán SVM",
  subtitle: "Nhập 30 đặc trưng của bệnh nhân để dự đoán khả năng mắc ung thư vú",
  icon: "brain",

  async render(view, ctx) {
    view.innerHTML = `
      <div class="diag-grid">
        <div class="diag-col">
          <section class="card">
            <div class="card-head">
              <h2 class="h-icon">${icon("user-round-search", 20)}Nhập đặc trưng (30 biến)</h2>
              <div class="model-chip"><span class="svm-pill">SVM RBF</span><span class="param-box" id="params">C = … | γ = …</span></div>
            </div>
            <form id="form" novalidate>
              <div class="feat-cols">${fields()}</div>
              <div class="form-actions">
                <button class="btn outline" type="button" id="clear" title="Khôi phục dữ liệu mặc định">${icon("rotate-ccw", 16)}Đặt lại</button>
                <button class="btn cta" type="submit" id="predictBtn">${icon("play", 16)}Dự đoán</button>
                <span class="sample-pick" title="Nạp ngẫu nhiên một mẫu của tập kiểm tra kèm nhãn thật">Mẫu test:
                  <button class="link-btn" type="button" data-sample="malignant">Ác tính</button>·
                  <button class="link-btn" type="button" data-sample="benign">Lành tính</button></span>
              </div>
              <p class="sample-line" id="formHint" hidden></p>
              <p class="sample-line" id="sampleInfo" hidden></p>
            </form>
          </section>
          <div class="diag-bottom">
            <section class="card">
              <div class="card-head"><h2 class="h-icon">${icon("settings", 18)}Thông tin mô hình</h2></div>
              <div id="facts"><div class="skeleton sk-line"></div><div class="skeleton sk-line"></div></div>
            </section>
            <section class="card">
              <div class="card-head"><h2 class="h-icon">${icon("users", 18)}Phân bố xác suất dự đoán</h2></div>
              <div id="donut"><p class="sub">Chưa có dự đoán.</p></div>
            </section>
          </div>
        </div>

        <div class="diag-col">
          <section class="card">
            <div class="t-head">
              <h2 class="h-icon">${icon("sliders-horizontal", 20)}Ngưỡng dự đoán (Threshold)</h2>
              <div class="t-value">
                <button class="icon-btn t-reset" type="button" id="tReset" title="Về ngưỡng mặc định" aria-label="Về ngưỡng mặc định" disabled>${icon("rotate-ccw", 16)}</button>
                <span class="t-pill" id="tPill">—</span>
              </div>
            </div>
            <p class="sub t-sub">Điều chỉnh ngưỡng để cân bằng giữa sensitivity và specificity.</p>
            <div id="tBody"><div class="skeleton sk-line"></div></div>
          </section>

          <section class="card" aria-live="polite">
            <div class="card-head" style="margin-bottom:0">
              <h2 class="h-icon">${icon("shield-check", 20)}Kết quả dự đoán</h2>
              <button class="btn ghost small" type="button" id="save" hidden>${icon("save", 14)}Lưu vào lịch sử</button>
            </div>
            <div id="result"><div class="verdict-empty">Chưa có kết quả — nhập 30 đặc trưng rồi bấm “Dự đoán”.</div></div>
            <hr class="section-divider">
            <h3 class="h-icon">${icon("chart-no-axes-column", 18)}Hiệu suất mô hình <small>(trên tập test)</small></h3>
            <div id="perf"><div class="skeleton sk-block"></div></div>
          </section>

          <section class="card">
            <div class="card-head"><h2 class="h-icon">${icon("clock", 18)}Thời gian dự đoán</h2></div>
            <div id="timing"><p class="sub">Chưa có dự đoán.</p></div>
          </section>
        </div>
      </div>`;

    const form = view.querySelector("#form");
    const box = view.querySelector("#result");
    const saveBtn = view.querySelector("#save");
    const inputs = () => [...form.querySelectorAll("input")];
    let sample = null;   // {id, label} of the loaded test sample; cleared once a value is edited
    let last = null;     // last successful prediction: {r, ms, payload, sample}
    let shownLabel = null;
    let scores = null;   // test-split scores of the deployed model
    let t = null;        // threshold currently on the slider
    let donut = null;

    const sampleInfo = view.querySelector("#sampleInfo");
    inputs().forEach(el => el.addEventListener("input", () => {
      el.classList.remove("invalid");
      if (sample) {
        sample = null;
        sampleInfo.textContent = "Đã sửa giá trị — không còn so sánh với nhãn thật của mẫu.";
      }
    }));

    const fill = values => inputs().forEach(el => { el.value = values[el.name] ?? ""; el.classList.remove("invalid"); });

    const loadDefault = async () => {
      try {
        const s = await modelApi("/samples/default");
        if (!ctx.alive()) return false;
        fill(s.features);
        sample = { id: s.id, label: s.label };
        sampleInfo.hidden = false;
        sampleInfo.innerHTML = `Dữ liệu mặc định: <b>${esc(s.id)}</b> (dòng đầu của bộ dữ liệu) · nhãn thật: <b>${CLASS_VI[s.label]}</b>`;
        view.querySelector("#formHint").hidden = true;
        return true;
      } catch (err) {
        toast(err.message);
        return false;
      }
    };

    const loadSample = async label => {
      try {
        const data = await modelApi(`/samples?n=1&label=${label}`);
        const s = data.items[0];
        fill(s.features);
        sample = { id: s.id, label: s.label };
        sampleInfo.hidden = false;
        sampleInfo.innerHTML = `Đã nạp mẫu <b>${esc(s.id)}</b> của tập kiểm tra · nhãn thật: <b>${CLASS_VI[s.label]}</b>`;
        return true;
      } catch (err) {
        toast(err.message);
        return false;
      }
    };

    // ---------------------------------------------------------------- model facts

    const facts = async () => {
      try {
        const m = await modelApi("/metadata");
        if (!ctx.alive()) return;
        const { svc__C: C, svc__gamma: gamma } = m.best_params;
        view.querySelector("#params").textContent = `C = ${C} | γ = ${gamma}`;
        const rows = [["Thuật toán", "SVM (RBF)"], ["C", C], ["Gamma (γ)", gamma], ["Pipeline", "StandardScaler + SVC"]];
        view.querySelector("#facts").innerHTML = `<table class="kv-table"><tbody>${rows.map(([k, v]) =>
          `<tr><th scope="row">${k}</th><td>${esc(v)}</td></tr>`).join("")}</tbody></table>`;
      } catch (err) {
        if (!ctx.alive()) return;
        view.querySelector("#facts").innerHTML = errorState(err.message);
      }
    };

    // ---------------------------------------------------------------- threshold slider + test metrics

    const renderPerf = () => {
      const c = confusion(scores.items, t);
      const target = scores.target_sensitivity;
      const reached = c.sens >= target;
      view.querySelector("#perf").innerHTML = `
        <div class="metric-tiles">
          <div class="metric-tile sens"><span>Sensitivity (Recall)</span><b>${pct(c.sens)}</b></div>
          <div class="metric-tile spec"><span>Specificity</span><b>${pct(c.spec)}</b></div>
          <div class="metric-tile prec"><span>Precision</span><b>${pct(c.prec)}</b></div>
          <div class="metric-tile f1"><span>F1-score</span><b>${pct(c.f1)}</b></div>
        </div>
        <div class="target-row" title="${scores.items.length} mẫu test · ${c.tp} TP · ${c.fn} FN · ${c.fp} FP · ${c.tn} TN tại ngưỡng ${fx(t, 4)}">
          ${icon("target", 24)}
          <div><b>Mục tiêu</b><code>Sensitivity ≥ ${fx(target, 2)}</code></div>
          <span class="goal-pill ${reached ? "ok" : "bad"}">${reached ? "Đạt được" : "Chưa đạt"}${icon(reached ? "check" : "x", 14)}</span>
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
          <div class="donut-row">
            <div class="donut-box"><canvas id="donutCanvas" role="img" aria-label="Xác suất lành tính và ác tính của mẫu vừa dự đoán"></canvas>
              <div class="donut-center"><div><b id="donutPct"></b></div></div></div>
            <ul class="legend" id="donutLegend"></ul>
          </div>`;
        donut = chart(host.querySelector("#donutCanvas"), {
          type: "doughnut",
          data: { labels: [CLASS_VI.benign, CLASS_VI.malignant],
            datasets: [{ data: [p.benign, p.malignant], backgroundColor: [CLASS_COLORS.benign, CLASS_COLORS.malignant], borderWidth: 2, borderColor: cssVar("--card") }] },
          options: { cutout: "70%", plugins: { legend: { display: false },
            tooltip: { callbacks: { label: c => ` ${c.label}: ${fx(c.parsed, 4)}` } } } },
        });
      } else {
        donut.data.datasets[0].data = [p.benign, p.malignant];
        donut.update("none");
      }
      const center = host.querySelector("#donutPct");
      center.textContent = pct(p[label]);
      center.style.color = CLASS_COLORS[label];
      host.querySelector("#donutLegend").innerHTML = ["benign", "malignant"].map(k => `
        <li><span class="dot" style="background:${CLASS_COLORS[k]}"></span><span>${CLASS_VI[k]}</span><b>${fx(p[k], 4)}</b></li>`).join("");
    };

    const renderResult = () => {
      const { r, sample: s } = last;
      const label = labelAt(r.probability_malignant, t);
      shownLabel = label;
      const bar = (k, p) => `
        <div class="p-row">
          <div class="p-head"><span>Xác suất ${CLASS_VI[k].toLowerCase()}</span><b style="color:${CLASS_COLORS[k]}">${fx(p, 4)}</b></div>
          <div class="p-bar"><div style="width:${p * 100}%;background:${CLASS_COLORS[k]}"></div></div>
        </div>`;
      const truth = s ? `<p class="truth-line">Nhãn thật của ${esc(s.id)}: <b>${CLASS_VI[s.label]}</b> —
          ${s.label === label ? `<span class="ok">dự đoán đúng</span>` : `<span class="bad">dự đoán sai</span>`}</p>` : "";
      box.innerHTML = `
        <div class="verdict-box ${label}">
          <div class="verdict-main">
            <span class="verdict-icon">${icon(label === "benign" ? "check" : "triangle-alert", 24)}</span>
            <div><div class="v-label">${CLASS_VI[label]}</div><div class="v-en">(${CLASS_EN[label]})</div></div>
          </div>
          <div class="verdict-probs">${bar("benign", r.probability_benign)}${bar("malignant", r.probability_malignant)}</div>
        </div>${truth}`;
    };

    saveBtn.addEventListener("click", async () => {
      if (!last) return;
      if (!getAuth()) { toast("Hãy đăng nhập để lưu lịch sử"); location.hash = "#/dang-nhap"; return; }
      saveBtn.disabled = true;
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
      } finally {
        saveBtn.disabled = false;
      }
    });

    // Called on every slider move: everything is recomputed here, no request is sent.
    const applyThreshold = value => {
      t = value;
      saveThreshold(t, scores.threshold);
      const slider = view.querySelector("#t");
      slider.style.setProperty("--fill", `${((t - slider.min) / (slider.max - slider.min)) * 100}%`);
      view.querySelector("#tPill").textContent = fx(t, 4);
      view.querySelector("#tReset").disabled = Math.abs(t - scores.threshold) < 1e-9;
      renderPerf();
      if (last) {
        if (labelAt(last.r.probability_malignant, t) !== shownLabel) renderResult();
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
        <div class="t-slider"><input type="range" class="indigo" id="t" min="${lo}" max="${hi}" step="0.0001" value="${t}" aria-label="Ngưỡng trên P(ác tính)"></div>
        <div class="range-ends"><span>${fx(lo, 2)}</span><span>${fx(hi, 2)}</span></div>
        <div class="info-box">${icon("info", 20)}<span>Ngưỡng được chọn dựa trên xác suất out-of-fold từ quá trình cross-validation
          (mặc định <b>${fx(locked, 4)}</b>).</span></div>`;
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
      saveBtn.hidden = false;
      view.querySelector("#timing").innerHTML = `
        <div class="timing"><b>~ ${fx(r.inference_ms, 1)} ms</b><span>(trên 1 mẫu)</span></div>
        <div class="note-box">Thời gian có thể thay đổi tùy theo môi trường triển khai và cấu hình phần cứng.
          Đo phía server (predict_proba); cả lượt gọi API mất ${ms} ms.</div>`;
    };

    const clearPrediction = () => {
      last = null;
      shownLabel = null;
      donut = null;
      saveBtn.hidden = true;
      view.querySelector("#donut").innerHTML = `<p class="sub">Chưa có dự đoán.</p>`;
      view.querySelector("#timing").innerHTML = `<p class="sub">Chưa có dự đoán.</p>`;
    };

    const predict = async event => {
      if (event) event.preventDefault();
      const hint = view.querySelector("#formHint");
      const values = {};
      const bad = [];
      inputs().forEach(el => {
        const v = el.value.trim() === "" ? NaN : Number(el.value);
        if (!Number.isFinite(v)) { bad.push(el.name); el.classList.add("invalid"); }
        values[el.name] = v;
      });
      if (bad.length) {
        hint.hidden = false;
        hint.textContent = `Còn ${bad.length} ô trống hoặc không phải số — cần đủ 30 giá trị.`;
        return;
      }
      hint.hidden = true;
      const btn = view.querySelector("#predictBtn");
      btn.disabled = true;
      const started = performance.now();
      try {
        const r = await modelApi("/predict", { method: "POST", body: values });
        if (!ctx.alive()) return;
        showPrediction(r, Math.round(performance.now() - started), values);
        if (window.matchMedia("(max-width: 1200px)").matches) box.scrollIntoView({ behavior: "smooth", block: "center" });
      } catch (err) {
        if (!ctx.alive()) return;
        // Forget the previous prediction so the slider does not re-label a result that is no longer shown.
        clearPrediction();
        const detail = err.body && err.body.detail;
        const list = detail && detail.out_of_range
          ? detail.out_of_range.map(f => `${f.feature} = ${f.value} (tối đa ${fx(f.upper_bound, 2)})`)
          : [];
        box.innerHTML = `${errorState(err.message)}${list.length ? `<ul class="bullets">${list.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`;
      } finally {
        btn.disabled = false;
      }
    };

    form.addEventListener("submit", predict);
    view.querySelectorAll("[data-sample]").forEach(b => b.addEventListener("click", () => loadSample(b.dataset.sample)));
    view.querySelector("#clear").addEventListener("click", async () => {
      if (await loadDefault()) predict();
    });
    facts();
    await setupThreshold();
    if (!ctx.alive()) return;

    const q = new URLSearchParams(location.search);
    const wanted = q.get("sample");
    if (wanted === "malignant" || wanted === "benign") {
      if (await loadSample(wanted) && q.get("auto") === "1") predict();
    } else if (await loadDefault()) {
      predict();
    }
  },
};
