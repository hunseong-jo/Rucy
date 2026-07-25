---
name: feature-meal-gallery-s37
description: 식사 사진 날짜별 갤러리 신설. 사진을 앱 내부 저장소에 영속 저장하도록 프라이버시 원칙을 뒤집었다.
metadata: 
  node_type: memory
  type: project
  originSessionId: 5925c7df-2e07-4655-b6e1-0c94d1f71752
---

세션37에서 **식사 기록 갤러리**를 추가했다. 알 키우기 화면 우상단 버튼 5번째(설정0·가이드북1·도전과제2·리포트3·**갤러리4**), 카메라 아이콘.

**프라이버시 원칙이 뒤집혔다.** 기존 `MealCaptureUI.cs` 주석은 "사진은 저장하지 않고 분석에만 쓴다(프라이버시)"였고 `FreeShot()`이 분석 직후 텍스처를 파괴했다. 이제 **확인을 누른 사진만** `MealPhotoStore`에 저장한다(취소/다시 찍기는 저장 안 함). 게임 목적이 "힐링"만이 아니라 **자신의 식단 기록**이기도 하다는 사용자 결정. 기기 사진첩은 여전히 안 건드린다(앱 내부 `persistentDataPath/MealPhotos`, 앱 삭제 시 함께 사라짐).

## 구조
- `MealPhotoStore.cs`(신규): 사진 1장당 **원본(긴 변 720px, JPG q82) + 썸네일(200px, q75)** 두 파일. 썸네일이 따로 있는 이유 — 갤러리 그리드가 720px 텍스처 수십 장을 동시에 올리면 모바일 메모리가 못 버틴다. 실측 1장 ≈ 17KB(15KB+2KB) → 하루 3끼면 1년에 ~18MB.
- 저장 id는 `yyyyMMdd_HHmmss_난수` (같은 초 중복 방지). `SaveData.MealRecord.photo`엔 확장자 없는 id만.
- 축소는 `RenderTexture.GetTemporary` + `Graphics.Blit` + `ReadPixels`. 방향 뒤집힘 없음(검증함).
- `MealRecord`에 `time`(HH:mm) · `photo` · `manual` 필드 추가. 구버전 저장본은 필드 초기화자 값("" / false)으로 안전.
- `MealGallery.cs`(신규): 날짜 내림차순 섹션 + 3열 썸네일 그리드(240px, 중앙 정사각 크롭 `uvRect`). 14일씩 '더 보기'. 사진 없는 끼니는 분류 색 카드. 탭 → 뷰어(원본·시각·분류·AI/직접입력).
- 텍스처 수명: 칸을 먼저 파괴한 뒤 텍스처를 Destroy(살아있는 RawImage가 파괴된 텍스처를 가리키지 않게). 팝업 닫을 때도 전부 해제.

## 삭제 정책
뷰어의 **'사진 삭제'는 사진 파일만 지우고 끼니 기록은 남긴다**. 기록까지 지우면 식단 리포트·도전과제 수치가 소급해서 바뀌기 때문. 확인 팝업 문구로 명시.

## 남은 일
- **실기기 확인 대기** (에디터엔 웹캠이 없어 카메라→촬영→저장 경로는 미검증. 저장/로드/삭제/그리드/뷰어는 합성 텍스처로 E2E 검증 완료.)
- 문서 반영 완료: 기획서 Ver 1.4 s6 신설([[reference_design_doc_ppt]]), 화면정의서 17_식사 기록 갤러리 신설([[reference_screen_definition_ppt]]).
- 관련: [[feature_manual_diet_input_s37]], [[project_meal_capture]], [[feature_achievements_dietreport]]

## 함정
Hatchery Canvas에 **`ConfirmPopup`이라는 이름의 GameObject가 둘** 있다(씬의 보내기 확인용 + `ConfirmPopup.cs`가 런타임에 만드는 루트). `transform.Find("ConfirmPopup")`은 씬 쪽(비활성, 자식이 `ConfirmBox`)을 먼저 잡는다. 런타임 쪽을 원하면 `FindAnyObjectByType<ConfirmPopup>()` 컴포넌트로 접근할 것.
