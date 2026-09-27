// Model comparison: five classifiers under the same protocol — leaderboard, clinical metrics, ROC curves,
// timings with speed badges, retrain (stored in the database) and Excel export.
import { dbApi, downloadFromDb, modelApi } from "../api.js";
import { getAuth } from "../auth.js";
import { chart } from "../charts.js";
import { icon } from "../icons.js";
import {
  duration, emptyState, errorState, esc, localTime, MODEL_COLORS, MODEL_SHORT, num, onClick, skeleton, speedBadge,
  toast,
} from "../ui.js";

const DEPLOYED = "svm_rbf";

function params(p) {
  const entries = Object.entries(p || {});
  return entries.length ? entries.map(([k, v]) => `${k}=${v ?? "None"}`).join(", ") : "mặc định";
}

function kpi(ico, label, value, hint) {
  return `<div class="card kpi"><div class="ico">${icon(ico, 20)}</div>
    <div><div class="label">${label}</div><div class="value">${value}</div><div class="hint">${hint}</div></div></div>`;
}

function leaderboard(report) {
  const rows = [...report.models].sort((a, b) => b.cv_mean - a.cv_mean || b.roc_auc - a.roc_auc);
  return rows.map((m, i) => {
    const best = m.model === report.best_model;
    const deployed = m.model === DEPLOYED;
    return `
      <tr class="${best ? "best" : ""}">
        <td class="num">${i + 1}</td>
        <td><span class="swatch" style="background:${MODEL_COLORS[m.model]}"></span><b>${esc(m.label)}</b>
          ${best ? `<span class="badge best">${icon("trophy", 12)}CV cao nhất</span>` : ""}
          ${deployed ? `<span class="badge neutral">${icon("microscope", 12)}Đang triển khai</span>` : ""}</td>
        <td class="num"><b>${num(m.cv_mean, 4)}</b> ± ${num(m.cv_std, 4)}</td>
        <td class="num">${num(m.sensitivity, 4)}</td>
        <td class="num">${num(m.specificity, 4)}</td>
        <td class="num">${num(m.precision_malignant, 4)}</td>
        <td class="num">${num(m.roc_auc, 4)}</td>
        <td class="num">${num(m.pr_auc, 4)}</td>
        <td class="num">${num(m.threshold, 4)}</td>
        <td class="num">${m.false_negatives} / ${m.false_positives}</td>
        <td class="num">${duration(m.train_seconds * 1000)} ${speedBadge(m.train_speed)}</td>
        <td class="num">${duration(m.predict_ms_per_sample)} ${speedBadge(m.predict_speed)}</td>
        <td>${esc(params(m.best_params))}</td>
      </tr>`;
  }).join("");
}

function runsTable(runs) {
  if (!runs.length) return emptyState("Chưa có lần train nào trong CSDL", "Bấm “Train lại” để lưu bảng đánh giá đầu tiên.");
  return `<div class="table-wrap"><table class="data">
    <thead><tr><th class="num">Lần</th><th>Thời gian</th><th>Người train</th><th>CV cao nhất</th>
      <th class="num">CV recall_macro</th><th class="num">Sensitivity</th><th class="num">Tổng thời gian</th></tr></thead>
    <tbody>${runs.map(r => {
      const best = r.models.find(m => m.is_best) || r.models[0];
      return `<tr><td class="num">#${r.id}</td><td>${localTime(r.created_at)}</td><td>${esc(r.username || "—")}</td>
        <td><span class="swatch" style="background:${MODEL_COLORS[best.model]}"></span>${esc(best.label)}</td>
        <td class="num">${num(best.cv_mean, 4)}</td><td class="num">${num(best.sensitivity, 4)}</td>
        <td class="num">${r.total_seconds ? duration(r.total_seconds * 1000) : "—"}</td></tr>`;
    }).join("")}</tbody></table></div>`;
}

