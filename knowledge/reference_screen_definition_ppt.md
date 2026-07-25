---
name: reference-screen-definition-ppt
description: SaladFarm 화면 정의서 PPT — Desktop\SaladFarm_화면정의서.pptx. 화면·팝업 16종을 참고문서(쥐독한등반) 스타일로 1장씩(스크린샷+번호 콜아웃+구성·기능 표+설명).
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8e44b60e-f869-4938-bfe7-0cd2f06a996f
---

# SaladFarm 화면 정의서 PPT (2026-07-05 세션28)

## 2026-07-08 세션32 갱신 (백업 .bak_s32)
- **스크린샷 3장 재캡처·교체**: 농장(s6, 새 울타리 위치+생물 분산+전폭 카드바)·상점(s8, 가로 스크롤 탭)·인벤토리(s9, 새 그리드). 1080×1920, `PlayModeWindow.SetCustomRenderingResolution` + 플레이모드 ScreenCapture, **cheatActive=false로 관리자 슬라이더 제거 후 캡처**(끝나고 복원).
- 이미지 교체법: 파트 blob 교체 — `slide.part.related_part(shape._element.blip_rId)._blob = bytes` (같은 해상도라 콜아웃·지오메트리 유지, 재배치 불필요했음).
- 텍스트: s8 탭 순서 정정(알/배경/꾸미기/성장/아이템+가로 스크롤), s7 41종, s6 겹침방지·정지형(스핑크스), s17 보내기 작별 선물 문구.
- ⚠️ **ScreenCapture.CaptureScreenshot은 비동기(프레임 끝 실행)** — 같은 호출에서 캡처+LoadScene 하면 다음 씬이 찍힌다(상점이 인벤으로 찍혔던 사고). 캡처→2~3초 대기→씬 전환 순서 엄수.

기존 [[reference-design-doc-ppt]](게임기획서)와 **별개 신규 파일**. 사용자가 「쥐독한 등반」 기획서(`F:\Project_쥐독한 등반\쥐독한등반_기획서.pptx`) 스타일 — 각 화면·팝업을 1슬라이드씩 구성/기능/설명으로 정의 — 를 요청.

**산출물**: `C:\Users\user\Desktop\SaladFarm_화면정의서.pptx` (16:9, 18슬라이드 = 표지+목차+16). 기존 기획서는 그대로 둠.

## 슬라이드 구조 (참고문서 모방)
슬라이드당: 좌상단 제목(세이지 accent bar) + 좌측 스크린샷(높이 5.95in, 9:16) + 스크린샷 위 번호 콜아웃(①②③ 코랄 원, 정규화 좌표) + 우측 구성·기능 표(No.|기능, 세이지 헤더) + 하단 설명·기획 의도 박스. 팔레트는 게임 톤(크림 BG·세이지·브라운·코랄), 폰트 맑은 고딕(a:ea 주입).

## 16종 목록
화면: 1타이틀 2부화장 3식사촬영 4농장 5도감 6상점 7인벤토리. 팝업: 8설정 9가이드북 10도전과제 11식단리포트 12출석 13배경선택 14꾸미기편집 15생물상세 16사진미리보기.

## 스크린샷 캡처 (Unity MCP)
플레이모드에서 씬 LoadScene + 팝업은 매니저 Open()/reflection으로 열어 `ScreenCapture.CaptureScreenshot`. 1080x1920. scratchpad/shots에 01~16 저장.
- 팝업 여는 법: SettingsPanel/Guidebook/AchievementBook/DietReport/MealCaptureUI = public Open(). AttendanceManager.Open()·FarmBackground.OpenPicker()·FarmDecorate.EnterEdit/ExitEdit = private(reflection). CreatureDetailPopup.Open(creature). FarmPhoto.TakePhoto().
- ⚠️ **식사 촬영(MealCaptureUI)은 WebCamTexture 의존 → 에디터에서 Open() NRE**. MealCapture 씬은 옛 미사용 플레이스홀더(회색 박스)라 안 씀 → 스크린샷 없이 3단계 흐름 박스(미리보기→분석→결과)로 표기.

