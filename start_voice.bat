@echo off
chcp 65001 > nul
REM 로컬 신경망 목소리 서버(MeloTTS). 이 창을 켜 두면 루시가 오프라인에서도 부드럽게 읽습니다.
REM 꺼져 있으면 루시는 조용히 구글 → 윈도우 목소리로 내려갑니다(오류 아님).
cd /d "%~dp0"
"D:\lucy-tts\venv\Scripts\python.exe" tts_local_server.py
pause
