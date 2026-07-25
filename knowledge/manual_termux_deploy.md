# 스마트폰 Termux 안드로이드 루시(Lucy) 1-Click 구축 가이드

이 문서는 안드로이드 스마트폰의 **Termux** 환경에 **루시(Lucy) AI 비서** 웹 서버를 1-Click 스크립트로 설치하고 24시간 백그라운드로 구동하는 방법을 설명합니다.

---

## 1. 개요 및 사전 준비

안드로이드 스마트폰에 Termux 환경을 구축하면 PC 없이도 루시 웹 UI(`http://localhost:8765`)에 접속하여 AI 비서 기능을 사용할 수 있습니다.

### ⚠️ 필독: Termux 앱 다운로드 안내 (Google Play Store 금지)
> [!IMPORTANT]
> **구글 플레이 스토어(Google Play Store)의 Termux 앱은 2020년 이후 업데이트가 중단된 구버전입니다.**
> 패키지 업데이트(`pkg update`) 및 Python 설치 시 오류가 발생하므로 반드시 **F-Droid** 또는 **GitHub 공식 릴리즈 APK**를 설치해야 합니다.

- **F-Droid 다운로드**: [https://f-droid.org/packages/com.termux/](https://f-droid.org/packages/com.termux/)
- **GitHub APK 다운로드**: [https://github.com/termux/termux-app/releases](https://github.com/termux/termux-app/releases)
  - `termux-app_v0.118.1+github-debug_arm64-v8a.apk` (일반적인 스마트폰 기종)

---

## 2. Termux 1-Click 자동 설치 (Command Execution)

Termux 앱을 실행한 후 아래의 **원클릭 단축 명령**을 복사하여 Termux 터미널에 붙여넣고 실행합니다.

```bash
pkg update -y && pkg install -y git python curl && git clone https://github.com/user/my-agent.git ~/my-agent && cd ~/my-agent && chmod +x scripts/deploy_termux_android.sh && ./scripts/deploy_termux_android.sh
```

### 💡 스크립트 자동 처리 내용
1. `pkg update` 및 필수 패키지(`python`, `git`, `ffmpeg`, `libjpeg-turbo` 등) 자동 설치
2. `termux-wake-lock` 실행으로 스마트폰 화면 슬립 시 CPU 절전 모드 진입 방지
3. 저장소 클론 및 `keys/web_pin.txt` 보안 PIN 자동 생성 (6자리 숫자)
4. Python 의존성 라이브러리(`requests`, `Pillow`, `pypdf` 등) 자동 설치
5. 루시 웹 서버 (`python web.py`) 자동 구동

---

## 3. 웹 접속 및 PIN 로그인 (PIN Login & Web Access)

설치가 완료되면 Termux 화면에 접속 주소와 생성된 PIN 번호가 표시됩니다.

### 1) 접속 주소
- **스마트폰 자체 브라우저 (Chrome, Samsung Internet 등)**:
  `http://localhost:8765`
- **동일 Wi-Fi 공유기에 연결된 PC / 타 기기**:
  `http://<스마트폰_IP_주소>:8765` (터미널 출력 메시지 참조)

### 2) PIN 로그인
- 최초 웹 접속 시 6자리 PIN 입력 창이 나타납니다.
- Termux 화면에 출력된 PIN 번호를 입력하면 로그인 쿠키(`lucy_auth`)가 90일간 저장되어 이후 자동 로그인됩니다.
- PIN 번호 확인/변경: `cat ~/my-agent/keys/web_pin.txt`

---

## 4. 24시간 백그라운드 구동 및 배터리 최적화 해제 (Background Execution)

스마트폰 화면이 꺼져도 루시 서버가 종료되지 않고 24시간 안정적으로 작동하도록 설정합니다.

### 1) Termux Wake Lock 활성화
- Termux 터미널에서 다음 명령 실행:
  ```bash
  termux-wake-lock
  ```
- 알림창에 `Termux (wake lock held)` 상태가 표시되며 화면이 꺼져도 CPU가 켜진 상태를 유지합니다.

### 2) 안드로이드 배터리 최적화 중단 (필수)
1. 스마트폰 **[설정]** ➔ **[애플리케이션]** ➔ **[Termux]** 이동.
2. **[배터리]** 메뉴 선택.
3. 배터리 사용량을 **[제한 없음 (Unrestricted)]**으로 변경.

### 3) 백그라운드 백그라운드 프로세스 실행 명령
Termux 터미널을 닫아도 배경에서 계속 작동하게 하려면 다음과 같이 백그라운드 실행을 권장합니다:

```bash
cd ~/my-agent
nohup python web.py > web.log 2>&1 &
```

- **상태 확인**: `ps aux | grep python`
- **로그 확인**: `tail -f ~/my-agent/web.log`
- **서버 종료**: `pkill -f 'python web.py'`

---

## 5. 자주 묻는 질문 (FAQ) & 트러블슈팅

1. **`pkg update` 실행 시 404 또는 Repository Error가 발생하는 경우**:
   - `termux-change-repo` 명령을 실행하여 메인 미러 서버(Grimler / Cloudflare)로 변경 후 다시 시도합니다.
2. **외부 네트워크(LTE/5G)에서 접속하고 싶은 경우**:
   - Termux에 Tailscale을 설치하여 VPN 가상 IP로 접속할 수 있습니다 (`pkg install tailscale`).

---
*최종 작성일: 2026-07-26 (Lucy Termux Deployment Manual)*
