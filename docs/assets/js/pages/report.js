// 📋 월간 점검: 지난 한 달의 등급/종합지수/매크로 변화 + 큰손 새 공시 다이제스트.

import { load, fmt, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { ratingBadge } from "../charts.js";
import { initSubtabs } from "../subtabs.js";

injectNav();
const { meta, registry, report } = await load("registry", "report");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const label = (key) =>
  (registry.indicators[key] && registry.indicators[key].label_ko) || key;
const unit = (key) =>
  (registry.indicators[key] && registry.indicators[key].unit) || "";

// ---- headline ----
const changes = report.ratings.filter((r) => r.changed);
const compChanged = report.composite.rating_now !== report.composite.rating_prev;
if (!changes.length && !compChanged) {
  $("headline").innerHTML = `<div class="box box-good"><b>✅ ${report.month_prev} →
    ${report.month_now}: 등급 변화 없음.</b> 이번 달 점검은 여기서 끝내도 됩니다.</div>`;
} else {
  const items = changes.map((r) =>
    `<li><b>${label(r.key)}</b>: ${ratingBadge(registry, r.rating_prev)} →
     ${ratingBadge(registry, r.rating_now)}</li>`);
  if (compChanged) {
    items.unshift(`<li><b>종합 밸류에이션</b>:
      ${ratingBadge(registry, report.composite.rating_prev)} →
      ${ratingBadge(registry, report.composite.rating_now)}</li>`);
  }
  $("headline").innerHTML = `<div class="box box-warn"><b>🔔 이번 달 등급 변화
    ${items.length}건</b><ul style="margin:6px 0 0 18px">${items.join("")}</ul>
    행동하기 전에 <a href="discipline.html">시나리오 규칙</a>을 먼저 확인하세요.</div>`;
}

// ---- composite ----
const c = report.composite;
$("composite").innerHTML = `
  <div class="card"><div class="metric-label">지금 (${report.month_now})</div>
    <div class="metric-value">${c.now === null ? "-" : c.now.toFixed(2)}σ</div>
    <div class="metric-note">${ratingBadge(registry, c.rating_now)}</div></div>
  <div class="card"><div class="metric-label">한 달 전 (${report.month_prev})</div>
    <div class="metric-value">${c.prev === null ? "-" : c.prev.toFixed(2)}σ</div>
    <div class="metric-note">${ratingBadge(registry, c.rating_prev)}</div></div>`;

// ---- per-indicator table ----
$("ratings-tbl").innerHTML =
  `<tr><th>지표</th><th>현재값</th><th>한 달 전</th><th>지금</th><th>변화</th></tr>` +
  report.ratings.map((r) => `
    <tr><td>${label(r.key)}</td>
    <td class="num">${fmt(r.value_now, unit(r.key), registry)} ${unit(r.key)}</td>
    <td>${ratingBadge(registry, r.rating_prev)}</td>
    <td>${ratingBadge(registry, r.rating_now)}</td>
    <td>${r.changed ? "🔔 변경" : "—"}</td></tr>`).join("");

// ---- macro table ----
$("macro-tbl").innerHTML =
  `<tr><th>지표</th><th>한 달 전</th><th>지금</th><th>변화</th></tr>` +
  report.macro.map((m) => {
    const d = m.now !== null && m.prev !== null ? m.now - m.prev : null;
    return `<tr><td>${label(m.key)}</td>
      <td class="num">${fmt(m.prev, unit(m.key), registry)}</td>
      <td class="num">${fmt(m.now, unit(m.key), registry)}</td>
      <td class="num">${d === null ? "-" : fmtSigned(d, 2)}</td></tr>`;
  }).join("");

// ---- whale filings ----
$("filings").innerHTML = report.whale_filings.length
  ? `<ul>` + report.whale_filings.map((f) =>
      `<li><b>${f.name_ko}</b> — ${f.as_of} 분기분 공시 (${f.filed}) ·
       <a href="whales.html">큰손 추적기에서 보기</a></li>`).join("") + `</ul>`
  : `<p class="caption">최근 45일 내 새 13F 공시가 없습니다. 13F는 분기말 45일
     뒤에 몰려 나옵니다 (2·5·8·11월 중순).</p>`;

initSubtabs("rep-tabs", [
  { id: "summary", label: "변화 요약", section: "rtab-summary" },
  { id: "detail", label: "지표·매크로", section: "rtab-detail" },
  { id: "etc", label: "큰손·루틴", section: "rtab-etc" },
]);
