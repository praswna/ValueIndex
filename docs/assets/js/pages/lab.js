// 초단기 실험실: S&P 일간 종가 백테스트 (backtest.js), 거래비용 효과.

import { load } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render } from "../charts.js";
import { RULES, evaluate } from "../backtest.js";

injectNav();
const { meta, registry, spx_daily } = await load("registry", "spx_daily");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const dates = spx_daily.dates;
const close = spx_daily.close;

const rulePicker = $("rule");
for (const [key, rule] of Object.entries(RULES)) {
  const opt = document.createElement("option");
  opt.value = key;
  opt.textContent = rule.label;
  rulePicker.appendChild(opt);
}

const years = [...new Set(dates.map((d) => Number(d.slice(0, 4))))];
const fromInput = $("from-year");
fromInput.min = years[0];
fromInput.max = years[years.length - 1] - 1;
fromInput.value = Math.max(years[0], 1990);

[rulePicker, $("cost"), fromInput].forEach((el) => {
  el.addEventListener("input", draw);
  el.addEventListener("change", draw);
});

function sliceView(startYear) {
  const start = `${startYear}-01-01`;
  const i0 = dates.findIndex((d) => d >= start);
  return { dates: dates.slice(i0), close: close.slice(i0) };
}

function draw() {
  $("from-label").textContent = fromInput.value;
  $("cost-label").textContent = $("cost").value;
  const ruleKey = rulePicker.value;
  const costBps = Number($("cost").value);
  const view = sliceView(Number(fromInput.value));

  const positions = RULES[ruleKey].fn(view.close, view.dates);
  const res = evaluate(positions, view.close, costBps);
  const resFree = evaluate(positions, view.close, 0);

  const metrics = [
    ["진입 횟수", res.n_trades.toLocaleString("ko-KR")],
    ["보유일 승률", `${(res.win_rate * 100).toFixed(1)}%`],
    ["보유일 평균 수익률 (%/일)", res.mean_daily_ret.toFixed(3)],
    ["t-통계", res.t_stat.toFixed(2)],
    ["누적 비용", `−${res.total_costs_pct.toFixed(1)}%p`],
  ];
  $("metrics").innerHTML = metrics.map(([label, v]) => `
    <div class="card"><div class="metric-label">${label}</div>
    <div class="metric-value" style="font-size:1.3rem">${v}</div></div>`).join("");

  render($("chart"), [
    { x: view.dates, y: res.buyHoldCurve, mode: "lines", name: "그냥 보유 (buy & hold)",
      line: { color: registry.chrome.muted, width: 2 } },
    { x: view.dates, y: resFree.equityCurve, mode: "lines", name: "전략 (비용 0)",
      line: { color: "#2a78d6", width: 2, dash: "dot" } },
    { x: view.dates, y: res.equityCurve, mode: "lines", name: `전략 (비용 ${costBps}bp)`,
      line: { color: "#eb6834", width: 2 } },
  ], baseLayout(registry, {
    yaxis: { title: { text: "누적 배수 (시작 = 1)" }, type: "log",
             gridcolor: registry.chrome.grid },
  }, 440));

  const verdicts = [];
  if (Math.abs(res.t_stat) < 2) {
    verdicts.push("보유일 수익률이 <b>통계적으로 유의하지 않습니다</b> (|t| < 2) — 우연과 구분되지 않습니다.");
  } else {
    verdicts.push("보유일 수익률이 통계적으로는 유의해 보입니다 (|t| ≥ 2) — 위 다중검정 함정을 꼭 읽어보세요.");
  }
  const sFinal = res.equityCurve[res.equityCurve.length - 1];
  const bhFinal = res.buyHoldCurve[res.buyHoldCurve.length - 1];
  if (sFinal < bhFinal) {
    verdicts.push(
      `비용 ${costBps}bp 반영 시 전략(${sFinal.toFixed(2)}배)이 그냥 보유(${bhFinal.toFixed(2)}배)에 ` +
      "<b>뒤집니다</b> — 신호가 있어 보여도 시장에서 빠져 있는 날의 기회비용과 거래비용이 이깁니다.");
  } else {
    verdicts.push(
      `이 구간에서는 전략(${sFinal.toFixed(2)}배)이 보유(${bhFinal.toFixed(2)}배)를 앞섭니다 — ` +
      "기간을 바꿔보세요. 특정 구간에서만 이기는 전략은 대부분 과최적화입니다.");
  }
  if (costBps === 0) {
    verdicts.push("지금은 <b>비용 0의 가상 세계</b>입니다. 슬라이더로 현실적 비용(10~30bp)을 넣어 보세요.");
  }
  $("verdict").innerHTML = verdicts.map((v) => `<li>${v}</li>`).join("");
}

draw();
