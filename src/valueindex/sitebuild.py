"""Python→JSON bridge for the static site (docs/).

Everything the browser needs is produced here from the existing data and
math modules, so all Korean text, colors, and statistics stay
single-sourced in Python. `scripts/build_site_data.py` is the CLI wrapper;
the GitHub Actions workflow runs it daily after the data refresh.

No streamlit imports — this module is shared by the build script and
`webui.py`.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config, indicators, loader, quant, registry, stats

SCHEMA_VERSION = 1

# Decimal places per display unit (mirrors the Streamlit pages' FMT).
UNIT_DECIMALS = {
    "배": 1, "%": 2, "%p": 2, "비율": 2, "pt": 1, "$B": 1, "$/oz": 0, "$/bbl": 1,
}

# Chart chrome shared with charts.js (kept in sync with webui constants).
CHROME = {
    "grid": "#e1e0d9",
    "muted": "#898781",
    "recession_fill": "rgba(137, 135, 129, 0.15)",
    "plot_bg": "#ffffff",
    "ink": "#0b0b0b",
    "axis_line": "#c3c2b7",
}
# Dark-theme counterpart (site.css [data-theme=dark] palette).
CHROME_DARK = {
    "grid": "#3b3a35",
    "muted": "#8f8d85",
    "recession_fill": "rgba(200, 198, 190, 0.13)",
    "plot_bg": "#242320",
    "ink": "#ecebe7",
    "axis_line": "#55534c",
}

SERIES_COLORS = {
    "cape": "#2a78d6", "ecy": "#1baf7a", "buffett": "#eda100", "pe": "#008300",
    "pb": "#4a3aa7", "div_yield": "#e34948", "fed_spread": "#e87ba4",
    "trend_dev": "#eb6834", "aiae": "#0d9488",
    "vix": "#2a78d6", "t10y2y": "#4a3aa7", "hy_spread": "#e34948",
    "gold": "#eda100", "wti": "#008300",
    "fear_greed": "#2a78d6", "aaii_spread": "#4a3aa7", "margin_debt": "#e34948",
    "umcsent": "#008300",
    "fedfunds": "#2a78d6", "cpi_yoy": "#e34948", "unrate": "#eb6834",
    "m2_yoy": "#008300", "t10yie": "#4a3aa7",
}

DISCLAIMER = (
    "이 앱은 교육용 정보 도구이며 투자 자문이 아닙니다. "
    "모든 투자 판단과 책임은 본인에게 있습니다."
)


# ------------------------------------------------------------- shared build --

def yoy(level: pd.Series) -> pd.Series:
    """Year-over-year percent change of a monthly level series."""
    return (level / level.shift(12) - 1) * 100


def build_extras(frames: dict[str, pd.DataFrame]) -> dict:
    """Context series, real total-return index, recessions, daily closes.

    Shared by the Streamlit app (webui._load) and the static-site builder.
    """
    sh = frames["shiller"].set_index("date").sort_index()
    tri = indicators.real_total_return_index(
        sh["real_price"], sh["dividend"] / sh["cpi"] * sh["cpi"].iloc[-1]
    )
    return {
        "usrec": frames["fred_USREC"].set_index("date")["value"],
        "real_tri": tri,
        "spx_daily": frames["stooq_spx_daily"],
        "context": {
            "vix": indicators.to_monthly(frames["fred_VIXCLS"], how="mean"),
            "t10y2y": indicators.to_monthly(frames["fred_T10Y2Y"], how="mean"),
            "hy_spread": indicators.to_monthly(frames["fred_BAMLH0A0HYM2"], how="mean"),
            "gold": frames["stooq_gold"].set_index("date")["close"].resample("MS").mean(),
            "wti": indicators.to_monthly(frames["fred_DCOILWTICO"], how="mean"),
            "fear_greed": indicators.to_monthly(frames["cnn_fear_greed"], how="mean"),
            "aaii_spread": indicators.to_monthly(frames["aaii_sentiment"], how="mean"),
            "margin_debt": indicators.to_monthly(frames["finra_margin_debt"]),
            "umcsent": indicators.to_monthly(frames["fred_UMCSENT"]),
            "fedfunds": indicators.to_monthly(frames["fred_FEDFUNDS"]),
            "cpi_yoy": yoy(indicators.to_monthly(frames["fred_CPIAUCSL"])),
            "unrate": indicators.to_monthly(frames["fred_UNRATE"]),
            "m2_yoy": yoy(indicators.to_monthly(frames["fred_M2SL"])),
            "t10yie": indicators.to_monthly(frames["fred_T10YIE"], how="mean"),
        },
    }


# -------------------------------------------------------------- json helpers --

def _num(v):
    """Round to 6 significant digits; NaN/inf -> None (JSON null)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    if f == 0:
        return 0
    return float(f"{f:.6g}")


