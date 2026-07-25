---
name: reference-unity-mcp-hang
description: DietCreature 에디터가 멈추고 클릭이 안 될 때 — Unity MCP 플러그인 연결 실패 폭주가 원인
metadata: 
  node_type: memory
  type: reference
  originSessionId: 9c1be722-5240-41d8-ad6b-dba7741abdd1
---

DietCreature 프로젝트에서 "화면은 보이는데 클릭이 안 되고 콘솔에 빨간 에러가 쏟아짐" 증상의 원인은 게임 버그가 아니라 **Unity MCP 플러그인(`com.ivanmurzak.unity.mcp`, manifest.json에 dependency)**이다.

대표 에러:
`HubConnection Failed to start connection. Error getting negotiation response from 'http://localhost:8080/hub/mcp-server'.`
(SignalR/HttpConnection NegotiateAsync 실패가 `UnitySynchronizationContext`를 통해 메인 스레드로 올라와 매번 거대한 스택을 `Debug.LogError`로 찍음 → 에디터가 멈춘 듯 입력 불가)

해결:
- 즉시: **AI Game Developer 창에서 MCP 서버 연결 Stop/Disconnect** (에러 메시지가 직접 안내함).
- MCP를 쓰려면 `localhost:8080` 서버를 먼저 띄운 뒤 연결.
- 안 쓰면 manifest.json에서 `com.ivanmurzak.unity.mcp` 제거(재추가 가능).

진단 팁: Editor.log가 이 MCP/소켓 에러로 도배되면, 실제 게임 예외는 `(at Assets/Scripts/...)`로 필터해 찾는다. 그게 없으면 게임 버그가 아니다. [[project_ui_redesign]]의 "Unity MCP 검증 함정"과 연결됨.

## MCP 재연결 시도 결과 (2026-06-28 세션12)
Claude Code에 `ai-game-developer` MCP 서버가 등록돼 있음: `Library/mcp-server/win-x64/gamedev-mcp-server.exe port=8080 client-transport=stdio`. 연결 사슬 = Claude Code ─stdio→ 서버(:8080 리스닝) ─SignalR /hub/mcp-server→ Unity 플러그인.
- 증상: `claude mcp list` = "Connected · tools fetch failed"(서버는 떠 있으나 Unity가 허브에 못 붙어 도구목록 못 가져옴). Editor.log에 13초마다 `McpManagerClientHub ... EnsureConnection Connection not available and auto-reconnect disabled for endpoint: /hub/mcp-server` 반복.
- ⚠️ **AI Game Developer 창에서 Connect 눌러도 연결 안 됨**(로그상 동일 경고 지속). 
- config `UserSettings/AI-Game-Developer-Config.json`의 `maxConsecutiveConnectionFailures:0`/`connectTimeoutSeconds:0`을 의심해 **10/15로 고치고 강제 재컴파일(스크립트 touch)로 도메인 리로드** → ConnectionManager GUID는 새로 생성됐으나(=config 재로드됨) **여전히 연결 실패**. 즉 설정값이 원인이 아니라 연결계층 자체 문제. (config는 10/15로 남겨둠 — 무한폭주 없이 제한.)
- **결론: 블라인드로 더 시도 말 것(에디터 멈춤 위험). 라이브 MCP가 꼭 필요하면 Unity 완전 재시작이 가장 확실**(서버는 떠 있으니 새 기동 때 keepConnected로 붙을 가능성). 코드 검증은 MCP 없이 Editor.log(`error CS`/예외 필터)+정적 추적으로 충분히 가능.

## 또 다른 증상: "Invalid editor window" 반복 에러 (2026-06-30 세션13)
- 에러: `Invalid editor window of type: com.IvanMurzak.Unity.MCP.Editor.UI.MainWindowEditor, title: Game Developer` (스택 `EditorApplication:Internal_CallDelayFunctions`). ~1.5초마다 반복 재발.
- 원인: 잦은 도메인 리로드(코드 수정/assets-refresh/script-execute 재컴파일) 후 MCP 플러그인의 'AI Game Developer(Game Developer)' 에디터 창 참조가 무효화 → delayCall이 매번 repaint 시도하며 에러 로그. **게임/코드/빌드 무관, 에디터 창만의 문제.** 이때도 MCP 도구 호출 자체는 계속 동작할 수 있음(완전 멈춤 직전 단계).
- 해결: **'AI Game Developer' 창을 닫기**(반복 멈춤). 지속/버벅이면 Unity 재시작. ⚠️ 창 닫으면 라이브 MCP 끊길 수 있으나 작업물은 디스크 저장돼 무손실.
- 함정: 이 세션엔 MCP가 정상 동작해 script-execute로 런타임 검증까지 했는데(시너지/팝업 레이아웃 측정), 그 직후 이 repaint 에러가 누적됨. 잦은 재컴파일을 유발하는 작업 뒤엔 예상되는 부작용.
