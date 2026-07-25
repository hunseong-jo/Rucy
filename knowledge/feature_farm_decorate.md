---
name: feature-farm-decorate
description: "농장 꾸미기 시스템 - 8x12 그리드에 8종(나무/호수/꽃+세션28 버섯/벤치/랜턴/풍차/우물) 배치, 상점 꾸미기 탭, 탭 회수. 세션28 DecorFx로 밤 점등/풍차 회전/벤치 생물 앉기 연출."
metadata: 
  node_type: memory
  type: project
  originSessionId: 0b880453-c193-4ef9-93dc-415751995e0c
---

## 농장 꾸미기(데코) 시스템 (2026-06-28 세션8) — [[project-diet-creature-game]] [[project-ui-redesign]]

식단게임 농장에 꾸미기 아이템 배치 기능 추가. 참고 `초안.png`(빨간 4x6 그리드, 나무1칸/호수2x2).

### 동작
- 농장 좌측 **'농장 꾸미기'** 버튼(보라, BgButton 아래 (30,-300)) → 편집 모드: **4열×6행 빨간 그리드**(월드) + 하단 보유 아이템 카드바 + '완료' 버튼.
- 카드 선택(보라 강조) 후 칸 탭 → 배치. 배치된 항목 탭 → **회수**(보유로 복귀, 재배치 가능). 사용자 결정: 탭회수 + 순수장식(생물 자유 이동, 충돌 없음).
- 배치물은 편집 모드 아니어도 농장에 월드 스프라이트로 그려짐(sortingOrder -10: 배경 위·생물 아래).

### 아이템 (세션28에 8종으로 확장)
- 원본 3종: 나무(tree) 1x2 **200골드**(세션28 300→200), 호수(lake) 3x3 300골드, 꽃은 5색 분화(아래, 각 **100골드**).
- **세션28 신규 5종**: 버섯(mushroom 1x1, 150) / 벤치(bench 2x1, 300) / 랜턴(lantern 1x2, 300) / 풍차(windmill 2x3, 500) / 우물(well 2x2, 800). footprint 좌하단 칸 기준 앵커(그리드 밖이면 Clamp 보정). 우물800은 후반 골드 싱크.
- 상점 상단 탭에 **'꾸미기'** 추가(알/배경/꾸미기/아이템). 카드 sub="N 골드 · 보유 N". 골드 차감 구매 → AddDecor.
- 아트: `gen_decor.py`(scratchpad, 소멸)로 도트 절차생성. 32px/칸 그린 뒤 NEAREST x4 업스케일. glow.png만 부드러운 그라데이션(밤 발광용, Bilinear). 임포트 설정(Sprite/Point/PPU100/무압축, glow만 Bilinear) script-execute로 일괄 적용.

### 살아있는 연출 — DecorFx.cs (신규, 세션28) [[feature-day-night-cycle]] [[feature-farm-weather]] [[feature-synergy-ecosystem]]
- FarmDecorate.RenderPlaced가 배치물마다 `DecorFx.Attach(go, type)`. 4모드: 랜턴/버섯=밤 글로우, 풍차=회전, 벤치=생물 앉기.
- **랜턴·버섯 밤 점등**: GameClock.IsNight일 때 글로우 표시. ⚠️핵심 함정: 밤 틴트(DayNightCycle SkyTint)가 ScreenSpaceOverlay 캔버스라 **월드 스프라이트 글로우를 덮어 죽인다**. 해결=달·별과 똑같이 **DayNight 루트 밑 UI Image**로 글로우를 그리고(틴트 위·버튼 아래), 꾸미기 월드좌표를 WorldToScreenPoint→ScreenPointToLocalPointInRectangle로 매프레임 추적. ⚠️실행순서: FarmDecorate.Start가 DayNightCycle.Start보다 먼저면 "DayNight"가 아직 없어 Canvas 직속에 생성됨→버튼 위로 샐 수 있음 → TickGlow에서 DayNight 생기는 즉시 1회 재부모화(`_dayNightParented`). 랜턴=상시(미세흔들림) α0.85, 버섯=은은한 맥동 α0.7. 글로우 UI는 꾸미기가 아닌 DayNight에 붙으니 OnDestroy에서 명시적 Destroy(누수 방지).
- **풍차 회전**: windmill_blades 자식 스프라이트를 z축 회전. 속도=WeatherSystem.Current별(Calm25~Thunder210 도/초), 날씨 바뀌면 MoveTowards로 서서히 가감속.
- **벤치 앉기**: CreatureWander에 Sitting 상태+`SitAt(pos,dur)`/`StandUp()`/`IsBusySitting` 추가. DecorFx가 주기적으로 근처(4유닛) 배회 생물 1마리를 저수지샘플링해 좌석으로 보냄(밤엔 안 함, 40% 스킵). 벤치 회수 시 OnDestroy→StandUp.
- 검증: 낮/밤 플레이 캡처로 랜턴 황금점등·벤치 생물착석·우물 옆 생물·풍차 회전(각도 50.9°→242.9°) 확인. 재부모화 glowUnderDayNight=2/Canvas직속=0 확인. 테스트 5종 배치·인벤 cleanup 원복. **실기기 확인은 다음 APK 빌드 후.**

