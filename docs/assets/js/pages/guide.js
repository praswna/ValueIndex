// 지표 가이드: σ 등급표, 조건부 분위 팬차트 + 현재 CAPE 리드아웃, 지표 해설.

import { load, fmt, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, hline } from "../charts.js";
import { interp } from "../stats.js";

injectNav();
const { meta, registry, overview, guide, content } =
  await load("registry", "overview", "guide", "content");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);

// σ rating table from registry (single source)
const FREQ = ["약 2%", "약 14%", "약 70%", "약 14%", "약 2%"];
const BOUNDS = ["평균 −2σ 아래", "−2σ ~ −1σ", "−1σ ~ +1σ", "+1σ ~ +2σ", "+2σ 위"];
$("rating-table").innerHTML = `<table class="vi">
  <tr><th>등급</th><th>의미</th><th>역사적 빈도</th></tr>
  ${registry.ratings.map((r, i) => `<tr>
    <td><span class="badge" style="background:${r.color}">${r.label_ko}</span></td>
    <td>${BOUNDS[i]}</td><td>${FREQ[i]}</td></tr>`).join("")}
</table>`;

// ---------------------------------------------------------------- fan chart
const fan = guide.fan;
const cur = guide.current_cape;
const bandFill = (upper, lower, color, name) => [
  { x: fan.x, y: upper, mode: "lines", line: { width: 0 }, showlegend: false,
    hoverinfo: "skip" },
  { x: fan.x, y: lower, mode: "lines", fill: "tonexty", fillcolor: color,
    line: { width: 0 }, name, hoverinfo: "skip" },
];
render($("fan-chart"), [
  { x: guide.scatter.cape, y: guide.scatter.fwd, mode: "markers",
    marker: { color: "#9ec5f4", size: 4, opacity: 0.5 }, name: "각 월 (1871~)",
    hovertemplate: "CAPE %{x:.1f} → 이후 10년 연 %{y:.1f}%<extra></extra>" },
  ...bandFill(fan.q95, fan.q5, "rgba(28,92,171,0.10)", "역사적 90% 구간"),
  ...bandFill(fan.q75, fan.q25, "rgba(28,92,171,0.18)", "역사적 50% 구간"),
  { x: fan.x, y: fan.q50, mode: "lines", name: "조건부 중앙값",
    line: { color: "#1c5cab", width: 2.5 },
    hovertemplate: "CAPE %{x:.1f}일 때 중앙값 연 %{y:.1f}%<extra></extra>" },
], baseLayout(registry, {
  hovermode: "closest",
  shapes: [
    { type: "line", xref: "x", yref: "paper", x0: cur, x1: cur, y0: 0, y1: 1,
      line: { color: "#c22f2f", width: 2 } },
    { ...hline(0, registry.chrome.muted) },
  ],
  annotations: [{ x: cur, y: 1, yref: "paper", yanchor: "bottom",
    text: `현재 CAPE ${cur.toFixed(1)}`, showarrow: false,
    font: { color: "#c22f2f" } }],
  xaxis: { title: { text: "그 시점의 CAPE" }, showgrid: false, linecolor: registry.chrome.axis_line },
  yaxis: { title: { text: "이후 10년 실질 총수익률 (연환산 %)" },
           gridcolor: registry.chrome.grid },
}, 460));

// readout at the current CAPE
const xs = [], q = { q5: [], q25: [], q50: [], q75: [], q95: [] };
for (let i = 0; i < fan.x.length; i++) {
  if (fan.q50[i] !== null) {
    xs.push(fan.x[i]);
    for (const k of Object.keys(q)) q[k].push(fan[k][i]);
  }
}
if (xs.length && cur >= xs[0] && cur <= xs[xs.length - 1]) {
  const at = (k) => interp(cur, xs, q[k]);
  $("fan-readout").innerHTML =
    `<b>지금 CAPE(${cur.toFixed(1)})와 비슷했던 과거 국면들의 이후 10년 실질수익률</b> — ` +
    `중앙값 <b>연 ${fmtSigned(at("q50"), 1)}%</b>, ` +
    `절반은 연 ${fmtSigned(at("q25"), 1)}%~${fmtSigned(at("q75"), 1)}% 사이, ` +
    `90%는 연 ${fmtSigned(at("q5"), 1)}%~${fmtSigned(at("q95"), 1)}% 사이였습니다. ` +
    `(커널 가중 분위 추정 — 예측이 아니라 역사적 조건부 분포입니다)`;
}

// ------------------------------------------------------- per-indicator guide
$("per-indicator").innerHTML = registry.valuation_keys.map((key) => {
  const m = registry.indicators[key];
  const s = overview.summaries[key];
  const parts = [];
  if (m.analogy_ko) parts.push(`<p><b>① 비유하면</b> — ${m.analogy_ko}</p>`);
  if (m.formula_ko) parts.push(`<p><b>② 공식</b> — <code>${m.formula_ko}</code></p>`);
  if (m.interpret_ko) parts.push(`<p><b>③ 해석</b> — ${m.interpret_ko}</p>`);
  if (s) parts.push(`<p><b>④ 지금은</b> — ${fmt(s.current, m.unit, registry)} ${m.unit}
    (역사 평균 ${fmt(s.mean, m.unit, registry)}, ${s.start_year}년 이후
    고평가 백분위 ${s.aligned_pctile.toFixed(0)})</p>`);
  if (m.caveats_ko.length) {
    parts.push("<p><b>⑤ 한계점</b></p><ul>" +
      m.caveats_ko.map((c) => `<li>${c}</li>`).join("") + "</ul>");
  }
  return `<details class="vi"><summary>${m.label_ko} — ${m.what_ko}</summary>
    ${parts.join("")}</details>`;
}).join("");

$("resources").innerHTML = content.resources_ko;
