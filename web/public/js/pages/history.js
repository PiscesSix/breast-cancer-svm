// Prediction history of the logged-in user: filters, pagination, confirmed labels, Excel export.
import { dbApi, downloadFromDb, query } from "../api.js?v=20261005";
import { getAuth } from "../auth.js?v=20261005";
import { icon } from "../icons.js?v=20261005";
import {
  CLASS_COLORS, CLASS_VI, duration, emptyState, errorState, esc, localTime, loginPrompt, MODEL_COLORS, MODEL_SHORT, num,
  onClick, skeleton, toast,
} from "../ui.js?v=20261005";

const filters = { page: 1, page_size: 10, model: "", date_from: "", date_to: "" };

function labelCell(label) {
  return `<span class="class-dot" style="background:${CLASS_COLORS[label]}"></span>${CLASS_VI[label]}`;
}

function row(p) {
  const options = ["", "malignant", "benign"].map(v =>
    `<option value="${v}" ${p.actual_label === (v || null) ? "selected" : ""}>${v ? CLASS_VI[v] : "Chưa có"}</option>`).join("");
  const verdict = p.correct === null ? "—"
    : p.correct ? `<span class="badge fast">${icon("circle-check", 12)}Đúng</span>`
      : `<span class="badge slow">${icon("triangle-alert", 12)}Sai</span>`;
  return `<tr>
    <td>${localTime(p.created_at)}</td>
    <td><span class="swatch" style="background:${MODEL_COLORS[p.model] || "#1E2A5A"}"></span>${esc(MODEL_SHORT[p.model] || p.model)}</td>
    <td>${esc(p.sample_id || "nhập tay")}</td>
    <td><b>${labelCell(p.predicted_label)}</b></td>
    <td class="num">${num(p.probability_malignant, 4)}</td>
    <td class="num">${num(p.threshold, 4)}</td>
    <td><select class="cell-input" style="width:120px" data-id="${p.id}" aria-label="Nhãn thật của bản ghi ${p.id}">${options}</select></td>
    <td>${verdict}</td>
    <td class="num">${duration(p.runtime_ms)}</td>
  </tr>`;
}

