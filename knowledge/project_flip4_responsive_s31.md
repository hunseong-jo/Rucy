---
name: project-flip4-responsive-s31
description: "Z 플립4 테스터 PPT 3건 대응(세션31) — 남쪽 울타리 하단UI 위 배치, 상점 탭 가로 스크롤, 하단 바 스트레치. 테스터 APK가 구버전이라 인벤 잘림은 기수정이었음."
metadata: 
  node_type: memory
  type: project
  originSessionId: 4d233b42-22c0-4e53-b42e-a324948bc5a4
---

# Z 플립4(1080×2640) 반응형 대응 (2026-07-08 세션31)

테스터가 `Desktop\버그 및 개선사항.pptx`로 3건 보고. **테스터 APK=7/4 빌드**라 ResponsiveGridFit·FenceFit(7/7 작성)이 미포함이었음 → 인벤토리 카드 잘림(슬라이드1)은 이미 수정돼 있었고, 나머지를 이번에 수정. **새 APK 빌드해서 테스터에게 전달 필요.**

1. **농장 남쪽 울타리/생물 경계(FenceFit.cs)**: 남쪽 울타리를 화면 맨 아래(cc.y-halfH)가 아니라 **하단 UI(FarmCreatureBar, 없으면 NavBarPanel) 상단의 월드 y 위에** 배치(GetWorldCorners→픽셀, Overlay 캔버스라 코너=픽셀좌표 → ScreenToWorldPoint + 울타리 절반높이 + southGap). 생물 CreatureWander.minY도 울타리+creaturePad 위로 클램프, 경계 밖 생물은 즉시 올림. DevTimePanel(관리자 시간 슬라이더)은 울타리를 가려 y460→560으로 올림.
2. **상점 탭 가로 스크롤(ShopManager.cs)**: 고정폭 1000 탭바 → 화면폭 스트레치(sizeDelta.x=-60)+가로 ScrollRect+HorizontalLayoutGroup(탭 preferredWidth 185)+ContentSizeFitter. `EnsureTabVisible`이 선택 탭(autoTab 진입 포함)을 스크롤로 보이게 함(Canvas.ForceUpdateCanvases 후 anchoredPosition 계산). 항목이 늘어도 스크롤로 수용.
3. **하단 바 폭 스트레치**: FarmCreatureBar·FarmDecorate DecorBar(1040 고정) → 앵커(0,0)-(1,0)+sizeDelta(-40,h). 힌트문구(1000)도 스트레치(-80). MealCaptureUI Box 940→900(플립4 캔버스폭 ~921, 내부 최대 요소 860).

검증: PlayModeWindow.SetCustomRenderingResolution(1080,2640)로 게임뷰 강제 후 플레이모드 캡처(ScreenCapture.CaptureScreenshot) — 농장 울타리 y=-4.48(카드바 위 노출)·상점 탭 스크롤+자동 스크롤 확인. 캔버스폭 공식: 1080/sqrt(h/1920) (match 0.5), 플립4=921 — **고정폭 UI는 921 이하로**.

## ★인벤 잘림의 진짜 원인(사용자 재보고 후 발견): NewUI 기본 sizeDelta(100,100) 함정
`new GameObject(name, typeof(RectTransform))`의 RectTransform 기본 크기 100×100. **스트레치 앵커를 걸어도 sizeDelta를 0으로 리셋 안 하면 부모보다 100 커진다** — 인벤 Grid가 뷰포트 801인데 901이 돼 셀 계산이 커지고 좌우 카드가 RectMask2D에 잘림(ResponsiveGridFit은 무죄, 커진 rect 폭 기준으로 정직하게 계산했을 뿐). 상점 탭 TabContent는 세로 +100이라 **둥근 모서리가 마스크에 잘려 각져 보임**. 수정: Inventory Grid·Shop Content·Shop TabContent·Collection Content에 `sizeDelta = Vector2.zero`. **런타임 UI에서 스트레치 앵커 컨테이너 만들면 반드시 sizeDelta 리셋** — UIFactory.Stretch는 offset까지 0으로 해줘서 안전, 수동 앵커 설정이 위험.

관련: [[project-device-bugfix-s26]] [[project-release-prep]] [[feature-creature-evolution]]
