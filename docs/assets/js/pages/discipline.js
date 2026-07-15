// 투자 규율: 중요도순 규칙 카드 + 탭하면 팝업 (상황 → 규칙 → 근거 → 실행).
// ★ = 어겼을 때 잃는 돈의 크기에 대한 이 앱의 평가.

import { load, ym } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, recessionShapes, ratingBadge } from "../charts.js";
import { cleanPairs, drawdown } from "../stats.js";
import { openModal } from "../modal.js";
import { STARS } from "../strategies.js";

injectNav();
const { meta, registry, panel, overview, content } =
  await load("registry", "panel", "overview", "content");
injectFooter(meta, registry);

// 드로다운 시리즈 (팝업 차트용, 미리 계산)
const { dates, values } = cleanPairs(panel.dates, panel.series.real_tri);
const dd = drawdown(values);
let ddMin = 0, ddArg = 0;
dd.forEach((x, i) => { if (x < ddMin) { ddMin = x; ddArg = i; } });

const CHECKS = [
  "비상금(3~6개월 생활비)이 투자금과 별도로 있다",
  "이 돈은 최소 10년 묻어둘 수 있는 돈이다",
  "연 5% 이상 고금리 부채가 없다",
  "매수 이유가 유튜브·지인 추천·급등 뉴스가 아니다",
  "이 매수 후에도 한 종목/테마 비중이 전체의 20%를 넘지 않는다",
  "떨어져도 팔지 않을 하락 한도를 미리 정했다",
];

