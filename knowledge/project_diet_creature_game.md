---
name: project-diet-creature-game
description: 식단 기반 생명체 육성 유니티 모바일 게임 프로젝트 기획
metadata: 
  node_type: memory
  type: project
  originSessionId: 03e52531-e905-46ba-bfab-cfaa92401774
---

## 프로젝트: 식단 기반 생명체 육성 게임 (Unity 모바일)

시작일: 2026-06-26

### 핵심 컨셉
- 사용자가 식사를 10번 촬영하면 식습관 데이터 기반 생명체 탄생
- 태어난 생명체들이 농장 울타리 안에서 돌아다니는 힐링 게임

### 주요 기능
- **식습관 반영**: AI(Unity Sentis)로 음식 사진 분석 → 생명체 특징(색상, 형태, 성격) 결정
- **감정 교류**: 매일 접속 시 기분 상태 입력 → 생명체 표정 변화(웃음, 인상 등)
- **도감 시스템**: 언제, 어떤 음식으로 탄생했는지 히스토리 기록

### 개발 방향
- **디자인**: 모듈형 시스템 (기본 몸체 + 특징 파츠 + 식재료별 색상 조합)
- **구현**: 2D 스프라이트 애니메이션 + 상태 머신(FSM)

### Why:
힐링 + 일상 기록을 결합한 독창적인 모바일 게임. 식습관 데이터를 게임화.

### How to apply:
작업 시 이 기획을 기반으로 유니티 구현 방향 제안. Unity Sentis, FSM, 2D 스프라이트 위주로 접근.

### 개발 환경 (2026-06-26 확인)
- Unity 에디터: **6000.4.5f1 (Unity 6.4)**, 위치 `D:\6000.4.5f1\Editor\Unity.exe`, URP
- Unity Hub 설치됨, Unity 계정 연동됨 (userInfoKey.json 존재)
- 참고용 기존 프로젝트: `C:\Users\user\Documents\OnlyUpRat` (2D 풀세트 + URP, 같은 스택 재사용 가능)
- 로컬 도구: .NET 9 SDK 설치됨 / Python·node·uv 미설치 / git 2.54
- 식단 게임용 Unity 프로젝트는 **아직 미생성**

### 백업 (2026-06-26 세션3)
- 작업 원본: `C:\Users\user\Documents\DietCreature` (Unity+MCP 연결됨, 여기서 작업)
- Google Drive 백업본: `G:\내 드라이브\바이브코딩\02_게임개발\DietCreature` (robocopy로 복사, Library/Temp/Logs 캐시 제외 ~30MB)
- 백업 명령: `robocopy <src> <dst> /E /XD Library Temp Logs obj .git Build Builds .vs` (exit code 1=정상). "구글드라이브에 다시 복사" 요청 시 갱신
- 주의: 백업본을 직접 Unity로 열지 말 것(동기화 충돌). 원본에서만 작업. Git 미설정(원하면 세팅 가능)

### Claude ↔ Unity 연결 방식 (결정: 2026-06-26)
- 사용자가 **Unity MCP 연동**(실시간 에디터 제어) 선택
- 1순위: **공식 Unity MCP 서버** (Unity 6.4 내장, `com.unity.ai.assistant` 패키지 필요, Project Settings > AI > Unity MCP Server > Integrations > Claude Code > Configure로 자동 연결). 단 Unity 구독 필요 가능성 있음
- 무료 대체안: **IvanMurzak/Unity-MCP** (완전 무료, 모든 라이선스, .NET 기반 — dotnet 설치돼 있어 가능)
- 연결 순서: ① 식단 게임 프로젝트 생성 → ② MCP 서버 켜기 → ③ Claude Code 자동 연결
- **무료 MCP 결정 확정**: IvanMurzak/Unity-MCP (패키지명 `com.ivanmurzak.unity.mcp`)

### 진행 상황 (2026-06-26 세션2, 이전 세션 튕김 복구)
- 프로젝트 위치: `C:\Users\user\Documents\DietCreature` (Unity 6000.4.5f1, **Built-in 렌더파이프라인** — URP 아님, 사용자가 Built-in 유지 결정)
- manifest.json에 `com.ivanmurzak.unity.mcp` 0.82.2 + openupm 스코프레지스트리 추가 완료
- 2D 풀세트 설치됨: 2D Animation, Pixel Perfect, PSD Importer, Cinemachine, Input System
- Assets 폴더 비어있음 (씬·스크립트·아트 아직 없음)
- **MCP 연결 방법**: Unity 열어 플러그인 임포트 → `Library/mcp-server/win-x64/gamedev-mcp-server.exe` 생성됨 → `claude mcp add ai-game-developer "<exe>" port=8080 client-transport=stdio` → Claude Code 재시작
- 플러그인 요구사항: 프로젝트 경로에 공백 금지 (현재 경로 OK)
- node 미설치라 unity-mcp-cli(npm)는 사용 안 함, 바이너리 직접 등록 방식 사용
- 바이너리 생성됨: `Library/mcp-server/win-x64/gamedev-mcp-server.exe` (101MB)
- Claude Code에 MCP 등록 완료: `claude mcp add ai-game-developer --scope user -- "<exe>" port=8080 client-transport=stdio` → `C:\Users\user\.claude.json` 기록됨

### MCP 연결 트러블슈팅 (중요, 2026-06-26 세션2)
- 증상: `claude mcp list`에서 `Connected · tools fetch failed`. 서버 로그에 `No connected clients. Retrying [1/10]` → tools/list 타임아웃
- 원인: Unity 플러그인이 **Cloud 모드**라 로컬 서버(8080)에 연결 안 함. 설정파일 `UserSettings/AI-Game-Developer-Config.json`의 host가 localhost:24079(포트 불일치), connectionMode=Cloud
- 해결: Unity 종료 후 `AI-Game-Developer-Config.json` 수정 → `connectionMode: "Custom"`, `host: "http://localhost:8080"`, `keepServerRunning: false` (Claude가 stdio로 서버 띄우므로 플러그인은 자체서버 끔). keepConnected=true 유지
- 토폴로지: Client(Claude, stdio) → Server(8080) ← Plugin(Unity, streamableHttp로 localhost:8080 접속)
- **연결 검증 완료 (2026-06-26 21:56)**: 설정 수정 후 임시 서버(streamableHttp 8080) 띄워 테스트 → 플러그인 접속 + 버전 핸드셰이크 성공 로그 확인. 설정 정확함
- 주의: Unity MCP 도구 쓰려면 Unity 에디터가 켜져 있어야 함 (플러그인이 서버에 붙어야 도구 노출됨)

