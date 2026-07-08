// Port of quant.simulate_dca (block-bootstrap DCA) + Bogle formula.
// RNG differs from numpy PCG64 (not reproducible in JS) — mulberry32 with
// the same seed formula; parity is statistical (percentiles within tol).

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function bogleExpectedReturn(divYieldPct, growthPct, capeNow, capeFuture) {
  const valuationChange = (Math.pow(capeFuture / capeNow, 1 / 10) - 1) * 100;
  return divYieldPct + growthPct + valuationChange;
}

// np.percentile 'linear' interpolation
export function percentileLinear(sortedVals, p) {
  const n = sortedVals.length;
  const rank = ((n - 1) * p) / 100;
  const lo = Math.floor(rank), hi = Math.ceil(rank);
  if (lo === hi) return sortedVals[lo];
  return sortedVals[lo] + (rank - lo) * (sortedVals[hi] - sortedVals[lo]);
}

export function simulateDca(monthlyReturns, monthlyContribution, years, opts = {}) {
  const { nSims = 2000, block = 12, annualDriftTarget = null, seed = 42 } = opts;
  const rets = monthlyReturns.filter((x) => x !== null && !Number.isNaN(x));
  const horizon = years * 12;
  const nBlocks = Math.ceil(horizon / block);
  const rng = mulberry32(seed);

  let shift = 0;
  if (annualDriftTarget !== null) {
    const targetMonthly = Math.pow(1 + annualDriftTarget / 100, 1 / 12) - 1;
    const m = rets.reduce((a, b) => a + b, 0) / rets.length;
    shift = targetMonthly - m;
  }

  const finalWealth = new Array(nSims);
  const wealthPct = { p5: [], p25: [], p50: [], p75: [], p95: [] };
  // store per-month wealth across sims (horizon x nSims) for percentiles
  const monthly = Array.from({ length: horizon }, () => new Array(nSims));

  for (let s = 0; s < nSims; s++) {
    const sim = new Array(horizon);
    let t = 0;
    for (let b = 0; b < nBlocks && t < horizon; b++) {
      const start = Math.floor(rng() * (rets.length - block));
      for (let k = 0; k < block && t < horizon; k++, t++) {
        sim[t] = rets[start + k] + shift;
      }
    }
    let w = 0;
    for (let m = 0; m < horizon; m++) {
      w = (w + monthlyContribution) * (1 + sim[m]);
      monthly[m][s] = w;
    }
    finalWealth[s] = w;
  }

  for (let m = 0; m < horizon; m++) {
    const sorted = monthly[m].slice().sort((a, b) => a - b);
    wealthPct.p5.push(percentileLinear(sorted, 5));
    wealthPct.p25.push(percentileLinear(sorted, 25));
    wealthPct.p50.push(percentileLinear(sorted, 50));
    wealthPct.p75.push(percentileLinear(sorted, 75));
    wealthPct.p95.push(percentileLinear(sorted, 95));
  }

  return {
    percentiles: wealthPct,
    months: Array.from({ length: horizon }, (_, i) => i + 1),
    finalWealth,
    totalContributed: monthlyContribution * horizon,
  };
}
