// 시장 온도계: 심리/참고/거시 타일 3섹션 + 탭하면 팝업(차트·해석).

import { load, fmt, fmtSigned, ym } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, lineTrace, ratingBadge } from "../charts.js";
import { asofIndex, shiftDateStr, cleanPairs, drawdown, percentileRanks } from "../stats.js";
import { showContextPopup, CTX_SOURCE, isApprox, approxBadge } from "../ctxpop.js";
import { openModal } from "../modal.js";
import { initSubtabs } from "../subtabs.js";

injectNav();
const { meta, registry, context, overview } = await load("registry", "context", "overview");
injectFooter(meta, registry);

const SECTIONS = [
  ["sentiment", "🧠 심리",
   "사람들이 <b>말하는</b> 것(설문)과 <b>돈으로 실제 하는</b> 것(포지셔닝). 극단일 때만 " +
   "의미가 있고, 관례적으로 <b>역발상</b>으로 읽습니다."],
  ["reference", "📌 자주 참고하는 매크로",
   "뉴스에 매번 나오는 기준 숫자들 — 시장의 배경 조건이지, 매매 신호가 아닙니다."],
  ["macro", "🌍 거시·시장", ""],
];

const root = document.getElementById("sections");

function lastDelta(key) {
  const s = context[key];
  const last = s.values[s.values.length - 1];
  const yi = asofIndex(s.dates, shiftDateStr(s.dates[s.dates.length - 1], -1));
  return { last, delta: yi >= 0 ? last - s.values[yi] : null };
}

for (const [group, title, desc] of SECTIONS) {
  const keys = registry.context_keys.filter(
    (k) => registry.indicators[k].group === group && context[k]
  );
  if (!keys.length) continue;
  const tiles = keys.map((key) => {
    const m = registry.indicators[key];
    const { last, delta } = lastDelta(key);
    const approx = isApprox(meta, CTX_SOURCE[key]);
    return `<button class="tile" data-key="${key}">
      <span class="tile-label">${m.label_ko}</span>
      <span class="tile-value">${fmt(last, m.unit, registry)}</span>
      <span class="tile-sub">${m.unit || ""}${
        delta !== null ? ` · 1년 ${fmtSigned(delta, 1)}` : ""}${
        approx ? " · ⚠️ 근사" : ""}</span>
    </button>`;
  }).join("");
  root.insertAdjacentHTML("beforeend", `
    <div id="ttab-${group}" hidden>
      <h2>${title}</h2>
      ${desc ? `<p class="caption">${desc}</p>` : ""}
      <div class="tiles">${tiles}</div>
    </div>`);
}

root.addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (tile) showContextPopup(registry, overview, context, tile.dataset.key, meta);
});

