"""Live-source smoke tests. Run manually on a machine with network access:

    pytest -m network
"""
import pandas as pd
import pytest

from valueindex.fetchers import fred, multpl, shiller, stooq

pytestmark = pytest.mark.network

RECENT = pd.Timestamp.now() - pd.DateOffset(months=6)


def test_fred_live():
    df = fred.fetch_series("GDP")
    assert len(df) > 300
    assert df["date"].iloc[-1] > RECENT - pd.DateOffset(months=6)


def test_shiller_live():
    df = shiller.fetch_shiller()
    assert len(df) > 1700
    assert df["cape"].iloc[-1] > 5


def test_multpl_live():
    df = multpl.fetch_table("pe")
    assert len(df) > 1000
    assert df["date"].iloc[-1] > RECENT


def test_stooq_live():
    df = stooq.fetch_daily("spx_daily")
    assert len(df) > 5000
    assert df["date"].iloc[-1] > RECENT
