// Chart.js defaults matching the dashboard, and lifetime tracking per page.
const Chart = window.Chart;
const live = new Set();

if (Chart) {
  Chart.defaults.locale = "vi-VN";
  Chart.defaults.font.family = '"Be Vietnam Pro", system-ui, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.boxHeight = 8;
  Chart.defaults.plugins.tooltip.backgroundColor = "#1E2A5A";
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.titleFont = { weight: "600" };
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.animation.duration = 350;
  applyChartTheme();
}

/** Read text / grid colours from the CSS tokens of the current theme (call again after switching theme). */
export function applyChartTheme() {
  if (!Chart) return;
  const css = getComputedStyle(document.documentElement);
  const v = name => css.getPropertyValue(name).trim();
  Chart.defaults.color = v("--muted") || "#6B7280";
  Chart.defaults.borderColor = v("--border") || "#E6E9F2";
  Chart.defaults.plugins.legend.labels.color = v("--text") || "#2E3654";
}

/** Value of a CSS custom property, e.g. cssVar("--card"). */
export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function chart(canvas, config) {
  if (!Chart) throw new Error("Chưa nạp được thư viện Chart.js");
  const existing = Chart.getChart(canvas);
  if (existing) {
    existing.destroy();
    live.delete(existing);
  }
  const c = new Chart(canvas, config);
  live.add(c);
  return c;
}

/** Destroy every chart of the previous page before rendering the next one. */
export function destroyAll() {
  live.forEach(c => c.destroy());
  live.clear();
}

export const gridColor = "#EEF0F7";