### ✅ MCP 연결 최종 검증 완료 (2026-06-26 세션3, 재접속 후)
- Claude Code 재시작 후 `mcp__ai-game-developer__*` 도구 로드 확인됨
- `scene-list-opened` 실제 호출 성공 → Unity 에디터 실시간 제어 가능 상태 확정
- 현재 씬: 이름 없는 새 씬 (미저장), 루트 오브젝트 2개(기본 카메라+라이트), Assets 폴더 비어있음
- **다음 단계: 실제 게임 개발 착수** (씬 구성/생명체 프리팹/식습관 데이터 구조 등)

### 🩷 2D 스프라이트 프로토타입 완료 (2026-06-26 세션3)
- **중요 사용자 선호**: 게임은 **2D 스프라이트, 단순하게 생긴** 스타일을 원함 (처음에 3D 프리미티브로 만들었다가 사용자 요청으로 2D 전면 전환함)
- 아트 에셋 없어서 **코드(script-execute)로 PNG 스프라이트를 절차적으로 그려서 생성** (Texture2D→EncodeToPNG→TextureImporter Sprite 설정). 이 방식 유효함
- 생성물:
  - `Assets/Scripts/CreatureWander.cs` (namespace DietCreature): 2D(XY 평면) Idle<->Moving FSM. 경계 minX/maxX/minY/maxY 안 랜덤 이동+휴식. flipX 방향전환, bob(통통튀기) 효과. [RequireComponent(SpriteRenderer)]
  - `Assets/Art/Slime.png` (128px, PPU110): 분홍 슬라임 - 둥근 몸+외곽선+점눈2개+하이라이트+볼터치. 단순/귀여움
  - `Assets/Art/Square.png` (64px 흰 사각형): 바닥/울타리에 SpriteRenderer.color로 틴팅해 재사용
  - `Assets/Scenes/Farm.unity`: Ground(잔디초록 10x10), Fence_N/S/E/W(갈색 테두리), Creature_01(슬라임+CreatureWander, scale1.1)
  - Main Camera: orthographic size6, pos(0,0,-10), 연두 배경, 2D
- 검증: screenshot-isolated(Front)로 2D 농장 렌더링 확인 완료. 움직임은 Play 모드에서만 동작
- 잔재: 이전 3D용 `Assets/Materials/`(M_Ground 등)는 미사용 상태로 남아있음 (정리 가능)
### 📱 프리팹화 + 세로 화면 (2026-06-26 세션3)
- 버그픽스: CreatureWander bob효과가 transform.position에 누적돼 슬라임이 위로 무한상승 → bob 제거, moveSpeed 1.5→0.8(천천히). 사용자가 단순 디자인 선호 확인
- `Assets/Prefabs/Creature.prefab` 생성 (Creature_01을 SaveAsPrefabAsset). 5마리 인스턴스 Creature_01~05, 위치랜덤+크기 0.9~1.2
- 농장 **세로 9×16** 재구성: halfW=4.5, halfH=8. Ground scale(9,16), 울타리 4면, 이동경계 bx=halfW-0.7/by=halfH-0.7
- 카메라 orthographic size = halfH+0.3, 세로 9:16 기준
- PlayerSettings: defaultInterfaceOrientation=Portrait, 가로회전 차단
- **사용자가 직접 해야할 것**: Unity Game뷰 상단 해상도 드롭다운에서 9:16(1080x1920) 선택 (게임뷰 aspect는 코드로 강제 어려움)
- screenshot-isolated는 정사각(width=height)만 지원 → 세로화면 직접 캡처 불가, Front뷰로 세로농장 형태만 확인
### 🎬 씬 전환 / 인트로 화면 (2026-06-26 세션3)
- `Assets/Scenes/Intro.unity`: 메인메뉴. Canvas(Overlay, CanvasScaler ScaleWithScreenSize 1080x1920 match0.5), 타이틀 "Diet Creature", StartButton/SettingsButton, SettingsPanel(Box+CLOSE). EventSystem은 InputSystemUIInputModule(Input System 패키지) 우선
- `Assets/Scripts/MainMenu.cs` (namespace DietCreature): Start()에서 버튼 이름으로 찾아 onClick 런타임 연결. OnStartGame→SceneManager.LoadScene("Farm"), OnOpenSettings/OnCloseSettings 패널 토글. 시작 시 SettingsPanel 비활성
- Build Settings: Intro(index0, 시작) → Farm(index1). EditorBuildSettings.scenes로 등록
- UI 텍스트는 **영어** (Legacy UI Text + LegacyRuntime.ttf 내장폰트는 한글 글리프 없음). 한글 메뉴하려면 TMP+한글 폰트에셋 필요 (미구현)
- UI builtin: Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"), AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/UISprite.psd") 둘다 정상 로드됨
- **제약**: Screen Space Overlay UI는 screenshot-isolated(자체 카메라)로 캡처 불가 → Intro 화면 확인은 사용자가 Play로 직접
### 🗺️ 전체 씬 골격 + 네비게이션 완성 (2026-06-26 세션3, 사용자가 "전체 흐름 전부" 선택)
- 씬 4개 (Build Settings 순서): Intro(0)/Farm(1)/MealCapture(2)/Collection(3). 전부 1080x1920 세로, Overlay Canvas+CanvasScaler+EventSystem
- 공용 컴포넌트 (앞으로 버튼에 재사용):
  - `Assets/Scripts/NavButton.cs`: public sceneName, Start에서 onClick→SceneManager.LoadScene
  - `Assets/Scripts/PanelToggle.cs`: public GameObject target, bool show. onClick→target.SetActive(show)
  - 둘 다 [RequireComponent(Button)]. script-execute에서 reflection으로 필드(sceneName/target/show) 할당
- 화면 흐름:
  - Intro: START→Farm, SETTINGS 패널(MainMenu.cs가 처리)
  - Farm: 하단 NavBar 3버튼(MEAL→MealCapture, DEX→Collection, MENU→Intro) + MOOD버튼→EmotionPanel(:) :| :( 데모) + 기존 슬라임5마리/울타리
  - MealCapture.unity: Title/Counter(Photos 0/10)/PhotoBox placeholder, TAKE PHOTO(기능없음), ANALYZE→HatchPanel(슬라임이미지+GO TO FARM→Farm), BACK→Farm
  - Collection.unity: 도감 슬롯 6칸(2x3, "?" placeholder), BACK→Farm
- 검증: 4씬 .unity 생성 확인, 컴파일/런타임 에러 없음. UI는 Overlay라 스크린샷 불가→사용자 Play 확인

