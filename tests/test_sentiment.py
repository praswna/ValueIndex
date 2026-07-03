from pathlib import Path

import pandas as pd
import pytest

from valueindex.fetchers.sentiment import (
    _clean_aaii_frame,
    _parse_fear_greed_json,
    _parse_margin_tables,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestFinraMargin:
    def test_parses_yearly_tables_and_converts_to_billions(self):
        df = _parse_margin_tables((FIXTURES / "finra_margin.html").read_text())
        assert list(df.columns) == ["date", "value"]
        assert len(df) == 3  # unrelated table ignored
        assert df["date"].is_monotonic_increasing
        assert df["value"].iloc[-1] == pytest.approx(1005.123)  # $M -> $B

    def test_no_tables_raises(self):
        with pytest.raises(ValueError):
            _parse_margin_tables("<html><table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table></html>")


class TestCnnFearGreed:
    def test_parses_graphdata(self):
        df = _parse_fear_greed_json((FIXTURES / "cnn_fear_greed.json").read_text())
        assert list(df.columns) == ["date", "value"]
        assert len(df) == 3
        assert df["value"].iloc[-1] == pytest.approx(48.0)
        assert df["date"].iloc[0] == pd.Timestamp("2025-06-30")


class TestAaii:
    def test_fraction_format(self):
        raw = pd.DataFrame(
            {
                "Date": ["2026-06-11", "2026-06-18", None],
                "Bullish": [0.38, 0.45, None],
                "Neutral": [0.30, 0.25, None],
                "Bearish": [0.32, 0.30, "Source: AAII"],
            }
        )
        df = _clean_aaii_frame(raw)
        assert len(df) == 2  # footer row dropped
        assert df["value"].iloc[0] == pytest.approx(6.0)   # (38-32)%p
        assert df["value"].iloc[1] == pytest.approx(15.0)

    def test_percent_format(self):
        raw = pd.DataFrame(
            {"Reported Date": ["2026-06-11"], "Bullish": [38.0], "Bearish": [32.0]}
        )
        df = _clean_aaii_frame(raw)
        assert df["value"].iloc[0] == pytest.approx(6.0)

    def test_unexpected_columns_raise(self):
        with pytest.raises(ValueError):
            _clean_aaii_frame(pd.DataFrame({"foo": [1], "bar": [2]}))
