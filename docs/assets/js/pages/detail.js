// 지표 상세: 히스토리 + σ밴드, 분포 히스토그램, 반감기, 설명.

import { load, fmt, fmtSigned, ym } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, lineTrace, recessionShapes, ratingBadge } from "../charts.js";
import { cleanPairs } from "../stats.js";

injectNav();
const { meta, registry, panel, overview } = await load("registry", "panel", "overview");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const picker = $("picker");
for (const key of registry.valuation_keys) {
  const opt = document.createElement("option");
  opt.value = key;
  opt.textContent = registry.indicators[key].label_ko;
  picker.appendChild(opt);
}
picker.addEventListener("change", () => draw(picker.value));

function bandRect(y0, y1, color) {
  return { type: "rect", xref: "paper", yref: "y", x0: 0, x1: 1, y0, y1,
           fillcolor: color, line: { width: 0 }, layer: "below" };
}

function draw(key) {
  const m = registry.indicators[key];
  const s = overview.summaries[key];
  const band = registry.ratings.find((r) => r.key === s.rating);
  const { dates, values } = cleanPairs(panel.dates, panel.series[key]);

  $("title").textContent = m.label_ko;
  $("badge").innerHTML = ratingBadge(registry, s.rating);
  const direction = m.higher_is_expensive ? "높을수록 고평가" : "낮을수록 고평가";
  $("subtitle").textContent = `${m.what_ko} (${direction} · 출처: ${m.source})`;

  const hl = s.half_life_months;
  const cards = [
    ["현재값", `${fmt(s.current, m.unit, registry)} ${m.unit}`, `기준: ${ym(s.asof)}`],
    ["역사 평균", fmt(s.mean, m.unit, registry), `±1σ = ${fmt(s.std, m.unit, registry)}`],
    ["고평가 백분위", `${s.aligned_pctile.toFixed(0)} / 100`, ""],
    ["z-score (방향 정렬)", `${fmtSigned(s.aligned_z)}σ`, ""],
    ["평균회귀 반감기", hl ? `약 ${(hl / 12).toFixed(1)}년` : "회귀 성향 약함",
     "이탈이 절반으로 줄어드는 기대 시간 (AR(1) 근사)"],
  ];
  $("metrics").innerHTML = cards.map(([label, value, note]) => `
    <div class="card"><div class="metric-label">${label}</div>
    <div class="metric-value" style="font-size:1.25rem">${value}</div>
    <div class="metric-note">${note}</div></div>`).join("");

  // history with constant ±1σ/±2σ bands
  const shapes = [
    bandRect(s.mean - 2 * s.std, s.mean + 2 * s.std, "rgba(137,135,129,0.10)"),
    bandRect(s.mean - s.std, s.mean + s.std, "rgba(137,135,129,0.14)"),
    { type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: s.mean, y1: s.mean,
      line: { color: registry.chrome.muted, width: 1, dash: "dash" } },
    ...recessionShapes(registry, overview.recessions, dates[0]),
  ];
  render($("history"), [
    lineTrace(dates, values, m.label_ko, registry.series_colors[key]),
    { x: [dates[dates.length - 1]], y: [values[values.length - 1]], mode: "markers",
      marker: { color: band.color, size: 10 }, name: "현재",
      hovertemplate: "현재: %{y:.2f}<extra></extra>" },
  ], baseLayout(registry, {
    shapes, yaxis: { title: { text: `${m.label_ko} (${m.unit})` },
                     gridcolor: registry.chrome.grid },
  }, 460));

  // distribution histogram
  render($("hist"), [{
    type: "histogram", x: values, nbinsx: 60,
    marker: { color: "#9ec5f4" },
    hovertemplate: "구간 %{x}: %{y}개월<extra></extra>",
  }], baseLayout(registry, {
    hovermode: "closest", showlegend: false,
    shapes: [{ type: "line", xref: "x", yref: "paper", x0: s.current, x1: s.current,
               y0: 0, y1: 1, line: { color: band.color, width: 2 } }],
    annotations: [{ x: s.current, y: 1, yref: "paper", yanchor: "bottom",
      text: `현재 ${fmt(s.current, m.unit, registry)} (백분위 ${s.pctile.toFixed(0)})`,
      showarrow: false, font: { color: band.color } }],
    xaxis: { title: { text: `${m.label_ko} (${m.unit})` }, showgrid: false,
             linecolor: registry.chrome.axis_line },
    yaxis: { title: { text: "개월 수" }, gridcolor: registry.chrome.grid },
  }, 320));

  // explanation
  const parts = [];
  if (m.analogy_ko) parts.push(`<p><b>비유하면</b> — ${m.analogy_ko}</p>`);
  if (m.formula_ko) parts.push(`<p><b>공식</b> — <code>${m.formula_ko}</code></p>`);
  if (m.interpret_ko) parts.push(`<p><b>해석</b> — ${m.interpret_ko}</p>`);
  if (m.caveats_ko.length) {
    parts.push("<p><b>주의할 점</b></p><ul>" +
      m.caveats_ko.map((c) => `<li>${c}</li>`).join("") + "</ul>");
  }
  $("explain").innerHTML = parts.join("");
}

draw(registry.valuation_keys[0]);
