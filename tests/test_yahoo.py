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

    def test_drops_partial_candle(self):
        # last row is a partial "today" candle: 0/null OHLC -> dropped
        raw = (
            '{"chart":{"result":[{"timestamp":[1751068800,1751155200],'
            '"indicators":{"quote":[{"open":[100.0,0.0],"high":[101.0,0.0],'
            '"low":[99.0,0.0],"close":[100.5,7246.79]}]}}],"error":null}}'
        )
        df = _parse_chart_json(raw)
        assert len(df) == 1
        assert df["close"].iloc[0] == pytest.approx(100.5)

    def test_error_and_empty_raise(self):
        with pytest.raises(ValueError):
            _parse_chart_json('{"chart":{"result":null,"error":{"code":"x"}}}')
        with pytest.raises(ValueError):
            _parse_chart_json('{"chart":{"result":[{"timestamp":null,'
                              '"indicators":{"quote":[{}]}}],"error":null}}')
