// Advanced analysis (highlight feature): an interactive threshold explorer on the test split — confusion
// matrix, clinical metrics, probability histogram, metrics-by-threshold curves and the ROC / PR operating
// points all follow the slider, whose value is shared with the diagnosis page — plus the permutation
// importance of the 30 features (an RBF SVC has no coef_ / feature_importances_) and a PCA 2D view of
// the dataset. Every remark is generated from the numbers.
import { modelApi } from "../api.js";
import { chart } from "../charts.js";
import { icon } from "../icons.js";
import { confusion, currentThreshold, saveThreshold, testScores } from "../threshold.js";
import { CLASS_COLORS, CLASS_KEYS, CLASS_VI, PALETTE, errorState, esc, num, onClick, skeleton } from "../ui.js";

const BINS = 25;
const TOP_FEATURES = 15;
const METRIC_LINES = [
  { key: "sens", label: "Sensitivity", color: "#2F9E44" },
  { key: "spec", label: "Specificity", color: CLASS_COLORS.benign },
  { key: "prec", label: "Precision", color: PALETTE[0] },
  { key: "f1", label: "F1-score", color: PALETTE[4] },
];

function rocCurve(items) {
  const thresholds = [...new Set(items.map(s => s.proba_malignant))].sort((a, b) => b - a);
  const pts = [{ x: 0, y: 0 }];
  thresholds.forEach(t => {
    const c = confusion(items, t);
    pts.push({ x: 1 - c.spec, y: c.sens });
  });
  pts.push({ x: 1, y: 1 });
  let auc = 0;
  for (let i = 1; i < pts.length; i++) auc += (pts[i].x - pts[i - 1].x) * (pts[i].y + pts[i - 1].y) / 2;
  return { pts, auc };
}

// Precision–recall curve and average precision AP = Σ (R_i − R_{i−1}) · P_i.
function prCurve(items) {
  const thresholds = [...new Set(items.map(s => s.proba_malignant))].sort((a, b) => b - a);
  const pts = [{ x: 0, y: 1 }];
  let ap = 0;
  let prevRecall = 0;
  thresholds.forEach(t => {
    const c = confusion(items, t);
    pts.push({ x: c.sens, y: c.prec });
    ap += (c.sens - prevRecall) * c.prec;
    prevRecall = c.sens;
  });
  return { pts, ap };
}

// Vertical dashed line at the current threshold. With `bins` the x axis is a category axis of histogram
// bins; otherwise it is a linear axis in threshold units. (No annotation plugin is bundled.)
const thresholdLine = {
  id: "thresholdLine",
  afterDatasetsDraw(c) {
    const opts = c.options.plugins.thresholdLine;
    const t = opts.value;
    const x = c.scales.x.getPixelForValue(opts.bins ? t * opts.bins - 0.5 : t);
    const g = c.ctx;
    g.save();
    g.strokeStyle = "#C2255C";
    g.lineWidth = 2;
    g.setLineDash([6, 4]);
    g.beginPath();
    g.moveTo(x, c.chartArea.top);
    g.lineTo(x, c.chartArea.bottom);
    g.stroke();
    g.restore();
  },
};

function importanceRemark(pi) {
  const top = pi.items[0];
  const useless = pi.items.filter(i => i.mean <= 0).length;
  const top3 = pi.items.slice(0, 3).map(i => esc(i.feature_vi)).join(", ");
  return `<div class="insight">${icon("lightbulb", 18)}<p>SVC kernel RBF không có <code>coef_</code> hay <code>feature_importances_</code>,
    nên mức quan trọng được đo bằng cách xáo trộn từng đặc trưng ${pi.n_repeats} lần trên ${pi.n_samples} mẫu test và xem ROC-AUC
    (gốc ${num(pi.baseline_score, 4)}) giảm bao nhiêu. Ba đặc trưng quan trọng nhất: ${top3}; xáo
    “${esc(top.feature_vi)}” làm ROC-AUC giảm trung bình ${num(top.mean, 4)}. ${useless} / ${pi.items.length} đặc trưng có mức giảm ≤ 0.
    Mức giảm đều nhỏ vì nhiều đặc trưng tương quan mạnh (bán kính, chu vi, diện tích…): xáo một cột thì mô hình vẫn lấy lại
    thông tin từ cột cùng nhóm — nên đọc thứ hạng hơn là độ lớn. ROC-AUC không phụ thuộc ngưỡng nên bảng này không đổi khi kéo thanh trượt.</p></div>`;
}

