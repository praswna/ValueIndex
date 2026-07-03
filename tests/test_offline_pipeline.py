"""End-to-end offline pipeline: sample data -> panel -> summaries."""
import pandas as pd
import pytest

from valueindex import config, indicators, loader, registry, stats


@pytest.fixture(scope="module")
def panel(monkeypatch_module):
    monkeypatch_module.setattr(config, "OFFLINE", True)
    # Point the cache away from any real cache dir.
    data = {name: loader._load_sample(name) for name in loader.SOURCES}
    assert all(df is not None for df in data.values()), "missing sample csvs"
    return indicators.build_panel(data)


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


class TestOfflinePipeline:
    def test_all_indicators_present(self, panel):
        assert set(registry.VALUATION_KEYS) <= set(panel.columns)
        assert panel.index.is_monotonic_increasing

    def test_no_all_nan_columns(self, panel):
        assert not panel.isna().all().any()

    def test_sample_values_plausible(self, panel):
        last = panel.dropna(how="all").iloc[-1]
        assert 25 < last["cape"] < 55
        assert 1.2 < last["buffett"] < 3.0
        assert 15 < last["pe"] < 45
        assert 0.2 < last["aiae"] < 0.6

    def test_summaries_work_for_all_valuation_keys(self, panel):
        for key in registry.VALUATION_KEYS:
            s = stats.summary(panel[key])
            assert 0 <= s.pctile <= 100
            assert s.asof >= pd.Timestamp("2025-01-01")

    def test_time_machine_no_lookahead(self, panel):
        """Percentile at a past date must use only data up to that date."""
        asof = pd.Timestamp("2000-03-01")
        s_full = panel["cape"].dropna()
        s_past = s_full.loc[:asof]
        p_past = stats.summary(s_past).pctile
        # dot-com peak: should be at/near its own historical max at the time
        assert p_past > 97

    def test_recessions_flagged(self):
        usrec = loader._load_sample("fred_USREC")
        s = usrec.set_index("date")["value"]
        assert s.loc["2008-06-01"] == 1
        assert s.loc["2019-06-01"] == 0
