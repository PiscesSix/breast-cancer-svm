// Small rendering helpers shared by every page: escaping, number format, states, badges.
import { icon } from "./icons.js";

// Chart palette from the reference design; one fixed colour per model.
export const PALETTE = ["#6C63FF", "#B38BFA", "#5CB85C", "#6FA8DC", "#F4A261"];
export const MODEL_KEYS = ["svm_rbf", "svm_linear", "logreg", "knn", "random_forest"];
export const MODEL_SHORT = {
  svm_rbf: "SVM RBF", svm_linear: "SVM tuyến tính", logreg: "Logistic", knn: "KNN", random_forest: "Random Forest",
};
export const MODEL_COLORS = Object.fromEntries(MODEL_KEYS.map((k, i) => [k, PALETTE[i]]));
export const CLASS_KEYS = ["benign", "malignant"];
// Red / blue stay distinct for colour-blind readers (red / green does not); used by every class chart.
export const CLASS_COLORS = { malignant: "#E5484D", benign: "#2E9E5B" };
export const CLASS_VI = { malignant: "Ác tính", benign: "Lành tính" };
export const WARNING = "Chỉ phục vụ mục đích giáo dục — không thay thế chẩn đoán y khoa.";

export const cap = s => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function num(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return Number(value).toLocaleString("vi-VN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Format a duration in milliseconds with a sensible unit. */
export function duration(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1) return `${num(ms * 1000, 1)} µs`;
  if (ms < 1000) return `${num(ms, 2)} ms`;
  return `${num(ms / 1000, 2)} s`;
}

export function localTime(utcIso) {
  if (!utcIso) return "—";
  return new Date(utcIso).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "medium" });
}

export function speedBadge(speed) {
  if (!speed) return "";
  const title = `Gấp ${num(speed.ratio_to_fastest, 2)} lần mô hình nhanh nhất`;
  const ico = speed.tier === "fast" ? "zap" : speed.tier === "medium" ? "timer" : "triangle-alert";
  return `<span class="badge ${speed.tier}" title="${title}">${icon(ico, 12)}${esc(speed.label)}</span>`;
}

export function skeleton({ lines = 3, block = false } = {}) {
  const rows = Array.from({ length: lines }, (_, i) =>
    `<div class="skeleton sk-line" style="width:${90 - i * 12}%"></div>`).join("");
  return `${block ? '<div class="skeleton sk-block"></div>' : ""}${rows}`;
}

export function emptyState(title, text, action = "") {
  return `<div class="state">${icon("inbox", 34)}<b>${esc(title)}</b><p>${text}</p>${action}</div>`;
}

export function errorState(message, retryId = "") {
  const retry = retryId ? `<button class="btn ghost small" id="${retryId}">${icon("refresh-cw", 14)}Thử lại</button>` : "";
  return `<div class="state error">${icon("circle-alert", 34)}<b>Không tải được dữ liệu</b><p>${esc(message)}</p>${retry}</div>`;
}

export function loginPrompt(text) {
  return emptyState("Cần đăng nhập", text,
    `<a class="btn" href="#/dang-nhap">${icon("log-in", 16)}Đăng nhập / Đăng ký</a>`);
}

let toastTimer;
export function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

/** Wire a retry button rendered by errorState(). */
export function onClick(root, selector, fn) {
  const el = root.querySelector(selector);
  if (el) el.addEventListener("click", fn);
  return el;
}
