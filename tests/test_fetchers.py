from pathlib import Path

import pandas as pd
import pytest

from valueindex.fetchers.fred import _parse_api_json, _parse_fredgraph_csv
from valueindex.fetchers.multpl import _parse_table_html
from valueindex.fetchers.shiller import _clean_data_sheet, _parse_shiller_date
from valueindex.fetchers.stooq import _parse_stooq_csv

FIXTURES = Path(__file__).parent / "fixtures"


class TestFred:
    def test_old_date_header_and_missing_dot(self):
        df = _parse_fredgraph_csv((FIXTURES / "fredgraph_old_header.csv").read_text(), "GDP")
        assert list(df.columns) == ["date", "value"]
        assert len(df) == 3  # the "." row is dropped
        assert df["value"].iloc[0] == pytest.approx(243.164)

    def test_new_observation_date_header(self):
        df = _parse_fredgraph_csv((FIXTURES / "fredgraph_new_header.csv").read_text(), "DGS10")
        assert len(df) == 3
        assert df["date"].iloc[-1] == pd.Timestamp("2024-01-05")

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            _parse_fredgraph_csv("foo,bar\n1,2\n", "X")

    def test_official_api_json(self):
        df = _parse_api_json((FIXTURES / "fred_api.json").read_text(), "GDP")
        assert list(df.columns) == ["date", "value"]
        assert len(df) == 3  # "." observation dropped
        assert df["value"].iloc[-1] == pytest.approx(259.745)

    def test_official_api_empty_raises(self):
        with pytest.raises(ValueError):
            _parse_api_json('{"observations": []}', "GDP")


class TestShillerDate:
    def test_fractional_month_trap_dot1_is_october(self):
        assert _parse_shiller_date("1871.1") == pd.Timestamp("1871-10-01")

    def test_dot01_is_january(self):
        assert _parse_shiller_date("1871.01") == pd.Timestamp("1871-01-01")

    def test_regular_months(self):
        assert _parse_shiller_date(2020.05) == pd.Timestamp("2020-05-01")
        assert _parse_shiller_date("1999.12") == pd.Timestamp("1999-12-01")

    def test_footer_noise_returns_none(self):
        assert _parse_shiller_date("Source: Robert Shiller") is None
        assert _parse_shiller_date("") is None
        assert _parse_shiller_date("1871") is None
        assert _parse_shiller_date("1871.13") is None


class TestShillerClean:
    def test_drops_footers_and_partial_rows(self):
        # Mimics the raw Data-sheet grid: 17 positional columns.
        rows = [
            ["1871.01", 4.44, 0.26, 0.4, 12.46, 0, 5.32, 100.0, 0, 0, 8.9, 0, 15.0, 0, 0, 0, 3.1],
            ["1871.1", 4.60, 0.26, 0.4, 12.20, 0, 5.30, 101.0, 0, 0, 9.0, 0, 15.2, 0, 0, 0, 3.0],
            ["2026.06", 6200.0, 75.0, 210.0, 330.0, 0, 4.3, 6200.0, 0, 0, 210.0, 0, 40.4, 0, 0, 0, 1.2],
            ["2026.07", None, None, None, None, 0, None, None, 0, 0, None, 0, None, 0, 0, 0, None],
            ["Note: data are monthly averages", None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None],
        ]
        raw = pd.DataFrame(rows)
        df = _clean_data_sheet(raw)
        assert len(df) == 3  # partial month and footer dropped
        assert df["date"].iloc[1] == pd.Timestamp("1871-10-01")
        assert df["cape"].iloc[-1] == pytest.approx(40.4)
        assert df["ecy"].iloc[-1] == pytest.approx(1.2)


class TestMultpl:
    def test_parses_percent_and_estimate_markers(self):
        df = _parse_table_html((FIXTURES / "multpl_table.html").read_text())
        assert list(df.columns) == ["date", "value"]
        assert len(df) == 4
        assert df["value"].iloc[-1] == pytest.approx(29.41)  # estimate row cleaned
        assert df["date"].is_monotonic_increasing


class TestStooq:
    def test_parses_ohlc(self):
        df = _parse_stooq_csv((FIXTURES / "stooq_daily.csv").read_text())
        assert list(df.columns) == ["date", "open", "high", "low", "close"]
        assert len(df) == 3
        assert df["close"].iloc[-1] == pytest.approx(6178.1)
