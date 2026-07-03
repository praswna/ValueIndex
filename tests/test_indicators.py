import numpy as np
import pandas as pd
import pytest

from valueindex import indicators


def monthly_index(n, start="2000-01-01"):
    return pd.date_range(start, periods=n, freq="MS")


class TestBuffett:
    def test_million_billion_unit_trap(self):
        idx = monthly_index(2)
        equities = pd.Series([20_000_000.0, 22_000_000.0], index=idx)  # millions
        gdp = pd.Series([10_000.0, 11_000.0], index=idx)  # billions
        ratio = indicators.buffett_ratio(equities, gdp)
        assert ratio.iloc[0] == pytest.approx(2.0)
        assert ratio.iloc[1] == pytest.approx(2.0)


class TestFedSpread:
    def test_sign(self):
        idx = monthly_index(1)
        pe = pd.Series([20.0], index=idx)     # earnings yield 5%
        y10 = pd.Series([4.0], index=idx)
        assert indicators.fed_spread(pe, y10).iloc[0] == pytest.approx(1.0)
        y10_high = pd.Series([7.0], index=idx)
        assert indicators.fed_spread(pe, y10_high).iloc[0] == pytest.approx(-2.0)


class TestTrendDeviation:
    def test_pure_exponential_has_zero_deviation(self):
        idx = monthly_index(240)
        s = pd.Series(100 * 1.005 ** np.arange(240), index=idx)
        dev = indicators.trend_deviation(s)
        assert dev.abs().max() < 1e-6

    def test_spike_is_positive(self):
        idx = monthly_index(240)
        vals = 100 * 1.005 ** np.arange(240)
        vals[-1] *= 1.5
        dev = indicators.trend_deviation(pd.Series(vals, index=idx))
        assert dev.iloc[-1] > 30


class TestAiae:
    def test_known_ratio_and_bounds(self):
        idx = monthly_index(1)
        inputs = pd.DataFrame(
            {
                "date": idx,
                "equities_nonfin": [30_000_000.0],  # 30,000 B
                "equities_fin": [10_000_000.0],     # 10,000 B
                "debt_business": [20_000.0],
                "debt_household": [20_000.0],
                "debt_federal": [15_000.0],
                "debt_state_local": [3_000.0],
                "debt_world": [2_000.0],
            }
        )
        # equities 40,000B / (40,000 + 60,000) = 0.4
        val = indicators.aiae(inputs).iloc[0]
        assert val == pytest.approx(0.4)
        assert 0 < val < 1


class TestDrawdown:
    def test_zero_at_peaks_and_negative_below(self):
        idx = monthly_index(5)
        s = pd.Series([100, 120, 90, 120, 150], index=idx, dtype=float)
        dd = indicators.drawdown(s)
        assert dd.iloc[0] == 0
        assert dd.iloc[1] == 0
        assert dd.iloc[2] == pytest.approx(-25.0)
        assert dd.iloc[4] == 0
        assert (dd <= 0).all()


class TestForwardReturn:
    def test_constant_growth(self):
        idx = monthly_index(360)
        # 0.5% per month -> (1.005^12 - 1) annualized
        tri = pd.Series(100 * 1.005 ** np.arange(360), index=idx)
        fwd = indicators.forward_10y_return(tri)
        expected = (1.005**12 - 1) * 100
        assert fwd.dropna().iloc[0] == pytest.approx(expected, rel=1e-6)
        # last 120 months have no forward window
        assert fwd.iloc[-120:].isna().all()


class TestBogle:
    def test_no_valuation_change(self):
        r = indicators.bogle_expected_return(2.0, 3.0, 30.0, 30.0)
        assert r == pytest.approx(5.0)

    def test_derating_reduces_return(self):
        r = indicators.bogle_expected_return(2.0, 3.0, 40.0, 20.0)
        assert r < 0  # halving of CAPE over 10y costs ~6.7%/yr


class TestQuarterlyAlignment:
    def test_ffill_limit_in_panel(self):
        # quarterly series should extend at most 3 months in the panel
        idx = pd.date_range("2020-01-01", periods=2, freq="QS")
        s = pd.Series([1.0, 2.0], index=idx)
        monthly = indicators.quarterly_to_monthly(s)
        assert monthly.loc["2020-02-01":"2020-03-01"].isna().all()
        filled = monthly.ffill(limit=indicators.QUARTER_FFILL_LIMIT)
        assert filled.loc["2020-03-01"] == 1.0


class TestRealTotalReturn:
    def test_grows_with_flat_price_and_positive_dividend(self):
        idx = monthly_index(24)
        price = pd.Series(100.0, index=idx)
        dividend = pd.Series(4.0, index=idx)  # 4% yield
        tri = indicators.real_total_return_index(price, dividend)
        assert tri.iloc[-1] > tri.iloc[0]