## 생성 스크립트
`gen_screendoc.py`(헬퍼: set_font/textbox/spec_table/callout/screen_slide) + `gen_content.py`(SLIDES 데이터: 콜아웃 정규화좌표·기능·설명). 둘 다 scratchpad(소멸). 실행: `exec(gen_screendoc)+exec(gen_content)` 로 네임스페이스 공유. 검수: PowerPoint COM Export.
- 추가·수정 시 스크립트 재작성 필요. 콜아웃 위치는 정규화(nx,ny)라 스크린샷 교체해도 유지.

## 부분 수정(이미지·콜아웃만) — 세션29 방식
전체 재생성 없이 python-pptx로 surgical 수정 가능. 이미지 프레임 EMU 고정: L0=502920,T0=960120,W=3060382,H=5440680(정확히 9:16). 콜아웃=지름 219750 원, 중심=(L+109875,T+109875). 정규화→EMU: `L=L0+nx*W-109875, T=T0+ny*H-109875`.
- **이미지 교체**: python-pptx save는 media를 원본으로 되쓰므로, ①python-pptx로 콜아웃 이동 후 save → ②zip에서 `ppt/media/imageN.png` 바이트 직접 교체(순서 중요). 슬라이드N↔imageK 매핑은 `slideN.xml.rels`로 확인(예: s7=image4, s14=image11, s15=image12).
- **콜아웃 이동**: shape.name이 '타원'으로 시작+text가 번호. `sh.left/top` 만 바꾸면 됨.

## 스크린샷 캡처 함정 — ScreenCapture 대신 RT 카메라 (세션29 필수)
`ScreenCapture.CaptureScreenshot`은 **정적 화면에서 무한 대기**(에디터 비포커스 시 게임뷰가 present를 안 해 end-of-frame 콜백 안 옴). QueuePlayerLoopUpdate로 프레임 돌려도(frameCount 급증) 안 써짐. → **임시 카메라+RenderTexture로 즉시 렌더**가 확실:
1. ScreenSpaceOverlay 캔버스들 모아 renderMode=ScreenSpaceCamera+worldCamera=임시cam으로 임시 전환(planeDistance 살짝 차등),
2. ortho 카메라(size=H/2, bg=Camera.main.backgroundColor, targetTexture=RT 1080x1920, aspect=W/H) `cam.Render()`,
3. RenderTexture.active=RT→Texture2D.ReadPixels→EncodeToPNG→File.WriteAllBytes,
4. 캔버스 renderMode/worldCamera 원복. 프레임 대기 불필요, 결과 정확.
- **출석 팝업은 부화장(Hatchery) 소속**(HatcheryManager가 AttendanceManager AddComponent) — Farm 아님. 오늘 셀 강조는 `lastAttendanceDate`≠오늘이어야 노란 링 표시.
- **배경 확인 팝업**: FarmBackground(Farm 씬) OpenPicker 후 `_confirm.Show(msg,noop)` 리플렉션. 단 ConfirmPopup 캔버스와 BgPicker 캔버스가 **둘 다 order=100**이라 확인팝업이 피커 뒤로 가려짐 → confirmCanvas.sortingOrder를 300+로 올리고 SetAsLastSibling. 관리자모드면 하단 DevTimePanel 보이니 SetActive(false)로 숨겨야 깔끔.
- 도감 ★뱃지: 발견종(hatchCount>0) 중 evolveCount>0이면 카드 우상단 금색 ★. ScrollRect.verticalNormalizedPosition으로 별 카드가 화면에 오게 스크롤 후 캡처.

## 세션29 수정 이력
피드백 반영: 좌측 이미지에 없던 요소를 실제 상태로 재캡처. (1)s7 도감 ③=진화★뱃지→슬라임/라면 진화시켜 별 보이게, (2)s14 출석 ②=오늘 셀→5일차 강조 상태, (3)s15 배경 ②=적용 확인 팝업→피커+확인팝업 동시. 세 이미지 교체+콜아웃 재배치, COM 검수 완료. 백업: Desktop\SaladFarm_화면정의서.bak_s29.pptx.

