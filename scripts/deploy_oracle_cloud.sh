#!/usr/bin/env bash
# ==============================================================================
# Oracle Cloud / Linux VPS 1-Click Automated 24/7 Deployment Script for Lucy
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}======================================================"
echo -e "       Lucy AI Agent 24/7 Deployment Setup           "
echo -e "======================================================${NC}"

# 1. Check Root Privileges
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[오류] 이 스크립트는 root 권한으로 실행해야 합니다. (sudo ./deploy_oracle_cloud.sh)${NC}"
  exit 1
fi

INSTALL_DIR="/opt/my-agent"
REPO_URL="https://github.com/user/my-agent.git"

echo -e "\n${YELLOW}[1/6] 시스템 패키지 업데이트 및 필요 도구 설치 중...${NC}"
apt-get update -y
apt-get install -y --no-install-recommends \
    curl \
    git \
    wget \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    fonts-nanum \
    fontconfig \
    iptables \
    ufw || true

# 2. Install Docker & Docker Compose
echo -e "\n${YELLOW}[2/6] Docker & Docker Compose 설치 확인 중...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${CYAN}Docker 설치 중...${NC}"
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi

if ! docker compose version &> /dev/null; then
    echo -e "${CYAN}Docker Compose 플러그인 설치 중...${NC}"
    apt-get install -y docker-compose-plugin || true
fi

# 3. Install & Setup Tailscale VPN
echo -e "\n${YELLOW}[3/6] Tailscale VPN 설치 및 설정...${NC}"
if ! command -v tailscale &> /dev/null; then
    echo -e "${CYAN}Tailscale 설치 중...${NC}"
    curl -fsSL https://tailscale.com/install.sh | sh
fi

echo -e "${CYAN}Tailscale 데몬 시작...${NC}"
systemctl enable --now tailscaled || true

# 4. 방화벽 포트 개방 (8765)
echo -e "\n${YELLOW}[4/6] 방화벽 포트 8765 개방 중...${NC}"
if command -v iptables &> /dev/null; then
    iptables -I INPUT -p tcp --dport 8765 -j ACCEPT || true
fi
if command -v ufw &> /dev/null; then
    ufw allow 8765/tcp || true
fi

# 5. 프로젝트 디렉터리 준비
echo -e "\n${YELLOW}[5/6] Lucy 프로젝트 디렉터리 설정 (${INSTALL_DIR})...${NC}"
mkdir -p "${INSTALL_DIR}"
if [ -d ".git" ]; then
    echo -e "${CYAN}현재 경로의 파일들을 ${INSTALL_DIR}로 복사합니다...${NC}"
    cp -rf . "${INSTALL_DIR}/"
else
    echo -e "${CYAN}저장소에서 최신 코드 복사 중...${NC}"
    cp -rf "$(pwd)/"* "${INSTALL_DIR}/" 2>/dev/null || true
fi

cd "${INSTALL_DIR}"
mkdir -p memory keys uploads knowledge workspace

# PIN 확인 및 생성
if [ ! -f "keys/web_pin.txt" ]; then
    RANDOM_PIN=$(shuf -i 100000-999999 -n 1 2>/dev/null || echo "876543")
    echo "${RANDOM_PIN}" > keys/web_pin.txt
    echo -e "${GREEN}새로운 접속 PIN이 생성되었습니다: ${RANDOM_PIN}${NC}"
fi
PIN_VAL=$(cat keys/web_pin.txt | tr -d '\r\n')

# Python 의존성 설치
echo -e "${CYAN}Python 패키지 설치 중...${NC}"
pip3 install -q -r requirements.txt || true

# 6. Docker Compose 또는 systemd 서비스 시작
echo -e "\n${YELLOW}[6/6] 24/7 무중단 서비스 시작 중...${NC}"
if command -v docker &> /dev/null && [ -f "docker-compose.yml" ]; then
    echo -e "${CYAN}Docker Compose로 컨테이너를 실행합니다...${NC}"
    docker compose down 2>/dev/null || true
    docker compose up -d --build
else
    echo -e "${CYAN}systemd 서비스(lucy.service)로 등록하여 실행합니다...${NC}"
    cp -f lucy.service /etc/systemd/system/lucy.service
    systemctl daemon-reload
    systemctl enable --now lucy.service
fi

# Complete Summary
LOCAL_IP=$(hostname -I | awk '{print $1}' || echo "localhost")
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "Tailscale 미연결 (sudo tailscale up 실행 필요)")

echo -e "\n${GREEN}======================================================"
echo -e "         Lucy 24/7 배포가 성공적으로 완료되었습니다!     "
echo -e "======================================================${NC}"
echo -e "  📌 로컬 접속 주소    : http://${LOCAL_IP}:8765"
echo -e "  📌 Tailscale VPN 주소: http://${TAILSCALE_IP}:8765"
echo -e "  🔑 웹 접속 PIN 번호  : ${PIN_VAL}"
echo -e "  📁 설치 경로          : ${INSTALL_DIR}"
echo -e "------------------------------------------------------"
echo -e "  💡 Tailscale 로그인 방법: sudo tailscale up"
echo -e "  💡 상태 확인 방법      : docker compose ps  (또는 systemctl status lucy)"
echo -e "======================================================\n"
