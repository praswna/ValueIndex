// Shared "context indicator" detail popup (thermometer + summary): stats
// row, full history with guide lines + recession shading, definition and
// interpretation. Context series carry no valuation rating by design.

import { fmt, fmtSigned } from "./data.js";
import { baseLayout, render, lineTrace, recessionShapes, hline } from "./charts.js";
import { asofIndex, shiftDateStr, percentileRanks } from "./stats.js";
import { openModal } from "./modal.js";

// context key -> loader source name, for the sources that datacenter IPs
// block (these fall back to approximated sample data on the deployed site).
export const CTX_SOURCE = {
  aaii_spread: "aaii_sentiment",
  margin_debt: "finra_margin_debt",
};

export function isApprox(meta, sourceName) {
  const st = meta && meta.sources && meta.sources[sourceName];
  return st !== undefined && st !== "live" && st !== "snapshot" && st !== "cached";
}

export function approxBadge() {
  return '<span class="badge" style="background:#898781">⚠️ 근사</span>';
}

export function showContextPopup(registry, overview, context, key, meta = null) {
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

  const approx = isApprox(meta, CTX_SOURCE[key]);
  openModal(`
    <h2 style="margin:0 0 2px">${m.label_ko || key} ${approx ? approxBadge() : ""}</h2>
    <div class="metric-value">${fmt(last, m.unit, registry)} ${m.unit || ""}</div>
    ${approx ? `<div class="box box-warn note-sm">이 소스는 자동 갱신 IP가 차단되어
      현재 <b>근사 샘플</b>이 표시되고 있습니다. 집 PC에서 로컬 수집기를 돌리면
      실데이터로 교체됩니다.</div>` : ""}
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
