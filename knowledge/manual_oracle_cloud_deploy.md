# Oracle Cloud / VPS 24/7 Deployment & Setup Guide

이 문서는 **루시(Lucy) AI 비서**를 Oracle Cloud Free Tier VPS 또는 Linux 서버에 24시간 365일 무중단(24/7)으로 배포하고, **Tailscale VPN**과 **Web PIN**을 통한 보안 접속 환경을 구축하는 방법을 다룹니다.

---

## 1. 개요 및 배포 아키텍처

- **배포 목적**: PC가 꺼져도 Cloud VPS에서 24시간 상시 대기하며 웹/모바일 브라우저로 대화 및 지시 수행.
- **보안 모델**:
  - **Tailscale VPN**: 공용 인터넷 포트 개방 없이 가상 사설망(VPN)으로만 VPS에 접속.
  - **Web PIN (6자리)**: 인증받지 않은 기기의 접근을 차단하며 `lucy_auth` 쿠키로 기기 인증 관리 (`keys/web_pin.txt`).
- **무중단 이중화 지원**:
  - Docker Container (`docker-compose.yml`) 또는 systemd 배경 서비스 (`lucy.service`).

---

## 2. Oracle Cloud Free Tier VPS 생성

1. **Oracle Cloud 계정 생성 및 로그인**:
   - [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) 가입.
2. **인스턴스 생성 (Always Free)**:
   - **Ampere (ARM)**: `VM.Standard.A1.Flex` (4 vCPU, 24GB RAM - 권장) 또는 **AMD (x86)** `VM.Standard.E2.1.Micro`.
   - **OS**: Ubuntu 22.04 LTS / 24.04 LTS 또는 Oracle Linux 9.
   - **네트워크**: 기본 VCN 및 공용 IP 할당 선택. SSH 전용 키 저장.

---

## 3. 원클릭 자동 배포 (Automated 1-Click Deployment)

서버 접속 후 아래 명령을 통해 자동 배포 스크립트를 실행합니다:

```bash
# 1. 저장소 클론 및 이동
git clone https://github.com/user/my-agent.git /opt/my-agent
cd /opt/my-agent

# 2. 1-Click 배포 스크립트 실행 (root 권한)
sudo chmod +x scripts/deploy_oracle_cloud.sh
sudo ./scripts/deploy_oracle_cloud.sh
```

스크립트가 실행되면 다음 단계가 자동으로 완료됩니다:
1. `docker`, `docker-compose-plugin`, `tailscale`, `ffmpeg`, `fonts-nanum` 등 필수 패키지 자동 설치.
2. 8765 포트 방화벽 설정 및 `keys/web_pin.txt` 자동 생성.
3. Docker Compose 컨테이너 생성 및 24시간 무중단 시작.

---

## 4. Tailscale VPN 연동 및 접속 보안

공용 인터넷에 웹 포트(8765)를 직접 노출하는 대신 Tailscale을 통한 접근을 권장합니다.

1. **Tailscale 가입 및 인스턴스 등록**:
   ```bash
   sudo tailscale up
   ```
   - 출력되는 URL을 브라우저에 입력하여 Tailscale 계정에 VPS 등록.
2. **접속 주소 확인**:
   ```bash
   tailscale ip -4
   # 예: 100.115.xx.xx
   ```
3. **접속 방법**:
   - 모바일 폰이나 PC에 Tailscale 앱 설치 및 동일 계정 로그인.
   - 브라우저에서 `http://<Tailscale_IP>:8765` 접속.

---

## 5. Docker Compose & systemd 수동 관리법

### Docker Compose 명령어
```bash
# 서비스 상태 확인
docker compose ps

# 서비스 로그 조회 (실시간)
docker compose logs -f

# 서비스 재시작 및 재빌드
docker compose restart
docker compose up -d --build
```

### systemd 서비스 직접 사용 시 (`lucy.service`)
```bash
# 서비스 등록 및 시작
sudo cp lucy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lucy.service

# 상태 및 로그 확인
sudo systemctl status lucy.service
journalctl -u lucy.service -f
```

---

## 6. PIN 변경 및 보안 관리

- **웹 PIN 변경**:
  `keys/web_pin.txt` 파일의 6자리 숫자를 원하는 번호로 수정 후 서버 재시작.
- **연속 5회 실패 시 5분 자동 잠금**:
  브라우저 공격 방지를 위해 5회 오답 입력 시 IP/기기 잠금 적용.
- **인증 토큰 쿠키**:
  최초 1회 PIN 통과 시 90일간 쿠키가 유지되어 편리하게 접속 가능.

---

## 7. 크로스 플랫폼 동작 검증 (Linux & Windows)

- **경로 처리**: `portable.expand()`가 Linux `/home/user` 및 Windows `C:\Users\user` 자동 감지.
- **명령 실행**: `tools.run_powershell()`이 Windows에서는 PowerShell, Linux에서는 `/bin/bash`로 자동 동적 전환.
- **웹 서빙**: `web.py`가 `0.0.0.0:8765`에 바인딩되어 리눅스 및 도커 환경에서 안정적으로 동작.

---
*최종 Update: 2026-07-26 (Oracle Cloud VPS 24/7 Deployment Standard)*
