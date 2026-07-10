// 주기별 숫자: 갱신 주기별 타일 3섹션 + 탭하면 팝업(차트·해석).

import { load, fmt, fmtSigned, ym } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, lineTrace, ratingBadge } from "../charts.js";
import { cleanPairs, drawdown, percentileRanks, asofIndex, shiftDateStr } from "../stats.js";
import { openModal } from "../modal.js";

injectNav();
const { meta, registry, panel, context, overview, korea } =
  await load("registry", "panel", "context", "overview", "korea");
injectFooter(meta, registry);

const last = (s) => (s && s.values.length ? s.values[s.values.length - 1] : null);

// S&P drawdown from all-time high (client-computed)
const tri = cleanPairs(panel.dates, panel.series.real_tri);
const dd = drawdown(tri.values);

// Each item: [id, label, value, unit, cadence, note, {dates, values}, color]
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
    const { dates, values } = cleanPairs(panel.dates, panel.series[key]);
    return { id: key, label: ind(key).label_ko, value: sm.current,
      unit: ind(key).unit, cadence: "월간",
      note: `기준 ${ym(sm.asof)}. 이 앱의 본론 — 자세히는 🔍 상세 탭에서.`,
      series: { dates, values }, color: registry.series_colors[key],
      rating: sm.rating };
  }),
  ctxItem("cpi_yoy", "월간", "인플레이션 — 연준 목표는 2%입니다."),
  ctxItem("fedfunds", "월간", "미국 기준금리 — 모든 자산 가격의 기준입니다."),
  ctxItem("unrate", "월간", "실업률 — 경기의 핵심 신호입니다."),
  ctxItem("margin_debt", "월간", "신용융자 잔고 — 시장 전체의 레버리지(탐욕)를 계량합니다."),
].filter(Boolean);

const ALL = {};
function tilesHtml(items) {
  return items.map((it) => {
    ALL[it.id] = it;
    return `<button class="tile" data-id="${it.id}">
      <span class="tile-label">${it.label}</span>
      <span class="tile-value">${
        typeof it.value === "number" && it.unit !== ""
          ? fmt(it.value, it.unit, registry)
          : Number(it.value).toLocaleString("ko-KR")}</span>
      <span class="tile-sub">${it.unit || ""}${it.unit ? " · " : ""}${it.cadence}</span>
    </button>`;
  }).join("");
}
document.getElementById("daily").innerHTML = tilesHtml(DAILY);
document.getElementById("weekly").innerHTML = tilesHtml(WEEKLY);
document.getElementById("monthly").innerHTML = tilesHtml(MONTHLY);

function show(id) {
  const it = ALL[id];
  const vals = it.series.values, dates = it.series.dates;
  const yi = asofIndex(dates, shiftDateStr(dates[dates.length - 1], -1));
  const d1y = yi >= 0 ? vals[vals.length - 1] - vals[yi] : null;
  const clean = vals.filter((v) => v !== null);
  const pct = percentileRanks(vals)[vals.length - 1];
  const fmtV = (v) => (it.unit !== "" ? fmt(v, it.unit, registry)
                                      : Math.round(v).toLocaleString("ko-KR"));
  openModal(`
    <h2 style="margin:0 0 2px">${it.label}
      ${it.rating ? ratingBadge(registry, it.rating) : ""}</h2>
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
    <div id="m-chart" class="chart"></div>
    <p class="modal-desc">${it.note}</p>
    ${it.rating ? `<p><a href="detail.html#${it.id}">🔍 상세 팝업에서 ±σ 밴드·분포 보기</a></p>` : ""}
    <p class="caption">갱신 주기: <b>${it.cadence}</b> — 이 주기보다 자주 보는 것은
      새 정보가 아니라 소음입니다.</p>`);
  render(document.getElementById("m-chart"),
    [lineTrace(it.series.dates, it.series.values, it.label, it.color || "#2a78d6")],
    baseLayout(registry, { showlegend: false,
      margin: { l: 48, r: 10, t: 8, b: 30 },
      yaxis: { title: { text: it.unit || "" }, gridcolor: registry.chrome.grid } }, 260));
}

document.querySelector("main").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (tile && tile.dataset.id) show(tile.dataset.id);
});
