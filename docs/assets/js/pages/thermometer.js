// 시장 온도계: 심리/참고/거시 타일 3섹션 + 탭하면 팝업(차트·해석).

import { load, fmt, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, lineTrace, recessionShapes, hline } from "../charts.js";
import { asofIndex, shiftDateStr } from "../stats.js";
import { openModal } from "../modal.js";

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
    return `<button class="tile" data-key="${key}">
      <span class="tile-label">${m.label_ko}</span>
      <span class="tile-value">${fmt(last, m.unit, registry)}</span>
      <span class="tile-sub">${m.unit || ""}${
        delta !== null ? ` · 1년 ${fmtSigned(delta, 1)}` : ""}</span>
    </button>`;
  }).join("");
  root.insertAdjacentHTML("beforeend", `
    <h2>${title}</h2>
    ${desc ? `<p class="caption">${desc}</p>` : ""}
    <div class="tiles">${tiles}</div>`);
}

function show(key) {
  const m = registry.indicators[key];
  const s = context[key];
  const { last, delta } = lastDelta(key);
  openModal(`
    <h2 style="margin:0 0 2px">${m.label_ko}</h2>
    <div class="metric-value">${fmt(last, m.unit, registry)} ${m.unit || ""}
      ${delta !== null
        ? `<span class="metric-delta">1년 전 대비 ${fmtSigned(delta, 1)}</span>` : ""}</div>
    <div id="m-chart" class="chart"></div>
    <p class="modal-desc">${m.what_ko || ""}</p>
    <p class="caption">${m.interpret_ko || ""}</p>
    <p class="caption">${s.dates[0].slice(0, 4)}년~ · 출처: ${m.source} · 등급 없는
      참고 지표입니다. 빨간 점선 = 관례적 기준선, 회색 음영 = 미국 경기침체.</p>`);
  const shapes = [
    ...(registry.guide_lines[key] || []).map((y) => hline(y, "#c22f2f")),
    ...recessionShapes(registry, overview.recessions, s.dates[0]),
  ];
  render(document.getElementById("m-chart"),
    [lineTrace(s.dates, s.values, m.label_ko, registry.series_colors[key])],
    baseLayout(registry, {
      showlegend: false, shapes,
      margin: { l: 45, r: 10, t: 8, b: 30 },
      yaxis: { title: { text: m.unit }, gridcolor: registry.chrome.grid },
    }, 260));
}

root.addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (tile) show(tile.dataset.key);
});
