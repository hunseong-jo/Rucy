---
name: feature-achievements-dietreport
description: "도전과제(누적, 일일퀘스트 없음)+식단 리포트 팝업+인벤토리 3탭 개편 완료 (2026-07-04 세션25)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 9ca63411-2201-48d1-b953-3f6ff440d717
---

## 도전과제 + 식단 리포트 + 인벤토리 3탭 (2026-07-04 세션25)
[[todo-feature-backlog]]에서 진행. **사용자 방침: 일일 퀘스트는 만들지 않음**(짧은 시간 힐링 게임이라 숙제성 콘텐츠 지양, [[feedback-no-daily-quests]]) — 누적 도전과제만.

### 데이터 (SaveData/GameState)
- `MealRecord{date(yyyy-MM-dd), category(-1균형/0~3)}` + `SaveData.mealLog`: **부화해도 리셋 안 되는 영속 식사 로그**. `GameState.RecordMeal`(단일 훅, HatcheryManager.ApplyMeal 경유로 사진분석/관리자수동 모두 커버)이 dietCounts와 별개로 append.
- `SaveData.claimedAchievements`: 수령한 도전과제 id만 저장(진행도는 매번 계산).
- GameState 통계 헬퍼: `TotalMealsLogged / TotalHatches(부화+자연발생 합) / SpeciesDiscovered / SecretDiscovered`.

### AchievementBook.cs (알 화면 우측 트로피 버튼, 가이드북 아래 y=-260)
- 18개 누적 과제(식사 1/10/50/100끼, 만남 1/5/15/30, 도감 5/15/30/50종, 시크릿 1/4종, 누적골드 1k/10k, 꾸미기 5배치, 농장확장 1회). 보상 골드 50~500 또는 다이아 5~10 — **다이아 2차 획득수단 일부 해소**.
- 진행바+받기 버튼(달성 시 Sage 활성), 수령 완료 라벨, 버튼에 수령가능 빨간점 뱃지. Def struct+Func<int> current 패턴이라 한 줄 추가로 과제 확장.

### DietReport.cs (트로피 아래 그래프 버튼 y=-372)
- 팝업 세로스크롤: ①최근 7일 요일별 미니 바(오늘 강조) ②이번 주 분류별 가로 바 ③전체 누적 스택바+범례(N끼/%) ④규칙 기반 한 줄 코멘트(힐링 톤, 인스턴트40%↑→채소 권유 / 채식40%↑→칭찬 등).
- 분류색: 채식 그린/육류 웜레드/인스턴트 퍼플/디저트 핑크/균형 블루. 빈 기록 상태 문구 처리.

### 인벤토리 3탭 개편 (InventoryManager 재작성)
- 상단 탭 생물/알/꾸미기(활성=Sage). 생물=기존 보관 그리드(상세/별명 유지), 알=구매 보유 레어/프리미엄(기본알 무제한이라 제외, 0개면 빈 안내), 꾸미기="보유 N개 · 배치 M" 카드. **배경은 표시 안 함(사용자 지시, 농장 배경픽커가 담당)**.
- 함정 수정: 런타임 Destroy는 프레임 끝 처리라 같은 프레임 중복 Build 시 옛 InvRoot가 살아남음 → Build에서 InvRoot 이름 전수 제거로 보강.

### 기타
- 아이콘 trophy.png/chart.png PIL 생성(Icons/), TextureImporter Sprite 설정. 가이드북에 "도전과제 & 식단 리포트" 카드 추가(8페이지).
- 검증: 플레이모드 E2E — 버튼/뱃지 표시, 18카드 진행도, 받기(+50골드·수령완료 전환·중복차단), 리포트 4섹션+스크린샷 레이아웃 확인(요일 바 라벨 겹침 1회 수정), 인벤 3탭 전환·알/꾸미기 카드. 세이브 백업→복원 완료(수령 기록 0 유지).
- ⚠️ mealLog는 이 세션부터 쌓임 — 과거 식사는 소급 안 됨(dietCounts는 부화 시 리셋이라 복원 불가).

### ⚠️ 지연 생성 UI 폰트 풀림 함정 (버그픽스, 같은 세션)
- **증상**: 인벤토리 탭 전환 시 폰트가 시스템체로 풀림. **원인**: UIPolish(손글씨 폰트/둥근 이미지/×1.12 확대)는 씬 첫 프레임에만 돌고, Popup.OnEnable만 재적용 → 패널이 켜진 채/씬 진입 후 재생성된 Text는 미처리.
- **규칙**: 런타임에 UI를 재생성하는 코드는 생성 직후 `UIPolish.PolishTree(루트)` 호출(멱등, Sfx.WireButtons 포함). InventoryManager.Build / AchievementBook.RebuildList(받기 후) / DietReport.Rebuild에 적용, 플레이모드 폰트 전수검사(badFont=0) 검증.

### 버튼 아이콘 리디자인 (같은 세션 후속 요청)
- **UITheme.IconButton 신설**: 아이콘+라벨 가로형 둥근 버튼(그림자 포함, 배치까지 일괄). 새 아이콘 버튼은 이걸 쓸 것.
- 적용 3곳: 출석(132² 노랑, calendar 아이콘 위+라벨 아래), 농장 '배경'/'농장 꾸미기'는 **후속 요청으로 라벨 없는 아이콘 전용 80² 정사각 버튼**(scenery 초록 / decorate 화분 보라, y -210/-302). 아이콘 PIL 생성(Icons/calendar·scenery·decorate.png). UITheme.IconButton은 현재 미사용이나 아이콘+라벨형 버튼용으로 유지.
- **함정 수정**: AddShadow는 형제 오브젝트("이름_Shadow")라 버튼만 SetActive(false)하면 그림자가 남음 → FarmDecorate 편집 진입/종료에서 DecorateButton_Shadow·BgButton_Shadow 함께 토글(플레이모드 검증 완료). 앞으로 IconButton/AddShadow 쓴 버튼을 숨길 땐 그림자도 같이.
- 참고: 세션 중 사용자 실플레이로 골드 13085(대기골드 수령+출석 3일차) — 테스트 오염 아님.
