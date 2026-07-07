# ValueIndex 📊

미국 주식시장의 밸류에이션 지표들(Shiller CAPE, 버핏지수 등)을 자동 수집해서
한 화면에서 비교하는 Streamlit 대시보드입니다. **API 키·가입 전혀 불필요**, 전부
무료 공개 데이터만 씁니다.

A Streamlit dashboard that collects and compares US market valuation
indicators (Shiller CAPE, Buffett Indicator, and friends). No API keys needed.

## 빠른 시작

```bash
git clone <this-repo>
cd ValueIndex
pip install -e .
streamlit run app.py
```

브라우저가 자동으로 열립니다. 첫 실행 시 무료 소스들에서 데이터를 수집해
`data/cache/`에 저장하고, 이후에는 인터넷 없이도 동작합니다(캐시가 오래되면
자동 갱신). 네트워크가 안 되는 환경에서도 번들된 샘플 데이터로 항상 실행됩니다.

### 처음 실행 후 확인할 것

1. **사이드바 "데이터 상태"** — 🟢 실시간(또는 🔵 캐시)로 표시되면 실데이터로
   동작 중입니다. ⚪ 샘플 데이터로 남아 있으면 수집이 실패한 것입니다.
2. **소스 진단 실행**:
   ```bash
   python scripts/check_live_sources.py
   ```
   소스별로 OK/FAIL과 실패 원인을 표로 보여줍니다.
3. 특정 소스가 계속 실패하면 위 진단 출력을 복사해 GitHub 이슈로 남겨주세요.
   실패한 소스가 있어도 앱은 캐시/샘플로 계속 동작합니다.

## 페이지 구성

| 페이지 | 내용 |
|---|---|
| 📊 개요 | 종합 밸류에이션 지수(PCA 제1주성분) + 지표별 σ 등급(신호등 색) + 고평가 게이지 + 🕰️ 역사 타임머신 + CSV 다운로드 |
| 📈 비교 차트 | 지표 겹쳐 보기 (Z-점수/백분위/원값), 경기침체 음영, 상관관계 히트맵 |
| 🔍 지표 상세 | 전체 히스토리 + ±σ 밴드 + 분포 히스토그램 + 평균회귀 반감기(AR(1) 적합) |
| 🌡️ 시장 온도계 | 🧠 심리(CNN 공포·탐욕, AAII, 신용융자, 미시간대) + 📌 자주 참고하는 매크로(기준금리·CPI·실업률·M2·기대인플레) + 거시(VIX·금리차·하이일드·금·유가) — 등급 없는 참고 지표 |
| 📚 지표 가이드 | 초보자용 지표 해설(정의→비유→공식→해석→한계), CAPE vs 10년 수익률 **조건부 분위 팬차트**(커널 분위 회귀), FAQ |
| 🧭 투자 시작 가이드 | 무엇부터 할지 순서 + 🧮 Bogle 기대수익률 계산기 + 🎲 적립식 몬테카를로 시뮬레이션 + 📐 규칙·공식 치트시트(72의 법칙·4% 룰·100−나이·ERP) |
| 🧘 투자 규율 | 행동 편향 대처, 드로다운 차트, 시나리오 규칙, 매수 전 체크리스트 |
| 🔬 초단기 실험실 | 단기 패턴(RSI·골든크로스 등)을 거래비용 포함 백테스트로 통계 검증 |

## 지표와 데이터 소스

**밸류에이션 지표** (σ 등급 부여 — 항상 🔴 빨강 = 고평가, 🔵 파랑 = 저평가):

| 지표 | 소스 | 히스토리 |
|---|---|---|
| Shiller CAPE, 초과 CAPE 수익률(ECY) | Shiller ie_data.xls | 1881~ |
| 버핏지수 (시가총액÷GDP) | FRED `NCBEILQ027S`, `GDP` | 1947~ |
| S&P 500 PER / PBR / 배당수익률 | multpl.com | 1881~ / 2000~ |
| Fed 모델 스프레드 | multpl + FRED `DGS10` | 1881~ |
| 장기 추세 이탈도 | Shiller 실질가격 (계산) | 1881~ |
| AIAE 투자자 주식배분 비율 | FRED 자금순환표 (계산) | 1951~ |

