from pathlib import Path

import pandas as pd
import pytest

from valueindex.fetchers.yahoo import _parse_chart_json

FIXTURES = Path(__file__).parent / "fixtures"


class TestYahooChart:
    def test_parses_ohlc(self):
        df = _parse_chart_json((FIXTURES / "yahoo_chart.json").read_text())
        assert list(df.columns) == ["date", "open", "high", "low", "close"]
        assert len(df) == 3
        assert df["close"].iloc[-1] == pytest.approx(3250.8)
        assert df["date"].is_monotonic_increasing
        # unix seconds -> naive UTC date
        assert df["date"].iloc[0] == pd.Timestamp("2025-06-28")

    def test_drops_null_close(self):
        raw = (
            '{"chart":{"result":[{"timestamp":[1751068800,1751155200],'
            '"indicators":{"quote":[{"close":[100.0,null]}]}}],"error":null}}'
        )
        df = _parse_chart_json(raw)
        assert len(df) == 1

    def test_error_and_empty_raise(self):
        with pytest.raises(ValueError):
            _parse_chart_json('{"chart":{"result":null,"error":{"code":"x"}}}')
        with pytest.raises(ValueError):
            _parse_chart_json('{"chart":{"result":[{"timestamp":null,'
                              '"indicators":{"quote":[{}]}}],"error":null}}')
