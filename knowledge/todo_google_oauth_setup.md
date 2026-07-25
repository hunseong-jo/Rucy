---
name: todo-google-oauth-setup
description: "✅완료(2026-07-13 세션50) — 루시 메일·캘린더 연동 켜짐. 연동 중 함정 3가지 기록"
metadata: 
  node_type: memory
  type: project
  originSessionId: de4fa6a0-93b0-4ac6-9c76-241e6c37d4a1
---

# ✅ 구글 연동 완료 (2026-07-13 세션50)

사용자가 OAuth 자격증명을 만들고 첫 승인까지 마쳐 **메일·캘린더가 실제로 켜졌습니다**.
E2E 확인: 메일 읽기(받은편지함 2건) · 캘린더 읽기 · **일정 쓰기→되읽기→삭제**(add_event → events().list → delete, 원상복구). 아침 브리핑의 일정·메일 요약도 이제 자동 작동.

- 토큰: `keys/google_token.json` (자동 갱신). 자격증명: `keys/google_credentials.json`
- 실제 프로젝트: **trusty-ether-502212-c3** (프로젝트 번호 853908767485)

## ⚠️ 연동 중 실제로 밟은 함정 3가지 (다음에 같은 오류가 오면 여기부터)

1. **403 access_denied ("테스터만 액세스")** = OAuth 동의 화면이 '테스트 중'인데 본인 이메일이 테스트 사용자로 미등록. → 콘솔 '대상(Audience)' → 테스트 사용자 → +사용자 추가.
2. **⭐프로젝트 어긋남** — 사용자가 자격증명은 자동 생성된 프로젝트(trusty-ether-…)에서 만들고, 콘솔에서는 직접 만든 다른 프로젝트(lucy-502212)를 보고 있어서 "인증 플랫폼이 구성되지 않음"이 떴다. **`google_credentials.json`의 `project_id` 필드를 읽으면 진짜 프로젝트를 바로 알 수 있다** → `?project=<id>` 붙인 콘솔 URL을 주면 헤매지 않음.
3. **accessNotConfigured (403)** — 승인은 됐는데 Gmail/Calendar **API가 '사용 설정' 안 됨**(API 켜기도 엉뚱한 프로젝트에서 했던 것). 오류 메시지 속 enable 링크(프로젝트 번호 포함)를 그대로 열어 '사용' 클릭, 반영에 몇 분 걸릴 수 있어 재시도 루프로 확인.

**권한 방침(불변):** 메일 = 읽기 전용(보내기 스코프 없음 — 되돌릴 수 없는 일). 캘린더 = 읽기+쓰기(넣기 전 y/N). 보내기가 필요해지면 SCOPES에 gmail.send 추가 + token 삭제 후 재승인 + **반드시 _confirm 게이트**.

관련: [[project-my-agent]] 세션47·50 절.
