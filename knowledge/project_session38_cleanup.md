---
name: project-session38-cleanup
description: "세션38: 가이드북 11페이지로 확장·진화 걷기 3종 신설·삭제종 아트 21장 제거·hideFlags 유령 수정. premium9 진화 아트 결손 발견."
metadata: 
  node_type: memory
  type: project
  originSessionId: 4eae42bb-c73d-4bdf-b637-e8ca68b73cbd
---

# 세션38 잔여 정리 (2026-07-10)

사용자 지시: "GPGS랑 기능 백로그 빼고 나머지 전부". 메모리에 쌓인 잔여 항목을 소진했다.

1. **가이드북 9 → 11페이지** ([[feature_guidebook]], [[todo_guidebook_missing_pages]] 소진)
   - 신설: '식사 기록하기'(수동 입력 + 갤러리, 3페이지), '생물 보내기'(작별 선물, 5페이지)
   - 갱신: 꾸미기 3종 → **8종 + 가격표 + 밤 점등/풍차/벤치 연출**, 재화 페이지 다이아 획득원에 '생물 보내기 +1'
   - **본문 높이 실측법**: `Text.preferredHeight`(폰트 `Fonts/NanumPenScript-Regular`, size 34, rect 폭 624)로 잰다. 한계 **614px**(본문 상단에서 페이지 번호 상단까지). 현재 최대 550px(성장과 진화·시크릿 시너지).
   - ⚠️ **폰트를 틀리면 측정이 통째로 무의미하다.** 씬에서 아무 Text나 집으면 malgun이 잡혀 810px 같은 가짜 오버플로가 나온다. 본문 폰트는 UITheme.Body = NanumPenScript.

2. **진화(stage2) 걷기 프레임 3종 신설** — [[project_session35_fixes]] 5번 해소
   - `bm2`(스핑크스)·`rd2`(솜사탕)·`rd3`(초코)가 stage2 걷기 프레임이 없어 제자리 컷이었다.
   - 관례를 기존 stage2 아트에서 그대로 따랐다: **bd1(마카롱)=바닥 고정 스쿼시(-2)/스트레치(+2)**, **slime=전체 부유 ±2px**.
   - rd3=스쿼시/스트레치, rd2=부유 ±2px, **bm2는 `stationary:1`이라 걷지 않는다** → alwaysPlay로 제자리 재생되므로 '걸음' 대신 **숨쉬기**(앞발 밴드 y≥110 고정, 윗몸만 +1px). bm2는 stage1엔 걷기 프레임이 있어 진화 시 오히려 애니가 사라지던 셈.
   - 생성 스크립트: scratchpad `stage2walk.py`. 이제 **시크릿 4종 외 전 종이 stage2 걷기 프레임 보유**.

3. **삭제된 종의 잔존 아트 21장 제거** — [[project_session35_fixes]] 10번 '미정리 잔존' 해소
   - `bm3·pm1·premium7·rare4·rare7·ri3·rm3` (7종 × CreaturesEvolved / CreaturesEvolvedSleep / CreaturesSleep).
   - 전부 DB에 없는 삭제종이고 GUID 참조도 0건. **Resources/ 는 참조 여부와 무관하게 빌드에 포함되므로 지우면 APK가 줄어든다.**
   - 백업 `ArtBackups/s38_removed_species_art`. 삭제 후 살아있는 32종 아트 결손 0건 확인.

4. **hideFlags 유령 오브젝트 수정** — [[project_session35_fixes]] 17번 '보류' 해소
   - `Sfx.cs` · `Bgm.cs` · `UITween.cs` · `WeatherSoundManager.cs` 4곳의 `HideFlags.HideAndDontSave` → **`HideFlags.HideInHierarchy`**.
   - `HideAndDontSave`는 `DontSaveInEditor`를 포함해서 **플레이 종료·도메인 리로드 후에도 오브젝트가 살아남는다**. 이미 `DontDestroyOnLoad`가 걸려 있어 DontSave 계열은 불필요.
   - E2E 검증: 수정 전 플레이 진입→종료 시 유령 3개 잔존 재현 → 수정 후 0개. 빌드에는 영향 없음(에디터 한정).