## 세션35 갱신 (2026-07-09)
- 텍스트만 수정: 농장(정지형 2종·시크릿 1.5배), 도감 32종, 인벤·상세 팝업 보내기 시크릿 제외, 출석 시계 되감기 무효. 백업 `.bak_s35`.
- ⚠️ **스크린샷은 세션32 캡처본 그대로** — 세션35의 신규 해칠링 아트·매머드·삿싱 개명이 반영돼 있지 않다. 다음 APK/에디터 캡처 때 농장·도감·상세 팝업 재촬영 필요.

## 세션35 후반: 팝업 슬라이드 3장 추가 (16 → 21슬라이드)
- `17_부화장 팝업`(6종) · `18_농장 팝업`(4종) · `19_공용 · 기타 팝업`(7종). 스크린샷 없이 표(팝업/트리거/구성·버튼)로만 구성. 기존 슬라이드를 복제해 그림·콜아웃 번호를 지우고 표를 3열로 넓혔다.
- ⚠️ **PowerPoint 표 확장 함정**: `a:tbl` 안의 `extLst`(a16:colId / a16:rowId)를 그대로 deepcopy해 열·행을 늘리면 **id가 중복되어 PowerPoint가 그 열을 기본 파란 스타일로 다시 그리고 셀 내용이 사라진다**. 표 전체에서 `extLst`를 제거해 위치 기반 매핑으로 돌려야 한다(`scratchpad/doc/popups.py: strip_ext`). python-pptx로 읽으면 텍스트가 멀쩡히 보여서 렌더 전엔 못 잡는다.
- ⚠️ **목차 슬라이드는 항목 하나 = 텍스트박스 하나**(top 간격 457200). 문단을 늘리면 한 박스 안에서 뭉친다 → 박스를 복제해 아래로 내릴 것.
- 백업 `.bak_s35_pre_popups`.

## 세션37 갱신 (21 → 23슬라이드, 2026-07-09, 백업 `.bak_s37`)
- **스크린샷 7장 재캡처·교체**(세션35 todo 해소): s4 부화장·s6 농장·s7 도감·s9 인벤·s16 꾸미기·s17 상세·s18 사진 미리보기. 부화장은 갤러리 버튼이 늘어 콜아웃 ⑥ 추가·⑥~⑨→⑦~⑩ 재번호.
- **s5 식사 사진 찍기**: 플레이스홀더 3단계 흐름 박스를 걷어내고 **실제 스크린샷+콜아웃 5개**로 교체. 에디터엔 웹캠이 없어 `_shot`에 사진 텍스처를 밀어넣고 `mc.StopAllCoroutines()`로 Preview 코루틴을 죽인 뒤 dim 알파를 직접 세팅해 찍었다.
- **신설 `17_식사 기록 갤러리` · `18_수동 입력`**(구 17~19 팝업 슬라이드는 19~21로 재번호, 목차 우측단 10항목). 공용 팝업 표에 '식사 사진 삭제 확인' 행 추가, 관리자 모드 행에 빌드 시 선택 사실 반영.
- ⚠️ **`add_run`은 `a:endParaRPr` **앞에** 넣어야 한다**(`end.addprevious(r)`). 뒤에 붙이면 XML 순서가 깨져 **PowerPoint가 그 문단을 통째로 안 그린다** — python-pptx로 읽으면 텍스트가 멀쩡해 렌더 전엔 못 잡는다. `common.py: set_text_keep_style`에 반영됨.
- ⚠️ 새 슬라이드는 그림 없는 슬라이드를 복제하거나, **PICTURE 도형만 건너뛰고 나머지 shape XML을 deepcopy → `add_picture`로 새로 삽입**. 그림 도형을 deepcopy하면 `r:embed`가 깨진다.
- ⚠️ 콜아웃 원(지름 219750)에 **두 자리 수('10')를 넣으면 두 줄로 접힌다** — 폭을 320000으로 늘리고 `word_wrap=False`.
- ⚠️ 설명 박스(높이 868680)는 **한 줄짜리 문단 3개**가 한계. 넘치면 아래로 흘러 잘린다.
