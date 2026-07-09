@echo off
chcp 65001 >nul
REM ValueIndex 로컬 데이터 수집기 — 더블클릭으로 실행 (Windows)
REM 저장소 폴더 안에 두고 더블클릭하면 브라우저에 수집기가 열립니다.

cd /d "%~dp0"

REM 첫 실행이면 의존성 자동 설치 (사이트 재생성에 필요한 markdown 포함)
python -c "import valueindex, markdown" 2>nul
if errorlevel 1 (
  echo [ValueIndex] 첫 실행 - 필요한 패키지를 설치합니다...
  python -m pip install -e ".[site]"
)

echo [ValueIndex] 수집기 창을 엽니다...
python collector_gui.py

pause