export default {
  title: "Lịch sử dự đoán",
  subtitle: "Chỉ hiển thị dự đoán của tài khoản đang đăng nhập — lọc theo ngày và mô hình, ghi nhãn thật, xuất Excel",
  icon: "history",

  async render(view, ctx) {
    const auth = getAuth();
    if (!auth) {
      view.innerHTML = `<div class="card">${loginPrompt("Lịch sử dự đoán gắn với tài khoản. Đăng nhập (hoặc dùng tài khoản demo / demo123) để xem.")}</div>`;
      return;
    }

    view.innerHTML = `
      <section class="card">
        <div class="card-head">
          <div><h2>Dự đoán của ${esc(auth.user.username)}</h2><p class="sub" id="summary">Đang tải…</p></div>
          <button class="btn ghost" id="export" type="button">${icon("download", 16)}Xuất Excel (theo bộ lọc)</button>
        </div>
        <form class="form-grid" id="filters" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr));align-items:end;margin-bottom:14px">
          <label class="field">Mô hình<select class="input" name="model"><option value="">Tất cả</option>
            ${Object.entries(MODEL_SHORT).map(([k, v]) => `<option value="${k}" ${filters.model === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
          <label class="field">Từ ngày<input class="input" type="date" name="date_from" value="${filters.date_from}"></label>
          <label class="field">Đến ngày<input class="input" type="date" name="date_to" value="${filters.date_to}"></label>
          <label class="field">Số dòng / trang<select class="input" name="page_size">
            ${[10, 20, 50].map(n => `<option ${filters.page_size === n ? "selected" : ""}>${n}</option>`).join("")}</select></label>
          <div class="btn-row"><button class="btn" type="submit">${icon("funnel", 16)}Lọc</button>
            <button class="btn ghost" type="button" id="clear">Xoá lọc</button></div>
        </form>
        <div id="table"></div>
        <div class="pager" id="pager"></div>
      </section>`;

    const form = view.querySelector("#filters");
    form.addEventListener("submit", e => {
      e.preventDefault();
      const data = new FormData(form);
      Object.assign(filters, {
        page: 1, model: data.get("model"), date_from: data.get("date_from"), date_to: data.get("date_to"),
        page_size: parseInt(data.get("page_size"), 10),
      });
      this.load(view, ctx);
    });
    onClick(view, "#clear", () => {
      Object.assign(filters, { page: 1, model: "", date_from: "", date_to: "" });
      this.render(view, ctx);
    });
    onClick(view, "#export", async e => {
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        const name = await downloadFromDb(`/export/predictions.xlsx${query({ model: filters.model, date_from: filters.date_from, date_to: filters.date_to })}`);
        toast(`Đã tải ${name}`);
      } catch (err) {
        toast(err.message);
      } finally {
        btn.disabled = false;
      }
    });
    await this.load(view, ctx);
  },

  async load(view, ctx) {
    const table = view.querySelector("#table");
    const pager = view.querySelector("#pager");
    table.innerHTML = skeleton({ lines: 6 });
    pager.innerHTML = "";
    let data;
    try {
      data = await dbApi(`/predictions${query(filters)}`, { auth: true });
    } catch (err) {
      if (!ctx.alive()) return;
      table.innerHTML = errorState(err.message, "retry");
      onClick(table, "#retry", () => this.load(view, ctx));
      return;
    }
    if (!ctx.alive()) return;

    const filtered = filters.model || filters.date_from || filters.date_to;
    const accuracy = data.n_labelled ? ` · đúng ${data.n_correct}/${data.n_labelled} bản ghi có nhãn thật` : "";
    view.querySelector("#summary").textContent = `${data.total} bản ghi${filtered ? " khớp bộ lọc" : ""}${accuracy} · lưu trong bảng predictions`;
    if (!data.items.length) {
      table.innerHTML = filtered
        ? emptyState("Không có bản ghi khớp bộ lọc", "Thử bỏ bớt điều kiện lọc.")
        : emptyState("Chưa có dự đoán nào", "Vào Chẩn đoán SVM, dự đoán rồi bấm “Lưu vào lịch sử”.",
          `<a class="btn" href="#/chan-doan">${icon("microscope", 16)}Mở Chẩn đoán SVM</a>`);
      return;
    }
    table.innerHTML = `<div class="table-wrap"><table class="data">
      <thead><tr><th>Thời gian</th><th>Mô hình</th><th>Mẫu</th><th>Dự đoán</th><th class="num">P(ác tính)</th>
        <th class="num">Ngưỡng</th><th>Nhãn thật</th><th>Đúng / sai</th><th class="num">Thời gian chạy</th></tr></thead>
      <tbody>${data.items.map(row).join("")}</tbody></table></div>`;
    pager.innerHTML = `
      <span>Trang ${data.page}/${data.pages} · ${data.total} bản ghi</span>
      <div class="btn-row">
        <button class="btn ghost small" id="prev" ${data.page <= 1 ? "disabled" : ""}>${icon("chevron-left", 14)}Trước</button>
        <button class="btn ghost small" id="next" ${data.page >= data.pages ? "disabled" : ""}>Sau${icon("chevron-right", 14)}</button>
      </div>`;
    onClick(pager, "#prev", () => { filters.page -= 1; this.load(view, ctx); });
    onClick(pager, "#next", () => { filters.page += 1; this.load(view, ctx); });

    table.querySelectorAll("select.cell-input").forEach(el => {
      el.addEventListener("change", async () => {
        try {
          await dbApi(`/predictions/${el.dataset.id}`, { method: "PATCH", auth: true, body: { actual_label: el.value || null } });
          toast("Đã cập nhật nhãn thật");
          this.load(view, ctx);
        } catch (err) {
          toast(err.message);
        }
      });
    });
  },
};
