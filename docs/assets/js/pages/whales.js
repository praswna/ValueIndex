// 🐋 큰손 추적기: 기관별 13F 보유 종목 + 직전 분기 대비 변화.

import { load } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render } from "../charts.js";

injectNav();
const { meta, registry, whales } = await load("registry", "whales");
injectFooter(meta, registry);

const root = document.getElementById("whales");
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

function statusTag(status) {
  if (status === "live" || status === "snapshot") return "";
  return ` <span class="badge" style="background:#898781">⚠️ 예시 데이터</span>`;
}

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
  const rows = groups
    .map(
      ([title, list]) =>
        `<div class="chg-row"><span class="chg-title">${title}</span>
          <span class="chg-names">${list.join(", ")}</span></div>`
    )
    .join("");
  return `<div class="chg-head">${w.prior_quarter} 대비 변화</div>${rows}`;
}

if (whales.unavailable || !whales.whales || !whales.whales.length) {
  root.innerHTML =
    '<div class="box box-warn">현재 큰손 데이터를 불러오지 못했습니다. 자동 갱신이 복구되면 표시됩니다.</div>';
} else {
  root.innerHTML = whales.whales
    .map((w) => {
      const noteClass = w.region === "KR" ? "box-warn" : "box-info";
      return `<section class="whale-card">
        <div class="whale-head">
          <h2>${FLAG[w.region] || ""} ${w.name_ko}</h2>
          <div class="caption">${w.as_of} 기준 · 미국주식 ${w.holdings_count}종목 ·
            총 ${usd(w.total_value)} · 상위5 집중도 ${pct(w.top5_weight)}${statusTag(w.status)}</div>
        </div>
        <div class="box ${noteClass} note-sm">${w.note}</div>
        <div class="grid-2">
          <div><div id="wc-${w.slug}" class="chart"></div>
            <div class="caption">막대 색 = 지난 분기 행동:
              <b style="color:${CHG.new.c}">신규</b> ·
              <b style="color:${CHG.up.c}">늘림</b> ·
              <b style="color:${CHG.down.c}">줄임</b> ·
              <span style="color:${CHG.flat.c}">유지</span></div>
          </div>
          <div class="whale-changes">${changesBlock(w)}</div>
        </div>
        ${w.history && w.history.quarters.length >= 2
          ? `<h3 class="wh-title">미국주식 운용규모 추이</h3>
             <div id="wh-${w.slug}" class="chart"></div>
             <div class="caption">분기가 쌓일수록 길어지는 기록입니다 (13F 공시 기준, 미국 상장주식만).</div>`
          : ""}
      </section>`;
    })
    .join("");

  for (const w of whales.whales) {
    const top = w.top;
    // horizontal bars, largest at top -> reverse for Plotly's bottom-up order
    const names = top.map((h) => h.name).reverse();
    const weights = top.map((h) => h.weight).reverse();
    const colors = top.map((h) => (CHG[h.chg_kind] || CHG.flat).c).reverse();
    const hover = top
      .map(
        (h) =>
          `${h.name}<br>비중 ${pct(h.weight)} · ${usd(h.value)}` +
          (h.chg_pct !== null && h.chg_kind !== "new"
            ? `<br>주식수 ${h.chg_pct > 0 ? "+" : ""}${h.chg_pct.toFixed(1)}%`
            : h.chg_kind === "new" ? "<br>신규 매수" : "")
      )
      .reverse();
    const height = Math.max(200, names.length * 34 + 60);
    render(
      document.getElementById(`wc-${w.slug}`),
      [{
        type: "bar", orientation: "h", x: weights, y: names,
        marker: { color: colors }, hovertext: hover, hoverinfo: "text",
        text: weights.map((v) => pct(v)), textposition: "auto",
      }],
      baseLayout(registry, {
        hovermode: "closest",
        margin: { l: 165, r: 14, t: 8, b: 34 },
        xaxis: { title: { text: "포트폴리오 비중 %" }, gridcolor: registry.chrome.grid },
        yaxis: { automargin: true },
      }, height)
    );

    if (w.history && w.history.quarters.length >= 2) {
      const h = w.history;
      const hover = h.quarters.map(
        (q, i) =>
          `${q}<br>총 ${usd(h.total_value[i])} · ${h.holdings_count[i]}종목` +
          (h.top5_weight[i] !== null ? `<br>상위5 집중도 ${pct(h.top5_weight[i])}` : "")
      );
      render(
        document.getElementById(`wh-${w.slug}`),
        [{
          type: "bar", x: h.quarters, y: h.total_value.map((v) => v / 1e9),
          marker: { color: "#2a78d6" }, hovertext: hover, hoverinfo: "text",
        }],
        baseLayout(registry, {
          hovermode: "closest", showlegend: false,
          margin: { l: 55, r: 14, t: 8, b: 34 },
          xaxis: { type: "category" },
          yaxis: { title: { text: "$B" }, gridcolor: registry.chrome.grid },
        }, 190)
      );
    }
  }
}
