// 개요 페이지: 메트릭 카드, PCA 종합지수, 게이지, 닮은 과거, 타임머신.
// 기본 뷰는 overview.json(사전계산), 타임머신은 클라이언트 재계산.

import { load, fmt, fmtSigned, ym } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import {
  baseLayout, render, lineTrace, recessionShapes, ratingBadge, ratingOf, hline,
} from "../charts.js";
import { asofIndex, cleanPairs, summary } from "../stats.js";
import { alignedZFromPanel, pcaComposite, nearestAnalogs, monthsBetween } from "../quant.js";
import { initCompare } from "../compare-section.js";
import { initSubtabs } from "../subtabs.js";

injectNav();
const { meta, registry, panel, overview } = await load("registry", "panel", "overview");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const KEYS = registry.valuation_keys;
const latestDate = overview.latest_month;

// ---------------------------------------------------------------- view model

function currentView() {
  return {
    asof: null,
    label: null,
    summaries: overview.summaries,
    pca: overview.pca,
    analogs: overview.analogs,
  };
}

function snapshotView(asof) {
  const summaries = {};
  for (const key of KEYS) {
    const metaI = registry.indicators[key];
    const { dates, values } = cleanPairs(panel.dates, panel.series[key]);
    const s = summary(dates, values, asof);
    if (!s || s.std === 0 || Number.isNaN(s.std)) continue;
    const alignedZ = metaI.higher_is_expensive ? s.z : -s.z;
    const alignedPct = metaI.higher_is_expensive ? s.pctile : 100 - s.pctile;
    summaries[key] = {
      current: s.current, asof: s.asof, mean: s.mean, std: s.std,
      pctile: s.pctile, z: s.z, aligned_z: alignedZ, aligned_pctile: alignedPct,
      rating: ratingOf(registry, alignedZ).key, delta_1y: s.delta_1y,
      start_year: Number(s.start.slice(0, 4)),
    };
  }

  const az = alignedZFromPanel(panel, registry, asof);
  const pcaRes = pcaComposite(KEYS, az.columns);
  const pcaPairs = cleanPairs(az.dates, pcaRes.composite);
  const pcaCurrent = pcaPairs.values[pcaPairs.values.length - 1];

  const tri = cleanPairs(panel.dates, panel.series.real_tri);
  const triCut = asofIndex(tri.dates, asof);
  const triD = tri.dates.slice(0, triCut + 1);
  const triV = tri.values.slice(0, triCut + 1);
  const cape = cleanPairs(panel.dates, panel.series.cape);

  const analogs = nearestAnalogs(KEYS, az.columns, az.dates).map((a) => {
    const ci = asofIndex(cape.dates, a.date);
    const bi = asofIndex(triD, a.date);
    const base = bi >= 0 ? triV[bi] : null;
    const fwd = {};
    for (const [label, months] of [["1y", 12], ["5y", 60], ["10y", 120]]) {
      let val = null;
      if (base) {
        const targetMonths = monthsBetween(triD[bi], triD[triD.length - 1]);
        if (targetMonths >= months) {
          // last tri value at-or-before analog date + months
          const y = Number(a.date.slice(0, 4)) + Math.floor((Number(a.date.slice(5, 7)) - 1 + months) / 12);
          const m = ((Number(a.date.slice(5, 7)) - 1 + months) % 12) + 1;
          const fi = asofIndex(triD, `${y}-${String(m).padStart(2, "0")}-28`);
          if (fi > bi) val = (Math.pow(triV[fi] / base, 12 / months) - 1) * 100;
        }
      }
      fwd[label] = val;
    }
    const pathMonths = [], pathValues = [];
    for (let i = bi; i < triD.length && monthsBetween(a.date, triD[i]) <= 120; i++) {
      pathMonths.push(monthsBetween(a.date, triD[i]));
      pathValues.push((triV[i] / triV[bi]) * 100);
    }
    return {
      date: a.date, distance: a.distance,
      cape_then: ci >= 0 ? cape.values[ci] : null,
      fwd, path_months: pathMonths, path_values: pathValues,
    };
  });

  return {
    asof,
    label: ym(asof),
    summaries,
    pca: {
      dates: pcaPairs.dates, values: pcaPairs.values,
      weights: pcaRes.weights, explained_ratio: pcaRes.explained,
      current: pcaCurrent, rating: ratingOf(registry, pcaCurrent).key,
    },
    analogs,
  };
}

// ------------------------------------------------------------------- render

function renderBanner(view) {
  $("tm-banner").innerHTML = view.asof
    ? `<div class="box box-warn">🕰️ <b>${view.label} 시점 스냅샷</b>을 보고 있습니다 —
       그 시점까지의 데이터만으로 다시 계산했습니다. '현재' 버튼으로 돌아옵니다.</div>`
    : "";
}

