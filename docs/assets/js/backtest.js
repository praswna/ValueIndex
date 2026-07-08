// Port of valueindex/backtest.py with pandas semantics preserved:
// full-window rolling means (leading NaN), SMA-variant RSI, signal on
// close applied to next day's return, cost on |position change|.

import { mean, std } from "./stats.js";

const NaNArr = (n) => new Array(n).fill(NaN);

function rollingMean(values, window, minPeriods = window) {
  const out = NaNArr(values.length);
  let sum = 0, count = 0;
  const q = [];
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    q.push(v);
    if (!Number.isNaN(v)) { sum += v; count++; }
    if (q.length > window) {
      const old = q.shift();
      if (!Number.isNaN(old)) { sum -= old; count--; }
    }
    const inWin = Math.min(i + 1, window);
    if (count >= minPeriods && count === inWin) out[i] = sum / count;
    else if (count >= minPeriods && minPeriods < window) out[i] = sum / count;
  }
  return out;
}

function rollingMax(values, window, minPeriods = window) {
  const out = NaNArr(values.length);
  for (let i = 0; i < values.length; i++) {
    const lo = Math.max(0, i - window + 1);
    let m = -Infinity, count = 0;
    for (let j = lo; j <= i; j++) {
      if (!Number.isNaN(values[j])) { m = Math.max(m, values[j]); count++; }
    }
    if (count >= minPeriods) out[i] = m;
  }
  return out;
}

export function rsi(close, window = 14) {
  const n = close.length;
  const gain = NaNArr(n), loss = NaNArr(n);
  for (let i = 1; i < n; i++) {
    const d = close[i] - close[i - 1];
    gain[i] = Math.max(d, 0);
    loss[i] = Math.max(-d, 0);
  }
  const g = rollingMean(gain, window), l = rollingMean(loss, window);
  return g.map((gi, i) => {
    const li = l[i];
    if (Number.isNaN(gi) || Number.isNaN(li) || li === 0) return NaN;
    return 100 - 100 / (1 + gi / li);
  });
}

function holdAfterSignal(signal, hold) {
  // rolling(hold, min_periods=1).max() over 0/1
  const out = new Array(signal.length).fill(0);
  let lastTrue = -Infinity;
  for (let i = 0; i < signal.length; i++) {
    if (signal[i]) lastTrue = i;
    out[i] = i - lastTrue < hold ? 1 : 0;
  }
  return out;
}

export const RULES = {
  rsi: {
    label: "RSI 30 이하 매수 (5일 보유)",
    fn: (close) => holdAfterSignal(rsi(close).map((r) => r < 30), 5),
  },
  golden_cross: {
    label: "골든크로스 (50일 > 200일 이평선)",
    fn: (close) => {
      const fast = rollingMean(close, 50), slow = rollingMean(close, 200);
      return fast.map((f, i) => (f > slow[i] ? 1 : 0)); // NaN compare -> false
    },
  },
  down_streak: {
    label: "3일 연속 하락 후 매수 (5일 보유)",
    fn: (close) => {
      const down = close.map((c, i) => (i > 0 && c - close[i - 1] < 0 ? 1 : 0));
      const runs = rollingMean(down, 3).map((m) => !Number.isNaN(m) && m * 3 >= 3);
      return holdAfterSignal(runs, 5);
    },
  },
  dip_buy: {
    label: "고점 대비 -10% 진입 (20일 보유)",
    fn: (close) => {
      const high = rollingMax(close, 252, 60);
      const sig = close.map((c, i) =>
        !Number.isNaN(high[i]) && c <= high[i] * 0.9);
      return holdAfterSignal(sig, 20);
    },
  },
  monday: {
    label: "월요일 효과 (월요일만 보유)",
    fn: (close, dates) =>
      dates.map((d) => ((new Date(d + "T00:00:00Z").getUTCDay() + 6) % 7 === 0 ? 1 : 0)),
  },
};

export function evaluate(positions, close, costBps = 0) {
  const n = close.length;
  const dailyRet = new Array(n).fill(0);
  for (let i = 1; i < n; i++) dailyRet[i] = close[i] / close[i - 1] - 1;

  const held = [0, ...positions.slice(0, n - 1)];
  const strat = held.map((h, i) => h * dailyRet[i]);
  const turns = positions.map((p, i) => (i === 0 ? Math.abs(p) : Math.abs(p - positions[i - 1])));
  const costRate = costBps / 10000;
  let totalCost = 0, equity = 1, buyHold = 1;
  const equityCurve = new Array(n), buyHoldCurve = new Array(n);
  for (let i = 0; i < n; i++) {
    const cost = turns[i] * costRate;
    totalCost += cost;
    equity *= 1 + (strat[i] - cost);
    buyHold *= 1 + dailyRet[i];
    equityCurve[i] = equity;
    buyHoldCurve[i] = buyHold;
  }

  const inMarket = strat.filter((_, i) => held[i] > 0);
  const nDays = inMarket.length;
  let tStat = 0;
  if (nDays > 1) {
    const s = std(inMarket);
    if (s > 0) tStat = mean(inMarket) / (s / Math.sqrt(nDays));
  }
  let entries = 0;
  for (let i = 0; i < n; i++) {
    const prev = i === 0 ? 0 : positions[i - 1];
    if (positions[i] > 0 && prev === 0) entries++;
  }
  return {
    n_trades: entries,
    n_days_in_market: nDays,
    win_rate: nDays ? inMarket.filter((x) => x > 0).length / nDays : 0,
    mean_daily_ret: nDays ? mean(inMarket) * 100 : 0,
    t_stat: tStat,
    total_costs_pct: totalCost * 100,
    equityCurve,
    buyHoldCurve,
  };
}
