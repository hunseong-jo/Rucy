---
name: project-gemini-chatbot
description: "Gemini API 웹 챗봇 — C:\\Users\\user\\gemini-chatbot, 표준 라이브러리만 사용, api_key.txt에 키 필요"
metadata: 
  node_type: memory
  type: project
  originSessionId: 61ee1de9-7c6e-4c74-b229-dafdaf493781
---

사용자가 살라드팜 게임과 별개로 **Gemini API 웹 챗봇**을 만듦 (2026-07-03).

- 위치: `C:\Users\user\gemini-chatbot\` — `server.py`(stdlib만, 의존성 0) + `index.html`(채팅 UI) + `start.bat`
- 실행: `start.bat` 더블클릭 → http://localhost:8899 자동 오픈
- 모델: `gemini-3.5-flash` (2026-06 기준 무료 등급). 429 한도 시 `gemini-3.1-flash-lite`로 교체 안내됨
- API 키: **발급·설정 완료** (2026-07-03) — `api_key.txt` 첫 줄에 저장됨 (매 요청마다 읽음, `GEMINI_API_KEY` 환경변수도 지원). 실제 Gemini 응답 스트리밍까지 end-to-end 검증 완료
- 구조: 브라우저가 대화기록 전체를 POST /api/chat → 서버가 Gemini `streamGenerateContent?alt=sse` REST 호출 → SSE로 텍스트 조각 중계
- 시스템 프롬프트/모델은 server.py 상단 상수로 수정. **주의: SYSTEM_PROMPT 변경 시 서버 재시작 필요** (api_key.txt와 달리 시작 시 한 번만 읽음)
- 성격: 사용자 요청으로 '항상 화난 무뚝뚝한 아저씨(츤데레)' 페르소나 적용·검증 완료 (2026-07-03). 반말+추임새(허 참/쯧쯧/에잉), 투덜대지만 정확한 답변, 욕설 금지
- 함정: Git Bash에서 curl -d로 한글 보내면 cp949로 전송돼 서버 UnicodeDecodeError — 테스트는 UTF-8 파일 + --data-binary 사용. 서버에 디코드 실패 방어 코드 추가됨
- 처음엔 Claude API로 물었으나 사용자가 "재미나이(Gemini) API"로 변경 요청. 무료 사용 희망.
