"""투자 시작 가이드: 순서 + Bogle 기대수익률 계산기."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from valueindex import config, indicators, quant, stats, webui

st.set_page_config(page_title="투자 시작 가이드", page_icon="🧭", layout="wide")
panel, statuses, extras = webui.get_data()
webui.sidebar(statuses)

st.title("🧭 투자 시작 가이드")
st.warning(
    "아래 내용은 교육용 일반 원칙이며 개인 상황(소득·부채·세금)에 따른 투자 자문이 "
    "아닙니다. 큰 금액이라면 자격 있는 전문가와 상의하세요."
)

st.markdown((config.CONTENT_DIR / "investing_guide_ko.md").read_text(encoding="utf-8"))

# ------------------------------------------------------------ Bogle calculator
st.markdown("---")
st.header("🧮 10년 기대수익률 계산기 (Bogle 공식)")
st.markdown(
    "존 보글이 대중화한 분해식입니다 — Vanguard·GMO 같은 운용사의 장기 전망도 "
    "본질적으로 이 원리를 씁니다:\n\n"
    "> **기대수익률 ≈ 배당수익률 + 이익성장률 + 밸류에이션 변화(연환산)**\n\n"
    "배당수익률과 현재 CAPE는 최신 데이터로 채워져 있습니다. 나머지 두 가정을 직접 "
    "움직여 보세요 — **가정이 결론을 만든다**는 것을 보는 게 이 계산기의 목적입니다."
)

div_now = float(panel["div_yield"].dropna().iloc[-1])
cape_now = float(panel["cape"].dropna().iloc[-1])
cape_mean = float(panel["cape"].dropna().mean())

c1, c2 = st.columns(2)
growth = c1.slider(
    "실질 이익성장률 가정 (%/년)", -2.0, 6.0, 2.0, 0.25,
    help="미국 기업 실질 이익의 초장기 평균은 연 약 2%입니다.",
)
cape_future = c2.slider(
    "10년 뒤 CAPE 가정", 10.0, 60.0, round((cape_now + cape_mean) / 2, 1), 0.5,
    help=f"현재 {cape_now:.1f}, 역사 평균 {cape_mean:.1f}. "
    "기본값은 둘의 중간(부분적 평균회귀)입니다.",
)

valuation_change = indicators.bogle_expected_return(0, 0, cape_now, cape_future)
total = indicators.bogle_expected_return(div_now, growth, cape_now, cape_future)

st.metric(
    "10년 실질 기대수익률 (연환산)", f"{total:+.1f}%",
    help="인플레이션을 뺀 실질 기준입니다. 명목 수익률은 여기에 물가상승률을 더한 값입니다.",
)

wf = go.Figure(
    go.Waterfall(
        x=["배당수익률", "이익성장률", "밸류에이션 변화", "합계"],
        measure=["relative", "relative", "relative", "total"],
        y=[div_now, growth, valuation_change, None],
        text=[f"{v:+.1f}%" for v in (div_now, growth, valuation_change)] + [f"{total:+.1f}%"],
        textposition="outside",
        connector=dict(line=dict(color=webui.GRID)),
        increasing=dict(marker=dict(color="#2a78d6")),
        decreasing=dict(marker=dict(color="#c22f2f")),
        totals=dict(marker=dict(color="#898781")),
    )
)
wf.update_layout(yaxis_title="%/년 (실질)", showlegend=False)
webui.base_layout(wf, height=380)
wf.update_layout(hovermode="closest")
st.plotly_chart(wf, width="stretch")

rating = stats.rating(webui.aligned_z("cape", stats.summary(panel["cape"].dropna()).z))
st.caption(
    f"현재 CAPE {cape_now:.1f} ({rating.label_ko})에서 역사 평균({cape_mean:.1f})으로 "
    "완전히 회귀한다고 가정하면 밸류에이션 변화만으로 연 "
    f"{indicators.bogle_expected_return(0, 0, cape_now, cape_mean):+.1f}%가 됩니다. "
    "물론 회귀하지 않을 수도, 더 올라갈 수도 있습니다 — 그래서 '가정'입니다."
)

# ---------------------------------------------------- Monte Carlo DCA simulator
st.markdown("---")
st.header("🎲 적립식 투자 시뮬레이션 (몬테카를로)")
st.markdown(
    "위 계산기의 기대수익률은 **평균**일 뿐입니다. 실제 결과는 그 주변에 넓게 "
    "흩어집니다 — 얼마나 흩어지는지를 보여주는 것이 이 시뮬레이션입니다. "
    "지난 140여 년의 **월간 실질 수익률을 12개월 블록 단위로 무작위 재표집** "
    "(블록 부트스트랩)해서, 변동성의 군집성까지 보존한 수천 개의 가상 미래를 만듭니다."
)

s1, s2, s3 = st.columns(3)
contrib = s1.number_input("월 적립액 (만원)", 10, 1000, 50, 10)
sim_years = s2.slider("적립 기간 (년)", 5, 40, 20)
drift_mode = s3.radio(
    "수익률 가정", ["역사 평균 그대로", "위 계산기 결과 사용"],
    help="'계산기 결과 사용'은 시뮬레이션의 평균 수익률을 위에서 계산한 "
    f"연 {total:+.1f}%(실질)로 맞추고, 변동성은 역사 그대로 둡니다.",
)

monthly_rets = extras["real_tri"].pct_change().dropna()
drift = None if drift_mode == "역사 평균 그대로" else total
sim = quant.simulate_dca(
    monthly_rets, float(contrib), sim_years,
    annual_drift_target=drift,
    seed=int(contrib * 1000 + sim_years),  # stable per input combination
)

years_axis = sim.percentiles.index / 12
dfig = go.Figure()
dfig.add_trace(go.Scatter(x=years_axis, y=sim.percentiles["p95"], mode="lines",
                          line=dict(width=0), showlegend=False, hoverinfo="skip"))
dfig.add_trace(go.Scatter(x=years_axis, y=sim.percentiles["p5"], mode="lines",
                          fill="tonexty", fillcolor="rgba(28,92,171,0.10)",
                          line=dict(width=0), name="90% 구간", hoverinfo="skip"))
dfig.add_trace(go.Scatter(x=years_axis, y=sim.percentiles["p75"], mode="lines",
                          line=dict(width=0), showlegend=False, hoverinfo="skip"))
dfig.add_trace(go.Scatter(x=years_axis, y=sim.percentiles["p25"], mode="lines",
                          fill="tonexty", fillcolor="rgba(28,92,171,0.18)",
                          line=dict(width=0), name="50% 구간", hoverinfo="skip"))
dfig.add_trace(go.Scatter(x=years_axis, y=sim.percentiles["p50"], mode="lines",
                          name="중앙값", line=dict(color="#1c5cab", width=2.5),
                          hovertemplate="%{x:.0f}년차: %{y:,.0f}만원<extra></extra>"))
contrib_line = np.arange(1, sim_years * 12 + 1) * contrib
dfig.add_trace(go.Scatter(x=years_axis, y=contrib_line, mode="lines",
                          name="납입 원금", line=dict(color=webui.MUTED, width=1.5,
                                                   dash="dash"),
                          hovertemplate="%{x:.0f}년차 원금: %{y:,.0f}만원<extra></extra>"))
dfig.update_layout(xaxis_title="경과 (년)", yaxis_title="자산 (만원, 실질)")
webui.base_layout(dfig, height=420)
st.plotly_chart(dfig, width="stretch")

fw = sim.final_wealth
r1, r2, r3, r4 = st.columns(4)
r1.metric("납입 원금", f"{sim.total_contributed:,.0f}만원")
r2.metric("중앙값 결과", f"{np.median(fw):,.0f}만원")
r3.metric("하위 5% 결과", f"{np.percentile(fw, 5):,.0f}만원")
r4.metric("상위 5% 결과", f"{np.percentile(fw, 95):,.0f}만원")
loss_prob = float((fw < sim.total_contributed).mean()) * 100
st.caption(
    f"이 가정에서 {sim_years}년 뒤 자산이 납입 원금에 못 미칠 확률: **{loss_prob:.0f}%** "
    "(2,000회 시뮬레이션, 인플레이션 차감 실질 기준). 세금·수수료 미반영. "
    "미래가 과거의 통계적 반복이라는 가정 자체가 시뮬레이션의 한계입니다."
)

# ------------------------------------------------------- rules-of-thumb cheat sheet
st.markdown("---")
st.header("📐 자주 쓰는 규칙·공식")
st.caption("투자에서 사람들이 자주 인용하는 어림 계산들입니다. 정밀 계산이 아니라 감을 잡는 용도입니다.")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("72의 법칙 — 원금이 2배 되는 기간")
    r = st.slider("연 수익률 (%)", 1.0, 20.0, 7.0, 0.5, key="rule72")
    st.metric("2배까지 걸리는 시간", f"약 {72 / r:.1f}년",
              help="72 ÷ 수익률. 복리로 원금이 두 배가 되는 햇수를 빠르게 어림합니다.")
    st.caption(f"연 {r:.1f}%면 약 {72 / r:.0f}년마다 2배 → 30년이면 약 "
               f"{2 ** (30 / (72 / r)):.0f}배가 됩니다.")

    st.subheader("100 − 나이 — 주식 비중 어림")
    age = st.number_input("나이", 20, 90, 35, key="age100")
    st.metric("주식 비중 어림값", f"{max(0, 110 - age)}% 안팎",
              help="전통적으로 '100−나이', 요즘은 수명 연장으로 '110−나이'도 씁니다. 위험 감내도에 따라 조정하세요.")

with col_b:
    st.subheader("4% 룰 — 은퇴 후 안전 인출액")
    nest = st.number_input("은퇴 자산 (만원)", 1000, 1_000_000, 100_000, 1000, key="rule4")
    st.metric("연간 인출 가능액", f"{nest * 0.04:,.0f}만원",
              help="은퇴 첫해 자산의 4%를 인출하고 이후 물가만큼 늘리면 대체로 30년 이상 고갈되지 않는다는 경험칙(Trinity 연구).")
    st.caption(f"월 약 {nest * 0.04 / 12:,.0f}만원. 고평가 국면에 은퇴를 시작하면 더 보수적으로(3~3.5%) 보기도 합니다.")

    st.subheader("주식 위험프리미엄 (ERP)")
    st.metric("장기 평균", "약 4~5%p",
              help="주식 기대수익률에서 무위험(국채) 금리를 뺀 값. 주식을 드는 대가로 기대하는 초과수익입니다.")
    st.caption("이 앱의 **Fed 모델 스프레드**·**ECY**가 현재 시점의 ERP를 재는 지표입니다.")

st.info(
    "이 규칙들은 미국 장기 데이터에서 나온 **어림값**입니다. 개인의 세금·부채·목표에 따라 "
    "달라지며, 특히 4% 룰은 낮은 기대수익률 국면에서 논쟁이 많습니다."
)
st.caption(webui.DISCLAIMER)