def _nums(values) -> list:
    return [_num(v) for v in values]


def _dates(idx) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in idx]


def _write(out_dir: Path, name: str, payload) -> None:
    path = out_dir / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )


def aligned_z_panel(panel: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            k: (stats.zscore(panel[k].dropna())
                * (1 if registry.INDICATORS[k].higher_is_expensive else -1))
            for k in registry.VALUATION_KEYS
        }
    )


# ------------------------------------------------------------ file builders --

def registry_payload() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "indicators": {k: asdict(m) for k, m in registry.INDICATORS.items()},
        "valuation_keys": registry.VALUATION_KEYS,
        "context_keys": registry.CONTEXT_KEYS,
        "ratings": [
            {"max_z": (None if upper == float("inf") else upper),
             "key": r.key, "label_ko": r.label_ko, "color": r.color}
            for upper, r in stats.RATINGS
        ],
        "series_colors": SERIES_COLORS,
        "chrome": CHROME,
        "chrome_dark": CHROME_DARK,
        "unit_decimals": UNIT_DECIMALS,
        "time_machine_presets": registry.TIME_MACHINE_PRESETS,
        "guide_lines": {k: list(v) for k, v in registry.GUIDE_LINES.items()},
        "disclaimer": DISCLAIMER,
    }


def panel_payload(panel: pd.DataFrame, tri: pd.Series) -> dict:
    tri_on_grid = tri.reindex(panel.index)
    return {
        "dates": _dates(panel.index),
        "series": {
            **{k: _nums(panel[k].values) for k in registry.VALUATION_KEYS},
            "real_tri": _nums(tri_on_grid.values),
        },
    }


def context_payload(context: dict[str, pd.Series]) -> dict:
    out = {}
    for key, s in context.items():
        s = s.dropna()
        out[key] = {"dates": _dates(s.index), "values": _nums(s.values)}
    return out