### 🥚 메인 허브를 Hatchery(알 키우기)로 변경 (2026-06-26 세션3)
- **중요 구조 결정**: '게임 시작'(Intro START)으로 진입하는 메인 허브는 농장(Farm)이 아니라 **알 키우기 씬(Hatchery)**. 농장은 Hatchery의 FARM 버튼으로 들어가는 하위 화면
- `Assets/Scenes/Hatchery.unity` 신규: 중앙에 큰 알 이미지(Egg) + "Growth 0/10" + Hint, 하단 NavBar 3버튼(MEAL→MealCapture, DEX→Collection, FARM→Farm)
- `Assets/Art/Egg.png` 코드로 생성: 크림색 타원 알 + 갈색 점박이 + 하이라이트 (Ellipse/Circle 헬퍼). 단순/귀여움. Read 도구로 PNG 확인됨
- Intro MainMenu.gameSceneName: "Farm"→"Hatchery"로 변경
- Farm NavBar: 기존 MEAL/DEX/MENU 버튼 제거 → "< NEST"(→Hatchery) 한 개로 교체. MOOD버튼/EmotionPanel은 농장에 유지
- MealCapture/Collection BackButton 타깃: Farm→Hatchery
- Build Settings 순서: Intro(0)/Hatchery(1)/Farm(2)/MealCapture(3)/Collection(4)
- 주의: NewScene/씬편집은 Play 모드에서 불가 → 작업 전 isPlaying 확인 필요(이번에 한번 막혔다가 Stop 후 재실행)

### 🐣 부화/육성 게임 루프 + 한글 폰트 (2026-06-26 세션3)
- **테스트용**: Hatchery의 MEAL 버튼은 NavButton 제거하고 누를 때마다 Growth+1 (원래 MealCapture 이동이었음; 추후 실제 식사촬영과 연결 예정)
- 게임 루프: MEAL×10 → Growth 10 → "부화"버튼 등장 → 탄생팝업(BornPopup: 슬라임+농장배치/보내기) → 보내기→확인팝업(ConfirmPopup: "정말 보내시겠습니까? 되돌릴 수 없습니다." 예/아니오) → 예=삭제+알리셋, 아니오=탄생팝업복귀 / 농장배치=GameState.farmCreatures++ 후 Farm 로드
- 스크립트:
  - `Assets/Scripts/GameState.cs`: static class, farmCreatures int (씬간 유지, 저장 미구현)
  - `Assets/Scripts/HatcheryManager.cs`: Canvas에 부착. 버튼 이름으로 onClick 연결(NavMeal/HatchButton/PlaceFarmButton/ReleaseButton/ConfirmYesButton/ConfirmNoButton), Start에서 팝업/부화버튼 비활성화, Growth 텍스트 갱신
  - `Assets/Scripts/FarmSpawner.cs`: Farm 씬 빈GO에 부착. Start에서 GameState.farmCreatures만큼 Creature.prefab 스폰(랜덤위치 bx3.8/by7.3, 크기 0.9~1.2, CreatureWander 경계설정). creaturePrefab 필드에 프리팹 할당됨
- 농장: 기존 슬라임 5마리 삭제 → FarmSpawner가 동적 생성
- **한글 폰트 도입**: `Assets/Fonts/malgun.ttf` (C:\Windows\Fonts에서 복사). 새 UI(부화/팝업)는 한글 표시. ⚠️배포 전 무료폰트(나눔/Noto)로 교체 필요(MS 폰트 라이선스). ⚠️폰트 첫 import가 무거워 MCP 응답 끊김 발생했음 → 이후엔 LoadAssetAtPath만 쓰면 됨
- ⚠️ 사용자가 테스트하려 Play 켜두면 씬편집 차단됨. 작업 전 isPlaying 체크, 필요시 EditorApplication.ExitPlaymode()로 코드 종료 가능
- **다음 후보: ① MealCapture 실제 사진촬영→Growth 연동 ② 도감(Collection)에 부화한 생물 기록 ③ 기존 영어 UI들 한글화 ④ 식습관→생물 특징(색/크기) ⑤ 데이터 저장(PlayerPrefs/JSON)**
- **남은 placeholder/할일: 한글폰트(TMP), 식습관 데이터구조(ScriptableObject), 생명체 특징 파라미터화(색/크기/속도←식습관), 실제 식사촬영(카메라/갤러리), AI분석, 도감 데이터 연동, 감정→표정, 탄생 실제 로직**

### 💾 데이터 저장 구현 완료 (2026-06-27 세션4)
- **결정**: 생명체 리스트 구조 + JSON 파일 (사용자 선택). PlayerPrefs 아님
- 저장 경로: `Application.persistentDataPath/save.json` (Win 에디터: `C:/Users/user/AppData/LocalLow/DefaultCompany/DietCreature/save.json`)
- 신규 스크립트:
  - `Assets/Scripts/SaveData.cs`: `[Serializable] SaveData{ int eggGrowth; List<CreatureData> creatures }`, `CreatureData{ string id(GUID); string bornDate(ISO) }`. CreatureData에 추후 hue/size/personality 추가 예정 (주석 표시됨)
  - `Assets/Scripts/SaveSystem.cs`: static Load/Save/Delete. JsonUtility 사용, 손상 시 new SaveData 폴백, creatures null 보정, prettyPrint
- 변경:
  - `GameState.cs`: int farmCreatures 필드 제거 → 런타임 홀더로 전환. `Data`(최초접근 자동로드), `Save()`, `EggGrowth` 프로퍼티, `Creatures` 리스트, `AddCreature()`(GUID+now 생성해 추가)
  - `HatcheryManager.cs`: Start에서 growth=GameState.EggGrowth 복원, UpdateGrowth가 부화버튼 표시까지 담당(growth>=max). OnMeal/OnConfirmYes/OnPlaceFarm마다 EggGrowth 저장. **OnPlaceFarm: AddCreature()+growth 0리셋+Save** (기존엔 농장배치해도 알이 10유지였는데 이제 배치하면 알 리셋됨 — 동작변경, 사용자 확인함)
  - `FarmSpawner.cs`: GameState.farmCreatures(int) → GameState.Creatures.Count
- 검증: assets-refresh→컴파일 에러0. script-execute로 라운드트립 테스트(growth7+2마리 저장→로드 일치 PASS, 테스트후 원상복원) 완료. JsonUtility는 List<직렬화클래스> 지원 확인됨
- **남은 저장 관련 TODO: 세이브 버전 필드(마이그레이션용) 고려**

