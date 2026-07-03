"""ValueIndex — 미국 시장 밸류에이션 대시보드 (개요)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from valueindex import registry, stats, webui

st.set_page_config(page_title="ValueIndex — 밸류에이션 개요", page_icon="📊", layout="wide")

panel, statuses, extras = webui.get_data()
webui.sidebar(statuses)

st.title("📊 밸류에이션 개요")
st.caption(
    "미국 주식시장이 역사적으로 얼마나 비싼지/싼지를 여러 지표로 비교합니다. "
    "🔴 빨강 = 역사적 고평가(위험), 🔵 파랑 = 저평가(기회), ⚪ 회색 = 적정 범위. "
    "자세한 해석법은 **📚 지표 가이드**를 보세요."
)

# ---------------------------------------------------------------- time machine
latest = panel.dropna(how="all").index[-1]
with st.expander("🕰️ 역사 타임머신 — 과거 시점의 시장은 어땠을까?"):
    st.caption(
        "시점을 고르면 **그 시점까지의 데이터만으로** 등급을 다시 계산합니다 "
        "(당시 투자자가 알 수 있었던 정보만 사용)."
    )
    preset_cols = st.columns(len(registry.TIME_MACHINE_PRESETS) + 1)
    if preset_cols[0].button("현재", use_container_width=True):
        st.session_state["asof"] = latest
    for col, (label, date_str) in zip(preset_cols[1:], registry.TIME_MACHINE_PRESETS.items()):
        if col.button(label, use_container_width=True):
            st.session_state["asof"] = pd.Timestamp(date_str)
    years = list(range(1900, latest.year + 1, 1))
    slider_year = st.select_slider(
        "연도 선택", options=years,
        value=min(st.session_state.get("asof", latest).year, latest.year),
    )
    if slider_year != st.session_state.get("asof", latest).year:
        st.session_state["asof"] = pd.Timestamp(f"{slider_year}-06-01")

asof: pd.Timestamp = min(st.session_state.get("asof", latest), latest)
snapshot_mode = asof < latest - pd.DateOffset(months=1)
if snapshot_mode:
    st.warning(f"🕰️ **{asof:%Y년 %m월} 시점 스냅샷**을 보고 있습니다. '현재' 버튼으로 돌아올 수 있습니다.")

# ------------------------------------------------------------------- summaries
FMT = {"배": "{:.1f}", "%": "{:.2f}", "%p": "{:.2f}", "비율": "{:.2f}"}
rows = []
for key in registry.VALUATION_KEYS:
    s = panel[key].loc[:asof].dropna()
    if s.empty:
        continue
    summ = stats.summary(s)
    z = webui.aligned_z(key, summ.z)
    rows.append((key, summ, z, stats.rating(z)))

# ----------------------------------------------------------------- metric cards
cols = st.columns(3)
for i, (key, summ, z, rating) in enumerate(rows):
    meta = registry.INDICATORS[key]
    with cols[i % 3]:
        fmt = FMT.get(meta.unit, "{:.2f}")
        delta = None
        if summ.delta_1y is not None:
            delta = f"{summ.delta_1y:+.2f} (1년 전 대비)"
        st.metric(
            f"{meta.label_ko} ({meta.unit})",
            fmt.format(summ.current),
            delta=delta,
            delta_color="off",
            help=meta.what_ko,
        )
        history_flag = " ⚠️" if (asof - summ.start).days < 365 * 30 else ""
        top_pct = 100 - webui.aligned_pctile(key, summ.pctile)
        top_txt = "역대 상위 1% 이내" if top_pct < 1 else f"역대 상위 {top_pct:.0f}%"
        st.markdown(
            webui.rating_badge(rating)
            + f' <span style="color:{webui.MUTED};font-size:0.8rem">'
            f"고평가 {top_txt} · {summ.start.year}년~{history_flag}</span>",
            unsafe_allow_html=True,
        )
        st.write("")

if any((asof - summ.start).days < 365 * 30 for _, summ, _, _ in rows):
    st.caption("⚠️ 표시는 히스토리가 30년 미만이라 백분위·등급의 신뢰도가 낮다는 뜻입니다.")

# ------------------------------------------------------------------ gauge chart
st.subheader("고평가 게이지")
st.caption(
    "모든 지표를 같은 방향으로 정렬한 **역사적 백분위**입니다. "
    "100에 가까울수록 그 지표 기준으로 역사상 가장 비싼 구간입니다."
)
gauge_rows = sorted(rows, key=lambda r: webui.aligned_pctile(r[0], r[1].pctile))
fig = go.Figure(
    go.Bar(
        x=[webui.aligned_pctile(k, s.pctile) for k, s, _, _ in gauge_rows],
        y=[registry.INDICATORS[k].label_ko for k, s, _, _ in gauge_rows],
        orientation="h",
        marker=dict(color=[r.color for _, _, _, r in gauge_rows]),
        text=[f"{webui.aligned_pctile(k, s.pctile):.0f}" for k, s, _, _ in gauge_rows],
        textposition="outside",
        hovertemplate="%{y}: 백분위 %{x:.0f}<extra></extra>",
        width=0.55,
    )
)
fig.update_layout(xaxis=dict(range=[0, 108], title="고평가 백분위 (0 = 역사상 최저, 100 = 최고)"))
webui.base_layout(fig, height=380)
fig.update_layout(hovermode="closest")
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- summary table
st.subheader("요약 테이블")
table = pd.DataFrame(
    [
        {
            "지표": registry.INDICATORS[k].label_ko,
            "현재값": FMT.get(registry.INDICATORS[k].unit, "{:.2f}").format(s.current),
            "기준일": f"{s.asof:%Y-%m}",
            "등급": r.label_ko,
            "고평가 백분위": round(webui.aligned_pctile(k, s.pctile)),
            "역사 평균": FMT.get(registry.INDICATORS[k].unit, "{:.2f}").format(s.mean),
            "z-score": f"{z:+.2f}",
            "히스토리 시작": s.start.year,
            "출처": registry.INDICATORS[k].source,
        }
        for k, s, z, r in rows
    ]
)
st.dataframe(table, use_container_width=True, hide_index=True)

# -------------------------------------------------------------------- download
csv = panel.to_csv().encode("utf-8")
st.download_button(
    "💾 전체 지표 데이터 다운로드 (CSV)", csv,
    file_name="valueindex_panel.csv", mime="text/csv",
)
st.caption(webui.DISCLAIMER)
