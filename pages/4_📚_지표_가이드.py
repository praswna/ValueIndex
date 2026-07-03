"""지표 가이드: 초보자용 지표 설명 + 산점도 + FAQ + 추천 자료."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from valueindex import config, indicators, registry, stats, webui

st.set_page_config(page_title="지표 가이드", page_icon="📚", layout="wide")
panel, statuses, extras = webui.get_data()
webui.sidebar(statuses)

st.title("📚 지표 가이드 — 처음부터 차근차근")

st.markdown("""
### 밸류에이션 지표란?

주식시장의 **가격표가 합리적인지** 확인하는 도구입니다. 같은 아파트라도 3억이면 싸고
10억이면 비싸듯, 주식시장도 "무엇 대비 얼마인가"를 재야 비싼지 알 수 있습니다.
그 "무엇"이 기업의 이익이냐(PER, CAPE), 자산이냐(PBR), 경제 전체냐(버핏지수),
채권 금리냐(ECY, Fed 스프레드)에 따라 지표가 달라집니다.

### σ(시그마) 등급 읽는 법

이 앱의 모든 등급은 **"현재 값이 그 지표의 역사 평균에서 얼마나 멀리 떨어져 있나"**
(표준편차, σ)로 매깁니다.

| 등급 | 의미 | 역사적 빈도 |
|---|---|---|
| 🔵 매우 저평가 | 평균 −2σ 아래 | 약 2% |
| 🔵 저평가 | −2σ ~ −1σ | 약 14% |
| ⚪ 적정 | −1σ ~ +1σ | 약 70% |
| 🟠 고평가 | +1σ ~ +2σ | 약 14% |
| 🔴 매우 고평가 | +2σ 위 | 약 2% |

