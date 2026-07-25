# GitHub 이슈 자동 요약 및 알림을 위한 AI 비서 연동 방법 — 루시 자가 학습 노트 (2026-07-15)

> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니
> 수치·사실을 인용할 때는 출처를 함께 말할 것.

## 개요
AI 비서를 활용해 GitHub 이슈·PR·커밋을 자동으로 요약하고, 매일 아침 Slack 등 알림 채널로 전달한다. 주요 흐름은 GitHub Actions → Python 스크립트 → AI 프롬프트 → Slack 메시지다.

## 핵심 구성 요소
- **Hub Repo**: `works/` 디렉터리 아래에 각 프로젝트별 `project.yaml` 파일을 저장해 프로젝트 목록·우선순위 등을 관리.  
- **GitHub Actions**: 지정된 시간(예 09:00)에 워크플로우를 실행해 Python 스크립트를 호출.  
- **Python 스크립트**  
  - `project.yaml` → 프로젝트·상태 파악  
  - 각 프로젝트 레포에서 **오픈 이슈**, **PR**, **최근 커밋** 조회  
  - `current-pri…`(우선순위 파일)과 결합해 컨텍스트 생성  
  - AI(예 OpenAI GPT)에게 “오늘 해야 할 작업” 요약·우선순위 판단 프롬프트 전송  
- **Slack 연동**: AI 응답을 포맷팅해 `Slack Webhook` 혹은 Bot API로 전송.  

## 구현 흐름
1. **스케줄 트리거** – GitHub Actions가 매일 아침 실행.  
2. **컨텍스트 수집** – `project.yaml` + 레포 API(issues, pulls, commits).  
3. **프롬프트 설계** – “다음 정보를 바탕으로 오늘 가장 급한 작업을 1줄 요약하고, 우선순위를 매겨 주세요.”  
4. **AI 응답 처리** – 요약·우선순위 텍스트를 받아 Slack 메시지 형식으로 변환.  
5. **알림 전송** – Slack 채널에 자동 전송, 사용자에게 “오늘 이것부터 하세요” 제공.  

## 주요 프롬프트 설계 포인트
- **“한 곳에서만 쓰고 여러 곳에서 읽는다”** 원칙 적용 → 모든 프로젝트 정보와 최신 이슈·커밋을 하나의 프롬프트에 집합.  
- **우선순위 판단** – `current-pri…` 파일에 정의된 규칙(예 버그·긴급도) 을 프롬프트에 명시.  
- **간결 요약** – AI에게 1~2줄의 실행 가능한 작업 제안만 반환하도록 제한.  

## 보안·주의 사항
- AI 에이전트가 레포에 접근하려면 **PAT 토큰** 혹은 **SSH 키**가 필요(출처 2).  
- 로컬 AI 에이전트(예 OpenClaw) 사용 시 토큰이 `~/.clawdbot`에 평문 저장될 위험이 있음(출처 2).  
- 악성 스킬(341개 중 335개는 macOS 스틸러) 발견 사례가 보고돼, 신뢰할 수 있는 AI 플러그인만 사용해야 함(출처 2).  

## 참고 출처
- [요즘IT: “오늘 뭐부터 하지?” AI 비서 에이전트 만들기](https://yozm.wishket.com/magazine/detail/3692)  
- [LikeClaw: AI 에이전트로 GitHub 이슈 자동 생성하기](https://likeclaw.ai/ko/use-cases/github-automation)  
- [TwentyTwentyOne: GitHub App 기반 고급 자동화 기능 개발](https://twentytwentyone.tistory.com/585)
