// 📉 단기 시그널: 기술적 지표의 현재 상태 타일 + 탭하면 팝업
// (차트 + 해석 + 거래비용 포함 백테스트 성적표). 일간 종가 기준.

import { load, fmtSigned } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { baseLayout, render, lineTrace, hline } from "../charts.js";
import { std } from "../stats.js";
import { rsi, RULES, evaluate } from "../backtest.js";
import { openModal } from "../modal.js";

injectNav();
const { meta, registry, spx_daily, korea } = await load("registry", "spx_daily", "korea");
injectFooter(meta, registry);

const $ = (id) => document.getElementById(id);
const COST_BPS = 10; // 편도 0.1% — 수수료+슬리피지의 보수적이지 않은(후한) 가정

const MARKETS = {
  spx: { label: "S&P 500", dates: spx_daily.dates, close: spx_daily.close },
  kospi: korea.kospi && korea.kospi.dates.length
    ? { label: "KOSPI", dates: korea.kospi.dates, close: korea.kospi.values }
    : null,
};
let market = "spx";

// ---- local series helpers (daily) ----
function sma(values, w) {
  const out = new Array(values.length).fill(NaN);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= w) sum -= values[i - w];
    if (i >= w - 1) out[i] = sum / w;
  }
  return out;
}
function pctChangeN(values, n) {
  return values.map((v, i) => (i >= n ? (v / values[i - n] - 1) * 100 : NaN));
}
function rollVolAnnual(values, w = 20) {
  const rets = values.map((v, i) => (i > 0 ? v / values[i - 1] - 1 : NaN));
  const out = new Array(values.length).fill(NaN);
  for (let i = w; i < values.length; i++) {
    out[i] = std(rets.slice(i - w + 1, i + 1)) * Math.sqrt(252) * 100;
  }
  return out;
}
function ddFrom52wHigh(values) {
  const out = new Array(values.length).fill(NaN);
  for (let i = 0; i < values.length; i++) {
    const lo = Math.max(0, i - 251);
    let hi = -Infinity;
    for (let j = lo; j <= i; j++) hi = Math.max(hi, values[j]);
    out[i] = (values[i] / hi - 1) * 100;
  }
  return out;
}
const lastValid = (arr) => { for (let i = arr.length - 1; i >= 0; i--) if (!Number.isNaN(arr[i])) return arr[i]; return null; };

// ---- per-market signal model ----
function buildModel(mkt) {
  const { dates, close } = MARKETS[mkt];
  const rsiS = rsi(close);
  const f = sma(close, 50), s = sma(close, 200);
  const mom = pctChangeN(close, 20);
  const vol = rollVolAnnual(close);
  const dd = ddFrom52wHigh(close);
  const rsiNow = lastValid(rsiS), fNow = lastValid(f), sNow = lastValid(s);
  const cross = fNow > sNow;
  return {
    dates, close, rsiS, f, s, mom, vol, dd,
    tiles: [
      { id: "rsi", label: "RSI (14일)", value: rsiNow.toFixed(0),
        state: rsiNow < 30 ? "과매도 구간" : rsiNow > 70 ? "과매수 구간" : "중립",
        dot: rsiNow < 30 ? "#1baf7a" : rsiNow > 70 ? "#e34948" : "#898781" },
      { id: "cross", label: "이평선 50/200일", value: cross ? "골든크로스" : "데드크로스",
        state: `격차 ${fmtSigned((fNow / sNow - 1) * 100, 1)}%`,
        dot: cross ? "#2a78d6" : "#e34948", small: true },
      { id: "mom", label: "20일 모멘텀", value: fmtSigned(lastValid(mom), 1) + "%",
        state: lastValid(mom) > 0 ? "상승 추세" : "하락 추세",
        dot: lastValid(mom) > 0 ? "#2a78d6" : "#e34948" },
      { id: "vol", label: "변동성 (20일, 연환산)", value: lastValid(vol).toFixed(0) + "%",
        state: lastValid(vol) < 12 ? "조용한 장" : lastValid(vol) > 25 ? "거친 장" : "보통",
        dot: "#898781" },
      { id: "dd", label: "52주 고점 대비", value: lastValid(dd).toFixed(1) + "%",
        state: lastValid(dd) > -3 ? "고점권" : lastValid(dd) < -10 ? "조정 구간" : "고점 부근 이탈",
        dot: lastValid(dd) < -10 ? "#e34948" : "#898781" },
    ],
  };
}

function drawTiles() {
  const model = buildModel(market);
  $("tiles").innerHTML = model.tiles.map((t) => `
    <button class="tile" data-id="${t.id}">
      <span class="tile-dot" style="background:${t.dot}"></span>
      <span class="tile-label">${t.label}</span>
      <span class="tile-value"${t.small ? ' style="font-size:1.05rem"' : ""}>${t.value}</span>
      <span class="tile-sub">${t.state}</span>
    </button>`).join("");
  return model;
}

// market toggle
for (const key of Object.keys(MARKETS).filter((k) => MARKETS[k])) {
  const btn = document.createElement("button");
  btn.className = "vi-btn" + (key === market ? " active" : "");
  btn.textContent = MARKETS[key].label;
  btn.addEventListener("click", () => {
    market = key;
    document.querySelectorAll("#market-btns .vi-btn").forEach((b) =>
      b.classList.toggle("active", b.textContent === MARKETS[key].label));
    drawTiles();
  });
  $("market-btns").appendChild(btn);
}