const RULES = [
  {
    id: "nosell", stars: 5, label: "폭락장에서 팔지 않는다",
    line: "매도 결정은 하락장에서 내리지 않는다",
    trigger: "급락 뉴스, 계좌 -20%, \"일단 팔고 지켜보자\"는 생각이 올라올 때.",
    rule: "매도는 <b>평온할 때 정해둔 원칙</b>(리밸런싱·목표 도달)으로만 합니다. 하락장에서 새로 내리는 매도 결정은 결정이 아니라 반사입니다.",
    why: "미국 투자자 행동 연구(DALBAR 등)의 반복된 결론 — 펀드 수익률보다 그 펀드에 투자한 <b>사람들의 실제 수익률이 연 1~4%p 낮고</b>, 그 차이의 주범이 저점 매도입니다. 규율 항목 전체에서 어겼을 때 가장 비쌉니다.",
    special: "dd",
  },
  {
    id: "keepdca", stars: 5, label: "급락 시 적립을 멈추지 않는다",
    line: "시장 −30%에서 할 일은 '계속'뿐",
    trigger: "시장이 -30% 급락하고 뉴스가 종말을 이야기할 때.",
    rule: "적립 <b>중단 금지</b> — 같은 돈으로 더 많은 수량을 사는 구간입니다. 뉴스·계좌 확인 빈도를 줄이고, 드로다운 차트를 다시 봅니다: 매번 회복했습니다.",
    why: "하락장에 멈춘 적립은 '싸게 사는 구간'을 통째로 건너뛰는 것입니다. 적립식의 수익 대부분은 공포 구간에 산 수량에서 나옵니다.",
  },
  {
    id: "schedule", stars: 4, label: "신규 매수는 정해진 날에만",
    line: "FOMO 차단기 — 추격 매수 봉쇄",
    trigger: "\"다들 벌었다는데 나만 없네\", 급등 뉴스를 본 직후.",
    rule: "신규 매수는 <b>미리 정한 적립일에만</b>. 그 외의 매수 충동은 🛑 브레이크 탭의 24시간 타이머로 보냅니다.",
    why: "추격 매수는 통계적으로 고점 매수가 됩니다 — 급등이 뉴스가 되는 시점이 대개 단기 고점 근처이기 때문입니다. 자동이체가 이 규칙의 가장 강한 집행 장치입니다.",
  },
  {
    id: "checklist", stars: 4, label: "매수 전 체크리스트",
    line: "하나라도 막히면 오늘은 사지 않는다",
    trigger: "무언가를 사기로 거의 마음먹었을 때 — 누르기 전 마지막 관문.",
    rule: "아래 6개가 전부 체크되기 전에는 매수를 미루는 것이 규칙입니다.",
    why: "체크리스트는 판단력을 대체하는 게 아니라, 흥분 상태에서 판단력이 꺼진 것을 감지하는 장치입니다.",
    special: "checklist",
  },
  {
    id: "rebalance", stars: 3, label: "종목이 아니라 비중으로 판다",
    line: "손실 회피 편향의 해독제",
    trigger: "수익 난 것만 팔고 물린 것은 못 팔고 있을 때.",
    rule: "매도는 <b>종목 단위 감정이 아니라 자산배분 비중 기준</b>으로 — 목표에서 ±5%p 벗어난 자산군을 기계적으로 되돌립니다.",
    why: "사람은 이익은 서둘러 확정하고 손실은 미루도록 설계돼 있습니다(처분 효과). 비중 규칙은 이 감정 회로를 우회합니다. <a href=\"start.html#rebalance\">⚖️ 리밸런싱 도우미</a>가 계산해 줍니다.",
  },
  {
    id: "scenario", stars: 3, label: "등급별 행동을 미리 정한다",
    line: "고평가·저평가 시나리오 사전 약속",
    trigger: "개요의 등급 색이 바뀌었을 때 — 그리고 바뀌기 전인 지금.",
    rule: "",
    why: "패닉·유포리아 상황에서 즉흥 판단하지 않도록, <b>평온한 지금</b> 규칙을 적어두는 것이 목적입니다.",
    special: "scenario",
  },
  {
    id: "routine", stars: 3, label: "한 달에 한 번만 본다",
    line: "월간 점검 루틴 — 그 이상은 소음",
    trigger: "습관적으로 계좌·시세를 열고 있는 나를 발견할 때.",
    rule: "한 달에 한 번: ① <a href=\"report.html\">월간점검</a>에서 등급 변화 확인 ② 비중 ±5%p 이탈 확인 ③ <b>아무것도 안 해도 된다는 것</b>을 확인하고 닫기.",
    why: "이 앱의 데이터는 월간/분기 갱신이라 매일 봐도 새 정보가 없습니다. 자주 볼수록 손이 나가고, 손이 나갈수록 수익률이 깎입니다. 등급이 바뀌면 이메일 알림이 옵니다 — 그전에는 볼 일이 없습니다.",
  },
  {
    id: "devil", stars: 2, label: "반대 논리를 먼저 찾는다",
    line: "확증 편향 — 보고 싶은 것만 보는 눈",
    trigger: "보유 종목의 좋은 뉴스만 찾아 읽고 있을 때.",
    rule: "사기 전, 그리고 보유 중에도 주기적으로: <b>\"이 투자가 틀렸다면 왜인가\"</b>를 두 가지 이상 적어봅니다. 적지 못하면 아직 이해하지 못한 것입니다.",
    why: "확증 편향은 똑똑할수록 심해집니다 — 논리력이 반대 증거를 반박하는 데 쓰이기 때문입니다. 반대 논리를 의무화하는 것이 유일한 구조적 해독제입니다.",
  },
  {
    id: "benchmark", stars: 2, label: "성과를 지수와 비교해 기록한다",
    line: "과잉확신 — '나는 감이 좋다'의 검증",
    trigger: "몇 번의 성공 후 '나는 시장을 이길 수 있다'는 확신이 들 때.",
    rule: "내 계좌의 기간 수익률을 <b>같은 기간 인덱스와 나란히</b> 기록합니다. 3년 이상 이기고 있지 않다면, 그 확신은 데이터가 아니라 기분입니다.",
    why: "상승장에서는 누구나 천재 같습니다. 비교 기록만이 '시장이 벌어준 것'과 '내가 벌은 것'을 구별해 줍니다.",
  },
  {
    id: "why", stars: 2, label: "왜 규율인가",
    line: "대형 펀드와 개인의 진짜 격차",
    trigger: "\"규칙 없이도 잘할 수 있을 것 같은데\"라는 생각이 들 때.",
    rule: "",
    why: "",
    special: "content",
  },
  {
    id: "books", stars: 2, label: "더 공부하기",
    line: "읽는 순서대로 고른 책·자료",
    trigger: "",
    rule: "",
    why: "",
    special: "resources",
  },
];

// ---- tiles (sorted by stars) ----
const sorted = [...RULES].sort((a, b) => b.stars - a.stars);
document.getElementById("disc-tiles").innerHTML = sorted.map((r, i) => `
  <button class="tile" data-rule="${r.id}">
    <span class="tile-label">${i + 1}. ${r.label}</span>
    <span class="tile-value" style="font-size:1.05rem">${STARS(r.stars)}</span>
    <span class="tile-sub">${r.line}</span>
  </button>`).join("");

// ---- popups ----
function baseHtml(r) {
  return `
    <h2 style="margin:0 0 2px">${r.label}</h2>
    <div style="font-size:1.2rem">${STARS(r.stars)}
      <span class="metric-delta">중요도 = 어겼을 때 잃는 돈</span></div>
    ${r.trigger ? `<p class="modal-desc" style="margin-top:10px"><b>이럴 때</b> — ${r.trigger}</p>` : ""}
    ${r.rule ? `<div class="box box-info note-sm"><b>규칙</b> — ${r.rule}</div>` : ""}
    ${r.why ? `<p class="modal-desc"><b>왜</b> — ${r.why}</p>` : ""}`;
}