### 📖 도감(Collection) + 성별/별명 구현 완료 (2026-06-27 세션4)
- **요구**: 알에서 태어난 생물이 도감 등록, 도감 항목 클릭→상세(이름/태어난날/성별), 이름 옆 작은 펜버튼→별명 입력. 성별은 부화 시 50% 랜덤
- 데이터 모델 확장 (`SaveData.cs` CreatureData): `speciesName`(기본 "슬라임"), `bool isMale`(성별), `nickname`(별명). 계산 프로퍼티 `DisplayName`(별명 우선, 없으면 종이름), `GenderSymbol`(♂/♀), `GenderLabel`("수컷 ♂"/"암컷 ♀")
- `GameState.AddCreature()`: isMale = Random.value<0.5f 로 성별 50% 랜덤 부여 (부화→농장배치 시점 = OnPlaceFarm에서 호출됨). **도감=GameState.Creatures(농장 생물 목록)** 으로 정의함 (보내기로 삭제된 건 도감에 안 남음)
- `Assets/Scripts/CollectionManager.cs` 신규 (Canvas에 부착): Start에서 Build() 호출. **UI를 런타임 코드로 전부 생성**(DexRoot 하위에 그리드+상세패널). 
  - 그리드: GridLayoutGroup 3열, 생물 수만큼 Entry(슬라임아이콘+DisplayName라벨) 버튼. 클릭→OpenDetail
  - 상세패널(Detail, 기본 비활성): 반투명 배경(바깥클릭=닫기)+카드. 큰아이콘/이름+펜버튼/태어난날(yyyy-MM-dd)/성별/별명에디터/닫기
  - 펜버튼("✎")→NickEditor(Legacy InputField, malgun폰트, 한글, characterLimit 12)+확인버튼. ConfirmNick: nickname 저장(GameState.Save)+상세·엔트리라벨 갱신(전체 rebuild 안 함, _entryLabels 딕셔너리로 해당 라벨만 갱신)
  - 폰트/스프라이트는 public 필드(font, creatureSprite)에 에디터에서 malgun.ttf/Slime.png 할당(baked 참조, 런타임 동작)
- Collection.unity 변경: 플레이스홀더 Slot_0~5 제거, Canvas에 CollectionManager 부착+필드할당, 저장. (Title/Subtitle/BackButton 유지)

### 버그픽스 + Play 시작씬 고정 (2026-06-27 세션4)
- **BACK버튼 안눌림 버그**: 도감 빈상태 전체화면 Empty 텍스트가 raycastTarget=true라 클릭 가로챔. 해결: CollectionManager.NewText에 raycastTarget=false 추가(모든 런타임 생성 텍스트). 버튼 Image는 raycast 유지되어 클릭 정상. BackButton 자체는 NavButton(sceneName=Hatchery)+GraphicRaycaster 정상이었음
- **Play 시작씬 인트로 고정**: 어떤 씬 열어두고 Play해도 Intro부터 시작. Assets/Editor/PlayFromIntro.cs 신규([InitializeOnLoad]→도메인리로드마다 EditorSceneManager.playModeStartScene=Intro SceneAsset). 확인 로그 playModeStartScene=Intro. 단순 씬오픈보다 영구적
- 교훈: 런타임 코드로 UGUI 생성 시 장식 Text/Image는 raycastTarget=false 기본으로 둘 것(전체화면 stretch면 클릭 차단됨)
- 검증: 컴파일0. 임시생물3마리 메모리주입→Build()=3, Entry3개, OpenDetail reflection으로 상세텍스트 확인('콩이'/2025-01-02/암컷♀), 별명없으면 '슬라임' 표시, 저장파일 무오염 원복. 모두 PASS
- ⚠️ 주의/한계: ①Legacy InputField 한글 IME는 에디터에서 조합 글리치 가능(모바일은 터치키보드) ②♂♀✎ 글리프는 malgun 의존(정상예상) ③그리드 스크롤 없음(생물 많으면 오버플로—추후 ScrollRect) ④상세UI는 런타임생성이라 에디트모드/스크린샷으로 안 보임→Play로 확인 ⑤도감 진입경로: Hatchery NavBar의 DEX버튼→Collection

### 🛒 상점 + 인벤토리 + 부화 3선택지 (2026-06-27 세션4)
- **요구**: 상점/인벤토리 씬 추가. 상점은 '농장 확장' 1개 판매(무료). 인벤토리에 '생물' 항목. 부화 시 농장배치/보관/보내기 3선택. 보관→인벤토리 생물항목에 들어감
- **데이터**: CreatureData에 `location`("farm"/"storage", 상수 LocFarm/LocStorage, 구버전=farm). SaveData에 `farmExpansions`(int). GameState: `CreaturesAt(location)`, `AddCreature(species, location=farm)`, `FarmExpansions`. **도감(Collection)은 여전히 전체(Creatures) 표시, 농장(FarmSpawner)은 CreaturesAt("farm")만 스폰**
- **부화 흐름**: HatcheryManager에 OnStore 추가(AddCreature storage→Inventory씬 이동). OnPlaceFarm은 farm→Farm씬. BornPopup에 StoreButton(파란색,"보관") 추가, 3버튼 가로배치(BornBox x프랙션 0.18/0.50/0.82, y0.13, 폭270). Hook("StoreButton",OnStore)
- **신규 씬**: Shop.unity / Inventory.unity — **Collection.unity를 AssetDatabase.CopyAsset로 복제** 후 CollectionManager+Title+Subtitle 제거하고 ShopManager/InventoryManager 부착(font 할당). 카메라/Canvas/EventSystem/BackButton(→Hatchery) 재사용. Build Settings 순서: Intro/Hatchery/Farm/MealCapture/Collection/Shop/Inventory
- **신규 스크립트**:
  - `UIFactory.cs`: 런타임 uGUI 공용 헬퍼(NewUI/NewText/NewImage/NewButton/Place/Stretch/DestroyNow). 장식 텍스트 raycastTarget=false 기본. (CollectionManager는 아직 자체 헬퍼 사용—추후 통합 가능)
  - `ShopManager.cs`: '농장 확장' 카드+구매버튼→FarmExpansions++ & Save, "보유: N개" 표시. 구매 무료(추후 재화차감 자리). 뒤로가기는 씬 BackButton
  - `InventoryManager.cs`: '생물' 헤더+storage 생물 그리드(아이콘+이름). 비면 안내문
- **Hatchery 네비**: 상단에 ShopNav("상점"→Shop, 좌상단), InvNav("인벤토리"→Inventory, 우상단) 버튼 추가(NavMeal 복제+NavButton). 기존 NavBar(MEAL/DEX/FARM) 유지
- **농장확장 효과 미구현**(카운트만). ~~추후 농장 용량/크기에 연결 예정~~ → **해결됨**: GameState.FarmCapacity(기본10+개당+5, 최대30)로 부화/배치 체크 + 상점 다이아10 구매. (2026-07-04 확인)
- 검증: 컴파일0. location 구분(storage/farm 필터), FarmExpansions++, 저장 라운드트립(location+farmExpansions) PASS. 3씬 컴포넌트 점검(ShopManager/InventoryManager 부착, CollectionManager 제거, StoreButton="보관", ShopNav→Shop/InvNav→Inventory) 모두 OK. (사용자 실제 세이브에 생물 7마리 있음, 무오염)

