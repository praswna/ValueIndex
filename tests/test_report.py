"""Monthly report payload + rating-change alert diffing."""
import numpy as np
import pandas as pd

from valueindex import alerts, sitebuild


def _panel():
    idx = pd.date_range("2000-01-01", periods=200, freq="MS")
    rng = np.random.default_rng(7)
    base = pd.Series(20 + rng.normal(0, 1, 200).cumsum() * 0.1, index=idx)
    # jump in the final month so now-vs-prev differs
    cape = base.copy()
    cape.iloc[-1] = cape.iloc[-2] + 8
    return pd.DataFrame({"cape": cape})


def _overview():
    dates = [d.strftime("%Y-%m-%d")
             for d in pd.date_range("2000-01-01", periods=200, freq="MS")]
    values = list(np.linspace(-1, 2.6, 200))
    return {"pca": {"dates": dates, "values": values,
                    "current": values[-1], "rating": "very_expensive"}}


class TestReportPayload:
    def test_shape_and_change_detection(self):
        ctx = {"fedfunds": pd.Series(
            [4.0] * 23 + [4.5],
            index=pd.date_range("2024-01-01", periods=24, freq="MS"))}
        whales = {"whales": [
            {"name_ko": "테스트", "as_of": "2026-03-31",
             "filed": pd.Timestamp.now("UTC").strftime("%Y-%m-%d")},
            {"name_ko": "옛날", "as_of": "2020-03-31", "filed": "2020-05-15"},
        ]}
        out = sitebuild.report_payload(_panel(), _overview(), ctx, whales)

        assert out["month_now"] > out["month_prev"]
        cape = [r for r in out["ratings"] if r["key"] == "cape"][0]
        assert cape["z_now"] > cape["z_prev"]          # the engineered jump
        assert out["composite"]["rating_now"] == "very_expensive"
        assert out["macro"][0]["key"] == "fedfunds"
        assert out["macro"][0]["now"] == 4.5
        assert out["macro"][0]["prev"] == 4.0
        # only the recent filing survives the 45-day window
        assert [f["name_ko"] for f in out["whale_filings"]] == ["테스트"]

    def test_missing_panel_key_skipped(self):
        out = sitebuild.report_payload(_panel(), _overview(), {}, {"whales": []})
        assert {r["key"] for r in out["ratings"]} == {"cape"}


class TestAlerts:
    def _overview(self, cape_rating, pca_rating):
        return {"summaries": {"cape": {"rating": cape_rating}},
                "pca": {"rating": pca_rating}}

    def test_no_change_no_lines(self):
        o = self._overview("expensive", "expensive")
        assert alerts.diff_overview(o, o) == []

    def test_band_change_produces_korean_line(self):
        old = self._overview("expensive", "expensive")
        new = self._overview("very_expensive", "expensive")
        lines = alerts.diff_overview(old, new)
        assert len(lines) == 1
        assert "CAPE" in lines[0] or "cape" in lines[0]

    def test_pca_change_leads(self):
        old = self._overview("expensive", "expensive")
        new = self._overview("very_expensive", "very_expensive")
        lines = alerts.diff_overview(old, new)
        assert len(lines) == 2
        assert "종합" in lines[0]

    def test_issue_body_mentions_discipline(self):
        body = alerts.issue_body(["- x"])
        assert "report.html" in body and "discipline.html" in body
