# ValueIndex 📊

미국·한국 주식시장의 밸류에이션 지표들(Shiller CAPE, 버핏지수 등)을 자동 수집해서
한 화면에서 비교하는 대시보드입니다. **API 키·가입 전혀 불필요**, 전부 무료 공개
데이터만 씁니다.

**두 가지 형태로 제공됩니다:**

1. **정적 웹사이트 (정본)** — GitHub Pages: **https://praswna.github.io/ValueIndex/**
   서버가 없어 **즉시 로딩**되고, GitHub Actions가 매일 아침 데이터를 갱신·재배포합니다.
   콜드 스타트가 없어 폰에서 상시 접속하기 좋습니다.
2. **Streamlit 앱 (로컬용)** — 개발·오프라인 확인용. 아래 참고. (Streamlit Cloud
   배포는 콜드 스타트 때문에 폐기했습니다.)

정적 사이트와 Streamlit 앱은 **같은 Python 코어**(수집·지표·통계·백테스트)를
공유합니다 — 정적 사이트는 그 계산 결과를 `docs/data/*.json`으로 굽고, 브라우저
JS가 인터랙티브 부분만 다시 계산합니다. 두 UI는 픽스처 기반 패리티 테스트로
같은 값을 내도록 고정됩니다.

## 정적 사이트 (권장)

이미 배포되어 있으면 위 주소로 접속만 하면 됩니다. **최초 1회 설정** (저장소 소유자):

1. GitHub 저장소 → **Settings → Pages → Build and deployment → Source: "GitHub Actions"**
2. (선택) **Settings → Secrets and variables → Actions**에 `FRED_API_KEY` 추가
   — GitHub 서버 IP는 FRED의 키리스 CSV가 막혀 있어, 무료 API 키
   (fred.stlouisfed.org/docs/api/api_key.html)를 넣으면 FRED 지표가 실데이터로 채워집니다.
3. **Actions 탭 → "Refresh market data" → Run workflow**로 첫 빌드·배포 실행.

로컬에서 정적 사이트 미리보기:
```bash
pip install -e ".[site]"
python scripts/build_site_data.py      # docs/data/*.json 생성 (오프라인이면 샘플)
python -m http.server                  # http://localhost:8000/docs/index.html
```

## 🛰️ 로컬 데이터 수집기 (GUI)

KRX PER/PBR·FINRA 신용융자·AAII 설문·SEC EDGAR 큰손(13F)은 클라우드(GitHub
Actions) IP가 차단되어 자동 갱신에서 빠집니다. **집 PC(주거용 IP)에서는 이 소스들도
열리므로**, GUI 수집기로 모든 데이터를 직접 수집해 올릴 수 있습니다.

수집기는 **파이썬 표준 라이브러리 Tkinter 창** 하나입니다 — Streamlit·브라우저·
이메일 입력·무거운 의존성 없이 돕니다:

```bash
pip install -e ".[site]"     # 코어 + markdown (사이트 재생성용). streamlit 불필요
python collector_gui.py
```

**터미널이 익숙하지 않으면** 저장소 폴더의 실행 파일을 더블클릭하세요 — 첫 실행 때
필요한 패키지까지 자동 설치하고 수집기 창을 엽니다:
- Windows: `run_collector.bat` 더블클릭
- macOS: `run_collector.command` 더블클릭 (최초 1회는 Finder에서 우클릭 → 열기 로
  Gatekeeper 허용)

창의 버튼 3개를 순서대로 누르면 됩니다:
1. **① 전체 수집** — 모든 소스를 집 IP로 실시간 수집(진행 막대·소스별 ✓/✗ 로그),
   성공분을 `sample_data/`에 저장(실패한 소스는 기존 파일 유지)
2. **② 사이트 재생성** — `docs/data/*.json` 다시 굽기
3. **③ 커밋 & 푸시** — 저장소에 올리면 GitHub Pages가 1~2분 뒤 자동 배포

PER/PBR·신용융자·AAII·13F는 월/분기 단위라 **한 달에 한 번쯤** 돌려주면 충분합니다.
그 사이 매일 도는 Actions는 이 소스들의 마지막 실데이터를 덮어쓰지 않고 유지합니다.

