// ⚡ 요약 (루트): 타일 한 화면 + 하위 탭(종합지수·타임머신 / 닮은 과거 / 비교).
// 첫 화면은 가볍게(registry/overview/context만), 심화 탭은 panel.json이 필요해
// 처음 열 때 overview-section.js를 초기화한다. #<지표키> 해시는 딥다이브 팝업.

import { load, fmt, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, ratingBadge } from "../charts.js";
import { openModal } from "../modal.js";
import { showValuationPopup } from "../valpop.js";
import { showContextPopup } from "../ctxpop.js";
import { initSubtabs } from "../subtabs.js";
import { initOverview } from "../overview-section.js";

const initialHash = location.hash.slice(1);

injectNav();
const { meta, registry, overview, context } =
  await load("registry", "overview", "context");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const ind = (key) => registry.indicators[key] || {};
const ratingColor = (key) =>
  (registry.ratings.find((r) => r.key === key) || {}).color || "#898781";

let _panel = null;
async function getPanel() {
  if (!_panel) ({ panel: _panel } = await load("panel"));
  return _panel;
}

// ---- home tiles ----
const CTX_KEYS = ["fear_greed", "vix", "fedfunds", "cpi_yoy", "unrate", "gold"]
  .filter((k) => context[k] && context[k].values.length);
const last = (k) => context[k].values[context[k].values.length - 1];

const pca = overview.pca;
$("composite").innerHTML = `
  <button class="tile tile-wide" data-kind="pca">
    <span class="tile-label">종합 밸류에이션 (${overview.latest_month.slice(0, 7)})</span>
    <span class="tile-value">${fmtSigned(pca.current, 2)}σ</span>
    <span>${ratingBadge(registry, pca.rating)}</span>
  </button>`;

$("val-tiles").innerHTML = registry.valuation_keys.map((key) => {
  const s = overview.summaries[key];
  return `<button class="tile" data-kind="val" data-key="${key}">
    <span class="tile-dot" style="background:${ratingColor(s.rating)}"></span>
    <span class="tile-label">${ind(key).label_ko || key}</span>
    <span class="tile-value">${fmt(s.current, ind(key).unit, registry)}</span>
    <span class="tile-sub">${ind(key).unit || ""}</span>
  </button>`;
}).join("");

$("ctx-tiles").innerHTML = CTX_KEYS.map((key) => `
  <button class="tile" data-kind="ctx" data-key="${key}">
    <span class="tile-label">${ind(key).label_ko || key}</span>
    <span class="tile-value">${fmt(last(key), ind(key).unit, registry)}</span>
    <span class="tile-sub">${ind(key).unit || ""}</span>
  </button>`).join("");

// ---- composite popup (quick view; the 종합지수 tab has the full treatment)
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
    <p class="caption" style="margin-top:8px">타임머신·게이지는 위의
      <b>종합지수 탭</b>에서 볼 수 있습니다.</p>`);
  render($("m-spark"), [{ x: pca.dates, y: pca.values, mode: "lines",
    line: { color: "#2a78d6", width: 1.8 } }],
    baseLayout(registry, { showlegend: false,
      margin: { l: 40, r: 8, t: 6, b: 24 },
      yaxis: { title: { text: "σ" }, gridcolor: registry.chrome.grid } }, 220));
}

document.querySelector("main").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (!tile || !tile.dataset.kind) return;
  if (tile.dataset.kind === "val") {
    showValuationPopup(registry, overview, tile.dataset.key, getPanel);
  } else if (tile.dataset.kind === "ctx") {
    showContextPopup(registry, overview, context, tile.dataset.key, meta);
  } else if (tile.dataset.kind === "pca") showPca();
});

// ---- sub-tabs + lazy heavy section ----
const HEAVY = new Set(["composite", "analogs", "compare"]);
let overviewReady = false;
async function ensureOverview(currentTab) {
  if (overviewReady) return;
  overviewReady = true;
  const panel = await getPanel();
  initOverview({ registry, panel, overview, barId: "main-tabs", currentTab });
}

initSubtabs("main-tabs", [
  { id: "home", label: "한눈에", section: "itab-home" },
  { id: "composite", label: "종합지수", section: "itab-composite" },
  { id: "analogs", label: "닮은 과거", section: "itab-analogs" },
  { id: "compare", label: "비교", section: "itab-compare" },
]);
document.getElementById("main-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-tab]");
  if (btn && HEAVY.has(btn.dataset.tab)) ensureOverview(btn.dataset.tab);
});

// deep links: #<지표키> = popup, #composite/#analogs/#compare = heavy tab
if (registry.valuation_keys.includes(initialHash)) {
  showValuationPopup(registry, overview, initialHash, getPanel);
} else if (HEAVY.has(initialHash)) {
  ensureOverview(initialHash);
}
