// Overview page, laid out like the reference dashboard. Every number comes from
// GET /dataset/summary (computed from load_breast_cancer) and GET /classes.
import { modelApi, modelAsset } from "../api.js";
import { chart } from "../charts.js";
import { icon } from "../icons.js";
import { CLASS_COLORS, CLASS_KEYS, CLASS_VI, errorState, esc, num, onClick, skeleton } from "../ui.js";

const other = key => (key === "malignant" ? "benign" : "malignant");

function caption(info) {
  return `<p class="caption">Nguồn: ${esc(info.author)}, ${esc(info.license)},
    <a href="${esc(info.source_url)}" target="_blank" rel="noopener">${esc(info.source_url.replace("https://", ""))}</a></p>`;
}

function loading(view) {
  view.innerHTML = `
    <div class="grid overview">
      <div class="card area-photo">${skeleton({ block: true, lines: 1 })}</div>
      <div class="card area-parts">${skeleton({ lines: 6 })}</div>
      <div class="card area-donut">${skeleton({ block: true, lines: 0 })}</div>
      <div class="area-side"><div class="card">${skeleton({ lines: 6 })}</div><div class="card">${skeleton({ lines: 4 })}</div></div>
    </div>`;
}

export default {
  title: "Chẩn đoán minh hoạ ung thư vú",
  subtitle: "Khám phá bộ dữ liệu Breast Cancer Wisconsin: hai loại khối u và các đặc trưng tách chúng",
  icon: "layout-dashboard",

  async render(view, ctx) {
    loading(view);
    let summary, classes;
    try {
      [summary, classes] = await Promise.all([modelApi("/dataset/summary"), modelApi("/classes")]);
    } catch (err) {
      if (!ctx.alive()) return;
      view.innerHTML = `<div class="card">${errorState(err.message, "retry")}</div>`;
      onClick(view, "#retry", () => this.render(view, ctx));
      return;
    }
    if (!ctx.alive()) return;

    const key = ctx.cls;
    const s = summary.classes[key];
    const o = summary.classes[other(key)];
    const info = classes.classes.find(c => c.key === key);
    const vi = summary.feature_vi;
    const name = CLASS_VI[key];

    // Bars: this class's mean next to the other class's, both scaled to the larger of the two.
    const bars = s.key_features.map(f => {
      const a = s.stats[f].mean;
      const b = o.stats[f].mean;
      const top = Math.max(a, b) || 1;
      return `
        <div>
          <div class="bar-label"><span>${esc(vi[f])}</span><span>${num(a, 3)} · nhóm kia ${num(b, 3)}</span></div>
          <div class="track" role="img" aria-label="${esc(vi[f])}: ${num(a, 3)} so với ${num(b, 3)}">
            <div class="fill" style="width:${(a / top) * 100}%;background:${CLASS_COLORS[key]}"></div>
          </div>
          <div class="track" style="height:5px;margin-top:3px">
            <div class="fill" style="width:${(b / top) * 100}%;background:${CLASS_COLORS[other(key)]};opacity:.55"></div>
          </div>
        </div>`;
    }).join("");

    const statsRows = s.key_features.map(f => `
      <tr><td>${esc(vi[f])}</td>
        <td class="num">${num(s.stats[f].mean, 4)}</td><td class="num">${num(s.stats[f].std, 4)}</td>
        <td class="num">${num(s.stats[f].min, 4)}</td><td class="num">${num(s.stats[f].max, 4)}</td></tr>`).join("");

    const legend = CLASS_KEYS.map(k => `
      <li><span class="dot" style="background:${CLASS_COLORS[k]}"></span><span>${CLASS_VI[k]}</span>
        <b>${summary.classes[k].count} (${num(summary.classes[k].share, 1)}%)</b></li>`).join("");

    const f = s.top_features[0];
    const remark = `Đặc trưng tách hai nhóm rõ nhất là ${vi[f]}: trung bình ${num(s.stats[f].mean, 3)} ở nhóm ${name.toLowerCase()} `
      + `so với ${num(o.stats[f].mean, 3)} ở nhóm ${CLASS_VI[other(key)].toLowerCase()}. `
      + (s.n_zero_concavity
        ? `${s.n_zero_concavity} mẫu của nhóm này có độ lõm bằng đúng 0 — vì vậy API cho phép giá trị 0 ở sáu đặc trưng concavity.`
        : "Không mẫu nào của nhóm này có độ lõm bằng 0.");

    view.innerHTML = `
      <div class="grid overview">
        <section class="card area-photo">
          <div class="card-head"><div><h2>Tế bào ${esc(name.toLowerCase())}</h2><p class="sub">${esc(info.example)}</p></div></div>
          <img class="photo" src="${esc(modelAsset(info.image_url))}" alt="${esc(info.alt_text)}">
          ${caption(info)}
          <p style="margin:8px 0 0;font-size:13px">${esc(info.description)}</p>
        </section>

        <section class="card area-parts">
          <div class="card-head"><div><h2>So sánh đặc trưng chính</h2>
            <p class="sub">Thanh đậm: nhóm ${esc(name.toLowerCase())} · thanh mảnh: nhóm ${esc(CLASS_VI[other(key)].toLowerCase())} (cùng thang)</p></div></div>
          <div class="bars">${bars}</div>
        </section>

        <section class="card area-donut">
          <div class="band-title">Tỷ lệ hai loại khối u trong ${summary.n_samples} mẫu</div>
          <div class="donut-wrap">
            <div class="donut-box">
              <canvas id="donut" role="img" aria-label="Biểu đồ tròn: ${summary.classes.malignant.count} ác tính, ${summary.classes.benign.count} lành tính"></canvas>
              <div class="donut-center"><div><b>${summary.n_samples}</b><span>mẫu · ${summary.n_features} đặc trưng</span></div></div>
            </div>
            <ul class="legend">${legend}</ul>
          </div>
          <div class="table-wrap" style="margin-top:16px">
            <table class="data">
              <caption class="sr-only">Thống kê mô tả của nhóm ${esc(name)}</caption>
              <thead><tr><th>Đặc trưng (nhóm ${esc(name.toLowerCase())})</th><th class="num">Trung bình</th><th class="num">Độ lệch chuẩn</th><th class="num">Nhỏ nhất</th><th class="num">Lớn nhất</th></tr></thead>
              <tbody>${statsRows}</tbody>
            </table>
          </div>
        </section>

        <aside class="area-side">
          <section class="card">
            <div class="band-title">Kết quả phân tích</div>
            <div class="kv">
              <div class="kv-row">${icon("microscope", 24)}<div><div class="kv-label">Loại khối u</div><div class="kv-value" style="color:${CLASS_COLORS[key]}">${esc(name)}</div></div></div>
              <div class="kv-row">${icon("chart-pie", 24)}<div><div class="kv-label">Số mẫu trong dữ liệu</div><div class="kv-value">${s.count} / ${summary.n_samples} (${num(s.share, 1)}%)</div></div></div>
              <div class="kv-row">${icon("ruler", 24)}<div><div class="kv-label">Bán kính nhân trung bình (mean radius)</div><div class="kv-value">${num(s.stats["mean radius"].mean, 3)}</div></div></div>
              <div class="kv-row">${icon("target", 24)}<div><div class="kv-label">Số điểm lõm xấu nhất (worst concave points)</div><div class="kv-value">${num(s.stats["worst concave points"].mean, 4)}</div></div></div>
            </div>
          </section>
          <section class="card">
            <h2 style="margin-bottom:12px">Đặc điểm nổi bật</h2>
            <ul class="bullets">${s.highlights.map(h => `<li>${esc(h)}</li>`).join("")}</ul>
          </section>
          <section class="card tinted remark">
            ${icon("lightbulb", 24)}
            <div><h3>Nhận xét</h3><p>${esc(remark)}</p></div>
          </section>
        </aside>
      </div>
      <p class="caption" style="margin-top:14px">Dữ liệu: <code>${esc(summary.source)}</code> · ${summary.n_samples} mẫu ·
        số liệu tính trực tiếp qua API <code>/dataset/summary</code>. Chọn loại khối u ở thanh bên để đổi góc nhìn.</p>`;

    chart(view.querySelector("#donut"), {
      type: "doughnut",
      data: {
        labels: CLASS_KEYS.map(k => CLASS_VI[k]),
        datasets: [{
          data: CLASS_KEYS.map(k => summary.classes[k].count),
          backgroundColor: CLASS_KEYS.map(k => CLASS_COLORS[k]),
          borderColor: "#fff", borderWidth: 2, hoverOffset: 6,
        }],
      },
      options: {
        cutout: "58%",
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: c => ` ${c.label}: ${c.parsed} mẫu (${num(summary.classes[CLASS_KEYS[c.dataIndex]].share, 1)}%)` } },
        },
      },
    });
  },
};
