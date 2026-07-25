---
name: feature-farm-photo
description: "농장 사진 찍기(스크린샷 공유) — 좌측 카메라 버튼, UI 숨기고 캡처→미리보기 팝업(저장/다시찍기/버리기)→갤러리 저장(NativeGallery). E2E 검증 완료, 미리보기 실기기 확인 남음."
metadata: 
  node_type: memory
  type: project
  originSessionId: e22249c8-f63f-4f50-bbb7-336a86f9a495
---

# 농장 사진 찍기 (2026-07-04 세션27, E2E 검증 완료)

백로그 '스크린샷 공유' 구현. 서버 없는 첫 소셜 기능.

- **FarmPhoto.cs** (신규, Farm 씬 Canvas에 컴포넌트로 저장됨): 좌측 버튼열 3번째(30,-394, 배경/꾸미기와 동일 스타일, 갈색) 카메라 버튼 → `CaptureRoutine`: HideNames 목록의 캔버스 직속 자식(상태바/네비/버튼/카드/팝업 등)을 켜져 있던 것만 숨김 → WaitForEndOfFrame → `ScreenCapture.CaptureScreenshotAsTexture` → 복원 → PNG.
- **저장**: 실기기 `NativeGallery.SaveImageToGallery(png,"SaladFarm",파일명)`(DIET_NATIVEGALLERY && !UNITY_EDITOR), 에디터는 `persistentDataPath/Photos/SaladFarm_yyyyMMdd_HHmmss.png`. 저장 후 ConfirmPopup "갤러리에서 바로 공유할 수 있어요". 연출(DayNight/FarmWeather/FarmDecor/월드 생물)은 사진에 포함.
- **camera.png** 아이콘: PIL 생성(스크래치 gen_camera_icon.py, 소멸), gear.png에서 색 추출(75,62,55) 24px 그리드×4=96px. 임포트 Sprite/Point/PPU100/무압축 수동 적용(새 PNG 함정).
- **FarmCountHud(생물 수)를 -395→-490으로 이동** (카메라 버튼 자리와 겹쳤음, FarmSpawner.cs).
- 공유 시트(Android Intent)는 미구현 — FileProvider 매니페스트 필요해 리스크. 나중에 NativeShare 플러그인 도입이 정석.

## ✅ 미리보기 팝업 (2026-07-05 세션28, 에디터 E2E 완료)
촬영 즉시 저장 → **미리보기 팝업(PhotoPreview)** 으로 변경. CaptureRoutine이 Save() 대신 `ShowPreview(tex)` 호출.
- **UI**: 딤+Box(880x1280, 크림) + 타이틀 "찰칵! 잘 나왔나요?" + 폴라로이드풍 흰 프레임(사진 비율대로 최대 780x960 맞춤, RawImage에 캡처 텍스처 직접 표시) + 버튼3 [저장](녹)/[다시 찍기](갈)/[버리기](적). Popup.cs 부착(order100 자동), 첫 촬영 때 1회 생성.
- **동작**: 저장=EncodeToPNG→기존 Save(갤러리/Photos)+ConfirmPopup 안내, 다시 찍기=즉시 닫고(SetActive(false), 캡처에 안 찍히게) TakePhoto 재실행, 버리기=AnimatedClose. 모든 닫힘 경로에서 `DisposePending()`(RawImage.texture=null 후 텍스처 Destroy — 누수 규칙) + OnDestroy에도.
- "PhotoPreview"를 HideNames에 추가(캡처 시 안 찍히게 안전장치).
- **하단 크롭**(사용자 피드백): 남쪽 울타리 아래 빈 배경이 어색 → `CropBelowFence()`가 Fence_South의 SpriteRenderer.bounds.min.y를 WorldToScreenPoint로 환산(Screen↔tex 해상도 비율 보정)해 그 아래 픽셀을 잘라냄(1080x1920→1080x1627). 원본 텍스처는 Destroy. 미리보기 프레임은 비율대로 자동 리사이즈(665x988).
- **에디터 E2E 검증 완료**: 팝업/버튼 배치 스크린샷, 저장 PNG UI 전무, 다시 찍기 후 새 텍스처+UI 복원, 저장 후 파일 생성+pending 해제, 버리기 후 pending 해제·파일 수 불변. **실기기 확인은 다음 APK 빌드 후.**

관련: [[todo-feature-backlog]] [[project-meal-capture]](NativeGallery)
