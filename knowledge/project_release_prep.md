---
name: project-release-prep
description: "출시 준비(2단계) 진행 상태 - 회사명/패키지ID/시작재화 확정, 저장 원자화, 남은 블로커."
metadata: 
  node_type: memory
  type: project
  originSessionId: 39efb0cf-0d84-4dea-9266-d10f0337cb60
---

# 출시 준비 상태 (2026-07-01 세션17~)

식단 크리처 게임([[project_diet_creature_game]])을 스토어 출시로 가는 작업. "1~5단계 순서대로" 중 1단계(플레이테스트/버그) 후 2단계(출시준비) 진행 중.

## 확정된 브랜딩/경제 결정 (사용자, 세션17)
- **회사명(companyName) = `Team.HS`** — PlayerSettings에 반영 완료. ⚠️저장경로(persistentDataPath)를 바꾸므로 출시 후 변경 금지. (기존 DefaultCompany 경로의 테스트 세이브는 이제 안 읽힘 → 새 세이브 100/10로 시작, 정상)
- **패키지 ID = `com.teamhs.saladfarm`** (Android/iOS 둘 다) — 반영 완료.
- **앱 제목 = `My little Salad farm`** (영문, 유지).
- **시작 재화 = 골드 500 / 다이아 10** (SaveData.cs:126/128). 골드 100→500 상향(세션18, 사용자 요청 "100은 너무 적음"). 유일 소스=SaveData 필드 기본값(GameState는 읽기만). 다이아 10 = 농장확장 1회분.

## 이번 세션 완료된 수정
- **SaveSystem.cs**: 원자적 저장(tmp→File.Replace) + `.bak` 백업/복구. 저장중 크래시로 세이브 통째 손실되던 위험 제거.
- **FarmIncome.cs**: 오프라인 수급 8시간 상한(`MaxOfflineMinutes`) — 시계조작/장기미접속 골드폭증 방지.
- **SaveData.cs**: 디버그 9999 → 100/10.
- PlayerSettings: companyName + applicationIdentifier(위).
- **앱 아이콘**: `Assets/Art/Icons/app_icon.png`(1024, 파스텔 그라데이션+슬라임 중앙, 슬라임 알파 bbox 잘라 재배치). SetIconsForTargetGroup(Unknown+Android) 설정 완료.
- AI 활성 확인: `Assets/csc.rsp`가 `-define:DIET_SENTIS` + `-define:DIET_NATIVEGALLERY` → **모든 빌드타겟(Android/iOS 포함)에 적용**. ProjectSettings 플랫폼 심볼엔 없지만 csc.rsp라 정상. 모바일에서도 AI분석·앨범선택 켜짐.

## 3단계 온보딩 (세션17 완료)
- `SaveData.onboarded` 플래그 + `GameState.Onboarded`/`MarkOnboarded()`.
- `MainMenu.OnStartGame`: 첫 실행(미온보딩)이면 START가 Farm 대신 **Hatchery**로 라우팅(빈 농장 대신 할 일 있는 화면).
- `HatcheryManager`: 첫 실행 시 환영 팝업(`BuildWelcomePopup`) → "알 고르기" 버튼 → `MarkOnboarded`+Save → `OpenEggSelect()`로 자연 연결. 이후 기존 루프(식사기록→성장→부화).
- 게임내 텍스트는 이모지 미지원 폰트라 이모지 안 씀.
- **✅ 플레이모드 실검증 완료(세션17)**: 첫실행 START→Hatchery 라우팅, 환영팝업 생성·활성·문구 정확, "알 고르기"→onboarded=true 저장+환영닫힘+알선택팝업 열림까지 end-to-end 동작 확인. 시작재화 gold=100/dia=10도 런타임 확인.

### 화면별 튜토리얼(1회성) — 세션17 추가·검증
- **`TutorialPopup.cs`**(공용 헬퍼): `ShowOnce(canvasParent, font, key, title, message)` — HasSeenTutorial(key) 아니면 파스텔 팝업 표시 후 MarkTutorialSeen+Save. 표시 순간 기록(닫기 전 종료해도 재현 안 됨).
- **상태**: `SaveData.seenTutorials`(List<string>) + `GameState.HasSeenTutorial/MarkTutorialSeen`.
- **훅(각 매니저 Start/OnHatch 1줄)**: dex→`CollectionManager`, shop→`ShopManager`(autoPlace 아닐 때만), inventory→`InventoryManager`, farm→`FarmSpawner`(_canvas), hatch→`HatcheryManager.OnHatch`(첫 부화 시 배치/보관 안내).
- **검증**: 도감 첫 방문 팝업 뜸(seenDex=True 기록), 2번째 방문 안 뜸(1회성) 런타임 확인. 나머지는 동일 헬퍼 패턴+컴파일 확인.
- 검증 후 세이브 삭제해 깨끗한 첫실행 상태로 둠(onboarded/seen 전부 리셋).