// ---------------------------------------- 주기별 (구 cadence 탭, 지연 초기화)
// panel/korea가 추가로 필요해서 '주기별' 탭을 처음 열 때 로드한다.
let cadReady = false;
async function initCadence() {
  if (cadReady) return;
  cadReady = true;
  const { panel, korea } = await load("panel", "korea");
  const last = (s) => (s && s.values.length ? s.values[s.values.length - 1] : null);
  const tri = cleanPairs(panel.dates, panel.series.real_tri);
  const dd = drawdown(tri.values);
  const ind = (k) => registry.indicators[k] || {};
  const ctxItem = (key, cadence, note) =>
    context[key] && {
      id: key, label: ind(key).label_ko, value: last(context[key]),
      unit: ind(key).unit, cadence, note,
      series: context[key], color: registry.series_colors[key],
    };

  const DAILY = [
    { id: "dd", label: "S&P 500 고점 대비", value: dd[dd.length - 1], unit: "%",
      cadence: "매일", note: "사상 최고가 대비 하락률입니다. −30%도 장기 투자에 포함된 비용입니다 — 하락률 자체보다 '이때 팔지 않는 것'이 수익률을 결정합니다.",
      series: { dates: tri.dates, values: dd }, color: "#e34948" },
    korea.kospi && korea.kospi.values.length && {
      id: "kospi", label: "KOSPI", value: Math.round(last(korea.kospi)), unit: "",
      cadence: "매일", note: "한국 대표 지수. 자세한 밸류에이션은 🇰🇷 한국 탭에서.",
      series: korea.kospi, color: "#2a78d6" },
    ctxItem("vix", "매일", "시장의 불안 심리. 20 평온·30 공포가 관례적 기준입니다."),
    ctxItem("fear_greed", "매일", "0~100 공포·탐욕. 극단은 역발상 신호로 읽습니다."),
    ctxItem("wti", "매일", "국제 유가 — 경기·인플레이션의 입력값입니다."),
    korea.krw && {
      id: "krw", label: "원/달러 환율", value: Math.round(last(korea.krw)), unit: "원",
      cadence: "매일", note: "달러 대비 원화 가치.",
      series: korea.krw, color: "#eda100" },
  ].filter(Boolean);

  const WEEKLY = [
    ctxItem("aaii_spread", "주간", "개인투자자 심리 설문. 극단만 의미 있습니다."),
    ctxItem("hy_spread", "주간", "신용시장의 공포 온도계 — 급등은 스트레스 신호입니다."),
    ctxItem("t10y2y", "주간", "장단기 금리차. 역전(마이너스)은 역사적으로 침체에 선행했습니다."),
  ].filter(Boolean);

  const MONTHLY = [
    ...["cape", "buffett"].map((key) => {
      const sm = overview.summaries[key];
      const p = cleanPairs(panel.dates, panel.series[key]);
      return { id: key, label: ind(key).label_ko, value: sm.current,
        unit: ind(key).unit, cadence: "월간",
        note: `기준 ${ym(sm.asof)}. 이 앱의 본론 — 딥다이브는 요약 탭에서.`,
        series: p, color: registry.series_colors[key], rating: sm.rating };
    }),
    ctxItem("cpi_yoy", "월간", "인플레이션 — 연준 목표는 2%입니다."),
    ctxItem("fedfunds", "월간", "미국 기준금리 — 모든 자산 가격의 기준입니다."),
    ctxItem("unrate", "월간", "실업률 — 경기의 핵심 신호입니다."),
    ctxItem("margin_debt", "월간", "신용융자 잔고 — 시장 전체의 레버리지(탐욕)를 계량합니다."),
  ].filter(Boolean);

  const ALL = {};
  const tilesHtml = (items) => items.map((it) => {
    ALL[it.id] = it;
    const approx = isApprox(meta, CTX_SOURCE[it.id]);
    return `<button class="tile" data-cad="${it.id}">
      <span class="tile-label">${it.label}</span>
      <span class="tile-value">${
        typeof it.value === "number" && it.unit !== ""
          ? fmt(it.value, it.unit, registry)
          : Number(it.value).toLocaleString("ko-KR")}</span>
      <span class="tile-sub">${it.unit || ""}${it.unit ? " · " : ""}${it.cadence}${
        approx ? " · ⚠️ 근사" : ""}</span>
    </button>`;
  }).join("");
  document.getElementById("cad-daily").innerHTML = tilesHtml(DAILY);
  document.getElementById("cad-weekly").innerHTML = tilesHtml(WEEKLY);
  document.getElementById("cad-monthly").innerHTML = tilesHtml(MONTHLY);

  function showCad(id) {
    const it = ALL[id];
    const vals = it.series.values, dates = it.series.dates;
    const yi = asofIndex(dates, shiftDateStr(dates[dates.length - 1], -1));
    const d1y = yi >= 0 ? vals[vals.length - 1] - vals[yi] : null;
    const clean = vals.filter((v) => v !== null);
    const pct = percentileRanks(vals)[vals.length - 1];
    const fmtV = (v) => (it.unit !== "" ? fmt(v, it.unit, registry)
                                        : Math.round(v).toLocaleString("ko-KR"));
    const approx = isApprox(meta, CTX_SOURCE[id]);
    openModal(`
      <h2 style="margin:0 0 2px">${it.label}
        ${it.rating ? ratingBadge(registry, it.rating) : ""}${approx ? approxBadge() : ""}</h2>
      <div class="metric-value">${
        typeof it.value === "number" && it.unit !== ""
          ? fmt(it.value, it.unit, registry)
          : Number(it.value).toLocaleString("ko-KR")} ${it.unit || ""}</div>
      <div class="modal-stats">
        <div>1년 변화<br><b>${d1y === null ? "-" : fmtSigned(d1y, 1)}</b></div>
        <div>역사 백분위<br><b>${pct.toFixed(0)}/100</b></div>
        <div>역사 범위<br><b>${fmtV(Math.min(...clean))}~${fmtV(Math.max(...clean))}</b></div>
        <div>데이터 시작<br><b>${dates[0].slice(0, 4)}년</b></div>
      </div>
      <div id="m-cad-chart" class="chart"></div>
      <p class="modal-desc">${it.note}</p>
      ${it.rating ? `<p><a href="index.html#${it.id}">🔍 딥다이브 팝업 보기 (±σ 밴드·분포)</a></p>` : ""}
      <p class="caption">갱신 주기: <b>${it.cadence}</b> — 이 주기보다 자주 보는 것은
        새 정보가 아니라 소음입니다.</p>`);
    render(document.getElementById("m-cad-chart"),
      [lineTrace(it.series.dates, it.series.values, it.label, it.color || "#2a78d6")],
      baseLayout(registry, { showlegend: false,
        margin: { l: 48, r: 10, t: 8, b: 30 },
        yaxis: { title: { text: it.unit || "" }, gridcolor: registry.chrome.grid } }, 260));
  }

  document.getElementById("ttab-cadence").addEventListener("click", (e) => {
    const tile = e.target.closest("[data-cad]");
    if (tile) showCad(tile.dataset.cad);
  });
}

initSubtabs("therm-tabs", [
  { id: "sentiment", label: "심리", section: "ttab-sentiment" },
  { id: "reference", label: "매크로 참고", section: "ttab-reference" },
  { id: "macro", label: "거시·시장", section: "ttab-macro" },
  { id: "cadence", label: "주기별", section: "ttab-cadence" },
]);
document.getElementById("therm-tabs").addEventListener("click", (e) => {
  if (e.target.closest('[data-tab="cadence"]')) initCadence();
});
if (location.hash === "#cadence") initCadence();