### 🌾 농장 수용량 + 꽉참→자동확장구매 플로우 (2026-06-27 세션4)
- **세이브 초기화함**: SaveSystem.Delete()+GameState.Reload(). 사용자가 처음 부화부터 테스트 원함. GameState.Reload() 신규(=_data=Load())
- **농장 수용량**: GameState.BaseFarmCapacity=10, `FarmCapacity => 10 + FarmExpansions*5`. 농장확장 1개당 +5 (첫 구매 시 10→15)
- **농장 좌상단 HUD**: FarmSpawner.BuildCountHud — Farm씬 Canvas 찾아 좌상단에 "농장 안 생물 수 N/수용량" Text 생성. 폰트는 Canvas의 기존 Text(malgun)에서 가져옴. Farm엔 Canvas 있음(NavBar/MoodButton/EmotionPanel)
- **꽉참 플로우**: HatcheryManager.OnPlaceFarm에서 CreaturesAt(farm).Count >= FarmCapacity면 배치 대신 FarmFullPopup(런타임생성) 표시. "농장이 꽉 찼습니다. 상점 페이지로 이동하시겠습니까?" 예→PendingPlacement.Set(종)+Shop이동 / 아니오→닫기
- **씬간 전달**: `PendingPlacement.cs`(static, 저장X): autoPlace bool + species. Set/Clear. Hatchery.Start에서 Clear(상점 백버튼 이탈시 stale 방지)
- **상점 자동구매**: ShopManager 재작성 — 구매버튼→"구매하시겠습니까?(수용 N→N+5)" 확인팝업. 예=FarmExpansions++&저장. PendingPlacement.autoPlace면 진입즉시 확인팝업 자동표시 + 구매후 AddCreature(species,farm)+eggGrowth0+저장+Farm씬이동. 아니오=닫기+PendingPlacement.Clear. 카드에 현재수용량 표시
- HatcheryManager 런타임팝업용 폰트는 _bornTitle.font(또는 GetComponentInChildren<Text>)에서 획득. shopScene 필드 추가
- 검증: 컴파일0. 초기화 0/0/0/수용10, 10마리채움→꽉참True, 구매→수용15, 자동배치→11/15+pending정리, 최종 재초기화 0/0/0/10. 모두 PASS. 세이브 파일/메모리 fresh 상태로 종료
- **농장확장 실제 효과 = 수용량 증가로 이제 구현됨**(이전엔 카운트만이었음)

### 📚 도감 종단위화 + 상세팝업 이동 + 농장 카드바 (2026-06-27 세션4)
- **요구**: ①도감=종류별 1칸 ②기존 생물상세(이름/별명/태어난날/성별)는 인벤토리로 이동 ③도감 클릭=종이름/발견한날/부화횟수 ④농장 하단에 생물 카드 나열, 클릭=상세팝업
- **부화 횟수 정의(사용자 확정)**: 태어난 모든 횟수(농장배치+보관+보내기 전부). RecordHatch를 3곳(Hatchery OnPlaceFarm/OnStore/OnConfirmYes) + Shop 자동배치에서 호출
- **데이터**: SaveData에 `List<SpeciesRecord>{species, firstDate(발견일), hatchCount}`. GameState.RecordHatch/SpeciesRecords/GetSpeciesRecord. **백필**: 종기록 비었으면 보유 생물(farm+storage)로부터 종별 횟수/최초날짜 자동 생성(Data getter & Reload에서 BackfillSpecies). ISO날짜 string.CompareOrdinal로 최소값
- **CreatureDetailPopup.cs 신규(재사용)**: 생물 상세팝업(아이콘/이름+✎별명/종류/태어난날/성별, 별명에디터). Canvas에 부착, Open(creature, onChanged). 인벤토리+농장 공용
- **CollectionManager 재작성**: 종단위. CreatureCatalog.All 순회하며 record.hatchCount>0인 종만 카드. 클릭→종정보팝업(종이름/발견한날/부화횟수). 생물 상세 제거됨
- **InventoryManager**: 엔트리에 Button 추가→CreatureDetailPopup.Open(c, Refresh). 별명변경시 그리드 rebuild
- **FarmSpawner 재작성**: Start에서 canvas/font/CreatureDetailPopup 확보. 하단 가로 ScrollRect 카드바(FarmCreatureBar, NavBar 위 y195, 카드160x184, RectMask2D viewport+content 수동배치) 농장생물 나열, 클릭→상세. RefreshBar로 갱신. HUD(좌상단 수)도 유지
- 검증: 컴파일0. 백필5종, RecordHatch +1, 저장 라운드트립(speciesRecords) PASS. 실세이브 무오염. (사용자가 그새 5종 다 부화시켜놔서 도감 5종 채워짐)
- 주의: CreatureDetailPopup은 매니저가 런타임에 Canvas에 AddComponent. font는 매니저 font 또는 Canvas의 기존 Text에서 획득

### 🔁 상세팝업에 위치 이동(배치/보관) 버튼 (2026-06-27 세션4)
- **요구**: 인벤토리 상세→'농장에 배치' 버튼+확인팝업(예/아니오), 농장 카드 상세→'보관' 버튼+확인팝업
- CreatureDetailPopup에 위치이동 버튼 1개 추가 — **생물 location에 따라 자동 결정**: storage면 "농장에 배치", farm이면 "보관". Refresh()에서 라벨/리스너 설정(RemoveAllListeners 후 재설정)
- 확인 서브팝업 내장: ShowConfirm(msg, onYes, singleOk). 메시지 "{이름}을(를) 농장에 배치/보관하시겠습니까?" — 을/를 조사 Eul() 헬퍼(받침 (char-0xAC00)%28). 검증: 슬라임을/토끼를 정확
- **농장 배치 시 수용량 체크**: 꽉 차면 배치 대신 "농장이 꽉 찼습니다.\n상점에서 농장을 확장해 주세요." 안내(singleOk=확인). 농장→보관은 제한 없음
- Open(creature, onChanged, onMoved): onChanged=별명변경(라벨갱신), onMoved=위치이동. InventoryManager는 onMoved=그리드 rebuild. FarmSpawner는 onMoved=**농장씬 LoadScene 리로드**(월드 떠도는 스프라이트+HUD+카드바 동기화). 별명변경은 RefreshBar만
- 검증: 컴파일0, 조사처리 정확. (이동 UI 동작은 Play로 확인 필요)

