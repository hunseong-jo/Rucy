---
name: project-ui-redesign
description: "UI/UX 파스텔+손글씨 리디자인 시스템 - 새 공통 스크립트/프리팹, 씬 배선, Unity 검증 함정"
metadata: 
  node_type: memory
  type: project
  originSessionId: b536ef95-85b2-4f9b-a2f6-a11c7ed817e6
---

## UI/UX 리디자인 (2026-06-28 세션6) — [[project-diet-creature-game]]

참고안 `초안.png` 기준 전면 리디자인 완료. 범위: **UI/UX만, 생물·알 아트는 유지**(절차생성 PNG 그대로, [[reference-creature-art]]).

### 새 공통 스크립트 (Assets/Scripts)
- **UITheme** (static): 파스텔 팔레트 + 폰트 + 절차생성 스프라이트(둥근 9-slice `RoundedBox`, `SoftShadow`, `WoodButton`/`StoneButton`/`Leaf`/`Cactus`/`Reed`/`Grass`/`Circle`). 런타임 1회 생성·캐시.
- **UITween + TweenRunner**: 외부 의존 없는 코루틴 트윈(OutBack/Cubic). 팝업 등장/알 부유/터치.
- **Popup**: 팝업 루트(딤+`Box`자식)에 붙이면 SetActive(true) 시 자동 슬라이드업+젤리팝+딤페이드. `boxName`으로 박스 지정(`Box`/`Card`/`BornBox`/`ConfirmBox`), `closeOnBackdrop`, `AnimatedClose()`. **전 매니저 팝업에 부착됨**(Hatchery 알선택/식사/꽉참/알구매, Shop 확인, CreatureDetailPopup 상세+확인, Collection 정보, Settings, FarmBackground).
- **UIPolish**: 각 Canvas에 부착 → 첫 프레임에 OS폰트→손글씨, 기본 `UISprite` 네모→둥근 스프라이트(풀스트레치 딤/배경 제외), **폰트 `FontScale=1.12` 전역 확대**(`UIPolishedMark`로 멱등). 정적 `PolishTree(Transform)` 제공 → **Popup.OnEnable이 호출**해 지연 생성 팝업도 폰트/크기/둥근 처리됨. `UIPolishSkip`로 제외.
- **BottomNavBar**: 통합 하단바(패널+HorizontalLayoutGroup+활성탭 강조). 프리팹 `Assets/Prefabs/BottomNav.prefab`. `OverrideTab(key,action)`(Hatchery에서 MEAL→식사기록).
- **TopStatusBar**: 골드/다이아 칩(좌상단)+설정기어(우상단), 앵커고정. 프리팹 `Assets/Prefabs/TopStatusBar.prefab`. 기어는 `SettingsPanel.Open()`(런타임 빌드가드 추가).
- **EggFloat**(Sine 부유)+**EggTouchReact**(누름 반응), **IntroDecor**(나뭇결 START/연마돌 로그인 버튼+잎사귀 테두리+Fredoka 타이틀), **FarmDecor**(잎 덩굴+지형별 선인장/갈대/풀/돌).

### 폰트
`Assets/Resources/Fonts/`: **NanumPenScript-Regular**(본문/손글씨), **Fredoka**(영문 타이틀). UITheme.Body/Title로 로드.

### 씬 배선 (모두 저장됨)
모든 씬 Canvas에 UIPolish + TopStatusBar + BottomNav 프리팹. Intro=IntroDecor, Farm=FarmDecor. 레거시 NavBar/BackButton/배경HUD 제거·위치조정(FarmBackground BgButton·FarmSpawner FarmCountHud 아래로 이동). HatcheryManager는 TopStatusBar 있으면 재화HUD 생략 + WireNav 코루틴으로 MEAL 오버라이드.

### ✅ 시각 검증 + 마무리 (2026-06-28 세션7)
- **배선 정적검증**: 도달 가능한 6씬(Hatchery/Farm/Collection/Shop/Inventory + Intro) 전부 UIPolish/TopStatusBar/BottomNav 정상. Intro는 의도적으로 상태바·네비 없음(타이틀)+IntroDecor. **MealCapture는 어떤 코드도 참조 안 하는 고아 씬**(식단 선택 팝업이 사진촬영 대체) → 리디자인 미배선이지만 도달 불가라 버그 아님(빌드세팅에만 등록, 향후 실제 사진기능 placeholder).
- **시각 캡처 방식**: `Assets/Editor/UITourCapture.cs`(임시, 작업 후 삭제함) — SessionState 플래그로 도메인리로드 견디며 플레이 중 6씬 순회, 각 씬 캡처 순간만 오버레이 Canvas→ScreenSpaceCamera 전환 후 메인캠 RT 렌더 1080x1920 PNG 저장. PlayFromIntro가 Intro부터 시작시킴. 45프레임 settle 후 캡처. 잘 작동.
  - ⚠️ **캡처 아티팩트 주의**: ScreenSpaceCamera 전환 시 월드 스프라이트(생물/FarmDecor 테두리)가 Canvas 평면 앞에 렌더됨 → 캡처본에선 생물이 UI 위에 겹쳐 보이고 Farm HUD가 테두리에 가린 듯 보임. **실제 게임 ScreenSpaceOverlay에선 UI가 항상 월드 위라 이런 겹침 없음.** Farm 관련 "버그"로 오인 말 것.