### 첫 생명체 1회 부화 + 첫 식사 튜토리얼 — 세션17 추가·검증
- **`HatcheryManager.EffectiveMaxGrowth`**: 도감기록 0개(신규유저)면 **1**, 이후 `maxGrowth`(5). UpdateGrowth/OnMeal/ApplyMeal/PickDiet의 maxGrowth를 전부 이걸로 교체. → 첫 생명체는 1번 촬영으로 부화, 두번째부터 5번.
- **첫 식사 튜토리얼**: OnMeal 비관리자 경로에서 `TutorialPopup.ShowOnce("meal","음식을 찍어볼까요?","자신이 먹을 음식을 찍어보세요!\n당장 없다면 갤러리에 있는\n오늘 먹은 식사나 간식도 괜찮아요.", OpenMealCapture)`. 이미 봤으면 바로 촬영.
- `TutorialPopup.ShowOnce`에 `onConfirm` 콜백 + bool 반환 추가(확인 시 이어서 실행). 
- **검증**: 신규 effMax=1·1회 식사 후 부화버튼 활성, 2번째 effMax=5, meal 튜토리얼 표시 확인(런타임 리플렉션).

## 4단계 콘텐츠·밸런싱 (세션17)
- **도감 분포 검증(양호)**: 총 64종. basic17(veg4/meat4/instant4/dessert5), rare22(6/5/5/6), premium22(5/5/6/6), secret 3. **모든 티어×식단 조합에 최소 4종 → 빈 조합 없음.** "식단→생명체" 약속이 데이터로 완비.
- **✅다이아 획득 수단 추가**: `GameState.RecordHatch`가 신규 종 첫 발견 시 `NewSpeciesDiaReward`(=1) 다이아 지급 + bool 반환. 도감 수집 루프에 프리미엄 재화 연결. `HatcheryManager.OnHatch`가 탄생 팝업 타이틀에 "새로운 친구예요! +1 다이아"(isNew시) 표시. **검증됨**: 첫발견 +1, 재부화 중복없음(리플렉션 인메모리 테스트).

## 빌드 설정 (세션18 완료)
- **✅Android Target SDK = API35 명시**(PlayerSettings.Android.targetSdkVersion). 설치 SDK는 android-34/35/36(SDK root: D:\6000.4.5f1\...\AndroidPlayer\SDK). Play 규정(2025-08~ target35+) 충족. 원하면 36으로 상향 가능.
- **✅BuildAAB=True**(EditorUserBuildSettings.buildAppBundle) — 스토어 배포용 앱번들.
- 확인된 기존값(정상): 스크립팅백엔드 **IL2CPP**, Il2Cpp **Release**, 아키텍처 **ARM64**, ApiCompat **NET_Standard_2_0**, MinSdk 25. (ProjectSettings.asset의 scriptingBackend:{} 비어보여도 유효값은 IL2CPP)
- **✅릴리스 키스토어 완료(2026-07-04 세션27)**: 사용자가 Unity Keystore Manager(GUI)로 생성 — `C:/Users/user/Documents/SaladFarmKeys/saladfarm.keystore`, alias=saladfarm, useCustomKeystore=True 등록 확인. `G:\내 드라이브\saladfarm.keystore`로 백업함. 비밀번호는 사용자만 앎(Unity 미저장 → 릴리스 빌드 세션마다 재입력 필요). keytool CLI는 대화형이라 세션 `!` 실행 불가였음 → Keystore Manager가 정답.
- ~~Unity 스플래시~~ → **완료(2026-07-04 세션27)**: Unity 6은 무료판도 로고 끄기 가능 → showUnityLogo=False, 배경=UITheme.Paper 크림(0.972,0.945,0.894), 로고=app_icon(Sprite로 재임포트) 2.5초 Dolly. 다이아 2차획득(광고 등)은 추후 선택.

