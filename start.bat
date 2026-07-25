@echo off
chcp 65001 >nul
title 루시
cd /d "%~dp0"
REM 로컬 신경망 목소리(MeloTTS) 서버가 꺼져 있으면 루시가 조용히 구글 목소리로 내려갑니다.
REM 그래서 루시를 켤 때 같이 켭니다. 이미 켜져 있으면 새 창은 포트가 잡혀 있어 곧바로 스스로 꺼집니다(무해).
if exist "D:\lucy-tts\venv\Scripts\python.exe" start "Lucy 목소리" /min "D:\lucy-tts\venv\Scripts\python.exe" tts_local_server.py
python agent.py
pause
