"""초단기 실험실: 단기 패턴을 통계로 검증하는 백테스트 놀이터."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from valueindex import backtest, webui

st.set_page_config(page_title="초단기 실험실", page_icon="🔬", layout="wide")
panel, statuses, extras = webui.get_data()
webui.sidebar(statuses)

st.title("🔬 초단기 실험실 — 르네상스처럼 생각해보기")
st.info(
    "**정직한 안내**: 르네상스 테크놀로지 같은 초단타 시스템의 우위는 공식이 아니라 "
    "틱 단위 데이터, 페타바이트급 인프라, 거의 0에 가까운 거래비용입니다 — 개인이 재현할 "
    "수 없습니다. 이 실험실은 그들의 **방법론**(가설 → 데이터 → 통계 검증)을 일간 데이터로 "
    "체험하는 축소판입니다. 유명한 단기 패턴이 실제 데이터에서, 특히 **거래비용을 넣은 뒤** "
    "얼마나 살아남는지 직접 확인해 보세요."
)

spx = extras["spx_daily"].set_index("date").sort_index()

c1, c2, c3 = st.columns([2, 1, 1])
rule_labels = {label: key for key, (label, _) in backtest.RULES.items()}
rule_key = rule_labels[c1.selectbox("검증할 패턴 (가설)", list(rule_labels))]
years = sorted({d.year for d in spx.index})
yr = c2.select_slider("기간", options=years, value=(max(years[0], 1990), years[-1]))
cost_bps = c3.slider(
    "왕복 거래비용 (bp)", 0, 50, 10,
    help="수수료+슬리피지. 1bp = 0.01%. 개인 투자자의 현실적 왕복 비용은 대략 5~30bp입니다. "
    "0으로 두면 '수수료 없는 세상'의 결과를 봅니다.",
)

view = spx.loc[f"{yr[0]}":f"{yr[1]}"]
_, rule_fn = backtest.RULES[rule_key]
positions = rule_fn(view)
res = backtest.evaluate(positions, view["close"], cost_bps=cost_bps)
res_free = backtest.evaluate(positions, view["close"], cost_bps=0)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("진입 횟수", f"{res.n_trades:,}")
m2.metric("보유일 승률", f"{res.win_rate * 100:.1f}%",
          help="포지션 보유일 중 수익이 난 날의 비율")
m3.metric("보유일 평균 수익률 (%/일)", f"{res.mean_daily_ret:+.3f}")
m4.metric("t-통계", f"{res.t_stat:.2f}",
          help="±2를 넘어야 통계적으로 유의하다고 봅니다")
m5.metric("누적 비용", f"−{res.total_costs_pct:.1f}%p")

fig = go.Figure()
fig.add_trace(go.Scatter(x=res.buy_hold_curve.index, y=res.buy_hold_curve.values,
                         name="그냥 보유 (buy & hold)", mode="lines",
                         line=dict(color="#898781", width=2)))
fig.add_trace(go.Scatter(x=res_free.equity_curve.index, y=res_free.equity_curve.values,
                         name="전략 (비용 0)", mode="lines",
                         line=dict(color="#2a78d6", width=2, dash="dot")))
fig.add_trace(go.Scatter(x=res.equity_curve.index, y=res.equity_curve.values,
                         name=f"전략 (비용 {cost_bps}bp)", mode="lines",
                         line=dict(color="#eb6834", width=2)))
fig.update_layout(yaxis_title="누적 배수 (시작 = 1)", yaxis_type="log")
webui.base_layout(fig, height=440)
st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------- auto verdict
verdicts = []
if abs(res.t_stat) < 2:
    verdicts.append("보유일 수익률이 **통계적으로 유의하지 않습니다** (|t| < 2) — 우연과 구분되지 않습니다.")
else:
    verdicts.append("보유일 수익률이 통계적으로는 유의해 보입니다 (|t| ≥ 2) — 아래 다중검정 함정을 꼭 읽어보세요.")
strat_final = res.equity_curve.iloc[-1]
bh_final = res.buy_hold_curve.iloc[-1]
if strat_final < bh_final:
    verdicts.append(
        f"비용 {cost_bps}bp 반영 시 전략({strat_final:.2f}배)이 그냥 보유({bh_final:.2f}배)에 "
        "**뒤집니다** — 신호가 있어 보여도 시장에서 빠져 있는 날의 기회비용과 거래비용이 이깁니다."
    )
else:
    verdicts.append(
        f"이 구간에서는 전략({strat_final:.2f}배)이 보유({bh_final:.2f}배)를 앞섭니다 — "
        "기간을 바꿔보세요. 특정 구간에서만 이기는 전략은 대부분 과최적화입니다."
    )
if cost_bps == 0:
    verdicts.append("지금은 **비용 0의 가상 세계**입니다. 슬라이더로 현실적 비용(10~30bp)을 넣어 보세요.")
st.markdown("#### 자동 판정\n" + "\n".join(f"- {v}" for v in verdicts))

with st.expander("⚠️ 다중검정의 함정 — 퀀트가 가장 조심하는 것"):
    st.markdown(
        "패턴을 100개 시험하면 **순전히 우연으로도 약 5개는 유의해 보입니다** (유의수준 5%의 "
        "의미가 그것입니다). 르네상스 같은 회사들이 수학자를 고용하는 이유의 절반은 새 패턴을 "
        "찾는 것이고, 나머지 절반은 **찾은 패턴이 우연인지 가려내는 것**입니다. 이 실험실에서 "
        "여러 규칙·기간을 바꿔가며 '되는 조합'을 찾았다면, 그것이 바로 과최적화가 만들어지는 "
        "과정을 체험한 것입니다."
    )

st.caption(
    "방법론 주의: 신호는 당일 종가로 계산되고 수익은 다음 날부터 적용됩니다(미래 정보 미사용). "
    "세금·배당은 반영하지 않았습니다. " + webui.DISCLAIMER
)