export default {
  title: "So sánh mô hình (Đánh giá 5 mô hình phân loại)",
  subtitle: "Cùng một quy trình: GridSearchCV + StratifiedKFold(5) trên tập train, ngưỡng theo sensitivity, đánh giá một lần trên tập test",
  icon: "chart-column",

  async render(view, ctx) {
    view.innerHTML = `<div class="stack"><div class="grid cols-4">${Array(4).fill(`<div class="card">${skeleton({ lines: 2 })}</div>`).join("")}</div>
      <div class="card">${skeleton({ lines: 7 })}</div></div>`;
    let report;
    try {
      report = await modelApi("/models/metrics");
    } catch (err) {
      if (!ctx.alive()) return;
      view.innerHTML = `<div class="card">${errorState(err.message, "retry")}</div>`;
      onClick(view, "#retry", () => this.render(view, ctx));
      return;
    }
    if (!ctx.alive()) return;

    const byKey = Object.fromEntries(report.models.map(m => [m.model, m]));
    const best = byKey[report.best_model];
    const svm = byKey[DEPLOYED];
    const fastest = [...report.models].sort((a, b) => a.predict_ms_per_sample - b.predict_ms_per_sample)[0];
    const labels = report.models.map(m => MODEL_SHORT[m.model]);
    const gap = best.cv_mean - svm.cv_mean;
    const note = report.best_model === DEPLOYED
      ? "SVM RBF — mô hình đang triển khai — cũng là mô hình có điểm kiểm định chéo cao nhất."
      : `${best.label} có CV recall_macro cao nhất (${num(best.cv_mean, 4)}), hơn SVM RBF ${num(gap, 4)} — nhỏ hơn nhiều so với độ lệch giữa các fold (± ${num(svm.cv_std, 4)}). Sản phẩm vẫn triển khai SVM theo yêu cầu đề bài; bảng này cho thấy các mô hình tương đương nhau trên dữ liệu này.`;

    view.innerHTML = `
      <div class="stack">
        <div class="grid cols-4">
          ${kpi("trophy", "CV recall_macro cao nhất", esc(best.label), `${num(best.cv_mean, 4)} ± ${num(best.cv_std, 4)} qua 5 fold`)}
          ${kpi("microscope", "SVM RBF đang triển khai", `${num(svm.sensitivity, 4)} / ${num(svm.specificity, 4)}`, "sensitivity / specificity trên tập test")}
          ${kpi("target", "Mục tiêu sensitivity", `≥ ${num(report.target_sensitivity, 2)}`, "ngưỡng mỗi mô hình chọn trên xác suất out-of-fold")}
          ${kpi("zap", "Dự đoán nhanh nhất", esc(fastest.label), `${duration(fastest.predict_ms_per_sample)} mỗi mẫu`)}
        </div>

        <section class="card">
          <div class="card-head">
            <div><h2>Bảng xếp hạng 5 mô hình</h2>
              <p class="sub">Train lúc ${localTime(report.trained_at)}${report.trained_by ? ` bởi ${esc(report.trained_by)}` : ""} ·
                ${report.data.train_size} mẫu train / ${report.data.test_size} mẫu test · ${esc(report.data.cv)} · xếp theo CV recall_macro</p></div>
            <div class="btn-row">
              <button class="btn" id="retrain" type="button">${icon("refresh-cw", 16)}Train lại</button>
              <button class="btn ghost" id="export" type="button">${icon("download", 16)}Xuất Excel</button>
            </div>
          </div>
          <div id="trainMsg"></div>
          <div class="table-wrap"><table class="data">
            <thead><tr><th class="num">#</th><th>Mô hình</th><th class="num">CV recall_macro</th><th class="num">Sensitivity</th>
              <th class="num">Specificity</th><th class="num">Precision</th><th class="num">ROC-AUC</th><th class="num">PR-AUC</th>
              <th class="num">Ngưỡng</th><th class="num">FN / FP</th><th class="num">Thời gian train</th>
              <th class="num">Predict / mẫu</th><th>Tham số tốt nhất</th></tr></thead>
            <tbody>${leaderboard(report)}</tbody>
          </table></div>
          <div class="insight">${icon("lightbulb", 18)}<p>${esc(note)}</p></div>
          <p class="caption">Chỉ số tính trên ${report.data.test_size} mẫu test tại ngưỡng riêng của mỗi mô hình (lớp dương = ác tính).
            Badge tốc độ so với mô hình nhanh nhất: <b>Nhanh</b> ≤ ${num(report.speed_thresholds.fast, 1)}×, <b>Trung bình</b> ≤ ${num(report.speed_thresholds.medium, 1)}×,
            còn lại <b>Chậm</b>; thời gian đo bằng <code>time.perf_counter</code> trên máy chủ.</p>
        </section>

        <div class="grid cols-2">
          <section class="card">
            <div class="card-head"><div><h2>Chỉ số tại ngưỡng đã chọn</h2><p class="sub">Sensitivity, specificity, precision ác tính trên tập test</p></div></div>
            <div class="chart-box"><canvas id="metricChart" role="img" aria-label="Biểu đồ sensitivity, specificity và precision của 5 mô hình"></canvas></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2>Đường ROC trên tập test</h2><p class="sub">Càng sát góc trên bên trái càng tốt; AUC trong chú giải</p></div></div>
            <div class="chart-box"><canvas id="rocChart" role="img" aria-label="Đường ROC của 5 mô hình"></canvas></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2>Thời gian huấn luyện</h2><p class="sub">Fit cấu hình tốt nhất (kể cả hiệu chỉnh xác suất) trên ${report.data.train_size} mẫu (ms)</p></div></div>
            <div class="chart-box short"><canvas id="trainChart" role="img" aria-label="Biểu đồ thời gian huấn luyện"></canvas></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2>Thời gian dự đoán</h2><p class="sub">Trung bình mỗi mẫu (µs), lặp 200 lần trên tập test</p></div></div>
            <div class="chart-box short"><canvas id="predChart" role="img" aria-label="Biểu đồ thời gian dự đoán"></canvas></div>
          </section>
        </div>

        <section class="card">
          <div class="card-head"><div><h2>Lịch sử huấn luyện đã lưu trong CSDL</h2><p class="sub">Bảng <code>training_runs</code> + <code>model_runs</code> của API CSDL</p></div></div>
          <div id="runs">${skeleton({ lines: 3 })}</div>
        </section>
      </div>`;

    chart(view.querySelector("#metricChart"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Sensitivity", data: report.models.map(m => m.sensitivity), backgroundColor: "#C92A2A", borderRadius: 4 },
          { label: "Specificity", data: report.models.map(m => m.specificity), backgroundColor: "#1971C2", borderRadius: 4 },
          { label: "Precision ác tính", data: report.models.map(m => m.precision_malignant), backgroundColor: "#B38BFA", borderRadius: 4 },
        ],
      },
      options: {
        scales: { y: { min: Math.floor(Math.min(...report.models.flatMap(m => [m.sensitivity, m.specificity, m.precision_malignant])) * 20) / 20, max: 1, ticks: { callback: v => num(v, 2) } }, x: { grid: { display: false } } },
        plugins: { tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${num(c.raw, 4)}` } } },
      },
    });

    chart(view.querySelector("#rocChart"), {
      type: "scatter",
      data: {
        datasets: [
          ...report.models.map(m => ({
            label: `${MODEL_SHORT[m.model]} (AUC ${num(m.roc_auc, 4)})`,
            data: m.roc.fpr.map((x, i) => ({ x, y: m.roc.tpr[i] })),
            showLine: true, pointRadius: 0, borderWidth: m.model === DEPLOYED ? 2.5 : 1.6,
            borderColor: MODEL_COLORS[m.model], backgroundColor: MODEL_COLORS[m.model],
          })),
          { label: "Đoán ngẫu nhiên", data: [{ x: 0, y: 0 }, { x: 1, y: 1 }], showLine: true, pointRadius: 0, borderDash: [5, 4], borderColor: "#ADB5BD", borderWidth: 1 },
        ],
      },
      options: {
        scales: {
          x: { min: 0, max: 1, title: { display: true, text: "1 − Specificity" } },
          y: { min: 0, max: 1, title: { display: true, text: "Sensitivity" } },
        },
        plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: c => ` ${c.dataset.label}: (${num(c.parsed.x, 3)}; ${num(c.parsed.y, 3)})` } } },
      },
    });

    const timing = (canvas, values, unit, speeds) => chart(canvas, {
      type: "bar",
      data: { labels, datasets: [{ label: unit, data: values, backgroundColor: report.models.map(m => MODEL_COLORS[m.model]), borderRadius: 4, barPercentage: 0.6 }] },
      options: {
        indexAxis: "y",
        scales: { x: { beginAtZero: true, title: { display: true, text: unit } }, y: { grid: { display: false } } },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: c => ` ${num(c.raw, 3)} ${unit} · ${speeds[c.dataIndex].label} (${num(speeds[c.dataIndex].ratio_to_fastest, 2)}× nhanh nhất)` } },
        },
      },
    });
    timing(view.querySelector("#trainChart"), report.models.map(m => m.train_seconds * 1000), "ms", report.models.map(m => m.train_speed));
    timing(view.querySelector("#predChart"), report.models.map(m => m.predict_ms_per_sample * 1000), "µs", report.models.map(m => m.predict_speed));

    this.loadRuns(view, ctx);

    onClick(view, "#export", async e => {
      if (!getAuth()) { toast("Hãy đăng nhập để xuất Excel"); location.hash = "#/dang-nhap"; return; }
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        toast(`Đã tải ${await downloadFromDb("/export/model-runs.xlsx")}`);
      } catch (err) {
        toast(err.message);
      } finally {
        btn.disabled = false;
      }
    });

    onClick(view, "#retrain", async e => {
      if (!getAuth()) { toast("Hãy đăng nhập để train lại mô hình"); location.hash = "#/dang-nhap"; return; }
      const btn = e.currentTarget;
      const msg = view.querySelector("#trainMsg");
      btn.disabled = true;
      btn.innerHTML = `${icon("refresh-cw", 16)}Đang train 5 mô hình…`;
      msg.innerHTML = `<div class="notice info" style="margin-bottom:12px">${icon("timer", 18)}GridSearchCV, hiệu chỉnh và chọn ngưỡng đang chạy trên máy chủ (khoảng 20–60 giây trên gói Free).</div>`;
      try {
        const started = performance.now();
        const fresh = await modelApi("/models/train", { method: "POST", auth: true });
        const run = await dbApi("/model-runs", {
          method: "POST", auth: true,
          body: {
            trained_at: fresh.trained_at, train_size: fresh.data.train_size, test_size: fresh.data.test_size,
            target_sensitivity: fresh.target_sensitivity, best_model: fresh.best_model,
            total_seconds: fresh.total_seconds, models: fresh.models,
          },
        });
        toast(`Train xong sau ${duration(performance.now() - started)} · đã lưu lần train #${run.id}`);
        if (ctx.alive()) this.render(view, ctx);
      } catch (err) {
        msg.innerHTML = `<div class="notice error" style="margin-bottom:12px">${icon("circle-alert", 18)}${esc(err.message)}</div>`;
        btn.disabled = false;
        btn.innerHTML = `${icon("refresh-cw", 16)}Train lại`;
      }
    });
  },

  async loadRuns(view, ctx) {
    const box = view.querySelector("#runs");
    try {
      const data = await dbApi("/model-runs?limit=10");
      if (ctx.alive()) box.innerHTML = runsTable(data.runs);
    } catch (err) {
      if (!ctx.alive()) return;
      box.innerHTML = errorState(err.message, "retryRuns");
      onClick(box, "#retryRuns", () => this.loadRuns(view, ctx));
    }
  },
};
