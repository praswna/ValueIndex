// 시장 온도계: 심리/참고/거시 3섹션, 등급 없는 맥락 지표.

import { load, fmt, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, lineTrace, recessionShapes, hline } from "../charts.js";
import { asofIndex, shiftDateStr } from "../stats.js";

injectNav();
const { meta, registry, context, overview } = await load("registry", "context", "overview");
injectFooter(meta, registry);

const SECTIONS = [
  ["sentiment", "🧠 심리 온도계 — 시장의 감정을 재는 숫자들",
   "심리 지표는 두 부류입니다: 사람들이 <b>말하는</b> 것(설문 — AAII, 미시간대)과 " +
   "<b>돈으로 실제 하는</b> 것(포지셔닝 — 신용융자, 공포·탐욕의 구성요소). 극단일 때만 " +
   "의미가 있고, 관례적으로 <b>역발상</b>으로 읽습니다. 매매 신호가 아니라 '내 감정이 " +
   "시장 전체와 같은 방향인지 확인하는 거울'로 쓰세요."],
  ["reference", "📌 자주 참고하는 매크로 숫자",
   "뉴스에 매번 나오는 기준 숫자들입니다 — 시장의 배경 조건이지, 매매 신호가 아닙니다."],
  ["macro", "🌍 거시·시장 온도계", ""],
];

const root = document.getElementById("sections");

for (const [group, title, desc] of SECTIONS) {
  const keys = registry.context_keys.filter(
    (k) => registry.indicators[k].group === group && context[k]
  );
  if (!keys.length) continue;
  const h = document.createElement("h2");
  h.textContent = title;
  root.appendChild(h);
  if (desc) {
    const p = document.createElement("p");
    p.className = "caption";
    p.innerHTML = desc;
    root.appendChild(p);
  }
  for (const key of keys) renderIndicator(key);
}

function renderIndicator(key) {
  const m = registry.indicators[key];
  const s = context[key];
  const dates = s.dates, values = s.values;
  const last = values[values.length - 1];
  const yi = asofIndex(dates, shiftDateStr(dates[dates.length - 1], -1));
  const delta = yi >= 0 ? last - values[yi] : null;

  const sec = document.createElement("section");
  sec.innerHTML = `
    <h3>${m.label_ko}</h3>
    <div class="split">
      <div class="card" title="${m.what_ko}">
        <div class="metric-label">현재 (${m.unit})</div>
        <div class="metric-value">${fmt(last, m.unit, registry)}</div>
        ${delta !== null ? `<span class="metric-delta">${fmtSigned(delta, 1)} (1년 전 대비)</span>` : ""}
        <div class="metric-note">${dates[0].slice(0, 4)}년~ · ${m.source}</div>
      </div>
      <div id="chart-${key}" class="chart"></div>
    </div>
    <p style="font-size:0.92rem">${m.interpret_ko}</p>
    <hr>`;
  root.appendChild(sec);

  const shapes = [
    ...(registry.guide_lines[key] || []).map((y) => hline(y, "#c22f2f")),
    ...recessionShapes(registry, overview.recessions, dates[0]),
  ];
  render(document.getElementById(`chart-${key}`),
    [lineTrace(dates, values, m.label_ko, registry.series_colors[key])],
    baseLayout(registry, {
      showlegend: false, shapes,
      yaxis: { title: { text: m.unit }, gridcolor: registry.chrome.grid },
    }, 260));
}
