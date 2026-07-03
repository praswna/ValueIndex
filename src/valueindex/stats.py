"""Percentiles, z-scores, sigma ratings, and summary statistics."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Rating:
    key: str        # e.g. "very_expensive"
    label_ko: str   # e.g. "매우 고평가"
    color: str      # hex, shared across all pages


# Direction-aligned z-score -> five bands (Current Market Valuation style).
# Diverging blue<->red with neutral gray midpoint; validated for CVD
# separation and lightness on a white surface. Rating colors always ship
# with their text label, never color alone.
RATINGS = [
    (-2.0, Rating("very_cheap", "매우 저평가", "#1c5cab")),
    (-1.0, Rating("cheap", "저평가", "#5598e7")),
    (1.0, Rating("fair", "적정", "#898781")),
    (2.0, Rating("expensive", "고평가", "#ec835a")),
    (float("inf"), Rating("very_expensive", "매우 고평가", "#c22f2f")),
]


def rating(zscore_value: float) -> Rating:
    for upper, r in RATINGS:
        if zscore_value <= upper:
            return r
    return RATINGS[-1][1]


def percentile_rank(s: pd.Series) -> pd.Series:
    """Full-history percentile rank in [0, 100]."""
    return s.rank(pct=True) * 100


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


@dataclass(frozen=True)
class IndicatorSummary:
    current: float
    asof: pd.Timestamp
    mean: float
    std: float
    pctile: float          # percentile of current value in history
    z: float               # z-score of current value
    delta_1y: float | None
    hist_min: float
    hist_max: float
    start: pd.Timestamp


def summary(s: pd.Series) -> IndicatorSummary:
    """Summary of a monthly series (index: DatetimeIndex), NaNs dropped."""
    s = s.dropna()
    if s.empty:
        raise ValueError("empty series")
    current = float(s.iloc[-1])
    asof = s.index[-1]
    year_ago = asof - pd.DateOffset(years=1)
    prior = s.loc[:year_ago]
    delta_1y = current - float(prior.iloc[-1]) if len(prior) else None
    return IndicatorSummary(
        current=current,
        asof=asof,
        mean=float(s.mean()),
        std=float(s.std()),
        pctile=float(percentile_rank(s).iloc[-1]),
        z=float(zscore(s).iloc[-1]),
        delta_1y=delta_1y,
        hist_min=float(s.min()),
        hist_max=float(s.max()),
        start=s.index[0],
    )


def bands(s: pd.Series) -> pd.DataFrame:
    """Constant full-sample mean and +-1/2 sigma bands, aligned to s."""
    s = s.dropna()
    mean, std = s.mean(), s.std()
    return pd.DataFrame(
        {
            "mean": mean,
            "plus1": mean + std,
            "minus1": mean - std,
            "plus2": mean + 2 * std,
            "minus2": mean - 2 * std,
        },
        index=s.index,
    )
