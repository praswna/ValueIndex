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

    def test_whales_config_well_formed(self):
        for slug, w in config.WHALES.items():
            assert w["cik"].isdigit() and len(w["cik"]) == 10, slug
            assert w["name_ko"] and w["note"], slug
            assert w["region"] in ("US", "KR", "NO"), slug

    def test_whale_without_any_data_is_skipped(self):
        # a WHALES entry absent from both live and sample frames must not
        # break the payload (new whales before their first collect).
        df = pd.DataFrame([_row("berkshire", "2026-03-31", "A", "AAA", 1, 1)])
        out = sitebuild.whales_payload(df, None, "live")
        assert [w["slug"] for w in out["whales"]] == ["berkshire"]

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

    def test_failed_whale_keeps_last_known(self, monkeypatch):
        # one whale fetches live, another fails -> the failed one is backfilled
        # from its last-known rows instead of vanishing.
        def fake_fetch(slug, cik):
            if slug == "berkshire":
                return pd.DataFrame([_row("berkshire", "2026-03-31", "A", "AAA", 1, 1)])
            raise ValueError("kill CIK")

        def fake_last_known(slug):
            return pd.DataFrame([_row(slug, "2025-12-31", "Z", "ZZZ", 2, 2)])

        monkeypatch.setattr(edgar, "_fetch_whale", fake_fetch)
        monkeypatch.setattr(edgar, "_last_known", fake_last_known)
        out = edgar.fetch_13f_holdings()
        whales = set(out["whale"].unique())
        assert "berkshire" in whales           # live
        assert "nps" in whales                 # backfilled last-known

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

    def test_summarize_and_update_history(self, tmp_path):
        df = pd.DataFrame([
            _row("berkshire", "2026-03-31", "A", "AAA", 60, 1),
            _row("berkshire", "2026-03-31", "B", "BBB", 40, 1),
            _row("berkshire", "2025-12-31", "A", "AAA", 50, 1),
        ])
        path = tmp_path / "hist.csv"
        merged = edgar.update_history(df, path=path)
        assert len(merged) == 2
        latest = merged[merged["quarter"] == "2026-03-31"].iloc[0]
        assert latest["total_value"] == 100
        assert latest["holdings_count"] == 2
        assert latest["top5_weight"] == 100.0

        # next snapshot: newer quarter arrives, older one rolls off the
        # snapshot but STAYS in history; same-quarter rows are replaced.
        df2 = pd.DataFrame([
            _row("berkshire", "2026-06-30", "A", "AAA", 70, 1),
            _row("berkshire", "2026-03-31", "A", "AAA", 65, 1),
        ])
        merged2 = edgar.update_history(df2, path=path)
        assert list(merged2["quarter"]) == ["2025-12-31", "2026-03-31", "2026-06-30"]
        assert merged2[merged2["quarter"] == "2026-03-31"]["total_value"].iloc[0] == 65

    def test_history_attached_to_payload(self):
        df = pd.DataFrame([_row("berkshire", "2026-03-31", "A", "AAA", 1, 1)])
        hist = pd.DataFrame([
            {"whale": "berkshire", "quarter": "2025-12-31", "filed": "f",
             "total_value": 90.0, "holdings_count": 3, "top5_weight": 80.0},
            {"whale": "berkshire", "quarter": "2026-03-31", "filed": "f",
             "total_value": 100.0, "holdings_count": 2, "top5_weight": 100.0},
        ])
        out = sitebuild.whales_payload(df, None, "live", history=hist)
        w = out["whales"][0]
        assert w["history"]["quarters"] == ["2025-12-31", "2026-03-31"]
        assert w["history"]["total_value"] == [90, 100]

    def test_put_call_suffix(self):
        df = pd.DataFrame([
            _row("scion", "2026-03-31", "X", "PUTCO", 9, 9, pc="Put"),
        ])
        out = sitebuild.whales_payload(df, None, "live")
        w = [x for x in out["whales"] if x["slug"] == "scion"][0]
        assert w["top"][0]["name"] == "PUTCO · 풋"
