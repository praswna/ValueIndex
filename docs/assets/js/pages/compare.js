// 비교 차트: 지표 다중선택 + Z/백분위/원값 + 침체 음영 + 상관 히트맵.

import { load } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, recessionShapes, hline } from "../charts.js";
import { cleanPairs, percentileRanks, zscores, asofIndex } from "../stats.js";

injectNav();
const { meta, registry, panel, overview } = await load("registry", "panel", "overview");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const KEYS = registry.valuation_keys;
const DEFAULT = ["cape", "buffett", "pe"];
const MODES = ["Z-점수", "백분위", "원값"];
let selected = new Set(DEFAULT);
let mode = "Z-점수";

const years = [...new Set(panel.dates.map((d) => Number(d.slice(0, 4))))];
const minYear = years[0], maxYear = years[years.length - 1];
const fromInput = $("from-year");
fromInput.min = minYear;
fromInput.max = maxYear - 1;
fromInput.value = Math.max(minYear, 1950);

// picker checkboxes
for (const key of KEYS) {
  const label = document.createElement("label");
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = selected.has(key);
  cb.addEventListener("change", () => {
    if (cb.checked) {
      if (selected.size >= 4) { cb.checked = false; return; }
      selected.add(key);
    } else selected.delete(key);
    draw();
  });
  label.appendChild(cb);
  label.appendChild(document.createTextNode(registry.indicators[key].label_ko));
  $("picker").appendChild(label);
}
// mode buttons
for (const m of MODES) {
  const btn = document.createElement("button");
  btn.className = "vi-btn" + (m === mode ? " active" : "");
  btn.textContent = m;
  btn.addEventListener("click", () => {
    mode = m;
    document.querySelectorAll("#norm-btns .vi-btn").forEach((b) =>
      b.classList.toggle("active", b.textContent === m));
    draw();
  });
  $("norm-btns").appendChild(btn);
}
$("rec").addEventListener("change", draw);
fromInput.addEventListener("change", draw);
fromInput.addEventListener("input", () => { $("from-label").textContent = fromInput.value; });

function draw() {
  $("from-label").textContent = fromInput.value;
  const start = `${fromInput.value}-01-01`;
  const keys = KEYS.filter((k) => selected.has(k));
  if (!keys.length) return;

  const series = keys.map((k) => {
    let { dates, values } = cleanPairs(panel.dates, panel.series[k]);
    if (mode === "Z-점수") values = zscores(values);
    else if (mode === "백분위") values = percentileRanks(values);
    const i0 = Math.max(0, asofIndex(dates, start));
    return { k, dates: dates.slice(i0), values: values.slice(i0) };
  });

  const shapes = $("rec").checked
    ? recessionShapes(registry, overview.recessions, start) : [];
  let layout, traces;

  if (mode === "원값") {
    // one small multiple per indicator — never a dual axis
    const n = series.length;
    traces = [];
    layout = baseLayout(registry, { showlegend: false, shapes: [], annotations: [] },
      220 * n);
    series.forEach((s, i) => {
      const ax = i === 0 ? "" : String(i + 1);
      traces.push({
        x: s.dates, y: s.values, mode: "lines",
        name: registry.indicators[s.k].label_ko,
        line: { color: registry.series_colors[s.k], width: 2 },
        xaxis: "x" + ax, yaxis: "y" + ax,
      });
      const top = 1 - (i / n), bottom = 1 - ((i + 1) / n) + 0.06;
      layout["yaxis" + ax] = {
        domain: [bottom, top - 0.02], gridcolor: registry.chrome.grid,
        zerolinecolor: "#c3c2b7",
      };
      layout["xaxis" + ax] = {
        anchor: "y" + ax, showgrid: false, linecolor: "#c3c2b7",
        matches: i === 0 ? undefined : "x",
        showticklabels: i === n - 1,
      };
      layout.annotations.push({
        text: `${registry.indicators[s.k].label_ko} (${registry.indicators[s.k].unit})`,
        xref: "paper", yref: "paper", x: 0, y: top, yanchor: "bottom",
        showarrow: false, font: { size: 12, color: "#52514e" },
      });
      if ($("rec").checked) {
        layout.shapes.push(...recessionShapes(registry, overview.recessions, start)
          .map((sh) => ({ ...sh, xref: "x" + ax, yref: "paper",
                          y0: bottom, y1: top - 0.02 })));
      }
    });
    $("norm-note").textContent =
      "단위가 달라 지표별 개별 축으로 표시합니다 (이중축은 왜곡을 만들어 쓰지 않습니다).";
  } else {
    traces = series.map((s) => ({
      x: s.dates, y: s.values, mode: "lines",
      name: registry.indicators[s.k].label_ko,
      line: { color: registry.series_colors[s.k], width: 2 },
    }));
    const ytitle = mode === "Z-점수" ? "z-score (전체 역사 기준)" : "백분위 (전체 역사 기준)";
    if (mode === "Z-점수") {
      for (const [y, dash] of [[0, "solid"], [1, "dot"], [-1, "dot"], [2, "dash"], [-2, "dash"]]) {
        shapes.push({ ...hline(y, registry.chrome.muted, dash), opacity: 0.5 });
      }
    }
    layout = baseLayout(registry, {
      shapes, yaxis: { title: { text: ytitle }, gridcolor: registry.chrome.grid },
    }, 480);
    $("norm-note").textContent =
      "주의: Z-점수/백분위는 방향을 정렬하지 않은 원지표 기준입니다. " +
      "ECY·배당수익률·Fed 스프레드는 값이 낮을수록 고평가입니다.";
  }
  render($("chart"), traces, layout);
}

draw();

// ------------------------------------------------------ correlation heatmap
const labels = overview.corr.keys.map((k) => registry.indicators[k].label_ko);
render($("heatmap"), [{
  type: "heatmap",
  z: overview.corr.matrix, x: labels, y: labels,
  zmin: -1, zmax: 1,
  colorscale: [[0, "#1c5cab"], [0.5, "#f0efec"], [1, "#c22f2f"]],
  text: overview.corr.matrix.map((row) => row.map((v) => v.toFixed(2))),
  texttemplate: "%{text}",
  hovertemplate: "%{y} × %{x}: %{z:.2f}<extra></extra>",
  colorbar: { title: { text: "상관" } },
}], baseLayout(registry, {
  hovermode: "closest",
  yaxis: { autorange: "reversed", automargin: true },
  xaxis: { automargin: true },
  margin: { l: 10, r: 10, t: 10, b: 10 },
}, 520));
