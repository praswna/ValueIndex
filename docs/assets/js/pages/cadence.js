// 주기별 숫자: 기존 시리즈를 갱신 주기별로 재구성한 카드 뷰 + 규율 프레임.

import { load, fmt, ym } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { ratingBadge } from "../charts.js";
import { cleanPairs, drawdown } from "../stats.js";

injectNav();
const { meta, registry, panel, context, overview, korea } =
  await load("registry", "panel", "context", "overview", "korea");
injectFooter(meta, registry);

const last = (s) => (s && s.values.length ? s.values[s.values.length - 1] : null);
const lastDate = (s) => (s && s.dates.length ? s.dates[s.dates.length - 1] : null);

// S&P drawdown from all-time high (client-computed)
const tri = cleanPairs(panel.dates, panel.series.real_tri);
const dd = drawdown(tri.values);
const ddNow = dd[dd.length - 1];

function card(label, value, unit, cadence, note, extra = "") {
  const val = value === null ? "-"
    : (typeof value === "string" ? value : fmt(value, unit, registry));
  return `<div class="card">
    <div class="metric-label">${label} <span class="metric-delta">${cadence}</span></div>
    <div class="metric-value" style="font-size:1.5rem">${val}${unit && typeof value !== "string" ? " " + unit : ""}</div>
    ${extra}
    <div class="metric-note">${note}</div>
  </div>`;
}

// -------------------------------------------------------------------- daily
const daily = [];
daily.push(card("S&P 500 고점 대비", ddNow.toFixed(1), "%", "매일",
  "사상 최고가 대비 하락률. −30%도 장기 투자에 포함된 비용입니다."));
if (korea.kospi && korea.kospi.values.length)
  daily.push(card("KOSPI", Math.round(last(korea.kospi)), "", "매일", "한국 대표 지수"));
for (const [key, cad, note] of [
  ["vix", "매일", "시장의 불안 심리. 20 평온·30 공포"],
  ["fear_greed", "매일", "0~100 공포·탐욕. 극단은 역발상 신호"],
  ["wti", "매일", "국제 유가 — 경기·인플레이션 입력값"],
]) {
  const s = context[key];
  if (s) daily.push(card(registry.indicators[key].label_ko, last(s),
    registry.indicators[key].unit, cad, note));
}
if (korea.krw)
  daily.push(card("원/달러 환율", Math.round(last(korea.krw)), "원", "매일",
    "달러 대비 원화 가치"));
document.getElementById("daily").innerHTML = daily.join("");

// ------------------------------------------------------------------ weekly
const weekly = [];
for (const [key, note] of [
  ["aaii_spread", "개인투자자 심리 설문. 극단만 의미 있음"],
  ["hy_spread", "신용시장의 공포 온도계"],
  ["t10y2y", "장단기 금리차. 역전은 침체 선행 신호"],
]) {
  const s = context[key];
  if (s) weekly.push(card(registry.indicators[key].label_ko, last(s),
    registry.indicators[key].unit, "주간", note));
}
document.getElementById("weekly").innerHTML = weekly.join("");

// ----------------------------------------------------------------- monthly
const monthly = [];
// valuation ratings (the app's core)
for (const key of ["cape", "buffett"]) {
  const sm = overview.summaries[key];
  monthly.push(card(registry.indicators[key].label_ko, sm.current,
    registry.indicators[key].unit, "월간",
    `기준 ${ym(sm.asof)} · 자세히는 개요 페이지`,
    ratingBadge(registry, sm.rating)));
}
for (const [key, note] of [
  ["cpi_yoy", "인플레이션 — 연준 목표 2%"],
  ["fedfunds", "미국 기준금리 — 모든 자산의 기준"],
  ["unrate", "실업률 — 경기의 핵심 신호"],
  ["margin_debt", "신용융자 잔고 — 레버리지(탐욕) 계량"],
]) {
  const s = context[key];
  if (s) monthly.push(card(registry.indicators[key].label_ko, last(s),
    registry.indicators[key].unit, "월간", note));
}
document.getElementById("monthly").innerHTML = monthly.join("");
