#!/usr/bin/env bash
# ==============================================================================
# Termux Android 1-Click Automated Deployment Script for Lucy AI Agent
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}======================================================"
echo -e "      Lucy AI Agent Termux Android Deployment        "
echo -e "======================================================${NC}"

# 1. Termux Wake Lock & Storage Setup
echo -e "\n${YELLOW}[1/6] Termux 백그라운드 유지를 위한 Wake Lock 설정...${NC}"
if command -v termux-wake-lock &> /dev/null; then
    termux-wake-lock || true
    echo -e "${GREEN}✓ Termux Wake Lock이 활성화되었습니다 (슬립 방지).${NC}"
else
    echo -e "${YELLOW}! termux-wake-lock 명령을 찾을 수 없습니다. (Termux:API 패키지 미설치 시 계속 진행)${NC}"
fi

# 2. Package Repository Update & Core Package Install
echo -e "\n${YELLOW}[2/6] Termux 패키지 업데이트 및 필요 도구 설치 중...${NC}"
pkg update -y && pkg upgrade -y
pkg install -y \
    python \
    git \
    ffmpeg \
    curl \
    wget \
    clang \
    libjpeg-turbo \
    libpng \
    freepats \
    optipng || true

# 3. Project Directory Setup
TARGET_DIR="${HOME}/my-agent"
echo -e "\n${YELLOW}[3/6] Lucy 프로젝트 디렉터리 준비 (${TARGET_DIR})...${NC}"

if [ "$(pwd)" != "${TARGET_DIR}" ]; then
    mkdir -p "${TARGET_DIR}"
    if [ -f "web.py" ]; then
        echo -e "${CYAN}현재 작업 디렉터리의 파일들을 ${TARGET_DIR}로 복사합니다...${NC}"
        cp -rf . "${TARGET_DIR}/"
    else
        echo -e "${CYAN}저장소에서 최신 소스코드를 다운로드/클론 중...${NC}"
        if command -v git &> /dev/null; then
            if [ -d "${TARGET_DIR}/.git" ]; then
                cd "${TARGET_DIR}" && git pull || true
            else
                git clone https://github.com/user/my-agent.git "${TARGET_DIR}" || true
            fi
        fi
    fi
fi

cd "${TARGET_DIR}"
mkdir -p memory keys uploads knowledge workspace scripts

# 4. Generate Security PIN if not existing
echo -e "\n${YELLOW}[4/6] 보안 PIN 확인 및 생성 중...${NC}"
if [ ! -f "keys/web_pin.txt" ]; then
    RANDOM_PIN=$(shuf -i 100000-999999 -n 1 2>/dev/null || echo "$((100000 + RANDOM % 900000))")
    echo "${RANDOM_PIN}" > keys/web_pin.txt
    echo -e "${GREEN}새로운 웹 접속 PIN이 생성되었습니다: ${RANDOM_PIN}${NC}"
fi
PIN_VAL=$(cat keys/web_pin.txt | tr -d '\r\n')

# 5. Install Python Dependencies
echo -e "\n${YELLOW}[5/6] Python 패키지 의존성 설치 중...${NC}"
python -m pip install --upgrade pip setuptools wheel -q || true
if [ -f "requirements.txt" ]; then
    python -m pip install -q -r requirements.txt || true
else
    python -m pip install -q requests Pillow pypdf || true
fi

# 6. Resolve IP & Launch Web Server
echo -e "\n${YELLOW}[6/6] 네트워크 IP 확인 및 서빙 준비...${NC}"
WIFI_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}' || ifconfig wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' || echo "127.0.0.1")

echo -e "\n${GREEN}======================================================"
echo -e "       Lucy Termux 배포 설정이 완료되었습니다!           "
echo -e "======================================================${NC}"
echo -e "  📌 로컬 스마트폰 접속 주소: http://localhost:8765"
echo -e "  📌 동일 Wi-Fi 타 기기 주소: http://${WIFI_IP}:8765"
echo -e "  🔑 웹 접속 PIN 번호       : ${PIN_VAL}"
echo -e "  📁 설치 경로               : ${TARGET_DIR}"
echo -e "------------------------------------------------------"
echo -e "  💡 백그라운드 실행 방법: nohup python web.py > web.log 2>&1 &"
echo -e "  💡 종결/재시작 방법   : pkill -f 'python web.py'"
echo -e "======================================================\n"

echo -e "${CYAN}지금 바로 루시 웹 서버를 시작합니다... (Ctrl+C 로 중단 가능)${NC}\n"
python web.py
