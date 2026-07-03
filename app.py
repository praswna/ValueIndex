"""ValueIndex — 미국 시장 밸류에이션 대시보드 (개요)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from valueindex import quant, registry, stats, webui

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

# -------------------------------------------------------- PCA composite index
# Computed on data up to `asof` only, so the time machine stays free of
# look-ahead (weights, means, and stds are re-fit on the truncated history).
aligned_z_panel = pd.DataFrame(
    {
        k: (stats.zscore(panel[k].loc[:asof].dropna())
            * (1 if registry.INDICATORS[k].higher_is_expensive else -1))
        for k in registry.VALUATION_KEYS
    }
)
pca = quant.pca_composite(aligned_z_panel)
pca_series = pca.composite
pca_now = float(pca_series.iloc[-1])
pca_rating = stats.rating(pca_now)

st.subheader("종합 밸류에이션 지수 (PCA)")
c_metric, c_chart = st.columns([1, 3])
with c_metric:
    st.metric(
        "종합 지수 (σ)", f"{pca_now:+.2f}",
        help="9개 지표에서 주성분 분석(PCA)으로 추출한 공통 성분입니다. "
        "0 = 역사 평균, +2σ 이상 = 역사적 극단 고평가.",
    )
    st.markdown(webui.rating_badge(pca_rating), unsafe_allow_html=True)
    st.caption(
        f"이 한 축이 지표 전체 변동의 {pca.explained_ratio * 100:.0f}%를 "
        "설명합니다 — 지표들이 결국 같은 것을 재고 있다는 수학적 증거입니다."
    )
with c_chart:
    pfig = go.Figure()
    for level in (2, 1, -1, -2):
        pfig.add_hline(y=level, line_color=webui.MUTED, line_width=1,
                       line_dash="dot", opacity=0.4)
    pfig.add_hline(y=0, line_color=webui.MUTED, line_width=1, opacity=0.6)
    pfig.add_trace(go.Scatter(
        x=pca_series.index, y=pca_series.values, mode="lines", name="종합 지수",
        line=dict(color="#2a78d6", width=2),
        hovertemplate="%{x|%Y-%m}: %{y:+.2f}σ<extra></extra>",
    ))
    pfig.add_trace(go.Scatter(
        x=[pca_series.index[-1]], y=[pca_now], mode="markers",
        marker=dict(color=pca_rating.color, size=10), showlegend=False,
        hovertemplate=f"현재 {pca_now:+.2f}σ<extra></extra>",
    ))
    pfig.update_layout(yaxis_title="종합 고평가 지수 (σ)", showlegend=False)
    webui.base_layout(pfig, height=260)
    st.plotly_chart(pfig, use_container_width=True)

with st.expander("이 지수는 어떻게 계산되나요?"):
    st.markdown(
        "9개 지표를 방향 정렬(높을수록 고평가)한 z-score 행렬의 상관행렬을 "
        "**고유값 분해**해서 제1주성분(가장 많은 공통 변동을 담는 축)을 추출합니다. "
        "지표별 가중치는 데이터가 스스로 정한 것이며, 시작 시점이 다른 지표는 "
        "그 달에 존재하는 지표만으로 점수를 계산합니다(가중치 재정규화)."
    )
    wdf = pd.DataFrame({
        "지표": [registry.INDICATORS[k].label_ko for k in pca.weights.index],
        "가중치": pca.weights.round(3).values,
    }).sort_values("가중치", ascending=False)
    st.dataframe(wdf, hide_index=True, use_container_width=True)

st.divider()

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

# ------------------------------------------------------------ nearest analogs
st.subheader("🔎 오늘과 가장 닮은 과거")
st.caption(
    "9개 지표의 z-score 벡터가 현재와 가장 가까웠던 과거 국면들입니다 "
    "(최근접 이웃 탐색 · 최근 5년 제외 · 같은 국면 중복 제거). "
    "**역사가 반복된다는 뜻이 아니라**, '비슷한 상황에서 과거엔 무슨 일이 있었나'를 "
    "보는 참고자료입니다."
)
analogs = quant.nearest_analogs(aligned_z_panel)
tri = extras["real_tri"].loc[:asof]

if analogs:
    ana_rows = []
    for a in analogs:
        cape_then = panel["cape"].asof(a.date)
        row = {
            "시기": f"{a.date:%Y년 %m월}",
            "지표당 차이": f"{a.distance:.2f}σ",
            "그때 CAPE": f"{cape_then:.1f}" if pd.notna(cape_then) else "-",
        }
        for label, months in (("이후 1년", 12), ("이후 5년(연)", 60), ("이후 10년(연)", 120)):
            base = tri.asof(a.date)
            fut_idx = a.date + pd.DateOffset(months=months)
            fut = tri.asof(fut_idx) if fut_idx <= tri.index[-1] else None
            if fut and pd.notna(base) and base > 0:
                ret = ((fut / base) ** (12 / months) - 1) * 100
                row[label] = f"{ret:+.1f}%"
            else:
                row[label] = "-"
        ana_rows.append(row)
    st.dataframe(pd.DataFrame(ana_rows), hide_index=True, use_container_width=True)

    # What came next: real total return indexed to 100 at each analog month.
    st.markdown("**닮은 시점 이후 10년, 실제 경로** (실질 총수익, 시작 = 100)")
    afig = go.Figure()
    palette = ["#2a78d6", "#eda100", "#4a3aa7", "#008300"]
    for color, a in zip(palette, analogs):
        seg = tri.loc[a.date: a.date + pd.DateOffset(months=120)]
        if len(seg) < 2:
            continue
        months_axis = [(d.year - a.date.year) * 12 + (d.month - a.date.month) for d in seg.index]
        afig.add_trace(go.Scatter(
            x=months_axis, y=(seg / seg.iloc[0] * 100).values, mode="lines",
            name=f"{a.date:%Y-%m}", line=dict(color=color, width=2),
            hovertemplate=f"{a.date:%Y-%m} + %{{x}}개월: %{{y:.0f}}<extra></extra>",
        ))
    afig.add_hline(y=100, line_color=webui.MUTED, line_width=1, line_dash="dot")
    afig.update_layout(xaxis_title="닮은 시점 이후 경과 (개월)",
                       yaxis_title="실질 총수익 지수 (시작=100)")
    webui.base_layout(afig, height=380)
    afig.update_layout(hovermode="x unified")
    st.plotly_chart(afig, use_container_width=True)
    st.caption(
        "표본이 몇 개뿐이라 통계적 결론은 불가능합니다 — 경로들이 서로 크게 다르다는 것 "
        "자체가 교훈입니다(비슷한 밸류에이션에서도 미래는 갈라집니다)."
    )
else:
    st.info("비교할 수 있는 과거 데이터가 부족합니다.")

# -------------------------------------------------------------------- download
csv = panel.to_csv().encode("utf-8")
st.download_button(
    "💾 전체 지표 데이터 다운로드 (CSV)", csv,
    file_name="valueindex_panel.csv", mime="text/csv",
)
st.caption(webui.DISCLAIMER)
