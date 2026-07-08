from pathlib import Path

import pandas as pd
import pytest

from valueindex.fetchers.korea import _parse_per_pbr_json, _parse_worldbank_gdp

FIXTURES = Path(__file__).parent / "fixtures"


class TestKrx:
    def test_parses_per_pbr_div(self):
        df = _parse_per_pbr_json((FIXTURES / "krx_per_pbr.json").read_text())
        assert list(df.columns) == ["date", "per", "pbr", "div_yield"]
        assert len(df) == 3
        assert df["date"].is_monotonic_increasing
        assert df["per"].iloc[-1] == pytest.approx(13.24)
        # comma-thousands parsed, '-' dividend -> NaN
        assert df["per"].iloc[1] == pytest.approx(13001.0)
        assert pd.isna(df["div_yield"].iloc[1])

    def test_alternate_key_and_empty(self):
        assert _parse_per_pbr_json(
            '{"OutBlock_1": [{"TRD_DD": "2026/01/02", "PER": "10", "PBR": "1", "DVD_YLD": "2"}]}'
        ).iloc[0]["per"] == 10
        with pytest.raises(ValueError):
            _parse_per_pbr_json('{"output": []}')


class TestWorldBank:
    def test_parses_gdp_drops_null(self):
        df = _parse_worldbank_gdp((FIXTURES / "worldbank_gdp.json").read_text())
        assert list(df.columns) == ["date", "value"]
        assert len(df) == 3  # null 2022 dropped
        assert df["date"].iloc[-1] == pd.Timestamp("2024-12-31")
        assert df["value"].iloc[-1] == 1_870_000_000_000

    def test_empty_page_raises(self):
        with pytest.raises(ValueError):
            _parse_worldbank_gdp('[{"page":1},null]')
