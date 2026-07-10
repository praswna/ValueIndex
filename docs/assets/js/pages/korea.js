// 한국 시장: 타일 한 화면 + 탭하면 팝업(차트·σ 등급·미국 비교).

import { load, fmt } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, lineTrace, ratingBadge } from "../charts.js";
import { cleanPairs, percentileRanks } from "../stats.js";
import { openModal } from "../modal.js";

injectNav();
const { meta, registry, korea, panel } = await load("registry", "korea", "panel");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const ratingColor = (key) =>
  (registry.ratings.find((r) => r.key === key) || {}).color || "#898781";
const lastOf = (s) => s.values[s.values.length - 1];

if (korea.unavailable || !korea.kospi.dates.length) {
  $("unavailable").innerHTML =
    '<div class="box box-warn">현재 한국 데이터를 불러오지 못했습니다 (KRX 소스 일시 중단). ' +
    "자동 갱신이 복구되면 표시됩니다.</div>";
}

const COLORS = { per: "#008300", pbr: "#4a3aa7", div_yield: "#e34948" };

// ---- tiles: KOSPI, valuation trio (rating dot + ⚠️), macro pair ----
const tiles = [];
if (korea.kospi.dates.length) {
  tiles.push(`<button class="tile" data-kind="kospi">
    <span class="tile-label">KOSPI 지수</span>
    <span class="tile-value">${Math.round(lastOf(korea.kospi)).toLocaleString("ko-KR")}</span>
    <span class="tile-sub">${korea.kospi.dates[korea.kospi.dates.length - 1]}</span>
  </button>`);
}
for (const [key, v] of Object.entries(korea.indicators)) {
  tiles.push(`<button class="tile" data-kind="val" data-key="${key}">
    <span class="tile-dot" style="background:${ratingColor(v.rating)}"></span>
    <span class="tile-label">${v.label_ko}</span>
    <span class="tile-value">${fmt(v.current, v.unit, registry)}</span>
    <span class="tile-sub">${v.unit} · ${v.start_year}년~ ⚠️</span>
  </button>`);
}
const MACRO = [];
if (korea.krw) MACRO.push(["krw", "원/달러 환율", korea.krw, "#eda100", "원"]);
if (korea.kr_10y) MACRO.push(["kr_10y", "한국 10년 국채금리", korea.kr_10y, "#4a3aa7", "%"]);
for (const [key, label, s, , unit] of MACRO) {
  tiles.push(`<button class="tile" data-kind="macro" data-key="${key}">
    <span class="tile-label">${label}</span>
    <span class="tile-value">${fmt(lastOf(s), unit === "원" ? "" : unit, registry)}</span>
    <span class="tile-sub">${unit}</span>
  </button>`);
}
$("tiles").innerHTML = tiles.join("");

// ---- popups ----
function chart(id, dates, values, name, color, unit, height = 260) {
  render($(id), [lineTrace(dates, values, name, color)],
    baseLayout(registry, { showlegend: false,
      margin: { l: 48, r: 10, t: 8, b: 30 },
      yaxis: { title: { text: unit }, gridcolor: registry.chrome.grid } }, height));
}

function showKospi() {
  openModal(`
    <h2 style="margin:0 0 2px">KOSPI 지수</h2>
    <div class="metric-value">${Math.round(lastOf(korea.kospi)).toLocaleString("ko-KR")}</div>
    <div id="m-chart" class="chart"></div>
    <p class="caption">한국 대표 주가지수 (최근 10년 일간). 지수 자체는 밸류에이션이
      아니므로 등급이 없습니다 — 비싼지는 PER·PBR 타일에서 확인하세요.</p>`);
  chart("m-chart", korea.kospi.dates, korea.kospi.values, "KOSPI", "#2a78d6", "KOSPI", 300);
}

function showVal(key) {
  const v = korea.indicators[key];
  const short = 2026 - v.start_year < 30;
  openModal(`
    <h2 style="margin:0 0 2px">${v.label_ko} ${ratingBadge(registry, v.rating)}</h2>
    <div class="metric-value">${fmt(v.current, v.unit, registry)} ${v.unit}</div>
    <div class="modal-stats">
      <div>역사 평균<br><b>${fmt(v.mean, v.unit, registry)}</b></div>
      <div>고평가 백분위<br><b>${v.aligned_pctile === null ? "-" : v.aligned_pctile.toFixed(0)}%</b></div>
      <div>데이터 시작<br><b>${v.start_year}년</b></div>
      <div>기준일<br><b>${v.asof}</b></div>
    </div>
    <div id="m-chart" class="chart"></div>
    ${short ? `<p class="caption">⚠️ 히스토리가 ${2026 - v.start_year}년으로 짧아
      등급의 신뢰도는 미국 지표(150년)보다 낮습니다.</p>` : ""}
    ${key === "per" ? `<h3>미국과 나란히 보기</h3>
      <p class="caption">두 시장의 후행 PER을 각자의 역사 백분위로 비교 — 절대 배수보다
        '각 시장 기준으로 지금 비싼가'가 핵심입니다.</p>
      <div id="m-compare" class="chart"></div>` : ""}`);
  chart("m-chart", v.dates, v.values, v.label_ko, COLORS[key], v.unit);

  if (key === "per") {
    const krPct = percentileRanks(v.values);
    const us = cleanPairs(panel.dates, panel.series.pe);
    const usPct = percentileRanks(us.values);
    render($("m-compare"), [
      { x: us.dates, y: usPct, mode: "lines", name: "S&P 500",
        line: { color: registry.series_colors.pe, width: 2 } },
      { x: v.dates, y: krPct, mode: "lines", name: "KOSPI",
        line: { color: "#eb6834", width: 2 } },
    ], baseLayout(registry, {
      margin: { l: 45, r: 10, t: 30, b: 30 },
      yaxis: { title: { text: "각자 역사 백분위" }, gridcolor: registry.chrome.grid },
    }, 260));
  }
}

function showMacro(key) {
  const [, label, s, color, unit] = MACRO.find((m) => m[0] === key);
  const desc = key === "krw"
    ? "달러 대비 원화 가치입니다. 환율이 오르면(원화 약세) 원화 기준 해외자산 평가액이 커지고, 수출기업에 유리한 경향이 있습니다."
    : "한국 10년 국채금리 — 국내 장기 할인율의 기준입니다. 금리가 높을수록 주식의 상대 매력이 줄어듭니다.";
  openModal(`
    <h2 style="margin:0 0 2px">${label}</h2>
    <div class="metric-value">${fmt(lastOf(s), unit === "원" ? "" : unit, registry)} ${unit}</div>
    <div id="m-chart" class="chart"></div>
    <p class="caption">${desc} 등급 없는 참고 지표입니다.</p>`);
  chart("m-chart", s.dates, s.values, label, color, unit);
}

$("tiles").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (!tile) return;
  if (tile.dataset.kind === "kospi") showKospi();
  else if (tile.dataset.kind === "val") showVal(tile.dataset.key);
  else if (tile.dataset.kind === "macro") showMacro(tile.dataset.key);
});
