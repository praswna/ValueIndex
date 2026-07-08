// 투자 시작 가이드: Bogle 계산기(floating-bar 워터폴) + 몬테카를로 DCA.

import { load, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render } from "../charts.js";
import { cleanPairs, pctChange } from "../stats.js";
import { bogleExpectedReturn, simulateDca, percentileLinear } from "../mc.js";

injectNav();
const { meta, registry, panel, overview, content } =
  await load("registry", "panel", "overview", "content");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
$("content").innerHTML = content.investing_guide_ko;

const divNow = overview.summaries.div_yield.current;
const capeNow = overview.summaries.cape.current;
const capeMean = overview.summaries.cape.mean;

// ------------------------------------------------------------ Bogle calc
const capef = $("capef");
capef.value = ((capeNow + capeMean) / 2).toFixed(1);

function drawBogle() {
  const growth = Number($("growth").value);
  const capeF = Number(capef.value);
  $("growth-label").textContent = growth.toFixed(2);
  $("capef-label").textContent = capeF.toFixed(1);
  const valuation = bogleExpectedReturn(0, 0, capeNow, capeF);
  const total = bogleExpectedReturn(divNow, growth, capeNow, capeF);
  $("bogle-total").textContent = `${fmtSigned(total, 1)}%`;

  // waterfall as floating bars (cartesian bundle has no waterfall trace)
  const steps = [
    { name: "배당수익률", v: divNow },
    { name: "이익성장률", v: growth },
    { name: "밸류에이션 변화", v: valuation },
  ];
  let running = 0;
  const bars = steps.map((s) => {
    const base = s.v >= 0 ? running : running + s.v;
    running += s.v;
    return { x: s.name, base, y: Math.abs(s.v),
             color: s.v >= 0 ? "#2a78d6" : "#c22f2f",
             label: `${fmtSigned(s.v, 1)}%` };
  });
  bars.push({ x: "합계", base: Math.min(0, total), y: Math.abs(total),
              color: "#898781", label: `${fmtSigned(total, 1)}%` });
  render($("waterfall"), [{
    type: "bar",
    x: bars.map((b) => b.x), y: bars.map((b) => b.y), base: bars.map((b) => b.base),
    marker: { color: bars.map((b) => b.color) },
    text: bars.map((b) => b.label), textposition: "outside",
    hovertemplate: "%{x}: %{text}<extra></extra>",
  }], baseLayout(registry, {
    hovermode: "closest", showlegend: false,
    yaxis: { title: { text: "%/년 (실질)" }, gridcolor: registry.chrome.grid,
             zerolinecolor: "#c3c2b7" },
  }, 340));

  $("bogle-note").textContent =
    `현재 CAPE ${capeNow.toFixed(1)}에서 역사 평균(${capeMean.toFixed(1)})으로 완전히 ` +
    `회귀한다고 가정하면 밸류에이션 변화만으로 연 ` +
    `${fmtSigned(bogleExpectedReturn(0, 0, capeNow, capeMean), 1)}%가 됩니다. ` +
    "물론 회귀하지 않을 수도, 더 올라갈 수도 있습니다 — 그래서 '가정'입니다.";
  return total;
}

// ------------------------------------------------------------- Monte Carlo
const { values: triVals } = cleanPairs(panel.dates, panel.series.real_tri);
const monthlyRets = pctChange(triVals).slice(1);
let driftMode = "역사 평균 그대로";
const DRIFTS = ["역사 평균 그대로", "위 계산기 결과 사용"];
for (const m of DRIFTS) {
  const btn = document.createElement("button");
  btn.className = "vi-btn" + (m === driftMode ? " active" : "");
  btn.textContent = m;
  btn.addEventListener("click", () => {
    driftMode = m;
    document.querySelectorAll("#drift-btns .vi-btn").forEach((b) =>
      b.classList.toggle("active", b.textContent === m));
    drawMc();
  });
  $("drift-btns").appendChild(btn);
}

function drawMc() {
  const contrib = Number($("contrib").value);
  const years = Number($("years").value);
  $("years-label").textContent = years;
  const bogleTotal = drawBogle();
  const drift = driftMode === "역사 평균 그대로" ? null : bogleTotal;
  const sim = simulateDca(monthlyRets, contrib, years, {
    annualDriftTarget: drift, seed: contrib * 1000 + years,
  });

  const yearsAxis = sim.months.map((m) => m / 12);
  const p = sim.percentiles;
  const bandFill = (upper, lower, color, name) => [
    { x: yearsAxis, y: upper, mode: "lines", line: { width: 0 },
      showlegend: false, hoverinfo: "skip" },
    { x: yearsAxis, y: lower, mode: "lines", fill: "tonexty", fillcolor: color,
      line: { width: 0 }, name, hoverinfo: "skip" },
  ];
  const contribLine = sim.months.map((m) => m * contrib);
  render($("mc-chart"), [
    ...bandFill(p.p95, p.p5, "rgba(28,92,171,0.10)", "90% 구간"),
    ...bandFill(p.p75, p.p25, "rgba(28,92,171,0.18)", "50% 구간"),
    { x: yearsAxis, y: p.p50, mode: "lines", name: "중앙값",
      line: { color: "#1c5cab", width: 2.5 },
      hovertemplate: "%{x:.0f}년차: %{y:,.0f}만원<extra></extra>" },
    { x: yearsAxis, y: contribLine, mode: "lines", name: "납입 원금",
      line: { color: registry.chrome.muted, width: 1.5, dash: "dash" },
      hovertemplate: "%{x:.0f}년차 원금: %{y:,.0f}만원<extra></extra>" },
  ], baseLayout(registry, {
    xaxis: { title: { text: "경과 (년)" }, showgrid: false, linecolor: "#c3c2b7" },
    yaxis: { title: { text: "자산 (만원, 실질)" }, gridcolor: registry.chrome.grid },
  }, 420));

  const sorted = sim.finalWealth.slice().sort((a, b) => a - b);
  const stats = [
    ["납입 원금", sim.totalContributed],
    ["중앙값 결과", percentileLinear(sorted, 50)],
    ["하위 5% 결과", percentileLinear(sorted, 5)],
    ["상위 5% 결과", percentileLinear(sorted, 95)],
  ];
  $("mc-metrics").innerHTML = stats.map(([label, v]) => `
    <div class="card"><div class="metric-label">${label}</div>
    <div class="metric-value" style="font-size:1.3rem">${Math.round(v).toLocaleString("ko-KR")}만원</div>
    </div>`).join("");
  const lossProb =
    (sim.finalWealth.filter((w) => w < sim.totalContributed).length /
      sim.finalWealth.length) * 100;
  $("mc-note").textContent =
    `이 가정에서 ${years}년 뒤 자산이 납입 원금에 못 미칠 확률: ${lossProb.toFixed(0)}% ` +
    "(2,000회 시뮬레이션, 인플레이션 차감 실질 기준). 세금·수수료 미반영. " +
    "미래가 과거의 통계적 반복이라는 가정 자체가 시뮬레이션의 한계입니다.";
}

$("growth").addEventListener("input", drawMc);
capef.addEventListener("input", drawMc);
$("contrib").addEventListener("change", drawMc);
$("years").addEventListener("input", drawMc);

// 72 rule widget
function draw72() {
  const r = Number($("r72").value);
  $("r72-out").textContent =
    `연 ${r}%면 약 ${(72 / r).toFixed(1)}년마다 원금이 2배가 됩니다.`;
}
$("r72").addEventListener("input", draw72);
draw72();

drawMc();
