"""지표 상세: 지표 하나의 전체 히스토리와 분포."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import plotly.graph_objects as go
import streamlit as st

from valueindex import quant, registry, stats, webui

st.set_page_config(page_title="지표 상세", page_icon="🔍", layout="wide")
panel, statuses, extras = webui.get_data()
webui.sidebar(statuses)

st.title("🔍 지표 상세")

labels = {registry.INDICATORS[k].label_ko: k for k in registry.VALUATION_KEYS}
key = labels[st.selectbox("지표 선택", list(labels))]
meta = registry.INDICATORS[key]

s = panel[key].dropna()
summ = stats.summary(s)
z = webui.aligned_z(key, summ.z)
rating = stats.rating(z)

badge = webui.rating_badge(rating)
direction = "높을수록 고평가" if meta.higher_is_expensive else "**낮을수록** 고평가"
st.markdown(
    f"### {meta.label_ko} &nbsp; {badge}",
    unsafe_allow_html=True,
)
st.caption(f"{meta.what_ko} ({direction} · 출처: {meta.source})")

half_life = quant.ar1_half_life_months(s)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("현재값", f"{summ.current:,.2f} {meta.unit}", help=f"기준: {summ.asof:%Y-%m}")
c2.metric("역사 평균", f"{summ.mean:,.2f}")
c3.metric("고평가 백분위", f"{webui.aligned_pctile(key, summ.pctile):.0f} / 100")
c4.metric("z-score (방향 정렬)", f"{z:+.2f}σ")
c5.metric(
    "평균회귀 반감기",
    f"약 {half_life / 12:.1f}년" if half_life else "회귀 성향 약함",
    help="AR(1) 확률과정 적합으로 추정한, 평균에서의 이탈이 절반으로 줄어드는 데 "
    "걸리는 기대 시간입니다. 수년 단위라는 것이 핵심 — 고평가/저평가 상태는 "
    "몇 달이 아니라 몇 년씩 지속되는 경향이 있습니다. (근사 추정치입니다)",
)

# ------------------------------------------------------------- history + bands
band = stats.bands(s)
fig = go.Figure()
# +-2 sigma band fill, then +-1 sigma, then the series on top.
fig.add_trace(go.Scatter(x=band.index, y=band["plus2"], mode="lines",
                         line=dict(width=0), showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scatter(x=band.index, y=band["minus2"], mode="lines", fill="tonexty",
                         fillcolor="rgba(137,135,129,0.10)", line=dict(width=0),
                         name="±2σ", hoverinfo="skip"))
fig.add_trace(go.Scatter(x=band.index, y=band["plus1"], mode="lines",
                         line=dict(width=0), showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scatter(x=band.index, y=band["minus1"], mode="lines", fill="tonexty",
                         fillcolor="rgba(137,135,129,0.14)", line=dict(width=0),
                         name="±1σ", hoverinfo="skip"))
fig.add_trace(go.Scatter(x=band.index, y=band["mean"], mode="lines", name="역사 평균",
                         line=dict(color=webui.MUTED, width=1, dash="dash")))
fig.add_trace(webui.line_trace(s, key))
fig.add_trace(go.Scatter(x=[s.index[-1]], y=[s.iloc[-1]], mode="markers",
                         marker=dict(color=rating.color, size=10), name="현재",
                         hovertemplate=f"현재: %{{y:.2f}}<extra></extra>"))
fig.update_layout(yaxis_title=f"{meta.label_ko} ({meta.unit})")
webui.base_layout(fig, height=460)
webui.add_recession_shading(fig, extras["usrec"], start=s.index[0])
st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------- histogram
st.subheader("역사적 분포에서 현재 위치")
hist = go.Figure(
    go.Histogram(x=s.values, nbinsx=60, marker=dict(color="#9ec5f4"),
                 hovertemplate="구간 %{x}: %{y}개월<extra></extra>")
)
hist.add_vline(x=summ.current, line_color=rating.color, line_width=2)
hist.add_annotation(x=summ.current, y=1, yref="paper",
                    text=f"현재 {summ.current:,.2f} (백분위 {summ.pctile:.0f})",
                    showarrow=False, font=dict(color=rating.color), yanchor="bottom")
hist.update_layout(xaxis_title=f"{meta.label_ko} ({meta.unit})", yaxis_title="개월 수")
webui.base_layout(hist, height=320)
hist.update_layout(hovermode="closest")
st.plotly_chart(hist, width="stretch")

# ----------------------------------------------------------------- explanation
with st.expander("📖 이 지표 쉽게 이해하기", expanded=True):
    if meta.analogy_ko:
        st.markdown(f"**비유하면** — {meta.analogy_ko}")
    if meta.formula_ko:
        st.markdown(f"**공식** — `{meta.formula_ko}`")
    if meta.interpret_ko:
        st.markdown(f"**해석** — {meta.interpret_ko}")
    if meta.caveats_ko:
        st.markdown("**주의할 점**")
        for c in meta.caveats_ko:
            st.markdown(f"- {c}")

st.caption(webui.DISCLAIMER)
