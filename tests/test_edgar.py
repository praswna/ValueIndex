"""SEC EDGAR 13F fetcher parsing + whale-tracker payload deltas.

Live EDGAR is blocked by the sandbox egress policy, so these exercise the
parser against a fixture information table and the payload math against a
synthetic two-quarter frame. The Actions run validates live fetching.
"""
import pandas as pd
import pytest

from valueindex import config, loader, sitebuild
from valueindex.fetchers import edgar

INFOTABLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>037833100</cusip>
    <value>63000000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>300000000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
    <votingAuthority><Sole>300000000</Sole><Shared>0</Shared><None>0</None></votingAuthority>
  </infoTable>
  <infoTable>
    <nameOfIssuer>ALIBABA GROUP HLDG LTD</nameOfIssuer>
    <titleOfClass>SPON ADS</titleOfClass>
    <cusip>01609W102</cusip>
    <value>20000000</value>
    <shrsOrPrnAmt><sshPrnamt>150000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    <putCall>Put</putCall>
    <investmentDiscretion>SOLE</investmentDiscretion>
  </infoTable>
</informationTable>"""


class TestEdgarParse:
    def test_registered_source(self):
        assert "edgar_whales" in loader.SOURCES
        assert "edgar" in config.CACHE_TTL

    def test_parse_infotable_dollars(self):
        df = edgar._parse_infotable(INFOTABLE_XML, scale=1.0)
        assert len(df) == 2
        apple = df[df["name"] == "APPLE INC"].iloc[0]
        assert apple["value_usd"] == 63e9
        assert apple["shares"] == 300e6
        assert apple["put_call"] == ""
        baba = df[df["name"] == "ALIBABA GROUP HLDG LTD"].iloc[0]
        assert baba["put_call"] == "Put"

    def test_parse_infotable_thousands_scale(self):
        df = edgar._parse_infotable(INFOTABLE_XML, scale=1000.0)
        apple = df[df["name"] == "APPLE INC"].iloc[0]
        assert apple["value_usd"] == 63e9 * 1000

    def test_parse_infotable_empty_raises(self):
        with pytest.raises(ValueError):
            edgar._parse_infotable("<informationTable></informationTable>", 1.0)

    def test_recent_13f_newest_first(self):
        subs = {"filings": {"recent": {
            "form": ["4", "13F-HR", "8-K", "13F-HR", "13F-HR"],
            "accessionNumber": ["a0", "a1", "a2", "a3", "a4"],
            "reportDate": ["2026-01-01", "2026-03-31", "2026-02-01",
                           "2025-12-31", "2025-09-30"],
            "filingDate": ["2026-01-02", "2026-05-15", "2026-02-02",
                           "2026-02-13", "2025-11-14"],
        }}}
        out = edgar._recent_13f(subs, n=2)
        assert [f["report_date"] for f in out] == ["2026-03-31", "2025-12-31"]
        assert out[0]["accession"] == "a1"


def _row(whale, q, cusip, name, val, sh, pc=""):
    return {"whale": whale, "quarter": q, "filed": "2026-05-15", "cusip": cusip,
            "name": name, "class": "COM", "put_call": pc,
            "value_usd": val, "shares": sh}


class TestWhalesPayload:
    def _frame(self):
        L, P = "2026-03-31", "2025-12-31"
        return pd.DataFrame([
            _row("berkshire", L, "A", "AAA", 100, 100),   # up (from 80)
            _row("berkshire", L, "B", "BBB", 50, 50),     # down (from 100)
            _row("berkshire", L, "C", "CCC", 10, 10),     # new
            _row("berkshire", P, "A", "AAA", 80, 80),
            _row("berkshire", P, "B", "BBB", 90, 100),
            _row("berkshire", P, "D", "DDD", 5, 5),        # exited
        ])

    def test_deltas_and_weights(self):
        out = sitebuild.whales_payload(self._frame(), None, "live")
        whales = {w["slug"]: w for w in out["whales"]}
        assert "berkshire" in whales
        w = whales["berkshire"]
        assert w["as_of"] == "2026-03-31"
        assert w["prior_quarter"] == "2025-12-31"
        assert w["total_value"] == 160
        # top sorted by value: A, B, C
        assert [h["name"] for h in w["top"]] == ["AAA", "BBB", "CCC"]
        kinds = {h["name"]: h["chg_kind"] for h in w["top"]}
        assert kinds == {"AAA": "up", "BBB": "down", "CCC": "new"}
        assert w["changes"]["new"] == ["CCC"]
        assert w["changes"]["exited"] == ["DDD"]
        assert w["changes"]["increased"] == ["AAA"]
        assert w["changes"]["decreased"] == ["BBB"]
        assert w["top5_weight"] == 100.0

    def test_sample_backfill_marks_status(self):
        # live frame missing a whale -> that whale comes from sample as "sample"
        sample = pd.DataFrame([_row("scion", "2026-03-31", "E", "EEE", 7, 7)])
        out = sitebuild.whales_payload(self._frame(), sample, "live")
        by = {w["slug"]: w for w in out["whales"]}
        assert by["berkshire"]["status"] == "live"
        assert by["scion"]["status"] == "sample"

    def test_put_call_suffix(self):
        df = pd.DataFrame([
            _row("scion", "2026-03-31", "X", "PUTCO", 9, 9, pc="Put"),
        ])
        out = sitebuild.whales_payload(df, None, "live")
        w = [x for x in out["whales"] if x["slug"] == "scion"][0]
        assert w["top"][0]["name"] == "PUTCO · 풋"