방향이 다른 지표(배당수익률처럼 **낮을수록** 비싼 것)는 방향을 뒤집어 정렬하므로,
**어떤 지표든 빨강 = 비싸다/위험, 파랑 = 싸다/기회**로 읽으면 됩니다.
""")

# ------------------------------------------------- can vs cannot + scatter
st.markdown("### 이 지표들이 할 수 있는 것 vs 없는 것")
col_a, col_b = st.columns(2)
col_a.success(
    "**할 수 있는 것**\n\n"
    "- 지금 시장이 역사적으로 비싼 구간인지 확인\n"
    "- 향후 **10년** 기대수익률의 대략적 경향 파악\n"
    "- 주식/채권 비중 같은 장기 자산배분의 참고자료"
)
col_b.error(
    "**할 수 없는 것**\n\n"
    "- 다음 주·다음 달·내년 시장 방향 예측\n"
    "- 매수/매도 타이밍 신호 (CAPE는 1990년대 중반부터 '고평가'였지만 시장은 수년 더 올랐습니다)\n"
    "- 개별 종목 선택"
)

st.markdown("#### 증거: CAPE와 이후 10년 실질수익률")
tri = extras["real_tri"]
fwd = indicators.forward_10y_return(tri)
cape = panel["cape"]
scatter_df = pd.DataFrame({"cape": cape, "fwd": fwd}).dropna()
current_cape = cape.dropna().iloc[-1]

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=scatter_df["cape"], y=scatter_df["fwd"], mode="markers",
        marker=dict(color="#9ec5f4", size=5,
                    line=dict(color="#ffffff", width=0.5)),
        name="각 월 (1881~)",
        hovertemplate="CAPE %{x:.1f} → 이후 10년 연 %{y:.1f}%<extra></extra>",
    )
)
fig.add_vline(x=current_cape, line_color="#c22f2f", line_width=2)
fig.add_annotation(x=current_cape, y=1, yref="paper", yanchor="bottom",
                   text=f"현재 CAPE {current_cape:.1f}", font=dict(color="#c22f2f"),
                   showarrow=False)
fig.add_hline(y=0, line_color=webui.MUTED, line_width=1, line_dash="dot")
fig.update_layout(
    xaxis_title="그 시점의 CAPE", yaxis_title="이후 10년 실질 총수익률 (연환산 %)",
    showlegend=False,
)
webui.base_layout(fig, height=440)
fig.update_layout(hovermode="closest")
st.plotly_chart(fig, use_container_width=True)
st.caption(
    "우하향 **경향**은 분명하지만 같은 CAPE에서도 결과가 크게 흩어집니다 — "
    "그래서 '기대치 조정'에는 유용해도 '예측'은 아닙니다."
)

# --------------------------------------------------------- per-indicator guide
st.markdown("---")
st.markdown("### 지표별 해설")
for key in registry.VALUATION_KEYS:
    meta = registry.INDICATORS[key]
    s = panel[key].dropna()
    summ = stats.summary(s) if len(s) else None
    with st.expander(f"**{meta.label_ko}** — {meta.what_ko}"):
        if meta.analogy_ko:
            st.markdown(f"**① 비유하면** — {meta.analogy_ko}")
        if meta.formula_ko:
            st.markdown(f"**② 공식** — `{meta.formula_ko}`")
        if meta.interpret_ko:
            st.markdown(f"**③ 해석** — {meta.interpret_ko}")
        if summ:
            st.markdown(
                f"**④ 지금은** — {summ.current:,.2f} {meta.unit} "
                f"(역사 평균 {summ.mean:,.2f}, {summ.start.year}년 이후 "
                f"고평가 백분위 {webui.aligned_pctile(key, summ.pctile):.0f})"
            )
        if meta.caveats_ko:
            st.markdown("**⑤ 한계점**")
            for c in meta.caveats_ko:
                st.markdown(f"- {c}")

# ------------------------------------------------------------------------ FAQ
st.markdown("---")
st.markdown("### 자주 묻는 질문")
with st.expander("왜 금·유가는 밸류에이션 지표에 없나요?"):
    st.markdown(
        "금과 석유는 이익도 배당도 만들지 않아 **'적정 가격'의 기준점이 없습니다.** "
        "CAPE가 작동하는 원리는 가격을 펀더멘털(이익)에 비교하는 것인데, 금값에는 "
        "비교할 이익이 없어 '비싸다/싸다'를 판정할 수 없습니다. 대신 금은 인플레이션 "
        "불안·달러 신뢰의 온도계, 유가는 경기·인플레이션의 입력값으로서 "
        "**🌡️ 시장 온도계** 탭에서 등급 없이 보여줍니다."
    )
with st.expander("지표를 더 늘리면 예측이 정확해지지 않나요?"):
    st.markdown(
        "밸류에이션 지표들은 전부 '가격 ÷ 펀더멘털' 구조라 **서로 상관이 높습니다** "
        "(📈 비교 차트 탭의 상관관계 히트맵 참고). 같은 온도를 재는 온도계를 10개로 "
        "늘려도 예보가 정확해지지 않는 것과 같습니다. 여러 지표의 효용은 예측력 향상이 "
        "아니라 개별 지표의 왜곡을 걸러내는 것입니다."
    )
with st.expander("금융회사들은 뭘 쓰나요?"):
    st.markdown(
        "대형 운용사(Vanguard, GMO, BlackRock)의 장기 전망 모델도 본질적으로 이 앱과 "
        "같은 재료 — **밸류에이션 + 금리 + 배당 + 성장률** — 를 씁니다. 그들의 우위는 "
        "비밀 공식이 아니라 데이터 인프라, 거래 비용, 그리고 규율입니다. "
        "(🧘 투자 규율 탭 참고)"
    )

# ------------------------------------------------------------------- resources
st.markdown("---")
st.markdown("### 더 공부하기")
st.markdown((config.CONTENT_DIR / "resources_ko.md").read_text(encoding="utf-8"))
st.caption(webui.DISCLAIMER)