5. **기획서/화면정의서 PPT 옛 이름** — 확인 결과 **이미 깨끗함**(원본 XML 전수 검색: '불꽃'·'꼬리 사자'·'먼지 몬스터'·'랩터' 0건). [[project_session35_fixes]] 9번의 "기획서 s12 잔존" 메모는 낡은 것 — 세션36~37 PPT 갱신 때 함께 고쳐진 듯.

6. **실기기 확인용 APK 빌드 완료** — `Desktop\SaladFarm.apk` **82 MiB(85,302,940 B)**, 릴리스 키스토어 서명(`O=Team.HS`), `debuggable` 없음(관리자 모드 컴파일 제외 확인), package `com.teamhs.saladfarm` v1.0(code 1). 빌드 후 `buildAppBundle=False` 원복 확인.
   - 키스토어 비번은 **세션마다 Player Settings에 사용자가 직접 입력**해야 한다(빈 상태로 빌드하면 `UnityException: Unable to sign the application`).
   - 세션28~37에 쌓인 실기기 미확인 항목이 전부 이 APK에 들어 있다 ([[project_session33_fixes]] 대기 목록, [[project_session35_fixes]], [[feature_meal_gallery_s37]], [[feature_manual_diet_input_s37]]). GPGS만 자리표시자 AppId라 미동작.

## 세션 후반: 식사 AI 비음식 보강 (별도 문서)
사용자 실기기 보고 "주먹→디저트 오분류"를 같은 세션에 해결. 손·얼굴·반려동물 1210장 수집→재학습(run6)→게임 적용까지 완료. 상세는 [[feature_meal_ai_v6_nonfood]].

## premium9 진화 아트 결손 → 세션39 완료 ✅ (전면 리디자인)
발견 당시 `premium9`(백금)만 진화 아트 결손이었는데, **기존 base·성장이 '왕관 토끼'라 사용자가 3단계를 통째로 '반짝이 기린'으로 리디자인**해 옴(Downloads/백금/: 백금.png=부화, 5레벨.png=성장, 10레벨.png=진화). 사용자 승인 후 3단계 전부 교체.
- 파이프라인(스크래치 `premium9_art/sleep2/walk/commit.py`): 소스는 이미 투명배경. **최대 연결성분 bbox 크롭으로 우하단 'Made with MakeBead' 워터마크 자동 제외** → LANCZOS 다운스케일 128 → 베이스라인 배치(**부화 bottom 114 / 성장 117 / 진화 122**, 중심 x63).
- ⚠️**방향 교정(1차 오판)**: 처음 "정면 뷰라 flip 불필요"로 판단했으나 **틀림** — 기린은 꼬리가 우측/앞이 좌측이라 좌향이었고, 게임 기본 이동(우측)과 반대라 뒤로 걷는 것처럼 보였다. 사용자 지적으로 **전 스프라이트 좌우 반전(FLIP_LEFT_RIGHT)→우향(꼬리 왼쪽)**. 교훈: 다리·꼬리 있는 생물은 얼굴이 정면이어도 몸통 방향(꼬리 위치)으로 우향 판정할 것.
- 자는 얼굴: **최종 128 본체에서 직접 생성**(idle과 픽셀 정합, 소스 원본 없어도 됨—Downloads/백금 폴더는 이후 삭제됨). 눈 좌우 최대 다크 블롭 검출→피부색 채움→선명한 ‿ 아치. ⚠️눈 크면 높이 필터 완화(h한계 0.34*ch) 필요(안 그러면 한쪽만 감김).
  - **자는눈 2차례 반려**(사용자): ①단색 flat 채움=밋밋한 패치 ②페더링=**눈 테두리에 회색 링(판다눈)**. **최종 해결**: 눈 bbox를 **~1.4배 타원으로 확장해 다크 테두리 너머 깨끗한 크림 얼굴까지 통째로 채움**(경계가 크림-크림이라 안 보임) + 그 위 ‿. 교훈: 큰 눈은 '동공만' 지우면 링 남음 → **눈 외곽선까지 넉넉히 덮을 것.**
  - **방향(1차 오판)**: "정면이라 그대로" 틀림 → 꼬리 위치로 보면 좌향이었음. 전 스프라이트 좌우반전=우향. 백업 `ArtBackups/s39_premium9_bunny`(토끼)·`_giraffe_v1`·`_giraffe_v2sleep`.
