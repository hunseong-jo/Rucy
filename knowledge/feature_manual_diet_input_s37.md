---
name: feature-manual-diet-input-s37
description: "식사 사진 팝업 상단에 '수동 입력' 버튼 — AI가 틀리거나 못 읽을 때 5종을 직접 고르는 탈출구."
metadata: 
  node_type: memory
  type: project
  originSessionId: 5925c7df-2e07-4655-b6e1-0c94d1f71752
---

세션37. `MealCaptureUI` 상단 "식사 사진 찍기" 제목 **오른쪽에 '수동 입력' 버튼**. 누르면 박스를 덮는 패널에서 **균형 잡힌 식단(-1) / 채식(0) / 육류(1) / 인스턴트(2) / 디저트(3)** 5종을 직접 고른다.

AI 오분류·비인식 대비용 탈출구. 사용자는 "육식"이라 했지만 기존 UI 표기(`MealAnalyzer.CategoryNames`, `DietReport`)와 맞추려고 **"육류"로 통일**했다.

## 노출 시점
사용자 요청은 "사진을 찍은 후"였지만, **촬영 전(Preview)과 결과(Result) 양쪽에서 모두** 보이게 했다 — AI가 아예 작동 안 하는 경우(카메라 권한 거부·기기 카메라 없음)엔 결과 화면까지 갈 수 없기 때문. 분석 중(Analyzing)에만 숨긴다.

촬영 전에 고르면 사진 없는 끼니로, 결과 화면에서 고르면 찍어둔 사진과 함께 기록된다.

## 데이터 흐름
`MealCaptureUI.Create`의 콜백이 `Action<int>` → **`Action<int,string,bool>`(category, photoId, manual)** 로 바뀜.
`HatcheryManager.ApplyMeal(int, string photoId = "", bool manual = false)` → `GameState.RecordMeal(cat, photoId, manual)`.
확인을 눌러야 `MealPhotoStore.Save(_shot)`이 돈다(`Close()`가 `_shot`을 파괴하므로 저장이 먼저). 취소하면 저장 안 됨 — E2E로 검증.

균형(-1)은 기존대로 `dietCounts`에 집계되지 않고 알 성장만 시킨다.

## 함정
- 분류 이름 뒤에 조사를 붙이지 말 것. 받침에 따라 "채식**으로**"/"디저트**로**", "채식**이에요**"/"디저트**예요**"가 갈린다. 결과 문구는 이름을 띄어쓰기로 분리했다.
- 제목 Text의 pivot이 (0.5, **1**)이라 `anchoredPosition.y = -60`은 **위쪽 모서리**다(세로 중심은 -100). 옆에 버튼을 나란히 놓을 땐 중심을 -100에 맞춰야 한다.
- 덮는 패널의 배경 알파는 **1.0**이어야 한다. 0.98만 돼도 뒤의 검은 뷰파인더 프레임이 얼룩처럼 비친다.

관련: [[feature_meal_gallery_s37]], [[project_meal_capture]], [[feature_meal_ai_v5_chicken]]