## Streamlit 앱 (로컬, 선택)

정본은 정적 사이트입니다. 예전 Streamlit 대시보드가 필요하면 `app` 엑스트라로
streamlit을 따로 설치하세요(코어 설치에는 포함되지 않습니다):

```bash
git clone <this-repo>
cd ValueIndex
pip install -e ".[app]"
streamlit run app.py
```

Windows PowerShell에서는 `&&`가 안 되니 두 줄로 나눠 실행하세요.
첫 실행 시 무료 소스에서 데이터를 수집해 `data/cache/`에 저장하고, 이후에는 인터넷
없이도 동작합니다. 사이드바 "데이터 상태"에서 소스별 상태를 확인할 수 있고,
`python scripts/check_live_sources.py`로 어떤 소스가 살아 있는지 진단할 수 있습니다.

## 페이지 구성

| 페이지 | 내용 |
|---|---|
| ⚡ 요약 | 첫 화면 — 지표 타일 한 화면, 누르면 딥다이브 팝업(±σ 밴드·분포·해석). `summary.html#cape` 딥링크 지원 |
| 📊 개요 | 종합 밸류에이션 지수(PCA) + 게이지 + 🕰️ 역사 타임머신 + 닮은 과거 + 접이식 비교 차트(Z/백분위/원값·상관 히트맵) + CSV 다운로드 |
| 🌡️ 시장 온도계 | 🧠 심리(CNN 공포·탐욕, AAII, 신용융자, 미시간대) + 📌 자주 참고하는 매크로(기준금리·CPI·실업률·M2·기대인플레) + 거시(VIX·금리차·하이일드·금·유가) — 등급 없는 참고 지표 |
| 🇰🇷 한국 시장 | KOSPI 지수·PER/PBR/배당(σ 등급, ⚠️ 짧은 히스토리) + 미국 PER 비교 + 환율·금리 (정적 사이트 전용) |
| 🐋 큰손 추적기 | 버핏(버크셔)·국민연금·브리지워터·마이클 버리의 **13F 보유 종목**과 직전 분기 대비 변화(신규/매도/증감) — SEC EDGAR, 분기 갱신 (정적 사이트 전용) |
| ⏱️ 주기별 숫자 | 지표를 하루/일주일/한 달 갱신 주기로 묶어 "얼마나 자주 봐야 하나"를 보여줌 (정적 사이트 전용) |
| 📋 월간 점검 | 지난 한 달의 등급 변화·종합지수 이동·매크로 변화·큰손 새 공시만 모은 다이제스트 — "이 페이지 하나로 점검 끝" (정적 사이트 전용) |
| 📚 지표 가이드 | 초보자용 지표 해설(정의→비유→공식→해석→한계), CAPE vs 10년 수익률 **조건부 분위 팬차트**(커널 분위 회귀), FAQ |
| 🧭 투자 시작 가이드 | 무엇부터 할지 순서 + 🧮 Bogle 기대수익률 계산기 + 🎲 적립식 몬테카를로 시뮬레이션 + 📐 규칙·공식 치트시트(72의 법칙·4% 룰·100−나이·ERP) |
| 🧘 투자 규율 | 행동 편향 대처, 드로다운 차트, 시나리오 규칙, 매수 전 체크리스트 |

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

**큰손 13F** (🐋 큰손 추적기): SEC EDGAR의 무료·무키 JSON/XML을 파싱해 기관별 미국
상장주식 보유내역을 분기 단위로 수집합니다(`src/valueindex/config.py`의 `WHALES`에
CIK 한 줄 추가로 인물 확장). SEC 정책상 연락처가 담긴 User-Agent가 필요하며, EDGAR는
GitHub Actions에서는 열리지만 일부 샌드박스 IP는 차단되므로 파서는 픽스처로 검증하고
CIK는 **첫 Actions 실행이 라이브 검증**합니다. 13F는 미국 상장주식만 담아 국민연금은
미국 부분만 보입니다. CIK가 바뀌거나 막힌 큰손은 번들 샘플(⚠️ 예시)로 폴백합니다.