### 📱 세로 비율 + 버튼 아이콘 디자인 (2026-06-27 세션4)
- **세로 비율**: PlayerSettings Portrait 고정(defaultInterfaceOrientation=Portrait, 가로회전 차단). Game뷰에 1080x1920 커스텀 해상도 리플렉션으로 추가+선택(UnityEditor.GameViewSizes/GameViewSize, GameView.SizeSelectionCallback). 라벨 "DietCreature 1080x1920"
- **버튼 아이콘 9종**: 코드 절차생성 → `Assets/Art/Icons/{shop(바구니),bag(가방),nest(왼쪽휜화살표),back(왼쪽화살표),meal(숟가락),dex(책),farm(새싹),hatch(금간알),mood(웃는얼굴)}.png` (128px, Sprite, PPU100). Read도구로 9종 시각확인 OK. GenIcons에 Arc/Line/Poly/Tri/Disc/Rect 헬퍼
- **표시 방식(사용자 선택)**: 아이콘+글자. 적용 범위: 주요 버튼 전부
- **적용(ApplyButtonIcons)**: 버튼마다 Icon자식 Image(상단 0.2~0.8 x, 0.34~0.96 y, preserveAspect, raycastTarget=false) 추가 + 기존 라벨을 하단밴드(0.04~0.34 y)로 옮기고 fontSize24. 매핑: Hatchery(NavMeal=meal/NavDex=dex/NavFarm=farm/ShopNav=shop+"상점"/InvNav=bag+"인벤토리"/HatchButton=hatch), Farm(NavBackNest=nest+"NEST"/MoodButton=mood), Shop·Inventory·Collection·MealCapture(BackButton=back+"뒤로")
- 검증: 12개 버튼 전부 적용(누락 없음), 컴파일/에러0. (실제 모양은 Play로 확인)
- 참고: Intro의 START/SETTINGS 버튼은 아이콘 미적용(원하면 play/gear 추가 가능)
- **식단 선택 메커니즘(사진촬영 대체) (2026-06-27 세션4)**: MEAL 버튼이 즉시 +1이 아니라 **식단 선택 팝업**을 띄움 — 채식/육류/인스턴트/디저트 4버튼(2x2). 하나 고르면 한 끼=성장+1 + 해당 종류 카운트 기록 후 팝업 닫힘(10번 반복→부화). HatcheryManager: OnMeal→OpenDietPicker(알 없으면 알선택 먼저, 성장 만땅이면 무시), BuildDietPicker/PickDiet(growth++, GameState.RecordMeal(idx), Save). SaveData.dietCounts[4]([채식,육류,인스턴트,디저트]) + GameState.RecordMeal/ResetEgg서 초기화. 검증: 기록/리셋/라운드트립 PASS
  - ✅ **식단→종 매핑 완료**(아래)
- **농장 생물 클릭 상호작용(2026-06-27 세션4)**: 농장에서 생물 클릭 시 종마다 다른 반응 + 이모트. 
  - 이모트 5종 Resources/Emotes/{heart,note,sparkle,smile,exclaim}.png(64px) 절차생성. CreatureInteract.cs: motionVariant 0~4(점프/좌우흔들/회전/스쿼시/점프+뒤집기) 코루틴, 반응중 CreatureWander 비활성, 머리위 이모트 스폰(EmoteFloat=위로뜨며 페이드). FarmTouch.cs: Pointer(InputSystem) press→Camera.ScreenToWorldPoint→Physics2D.OverlapPoint→CreatureInteract.Interact(), UI위(IsPointerOverGameObject)면 무시
  - FarmSpawner 스폰 시 각 생물에 CircleCollider2D(r0.5)+CreatureInteract 부착, 종 id 문자합 h로 motionVariant=h%5, emote=emotes[(h/3)%5] (종별 일관·차별). FarmTouch는 FarmSpawner GO에 런타임 부착
  - 검증: 이모트로드/25종 매핑/컴파일 OK. 클릭 동작은 Play 확인 필요(Pointer+Physics2D)
