import numpy as np
import pandas as pd
import pytest

from valueindex import backtest


def make_ohlc(closes, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c}, index=idx)


class TestNoLookAhead:
    def test_signal_earns_next_day_return(self):
        # Day 0 signal; day 1 return +10%; day 2 return -50%.
        ohlc = make_ohlc([100, 110, 55])
        positions = pd.Series([1.0, 0.0, 0.0], index=ohlc.index)
        res = backtest.evaluate(positions, ohlc["close"])
        # held only day 1 -> +10% and nothing else
        assert res.equity_curve.iloc[-1] == pytest.approx(1.10)


class TestCosts:
    def test_cost_monotonicity(self):
        rng = np.random.default_rng(7)
        closes = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, 500))
        ohlc = make_ohlc(closes)
        positions = backtest.rule_down_streak(ohlc)
        finals = [
            backtest.evaluate(positions, ohlc["close"], cost_bps=bps).equity_curve.iloc[-1]
            for bps in (0, 10, 50)
        ]
        assert finals[0] > finals[1] > finals[2]

    def test_zero_positions_zero_cost(self):
        ohlc = make_ohlc([100, 101, 102])
        res = backtest.evaluate(pd.Series(0.0, index=ohlc.index), ohlc["close"], cost_bps=100)
        assert res.total_costs_pct == 0
        assert res.n_trades == 0


class TestRules:
    def test_positions_are_binary(self):
        rng = np.random.default_rng(11)
        closes = 100 * np.cumprod(1 + rng.normal(0, 0.01, 600))
        ohlc = make_ohlc(closes)
        for _, (label, fn) in backtest.RULES.items():
            pos = fn(ohlc)
            assert set(pos.dropna().unique()) <= {0.0, 1.0}, label

    def test_monday_rule(self):
        ohlc = make_ohlc([100] * 10, start="2024-01-01")  # Mon Jan 1 2024
        pos = backtest.rule_monday(ohlc)
        assert pos.sum() == 2  # two Mondays in 10 business days
        assert pos[ohlc.index.dayofweek == 0].all()

    def test_buy_hold_curve_matches_prices(self):
        ohlc = make_ohlc([100, 110, 121])
        res = backtest.evaluate(pd.Series(0.0, index=ohlc.index), ohlc["close"])
        assert res.buy_hold_curve.iloc[-1] == pytest.approx(1.21)
