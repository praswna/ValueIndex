// 🐋 큰손 추적기: 기관 타일 한 화면 + 탭하면 팝업(보유 종목·분기 변화·규모 추이).

import { load } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render } from "../charts.js";

injectNav();
const { meta, registry, whales } = await load("registry", "whales");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const FLAG = { US: "🇺🇸", KR: "🇰🇷", NO: "🇳🇴" };
// bar color encodes what the whale DID with the position last quarter
const CHG = {
  new: { c: "#1baf7a", label: "신규" },
  up: { c: "#2a78d6", label: "늘림" },
  down: { c: "#e34948", label: "줄임" },
  flat: { c: "#898781", label: "유지" },
};

function usd(v) {
  if (v === null || v === undefined) return "-";
  const a = Math.abs(v);
  if (a >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (a >= 1e6) return "$" + (v / 1e6).toFixed(0) + "M";
  return "$" + Math.round(v).toLocaleString("en-US");
}
const pct = (v) => (v === null || v === undefined ? "-" : v.toFixed(1) + "%");

// ---- tiles ----
if (whales.unavailable || !whales.whales || !whales.whales.length) {
  $("unavailable").innerHTML =
    '<div class="box box-warn">현재 큰손 데이터를 불러오지 못했습니다. 자동 갱신이 복구되면 표시됩니다.</div>';
} else {
  $("whale-tiles").innerHTML = whales.whales.map((w) => `
    <button class="tile" data-slug="${w.slug}">
      <span class="tile-label">${FLAG[w.region] || ""} ${w.name_ko}</span>
      <span class="tile-value">${usd(w.total_value)}</span>
      <span class="tile-sub">${w.as_of} · ${w.holdings_count}종목${
        w.status === "live" || w.status === "snapshot" ? "" : " · ⚠️ 예시"}</span>
    </button>`).join("");
}

// ---- modal ----
const overlay = $("modal-overlay");
function closeModal() {
  overlay.hidden = true;
  document.body.style.overflow = "";
}
$("modal-close").addEventListener("click", closeModal);
overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

function changesBlock(w) {
  if (!w.prior_quarter) {
    return `<div class="caption">직전 분기 데이터가 없어 변화를 계산할 수 없습니다 (첫 공시).</div>`;
  }
  const groups = [
    ["🟢 신규 매수", w.changes.new],
    ["🔴 전량 매도", w.changes.exited],
    ["▲ 늘림", w.changes.increased],
    ["▽ 줄임", w.changes.decreased],
  ].filter(([, list]) => list && list.length);
  if (!groups.length) return `<div class="caption">직전 분기 대비 유의미한 변동이 없습니다.</div>`;
  return `<div class="chg-head">${w.prior_quarter} 대비 변화</div>` + groups
    .map(([title, list]) =>
      `<div class="chg-row"><span class="chg-title">${title}</span>
        <span class="chg-names">${list.join(", ")}</span></div>`)
    .join("");
}

function openWhale(slug) {
  const w = whales.whales.find((x) => x.slug === slug);
  if (!w) return;
  const noteClass = w.region === "KR" ? "box-warn" : "box-info";
  const hasHist = w.history && w.history.quarters.length >= 2;
  $("modal-body").innerHTML = `
    <h2 style="margin:0 0 2px">${FLAG[w.region] || ""} ${w.name_ko}</h2>
    <div class="caption">${w.as_of} 기준 · 미국주식 ${w.holdings_count}종목 ·
      총 ${usd(w.total_value)} · 상위5 집중도 ${pct(w.top5_weight)}${
      w.status === "live" || w.status === "snapshot"
        ? "" : ' · <span class="badge" style="background:#898781">⚠️ 예시 데이터</span>'}</div>
    <div class="box ${noteClass} note-sm">${w.note}</div>
    <h3 style="margin-top:12px">상위 보유 종목</h3>
    <div id="m-top" class="chart"></div>
    <div class="caption">막대 색 = 지난 분기 행동:
      <b style="color:${CHG.new.c}">신규</b> ·
      <b style="color:${CHG.up.c}">늘림</b> ·
      <b style="color:${CHG.down.c}">줄임</b> ·
      <span style="color:${CHG.flat.c}">유지</span></div>
    <div class="whale-changes">${changesBlock(w)}</div>
    ${hasHist ? `<h3 style="margin-top:16px">미국주식 운용규모 추이</h3>
      <div id="m-hist" class="chart"></div>
      <div class="caption">분기가 쌓일수록 길어지는 기록입니다 (13F 공시 기준).</div>` : ""}`;
  overlay.hidden = false;
  document.body.style.overflow = "hidden";

  const top = w.top;
  const names = top.map((h) => h.name).reverse();
  const weights = top.map((h) => h.weight).reverse();
  const colors = top.map((h) => (CHG[h.chg_kind] || CHG.flat).c).reverse();
  const hover = top.map(
    (h) =>
      `${h.name}<br>비중 ${pct(h.weight)} · ${usd(h.value)}` +
      (h.chg_pct !== null && h.chg_kind !== "new"
        ? `<br>주식수 ${h.chg_pct > 0 ? "+" : ""}${h.chg_pct.toFixed(1)}%`
        : h.chg_kind === "new" ? "<br>신규 매수" : "")
  ).reverse();
  render($("m-top"), [{
    type: "bar", orientation: "h", x: weights, y: names,
    marker: { color: colors }, hovertext: hover, hoverinfo: "text",
    text: weights.map((v) => pct(v)), textposition: "auto",
  }], baseLayout(registry, {
    hovermode: "closest",
    margin: { l: 150, r: 10, t: 6, b: 30 },
    xaxis: { title: { text: "포트폴리오 비중 %" }, gridcolor: registry.chrome.grid },
    yaxis: { automargin: true, tickfont: { size: 10.5 } },
  }, Math.max(190, names.length * 30 + 50)));

  if (hasHist) {
    const h = w.history;
    const hhover = h.quarters.map(
      (q, i) =>
        `${q}<br>총 ${usd(h.total_value[i])} · ${h.holdings_count[i]}종목` +
        (h.top5_weight[i] !== null ? `<br>상위5 집중도 ${pct(h.top5_weight[i])}` : "")
    );
    render($("m-hist"), [{
      type: "bar", x: h.quarters, y: h.total_value.map((v) => v / 1e9),
      marker: { color: "#2a78d6" }, hovertext: hhover, hoverinfo: "text",
    }], baseLayout(registry, {
      hovermode: "closest", showlegend: false,
      margin: { l: 50, r: 10, t: 6, b: 30 },
      xaxis: { type: "category" },
      yaxis: { title: { text: "$B" }, gridcolor: registry.chrome.grid },
    }, 170));
  }
}

$("whale-tiles").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (tile) openWhale(tile.dataset.slug);
});