**참고 지표** (등급 없음): VIX, 10Y−2Y 금리차, 하이일드 스프레드, 미시간대 소비자심리 (FRED),
금·S&P 일간 (Stooq), CNN 공포·탐욕 지수(비공식 엔드포인트), AAII 주간 설문, FINRA 신용융자 잔고

> 심리 소스 3종(CNN·AAII·FINRA)은 공식 API가 없어 공개 페이지/파일을 파싱합니다.
> 형식이 바뀌면 해당 지표만 캐시/샘플로 폴백하며, `scripts/check_live_sources.py`로
> 어느 소스가 살아 있는지 확인할 수 있습니다.

모든 소스는 [무료 키리스 접근]이며, 실패 시 `신선한 캐시 → 라이브 → 오래된 캐시 →
번들 샘플` 순서로 폴백합니다. 사이드바에서 각 소스의 데이터 상태를 확인할 수 있습니다.

## 테스트

```bash
pip install -e ".[dev]"
pytest                 # 오프라인 단위 테스트 (fixture 기반)
pytest -m network      # 라이브 소스 스모크 테스트 (네트워크 필요, 수동 실행)
```

오프라인 강제 실행: `VALUEINDEX_OFFLINE=1 streamlit run app.py`

## 데이터 자동 갱신 (GitHub Actions)

`.github/workflows/refresh-data.yml`이 **매일 07:00 KST**에 모든 소스의 실데이터를
수집해 `src/valueindex/sample_data/`에 커밋합니다(성공한 소스만, 갱신 시각은
`_meta.json`에 기록). 앱은 **3일 이내의 스냅샷이면 네트워크를 건너뛰고 즉시 로딩**
하므로, 배포 앱의 콜드 스타트가 수 초 안에 끝납니다. 사이드바에 🟣 "자동 갱신
스냅샷"으로 표시되며, 새로고침 버튼은 여전히 라이브 수집을 강제합니다.

- 수동 실행: GitHub 저장소 → Actions 탭 → "Refresh market data" → **Run workflow**
- 첫 실행 전까지는 보간 샘플(⚪)로 동작합니다 — 워크플로를 한 번 수동 실행해 주세요.

## 번들 샘플 데이터에 관해

`src/valueindex/sample_data/`의 CSV들은 실제 발표된 역사적 기준값(예: 2000년 CAPE
44, 2009년 13) 사이를 보간한 **근사치**로, 네트워크 없이도 앱이 항상 뜨게 하기 위한
것입니다. 정확한 실데이터가 필요하면:

```bash
python scripts/refresh_sample_data.py   # 라이브 데이터로 샘플 교체
python scripts/generate_sample_data.py  # 보간 샘플 재생성
```

## Streamlit Cloud 무료 배포 (선택)

폰으로 상시 접속하고 싶다면:

1. 이 저장소를 GitHub에 푸시
2. [share.streamlit.io](https://share.streamlit.io) 에서 GitHub 로그인 → **New app**
3. 저장소 선택, 진입점 `app.py` 지정 → **Deploy**

몇 분 뒤 `https://<앱이름>.streamlit.app` 주소가 생깁니다. `requirements.txt`가
포함되어 있어 별도 설정이 필요 없습니다.

## 알아둘 것

- 이 앱은 **장기 투자자용 상황판**입니다. 데이터가 월간/분기 갱신이라 매일 볼 이유가
  없고, 지표들은 단기 시장 방향을 예측하지 못합니다(📚 지표 가이드의 "할 수 있는 것 vs
  없는 것" 참고).
- 버핏지수는 비금융법인 주식 기준 근사치입니다(윌셔5000이 FRED에서 제거됨).
  시리즈 교체는 `src/valueindex/config.py`에서 한 줄로 가능합니다.
- FRED CSV 헤더가 다시 바뀌어도 파서가 두 형식(`DATE`/`observation_date`)을 모두
  처리합니다. 공식 FRED API 키 방식이 필요해지면 이슈로 남겨주세요.

## 향후 아이디어 (기능 동결 — 구현하지 않고 기록만)

- 한국 시장(KOSPI) 지표 추가
- 등급 변화 알림 (배포 환경에서)
- 사용자 정의 백테스트 규칙 조합기

---

*이 앱은 교육용 정보 도구이며 투자 자문이 아닙니다. 모든 투자 판단과 책임은
본인에게 있습니다.*
