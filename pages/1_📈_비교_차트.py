"""지표 비교 차트: 여러 밸류에이션 지표를 겹쳐 보기."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from valueindex import registry, stats, webui

st.set_page_config(page_title="비교 차트", page_icon="📈", layout="wide")
panel, statuses, extras = webui.get_data()
webui.sidebar(statuses)

st.title("📈 지표 비교 차트")

labels = {registry.INDICATORS[k].label_ko: k for k in registry.VALUATION_KEYS}
selected_labels = st.multiselect(
    "비교할 지표 (최대 4개 권장 — 많을수록 읽기 어려워집니다)",
    options=list(labels),
    default=[registry.INDICATORS[k].label_ko for k in ("cape", "buffett", "pe")],
    max_selections=4,
)
selected = [labels[l] for l in selected_labels]

col1, col2, col3 = st.columns([2, 2, 1])
norm = col1.radio(
    "표시 방식", ["Z-점수", "백분위", "원값"], horizontal=True,
    help="지표마다 단위가 달라(배, %, 비율) 그대로 겹치면 비교가 안 됩니다. "
    "Z-점수는 '역사 평균에서 몇 σ 떨어졌나', 백분위는 '역사상 몇 % 위치인가'로 "
    "단위를 통일하는 표준화입니다.",
)
years = sorted({d.year for d in panel.index})
yr_range = col2.select_slider(
    "기간", options=years, value=(max(years[0], 1950), years[-1])
)
show_rec = col3.checkbox("경기침체 음영", value=True,
                         help="회색 음영 = NBER 공식 경기침체 구간")

start = pd.Timestamp(f"{yr_range[0]}-01-01")
end = pd.Timestamp(f"{yr_range[1]}-12-31")

if not selected:
    st.info("지표를 하나 이상 선택하세요.")
    st.stop()

view = panel.loc[start:end, selected]

if norm == "원값":
    # Units differ -> one small multiple per indicator, never a dual axis.
    fig = make_subplots(
        rows=len(selected), cols=1, shared_xaxes=True, vertical_spacing=0.06,
        subplot_titles=[
            f"{registry.INDICATORS[k].label_ko} ({registry.INDICATORS[k].unit})"
            for k in selected
        ],
    )
    for i, key in enumerate(selected, start=1):
        s = view[key].dropna()
        fig.add_trace(webui.line_trace(s, key), row=i, col=1)
        fig.update_yaxes(gridcolor=webui.GRID, row=i, col=1)
        fig.update_xaxes(showgrid=False, row=i, col=1)
    fig.update_layout(showlegend=False)
    webui.base_layout(fig, height=220 * len(selected))
else:
    fig = go.Figure()
    for key in selected:
        s = view[key].dropna()
        if norm == "Z-점수":
            s = stats.zscore(panel[key].dropna()).loc[start:end]
        else:
            s = stats.percentile_rank(panel[key].dropna()).loc[start:end]
        fig.add_trace(webui.line_trace(s, key))
    ytitle = "z-score (전체 역사 기준)" if norm == "Z-점수" else "백분위 (전체 역사 기준)"
    fig.update_layout(yaxis_title=ytitle)
    if norm == "Z-점수":
        for level, dash in ((0, "solid"), (1, "dot"), (-1, "dot"), (2, "dash"), (-2, "dash")):
            fig.add_hline(y=level, line_color=webui.MUTED, line_width=1, line_dash=dash,
                          opacity=0.5)
    webui.base_layout(fig, height=480)

if show_rec:
    webui.add_recession_shading(fig, extras["usrec"], start=start)
st.plotly_chart(fig, width="stretch")

if norm != "원값":
    st.caption(
        "주의: Z-점수/백분위는 **방향을 정렬하지 않은 원지표 기준**입니다. "
        "ECY·배당수익률·Fed 스프레드는 값이 **낮을수록** 고평가입니다."
    )

# ----------------------------------------------------------- correlation heatmap
st.subheader("지표 상관관계")
st.caption(
    "방향을 정렬한(높을수록 고평가) 백분위끼리의 상관계수입니다. "
    "밸류에이션 지표들은 서로 상관이 높습니다 — **지표를 늘려도 정보가 비례해 "
    "늘지 않는 이유**이자, 여러 지표가 같은 방향을 가리킬 때 신뢰가 커지는 이유입니다."
)
aligned = pd.DataFrame(
    {
        registry.INDICATORS[k].label_ko: (
            p if registry.INDICATORS[k].higher_is_expensive else 100 - p
        )
        for k in registry.VALUATION_KEYS
        for p in [stats.percentile_rank(panel[k].dropna())]
    }
)
corr = aligned.corr().round(2)
heat = go.Figure(
    go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.columns,
        zmin=-1, zmax=1,
        colorscale=[[0.0, "#1c5cab"], [0.5, "#f0efec"], [1.0, "#c22f2f"]],
        text=corr.values,
        texttemplate="%{text:.2f}",
        hovertemplate="%{y} × %{x}: %{z:.2f}<extra></extra>",
        colorbar=dict(title="상관"),
    )
)
webui.base_layout(heat, height=520)
heat.update_layout(hovermode="closest", yaxis=dict(autorange="reversed"))
st.plotly_chart(heat, width="stretch")
st.caption(webui.DISCLAIMER)
