// Port of valueindex/quant.py: PCA composite (Jacobi eigensolver on the
// pairwise correlation matrix) and nearest-analog search. Semantics match
// the Python implementation exactly (see tests/e2e parity fixtures).

import { asofIndex, mean, std } from "./stats.js";

// Direction-aligned z-score columns on the panel's shared grid, optionally
// truncated at `asof` (the time machine). Mirrors app.py's aligned_z_panel.
export function alignedZFromPanel(panel, registry, asof = null) {
  const cut = asof === null ? panel.dates.length - 1 : asofIndex(panel.dates, asof);
  const dates = panel.dates.slice(0, cut + 1);
  const columns = {};
  for (const key of registry.valuation_keys) {
    const sign = registry.indicators[key].higher_is_expensive ? 1 : -1;
    const raw = panel.series[key].slice(0, cut + 1);
    const vals = raw.filter((x) => x !== null);
    if (vals.length < 2) {
      columns[key] = raw.map(() => null);
      continue;
    }
    const m = mean(vals), s = std(vals);
    columns[key] = raw.map((x) => (x === null ? null : ((x - m) / s) * sign));
  }
  return { dates, columns };
}

// ---- pairwise-complete Pearson correlation (pandas corr(min_periods)) ----

function pearson(a, b) {
  // over indices where both non-null; returns [corr, count]
  let n = 0, sa = 0, sb = 0;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== null && b[i] !== null) { n++; sa += a[i]; sb += b[i]; }
  }
  if (n < 2) return [NaN, n];
  const ma = sa / n, mb = sb / n;
  let cov = 0, va = 0, vb = 0;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== null && b[i] !== null) {
      const da = a[i] - ma, db = b[i] - mb;
      cov += da * db; va += da * da; vb += db * db;
    }
  }
  const denom = Math.sqrt(va * vb);
  return [denom === 0 ? NaN : cov / denom, n];
}

// ---- Jacobi eigendecomposition for a symmetric matrix ----

export function jacobiEigh(matrix) {
  const n = matrix.length;
  const a = matrix.map((row) => row.slice());
  let v = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => (i === j ? 1 : 0))
  );
  for (let sweep = 0; sweep < 200; sweep++) {
    let off = 0;
    for (let p = 0; p < n; p++)
      for (let q = p + 1; q < n; q++) off += a[p][q] * a[p][q];
    if (off < 1e-22) break;
    for (let p = 0; p < n; p++) {
      for (let q = p + 1; q < n; q++) {
        if (Math.abs(a[p][q]) < 1e-15) continue;
        const theta = (a[q][q] - a[p][p]) / (2 * a[p][q]);
        const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1);
        const s = t * c;
        for (let k = 0; k < n; k++) {
          const akp = a[k][p], akq = a[k][q];
          a[k][p] = c * akp - s * akq;
          a[k][q] = s * akp + c * akq;
        }
        for (let k = 0; k < n; k++) {
          const apk = a[p][k], aqk = a[q][k];
          a[p][k] = c * apk - s * aqk;
          a[q][k] = s * apk + c * aqk;
        }
        for (let k = 0; k < n; k++) {
          const vkp = v[k][p], vkq = v[k][q];
          v[k][p] = c * vkp - s * vkq;
          v[k][q] = s * vkp + c * vkq;
        }
      }
    }
  }
  const eigvals = a.map((row, i) => row[i]);
  // eigenvectors are columns of v
  return { eigvals, eigvecs: v };
}

// ---- PCA composite (port of quant.pca_composite) ----

// columns: {key: array-with-nulls on a shared grid}
export function pcaComposite(keys, columns, minSeries = 4, minObs = 24) {
  const usable = keys.filter(
    (k) => columns[k].reduce((c, x) => c + (x !== null ? 1 : 0), 0) >= minObs
  );
  minSeries = Math.min(minSeries, Math.max(1, usable.length));

  const gridLen = usable.length ? columns[usable[0]].length : 0;

  if (usable.length === 1) {
    const raw = columns[usable[0]];
    const vals = raw.filter((x) => x !== null);
    const m = mean(vals), s = std(vals);
    const composite = raw.map((x) => (x === null ? null : (x - m) / s));
    return { usable, weights: { [usable[0]]: 1.0 }, explained: 1.0, composite };
  }

  const n = usable.length;
  const corr = Array.from({ length: n }, () => new Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    corr[i][i] = 1;
    for (let j = i + 1; j < n; j++) {
      const [r, count] = pearson(columns[usable[i]], columns[usable[j]]);
      const val = count >= minObs && !Number.isNaN(r) ? r : 0; // fillna(0)
      corr[i][j] = val;
      corr[j][i] = val;
    }
  }

  const { eigvals, eigvecs } = jacobiEigh(corr);
  let maxI = 0;
  for (let i = 1; i < n; i++) if (eigvals[i] > eigvals[maxI]) maxI = i;
  let v1 = eigvecs.map((row) => row[maxI]);
  if (v1.reduce((a, b) => a + b, 0) < 0) v1 = v1.map((x) => -x);
  const explained = eigvals[maxI] / eigvals.reduce((a, b) => a + b, 0);
  const weights = Object.fromEntries(usable.map((k, i) => [k, v1[i]]));

  // per-row score with renormalized weights over available indicators
  const raw = new Array(gridLen).fill(null);
  for (let r = 0; r < gridLen; r++) {
    let dot = 0, norm2 = 0, present = 0;
    for (let i = 0; i < n; i++) {
      const x = columns[usable[i]][r];
      if (x !== null) { dot += x * v1[i]; norm2 += v1[i] * v1[i]; present++; }
    }
    if (present >= minSeries && norm2 > 0) raw[r] = dot / Math.sqrt(norm2);
  }
  const vals = raw.filter((x) => x !== null);
  const m = mean(vals), s = std(vals);
  const composite = raw.map((x) => (x === null ? null : (x - m) / s));
  return { usable, weights, explained, composite };
}

// ---- nearest analogs (port of quant.nearest_analogs) ----

const DAY = 86400000;

function daysBetween(d1, d2) {
  return Math.abs(Date.parse(d1) - Date.parse(d2)) / DAY;
}

// columns: {key: array-with-nulls}, dates: shared grid (ascending)
export function nearestAnalogs(keys, columns, dates, opts = {}) {
  const { n = 4, minSepMonths = 36, excludeRecentMonths = 60, minShared = 4 } = opts;
  const last = dates.length - 1;
  const target = keys.map((k) => columns[k][last]);
  const histEnd = last - excludeRecentMonths; // exclusive of target row already
  const candidates = [];
  for (let r = 0; r < histEnd; r++) {
    let sum = 0, shared = 0;
    for (let i = 0; i < keys.length; i++) {
      const a = columns[keys[i]][r], b = target[i];
      if (a !== null && b !== null) { const d = a - b; sum += d * d; shared++; }
    }
    if (shared >= minShared) {
      candidates.push({ date: dates[r], distance: Math.sqrt(sum / shared), shared });
    }
  }
  candidates.sort((a, b) => a.distance - b.distance);
  const picked = [];
  for (const c of candidates) {
    if (picked.some((p) => daysBetween(p.date, c.date) < minSepMonths * 30)) continue;
    picked.push(c);
    if (picked.length >= n) break;
  }
  return picked;
}

export function monthsBetween(d1, d2) {
  const [y1, m1] = [Number(d1.slice(0, 4)), Number(d1.slice(5, 7))];
  const [y2, m2] = [Number(d2.slice(0, 4)), Number(d2.slice(5, 7))];
  return (y2 - y1) * 12 + (m2 - m1);
}