### 꽃 5색 분화 (세션28, 사용자 요청)
- 기존 꽃 1종 → **5색**(분홍/노랑/보라/파랑/주황)으로 분화 + **살짝 작게**(투명 여백 ↑). 사용자 선택: 랜덤 아님, **색 직접 선택**(5종 개별 상점/카드).
- id: `flower`(분홍, **id 유지 → 구 '꽃' 세이브 호환**) + `flower_yellow/purple/blue/orange` 4종 신규. 전부 1x1·**100골드**(세션28 300→100). 이름 분홍꽃/노랑꽃/보라꽃/파랑꽃/주황꽃. 카탈로그 총 12종.
- 아트: `gen_flowers.py`(scratchpad). 64px 로직→NEAREST x4=256px, 5꽃잎+꽃술+줄기+잎2. 노랑꽃만 꽃술을 주황으로 구분. 기존 flower.png는 캔버스의 90%→~78%로 줄여 렌더 크기 축소. 임포트 Sprite/Point/PPU100/무압축.
- 검증: 카탈로그 12종·5색 스프라이트 로드·id매치 확인, 5색 나란히 배치 플레이 캡처(색·축소 확인). 테스트 배치·지급분 cleanup(좌표 row6·AddDecor -1로 원복, 사용자 기존 flower owned=1 보존).

### 편집 카드바 가로 스크롤 (세션28, 8종 확장 후 버그픽스)
- 아이템 8종이 되며 하단 카드바(고정폭 1040)를 넘쳐 뒤쪽(풍차·우물) 카드에 접근 불가 → **ScrollRect로 교체**. 구조: DecorBar(ScrollRect, horizontal only, Elastic) → Viewport(RectMask2D) → Content(HorizontalLayoutGroup + ContentSizeFitter horizontal=PreferredSize). CreateDecorCard를 content에 붙임. 카드는 LayoutElement preferredWidth 190 유지. 검증: 8장 contentW=1736>viewportW=1040 overflow, 끝까지 스크롤해 풍차·우물 카드 노출 확인. **아이템 더 늘려도 자동 스크롤됨.**

### 구조 (전부 신규/수정)
- **DecorCatalog.cs**(신규 static): Decor{id,name,price,w,h} 3종 + 그리드 상수 `Cols=4,Rows=6,Cell=1.95f,OriginX=-3.9f,OriginY=-4.2f`(농장 울타리 안쪽 가용영역 x[-3.9,3.9]·y[-4.2,7.5]에 맞춤). CellCenter/FootprintCenter/WorldToCell 헬퍼. 스프라이트 Resources/Decor/<id>.
- **아트**: `Assets/Resources/Decor/{tree,lake,flower}.png` 256px 절차생성(귀여운 둥근 톤, [[reference-creature-art]]와 동일 방식, 생성스크립트 미저장). 코드에서 footprint*Cell*0.9로 스케일.
- **SaveData.cs**: `DecorOwn{type,count}` + `DecorItem{type,col,row}`, SaveData에 `decorInventory`·`placedDecor` 리스트.
- **GameState.cs**: PlacedDecor/DecorOwned/AddDecor/DecorPlacedCount/DecorAvailable/PlaceDecor/RemoveDecor.
- **ShopManager.cs**: "decor" 탭+Populate case+AskBuyDecor/DoBuyDecor.
- **FarmDecorate.cs**(신규, Canvas에 부착·Farm씬 저장됨): 좌측버튼/그리드(월드 흰1px스프라이트 라인 빨강 order50)/편집UI/배치·회수 입력(Camera.ScreenToWorldPoint, EventSystem.IsPointerOverGameObject로 UI탭 무시)/RenderPlaced/occupancy. 편집 중 FarmTouch·FarmCreatureBar·BgButton·FarmCountHud 숨김.

