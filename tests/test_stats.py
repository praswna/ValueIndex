import pandas as pd
import pytest

from valueindex import stats


def series(vals, start="2000-01-01"):
    return pd.Series(vals, index=pd.date_range(start, periods=len(vals), freq="MS"), dtype=float)


class TestPercentile:
    def test_known_small_series(self):
        s = series([1, 2, 3, 4, 5])
        p = stats.percentile_rank(s)
        assert p.iloc[-1] == pytest.approx(100.0)
        assert p.iloc[0] == pytest.approx(20.0)


class TestRatingBands:
    @pytest.mark.parametrize(
        "z,key",
        [
            (-2.5, "very_cheap"),
            (-2.0, "very_cheap"),   # boundary belongs to the outer band
            (-1.5, "cheap"),
            (0.0, "fair"),
            (1.0, "fair"),
            (1.5, "expensive"),
            (2.5, "very_expensive"),
        ],
    )
    def test_boundaries(self, z, key):
        assert stats.rating(z).key == key

    def test_colors_unique(self):
        colors = [r.color for _, r in stats.RATINGS]
        assert len(set(colors)) == len(colors)


class TestSummary:
    def test_fields(self):
        s = series(list(range(1, 25)))  # 2 years rising
        summ = stats.summary(s)
        assert summ.current == 24.0
        assert summ.pctile == pytest.approx(100.0)
        assert summ.delta_1y == pytest.approx(12.0)
        assert summ.start == s.index[0]

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            stats.summary(series([]))


class TestBands:
    def test_symmetry(self):
        s = series([10, 20, 30])
        b = stats.bands(s)
        assert b["mean"].iloc[0] == pytest.approx(20.0)
        assert (b["plus1"] - b["mean"]).iloc[0] == pytest.approx((b["mean"] - b["minus1"]).iloc[0])
