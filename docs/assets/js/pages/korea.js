// 한국 시장: KOSPI 지수·PER/PBR/배당(σ 등급), 미국 PER 비교, 환율·금리.

import { load, fmt, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, lineTrace, ratingBadge } from "../charts.js";
import { cleanPairs, percentileRanks } from "../stats.js";

injectNav();
const { meta, registry, korea, panel, overview } =
  await load("registry", "korea", "panel", "overview");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);

if (korea.unavailable || !korea.kospi.dates.length) {
  $("unavailable").innerHTML =
    '<div class="box box-warn">현재 한국 데이터를 불러오지 못했습니다 (KRX 소스 일시 중단). ' +
    '자동 갱신이 복구되면 표시됩니다.</div>';
}

// KOSPI index
if (korea.kospi.dates.length) {
  render($("kospi-chart"),
    [lineTrace(korea.kospi.dates, korea.kospi.values, "KOSPI", "#2a78d6")],
    baseLayout(registry, { showlegend: false,
      yaxis: { title: { text: "KOSPI" }, gridcolor: registry.chrome.grid } }, 320));
}

// valuation cards + charts
const COLORS = { per: "#008300", pbr: "#4a3aa7", div_yield: "#e34948" };
const cards = [], charts = [];
for (const [key, v] of Object.entries(korea.indicators)) {
  const short = 2026 - v.start_year < 30;
  cards.push(`<div class="card">
    <div class="metric-label">${v.label_ko} (${v.unit})</div>
    <div class="metric-value">${fmt(v.current, v.unit, registry)}</div>
    <div class="metric-note">${ratingBadge(registry, v.rating)}
      역사 평균 ${fmt(v.mean, v.unit, registry)} · ${v.start_year}년~${short ? " ⚠️" : ""}</div>
  </div>`);
  charts.push(`<h3>${v.label_ko}</h3><div id="kv-${key}" class="chart"></div>`);
}
$("val-cards").innerHTML = cards.join("");
$("val-charts").innerHTML = charts.join("");
for (const [key, v] of Object.entries(korea.indicators)) {
  render($(`kv-${key}`),
    [lineTrace(v.dates, v.values, v.label_ko, COLORS[key])],
    baseLayout(registry, { showlegend: false,
      yaxis: { title: { text: v.unit }, gridcolor: registry.chrome.grid } }, 240));
}

// US vs Korea trailing PE, each as its own historical percentile
if (korea.indicators.per) {
  const kr = korea.indicators.per;
  const krPct = percentileRanks(kr.values);
  const us = cleanPairs(panel.dates, panel.series.pe);
  const usPct = percentileRanks(us.values);
  render($("compare-chart"), [
    { x: us.dates, y: usPct, mode: "lines", name: "S&P 500 PER 백분위",
      line: { color: registry.series_colors.pe, width: 2 } },
    { x: kr.dates, y: krPct, mode: "lines", name: "KOSPI PER 백분위",
      line: { color: "#eb6834", width: 2 } },
  ], baseLayout(registry, {
    yaxis: { title: { text: "각 시장 역사 백분위" }, gridcolor: registry.chrome.grid },
  }, 360));
}

// macro: KRW, 10Y
const macro = [];
if (korea.krw) macro.push(["원/달러 환율", korea.krw, "#eda100", "원"]);
if (korea.kr_10y) macro.push(["한국 10년 국채금리", korea.kr_10y, "#4a3aa7", "%"]);
$("macro-charts").innerHTML = macro.map((_, i) => `<div id="km-${i}" class="chart"></div>`).join("");
macro.forEach(([label, s, color, unit], i) => {
  render($(`km-${i}`), [lineTrace(s.dates, s.values, label, color)],
    baseLayout(registry, { showlegend: false,
      yaxis: { title: { text: `${label} (${unit})` }, gridcolor: registry.chrome.grid } }, 260));
});