function show(id) {
  const r = RULES.find((x) => x.id === id);

  if (r.special === "content") {
    openModal(`<h2 style="margin:0 0 2px">${r.label}</h2>
      <div style="font-size:1.2rem">${STARS(r.stars)}</div>
      <div class="modal-desc">${content.discipline_ko}</div>`);
    return;
  }
  if (r.special === "resources") {
    openModal(`<h2 style="margin:0 0 2px">${r.label}</h2>
      <div class="modal-desc">${content.resources_ko}</div>`);
    return;
  }
  if (r.special === "scenario") {
    openModal(`${baseHtml(r)}
      <p class="caption">지금 CAPE 등급: ${ratingBadge(registry, overview.summaries.cape.rating)}
        (${ym(overview.summaries.cape.asof)})</p>
      <div class="box box-bad note-sm"><b>🔴 매우 고평가일 때</b><ul style="margin:4px 0 0 18px">
        <li>신규 목돈은 분할 폭을 <b>넓게</b> (예: 12개월)</li>
        <li>향후 10년 기대치를 낮춰 잡기 (<a href="start.html#calc">🧮 계산기</a>)</li>
        <li>채권/현금 비중 재점검</li>
        <li>❌ <b>보유분 전량 매도가 아닙니다</b></li></ul></div>
      <div class="box box-info note-sm"><b>🔵 저평가일 때</b><ul style="margin:4px 0 0 18px">
        <li>미리 정한 리밸런싱 실행 (주식 비중 복원)</li>
        <li>적립 금액 유지 또는 계획된 범위 내 증액</li>
        <li>❌ <b>빚내서 몰빵이 아닙니다</b></li></ul></div>`);
    return;
  }
  if (r.special === "checklist") {
    openModal(`${baseHtml(r)}
      <div id="m-checklist"></div>
      <div class="box" id="m-check-result"></div>
      <p class="caption">체크 상태는 저장되지 않습니다 — 매번 새로 답하는 것이 의도입니다.</p>`);
    const wrap = document.getElementById("m-checklist");
    for (const text of CHECKS) {
      const label = document.createElement("label");
      label.style.display = "block";
      label.style.margin = "6px 0";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.addEventListener("change", update);
      label.appendChild(cb);
      label.appendChild(document.createTextNode(" " + text));
      wrap.appendChild(label);
    }
    function update() {
      const done = wrap.querySelectorAll("input:checked").length;
      const box = document.getElementById("m-check-result");
      if (done === CHECKS.length) {
        box.className = "box box-good";
        box.textContent = "✅ 모든 항목 통과 — 계획대로 진행하세요.";
      } else {
        box.className = "box box-info";
        box.textContent =
          `${done}/${CHECKS.length} 통과 — 전부 체크되기 전에는 매수를 미루는 것이 규칙입니다.`;
      }
    }
    update();
    return;
  }

  // 기본 + (nosell이면 드로다운 차트)
  openModal(`${baseHtml(r)}
    ${r.special === "dd" ? `<h3>급락은 정상입니다 — 150년의 드로다운</h3>
      <div id="m-dd" class="chart"></div>
      <ul style="font-size:0.9rem">
        <li>지난 150여 년 동안 <b>−50% 이상의 하락이 여러 번</b> 있었고, 매번 회복했습니다.</li>
        <li>최악의 드로다운: <b>${ddMin.toFixed(0)}%</b> (${dates[ddArg].slice(0, 4)}년).</li>
        <li>'−30% 급락'은 이례적 사건이 아니라 장기 투자에 <b>포함된 비용</b>입니다.</li></ul>` : ""}`);
  if (r.special === "dd") {
    render(document.getElementById("m-dd"), [{
      x: dates, y: dd, mode: "lines", name: "고점 대비 하락률",
      line: { color: "#c22f2f", width: 1.5 }, fill: "tozeroy",
      fillcolor: "rgba(194,47,47,0.12)",
      hovertemplate: "%{x|%Y-%m}: %{y:.0f}%<extra></extra>",
    }], baseLayout(registry, {
      showlegend: false,
      margin: { l: 45, r: 10, t: 8, b: 30 },
      shapes: recessionShapes(registry, overview.recessions, dates[0]),
      yaxis: { title: { text: "고점 대비 %" }, gridcolor: registry.chrome.grid },
    }, 280));
  }
}

document.getElementById("disc-tiles").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (tile) show(tile.dataset.rule);
});