// ---- popup ----
const EXPLAIN = {
  rsi: "최근 14일의 상승폭/하락폭 비율입니다. 30 이하를 '과매도(반등 기대)', 70 이상을 '과매수'로 읽는 것이 관례입니다.",
  cross: "50일 이평선이 200일 위로 올라오면 골든크로스(상승 국면), 아래로 내려가면 데드크로스로 읽는 고전적 추세 신호입니다.",
  mom: "최근 20거래일(약 한 달) 수익률입니다. 단기 추세의 방향과 세기를 봅니다.",
  vol: "최근 20일 일간수익률의 표준편차를 연 단위로 환산한 값입니다. 12% 이하면 이례적으로 조용한 장, 25% 이상이면 거친 장입니다.",
  dd: "최근 52주 최고가 대비 현재 위치입니다. -10%를 조정(correction), -20%를 약세장이라 부르는 것이 관례입니다.",
};
// tile -> backtest rule (없으면 성적표 생략)
const RULE_OF = { rsi: "rsi", cross: "golden_cross", dd: "dip_buy", mom: "down_streak" };

function verdictHtml(model) {
  return (ruleKey) => {
    const rule = RULES[ruleKey];
    const positions = rule.fn(model.close, model.dates);
    const r = evaluate(positions, model.close, COST_BPS);
    const n = model.close.length;
    const eq = r.equityCurve[n - 1], bh = r.buyHoldCurve[n - 1];
    const noEdge = Math.abs(r.t_stat) < 2;
    const years = ((new Date(model.dates[n - 1]) - new Date(model.dates[0])) / 3.15e10).toFixed(0);
    return `
      <h3>이 신호의 역사 성적표 <span class="caption">(${years}년 · 비용 편도 0.1% 포함)</span></h3>
      <p class="caption">검증 규칙: ${rule.label}</p>
      <div class="modal-stats">
        <div>신호대로 투자<br><b>${eq.toFixed(2)}배</b></div>
        <div>그냥 보유<br><b>${bh.toFixed(2)}배</b></div>
        <div>승률(일)<br><b>${(r.win_rate * 100).toFixed(0)}%</b></div>
        <div>진입 횟수<br><b>${r.n_trades}회</b></div>
        <div>누적 비용<br><b>${r.total_costs_pct.toFixed(0)}%</b></div>
        <div>t-통계<br><b>${r.t_stat.toFixed(2)}</b></div>
      </div>
      <div class="box ${noEdge ? "box-warn" : "box-info"} note-sm">
        판정: ${noEdge
          ? "<b>통계적 우위 없음</b> (|t| < 2) — 이 신호의 성과는 우연과 구별되지 않습니다."
          : "표본상 t-통계는 2를 넘지만, 실전에서는 슬리피지·세금이 추가되고 과거 패턴이 유지된다는 보장이 없습니다."}
        그냥 보유(${bh.toFixed(1)}배)와 비교해 보세요.
      </div>`;
  };
}

function show(id) {
  const model = buildModel(market);
  const mLabel = MARKETS[market].label;
  const tile = model.tiles.find((t) => t.id === id);
  const K = 504; // 차트는 최근 2년
  const cut = (arr) => arr.slice(-K);
  const d = cut(model.dates);
  const verdict = RULE_OF[id] ? verdictHtml(model)(RULE_OF[id]) : "";
  const kospiNote = market === "kospi"
    ? '<p class="caption">⚠️ KOSPI 데이터는 10년치라 백테스트 표본이 작습니다.</p>' : "";

  openModal(`
    <h2 style="margin:0 0 2px">${mLabel} · ${tile.label}</h2>
    <div class="metric-value">${tile.value}
      <span class="metric-delta">${tile.state}</span></div>
    <div id="sg-chart" class="chart"></div>
    <p class="modal-desc">${EXPLAIN[id]}</p>
    ${verdict}${kospiNote}
    <p class="caption">일간 종가 기준, 하루 1회 갱신 — 장중 매매 판단에 쓸 수 없는
      데이터입니다.</p>`);

  const color = registry.series_colors.cape || "#2a78d6";
  let traces, overrides = { showlegend: false,
    margin: { l: 45, r: 10, t: 8, b: 30 },
    yaxis: { gridcolor: registry.chrome.grid } };
  if (id === "rsi") {
    traces = [lineTrace(d, cut(model.rsiS), "RSI", color)];
    overrides.shapes = [hline(30, "#1baf7a"), hline(70, "#e34948")];
    overrides.yaxis.range = [0, 100];
  } else if (id === "cross") {
    traces = [
      lineTrace(d, cut(model.close), "종가", "#898781", { line: { color: "#898781", width: 1.2 } }),
      lineTrace(d, cut(model.f), "50일", "#2a78d6"),
      lineTrace(d, cut(model.s), "200일", "#e34948"),
    ];
    overrides.showlegend = true;
  } else if (id === "mom") {
    traces = [lineTrace(d, cut(model.mom), "20일 수익률 %", color)];
    overrides.shapes = [hline(0, registry.chrome.muted, "solid")];
  } else if (id === "vol") {
    traces = [lineTrace(d, cut(model.vol), "연환산 변동성 %", "#eb6834")];
  } else {
    traces = [lineTrace(d, cut(model.dd), "52주 고점 대비 %", "#e34948")];
    overrides.shapes = [hline(-10, "#eda100"), hline(-20, "#e34948")];
  }
  render($("sg-chart"), traces, baseLayout(registry, overrides, 280));
}

$("tiles").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (tile) show(tile.dataset.id);
});

drawTiles();
