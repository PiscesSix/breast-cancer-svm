// "Điểm nổi bật": the project's key results at a glance and shortcuts to the features worth demoing.
// Every number comes from GET /metadata, /models/metrics and /dataset/summary.
import { modelApi } from "../api.js";
import { icon } from "../icons.js";
import { errorState, esc, num, onClick, skeleton } from "../ui.js";

const FEATURES = [
  ["chan-doan", "sliders-horizontal", "Thanh trượt ngưỡng", "Kéo ngưỡng P(ác tính): nhãn, donut và 4 chỉ số trên tập test đổi ngay, không gọi lại API."],
  ["phan-tich", "trending-up", "Phân tích nâng cao", "Ma trận nhầm lẫn, đường ROC / Precision–Recall có điểm vận hành, permutation importance, PCA 2D."],
  ["so-sanh", "chart-no-axes-column", "So sánh 5 mô hình", "Cùng quy trình GridSearchCV + ngưỡng theo sensitivity; train lại và xuất Excel."],
  ["du-lieu-sql", "database", "Dữ liệu SQL", "Xem trực tiếp CSDL (bảng wdbc 569 mẫu, lịch sử) và chạy câu SELECT chỉ đọc."],
  ["lich-su", "clock", "Lịch sử dự đoán", "Lưu dự đoán theo tài khoản, ghi nhãn thật, lọc và xuất Excel."],
];

export default {
  title: "Điểm nổi bật",
  subtitle: "Kết quả chính của mô hình SVM đang triển khai và các tính năng đáng xem nhất",
  icon: "star",

  async render(view, ctx) {
    view.innerHTML = `<div class="grid cols-4">${Array(4).fill(`<div class="card">${skeleton({ lines: 2 })}</div>`).join("")}</div>`;
    let meta, report, summary;
    try {
      [meta, report, summary] = await Promise.all([modelApi("/metadata"), modelApi("/models/metrics"), modelApi("/dataset/summary")]);
    } catch (err) {
      if (!ctx.alive()) return;
      view.innerHTML = `<div class="card">${errorState(err.message, "retry")}</div>`;
      onClick(view, "#retry", () => this.render(view, ctx));
      return;
    }
    if (!ctx.alive()) return;

    const t = meta.test_metrics;
    const svm = report.models.find(m => m.model === "svm_rbf");
    const best = report.models.find(m => m.model === report.best_model);
    const kpis = [
      ["target", "Sensitivity (test)", num(t.sensitivity, 4), `mục tiêu ≥ ${num(meta.target_sensitivity, 2)} · ngưỡng ${num(meta.threshold_malignant, 4)}`],
      ["shield-check", "Specificity (test)", num(t.specificity, 4), `precision ác tính ${num(t.precision_malignant, 4)}`],
      ["activity", "ROC-AUC (test)", num(t.roc_auc, 4), `PR-AUC ${num(t.pr_auc, 4)}`],
      ["database", "Dữ liệu", `${summary.n_samples} mẫu`, `${summary.classes.malignant.count} ác tính · ${summary.classes.benign.count} lành tính · ${summary.n_features} đặc trưng`],
    ];
    let bestNote = "SVM (RBF) có CV recall_macro cao nhất trong 5 mô hình đã so sánh.";
    if (best && svm && best.model !== svm.model) {
      const gap = best.cv_mean - svm.cv_mean;
      bestNote = `Theo CV recall_macro, ${esc(best.label)} cao nhất (${num(best.cv_mean, 4)}), hơn SVM (RBF) ${num(gap, 4)}`
        + (gap < svm.cv_std ? ` — nhỏ hơn độ lệch chuẩn CV của SVM (${num(svm.cv_std, 4)}).` : ".")
        + " Đề bài yêu cầu triển khai SVM.";
    }

    view.innerHTML = `
      <div class="stack">
        <div class="grid cols-4">
          ${kpis.map(([ic, label, value, hint]) => `
            <section class="card kpi"><div class="ico">${icon(ic, 20)}</div>
              <div><div class="label">${label}</div><div class="value">${esc(value)}</div><div class="hint">${esc(hint)}</div></div></section>`).join("")}
        </div>
        <section class="card">
          <div class="card-head"><h2 class="h-icon">${icon("brain", 18)}Mô hình đang triển khai</h2></div>
          <table class="kv-table"><tbody>
            <tr><th>Mô hình</th><td>SVM (RBF) · C = ${esc(meta.best_params.svc__C)}, γ = ${esc(meta.best_params.svc__gamma)} · StandardScaler + SVC</td></tr>
            <tr><th>Ngưỡng quyết định</th><td>${num(meta.threshold_malignant, 4)} — chọn trên xác suất out-of-fold sao cho sensitivity ≥ ${num(meta.target_sensitivity, 2)}</td></tr>
            <tr><th>Dữ liệu train / test</th><td>${meta.n_train} / ${meta.n_test} mẫu (stratified, random_state = ${meta.random_state})</td></tr>
            <tr><th>So với 4 mô hình khác</th><td>${bestNote}</td></tr>
          </tbody></table>
        </section>
        <div class="grid cols-3 highlight-links">
          ${FEATURES.map(([route, ic, title, text]) => `
            <a class="card link-card" href="#/${route}">
              <h3 class="h-icon">${icon(ic, 18)}${title}</h3><p>${text}</p><span>Mở trang ${icon("chevron-right", 14)}</span>
            </a>`).join("")}
        </div>
      </div>`;
  },
};