> 심리 소스 3종(CNN·AAII·FINRA)은 공식 API가 없어 공개 페이지/파일을 파싱합니다.
> 형식이 바뀌면 해당 지표만 캐시/샘플로 폴백하며, `scripts/check_live_sources.py`로
> 어느 소스가 살아 있는지 확인할 수 있습니다.

모든 소스는 [무료 키리스 접근]이며, 실패 시 `신선한 캐시 → 라이브 → 오래된 캐시 →
번들 샘플` 순서로 폴백합니다. 사이드바에서 각 소스의 데이터 상태를 확인할 수 있습니다.

## 테스트

```bash
pip install -e ".[dev]"
pytest                 # 오프라인 단위 테스트 (fixture 기반, 93개)
pytest -m e2e          # JS↔Python 패리티 (브라우저, playwright 필요)
pytest -m network      # 라이브 소스 스모크 테스트 (네트워크 필요, 수동 실행)
```

패리티 테스트는 정적 사이트의 JS 이식본(stats/quant/backtest/mc)이 Python 원본과
같은 값을 내는지 브라우저에서 검증합니다. 실행 전 `python scripts/build_site_data.py`와
`python scripts/build_parity_fixtures.py`가 필요합니다(CI에서 자동). 오프라인 강제
실행: `VALUEINDEX_OFFLINE=1 streamlit run app.py`

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

## 아키텍처 (정적 사이트)

```
GitHub Actions (매일 07:00 KST 또는 docs/ 커밋 시)
  refresh_sample_data.py   무료 소스에서 실데이터 수집 → sample_data/*.csv (+_meta.json)
  build_site_data.py       기존 valueindex 모듈로 계산 → docs/data/*.json
  → 커밋 → Pages 배포 (콜드 스타트 0초)

브라우저 (docs/*.html + assets/js)
  사전계산 JSON 로드 → 정적 뷰 즉시 렌더
  stats/quant/backtest/mc .js  사용자 입력에 반응하는 부분만 재계산
  (Python 원본과 패리티 테스트로 값 일치 보장)
```

- `docs/assets/vendor/plotly-cartesian-*.min.js`는 내장(vendor)이라 외부 CDN 의존이
  없습니다 — 오프라인·사내망에서도 동일하게 동작합니다.
- 모든 한국어 텍스트·색상·등급 밴드는 Python(`registry.py`, `stats.RATINGS`,
  `content/*.md`)에 단일 소스로 남고 `registry.json`/`content.json`으로만 전달됩니다.

## 알아둘 것

- 이 앱은 **장기 투자자용 상황판**입니다. 데이터가 월간/분기 갱신이라 매일 볼 이유가
  없고, 지표들은 단기 시장 방향을 예측하지 못합니다(📚 지표 가이드의 "할 수 있는 것 vs
  없는 것" 참고).
- 버핏지수는 비금융법인 주식 기준 근사치입니다(윌셔5000이 FRED에서 제거됨).
  시리즈 교체는 `src/valueindex/config.py`에서 한 줄로 가능합니다.
- FRED CSV 헤더가 다시 바뀌어도 파서가 두 형식(`DATE`/`observation_date`)을 모두
  처리합니다. 공식 FRED API 키 방식이 필요해지면 이슈로 남겨주세요.

## 알림 (등급 변화 시 GitHub 이슈)

매일 갱신에서 지표의 σ 등급 밴드가 바뀌면 워크플로가 **GitHub 이슈를 자동 생성**하고,
GitHub이 저장소 소유자에게 이메일을 보냅니다 — 서버·키 없이 "볼 필요가 생겼을 때만
연락 오는" 알림입니다. 확인 후 이슈를 닫으면 됩니다.

## 다크 모드

시스템 설정을 자동으로 따르고, 상단 바 오른쪽 끝의 🌙/☀️ 버튼으로 수동 전환할 수
있습니다 (선택은 브라우저에 저장, 차트 색상까지 함께 전환).

## 향후 아이디어

- 사용자 정의 백테스트 규칙 조합기
- 한국 버핏지수 정밀화 (KRX 시가총액 시계열 확보 시)
- 버핏 명언 타임라인 (당시 밸류에이션과 함께)

---

*이 앱은 교육용 정보 도구이며 투자 자문이 아닙니다. 모든 투자 판단과 책임은
본인에게 있습니다.*
