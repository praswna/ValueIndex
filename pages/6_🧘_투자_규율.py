"""투자 규율: 드로다운 차트, 시나리오 규칙, 체크리스트."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import plotly.graph_objects as go
import streamlit as st

from valueindex import config, indicators, registry, stats, webui

st.set_page_config(page_title="투자 규율", page_icon="🧘", layout="wide")
panel, statuses, extras = webui.get_data()
webui.sidebar(statuses)

st.title("🧘 투자 규율")

st.markdown((config.CONTENT_DIR / "discipline_ko.md").read_text(encoding="utf-8"))

# ------------------------------------------------------------- drawdown chart
st.markdown("---")
st.header("역사적 드로다운 — 급락은 정상입니다")
dd = indicators.drawdown(extras["real_tri"])
fig = go.Figure(
    go.Scatter(
        x=dd.index, y=dd.values, mode="lines", name="고점 대비 하락률",
        line=dict(color="#c22f2f", width=1.5), fill="tozeroy",
        fillcolor="rgba(194,47,47,0.12)",
        hovertemplate="%{x|%Y-%m}: %{y:.0f}%<extra></extra>",
    )
)
fig.update_layout(yaxis_title="실질 총수익 기준 고점 대비 %", showlegend=False)
webui.base_layout(fig, height=380)
webui.add_recession_shading(fig, extras["usrec"], start=dd.index[0])
st.plotly_chart(fig, width="stretch")
st.markdown(
    f"- 지난 140여 년 동안 **−50% 이상의 하락이 여러 번** 있었고, 매번 회복했습니다.\n"
    f"- 최악의 드로다운: **{dd.min():.0f}%** ({dd.idxmin():%Y년}).\n"
    "- '−30% 급락'은 이례적 사건이 아니라 장기 투자에 **포함된 비용**입니다. "
    "이걸 미리 알고 시작하는 것과 모르고 당하는 것의 차이가 규율입니다."
)

# ------------------------------------------------------- scenario rules
st.markdown("---")
st.header("시나리오별 행동 규칙 (사전 약속)")
cape_summ = stats.summary(panel["cape"].dropna())
current_rating = stats.rating(webui.aligned_z("cape", cape_summ.z))
st.markdown(
    f"지금 CAPE 기준 등급: {webui.rating_badge(current_rating)} — 패닉 상황에서 즉흥적으로 "
    "판단하지 않도록, **평온한 지금** 규칙을 정해두는 것이 이 섹션의 목적입니다.",
    unsafe_allow_html=True,
)
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("#### 🔴 매우 고평가일 때")
    st.markdown(
        "- 신규 목돈은 분할 폭을 **넓게** (예: 12개월)\n"
        "- 향후 10년 기대치를 낮춰 잡기 (🧭 계산기)\n"
        "- 채권/현금 비중 재점검\n"
        "- ❌ **보유분 전량 매도가 아닙니다**"
    )
with c2:
    st.markdown("#### 🔵 저평가일 때")
    st.markdown(
        "- 미리 정한 리밸런싱 실행 (주식 비중 복원)\n"
        "- 적립 금액 유지 또는 계획된 범위 내 증액\n"
        "- ❌ **빚내서 몰빵이 아닙니다**"
    )
with c3:
    st.markdown("#### 📉 시장 −30% 급락 시")
    st.markdown(
        "- 적립 **중단 금지** — 같은 돈으로 더 많이 삽니다\n"
        "- 뉴스·계좌 확인 빈도 줄이기\n"
        "- 왼쪽 드로다운 차트 다시 보기: 매번 회복했습니다\n"
        "- ❌ **'일단 팔고 지켜보기'가 최악의 수입니다**"
    )

# ------------------------------------------------------------------ checklist
st.markdown("---")
st.header("매수 전 체크리스트")
st.caption("하나라도 체크가 안 되면, 오늘은 사지 않는 것이 규칙입니다. (체크 상태는 저장되지 않습니다)")
checks = [
    "비상금(3~6개월 생활비)이 투자금과 별도로 있다",
    "이 돈은 최소 10년 묻어둘 수 있는 돈이다",
    "연 5% 이상 고금리 부채가 없다",
    "매수 이유가 유튜브·지인 추천·급등 뉴스가 아니다",
    "이 매수 후에도 한 종목/테마 비중이 전체의 20%를 넘지 않는다",
    "떨어져도 팔지 않을 하락 한도를 미리 정했다",
]
done = sum(st.checkbox(c, key=f"chk_{i}") for i, c in enumerate(checks))
if done == len(checks):
    st.success("✅ 모든 항목 통과 — 계획대로 진행하세요.")
else:
    st.info(f"{done}/{len(checks)} 통과 — 전부 체크되기 전에는 매수를 미루는 것이 규칙입니다.")

# --------------------------------------------------------------- monthly routine
st.markdown("---")
st.header("월간 점검 루틴 — 한 달에 한 번, 이 3가지만")
st.markdown(
    "1. **개요 페이지**에서 등급 색이 바뀌었는지 확인 (대부분 그대로입니다)\n"
    "2. 내 포트폴리오의 주식/채권 비중이 목표에서 ±5%p 이상 벗어났는지 확인\n"
    "3. **아무것도 안 해도 된다는 것**을 확인하고 닫기 — 행동하지 않는 것도 결정입니다\n"
)

st.markdown("---")
st.markdown("### 더 공부하기")
st.markdown((config.CONTENT_DIR / "resources_ko.md").read_text(encoding="utf-8"))
st.caption(webui.DISCLAIMER)