- **관리자(테스트) 모드(2026-06-27 세션4)**: 설정에 "관리자 모드" 토글(ON/OFF) 추가(GameSettings.adminMode, SettingsPanel ToggleAdmin). ON이면 HatcheryManager.PickDiet에서 식단 1번 선택 즉시: dietCounts=[선택]1로 세팅+growth=max+OnHatch() 호출 → 그 식단·알티어에 맞는 생물 바로 부화(10끼 생략). OFF면 기존대로 10끼. 검증: 저장 라운드트립 PASS
- **수급 골드 클릭 수령으로 변경(2026-06-27 세션4)**: 기존엔 실시간 자동 적립이었으나, 이제 **대기 골드(SaveData.pendingGold)** 에 누적되고 농장 우상단 버튼을 **탭하면 한 번에 GameState.Gold로 수령**. FarmIncome: Update/오프라인 모두 pendingGold에 누적(Gold 직접증가 X), HUD는 IncomeButton(클릭)=골드아이콘+pending수+"탭하여 수령 (+N/분)", Collect()=Gold+=pending;pending=0;Save. 검증: 수령/라운드트립 PASS
- **재화 수급 시스템(2026-06-27 세션4)**: 농장(location=farm) 생물이 티어별 골드 생성 — 기본1/레어3/프리미엄5 (분당). `FarmIncome.cs`(Farm Canvas 부착): Start서 수급률=Σ TierGold(생물), GrantOffline(lastIncomeTime~now 경과분×rate 지급), Update서 rate/60×dt 누적해 정수골드를 GameState.Gold++ & goldEarnedTotal++, 3초마다 저장+lastIncomeTime갱신, OnDisable에 저장. SaveData.goldEarnedTotal/lastIncomeTime 추가. 농장 화면 기분(MOOD) 아래에 골드아이콘+누적수급(goldEarnedTotal)+"+N/분" 실시간 표시. 수급골드는 GameState.Gold(사용가능)에도 적립. 검증: rate계산/오프라인공식/라운드트립 PASS
- **소소 변경(2026-06-27 세션4)**: ①농장확장 무료→**다이아 10개**(GameState.SpendDia 추가, ShopManager DoBuyFarmExpansion에서 차감, 부족시 "다이아가 부족합니다", 카드 sub "다이아 10 (수용 +5)"+dia아이콘) ②인트로 SETTINGS 버튼→**"로그인"**(SettingsButton 라벨/패널 SetTitle="로그인" SetMsg="로그인 기능은 준비 중입니다"; MainMenu는 그대로 SettingsButton→패널 오픈, 실제 로그인 미구현 placeholder) ③게임이름 **"My little Salad farm"**(인트로 Title 텍스트 "My little\nSalad farm" + PlayerSettings.productName). 게임명이 더이상 Diet Creature 아님(폴더/네임스페이스 DietCreature는 유지)
- **농장 배경 시스템(2026-06-27 세션4)**: 배경 5종(default 기본 + meadow초원/swamp늪지/desert사막/rocky바위지대). 각 50골드 상점 판매(기본 무료/항상보유).
  - 아트: Resources/Backgrounds/*.png(360x640 절차생성, Sprite). BackgroundCatalog(id/name/price/GetSprite). SaveData.ownedBackgrounds(List)+currentBackground("default"). GameState.OwnsBackground(기본항상true)/AddBackground/CurrentBackground/SpendDia
  - FarmBackground.cs(Farm Canvas): 카메라 덮는 "Backdrop" SpriteRenderer(sortingOrder-100, max커버스케일)에 현재배경 적용, 기존 "Ground" 숨김. 좌상단 "배경" 버튼→보유배경 선택팝업(2열 썸네일카드, 적용중 표시)→"OO 배경을 적용하시겠습니까" 예/아니오. FarmSpawner 생물수HUD는 y-120로 내림(배경버튼 자리)
  - ShopManager 스크롤목록 개편(VerticalLayoutGroup+ContentSizeFitter): 레어알/프리미엄알/농장확장 + 배경4종. 배경 구매=구매확인 예/아니오→예(SpendGold50+AddBackground)→"바로 적용하시겠습니까" 예/아니오→예(CurrentBackground 설정). 이미보유 배경은 버튼"적용". 농장확장은 다이아10
  - 검증: 배경5종로드/보유·적용 라운드트립/FarmBackground 적용(Backdrop sprite+Ground숨김) PASS
  - **울타리 배경맞춤 색**: FarmBackground.ApplyBackground가 Fence_N/S/E/W SpriteRenderer.color도 배경별로 틴팅(FenceColor): 기본 갈색/초원 밝은나무/늪지 이끼색/사막 모래빛/바위 돌회색. 검증 OK
- **도감 4식단 섹션화(2026-06-27 세션4)**: 도감을 채식/육류/인스턴트/디저트 4섹션으로. 각 섹션 헤더=식단아이콘+"OO found/total", 그 아래 해당 식단 생물 카드 그리드(미발견 실루엣/발견 컬러). 세로 ScrollRect 안 Content=VerticalLayoutGroup+ContentSizeFitter, 섹션마다 [Header(LayoutElement preferredHeight92) + Grid(GridLayoutGroup 3열)]. 식단 아이콘 신규 Resources/Icons/{grass(풀),meat(닭다리),flour(밀가루봉투),cake(케이크)}.png. 검증: Content 8자식(헤더4+그리드4), 섹션 카드수 veg15/meat14/instant15/dessert17=61
- **생물 36종 추가 → 총 61종(2026-06-27 세션4)**: 각 티어(basic/rare/premium)×각 식단(veg/meat/instant/dessert)에 3종씩 추가. AddManyCreatures 스크립트(파라미터 Draw + 임포트 + DB append 한번에). id=tierAbbr+dietAbbr+i (bv1~pd3). 색=식단별 팔레트(채식초록/육류빨강/인스턴트보라/디저트핑크), accent=티어(basic 볼터치·배·점, rare 반짝, premium 왕관). 분포 결과 basic v4/m4/i4/d5, rare v6/m5/i5/d6, premium v5/m5/i6/d6. 모든 티어×식단 탄생 매칭 정상. 도감(ScrollRect)이 61종 처리
- **식단→어울리는 생물 매핑(2026-06-27 세션4)**: 25종에 dietCategory(veg/meat/instant/dessert) 부여. 부화 시 = (알 티어) + (10끼 중 최다 식단; 동점이면 동점들 중 랜덤)에 맞는 종 중 랜덤.
  - CreatureSpeciesDef.dietCategory 추가. CreatureCatalog.RandomIdByDiet(tier,dietIdx)(조합 없으면 티어 폴백)+DietCats[]{veg,meat,instant,dessert}. GameState.DominantDietCategory()(dietCounts 최댓값 인덱스, 동점 랜덤, 전무면 전체랜덤). HatcheryManager.OnHatch가 RandomIdByDiet(tier, DominantDietCategory())
  - **분류**: basic[slime=instant,chick=meat,frog=veg,bunny=dessert,star=dessert] / rare[보라요정=instant,민트=veg,자수정=meat,하늘토끼=dessert,라임=veg,산호=meat,라벤더=dessert,로즈=dessert,아쿠아=veg,푸른별=instant] / premium[황금이=meat,루비=meat,사파이어=instant,에메랄드=veg,무지개=dessert,별빛천사=dessert,크리스탈=instant,호박석=veg,백금=instant,오로라=dessert]. 모든 티어가 4식단 ≥1 커버(basic veg1/meat1/instant1/dessert2, rare 3/2/2/3, premium 2/2/3/3)
  - RebuildDBWithDiet 스크립트로 DB 재구성. 검증: 예시[4,4,2,0]→채식·육류만, 티어/식단 조합 정확 일치 PASS
- **티어별 생물(레어/프리미엄 10종씩) + 테스트 재화(2026-06-27 세션4)**: 알 종류(=티어)에 따라 다른 생물 풀에서 탄생
  - CreatureSpeciesDef에 `tier`("basic"/"rare"/"premium") 추가. CreatureCatalog.RandomId(tier)=해당 티어 풀 랜덤. HatcheryManager.OnHatch가 RandomId(GameState.EggType)로 호출(eggType이 곧 tier)
  - 생물 25종: basic 5(기존 slime/chick/frog/bunny/star) + rare 10(rare1~10) + premium 10(premium1~10). 모두 Art/Creatures/*.png. CreatureDatabase.asset 재구성(RebuildCreatureDB)
  - 레어 이름: 보라요정/민트/자수정/하늘토끼/라임/산호/라벤더/로즈/아쿠아/푸른별. 프리미엄: 황금이/루비/사파이어/에메랄드/무지개/별빛천사/크리스탈/호박석/백금/오로라
  - 아트: GenTierCreatures의 파라미터형 Draw(body,shape0-2,ears0-4(cat/bunny/horn/antenna),accent0-5(cheeks/spots/sparkle/crown/tummy)). 레어=보석빛+반짝, 프리미엄=왕관/금빛 반짝
  - **테스트용 재화 9999**: SaveData 기본값 gold/dia 9999로 변경 + 현재 세이브도 9999 설정. ⚠️배포 전 적정값으로 되돌릴 것
  - 검증: 티어수 5/10/10, RandomId 티어일치, 스프라이트 로드 OK, 재화 9999 저장
  - 도감 개편(2026-06-27 세션4): 25종 전부 카드 표시 — 미발견=검은 실루엣(Icon.color=어두운색)+"???", 발견=컬러+이름. CollectionManager에 세로 ScrollRect(Viewport RectMask2D + Content GridLayoutGroup 3열+ContentSizeFitter PreferredSize) 추가. 상단에 발견수 "N/25" 카운터. ShowInfo(id,found): found면 이름/발견한날/부화횟수, 아니면 ???/"아직 발견하지 못한 생물이에요". 검증: Content 25카드(컬러5+실루엣20). ContentSizeFitter는 FitMode.PreferredSize(.Fit 아님 주의)
- **재화(골드/다이아) + 알 구매 경제(2026-06-27 세션4)**: 사용자 결정 = 소모형, 둘 다 골드, 재화획득은 지금 고정(테스트용 시작값 골드300/다이아10)
  - 데이터: SaveData.gold(300)/dia(10)/rareEggs/premiumEggs. GameState.Gold/Dia/SpendGold(bool)/EggCount(id, basic=int.MaxValue 무제한)/AddEgg/ConsumeEgg
  - 아이콘: Art/Icons/gold(코인)·dia(보석) 절차생성 + Resources/Icons에 복사(런타임 HUD 로드용)
  - Hatchery 좌상단 재화 HUD(gold/dia 아이콘+숫자, BuildCurrencyHud). EggCatalog에 price/purchasable(basic 0/false, rare 100/true, premium 300/true)
  - 알 선택 팝업: 카드에 보유수 표시(기본=무제한, 레어/프리미엄="보유 N", OpenEggSelect서 RefreshEggCounts). SelectEgg: 기본=무제한, 레어/프리미엄 0개면 EggBuyPopup("보유한 알이 없습니다 상점으로?" 예→Shop)·1개이상이면 ConsumeEgg후 선택
  - ShopManager 개편: 다종 아이템(레어알 100골드/프리미엄알 300골드/농장확장 무료) 카드 리스트 + 상단 재화표시. 구매확인→SpendGold, 부족시 "골드가 부족합니다"(확인). 농장확장 자동구매 플로우(PendingPlacement) 유지(DoBuyFarmExpansion). 가격은 rare100/prem300 (조정가능)
  - 검증: 골드차감/구매/잔액부족거부/소모/라운드트립 PASS. ⚠️다이아는 표시만(구매엔 미사용), 재화획득 수단 미구현(고정)
- **알 종류 시스템(2026-06-27 세션4)**: My Egg(Hatchery) 중앙 알을 + 버튼으로 토글. + 클릭→알 선택 팝업(기본알/레어알/프리미엄알 3종 카드). 선택시 해당 알 표시+성장 시작. 부화/리셋/자동배치시 알 비움(+로 복귀). 알 미선택 상태에서 MEAL 누르면 선택 팝업 안내
  - 아트: Resources/Eggs/{basic(크림),rare(하늘+별),premium(골드+별),add(+원형)}.png 절차생성, Sprite Single. EggCatalog.cs(static, Resources/Eggs 로드, basic/rare/premium)
  - 데이터: SaveData.eggType(""=미선택), GameState.EggType/ResetEgg(growth0+type""). 부화 finalize 4곳(OnPlaceFarm/OnStore/OnConfirmYes/Shop자동배치) EggGrowth=0→ResetEgg()로 교체
  - HatcheryManager: 기존 "Egg" Image를 선택된 알 표시용으로, "EggAddButton"(런타임, Egg와 같은 위치, Eggs/add 스프라이트) 토글. BuildEggSelectPopup(3카드). RefreshEggDisplay(has면 알이미지+성장텍스트, 아니면 +버튼). Hint 텍스트 상태별 변경
  - ⚠️ **알 종류는 현재 외형/선택만**, 탄생 생물엔 영향 없음(종은 여전히 랜덤). 추후 알별 희귀도/종 가중치 연결 가능
- **설정 패널 구현(2026-06-27 세션4)**: `SettingsPanel.cs`(Hatchery Canvas 부착, SettingsButton onClick→Open). 런타임 카드 UI: 배경음/효과음 볼륨(−/+, 10%단위, %표시), 진동(켜짐/꺼짐), 언어(한국어/English), 데이터 초기화(확인팝업"정말 초기화하시겠습니까?\n모든 생물과 진행이 사라집니다"→SaveSystem.Delete+Reload+Hatchery재로드), 로그아웃(→Intro씬), 버전(Application.version), 닫기. SaveData.GameSettings{bgm,sfx,vibration,language} 추가, GameState.Settings/ApplyAudio(AudioListener.volume=bgm). 검증: 설정 라운드트립 PASS. ⚠️**placeholder**: 효과음/언어/진동은 값만 저장(오디오 시스템·로컬라이즈·햅틱 미구현), 로그아웃=계정없어서 Intro로 이동만. 배경음만 AudioListener.volume에 실제 반영(현재 게임에 오디오 없음). 보내기 문구 "정말 보내시겠습니까?\n되돌릴 수 없습니다."로 통일
- **상세팝업 보내기 추가(2026-06-27 세션4)**: CreatureDetailPopup에 ReleaseButton("보내기", 빨강) 추가 — 배치/보관 버튼 옆(좌우 2열, 각 300x100). 클릭→ShowConfirm("보내시겠습니까?\n되돌릴 수 없습니다.", 예/아니오). 예=GameState.Creatures.Remove(_current)+Save+CloseAll+onMoved(인벤=그리드rebuild/농장=씬reload). 도감 부화횟수는 유지. 인벤·농장 공용
- **레이아웃 수정2(2026-06-27 세션4)**: 도감 씬의 옛 영문 Title("Collection")/Subtitle("creatures you've raised") 제거(런타임 "도감" 제목/카드와 겹쳐서). 농장 HUD "농장 안 생물 수"→"생물 수". Farm MoodButton 우상단 코너(1,1 -30,-30 110)로 이동. NavBackNest 라벨 "NEST"→"이전"(아이콘 nest 유지)
- **버튼 레이아웃 정리(2026-06-27 세션4)**: 하단 NavBar에 5개 정사각(120x120) 균등배치 — MEAL/도감/농장/상점/인벤토리(상점·InvNav를 NavBar로 reparent, x프랙션 0.1/0.3/0.5/0.7/0.9). Farm 기분(MOOD) 110x110 정사각. 우상단(원래 인벤 자리)에 SettingsButton 추가(NavMeal 복제, gear 아이콘+"설정", 110x110, 연회색). gear.png 아이콘 신규(Art/Icons, 8teeth+center hole). ⚠️**SettingsButton은 아직 onClick 없음(플레이스홀더)** — 설정 패널/기능 미구현
- 🐛 버그픽스(아이콘 흰상자): TextureImporter.textureType=Sprite만 설정하고 **spriteImportMode를 안 정하면 Sprite 서브에셋이 생성 안 됨** → LoadAssetAtPath<Sprite>=null → Image가 흰 사각형. 해결: `ti.spriteImportMode = SpriteImportMode.Single` 명시 후 SaveAndReimport. **교훈: 코드로 PNG→Sprite 만들 때 spriteImportMode=Single 필수**(GenCreatures/도감 아이콘에도 동일 적용 권장). 라벨도 DEX→도감, FARM→농장, MOOD→기분으로 변경(MEAL/부화/상점/인벤토리/NEST/뒤로는 유지)

### 🐛 버그픽스: 인벤토리에서 농장으로 보낸 뒤 다른 생물 클릭 시 상세팝업이 카드 뒤에 숨음. 원인=onMoved→Build()가 InvRoot를 재생성하며 Canvas 맨끝 자식이 되어 팝업(별도 Canvas자식)보다 위에 그려짐. 해결=CreatureDetailPopup.Open에서 `_root.transform.SetAsLastSibling()`. 교훈: 리스트를 재생성하는 화면에서 별도 오버레이는 Open마다 맨앞으로 올릴 것
