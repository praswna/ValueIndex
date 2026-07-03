"""Advanced-statistics helpers: kernel quantile regression, PCA composite,
AR(1) mean-reversion half-life, and block-bootstrap DCA simulation.

Pure numpy/pandas functions, no ML dependencies, all unit-tested.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# A. Conditional quantiles (Nadaraya-Watson-weighted quantile regression)
# ---------------------------------------------------------------------------


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """Quantile of `values` under observation `weights` (q in [0, 1])."""
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w) - 0.5 * w
    cum /= w.sum()
    return float(np.interp(q, cum, v))


def conditional_quantiles(
    x: pd.Series,
    y: pd.Series,
    quantiles: tuple[float, ...] = (0.05, 0.25, 0.5, 0.75, 0.95),
    n_grid: int = 60,
    bandwidth: float | None = None,
) -> pd.DataFrame:
    """Kernel-weighted conditional quantiles of y given x.

    For each grid point x0, observations are weighted by a Gaussian kernel
    in x, and weighted quantiles of y are computed. Returns a frame indexed
    by the x grid with one column per quantile (e.g. "q50").
    """
    df = pd.DataFrame({"x": x, "y": y}).dropna()
    xv, yv = df["x"].to_numpy(float), df["y"].to_numpy(float)
    if bandwidth is None:
        # Silverman-flavored rule of thumb, widened for stability in tails.
        bandwidth = 1.06 * xv.std() * len(xv) ** (-1 / 5) * 1.5
    grid = np.linspace(xv.min(), xv.max(), n_grid)
    out = {f"q{int(q * 100)}": np.empty(n_grid) for q in quantiles}
    for i, x0 in enumerate(grid):
        w = np.exp(-0.5 * ((xv - x0) / bandwidth) ** 2)
        # Skip grid points with too little effective data.
        if w.sum() < 5:
            for q in quantiles:
                out[f"q{int(q * 100)}"][i] = np.nan
            continue
        for q in quantiles:
            out[f"q{int(q * 100)}"][i] = weighted_quantile(yv, w, q)
    return pd.DataFrame(out, index=pd.Index(grid, name="x"))


# ---------------------------------------------------------------------------
# B. PCA composite valuation index
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PcaComposite:
    composite: pd.Series          # first-PC score, z-scaled, monthly
    weights: pd.Series            # loading per indicator (sums of squares = 1)
    explained_ratio: float        # share of total variance carried by PC1


def pca_composite(aligned_z: pd.DataFrame, min_series: int = 4) -> PcaComposite:
    """First principal component of direction-aligned z-scored indicators.

    Indicators start at different dates, so the correlation matrix uses
    pairwise-complete observations and per-row scores use only the
    indicators available that month (weights renormalized). Rows with
    fewer than `min_series` indicators are dropped.
    """
    corr = aligned_z.corr(min_periods=24)
    eigvals, eigvecs = np.linalg.eigh(corr.to_numpy())
    v1 = eigvecs[:, -1]
    if v1.sum() < 0:  # sign convention: composite up = more expensive
        v1 = -v1
    weights = pd.Series(v1, index=aligned_z.columns)
    explained = float(eigvals[-1] / eigvals.sum())

    z = aligned_z.to_numpy(float)
    w = weights.to_numpy(float)
    mask = ~np.isnan(z)
    eff_w = np.where(mask, w, 0.0)
    norm = np.sqrt((eff_w**2).sum(axis=1))
    score = np.nansum(z * eff_w, axis=1) / np.where(norm == 0, np.nan, norm)
    score[mask.sum(axis=1) < min_series] = np.nan
    composite = pd.Series(score, index=aligned_z.index).dropna()
    composite = (composite - composite.mean()) / composite.std()
    return PcaComposite(composite=composite, weights=weights, explained_ratio=explained)


# ---------------------------------------------------------------------------
# Nearest historical analogs (z-space nearest-neighbor search)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Analog:
    date: pd.Timestamp
    distance: float      # RMS difference per shared indicator, in sigmas
    shared: int          # number of indicators available in both months


def nearest_analogs(
    aligned_z: pd.DataFrame,
    n: int = 4,
    min_separation_months: int = 36,
    exclude_recent_months: int = 60,
    min_shared: int = 4,
) -> list[Analog]:
    """Historical months most similar to the latest month in indicator space.

    Distance is the RMS z-score difference over indicators present in BOTH
    months (indicators start at different dates). The most recent
    `exclude_recent_months` are excluded (trivially similar), and picked
    analogs must be `min_separation_months` apart so one episode doesn't
    fill every slot.
    """
    target = aligned_z.iloc[-1]
    hist = aligned_z.iloc[:-1]
    if exclude_recent_months:
        hist = hist.iloc[:-exclude_recent_months]
    if hist.empty:
        return []

    diff_sq = (hist - target) ** 2
    shared = diff_sq.notna().sum(axis=1)
    dist = np.sqrt(diff_sq.mean(axis=1, skipna=True))
    dist[shared < min_shared] = np.nan

    picked: list[Analog] = []
    for date, d in dist.dropna().sort_values().items():
        if any(abs((date - p.date).days) < min_separation_months * 30 for p in picked):
            continue
        picked.append(Analog(date=date, distance=float(d), shared=int(shared[date])))
        if len(picked) >= n:
            break
    return picked


# ---------------------------------------------------------------------------
# C. AR(1) mean-reversion half-life
# ---------------------------------------------------------------------------


def ar1_half_life_months(s: pd.Series) -> float | None:
    """Half-life (months) of deviations from the mean under an AR(1) fit.

    phi is the lag-1 autocorrelation of the demeaned series; half-life is
    ln(0.5)/ln(phi). Returns None when the series doesn't mean-revert
    (phi >= 1) or is too short.
    """
    s = s.dropna()
    if len(s) < 36:
        return None
    x = s - s.mean()
    phi = float(x.autocorr(lag=1))
    if not (0 < phi < 1):
        return None
    return float(np.log(0.5) / np.log(phi))


# ---------------------------------------------------------------------------
# D. Block-bootstrap DCA (monthly contribution) simulation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DcaResult:
    percentiles: pd.DataFrame     # index: month, columns p5/p25/p50/p75/p95
    final_wealth: np.ndarray      # per-simulation final wealth
    total_contributed: float


def simulate_dca(
    monthly_returns: pd.Series,
    monthly_contribution: float,
    years: int,
    n_sims: int = 2000,
    block: int = 12,
    annual_drift_target: float | None = None,
    seed: int = 42,
) -> DcaResult:
    """Simulate dollar-cost averaging with block-bootstrapped returns.

    Contiguous `block`-month chunks of history are resampled to preserve
    volatility clustering. If `annual_drift_target` (percent, real) is
    given, the resampled returns are shifted so their expected annual
    return matches it — this plugs the Bogle-calculator estimate in while
    keeping historical volatility.
    """
    rng = np.random.default_rng(seed)
    rets = monthly_returns.dropna().to_numpy(float)
    horizon = years * 12
    n_blocks = int(np.ceil(horizon / block))
    starts = rng.integers(0, len(rets) - block, size=(n_sims, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_sims, -1)
    sims = rets[idx[:, :horizon]]

    if annual_drift_target is not None:
        target_monthly = (1 + annual_drift_target / 100) ** (1 / 12) - 1
        sims = sims + (target_monthly - rets.mean())

    wealth = np.zeros((n_sims, horizon))
    w = np.zeros(n_sims)
    for t in range(horizon):
        w = (w + monthly_contribution) * (1 + sims[:, t])
        wealth[:, t] = w

    pct = pd.DataFrame(
        {
            f"p{p}": np.percentile(wealth, p, axis=0)
            for p in (5, 25, 50, 75, 95)
        },
        index=pd.RangeIndex(1, horizon + 1, name="month"),
    )
    return DcaResult(
        percentiles=pct,
        final_wealth=wealth[:, -1],
        total_contributed=monthly_contribution * horizon,
    )
