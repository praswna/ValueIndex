"""Static-site data pipeline: schema, rounding, and completeness."""
import json
import math

import pytest

from valueindex import config, registry, sitebuild


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("sitedata")
    prev = config.OFFLINE
    config.OFFLINE = True
    try:
        statuses = sitebuild.build_site(out)
    finally:
        config.OFFLINE = prev
    return out, statuses


def load(out, name):
    return json.loads((out / name).read_text(encoding="utf-8"))


class TestBuildSite:
    def test_all_files_written(self, built):
        out, _ = built
        expected = {
            "meta.json", "registry.json", "panel.json", "context.json",
            "overview.json", "guide.json", "spx_daily.json", "korea.json",
            "content.json", "valueindex_panel.csv",
        }
        assert expected <= {p.name for p in out.iterdir()}

    def test_korea_payload(self, built):
        out, _ = built
        k = load(out, "korea.json")
        assert len(k["kospi"]["dates"]) == len(k["kospi"]["values"]) > 100
        rating_keys = {r.key for _, r in
                       __import__("valueindex.stats", fromlist=["RATINGS"]).RATINGS}
        for key, v in k["indicators"].items():
            assert v["rating"] in rating_keys
            assert len(v["dates"]) == len(v["values"])
            assert v["start_year"] >= 2004
        assert "krw" in k

    def test_panel_grid_consistent(self, built):
        out, _ = built
        panel = load(out, "panel.json")
        n = len(panel["dates"])
        assert n > 1500
        for key, values in panel["series"].items():
            assert len(values) == n, key
        assert set(registry.VALUATION_KEYS) <= set(panel["series"])
        assert "real_tri" in panel["series"]

    def test_nan_becomes_null_and_rounding(self, built):
        out, _ = built
        panel = load(out, "panel.json")
        pb = panel["series"]["pb"]
        assert pb[0] is None  # pb starts in 2000; 1871 is null
        # 6 significant digits max
        for v in panel["series"]["cape"]:
            if v is not None:
                assert len(f"{v:.10g}".replace(".", "").replace("-", "").lstrip("0")) <= 6

    def test_overview_schema(self, built):
        out, _ = built
        ov = load(out, "overview.json")
        rating_keys = {r.key for _, r in __import__("valueindex.stats", fromlist=["RATINGS"]).RATINGS}
        for key in registry.VALUATION_KEYS:
            s = ov["summaries"][key]
            assert s["rating"] in rating_keys
            assert 0 <= s["aligned_pctile"] <= 100
        assert 0 < ov["pca"]["explained_ratio"] <= 1
        assert len(ov["analogs"]) >= 1
        assert len(ov["corr"]["matrix"]) == len(registry.VALUATION_KEYS)
        for start, end in ov["recessions"]:
            assert start < end

    def test_registry_payload_complete(self, built):
        out, _ = built
        reg = load(out, "registry.json")
        assert set(reg["indicators"]) == set(registry.INDICATORS)
        assert reg["valuation_keys"] == registry.VALUATION_KEYS
        assert len(reg["ratings"]) == 5
        assert reg["ratings"][-1]["max_z"] is None  # top band unbounded
        # Korean text made it through as UTF-8
        assert "고평가" in json.dumps(reg, ensure_ascii=False)

    def test_context_and_guide(self, built):
        out, _ = built
        ctx = load(out, "context.json")
        assert set(registry.CONTEXT_KEYS) <= set(ctx)
        for key, s in ctx.items():
            assert len(s["dates"]) == len(s["values"])
        guide = load(out, "guide.json")
        assert len(guide["scatter"]["cape"]) == len(guide["scatter"]["fwd"])
        assert guide["current_cape"] > 5
        assert len(guide["fan"]["x"]) == len(guide["fan"]["q50"])

    def test_meta(self, built):
        out, statuses = built
        meta = load(out, "meta.json")
        assert meta["schema_version"] == sitebuild.SCHEMA_VERSION
        assert meta["sources"] == statuses
        assert meta["generated_at"].endswith("Z")


class TestNumRounding:
    def test_num_helper(self):
        assert sitebuild._num(float("nan")) is None
        assert sitebuild._num(None) is None
        assert sitebuild._num(math.inf) is None
        assert sitebuild._num(0) == 0
        assert sitebuild._num(1.23456789) == 1.23457
        assert sitebuild._num(-0.000123456789) == -0.000123457
