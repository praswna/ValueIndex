// Port of valueindex/stats.py. Pandas semantics preserved exactly:
// sample std (ddof=1), average rank for ties, asof (last at-or-before).
// Pure functions over arrays; nulls are skipped like pandas NaN.

export function cleanPairs(dates, values) {
  const d = [], v = [];
  for (let i = 0; i < values.length; i++) {
    if (values[i] !== null && values[i] !== undefined && !Number.isNaN(values[i])) {
      d.push(dates[i]);
      v.push(values[i]);
    }
  }
  return { dates: d, values: v };
}

export function mean(v) {
  let s = 0;
  for (const x of v) s += x;
  return s / v.length;
}

export function std(v) {
  // pandas default: sample std, ddof=1
  if (v.length < 2) return NaN;
  const m = mean(v);
  let s = 0;
  for (const x of v) s += (x - m) * (x - m);
  return Math.sqrt(s / (v.length - 1));
}

// rank(pct=True) with average ranks for ties, * 100.
export function percentileRanks(v) {
  const n = v.length;
  const order = v.map((x, i) => i).sort((a, b) => v[a] - v[b]);
  const ranks = new Array(n);
  let i = 0;
  while (i < n) {
    let j = i;
    while (j + 1 < n && v[order[j + 1]] === v[order[i]]) j++;
    const avg = (i + j + 2) / 2; // 1-based average rank of the tie block
    for (let k = i; k <= j; k++) ranks[order[k]] = avg;
    i = j + 1;
  }
  return ranks.map((r) => (r / n) * 100);
}

export function zscores(v) {
  const m = mean(v), s = std(v);
  return v.map((x) => (x - m) / s);
}

// index of last date <= target (ISO strings compare lexicographically), -1 if none
export function asofIndex(dates, target) {
  let lo = 0, hi = dates.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (dates[mid] <= target) { ans = mid; lo = mid + 1; }
    else hi = mid - 1;
  }
  return ans;
}

export function shiftDateStr(dateStr, years) {
  return `${String(Number(dateStr.slice(0, 4)) + years)}${dateStr.slice(4)}`;
}

// Port of stats.summary on a cleaned (dates, values) series, optionally
// truncated at `asof` (time machine).
export function summary(dates, values, asof = null) {
  let d = dates, v = values;
  if (asof !== null) {
    const cut = asofIndex(dates, asof);
    d = dates.slice(0, cut + 1);
    v = values.slice(0, cut + 1);
  }
  if (!v.length) return null;
  const current = v[v.length - 1];
  const currentDate = d[d.length - 1];
  const yearAgoIdx = asofIndex(d, shiftDateStr(currentDate, -1));
  const m = mean(v), s = std(v);
  return {
    current,
    asof: currentDate,
    mean: m,
    std: s,
    pctile: percentileRanks(v)[v.length - 1],
    z: (current - m) / s,
    delta_1y: yearAgoIdx >= 0 ? current - v[yearAgoIdx] : null,
    hist_min: Math.min(...v),
    hist_max: Math.max(...v),
    start: d[0],
  };
}

export function drawdown(values) {
  // (v / cummax - 1) * 100
  const out = new Array(values.length);
  let peak = -Infinity;
  for (let i = 0; i < values.length; i++) {
    peak = Math.max(peak, values[i]);
    out[i] = (values[i] / peak - 1) * 100;
  }
  return out;
}

export function pctChange(values) {
  const out = [null];
  for (let i = 1; i < values.length; i++) out.push(values[i] / values[i - 1] - 1);
  return out;
}

// np.interp equivalent (linear, clamped at ends), for the fan readout.
export function interp(x, xs, ys) {
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  let i = 1;
  while (xs[i] < x) i++;
  const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
  return ys[i - 1] + t * (ys[i] - ys[i - 1]);
}
