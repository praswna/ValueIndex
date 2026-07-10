// Shared "context indicator" detail popup (thermometer + summary): stats
// row, full history with guide lines + recession shading, definition and
// interpretation. Context series carry no valuation rating by design.

import { fmt, fmtSigned } from "./data.js";
import { baseLayout, render, lineTrace, recessionShapes, hline } from "./charts.js";
import { asofIndex, shiftDateStr, percentileRanks } from "./stats.js";
import { openModal } from "./modal.js";

export function showContextPopup(registry, overview, context, key) {
  const m = registry.indicators[key] || {};
  const s = context[key];
  const values = s.values, dates = s.dates;
  const last = values[values.length - 1];
  const yi = asofIndex(dates, shiftDateStr(dates[dates.length - 1], -1));
  const delta = yi >= 0 ? last - values[yi] : null;
  const pct = percentileRanks(values)[values.length - 1];
  const lo = Math.min(...values.filter((v) => v !== null));
  const hi = Math.max(...values.filter((v) => v !== null));
  const guides = registry.guide_lines[key] || [];

  openModal(`
    <h2 style="margin:0 0 2px">${m.label_ko || key}</h2>
    <div class="metric-value">${fmt(last, m.unit, registry)} ${m.unit || ""}</div>
    <div class="modal-stats">
      <div>1년 변화<br><b>${delta === null ? "-" : fmtSigned(delta, 1)}</b></div>
      <div>역사 백분위<br><b>${pct.toFixed(0)}/100</b></div>
      <div>역사 범위<br><b>${fmt(lo, m.unit, registry)}~${fmt(hi, m.unit, registry)}</b></div>
      <div>데이터 시작<br><b>${dates[0].slice(0, 4)}년</b></div>
    </div>
    <div id="cp-chart" class="chart"></div>
    <p class="modal-desc">${m.what_ko || ""}</p>
    <p class="caption">${m.interpret_ko || ""}</p>
    <p class="caption">출처: ${m.source || "-"} · 등급 없는 참고 지표입니다.${
      guides.length ? " 빨간 점선 = 관례적 기준선." : ""} 회색 음영 = 미국 경기침체.</p>`);

  const shapes = [
    ...guides.map((y) => hline(y, "#c22f2f")),
    ...recessionShapes(registry, overview.recessions, dates[0]),
  ];
  render(document.getElementById("cp-chart"),
    [lineTrace(dates, values, m.label_ko || key, registry.series_colors[key])],
    baseLayout(registry, {
      showlegend: false, shapes,
      margin: { l: 45, r: 10, t: 8, b: 30 },
      yaxis: { title: { text: m.unit }, gridcolor: registry.chrome.grid },
    }, 280));
}