### 후속 조정 (세션8 후반)
- 생물 수 HUD(FarmSpawner.BuildCountHud)가 꾸미기 버튼과 같은 y(-300)라 가려짐 → `(35,-395)`로 내려 좌측 세로 순서 배경→꾸미기→생물수 정리.
- **농장 수용 상한 30마리**: `GameState.MaxFarmCapacity=30`, FarmCapacity=`min(30,10+exp*5)`. `CanExpandFarm`(상한 미만) 추가. ShopManager.AskBuyFarmExpansion이 상한 도달 시 "이미 최대(30마리)" 단일확인으로 막아 다이아 낭비 방지.
- ⚠️ 저장본의 placed/inventory 데이터는 사용자가 직접 배치한 실데이터일 수 있음 — 검증용으로 주입했어도 지우기 전 script로 내용 확인할 것(위치로 구분).

### 배경별 레이아웃 (세션8 후반)
- 요청: 배경마다 꾸미기 따로. 초원에서 꾸민 건 초원에서만 보이고, 늪지/사막 가면 사라지고, 초원 복귀 시 복원. 저장됨.
- 결정(수정됨): **보유 수는 공유 소모 자원**. **레이아웃만 배경별 분리**, 배치 가능 수는 **전체 배경 통틀어** 차감. DecorAvailable = owned - 모든배경 배치총합. (처음엔 배치가능수도 배경별로 했다가 "늪지에 놨는데 초원에서 갯수 안 줆" 버그 신고로 전체 합산으로 정정 — 같은 나무를 두 배경에 동시 배치 불가, 한 곳에 놓으면 소모됨.)
- 구현: `DecorItem.background` 필드 추가. `GameState.PlacedDecorHere()`(현재 배경 필터, 렌더/충돌/회수용). PlaceDecor는 CurrentBackground 스탬프. **DecorPlacedCount는 전체 배경 합산**(보유 공유). 구버전 저장본은 `BackfillDecor`로 빈 background를 현재 배경에 이관(Data 로드 시). FarmDecorate의 RenderPlaced/FindPlacedAt/BuildOccupancy가 PlacedDecorHere() 사용. 배경 변경 시 `FarmBackground.ApplyAndSet`가 `FarmDecorate.RefreshDecor()` 호출해 즉시 다시 그림(상점에서 바꾸면 농장 재진입 Start에서 반영). 편집 중엔 BgButton 숨겨져 배경변경 불가(단순화).
- 검증: 플레이 캡처 3장(초원 꾸밈→늪지 빈→초원 복원) 정상.

### 검증
- 플레이 캡처(임시 Assets/Editor/DecorCapture.cs, 작업후 삭제)로 농장 편집모드(그리드+배치된 나무/호수/꽃+카드 보유수 정확)와 상점 꾸미기 탭 둘 다 확인. 컴파일0. 테스트로 주입한 보유/배치 데이터는 cleanup 스크립트로 초기화함.

### 그리드 세분화 8x12 (2026-07-03 세션24)
- 사용자 요청으로 4x6→**8x12**(Cell 1.95→0.975, 전체 영역 7.8x11.7 동일). 장식은 footprint 유지 → **절반 크기**로 렌더(사용자 선택: 더 많이 배치 우선).
- footprint 재조정(사용자 지정): **나무 1x2 / 호수 3x3 / 꽃 1x1**. 나무 아트도 128x256 세로 1:2로 재생성(긴 기둥+뿌리 벌어짐, 원본 팔레트 유지, PNG만 교체·meta 유지).
- ⚠️ 사용자가 에디터로 **동시에 플레이 중**일 수 있음 — 테스트 배치 전 placedDecor 스냅샷 찍고, 회수는 좌표로 내 것만 제거할 것(전체 삭제 금지).
- 구버전 저장 호환: `SaveData.decorGridVersion`(0=구, 2=현행) + `GameState.BackfillDecor`에서 좌표 x2 이관(좌하단 앵커 보존).
- 검증: 인접 반 칸 나무 2그루/우상단 (7,11) 배치/2x2 호수/그리드 라인 22개 플레이 캡처 확인 후 테스트 배치 회수(보유수 원상복구).
