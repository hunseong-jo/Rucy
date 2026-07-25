@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 파이썬이 없으면 setup_check.py 자체가 못 돌아가므로 여기서 먼저 잡아냅니다.
where python >nul 2>nul
if errorlevel 1 (
    echo ============================================================
    echo   나만의 AI 비서 — 새 PC 점검
    echo ============================================================
    echo.
    echo   [없음] 파이썬이 설치돼 있지 않습니다. 이게 없으면 비서가 안 켜집니다.
    echo.
    echo     1. https://www.python.org/downloads/ 에서 설치
    echo     2. 설치 화면 맨 아래 'Add python.exe to PATH' 를 반드시 체크
    echo     3. 이 창을 닫고 setup_check.bat 을 다시 실행
    echo.
    echo   추가로 설치할 패키지는 없습니다. 파이썬 하나면 됩니다.
    echo.
    pause
    exit /b 1
)

python setup_check.py %*
pause