def _recession_ranges(usrec: pd.Series) -> list[list[str]]:
    s = usrec.sort_index()
    flag = s > 0
    edges = flag.astype(int).diff().fillna(0)
    starts = list(s.index[edges == 1])
    ends = list(s.index[edges == -1])
    if len(flag) and flag.iloc[0]:
        starts.insert(0, s.index[0])
    if len(ends) < len(starts):
        ends.append(s.index[-1])
    return [[a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")] for a, b in zip(starts, ends)]


def overview_payload(panel: pd.DataFrame, tri: pd.Series, usrec: pd.Series) -> dict:
    summaries = {}
    for key in registry.VALUATION_KEYS:
        s = panel[key].dropna()
        summ = stats.summary(s)
        meta = registry.INDICATORS[key]
        z = summ.z if meta.higher_is_expensive else -summ.z
        pct = summ.pctile if meta.higher_is_expensive else 100 - summ.pctile
        half_life = quant.ar1_half_life_months(s)
        summaries[key] = {
            "current": _num(summ.current), "asof": summ.asof.strftime("%Y-%m-%d"),
            "mean": _num(summ.mean), "std": _num(summ.std),
            "pctile": _num(summ.pctile), "z": _num(summ.z),
            "aligned_z": _num(z), "aligned_pctile": _num(pct),
            "rating": stats.rating(z).key,
            "delta_1y": _num(summ.delta_1y),
            "hist_min": _num(summ.hist_min), "hist_max": _num(summ.hist_max),
            "start_year": int(summ.start.year),
            "half_life_months": _num(half_life),
        }

    az = aligned_z_panel(panel)
    pca = quant.pca_composite(az)
    pca_now = float(pca.composite.iloc[-1])

    analogs = []
    for a in quant.nearest_analogs(az):
        cape_then = panel["cape"].asof(a.date)
        fwd = {}
        base = tri.asof(a.date)
        for label, months in (("1y", 12), ("5y", 60), ("10y", 120)):
            fut_idx = a.date + pd.DateOffset(months=months)
            fut = tri.asof(fut_idx) if fut_idx <= tri.index[-1] else None
            fwd[label] = (
                _num(((fut / base) ** (12 / months) - 1) * 100)
                if fut is not None and pd.notna(base) and base > 0 else None
            )
        seg = tri.loc[a.date: a.date + pd.DateOffset(months=120)].dropna()
        months_axis = [
            (d.year - a.date.year) * 12 + (d.month - a.date.month) for d in seg.index
        ]
        analogs.append({
            "date": a.date.strftime("%Y-%m-%d"),
            "distance": _num(a.distance),
            "cape_then": _num(cape_then),
            "fwd": fwd,
            "path_months": months_axis,
            "path_values": _nums((seg / seg.iloc[0] * 100).values) if len(seg) else [],
        })

    aligned_pct = pd.DataFrame(
        {
            k: (p if registry.INDICATORS[k].higher_is_expensive else 100 - p)
            for k in registry.VALUATION_KEYS
            for p in [stats.percentile_rank(panel[k].dropna())]
        }
    )
    corr = aligned_pct.corr()

    return {
        "latest_month": panel.dropna(how="all").index[-1].strftime("%Y-%m-%d"),
        "summaries": summaries,
        "pca": {
            "dates": _dates(pca.composite.index),
            "values": _nums(pca.composite.values),
            "weights": {k: _num(w) for k, w in pca.weights.items()},
            "explained_ratio": _num(pca.explained_ratio),
            "current": _num(pca_now),
            "rating": stats.rating(pca_now).key,
        },
        "analogs": analogs,
        "corr": {"keys": list(corr.columns), "matrix": [_nums(row) for row in corr.values]},
        "recessions": _recession_ranges(usrec),
    }


def guide_payload(panel: pd.DataFrame, tri: pd.Series) -> dict:
    fwd = indicators.forward_10y_return(tri)
    df = pd.DataFrame({"cape": panel["cape"], "fwd": fwd}).dropna()
    fan = quant.conditional_quantiles(df["cape"], df["fwd"])
    return {
        "scatter": {"cape": _nums(df["cape"].values), "fwd": _nums(df["fwd"].values)},
        "fan": {
            "x": _nums(fan.index.values),
            **{c: _nums(fan[c].values) for c in fan.columns},
        },
        "current_cape": _num(panel["cape"].dropna().iloc[-1]),
    }


def spx_payload(spx_daily: pd.DataFrame) -> dict:
    df = spx_daily.sort_values("date")
    return {"dates": _dates(df["date"]), "close": _nums(df["close"].values)}


def korea_payload(frames: dict[str, pd.DataFrame]) -> dict:
    """KOSPI index, KRX valuation (PER/PBR/div) with ratings, Korea Buffett
    approximation, KRW, and — when available — Korea 10Y.

    PER/PBR/dividend get direction-aligned sigma ratings against their own
    (short, 2004+) history, flagged as low-confidence in the UI.
    """
    krx = frames["krx_valuation"].set_index("date").sort_index()
    kospi = frames["stooq_kospi_daily"].set_index("date").sort_index()["close"]

    out = {
        "kospi": {"dates": _dates(kospi.index), "values": _nums(kospi.values)},
        "indicators": {},
        "start_year": int(krx.index[0].year),
    }

    # KOSPI PER / PBR / dividend yield: monthly, own-history rating.
    higher_expensive = {"per": True, "pbr": True, "div_yield": False}
    labels = {"per": "KOSPI PER", "pbr": "KOSPI PBR", "div_yield": "KOSPI 배당수익률"}
    units = {"per": "배", "pbr": "배", "div_yield": "%"}
    for col in ("per", "pbr", "div_yield"):
        s = indicators.to_monthly(
            krx[col].reset_index().rename(columns={col: "value"})[["date", "value"]]
        ).dropna()
        if s.empty:
            continue
        summ = stats.summary(s)
        z = summ.z if higher_expensive[col] else -summ.z
        out["indicators"][col] = {
            "label_ko": labels[col], "unit": units[col],
            "higher_is_expensive": higher_expensive[col],
            "dates": _dates(s.index), "values": _nums(s.values),
            "current": _num(summ.current), "asof": summ.asof.strftime("%Y-%m-%d"),
            "mean": _num(summ.mean),
            "aligned_z": _num(z), "rating": stats.rating(z).key,
            "aligned_pctile": _num(summ.pctile if higher_expensive[col]
                                   else 100 - summ.pctile),
            "start_year": int(summ.start.year),
        }

    # Korea Buffett indicator (approx): KOSPI market cap proxy not directly
    # available free; approximate the *ratio's shape* is out of scope, so we
    # ship KRW and GDP for context and label Buffett as unavailable-precise.
    krw = indicators.to_monthly(frames["fred_DEXKOUS"], how="mean").dropna()
    out["krw"] = {"dates": _dates(krw.index), "values": _nums(krw.values)}

    if "fred_IRLTLT01KRM156N" in frames:
        y10 = indicators.to_monthly(frames["fred_IRLTLT01KRM156N"]).dropna()
        if len(y10):
            out["kr_10y"] = {"dates": _dates(y10.index), "values": _nums(y10.values)}

    # US comparison values for the side-by-side view.
    return out


def _wname(row) -> str:
    nm = str(row["name"])
    pc = str(row.get("put_call") or "").lower()
    if pc == "put":
        return nm + " · 풋"
    if pc == "call":
        return nm + " · 콜"
    return nm


def _agg_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """Sum a whale's rows for one quarter by (cusip, put_call)."""
    df = df.copy()
    for c in ("cusip", "name", "class", "put_call"):
        df[c] = df[c].fillna("")
    g = df.groupby(["cusip", "put_call"], as_index=False, dropna=False).agg(
        name=("name", "first"), cls=("class", "first"),
        value_usd=("value_usd", "sum"), shares=("shares", "sum"))
    return g.sort_values("value_usd", ascending=False).reset_index(drop=True)


def _one_whale(slug: str, meta: dict, wdf: pd.DataFrame, status: str) -> dict | None:
    quarters = sorted(wdf["quarter"].dropna().astype(str).unique(), reverse=True)
    if not quarters:
        return None
    latest_q = quarters[0]
    prior_q = quarters[1] if len(quarters) > 1 else None
    lat = _agg_quarter(wdf[wdf["quarter"].astype(str) == latest_q])
    pri = _agg_quarter(wdf[wdf["quarter"].astype(str) == prior_q]) if prior_q else None
    total = float(lat["value_usd"].sum())

    pri_shares, pri_val = {}, {}
    if pri is not None:
        for _, r in pri.iterrows():
            pri_shares[(r["cusip"], r["put_call"])] = r["shares"]
            pri_val[(r["cusip"], r["put_call"])] = r["value_usd"]
    lat_keys = set(zip(lat["cusip"], lat["put_call"]))
    pri_keys = set(pri_shares)

    # Disambiguate issuer names that map to more than one security within this
    # whale (e.g. two different iShares ETFs both named "ISHARES TR") by
    # appending the class — otherwise the chart's categorical y-axis collapses
    # them onto one row.
    keyrows = {}
    for df in (pri, lat):  # lat wins on overlap
        if df is not None:
            for _, r in df.iterrows():
                keyrows[(r["cusip"], r["put_call"])] = r
    from collections import Counter
    name_counts = Counter(_wname(r) for r in keyrows.values())
    dname = {}
    for key, r in keyrows.items():
        nm = _wname(r)
        if name_counts[nm] > 1 and r["cls"]:
            nm = f"{nm} ({r['cls']})"
        dname[key] = nm

    top = []
    for _, r in lat.head(12).iterrows():
        key = (r["cusip"], r["put_call"])
        prev = pri_shares.get(key)
        if prev is None or pd.isna(prev):
            kind, chg_pct = ("new" if pri is not None else "flat"), None
        elif r["shares"] > prev * 1.001:
            kind, chg_pct = "up", (r["shares"] / prev - 1) * 100 if prev else None
        elif r["shares"] < prev * 0.999:
            kind, chg_pct = "down", (r["shares"] / prev - 1) * 100 if prev else None
        else:
            kind, chg_pct = "flat", 0.0
        top.append({
            "name": dname[key], "cusip": r["cusip"], "class": r["cls"],
            "value": _num(r["value_usd"]),
            "weight": _num(r["value_usd"] / total * 100 if total else None),
            "shares": _num(r["shares"]), "chg_kind": kind, "chg_pct": _num(chg_pct),
        })

    changes = {"new": [], "exited": [], "increased": [], "decreased": []}
    if pri is not None:
        for _, r in lat.iterrows():
            key = (r["cusip"], r["put_call"])
            if key not in pri_keys:
                changes["new"].append(dname[key])
        for _, r in pri.iterrows():
            key = (r["cusip"], r["put_call"])
            if key not in lat_keys:
                changes["exited"].append(dname[key])
        moves = []
        for _, r in lat.iterrows():
            key = (r["cusip"], r["put_call"])
            prev = pri_shares.get(key)
            if prev is None or pd.isna(prev) or not prev:
                continue
            dv = abs(float(r["value_usd"]) - float(pri_val.get(key, 0)))
            if r["shares"] > prev * 1.02:
                moves.append(("increased", dname[key], dv))
            elif r["shares"] < prev * 0.98:
                moves.append(("decreased", dname[key], dv))
        moves.sort(key=lambda t: -t[2])
        for kind, nm, _ in moves:
            changes[kind].append(nm)
    changes = {k: v[:8] for k, v in changes.items()}

    latest_rows = wdf[wdf["quarter"].astype(str) == latest_q]
    return {
        "slug": slug, "name_ko": meta["name_ko"], "region": meta["region"],
        "note": meta["note"], "as_of": latest_q, "prior_quarter": prior_q,
        "filed": str(latest_rows["filed"].max()) if "filed" in wdf else None,
        "total_value": _num(total), "holdings_count": int(len(lat)),
        "top5_weight": _num(lat.head(5)["value_usd"].sum() / total * 100 if total else None),
        "status": status, "top": top, "changes": changes,
    }


def whales_payload(edf: pd.DataFrame | None, sample_edf: pd.DataFrame | None,
                   status: str, history: pd.DataFrame | None = None) -> dict:
    """Per-whale 13F snapshot with quarter-over-quarter changes. Whales missing
    from the loaded frame (e.g. a kill CIK) are backfilled from the sample so
    every configured whale always renders. `history` (cumulative per-quarter
    summaries) becomes each whale's size/concentration trend."""
    present = set(edf["whale"].unique()) if edf is not None and len(edf) else set()
    sample_present = (set(sample_edf["whale"].unique())
                      if sample_edf is not None and len(sample_edf) else set())
    whales = []
    for slug, meta in config.WHALES.items():
        if slug in present:
            wdf, st = edf[edf["whale"] == slug], status
        elif slug in sample_present:
            wdf, st = sample_edf[sample_edf["whale"] == slug], "sample"
        else:
            continue
        w = _one_whale(slug, meta, wdf, st)
        if w:
            if history is not None and len(history):
                h = (history[history["whale"] == slug]
                     .sort_values("quarter"))
                if len(h):
                    w["history"] = {
                        "quarters": [str(q) for q in h["quarter"]],
                        "total_value": _nums(h["total_value"].values),
                        "top5_weight": _nums(h["top5_weight"].values),
                        "holdings_count": [int(c) for c in h["holdings_count"]],
                    }
            whales.append(w)
    return {"whales": whales,
            "generated_quarter": whales[0]["as_of"] if whales else None}


REPORT_MACRO_KEYS = ["fedfunds", "cpi_yoy", "unrate", "vix", "hy_spread"]


def report_payload(panel: pd.DataFrame, overview: dict, context: dict,
                   whales_doc: dict) -> dict:
    """The monthly check-in digest: what changed over the last month.

    Everything is derived from the already-built series (no stored state):
    each indicator's sigma rating now vs one month ago, the composite's move,
    a month-over-month macro snapshot, and 13F filings from the last 45 days.
    """
    now_idx = panel.dropna(how="all").index[-1]
    prev_idx = now_idx - pd.DateOffset(months=1)

    ratings, any_change = [], False
    for key in registry.VALUATION_KEYS:
        if key not in panel:
            continue
        s = panel[key].dropna()
        if s.empty:
            continue
        summ = stats.summary(s)
        sign = 1 if registry.INDICATORS[key].higher_is_expensive else -1
        z_now = sign * summ.z
        v_prev = s.asof(prev_idx)
        z_prev = (sign * (v_prev - summ.mean) / summ.std
                  if pd.notna(v_prev) and summ.std else None)
        r_now = stats.rating(z_now).key
        r_prev = stats.rating(z_prev).key if z_prev is not None else r_now
        changed = r_now != r_prev
        any_change = any_change or changed
        ratings.append({
            "key": key, "rating_now": r_now, "rating_prev": r_prev,
            "changed": changed, "value_now": _num(summ.current),
            "z_now": _num(z_now), "z_prev": _num(z_prev),
        })

    pca = overview["pca"]
    prev_str = prev_idx.strftime("%Y-%m-%d")
    prev_pos = max((i for i, d in enumerate(pca["dates"]) if d <= prev_str),
                   default=None)
    comp_prev = pca["values"][prev_pos] if prev_pos is not None else None
    composite = {
        "now": pca["current"], "prev": _num(comp_prev),
        "rating_now": pca["rating"],
        "rating_prev": (stats.rating(comp_prev).key
                        if comp_prev is not None else pca["rating"]),
    }

    macro = []
    for key in REPORT_MACRO_KEYS:
        s = context.get(key)
        if s is None or s.dropna().empty:
            continue
        s = s.dropna()
        v_prev = s.asof(s.index[-1] - pd.DateOffset(months=1))
        macro.append({"key": key, "now": _num(s.iloc[-1]), "prev": _num(v_prev)})

    cutoff = (datetime.now(timezone.utc) - pd.Timedelta(days=45)).strftime("%Y-%m-%d")
    filings = [
        {"name_ko": w["name_ko"], "as_of": w["as_of"], "filed": w.get("filed")}
        for w in whales_doc.get("whales", [])
        if w.get("filed") and w["filed"] >= cutoff
    ]

    return {
        "month_now": now_idx.strftime("%Y-%m"),
        "month_prev": prev_idx.strftime("%Y-%m"),
        "ratings": ratings,
        "any_rating_change": any_change,
        "composite": composite,
        "macro": macro,
        "whale_filings": filings,
    }


def content_payload() -> dict:
    import markdown

    out = {}
    for name in ("investing_guide_ko", "discipline_ko", "resources_ko"):
        text = (config.CONTENT_DIR / f"{name}.md").read_text(encoding="utf-8")
        out[name] = markdown.markdown(text, extensions=["tables"])
    return out


def meta_payload(statuses: dict[str, str], panel: pd.DataFrame) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latest_month": panel.dropna(how="all").index[-1].strftime("%Y-%m-%d"),
        "sources": statuses,
    }


# --------------------------------------------------------------- orchestrator --

def build_site(out_dir: Path, force: bool = False) -> dict[str, str]:
    """Build every docs/data file. Returns per-source statuses."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = loader.load_all(force=force)
    frames = {k: v[0] for k, v in data.items()}
    statuses = {k: v[1].value for k, v in data.items()}

    panel = indicators.build_panel(frames)
    extras = build_extras(frames)
    tri, usrec = extras["real_tri"], extras["usrec"]

    overview = overview_payload(panel, tri, usrec)

    _write(out_dir, "meta.json", meta_payload(statuses, panel))
    _write(out_dir, "registry.json", registry_payload())
    _write(out_dir, "panel.json", panel_payload(panel, tri))
    _write(out_dir, "context.json", context_payload(extras["context"]))
    _write(out_dir, "overview.json", overview)
    _write(out_dir, "guide.json", guide_payload(panel, tri))
    _write(out_dir, "spx_daily.json", spx_payload(extras["spx_daily"]))
    try:
        _write(out_dir, "korea.json", korea_payload(frames))
    except Exception:  # noqa: BLE001 - Korea data is optional; page degrades
        _write(out_dir, "korea.json", {"kospi": {"dates": [], "values": []},
                                       "indicators": {}, "unavailable": True})
    try:
        hist_path = config.SAMPLE_DATA_DIR / "edgar_whale_history.csv"
        history = pd.read_csv(hist_path) if hist_path.exists() else None
        whales_doc = whales_payload(
            frames.get("edgar_whales"), loader._load_sample("edgar_whales"),
            statuses.get("edgar_whales", "sample"), history=history)
    except Exception:  # noqa: BLE001 - whale tracker is optional; page degrades
        whales_doc = {"whales": [], "unavailable": True}
    _write(out_dir, "whales.json", whales_doc)
    _write(out_dir, "report.json",
           report_payload(panel, overview, extras["context"], whales_doc))
    _write(out_dir, "content.json", content_payload())
    panel.to_csv(out_dir / "valueindex_panel.csv")
    return statuses