export default {
  title: "Phân tích nâng cao",
  subtitle: "Khám phá ngưỡng quyết định trên tập kiểm tra, đường ROC / PR, permutation importance và PCA 2D",
  icon: "chart-scatter",

  async render(view, ctx) {
    view.innerHTML = `<div class="stack"><div class="card">${skeleton({ block: true, lines: 3 })}</div>
      <div class="grid cols-2"><div class="card">${skeleton({ block: true, lines: 2 })}</div><div class="card">${skeleton({ block: true, lines: 2 })}</div></div></div>`;
    let scores, pca;
    try {
      [scores, pca] = await Promise.all([testScores(), modelApi("/dataset/pca")]);
    } catch (err) {
      if (!ctx.alive()) return;
      view.innerHTML = `<div class="card">${errorState(err.message, "retry")}</div>`;
      onClick(view, "#retry", () => this.render(view, ctx));
      return;
    }
    if (!ctx.alive()) return;

    const items = scores.items;
    const locked = scores.threshold;
    const target = scores.target_sensitivity;
    const nMal = items.filter(s => s.label === "malignant").length;
    const nBen = items.length - nMal;
    const roc = rocCurve(items);
    const pr = prCurve(items);
    const [r1, r2] = pca.explained_variance_ratio;
    const start = currentThreshold(locked);
    const lockedStats = confusion(items, locked);

    view.innerHTML = `
      <section class="stack" aria-labelledby="advTitle">
        <section class="card">
          <div class="card-head">
            <div><h2 id="advTitle">Khám phá ngưỡng quyết định</h2>
              <p class="sub">${items.length} mẫu test (${nMal} ác tính, ${nBen} lành tính) · P(ác tính) của mô hình SVM đang triển khai ·
                ngưỡng dùng chung với trang Chẩn đoán SVM</p></div>
            <div class="btn-row">
              <button class="btn ghost small" type="button" data-t="${locked}">${icon("refresh-cw", 14)}Ngưỡng mặc định ${num(locked, 4)}</button>
              <button class="btn ghost small" type="button" data-t="0.5">Ngưỡng 0,5</button>
            </div>
          </div>
          <div class="threshold-controls">
            <input type="range" id="t" min="0.01" max="0.99" step="0.0001" value="${start}" aria-label="Ngưỡng trên P(ác tính)">
            <b id="tValue" style="min-width:120px;text-align:right;color:var(--title)"></b>
          </div>
          <div class="stat-grid" style="margin-top:14px" id="stats"></div>
          <div class="grid cols-2" style="margin-top:14px">
            <div>
              <h3 style="font-size:14px;margin:0 0 6px">Ma trận nhầm lẫn</h3>
              <table class="cm2" id="cm" aria-label="Ma trận nhầm lẫn tại ngưỡng đang chọn"></table>
            </div>
            <div>
              <h3 style="font-size:14px;margin:0 0 6px">Phân phối P(ác tính) theo nhãn thật</h3>
              <div class="chart-box short"><canvas id="hist" role="img" aria-label="Histogram xác suất ác tính theo nhãn thật"></canvas></div>
            </div>
          </div>
          <div class="insight" id="thresholdInsight"></div>
        </section>

        <div class="grid cols-2">
          <section class="card">
            <div class="card-head"><div><h2>Các chỉ số theo ngưỡng</h2><p class="sub">Sensitivity, specificity, precision, F1 trên tập test · vạch đỏ là ngưỡng đang chọn</p></div></div>
            <div class="chart-box"><canvas id="curves" role="img" aria-label="Sensitivity, specificity, precision và F1 theo ngưỡng"></canvas></div>
            <div class="insight" id="curvesInsight"></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2>Mức quan trọng đặc trưng (permutation importance)</h2>
              <p class="sub" id="piSub">Đang tính trên tập test…</p></div></div>
            <div id="piBody"><div class="skeleton sk-block"></div></div>
          </section>
        </div>

        <div class="grid cols-2">
          <section class="card">
            <div class="card-head"><div><h2>Đường ROC và điểm vận hành</h2><p class="sub">Điểm đỏ di chuyển theo thanh trượt · AUC = ${num(roc.auc, 4)}</p></div></div>
            <div class="chart-box"><canvas id="roc" role="img" aria-label="Đường ROC của mô hình SVM trên tập test"></canvas></div>
            <div class="insight">${icon("lightbulb", 18)}<p>ROC-AUC ${num(roc.auc, 4)}: nếu chọn ngẫu nhiên một ca ác tính và một ca lành tính,
              mô hình chấm ca ác tính cao hơn trong ${num(roc.auc * 100, 1)}% số cặp. Đổi ngưỡng chỉ trượt điểm vận hành dọc theo
              đường này — không làm đường cong tốt lên.</p></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2>Đường Precision–Recall</h2><p class="sub">Điểm đỏ di chuyển theo thanh trượt · AP = ${num(pr.ap, 4)}</p></div></div>
            <div class="chart-box"><canvas id="pr" role="img" aria-label="Đường precision recall của mô hình SVM trên tập test"></canvas></div>
            <div class="insight">${icon("lightbulb", 18)}<p>Tỉ lệ ca ác tính trong tập test là ${num(nMal / items.length * 100, 1)}% — đó là precision
              của một mô hình đoán ngẫu nhiên (đường nét đứt); average precision của SVM là ${num(pr.ap, 4)}. Tại ngưỡng mặc định
              ${num(locked, 4)}: recall ${num(lockedStats.sens, 4)}, precision ${num(lockedStats.prec, 4)} — ngưỡng thấp ưu tiên không bỏ
              sót ca ác tính, chấp nhận thêm ca báo nhầm.</p></div>
          </section>
        </div>

        <section class="card">
          <div class="card-head"><div><h2>PCA 2D</h2><p class="sub">${pca.n_samples} mẫu, 30 đặc trưng chuẩn hoá rồi chiếu xuống 2 thành phần chính</p></div></div>
          <div class="chart-box"><canvas id="pca" role="img" aria-label="Biểu đồ PCA 2D tô màu theo nhãn"></canvas></div>
          <div class="insight">${icon("lightbulb", 18)}<p>PC1 và PC2 giữ ${num((r1 + r2) * 100, 1)}% phương sai (PC1 ${num(r1 * 100, 1)}%,
            PC2 ${num(r2 * 100, 1)}%). Hai lớp tách chủ yếu theo PC1 nhưng vẫn có vùng chồng lấn — nơi các ca khó nằm, và là lý do
            cần xác suất cùng ngưỡng thay vì một đường biên cứng.</p></div>
        </section>
      </section>`;

    // Histogram of P(malignant), stacked by true label.
    const counts = label => {
      const bins = Array(BINS).fill(0);
      items.filter(s => s.label === label).forEach(s => { bins[Math.min(BINS - 1, Math.floor(s.proba_malignant * BINS))]++; });
      return bins;
    };
    const hist = chart(view.querySelector("#hist"), {
      type: "bar",
      data: {
        labels: Array.from({ length: BINS }, (_, i) => num((i + 0.5) / BINS, 2)),
        datasets: ["benign", "malignant"].map(k => ({
          label: CLASS_VI[k], data: counts(k), backgroundColor: CLASS_COLORS[k], stack: "s", barPercentage: 1, categoryPercentage: 0.95,
        })),
      },
      options: {
        scales: { x: { stacked: true, grid: { display: false }, title: { display: true, text: "P(ác tính)" }, ticks: { maxTicksLimit: 6 } },
          y: { stacked: true, beginAtZero: true, title: { display: true, text: "Số mẫu" }, ticks: { precision: 0 } } },
        plugins: { legend: { position: "bottom" }, thresholdLine: { value: start, bins: BINS } },
        animation: false,
      },
      plugins: [thresholdLine],
    });

    // Metrics as functions of the threshold, on a 0.005 grid.
    const grid = Array.from({ length: 197 }, (_, i) => 0.01 + i * 0.005);
    const atGrid = grid.map(t => confusion(items, t));
    const yMin = Math.floor(Math.min(...atGrid.flatMap(c => METRIC_LINES.map(m => c[m.key]))) * 10) / 10;
    const curves = chart(view.querySelector("#curves"), {
      type: "scatter",
      data: {
        datasets: [
          ...METRIC_LINES.map(m => ({
            label: m.label, data: grid.map((t, i) => ({ x: t, y: atGrid[i][m.key] })),
            showLine: true, pointRadius: 0, borderColor: m.color, backgroundColor: m.color, borderWidth: 2, stepped: true,
          })),
          { label: `Mục tiêu sensitivity ${num(target, 2)}`, data: [{ x: 0, y: target }, { x: 1, y: target }], showLine: true,
            pointRadius: 0, borderDash: [5, 4], borderColor: "#ADB5BD", borderWidth: 1 },
        ],
      },
      options: {
        animation: false,
        scales: { x: { min: 0, max: 1, title: { display: true, text: "Ngưỡng trên P(ác tính)" } },
          y: { min: yMin, max: 1.01, title: { display: true, text: "Giá trị" } } },
        plugins: { legend: { position: "bottom" }, thresholdLine: { value: start },
          tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${num(c.parsed.y, 4)} (ngưỡng ${num(c.parsed.x, 3)})` } } },
      },
      plugins: [thresholdLine],
    });
    // Highest threshold that still meets the sensitivity target on the test split (for the remark).
    const okGrid = grid.filter((_, i) => atGrid[i].sens >= target);
    const maxOk = okGrid.length ? okGrid[okGrid.length - 1] : null;

    const opPoint = { pointRadius: 7, pointHoverRadius: 8, backgroundColor: "#C92A2A", borderColor: "#fff", borderWidth: 2 };
    const rocChart = chart(view.querySelector("#roc"), {
      type: "scatter",
      data: {
        datasets: [
          { label: "ROC (test)", data: roc.pts, showLine: true, pointRadius: 0, borderColor: "#6C5CE7", borderWidth: 2 },
          { label: "Điểm vận hành", data: [{ x: 0, y: 0 }], ...opPoint },
          { label: "Đoán ngẫu nhiên", data: [{ x: 0, y: 0 }, { x: 1, y: 1 }], showLine: true, pointRadius: 0, borderDash: [5, 4], borderColor: "#ADB5BD", borderWidth: 1 },
        ],
      },
      options: {
        animation: false,
        scales: { x: { min: 0, max: 1, title: { display: true, text: "1 − Specificity" } }, y: { min: 0, max: 1.02, title: { display: true, text: "Sensitivity" } } },
        plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: c => ` ${c.dataset.label}: (${num(c.parsed.x, 3)}; ${num(c.parsed.y, 3)})` } } },
      },
    });

    const prevalence = nMal / items.length;
    const prChart = chart(view.querySelector("#pr"), {
      type: "scatter",
      data: {
        datasets: [
          { label: "PR (test)", data: pr.pts, showLine: true, pointRadius: 0, borderColor: PALETTE[1], borderWidth: 2, stepped: "before" },
          { label: "Điểm vận hành", data: [{ x: 0, y: 1 }], ...opPoint },
          { label: "Đoán ngẫu nhiên", data: [{ x: 0, y: prevalence }, { x: 1, y: prevalence }], showLine: true, pointRadius: 0, borderDash: [5, 4], borderColor: "#ADB5BD", borderWidth: 1 },
        ],
      },
      options: {
        animation: false,
        scales: { x: { min: 0, max: 1, title: { display: true, text: "Recall (sensitivity)" } }, y: { min: 0, max: 1.02, title: { display: true, text: "Precision" } } },
        plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: c => ` ${c.dataset.label}: (${num(c.parsed.x, 3)}; ${num(c.parsed.y, 3)})` } } },
      },
    });

    chart(view.querySelector("#pca"), {
      type: "scatter",
      data: {
        datasets: CLASS_KEYS.map(k => ({
          label: CLASS_VI[k],
          data: pca.points.filter(p => p.label === k).map(p => ({ x: p.pc1, y: p.pc2 })),
          pointStyle: k === "malignant" ? "triangle" : "circle",
          backgroundColor: CLASS_COLORS[k] + "B3", borderColor: "#fff", borderWidth: 0.6, pointRadius: 4, pointHoverRadius: 6,
        })),
      },
      options: {
        scales: { x: { title: { display: true, text: `PC1 (${num(r1 * 100, 1)}% phương sai)` } }, y: { title: { display: true, text: `PC2 (${num(r2 * 100, 1)}% phương sai)` } } },
        plugins: { legend: { position: "bottom" } },
      },
    });

    const slider = view.querySelector("#t");
    const update = () => {
      const t = parseFloat(slider.value);
      saveThreshold(t, locked);
      const c = confusion(items, t);
      view.querySelector("#tValue").textContent = `ngưỡng ${num(t, 4)}`;
      view.querySelector("#stats").innerHTML = [
        ["Sensitivity", c.sens, `${c.tp}/${nMal} ca ác tính · ${c.sens >= target ? "đạt" : "chưa đạt"} mục tiêu ${num(target, 2)}`],
        ["Specificity", c.spec, `${c.tn}/${nBen} ca lành tính`],
        ["Precision ác tính", c.prec, `${c.tp}/${c.tp + c.fp} dự đoán ác tính`],
        ["F1-score", c.f1, `${c.fn} bỏ sót · ${c.fp} báo nhầm`],
      ].map(([k, v, hint]) => `<div class="stat-box"><div class="k">${k}</div><div class="v">${num(v, 4)}</div><div class="sub">${hint}</div></div>`).join("");
      view.querySelector("#cm").innerHTML = `
        <thead><tr><th></th><th>Dự đoán ác tính</th><th>Dự đoán lành tính</th></tr></thead>
        <tbody>
          <tr><th scope="row">Thực tế ác tính</th><td class="ok">${c.tp}<small>TP</small></td><td class="${c.fn ? "miss" : ""}">${c.fn}<small>FN — bỏ sót</small></td></tr>
          <tr><th scope="row">Thực tế lành tính</th><td class="${c.fp ? "miss" : ""}">${c.fp}<small>FP — báo nhầm</small></td><td class="ok">${c.tn}<small>TN</small></td></tr>
        </tbody>`;
      const dFN = c.fn - lockedStats.fn;
      const dFP = c.fp - lockedStats.fp;
      const vsLocked = Math.abs(t - locked) < 1e-6 ? "Đây là ngưỡng mặc định, chọn trên xác suất out-of-fold của cross-validation trước khi nhìn tập test."
        : `So với ngưỡng mặc định: ${dFN === 0 ? "cùng số ca bỏ sót" : `${dFN > 0 ? "thêm" : "bớt"} ${Math.abs(dFN)} ca bỏ sót`}, `
          + `${dFP === 0 ? "cùng số ca báo nhầm" : `${dFP > 0 ? "thêm" : "bớt"} ${Math.abs(dFP)} ca báo nhầm`}.`;
      view.querySelector("#thresholdInsight").innerHTML = `${icon("lightbulb", 18)}<p>Ở ngưỡng ${num(t, 4)} mô hình bắt ${c.tp}/${nMal} ca ác tính
        và báo nhầm ${c.fp}/${nBen} ca lành tính. ${esc(vsLocked)} Kéo ngưỡng trên tập test chỉ để quan sát sự đánh đổi —
        chọn lại ngưỡng theo tập test là rò rỉ thông tin.</p>`;
      view.querySelector("#curvesInsight").innerHTML = `${icon("lightbulb", 18)}<p>Tại ngưỡng ${num(t, 4)}: sensitivity ${num(c.sens, 4)},
        specificity ${num(c.spec, 4)}, precision ${num(c.prec, 4)}, F1 ${num(c.f1, 4)}. Hạ ngưỡng thì sensitivity tăng còn specificity
        giảm. ${maxOk === null ? `Không ngưỡng nào trên lưới đạt sensitivity ≥ ${num(target, 2)} trên tập test.`
          : `Trên tập test, mọi ngưỡng ≤ ${num(maxOk, 3)} đều giữ sensitivity ≥ ${num(target, 2)}.`}</p>`;
      hist.options.plugins.thresholdLine.value = t;
      hist.update("none");
      curves.options.plugins.thresholdLine.value = t;
      curves.update("none");
      rocChart.data.datasets[1].data = [{ x: 1 - c.spec, y: c.sens }];
      rocChart.update("none");
      prChart.data.datasets[1].data = [{ x: c.sens, y: c.prec }];
      prChart.update("none");
    };
    slider.addEventListener("input", update);
    view.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => { slider.value = b.dataset.t; update(); }));
    update();

    this.loadImportance(view, ctx);
  },

  // Permutation importance takes a few seconds the first time the server computes it, so it loads on its own.
  async loadImportance(view, ctx) {
    const body = view.querySelector("#piBody");
    let pi;
    try {
      pi = await modelApi("/analysis/permutation-importance");
    } catch (err) {
      if (!ctx.alive()) return;
      body.innerHTML = errorState(err.message, "retryPi");
      onClick(body, "#retryPi", () => { body.innerHTML = `<div class="skeleton sk-block"></div>`; this.loadImportance(view, ctx); });
      return;
    }
    if (!ctx.alive()) return;
    const top = pi.items.slice(0, TOP_FEATURES);
    view.querySelector("#piSub").textContent =
      `Mức giảm ROC-AUC khi xáo trộn từng đặc trưng · ${TOP_FEATURES}/${pi.items.length} đặc trưng đứng đầu · ${pi.n_repeats} lần lặp`;
    body.innerHTML = `<div class="chart-box tall"><canvas id="piChart" role="img" aria-label="Permutation importance của các đặc trưng"></canvas></div>${importanceRemark(pi)}`;
    chart(body.querySelector("#piChart"), {
      type: "bar",
      data: {
        labels: top.map(i => i.feature),
        datasets: [{ label: "Mức giảm ROC-AUC", data: top.map(i => i.mean), backgroundColor: PALETTE[0], borderRadius: 4 }],
      },
      options: {
        indexAxis: "y",
        scales: { x: { beginAtZero: true, title: { display: true, text: "Mức giảm ROC-AUC trung bình" } }, y: { grid: { display: false }, ticks: { autoSkip: false } } },
        plugins: { legend: { display: false },
          tooltip: { callbacks: { title: c => `${top[c[0].dataIndex].feature} — ${top[c[0].dataIndex].feature_vi}`,
            label: c => ` ${num(top[c.dataIndex].mean, 5)} ± ${num(top[c.dataIndex].std, 5)}` } } },
      },
    });
  },
};