function renderPca(view) {
  const p = view.pca;
  $("pca-value").textContent = fmtSigned(p.current, 2);
  $("pca-badge").innerHTML = ratingBadge(registry, p.rating);
  $("pca-note").textContent =
    `이 한 축이 지표 전체 변동의 ${(p.explained_ratio * 100).toFixed(0)}%를 설명합니다 ` +
    "— 지표들이 결국 같은 것을 재고 있다는 수학적 증거입니다.";

  const band = registry.ratings.find((r) => r.key === p.rating);
  const shapes = [0, 1, -1, 2, -2].map((y) =>
    hline(y, registry.chrome.muted, y === 0 ? "solid" : "dot")
  );
  const traces = [
    lineTrace(p.dates, p.values, "종합 지수", registry.series_colors.cape,
      { hovertemplate: "%{x|%Y-%m}: %{y:+.2f}σ<extra></extra>" }),
    {
      x: [p.dates[p.dates.length - 1]], y: [p.current], mode: "markers",
      marker: { color: band.color, size: 10 }, showlegend: false,
      hovertemplate: `현재 ${fmtSigned(p.current, 2)}σ<extra></extra>`,
    },
  ];
  render($("pca-chart"), traces,
    baseLayout(registry, { showlegend: false, shapes,
      yaxis: { title: { text: "종합 고평가 지수 (σ)" }, gridcolor: registry.chrome.grid } }, 260));

  const rows = Object.entries(p.weights)
    .sort((a, b) => b[1] - a[1])
    .map(([k, w]) =>
      `<tr><td>${registry.indicators[k].label_ko}</td><td class="num">${w.toFixed(3)}</td></tr>`)
    .join("");
  $("pca-weights").innerHTML =
    `<table class="vi"><tr><th>지표</th><th>가중치</th></tr>${rows}</table>`;
}

function renderCards(view) {
  const cards = [];
  let anyShort = false;
  for (const key of KEYS) {
    const s = view.summaries[key];
    if (!s) continue;
    const m = registry.indicators[key];
    const topPct = 100 - s.aligned_pctile;
    const topTxt = topPct < 1 ? "역대 상위 1% 이내" : `역대 상위 ${topPct.toFixed(0)}%`;
    const asofYear = Number((view.asof ?? latestDate).slice(0, 4));
    const short = asofYear - s.start_year < 30;
    anyShort = anyShort || short;
    const delta = s.delta_1y !== null
      ? `<span class="metric-delta">${fmtSigned(s.delta_1y)} (1년 전 대비)</span>` : "";
    cards.push(`<div class="card" title="${m.what_ko}">
      <div class="metric-label">${m.label_ko} (${m.unit})</div>
      <div class="metric-value">${fmt(s.current, m.unit, registry)}</div>
      ${delta}
      <div class="metric-note">${ratingBadge(registry, s.rating)}
        고평가 ${topTxt} · ${s.start_year}년~${short ? " ⚠️" : ""}</div>
    </div>`);
  }
  $("cards").innerHTML = cards.join("");
  $("short-note").textContent = anyShort
    ? "⚠️ 표시는 히스토리가 30년 미만이라 백분위·등급의 신뢰도가 낮다는 뜻입니다." : "";
}

function renderGauge(view) {
  const rows = KEYS.filter((k) => view.summaries[k])
    .map((k) => ({ k, s: view.summaries[k] }))
    .sort((a, b) => a.s.aligned_pctile - b.s.aligned_pctile);
  const bandColor = (s) =>
    registry.ratings.find((r) => r.key === s.rating).color;
  render($("gauge"), [{
    type: "bar", orientation: "h",
    x: rows.map((r) => r.s.aligned_pctile),
    y: rows.map((r) => registry.indicators[r.k].label_ko),
    marker: { color: rows.map((r) => bandColor(r.s)) },
    text: rows.map((r) => r.s.aligned_pctile.toFixed(0)),
    textposition: "outside", width: 0.55,
    hovertemplate: "%{y}: 백분위 %{x:.0f}<extra></extra>",
  }], baseLayout(registry, {
    hovermode: "closest", showlegend: false,
    xaxis: { range: [0, 108], title: { text: "고평가 백분위 (0 = 역사상 최저, 100 = 최고)" },
             showgrid: false, linecolor: registry.chrome.axis_line },
    yaxis: { gridcolor: "rgba(0,0,0,0)", automargin: true },
    margin: { l: 10, r: 10, t: 10, b: 40 },
  }, 380));
}

