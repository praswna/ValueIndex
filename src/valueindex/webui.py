"""Shared Streamlit helpers: cached data bootstrap, colors, chart chrome."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import cache, config, indicators, loader, registry, stats

# Fixed color per indicator key (validated categorical palette; identity
# follows the entity, never the selection order).
SERIES_COLORS = {
    "cape": "#2a78d6",
    "ecy": "#1baf7a",
    "buffett": "#eda100",
    "pe": "#008300",
    "pb": "#4a3aa7",
    "div_yield": "#e34948",
    "fed_spread": "#e87ba4",
    "trend_dev": "#eb6834",
    "aiae": "#0d9488",
    # context indicators reuse the same slots (never plotted together
    # with valuation series)
    "vix": "#2a78d6",
    "t10y2y": "#4a3aa7",
    "hy_spread": "#e34948",
    "gold": "#eda100",
    "wti": "#008300",
}

GRID = "#e1e0d9"
MUTED = "#898781"
RECESSION_FILL = "rgba(137, 135, 129, 0.15)"

STATUS_LABELS = {
    loader.DataStatus.LIVE: "🟢 실시간",
    loader.DataStatus.CACHED: "🔵 캐시",
    loader.DataStatus.STALE_CACHE: "🟡 오래된 캐시",
    loader.DataStatus.SAMPLE: "⚪ 샘플 데이터",
}

DISCLAIMER = (
    "이 앱은 교육용 정보 도구이며 투자 자문이 아닙니다. "
    "모든 투자 판단과 책임은 본인에게 있습니다."
)


@st.cache_data(ttl=3600, show_spinner="데이터를 불러오는 중...")
def _load(force: bool = False):
    data = loader.load_all(force=force)
    frames = {k: v[0] for k, v in data.items()}
    statuses = {k: v[1].value for k, v in data.items()}
    panel = indicators.build_panel(frames)

    sh = frames["shiller"].set_index("date").sort_index()
    tri = indicators.real_total_return_index(sh["real_price"], sh["dividend"] / sh["cpi"] * sh["cpi"].iloc[-1])
    extras = {
        "usrec": frames["fred_USREC"].set_index("date")["value"],
        "real_tri": tri,
        "spx_daily": frames["stooq_spx_daily"],
        "context": {
            "vix": indicators.to_monthly(frames["fred_VIXCLS"], how="mean"),
            "t10y2y": indicators.to_monthly(frames["fred_T10Y2Y"], how="mean"),
            "hy_spread": indicators.to_monthly(frames["fred_BAMLH0A0HYM2"], how="mean"),
            "gold": frames["stooq_gold"].set_index("date")["close"].resample("MS").mean(),
            "wti": indicators.to_monthly(frames["fred_DCOILWTICO"], how="mean"),
        },
    }
    return panel, statuses, extras


def get_data():
    force = st.session_state.pop("force_refresh", False)
    if force:
        _load.clear()
    return _load(force=force)


def aligned_z(key: str, z: float) -> float:
    """Flip sign so that positive z always means expensive."""
    return z if registry.INDICATORS[key].higher_is_expensive else -z


def aligned_pctile(key: str, pctile: float) -> float:
    return pctile if registry.INDICATORS[key].higher_is_expensive else 100 - pctile


def rating_badge(r: stats.Rating) -> str:
    return (
        f'<span style="background:{r.color};color:#ffffff;padding:2px 10px;'
        f'border-radius:10px;font-size:0.85rem;white-space:nowrap">{r.label_ko}</span>'
    )


def sidebar(statuses: dict[str, str]) -> None:
    with st.sidebar:
        st.markdown("### 데이터 상태")
        by_status: dict[str, list[str]] = {}
        for name, status in statuses.items():
            by_status.setdefault(status, []).append(name)
        for status, names in sorted(by_status.items()):
            label = STATUS_LABELS[loader.DataStatus(status)]
            st.markdown(f"{label} — {len(names)}개 소스")
        if any(s == "sample" for s in statuses.values()):
            st.caption(
                "⚪ 샘플 데이터는 실제 역사적 기준값 사이를 보간한 근사치입니다. "
                "인터넷 연결 후 새로고침하면 실제 데이터로 바뀝니다."
            )
        newest = None
        for name in statuses:
            ci = cache.info(name)
            if ci and (newest is None or ci.fetched_at > newest):
                newest = ci.fetched_at
        if newest is not None:
            st.caption(f"마지막 수집: {newest:%Y-%m-%d %H:%M} UTC")
        if st.button("🔄 데이터 새로고침", use_container_width=True):
            st.session_state["force_refresh"] = True
            st.rerun()
        if config.OFFLINE:
            st.caption("오프라인 모드 (VALUEINDEX_OFFLINE=1)")
        st.divider()
        st.caption(DISCLAIMER)


def base_layout(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="#ffffff",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, sans-serif", color="#0b0b0b"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(showgrid=False, linecolor="#c3c2b7", ticks="outside", tickcolor=GRID),
        yaxis=dict(gridcolor=GRID, zerolinecolor="#c3c2b7", linecolor="rgba(0,0,0,0)"),
    )
    return fig


def add_recession_shading(fig: go.Figure, usrec: pd.Series,
                          start: pd.Timestamp | None = None) -> go.Figure:
    s = usrec.sort_index()
    if start is not None:
        s = s.loc[start:]
    flag = s > 0
    edges = flag.astype(int).diff().fillna(0)
    starts = list(s.index[edges == 1])
    ends = list(s.index[edges == -1])
    if flag.iloc[0]:
        starts.insert(0, s.index[0])
    if len(ends) < len(starts):
        ends.append(s.index[-1])
    for x0, x1 in zip(starts, ends):
        fig.add_vrect(x0=x0, x1=x1, fillcolor=RECESSION_FILL, line_width=0, layer="below")
    return fig


def line_trace(s: pd.Series, key: str, name: str | None = None) -> go.Scatter:
    return go.Scatter(
        x=s.index,
        y=s.values,
        mode="lines",
        name=name or registry.INDICATORS[key].label_ko,
        line=dict(color=SERIES_COLORS.get(key, "#2a78d6"), width=2),
    )
