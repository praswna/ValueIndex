import numpy as np
import pandas as pd
import pytest

from valueindex import quant


def monthly_index(n, start="1950-01-01"):
    return pd.date_range(start, periods=n, freq="MS")


class TestConditionalQuantiles:
    def setup_method(self):
        rng = np.random.default_rng(3)
        idx = monthly_index(1200)
        self.x = pd.Series(rng.uniform(5, 45, 1200), index=idx)
        self.y = pd.Series(-0.3 * self.x.values + rng.normal(0, 1.5, 1200), index=idx)

    def test_quantile_ordering(self):
        cq = quant.conditional_quantiles(self.x, self.y)
        valid = cq.dropna()
        assert (valid["q5"] <= valid["q50"]).all()
        assert (valid["q50"] <= valid["q95"]).all()

    def test_median_tracks_downward_relationship(self):
        cq = quant.conditional_quantiles(self.x, self.y).dropna()
        assert cq["q50"].iloc[0] > cq["q50"].iloc[-1]
        # slope roughly -0.3
        slope = (cq["q50"].iloc[-1] - cq["q50"].iloc[0]) / (
            cq.index[-1] - cq.index[0]
        )
        assert slope == pytest.approx(-0.3, abs=0.1)

    def test_weighted_quantile_uniform_weights(self):
        vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        w = np.ones(5)
        assert quant.weighted_quantile(vals, w, 0.5) == pytest.approx(3.0)


class TestPcaComposite:
    def test_common_factor_recovered(self):
        rng = np.random.default_rng(5)
        idx = monthly_index(600)
        factor = pd.Series(np.cumsum(rng.normal(0, 1, 600)), index=idx)
        z = pd.DataFrame(
            {
                "a": factor + rng.normal(0, 0.3, 600),
                "b": factor + rng.normal(0, 0.3, 600),
                "c": factor + rng.normal(0, 0.3, 600),
                "d": factor + rng.normal(0, 0.3, 600),
            }
        ).apply(lambda s: (s - s.mean()) / s.std())
        res = quant.pca_composite(z, min_series=2)
        assert res.explained_ratio > 0.85
        # composite correlates strongly with the true factor
        corr = res.composite.corr((factor - factor.mean()) / factor.std())
        assert abs(corr) > 0.95
        # sign convention: expensive (high factor) -> high composite
        assert corr > 0

    def test_handles_staggered_starts(self):
        rng = np.random.default_rng(6)
        idx = monthly_index(600)
        factor = pd.Series(np.cumsum(rng.normal(0, 1, 600)), index=idx)
        z = pd.DataFrame(
            {
                "long": factor + rng.normal(0, 0.3, 600),
                "long2": factor + rng.normal(0, 0.3, 600),
                "short": (factor + rng.normal(0, 0.3, 600)).where(idx >= idx[400]),
            }
        ).apply(lambda s: (s - s.mean()) / s.std())
        res = quant.pca_composite(z, min_series=2)
        assert res.composite.notna().sum() > 500  # early rows still scored
        assert abs(res.composite.std() - 1) < 0.01


class TestHalfLife:
    def test_recovers_known_phi(self):
        # Half-life is very sensitive near phi=1, so test a moderately
        # persistent process with a long sample and a loose tolerance.
        rng = np.random.default_rng(9)
        phi = 0.95  # half-life ~ 13.5 months
        n = 6000
        x = np.zeros(n)
        for t in range(1, n):
            x[t] = phi * x[t - 1] + rng.normal()
        s = pd.Series(x, index=monthly_index(n))
        hl = quant.ar1_half_life_months(s)
        assert hl == pytest.approx(np.log(0.5) / np.log(phi), rel=0.3)

    def test_random_walk_returns_none(self):
        rng = np.random.default_rng(10)
        s = pd.Series(np.cumsum(rng.normal(0, 1, 500)), index=monthly_index(500))
        hl = quant.ar1_half_life_months(s)
        assert hl is None or hl > 100  # non-reverting

    def test_too_short_returns_none(self):
        s = pd.Series([1.0, 2.0, 1.5], index=monthly_index(3))
        assert quant.ar1_half_life_months(s) is None


class TestSimulateDca:
    def test_zero_returns_equals_contributions(self):
        rets = pd.Series(np.zeros(600), index=monthly_index(600))
        res = quant.simulate_dca(rets, 100, years=10, n_sims=50)
        assert res.total_contributed == pytest.approx(100 * 120)
        assert np.allclose(res.final_wealth, 100 * 120)

    def test_positive_drift_beats_contributions(self):
        rng = np.random.default_rng(11)
        rets = pd.Series(rng.normal(0.005, 0.04, 900), index=monthly_index(900))
        res = quant.simulate_dca(rets, 100, years=20, n_sims=300)
        assert np.median(res.final_wealth) > res.total_contributed

    def test_percentile_ordering_and_drift_target(self):
        rng = np.random.default_rng(12)
        rets = pd.Series(rng.normal(0.004, 0.04, 900), index=monthly_index(900))
        res = quant.simulate_dca(rets, 100, years=15, n_sims=300, annual_drift_target=0.0)
        p = res.percentiles
        assert (p["p5"] <= p["p50"]).all() and (p["p50"] <= p["p95"]).all()
        # zero real drift -> median final wealth near contributions
        assert np.median(res.final_wealth) == pytest.approx(
            res.total_contributed, rel=0.35
        )

    def test_reproducible_with_seed(self):
        rng = np.random.default_rng(13)
        rets = pd.Series(rng.normal(0.004, 0.04, 600), index=monthly_index(600))
        a = quant.simulate_dca(rets, 100, years=5, n_sims=100, seed=7)
        b = quant.simulate_dca(rets, 100, years=5, n_sims=100, seed=7)
        assert np.array_equal(a.final_wealth, b.final_wealth)
