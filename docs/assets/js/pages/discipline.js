// 투자 규율: 드로다운 차트(클라이언트 계산), 체크리스트, 콘텐츠.

import { load, ym } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { initSubtabs } from "../subtabs.js";
import { baseLayout, render, recessionShapes, ratingBadge } from "../charts.js";
import { cleanPairs, drawdown } from "../stats.js";

injectNav();
const { meta, registry, panel, overview, content } =
  await load("registry", "panel", "overview", "content");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
$("content").innerHTML = content.discipline_ko;
$("resources").innerHTML = content.resources_ko;

// ---------------------------------------------------------------- drawdown
const { dates, values } = cleanPairs(panel.dates, panel.series.real_tri);
const dd = drawdown(values);
render($("dd-chart"), [{
  x: dates, y: dd, mode: "lines", name: "고점 대비 하락률",
  line: { color: "#c22f2f", width: 1.5 }, fill: "tozeroy",
  fillcolor: "rgba(194,47,47,0.12)",
  hovertemplate: "%{x|%Y-%m}: %{y:.0f}%<extra></extra>",
}], baseLayout(registry, {
  showlegend: false,
  shapes: recessionShapes(registry, overview.recessions, dates[0]),
  yaxis: { title: { text: "실질 총수익 기준 고점 대비 %" },
           gridcolor: registry.chrome.grid },
}, 380));

let min = 0, argmin = 0;
dd.forEach((x, i) => { if (x < min) { min = x; argmin = i; } });
$("dd-facts").innerHTML = `<ul>
  <li>지난 150여 년 동안 <b>−50% 이상의 하락이 여러 번</b> 있었고, 매번 회복했습니다.</li>
  <li>최악의 드로다운: <b>${min.toFixed(0)}%</b> (${dates[argmin].slice(0, 4)}년).</li>
  <li>'−30% 급락'은 이례적 사건이 아니라 장기 투자에 <b>포함된 비용</b>입니다.
    이걸 미리 알고 시작하는 것과 모르고 당하는 것의 차이가 규율입니다.</li></ul>`;

$("scenario-lead").innerHTML =
  `지금 CAPE 기준 등급: ${ratingBadge(registry, overview.summaries.cape.rating)} ` +
  `(${ym(overview.summaries.cape.asof)}) — 패닉 상황에서 즉흥적으로 판단하지 않도록, ` +
  `<b>평온한 지금</b> 규칙을 정해두는 것이 이 섹션의 목적입니다.`;

// ---------------------------------------------------------------- checklist
const CHECKS = [
  "비상금(3~6개월 생활비)이 투자금과 별도로 있다",
  "이 돈은 최소 10년 묻어둘 수 있는 돈이다",
  "연 5% 이상 고금리 부채가 없다",
  "매수 이유가 유튜브·지인 추천·급등 뉴스가 아니다",
  "이 매수 후에도 한 종목/테마 비중이 전체의 20%를 넘지 않는다",
  "떨어져도 팔지 않을 하락 한도를 미리 정했다",
];
const wrap = $("checklist");
for (const text of CHECKS) {
  const label = document.createElement("label");
  label.style.display = "block";
  label.style.margin = "6px 0";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.addEventListener("change", updateChecks);
  label.appendChild(cb);
  label.appendChild(document.createTextNode(" " + text));
  wrap.appendChild(label);
}
function updateChecks() {
  const done = wrap.querySelectorAll("input:checked").length;
  const box = $("check-result");
  if (done === CHECKS.length) {
    box.className = "box box-good";
    box.textContent = "✅ 모든 항목 통과 — 계획대로 진행하세요.";
  } else {
    box.className = "box box-info";
    box.textContent =
      `${done}/${CHECKS.length} 통과 — 전부 체크되기 전에는 매수를 미루는 것이 규칙입니다.`;
  }
}
updateChecks();

initSubtabs("disc-tabs", [
  { id: "why", label: "원칙", section: "dtab-why" },
  { id: "drawdown", label: "드로다운", section: "dtab-dd" },
  { id: "rules", label: "행동 규칙", section: "dtab-rules" },
  { id: "checklist", label: "체크·루틴", section: "dtab-check" },
]);
