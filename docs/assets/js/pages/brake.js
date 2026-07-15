// 🛑 브레이크: 도박 충동 판별 체크 + 24시간 타이머 + 기회비용 + 충동 일지.
// 모든 기록은 localStorage에만 저장된다 (서버 전송 없음).

import { load } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { initSubtabs } from "../subtabs.js";

injectNav();
const { meta, registry } = await load("registry");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------- 충동 체크
const QUIZ = [
  "이 돈을 전부 잃으면 비상금·생활비에 지장이 생긴다",
  "지금(오늘) 사지 않으면 늦는다는 조급함이 있다",
  "왜 오를지 남에게 두 문장으로 설명하지 못한다",
  "유튜브·커뮤니티·지인의 말이 계기가 됐다",
  "최근 손실을 만회하려는 마음이 있다 (복구 매매)",
  "지금 화나거나, 불안하거나, 심심하다",
  "신용·미수·레버리지·몰빵을 쓸 생각이다",
];

$("quiz").innerHTML = `<div class="check-row" style="flex-direction:column;align-items:stretch">
  ${QUIZ.map((q, i) => `<label><input type="checkbox" data-q="${i}"> ${q}</label>`).join("")}
</div>`;

function quizVerdict() {
  const n = document.querySelectorAll("#quiz input:checked").length;
  const v = $("quiz-verdict");
  if (n === 0) {
    v.innerHTML = `<div class="box box-good">체크 0개 — 충동이 아닐 수 있습니다.
      그래도 신규 진입이라면 아래 24시간 룰을 권합니다. 좋은 결정은 하루를 기다려도
      좋은 결정입니다.</div>`;
  } else if (n <= 2) {
    v.innerHTML = `<div class="box box-warn">체크 ${n}개 — 경고등이 켜졌습니다.
      최소한 아래 타이머를 켜고 내일 다시 판단하세요.</div>`;
  } else {
    v.innerHTML = `<div class="box box-bad"><b>체크 ${n}개 — 지금 상태는 투자가 아니라
      도박 충동입니다.</b> 이 상태로 누르는 매수 버튼은 통계적으로 돈을 지불하는
      버튼입니다. 타이머를 켜고, 오늘은 여기까지.</div>`;
  }
}
$("quiz").addEventListener("change", quizVerdict);
quizVerdict();

// ------------------------------------------------------------ 24시간 타이머
const KEY = "vi-brake";
const WAIT_MS = 24 * 3600 * 1000;
const loadEntries = () => { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; } };
const saveEntries = (e) => localStorage.setItem(KEY, JSON.stringify(e));

$("urge-start").addEventListener("click", () => {
  const what = $("urge-what").value.trim();
  if (!what) { $("urge-what").focus(); return; }
  const entries = loadEntries();
  entries.unshift({ ts: Date.now(), what, why: $("urge-why").value.trim(), status: "waiting" });
  saveEntries(entries);
  $("urge-what").value = ""; $("urge-why").value = "";
  renderAll();
});

function fmtRemain(ms) {
  const h = Math.floor(ms / 3600000), m = Math.ceil((ms % 3600000) / 60000);
  return h > 0 ? `${h}시간 ${m}분` : `${m}분`;
}
const fmtDate = (ts) => new Date(ts).toLocaleDateString("ko-KR",
  { month: "short", day: "numeric" });

function renderTimers() {
  const entries = loadEntries();
  const rows = entries.map((e, i) => {
    const left = e.ts + WAIT_MS - Date.now();
    if (e.status === "waiting" && left > 0) {
      return `<div class="box box-warn note-sm">⏳ <b>${e.what}</b>
        ${e.why ? `— "${e.why}"` : ""}<br>남은 시간 <b>${fmtRemain(left)}</b>.
        내일도 원하면 그때 계획을 세우세요.</div>`;
    }
    if (e.status === "waiting") {
      return `<div class="box box-info note-sm">⏰ <b>${e.what}</b>
        ${e.why ? `— "${e.why}"` : ""}<br>24시간이 지났습니다. 아직도 원하나요?
        <div style="margin-top:6px">
          <button class="vi-btn" data-act="resisted" data-i="${i}">참았다 🧊</button>
          <button class="vi-btn" data-act="bought" data-i="${i}">샀다</button>
        </div></div>`;
    }
    return "";
  }).join("");
  $("urge-list").innerHTML = rows ||
    `<p class="caption" style="margin-top:10px">진행 중인 타이머가 없습니다.</p>`;
}

function renderLog() {
  const entries = loadEntries();
  const done = entries.filter((e) => e.status !== "waiting");
  const resisted = done.filter((e) => e.status === "resisted").length;
  const bought = done.filter((e) => e.status === "bought").length;
  $("log-stats").innerHTML = `
    <div class="card"><div class="metric-label">참았다 🧊</div>
      <div class="metric-value">${resisted}회</div></div>
    <div class="card"><div class="metric-label">샀다</div>
      <div class="metric-value">${bought}회</div></div>
    <div class="card"><div class="metric-label">대기 중</div>
      <div class="metric-value">${entries.length - done.length}건</div></div>`;
  $("log-list").innerHTML = done.length
    ? done.map((e) => `<div class="chg-row">
        <span class="chg-title">${fmtDate(e.ts)}</span>
        <span class="chg-names">${e.status === "resisted" ? "🧊 참음" : "🛒 삼"} —
          <b>${e.what}</b>${e.why ? ` ("${e.why}")` : ""}</span></div>`).join("")
    : `<p class="caption">완료된 기록이 아직 없습니다.</p>`;
}

$("urge-list").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const entries = loadEntries();
  entries[Number(btn.dataset.i)].status = btn.dataset.act;
  saveEntries(entries);
  renderAll();
});

function renderAll() { renderTimers(); renderLog(); }
renderAll();
setInterval(renderTimers, 30000);

// ------------------------------------------------------------- 기회비용
function drawCost() {
  const amt = Number($("cost-amt").value) || 0;
  const grow = (y, r) => Math.round(amt * Math.pow(1 + r, y));
  $("cost-cards").innerHTML = [10, 20, 30].map((y) => `
    <div class="card"><div class="metric-label">${y}년 뒤 (인덱스에 뒀다면)</div>
      <div class="metric-value" style="font-size:1.3rem">${grow(y, 0.07).toLocaleString("ko-KR")}만원</div>
      <div class="metric-note">보수적 가정(연 5%)이면 ${grow(y, 0.05).toLocaleString("ko-KR")}만원</div>
    </div>`).join("");
  $("cost-note").textContent =
    `연 7%는 주식시장의 역사적 실질수익률 근사치입니다. 지금 ${amt.toLocaleString("ko-KR")}만원을 ` +
    "도박으로 태우는 것은 미래의 저 금액과 맞바꾸는 거래입니다 — 그리고 도박의 기대값은 마이너스입니다.";
}
$("cost-amt").addEventListener("input", drawCost);
drawCost();

// ------------------------------------------------------------- sub-tabs
initSubtabs("brake-tabs", [
  { id: "stop", label: "지금 멈추기", section: "btab-stop" },
  { id: "cost", label: "이 돈의 미래", section: "btab-cost" },
  { id: "log", label: "일지·대안", section: "btab-log" },
]);
