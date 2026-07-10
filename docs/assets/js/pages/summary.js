// ⚡ 요약: 타일 한 화면 + 탭하면 팝업 상세 (설명·통계·미니 차트).

import { load, fmt, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, ratingBadge } from "../charts.js";
import { cleanPairs } from "../stats.js";
import { openModal } from "../modal.js";

injectNav();
const { meta, registry, overview, context } =
  await load("registry", "overview", "context");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const ind = (key) => registry.indicators[key] || {};
const ratingColor = (key) =>
  (registry.ratings.find((r) => r.key === key) || {}).color || "#898781";

// panel.json은 팝업에서 처음 필요할 때만 내려받는다 (첫 화면을 가볍게).
let _panel = null;
async function panel() {
  if (!_panel) ({ panel: _panel } = await load("panel"));
  return _panel;
}

// 온도계 타일: context.json에 있는 것 중 대표 6개.
const CTX_KEYS = ["fear_greed", "vix", "fedfunds", "cpi_yoy", "unrate", "gold"]
  .filter((k) => context[k] && context[k].values.length);
const last = (k) => context[k].values[context[k].values.length - 1];

// ---- composite tile ----
const pca = overview.pca;
$("composite").innerHTML = `
  <button class="tile tile-wide" data-kind="pca">
    <span class="tile-label">종합 밸류에이션 (${overview.latest_month.slice(0, 7)})</span>
    <span class="tile-value">${fmtSigned(pca.current, 2)}σ</span>
    <span>${ratingBadge(registry, pca.rating)}</span>
  </button>`;

// ---- valuation tiles ----
$("val-tiles").innerHTML = registry.valuation_keys.map((key) => {
  const s = overview.summaries[key];
  return `<button class="tile" data-kind="val" data-key="${key}">
    <span class="tile-dot" style="background:${ratingColor(s.rating)}"></span>
    <span class="tile-label">${ind(key).label_ko || key}</span>
    <span class="tile-value">${fmt(s.current, ind(key).unit, registry)}</span>
    <span class="tile-sub">${ind(key).unit || ""}</span>
  </button>`;
}).join("");

// ---- context tiles ----
$("ctx-tiles").innerHTML = CTX_KEYS.map((key) => `
  <button class="tile" data-kind="ctx" data-key="${key}">
    <span class="tile-label">${ind(key).label_ko || key}</span>
    <span class="tile-value">${fmt(last(key), ind(key).unit, registry)}</span>
    <span class="tile-sub">${ind(key).unit || ""}</span>
  </button>`).join("");

function spark(id, dates, values, color) {
  render($(id), [{ x: dates, y: values, mode: "lines",
    line: { color, width: 1.8 } }],
    baseLayout(registry, { showlegend: false, hovermode: false,
      margin: { l: 40, r: 8, t: 6, b: 24 },
      xaxis: { nticks: 5 }, yaxis: { gridcolor: registry.chrome.grid } }, 180));
}

async function showValuation(key) {
  const s = overview.summaries[key];
  const m = ind(key);
  openModal(`
    <h2 style="margin:0 0 2px">${m.label_ko}</h2>
    <div class="metric-value">${fmt(s.current, m.unit, registry)} ${m.unit}
      ${ratingBadge(registry, s.rating)}</div>
    <div id="mspark" class="chart"></div>
    <div class="modal-stats">
      <div>역사 평균<br><b>${fmt(s.mean, m.unit, registry)}</b></div>
      <div>고평가 백분위<br><b>${s.aligned_pctile === null ? "-" : s.aligned_pctile.toFixed(0)}%</b></div>
      <div>1년 변화<br><b>${fmtSigned(s.delta_1y, 2)}</b></div>
      <div>데이터 시작<br><b>${s.start_year}년</b></div>
    </div>
    <p class="modal-desc">${m.what_ko || ""}</p>
    <p class="caption">${m.interpret_ko || ""}</p>
    <p><a href="detail.html#${key}">🔍 상세 페이지에서 전체 분석 보기</a></p>`);
  const p = await panel();
  const { dates, values } = cleanPairs(p.dates, p.series[key]);
  spark("mspark", dates, values, registry.series_colors[key] || "#2a78d6");
}

function showContext(key) {
  const m = ind(key);
  const c = context[key];
  openModal(`
    <h2 style="margin:0 0 2px">${m.label_ko || key}</h2>
    <div class="metric-value">${fmt(last(key), m.unit, registry)} ${m.unit || ""}</div>
    <div id="mspark" class="chart"></div>
    <p class="modal-desc">${m.what_ko || ""}</p>
    <p class="caption">${m.interpret_ko || ""} 등급 없는 참고 지표입니다 —
      해석은 <a href="thermometer.html">🌡️ 온도계</a>에서.</p>`);
  spark("mspark", c.dates, c.values, registry.series_colors[key] || "#2a78d6");
}

function showPca() {
  openModal(`
    <h2 style="margin:0 0 2px">종합 밸류에이션 지수</h2>
    <div class="metric-value">${fmtSigned(pca.current, 2)}σ
      ${ratingBadge(registry, pca.rating)}</div>
    <div id="mspark" class="chart"></div>
    <p class="modal-desc">9개 밸류에이션 지표를 주성분분석(PCA)으로 하나의 축에
      합친 값입니다. 이 축 하나가 지표 전체 변동의
      ${(pca.explained_ratio * 100).toFixed(0)}%를 설명합니다.
      0 = 역사 평균, ±1σ = 보통 범위, ±2σ 밖 = 역사적 극단.</p>
    <p><a href="index.html">📊 개요에서 타임머신·닮은 과거 보기</a></p>`);
  spark("mspark", pca.dates, pca.values, "#2a78d6");
}

document.querySelector("main").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (!tile) return;
  if (tile.dataset.kind === "val") showValuation(tile.dataset.key);
  else if (tile.dataset.kind === "ctx") showContext(tile.dataset.key);
  else if (tile.dataset.kind === "pca") showPca();
});
