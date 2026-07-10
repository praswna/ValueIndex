// Shared "valuation indicator" detail popup — the full deep-dive (±σ-band
// history, distribution histogram, stats grid, analogy/formula/caveats).
// Used by both the detail page (panel preloaded) and the summary page
// (panel passed as a lazy async getter).

import { fmt, fmtSigned, ym } from "./data.js";
import { baseLayout, render, lineTrace, recessionShapes, ratingBadge } from "./charts.js";
import { cleanPairs } from "./stats.js";
import { openModal } from "./modal.js";

function bandRect(y0, y1, color) {
  return { type: "rect", xref: "paper", yref: "y", x0: 0, x1: 1, y0, y1,
           fillcolor: color, line: { width: 0 }, layer: "below" };
}

export async function showValuationPopup(registry, overview, key, getPanel) {
  const m = registry.indicators[key];
  const s = overview.summaries[key];
  const band = registry.ratings.find((r) => r.key === s.rating);
  const direction = m.higher_is_expensive ? "높을수록 고평가" : "낮을수록 고평가";
  const hl = s.half_life_months;

  const parts = [];
  if (m.analogy_ko) parts.push(`<p><b>비유하면</b> — ${m.analogy_ko}</p>`);
  if (m.formula_ko) parts.push(`<p><b>공식</b> — <code>${m.formula_ko}</code></p>`);
  if (m.interpret_ko) parts.push(`<p><b>해석</b> — ${m.interpret_ko}</p>`);
  if (m.caveats_ko.length) {
    parts.push("<p><b>주의할 점</b></p><ul>" +
      m.caveats_ko.map((c) => `<li>${c}</li>`).join("") + "</ul>");
  }

  openModal(`
    <h2 style="margin:0 0 2px">${m.label_ko} ${ratingBadge(registry, s.rating)}</h2>
    <div class="metric-value">${fmt(s.current, m.unit, registry)} ${m.unit}</div>
    <p class="caption" style="margin:2px 0 6px">${m.what_ko} (${direction} ·
      기준 ${ym(s.asof)} · 출처: ${m.source})</p>
    <div class="modal-stats">
      <div>역사 평균<br><b>${fmt(s.mean, m.unit, registry)}</b></div>
      <div>±1σ<br><b>${fmt(s.std, m.unit, registry)}</b></div>
      <div>고평가 백분위<br><b>${s.aligned_pctile.toFixed(0)}/100</b></div>
      <div>z (방향 정렬)<br><b>${fmtSigned(s.aligned_z)}σ</b></div>
      <div>1년 변화<br><b>${fmtSigned(s.delta_1y, 2)}</b></div>
      <div>평균회귀 반감기<br><b>${hl ? `약 ${(hl / 12).toFixed(1)}년` : "약함"}</b></div>
      <div>데이터 시작<br><b>${s.start_year}년</b></div>
      <div>역사 범위<br><b>${fmt(s.hist_min, m.unit, registry)}~${fmt(s.hist_max, m.unit, registry)}</b></div>
    </div>
    <div id="vp-history" class="chart"></div>
    <p class="caption">회색 밴드 = 역사 평균 ±1σ/±2σ · 음영 = 미국 경기침체</p>
    <h3>역사적 분포에서 현재 위치</h3>
    <div id="vp-hist" class="chart"></div>
    <div class="modal-desc">${parts.join("")}</div>`);

  const panel = await getPanel();
  const { dates, values } = cleanPairs(panel.dates, panel.series[key]);

  const shapes = [
    bandRect(s.mean - 2 * s.std, s.mean + 2 * s.std, "rgba(137,135,129,0.10)"),
    bandRect(s.mean - s.std, s.mean + s.std, "rgba(137,135,129,0.14)"),
    { type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: s.mean, y1: s.mean,
      line: { color: registry.chrome.muted, width: 1, dash: "dash" } },
    ...recessionShapes(registry, overview.recessions, dates[0]),
  ];
  render(document.getElementById("vp-history"), [
    lineTrace(dates, values, m.label_ko, registry.series_colors[key]),
    { x: [dates[dates.length - 1]], y: [values[values.length - 1]], mode: "markers",
      marker: { color: band.color, size: 10 }, name: "현재",
      hovertemplate: "현재: %{y:.2f}<extra></extra>" },
  ], baseLayout(registry, {
    shapes, showlegend: false,
    margin: { l: 45, r: 10, t: 8, b: 30 },
    yaxis: { title: { text: m.unit }, gridcolor: registry.chrome.grid },
  }, 300));

  render(document.getElementById("vp-hist"), [{
    type: "histogram", x: values, nbinsx: 60,
    marker: { color: "#9ec5f4" },
    hovertemplate: "구간 %{x}: %{y}개월<extra></extra>",
  }], baseLayout(registry, {
    hovermode: "closest", showlegend: false,
    margin: { l: 45, r: 10, t: 24, b: 34 },
    shapes: [{ type: "line", xref: "x", yref: "paper", x0: s.current, x1: s.current,
               y0: 0, y1: 1, line: { color: band.color, width: 2 } }],
    annotations: [{ x: s.current, y: 1, yref: "paper", yanchor: "bottom",
      text: `현재 (백분위 ${s.pctile.toFixed(0)})`,
      showarrow: false, font: { color: band.color } }],
    xaxis: { title: { text: m.unit }, showgrid: false,
             linecolor: registry.chrome.axis_line },
    yaxis: { title: { text: "개월 수" }, gridcolor: registry.chrome.grid },
  }, 240));
}