function renderTable(view) {
  const rows = KEYS.filter((k) => view.summaries[k]).map((k) => {
    const s = view.summaries[k];
    const m = registry.indicators[k];
    return `<tr>
      <td>${m.label_ko}</td>
      <td class="num">${fmt(s.current, m.unit, registry)}</td>
      <td>${ym(s.asof)}</td>
      <td>${ratingBadge(registry, s.rating)}</td>
      <td class="num">${s.aligned_pctile.toFixed(0)}</td>
      <td class="num">${fmt(s.mean, m.unit, registry)}</td>
      <td class="num">${fmtSigned(s.aligned_z)}</td>
      <td class="num">${s.start_year}</td>
      <td>${m.source}</td>
    </tr>`;
  }).join("");
  $("summary-table").innerHTML = `<table class="vi">
    <tr><th>지표</th><th>현재값</th><th>기준일</th><th>등급</th><th>고평가 백분위</th>
        <th>역사 평균</th><th>z-score</th><th>히스토리 시작</th><th>출처</th></tr>
    ${rows}</table>`;
}

function renderAnalogs(view) {
  if (!view.analogs.length) {
    $("analog-table").innerHTML = "";
    $("analog-chart").innerHTML = "비교할 수 있는 과거 데이터가 부족합니다.";
    return;
  }
  const fwdTxt = (v) => (v === null || v === undefined ? "-" : `${fmtSigned(v, 1)}%`);
  const rows = view.analogs.map((a) => `<tr>
    <td>${ym(a.date).replace("-", "년 ")}월</td>
    <td class="num">${a.distance.toFixed(2)}σ</td>
    <td class="num">${a.cape_then === null ? "-" : a.cape_then.toFixed(1)}</td>
    <td class="num">${fwdTxt(a.fwd["1y"])}</td>
    <td class="num">${fwdTxt(a.fwd["5y"])}</td>
    <td class="num">${fwdTxt(a.fwd["10y"])}</td>
  </tr>`).join("");
  $("analog-table").innerHTML = `<table class="vi">
    <tr><th>시기</th><th>지표당 차이</th><th>그때 CAPE</th>
        <th>이후 1년</th><th>이후 5년(연)</th><th>이후 10년(연)</th></tr>${rows}</table>`;

  const c = registry.series_colors;
  const palette = [c.cape, c.buffett, c.pb, c.pe];
  const traces = view.analogs
    .filter((a) => a.path_months.length > 1)
    .map((a, i) => ({
      x: a.path_months, y: a.path_values, mode: "lines", name: ym(a.date),
      line: { color: palette[i % palette.length], width: 2 },
      hovertemplate: `${ym(a.date)} + %{x}개월: %{y:.0f}<extra></extra>`,
    }));
  render($("analog-chart"), traces, baseLayout(registry, {
    shapes: [hline(100, registry.chrome.muted)],
    xaxis: { title: { text: "닮은 시점 이후 경과 (개월)" }, showgrid: false, linecolor: registry.chrome.axis_line },
    yaxis: { title: { text: "실질 총수익 지수 (시작=100)" }, gridcolor: registry.chrome.grid },
  }, 380));
}

function renderAll(view) {
  renderBanner(view);
  renderPca(view);
  renderCards(view);
  renderGauge(view);
  renderTable(view);
  renderAnalogs(view);
}

// ------------------------------------------------------------- time machine

function setAsof(asof) {
  renderAll(asof === null ? currentView() : snapshotView(asof));
}

const presetWrap = $("tm-presets");
const presets = { "현재": null, ...registry.time_machine_presets };
for (const [label, date] of Object.entries(presets)) {
  const btn = document.createElement("button");
  btn.className = "vi-btn";
  btn.textContent = label;
  btn.addEventListener("click", () => {
    setAsof(date);
    if (date) $("tm-year").value = Number(date.slice(0, 4));
  });
  presetWrap.appendChild(btn);
}
const yearInput = $("tm-year");
yearInput.max = Number(latestDate.slice(0, 4));
yearInput.value = yearInput.max;
yearInput.addEventListener("change", () => {
  const y = Number(yearInput.value);
  $("tm-year-label").textContent = y;
  setAsof(y >= Number(yearInput.max) ? null : `${y}-06-01`);
});
yearInput.addEventListener("input", () => {
  $("tm-year-label").textContent = yearInput.value;
});
$("tm-year-label").textContent = yearInput.value;

renderAll(currentView());

// --------------------------- compare section (lazy on first tab selection)
let cmpReady = false;
document.getElementById("index-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest('[data-tab="compare"]');
  if (btn && !cmpReady) {
    cmpReady = true;
    initCompare({ registry, panel, overview });
  }
});

const selectIndexTab = initSubtabs("index-tabs", [
  { id: "main", label: "종합지수", section: "itab-main" },
  { id: "cards", label: "지표·게이지", section: "itab-cards" },
  { id: "analogs", label: "닮은 과거", section: "itab-analogs" },
  { id: "compare", label: "비교", section: "itab-compare" },
]);
// deep link straight to the compare tab still needs its init
if (location.hash === "#compare" && !cmpReady) {
  cmpReady = true;
  initCompare({ registry, panel, overview });
}