- 걷기(4다리): 프론트뷰라 다리 분리 안 됨 → **몸중심 좌/우 다리밴드(하단16px)를 교대로 3px 들어올림 + walk2 바디 바브 1px**. 부화는 다리 없어 걷기 없음.
- 반영 10파일: 기존(부화본체=Art/Creatures, 부화자는, 성장본체/자는)은 **PNG만 덮고 .meta 유지**(base guid b9f08b3b=DB참조 무결), 신규(성장 walk1/2, 진화 본체/자는/walk1/2)는 premium10 .meta 복사+새 uuid guid. guid 중복 0 확인. 백업 `ArtBackups/s39_premium9_bunny`.
- ⚠️Unity 닫힌 상태로 반영 → **다음 Unity 실행 시 자동 임포트**. 폴더↔단계: 성장=CreaturesEvolved/, 진화=CreaturesEvolved2/, 걷기 진화=CreaturesEvolved2/<id>_walk1.., 자는 진화=CreaturesEvolved2Sleep/. 관련 [[feedback_creature_art_pipeline]] [[reference_creature_baseline]].

## Active Input Handling 정리 (세션38에 해결)
`Active Input Handling`이 **Both**(activeInputHandler: 2)였다. Android가 이를 지원하지 않아 **Android 빌드마다 "Unsupported Input Handling on Android" 모달**이 떴다(빌드 결과 자체엔 무해). 조사 결과 프로젝트는 이미 신형 전용 — Input System 1.19.0 설치, 씬 7개 전부 `InputSystemUIInputModule`, Assets 전체에 구형 `Input.*` API 사용 0건. 사용자 승인 후 **`1`(Input System Package (New))로 변경**.
- ⚠️ `PlayerSettings.SetPropertyInt("activeInputHandler", ...)` 는 **동작하지 않는다**(엉뚱한 0을 읽고 아무것도 안 씀). `ProjectSettings/ProjectSettings.asset`을 `SerializedObject`로 열어 `activeInputHandler` 프로퍼티를 직접 써야 한다.
- **에디터 재시작 후 적용**된다. 바탕화면 APK는 Both 상태에서 빌드된 것 — 실기기 동작엔 문제없지만, 재시작 뒤 새로 빌드하면 이 설정이 반영된다.

## 함정 기록
- ⚠️ **MCP `script-execute`로 장시간 동기 작업(BuildPlayer 등)을 돌리지 말 것.** 호출이 타임아웃되면(`Response data is null`) **MCP 클라이언트가 같은 호출을 계속 재시도**하고, 재시도마다 빌드가 새로 시작된다. 세션38에 APK 빌드가 **10회** 중복 실행돼 Unity 모달이 반복해서 떴다(사용자가 Ignore로 종료). 빌드는 Unity 메뉴(`Build ▸ Android APK to Desktop`)로 사용자가 직접 누르게 하거나, 에디터를 닫고 `-batchmode -executeMethod`로 돌릴 것.
- `EditorApplication.delayCall += () => ...` 은 **즉시 실행되지 않는다**(에디터가 포커스를 얻는 등 다음 update까지 지연). 세션38에선 5분 뒤에 뒤늦게 발화해, 그때는 비번이 없어 서명 실패했다. "예약 로그만 찍히고 조용하다"고 실행 안 된 걸로 오판하지 말 것.
- 코드 편집 후 **`assets-refresh`만으로는 재컴파일이 안 될 수 있다** ([[reference_mcp_stale_compile]] 재확인). 이번에도 옛 코드로 플레이 모드가 돌아 `hideFlags`가 그대로였다. `RequestScriptCompilation` 필요.
- python 출력에 `—`·`•` 같은 문자를 쓰면 **cp949 UnicodeEncodeError**. `sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')` 로 회피.