- **6씬 외형**: 파스텔 크림/하늘 배경 + NanumPen 손글씨 + Fredoka 타이틀, 둥근 카드/나무·돌 버튼, 하단 5탭(MEAL/도감/농장/상점/인벤토리) 활성탭 sage pill 강조, 좌상단 골드/다이아 칩 + 우상단 기어 — 전 씬 일관되고 완성도 높음.
- **수정한 진짜 버그**: ShopManager.ItemCard 아이콘(pivot 0,left x80 폭120 → 우측끝 x200)이 이름/가격 텍스트(x170 시작) 30px 침범 → 텍스트 시작 x 170→225로 이동(레어알/프리미엄알 등 첫 글자·가격 가림 해소). 배경 썸네일은 세로로 길어 preserveAspect로 좁아져 원래 안 겹쳤음.
- **무해한 미관조정**: FarmSpawner.BuildCountHud HUD x 30→70(좌측 장식테두리 회피, 위 아티팩트와 무관하게 여백 개선).
- ✅ (세션8 수정) Intro "로그인" 돌버튼 글자 겹침 해결: `IntroDecor.SkinButton`에 `boldLabel`+`spaceOut` 파라미터 추가. 한글 손글씨(NanumPen) 라벨은 합성 Bold 시 획이 뭉치므로 Bold 생략(영문 START는 Bold 유지) + `SpaceOut()`으로 글자 사이 thin space(U+2009) 삽입 → "로 그 인"으로 또렷이 분리. 플레이 캡처로 검증(임시 `Assets/Editor/IntroCapture.cs`는 작업 후 삭제). ⚠️IntroDecor.cs SpaceOut의 sb.Append에 실제 U+2009 문자가 들어있음(주석으로 표기).

### 🛠️ 사용자 피드백 5건 반영 (2026-06-28 세션7 후반)
1. **농장 수급(IncomeButton)을 설정 기어 좌측에 배치**: FarmIncome.BuildHud Place pos (-24,-150)→(-140,-32) anchor/pivot(1,1). 기어(TopStatusBar SettingsButton: pos -28,-36 size96) 좌측에 나란히.
2. **기분(MoodButton, Farm 씬 오브젝트)을 기어 아래로**: RectTransform anchoredPosition (-30,-30)→(-28,-148). 기어와 겹침 해소.
3. **상점 구매/적용 버튼 우측 잘림**: ShopManager ItemCard — VerticalLayoutGroup에 `padding=RectOffset(6,14,0,0)`(카드를 RectMask2D 안쪽으로) + 버튼 pos -30→-36, size 200→196. 둥근 모서리 온전히 보임.
4. **인벤토리 좌측상단부터 채움**: InventoryManager 그리드 `childAlignment UpperCenter→UpperLeft`.
5. **울타리를 진짜 말뚝 울타리로**: 기존 Fence_N/S/E/W = `Square`(1x1) 갈색틴트 단순막대였음. 절차생성 `Assets/Art/fence_h.png`(900x100, 가로/말뚝위로)·`fence_v.png`(100x1600, 세로/말뚝오른쪽) 신규 — 뾰족말뚝+가로대2줄, **흰색채움+0.6회색 외곽선**(FarmBackground.TintFences의 배경별 색 틴트가 그대로 적용돼 갈색/돌색 등으로 칠해짐). PPU100 FullRect Single. N/S=fence_h, W=fence_v, E=fence_v+flipX(말뚝 안쪽 향하게). transform scale(1,1,1) drawMode Simple, 위치 N(0,8)/S(0,-8)/E(4.5,0)/W(-4.5,0). Farm씬 저장됨. ⚠️생성 스크립트는 일회성(미저장)이라 수정 시 PNG 직접 보정.
- 전부 플레이 캡처로 검증 완료(투어 도구 재사용 후 삭제).

### ⚠️ Unity MCP 검증 함정 (중요)
- 오버레이 Canvas는 `screenshot-isolated`로 못 잡음(렌더러 없음) → **Canvas를 잠깐 ScreenSpaceCamera로 바꿔 RenderTexture에 렌더 후 PNG 저장** 방식 사용.
- 플레이는 `Editor/PlayFromIntro.cs` 때문에 항상 Intro부터 시작 → 특정 씬은 플레이 중 `SceneManager.LoadScene`.
- MCP로 진입 시 **자동 일시정지**됨 → `EditorApplication.isPaused=false` 필수. 게다가 에디터 포커스 잃으면 플레이어 루프 정지 → **`Application.runInBackground=true`** 켜야 Start/코루틴이 돈다. (이걸로 한참 헤맴: Start 미실행=Pause/runInBackground 문제)