## 카메라 회전 (세션18 수정·검증)
- **MealCaptureUI 실기기 회전 대응 완료**(코드). 3가지:
  1) **후면 카메라 우선 선택** `PickCameraDevice()`(비-전면 우선, 없으면 devices[0]) — 기존 `new WebCamTexture()`는 일부 기기서 전면 잡힘.
  2) **업라이트 캡처** `BuildUprightShot()`+`RotateCW()`: `OnShutter`가 raw 대신 videoRotationAngle(시계 90/180/270)·videoVerticallyMirrored를 실제 픽셀에 적용해 세운 텍스처를 분석·표시. 정지사진은 프리뷰 RectTransform 회전/스케일을 원위치. → 분석기(회전 불변 아님) 정확도 개선.
  3) 첫 프레임 didUpdateThisFrame까지 대기해 videoRotationAngle 확정 후 프리뷰 보정.
- **✅첫 실행 "카메라를 찾을 수 없어요" 버그 수정**(세션18): 안드로이드는 권한 승인 직후 `WebCamTexture.devices`가 한두 프레임 늦게 채워져 첫 실행만 실패하고 재실행 땐 됨. `StartPreview`에서 devices.Length==0이면 최대 2초 폴링 후 판단하도록 수정.
- **✅저신뢰 재촬영 유도**(세션18, 사용자 요청 "벽지를 채식으로 인식"): `DietResult.confidence < MinConfidence(0.55)` 또는 !ok면 결과 확정 대신 "이게 무슨 음식인지 잘 모르겠어요…다시 찍어주세요" 문구 + 확인버튼 라벨을 "그래도 기록"으로(SetConfirmLabel). 하드블록 아님(진짜 음식 오인 대비 탈출구). ⚠️한계: 현 food.onnx는 4클래스 분류기라 "음식 아님"을 근본적으로 못 걸러냄(OOD 과신 가능) → 임계값은 모호한 경우만 잡음. 완전한 비음식 거부는 별도 non-food 클래스/엔트로피 컷 필요(추후).
  - 좌표계 좌하단원점(Get/SetPixels32). RotateCW 픽셀매핑 리플렉션 단위테스트 통과(ROT90 ow/oh스왑+코너픽셀 기대값 일치). 컴파일 검증됨.
  - ⚠️**실기기 방향 최종확인은 여전히 필요**(에디터 웹캠은 회전0이라 90/270 경로 미검증). 세로촬영 시 프리뷰=캡처 방향 일치하는지 실기기 1회 확인.

## ▶ 다음 세션 할 일 (세션27 갱신, 우선순위)
0. **(2026-07-04 세션27) APK 재빌드+실기기 확인 완료** — ApkBuilder 메뉴로 Desktop\SaladFarm.apk 78.3MB, 에러0. 사용자 실기기 플레이 이상무(세션26 버그 4건+카메라 전부 OK). **출시 블로커 전부 해소.** ⚠️ApkBuilder가 buildAppBundle=false로 바꿈 → 스토어 릴리스 AAB 빌드 전 True 복원 필요. 다음 단계 = 릴리스 AAB 빌드(키스토어 비번 입력 필요)+스토어 등록.
1. ~~릴리스 키스토어~~ → **완료**(위 ✅ 항목 참조).
2. **[검증] 실기기 카메라 방향 최종확인** — 세로 촬영 시 프리뷰=저장사진 방향 일치, 후면카메라 선택되는지, 첫실행 카메라인식 되는지. 안 맞으면 RotateCW 각도/미러만 조정.
3. **[검증] 신규 세이브로 시작골드 500 확인** + 저신뢰 팝업이 실제 음식에 과하게 뜨지 않는지(임계값 0.55 튜닝 여지).
4. (선택) 분석기 **비음식(OOD) 거부** 강화 — non-food 클래스 추가 또는 softmax 엔트로피/마진 컷. 벽지 등 확신 오인 방지.
5. (선택) Target SDK 35→36 상향, 다이아 2차 획득수단(일일보상/광고), Unity 스플래시(무료판 강제).

## 코드 품질 소견
핵심 루프(GameState/HatcheryManager/CreatureCatalog/ShopManager/MealCaptureUI/SentisMealAnalyzer) 정독함 — 구조 견고, 위 외 심각버그 없음. Unity가 관리자권한 실행 중이라 `graphicsApiMask` 에러 계속 뜨지만 무해(일반권한 재실행시 사라짐).
