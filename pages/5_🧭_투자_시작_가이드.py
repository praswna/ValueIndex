"""투자 시작 가이드: 순서 + Bogle 기대수익률 계산기."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import plotly.graph_objects as go
import streamlit as st

from valueindex import config, indicators, stats, webui

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
st.plotly_chart(wf, use_container_width=True)

rating = stats.rating(webui.aligned_z("cape", stats.summary(panel["cape"].dropna()).z))
st.caption(
    f"현재 CAPE {cape_now:.1f} ({rating.label_ko})에서 역사 평균({cape_mean:.1f})으로 "
    "완전히 회귀한다고 가정하면 밸류에이션 변화만으로 연 "
    f"{indicators.bogle_expected_return(0, 0, cape_now, cape_mean):+.1f}%가 됩니다. "
    "물론 회귀하지 않을 수도, 더 올라갈 수도 있습니다 — 그래서 '가정'입니다."
)
st.caption(webui.DISCLAIMER)
