---
name: project-device-bugfix-s26
description: 실기기 APK 테스트 버그 4건 수정 + UI 정렬 캔버스 규칙(콘텐츠0<네비바50<팝업100) 도입. APK 재빌드·실기기 재확인 남음.
metadata: 
  node_type: memory
  type: project
  originSessionId: a5b0be76-a8df-44d1-96a8-31ce5b4f3d9b
---

# 실기기 버그픽스 (2026-07-04 세션26)

사용자가 APK 실기기 플레이로 버그 4건 발견(스크린샷 Downloads\버그1·2.png) → 전부 수정, 에디터 플레이모드 검증 완료.

1. **카메라 프리뷰 납작 왜곡**: `AspectRatioFitter`는 RectTransform 회전(videoRotationAngle 90/270)을 모른 채 계산해 실기기 세로에서만 왜곡. → ARF 제거, `SetPreviewAspect`가 rect를 직접 계산(비율은 항상 텍스처 w/h, 회전 시 덮을 프레임 가로/세로를 뒤집어 커버). **회전된 rect에 ARF 쓰지 말 것.**
2. **촬영 힌트-버튼 겹침**: 촬영/앨범/테스트 버튼 h150→120, y210→180 (MealCaptureUI).
3. **출석 팝업 제목이 셀 뒤에 깔림**: 셀 첫 줄 y -80→-230, 둘째 줄 -290→-450 (제목 -70~-160·부제 아래로). 나중에 생성된 UI가 앞 텍스트를 가리는 전형 패턴.
4. **하단 네비 바 가림**: [[project-ui-redesign]] 전 화면 공통 규칙 신설 — **일반 콘텐츠(order 0) < NavBarPanel(전용 Canvas overrideSorting order 50) < 팝업(Popup.cs OnEnable에서 order 100)**. 분리 캔버스엔 GraphicRaycaster 필수(없으면 버튼 안 눌림). 같은 order끼리는 계층 순서라 SetAsLastSibling(팝업 위 팝업) 동작 유지. 새 오버레이/팝업 만들 때 이 규칙 따를 것(Popup 컴포넌트만 붙이면 자동).

~~남은 것: APK 재빌드 후 실기기 재확인~~ → **완료(2026-07-04 세션27)**: APK 재빌드 후 사용자 실기기 플레이 "이상한 점 안 보임" 확인. 4건 전부 해결 종결. 관련: [[project-release-prep]]
