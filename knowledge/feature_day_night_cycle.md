---
name: feature_day_night_cycle
description: "농장 밤낮 시스템. 실제 기기 시계 기반, 배경 안 건드리고 Canvas 오버레이로 해/달·틴트·별. 날씨와 독립 겹침."
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e3f6f28-2ea9-4139-b96c-c267a2acfd5f
---

농장에 밤낮 연출 추가(세션22, 2026-07-02). 배경(`Backdrop`)이 땅만 그려져 하늘이 없다는 제약을 [[project_ui_redesign]]의 오버레이 방식으로 우회.

**DayNightCycle.cs** (신규) + `FarmSpawner.cs`에서 `FarmWeather` 바로 뒤에 `AddComponent<DayNightCycle>()` 한 줄로 부착. [[feature_farm_weather]]의 `FarmWeather`와 동일 구조(Canvas 최하위 풀스크린 오버레이, `SetAsFirstSibling`, 전부 `raycastTarget=false`).

- **시간원**: 실제 기기 시계 `System.DateTime.Now` (별도 저장 불필요). 사용자가 실기기 시계 방식 선택함.
- **명암 틴트**: 시각 키프레임 8개(0/5/6.5/8/16/17.5/19/24시) 보간. 낮=투명, 새벽·노을=따뜻한 주황, 밤=남색 어둠(alpha~0.52).
- **해/달 아치**: 해 6~18시·달 18~6시, 진행도 0→1을 화면 좌→우, 고도는 sin, 지평선 근처 알파 페이드. 절차생성 소프트 원반 스프라이트(GenDisc) 공용.
- **별**: 밤에만 상단 55%에 20개, 개별 위상 트윙클, 새벽(4~6)·초저녁(18~20) 선형 페이드.
- **날씨와 독립 겹침**(사용자 선택): 밤에 비/천둥도 그대로. WeatherSystem 등과 커플링 없음, 자기완결.

**개발자 시간 조절**(같은 세션22 추가): 낮/노을/밤을 아무 때나 미리보게 관리자 모드에 시간 오버라이드 얹음.
- **GameClock.cs**(신규): 시간 SSOT. `DevOverride && adminMode`면 `DevHour`(0~24), 아니면 실제 시계. DayNightCycle이 `DateTime.Now` 대신 `GameClock.Hour` 사용.
- **DevTimeControl.cs**(신규, FarmSpawner 부착): 농장 하단 슬라이더(0~24)+"실시간" 버튼. `adminMode`일 때만 표시, 끄면 숨김+`DevOverride=false`로 실시간 복귀. 오버라이드는 저장 안 함(세션 한정)이라 개발자 모드 끄면 원복. 슬라이더 되먹임은 `_suppress` 가드.
- 관리자 모드 = `GameState.Settings.adminMode`([[feature_four_systems_s20]]의 재화치트와 동일 토글, SettingsPanel.ToggleAdmin). Unity Text가 이모지(🕐) 두부로 떠서 라벨은 "시간"으로 대체.

검증: Editor.log `error CS` 0개, 강제 동기 재컴파일 통과(밤낮+시간조절 둘 다). 이 세션에 **MCP(ai-game-developer) 미연결**이라 플레이모드 스크린샷 눈검증은 미완 → [[reference_mcp_stale_compile]] 참고. MCP 붙으면 관리자모드+슬라이더로 새벽/노을/밤 확인 예정.
