// Advanced analysis (highlight feature): an interactive threshold explorer on the test split — confusion
// matrix, clinical metrics, probability histogram and ROC operating point all follow the slider — plus a
// PCA 2D view of the dataset. Every remark is generated from the numbers.
import { modelApi } from "../api.js";
import { chart } from "../charts.js";
import { icon } from "../icons.js";
import { CLASS_COLORS, CLASS_KEYS, CLASS_VI, errorState, esc, num, onClick, skeleton } from "../ui.js";

const INK = "#1E2A5A";
const BINS = 25;

function confusion(items, t) {
  let tp = 0, fn = 0, fp = 0, tn = 0;
  items.forEach(s => {
    const pos = s.proba_malignant >= t;
    if (s.label === "malignant") pos ? tp++ : fn++;
    else pos ? fp++ : tn++;
  });
  const sens = tp / (tp + fn || 1);
  const spec = tn / (tn + fp || 1);
  const prec = tp + fp ? tp / (tp + fp) : 0;
  return { tp, fn, fp, tn, sens, spec, prec };
}

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

// Vertical line at the current threshold on the histogram (Chart.js has no annotation plugin bundled).
const thresholdLine = {
  id: "thresholdLine",
  afterDatasetsDraw(c) {
    const t = c.options.plugins.thresholdLine.value;
    const x = c.scales.x.getPixelForValue(t * BINS - 0.5);
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

export default {
  title: "Phân tích nâng cao",
  subtitle: "Khám phá ngưỡng quyết định trên tập kiểm tra, đường ROC và PCA 2D của bộ dữ liệu",
  icon: "chart-scatter",

  async render(view, ctx) {
    view.innerHTML = `<div class="stack"><div class="card">${skeleton({ block: true, lines: 3 })}</div>
      <div class="grid cols-2"><div class="card">${skeleton({ block: true, lines: 2 })}</div><div class="card">${skeleton({ block: true, lines: 2 })}</div></div></div>`;
    let scores, pca;
    try {
      [scores, pca] = await Promise.all([modelApi("/analysis/test-scores"), modelApi("/dataset/pca")]);
    } catch (err) {
      if (!ctx.alive()) return;
      view.innerHTML = `<div class="card">${errorState(err.message, "retry")}</div>`;
      onClick(view, "#retry", () => this.render(view, ctx));
      return;
    }
    if (!ctx.alive()) return;

    const items = scores.items;
    const locked = scores.threshold;
    const nMal = items.filter(s => s.label === "malignant").length;
    const nBen = items.length - nMal;
    const roc = rocCurve(items);
    const [r1, r2] = pca.explained_variance_ratio;

    view.innerHTML = `
      <section class="stack" aria-labelledby="advTitle">
        <section class="card">
          <div class="card-head">
            <div><h2 id="advTitle">Khám phá ngưỡng quyết định</h2>
              <p class="sub">${items.length} mẫu test (${nMal} ác tính, ${nBen} lành tính) · P(ác tính) của mô hình SVM đang triển khai</p></div>
            <div class="btn-row">
              <button class="btn ghost small" type="button" data-t="${locked}">${icon("target", 14)}Ngưỡng đã khoá ${num(locked, 4)}</button>
              <button class="btn ghost small" type="button" data-t="0.5">Ngưỡng 0,5</button>
            </div>
          </div>
          <div class="threshold-controls">
            <input type="range" id="t" min="0.01" max="0.99" step="0.0001" value="${locked}" aria-label="Ngưỡng trên P(ác tính)">
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
            <div class="card-head"><div><h2>Đường ROC và điểm vận hành</h2><p class="sub">Điểm đỏ di chuyển theo thanh trượt · AUC = ${num(roc.auc, 4)}</p></div></div>
            <div class="chart-box"><canvas id="roc" role="img" aria-label="Đường ROC của mô hình SVM trên tập test"></canvas></div>
            <div class="insight">${icon("lightbulb", 18)}<p>ROC-AUC ${num(roc.auc, 4)}: nếu chọn ngẫu nhiên một ca ác tính và một ca lành tính,
              mô hình chấm ca ác tính cao hơn trong ${num(roc.auc * 100, 1)}% số cặp. Đổi ngưỡng chỉ trượt điểm vận hành dọc theo
              đường này — không làm đường cong tốt lên.</p></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2>PCA 2D</h2><p class="sub">${pca.n_samples} mẫu, 30 đặc trưng chuẩn hoá rồi chiếu xuống 2 thành phần chính</p></div></div>
            <div class="chart-box"><canvas id="pca" role="img" aria-label="Biểu đồ PCA 2D tô màu theo nhãn"></canvas></div>
            <div class="insight">${icon("lightbulb", 18)}<p>PC1 và PC2 giữ ${num((r1 + r2) * 100, 1)}% phương sai (PC1 ${num(r1 * 100, 1)}%,
              PC2 ${num(r2 * 100, 1)}%). Hai lớp tách chủ yếu theo PC1 nhưng vẫn có vùng chồng lấn — nơi các ca khó nằm, và là lý do
              cần xác suất cùng ngưỡng thay vì một đường biên cứng.</p></div>
          </section>
        </div>
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
        plugins: { legend: { position: "bottom" }, thresholdLine: { value: locked } },
        animation: false,
      },
      plugins: [thresholdLine],
    });

    const rocChart = chart(view.querySelector("#roc"), {
      type: "scatter",
      data: {
        datasets: [
          { label: "ROC (test)", data: roc.pts, showLine: true, pointRadius: 0, borderColor: "#6C5CE7", borderWidth: 2 },
          { label: "Điểm vận hành", data: [{ x: 0, y: 0 }], pointRadius: 7, pointHoverRadius: 8, backgroundColor: "#C92A2A", borderColor: "#fff", borderWidth: 2 },
          { label: "Đoán ngẫu nhiên", data: [{ x: 0, y: 0 }, { x: 1, y: 1 }], showLine: true, pointRadius: 0, borderDash: [5, 4], borderColor: "#ADB5BD", borderWidth: 1 },
        ],
      },
      options: {
        animation: false,
        scales: { x: { min: 0, max: 1, title: { display: true, text: "1 − Specificity" } }, y: { min: 0, max: 1.02, title: { display: true, text: "Sensitivity" } } },
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
    const lockedStats = confusion(items, locked);
    const update = () => {
      const t = parseFloat(slider.value);
      const c = confusion(items, t);
      view.querySelector("#tValue").textContent = `ngưỡng ${num(t, 4)}`;
      view.querySelector("#stats").innerHTML = [
        ["Sensitivity", c.sens, `${c.tp}/${nMal} ca ác tính`], ["Specificity", c.spec, `${c.tn}/${nBen} ca lành tính`],
        ["Precision ác tính", c.prec, `${c.tp}/${c.tp + c.fp} dự đoán ác tính`], ["Bỏ sót / báo nhầm", null, `${c.fn} FN · ${c.fp} FP`],
      ].map(([k, v, hint]) => `<div class="stat-box"><div class="k">${k}</div><div class="v">${v === null ? `${c.fn} / ${c.fp}` : num(v, 4)}</div><div class="sub">${hint}</div></div>`).join("");
      view.querySelector("#cm").innerHTML = `
        <thead><tr><th></th><th>Dự đoán ác tính</th><th>Dự đoán lành tính</th></tr></thead>
        <tbody>
          <tr><th scope="row">Thực tế ác tính</th><td class="ok">${c.tp}<small>TP</small></td><td class="${c.fn ? "miss" : ""}">${c.fn}<small>FN — bỏ sót</small></td></tr>
          <tr><th scope="row">Thực tế lành tính</th><td class="${c.fp ? "miss" : ""}">${c.fp}<small>FP — báo nhầm</small></td><td class="ok">${c.tn}<small>TN</small></td></tr>
        </tbody>`;
      const dFN = c.fn - lockedStats.fn;
      const dFP = c.fp - lockedStats.fp;
      const vsLocked = Math.abs(t - locked) < 1e-6 ? "Đây là ngưỡng đã khoá, chọn trên dữ liệu kiểm định trước khi nhìn tập test."
        : `So với ngưỡng đã khoá: ${dFN === 0 ? "cùng số ca bỏ sót" : `${dFN > 0 ? "thêm" : "bớt"} ${Math.abs(dFN)} ca bỏ sót`}, `
          + `${dFP === 0 ? "cùng số ca báo nhầm" : `${dFP > 0 ? "thêm" : "bớt"} ${Math.abs(dFP)} ca báo nhầm`}.`;
      view.querySelector("#thresholdInsight").innerHTML = `${icon("lightbulb", 18)}<p>Ở ngưỡng ${num(t, 4)} mô hình bắt ${c.tp}/${nMal} ca ác tính
        và báo nhầm ${c.fp}/${nBen} ca lành tính. ${esc(vsLocked)} Kéo ngưỡng trên tập test chỉ để quan sát sự đánh đổi —
        chọn lại ngưỡng theo tập test là rò rỉ thông tin.</p>`;
      hist.options.plugins.thresholdLine.value = t;
      hist.update("none");
      rocChart.data.datasets[1].data = [{ x: 1 - c.spec, y: c.sens }];
      rocChart.update("none");
    };
    slider.addEventListener("input", update);
    view.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => { slider.value = b.dataset.t; update(); }));
    update();
  },
};
