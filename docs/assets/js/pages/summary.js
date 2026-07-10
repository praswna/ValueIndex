// ⚡ 요약: 타일 한 화면 + 탭하면 상세 팝업 (밸류에이션은 상세 페이지와 동일한
// 딥다이브, 온도계는 기준선·통계 포함 풀 차트).

import { load, fmt, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, ratingBadge } from "../charts.js";
import { openModal } from "../modal.js";
import { showValuationPopup } from "../valpop.js";
import { showContextPopup } from "../ctxpop.js";

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
async function getPanel() {
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

// ---- composite popup: series + PCA weights breakdown ----
function showPca() {
  const weights = Object.entries(pca.weights)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const wmax = Math.max(...weights.map(([, w]) => Math.abs(w)));
  const wrows = weights.map(([k, w]) => `
    <div class="chg-row"><span class="chg-title">${ind(k).label_ko || k}</span>
      <span class="chg-names"><span style="display:inline-block;height:9px;
        width:${(Math.abs(w) / wmax * 130).toFixed(0)}px;border-radius:4px;
        background:${registry.series_colors[k] || "#2a78d6"};vertical-align:middle">
      </span> ${w.toFixed(2)}</span></div>`).join("");
  openModal(`
    <h2 style="margin:0 0 2px">종합 밸류에이션 지수</h2>
    <div class="metric-value">${fmtSigned(pca.current, 2)}σ
      ${ratingBadge(registry, pca.rating)}</div>
    <div id="m-spark" class="chart"></div>
    <p class="modal-desc">9개 밸류에이션 지표를 주성분분석(PCA)으로 하나의 축에
      합친 값입니다. 이 축 하나가 지표 전체 변동의
      ${(pca.explained_ratio * 100).toFixed(0)}%를 설명합니다.
      0 = 역사 평균, ±1σ = 보통 범위, ±2σ 밖 = 역사적 극단.</p>
    <h3>어떤 지표가 얼마나 기여하나 (PCA 가중치)</h3>
    ${wrows}
    <p class="caption" style="margin-top:8px">가중치가 비슷하다는 것은 지표들이 결국
      같은 것을 재고 있다는 뜻입니다 — 특정 지표 하나가 결론을 좌우하지 않습니다.</p>
    <p><a href="index.html">📊 개요에서 타임머신·닮은 과거 보기</a></p>`);
  render($("m-spark"), [{ x: pca.dates, y: pca.values, mode: "lines",
    line: { color: "#2a78d6", width: 1.8 } }],
    baseLayout(registry, { showlegend: false,
      margin: { l: 40, r: 8, t: 6, b: 24 },
      yaxis: { title: { text: "σ" }, gridcolor: registry.chrome.grid } }, 220));
}

document.querySelector("main").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (!tile) return;
  if (tile.dataset.kind === "val") {
    showValuationPopup(registry, overview, tile.dataset.key, getPanel);
  } else if (tile.dataset.kind === "ctx") {
    showContextPopup(registry, overview, context, tile.dataset.key, meta);
  } else if (tile.dataset.kind === "pca") showPca();
});

// deep link: summary.html#cape opens that indicator's deep-dive right away
// (also the landing spot for links from the old detail page).
const hashKey = decodeURIComponent(location.hash.slice(1));
if (registry.valuation_keys.includes(hashKey)) {
  showValuationPopup(registry, overview, hashKey, getPanel);
}
