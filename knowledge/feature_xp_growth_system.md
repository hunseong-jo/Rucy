---
name: feature-xp-growth-system
description: "성장을 경험치제로 개편 — 아이템 1개=+500xp, 레벨업 필요치 1000+200/레벨, 카드 경험치 바, 날씨 자동 경험치(분당5, 매칭 식단 ×2). E2E 검증 완료."
metadata: 
  node_type: memory
  type: project
  originSessionId: e22249c8-f63f-4f50-bbb7-336a86f9a495
---

# 경험치 성장 시스템 (2026-07-04 세션27, E2E 검증 완료)

사용자 설계로 [[feature-creature-evolution]]의 "아이템 1개=1레벨"을 경험치제로 개편.

## 규칙 (단일 출처 = GrowthCatalog)
- **커브**: 레벨 n→n+1 필요 경험치 = `XpForLevel(n) = 1000 + 200*(n-1)` (1→2는 1000, 2→3은 1200…9→10은 2600, 총 16,200xp).
- **아이템**: 1개 = `XpPerItem`(500)xp. `Feed`가 `AddXp` 호출. `AddXp`가 레벨업 루프(초과분 이월)+진화(레벨10, xp=0) 전부 처리.
- **날씨 자동 경험치**: 농장 화면에 있는 동안만(오프라인 없음 — 아이템 가치 보존, 의도된 결정). `WeatherSynergy.BaseXpPerMin=5` × `XpMultiplier`: 햇살→채식×2 / 노을→육류×2 / 비·천둥→인스턴트×2(천둥은 골드↓ 경험치↑ 트레이드오프) / 눈→디저트×1.5 / 함박눈→디저트×2. FarmIncome이 생물별 누적(_xpEntries), 진화 시 hatch 사운드+축하 팝업(이/가 조사 포함)→확인 시 씬 리로드. 시크릿·진화체 제외.
- **데이터**: `CreatureData.xp`(신규, 구세이브 기본 0).

## UI
- **경험치 바**: CreatureDetailPopup 레벨 행 아래(y-790, 620×36) 트랙(PanelEdge)+채움(Sage)+`현재/필요` 텍스트. 진화체는 숨김. 정보 행 간격을 -605/-670/-735로 압축해 자리 확보(원래 -822에 놓으면 주기 버튼(-830~)과 겹쳐 가려짐 — **버튼 뒤에 깔린 원인이었음**).
- 주기 버튼 라벨에 "+500" 표기. **카드 열린 동안 0.5초마다 RefreshGrowth**(Update, stage 변화 시 전체 Refresh) → 바가 실시간으로 참.

## 함정/발견
- **order 100 캔버스끼리 겹침**: 상세 카드가 열린 채 자동 진화 팝업이 뜨면 SetAsLastSibling에도 불구하고 팝업이 카드 뒤에 깔렸음(같은 sortingOrder 서브캔버스 tie가 계층순을 안 따름). → FarmIncome이 진화 팝업 전에 `CreatureDetailPopup.Close()`(public으로 변경) 호출로 해결.
- **ConfirmPopup은 캔버스당 1인스턴스 공유**(Get이 GetComponent) — 상세팝업과 FarmIncome이 같은 걸 씀. detail.Open()이 confirm.Hide() 하는 것 주의.
- graphicsApiMask 무해 에러가 주기적으로 찍힘 → **Error Pause 켜져 있으면 플레이가 멋대로 멈춰 트윈/코루틴 동결**. `ConsoleWindow.SetConsoleErrorPause(false)` 리플렉션으로 끔.
- 플레이 시작 씬이 MainMenu로 고정돼 있어 씬 열고 플레이해도 소용없음 → 플레이 중 `SceneManager.LoadScene("Farm")`.

## 검증(전부 통과)
커브/이월/진화 단위테스트, 날씨 전환 시 율 재계산(함박눈 디저트10↔햇살 채식10), 실시간 누적, 바 렌더 스크린샷, 자동 진화 팝업 E2E, 카드 열린 채 실시간 갱신(27→33). 테스트로 진화시킨 dev세이브 생물 2마리(마카롱/컵케익)·도감 진화횟수 원복함(xp 잔여 ~30은 무해). **실기기 APK는 이 기능 이전 빌드** — 다음 빌드에 포함+스플래시도 같이 실림.

관련: [[feature-creature-evolution]] [[feature-farm-weather]] [[project-release-prep]]
