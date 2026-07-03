"""Toy backtester for the short-term lab page.

Signals are computed on close prices; entries apply to the NEXT day's
return (no look-ahead). Pure functions, unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def rule_rsi_oversold(ohlc: pd.DataFrame, threshold: float = 30, hold: int = 5) -> pd.Series:
    """Long for `hold` days after RSI(14) closes below threshold."""
    signal = rsi(ohlc["close"]) < threshold
    return signal.rolling(hold, min_periods=1).max().fillna(0).astype(float)

def rule_golden_cross(ohlc: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.Series:
    """Long while the fast moving average is above the slow one."""
    close = ohlc["close"]
    return (close.rolling(fast).mean() > close.rolling(slow).mean()).astype(float)


def rule_down_streak(ohlc: pd.DataFrame, streak: int = 3, hold: int = 5) -> pd.Series:
    """Long for `hold` days after `streak` consecutive down closes."""
    down = ohlc["close"].diff() < 0
    run = down.rolling(streak).sum() >= streak
    return run.rolling(hold, min_periods=1).max().fillna(0).astype(float)


def rule_dip_buy(ohlc: pd.DataFrame, dip_pct: float = 10, hold: int = 20) -> pd.Series:
    """Long for `hold` days when price is `dip_pct`% below its 1y high."""
    close = ohlc["close"]
    high_1y = close.rolling(252, min_periods=60).max()
    signal = close <= high_1y * (1 - dip_pct / 100)
    return signal.rolling(hold, min_periods=1).max().fillna(0).astype(float)


def rule_monday(ohlc: pd.DataFrame) -> pd.Series:
    """Long only on Mondays (weekend-effect test)."""
    idx = pd.DatetimeIndex(ohlc["date"]) if "date" in ohlc else ohlc.index
    return pd.Series((idx.dayofweek == 0).astype(float), index=ohlc.index)


RULES = {
    "rsi": ("RSI 30 이하 매수 (5일 보유)", rule_rsi_oversold),
    "golden_cross": ("골든크로스 (50일 > 200일 이평선)", rule_golden_cross),
    "down_streak": ("3일 연속 하락 후 매수 (5일 보유)", rule_down_streak),
    "dip_buy": ("고점 대비 -10% 진입 (20일 보유)", rule_dip_buy),
    "monday": ("월요일 효과 (월요일만 보유)", rule_monday),
}


@dataclass(frozen=True)
class BacktestResult:
    n_trades: int            # number of entry events (0 -> 1 transitions)
    n_days_in_market: int
    win_rate: float          # share of in-market days with positive return
    mean_daily_ret: float    # average daily return while in market, percent
    t_stat: float            # vs zero mean of in-market daily returns
    total_costs_pct: float   # cumulative cost drag, percent
    equity_curve: pd.Series  # strategy cumulative growth (starts at 1)
    buy_hold_curve: pd.Series


def evaluate(positions: pd.Series, close: pd.Series, cost_bps: float = 0.0) -> BacktestResult:
    """Apply positions to next-day returns with per-side transaction costs."""
    positions = positions.fillna(0).clip(0, 1)
    daily_ret = close.pct_change().fillna(0)
    # Signal on day t earns day t+1's return: shift positions forward.
    held = positions.shift(1).fillna(0)
    strat_ret = held * daily_ret
    # Cost charged on every position change (entry and exit).
    turns = positions.diff().abs().fillna(positions.iloc[0])
    cost = turns * (cost_bps / 10_000)
    strat_ret_net = strat_ret - cost

    in_market = strat_ret[held > 0]
    n_days = len(in_market)
    if n_days > 1 and in_market.std() > 0:
        t_stat = in_market.mean() / (in_market.std() / np.sqrt(n_days))
    else:
        t_stat = 0.0
    entries = int(((positions > 0) & (positions.shift(1).fillna(0) == 0)).sum())

    return BacktestResult(
        n_trades=entries,
        n_days_in_market=n_days,
        win_rate=float((in_market > 0).mean()) if n_days else 0.0,
        mean_daily_ret=float(in_market.mean() * 100) if n_days else 0.0,
        t_stat=float(t_stat),
        total_costs_pct=float(cost.sum() * 100),
        equity_curve=(1 + strat_ret_net).cumprod(),
        buy_hold_curve=(1 + daily_ret).cumprod(),
    )
