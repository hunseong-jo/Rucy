---
name: feature-meal-ai-v4-nonfood
description: v4 5클래스 모델(식단4+비음식) + 멀티크롭 추론으로 천장→디저트/밥상→채식쏠림 해결. 학습·검증·게임적용 완료.
metadata: 
  node_type: memory
  type: project
  originSessionId: 52becfc1-4efe-41ab-b901-b0ae0b46a35c
---

# 식사 AI v4 — 비음식 거부 + 밥상(혼합식) 대응 (2026-07-03 세션23)

사용자 실기기 리포트("한식 밥상→무조건 채식, 천장→디저트, 정확도 엉망")를 해결. [[project_meal_capture]] 후속.

## 무엇이 바뀌었나
1. **모델 5클래스화**: `food.onnx`가 식단4 + **인덱스4=비음식(nonfood)** 출력. 비음식 데이터 = imagenette 실사 800장(tench 물고기 제외) + 합성 텍스처 400장(천장/벽지/타일/줄무늬/저조도, `SyntheticTextureDataset`). GPU 12에폭 **val_acc 0.856**(4클래스 3차 0.833보다↑), **비음식 recall 0.99~1.00**.
2. **멀티크롭 추론** (`SentisMealAnalyzer.Analyze`): 전체1+4구역(60%) 5회 추론 → softmax 평균. 밥상처럼 구역별 판정이 갈리면 확률이 납작해져 '균형 잡힌 식사(중립)' 대역에 착지. `BuildInput(photo, rx, ry, rs)`로 크롭 파라미터화.
3. **비음식 판정 규칙**: 평균 p[4]>0.5 **그리고 전체컷 p[4]>0.5 둘 다**일 때만. (음식이 중앙에 작게 찍히면 구석 크롭=식탁 배경이라 평균만으로는 오판 — 비빔밥 실사에서 실제 발생해 규칙 보강.) 음식 confidence는 4종 재정규화 `p[best]/(1-p[4])` → 기존 3대역 로직 그대로.
4. `DietResult.nonFood` 필드 + `MakeNonFood()` (IMealAnalyzer.cs). MealCaptureUI가 비음식이면 "앗, 음식이 아닌 것 같아요!" 전용 문구(soft block, "그래도 기록" 유지).

## 검증 (전부 통과)
- Python `ModelTraining/validate_model.py`(게임과 동일 멀티크롭 재현): 천장/벽/타일/어두운방 5/5 비음식, 실제음식 12장 비음식 오판 0(9 정확+3 균형/인접), 4식단 콜라주→균형(중립).
- Unity 에디터 script-execute E2E: 천장/벽/어두운방 → nonFood=True, 비빔밥→채식 0.91, 삼겹살→육류 0.99 (Python과 일치).
- 컴파일 에러 0.
- **✅실기기 재확인 완료(2026-07-04 세션27)**: 사용자 체감 "80% 정확" → 유일한 불만 사례가 쭈꾸미볶음+고등어조림 밥상→육류였는데, 해산물=동물성이라 **육류가 정답**(오분류 아님)으로 합의·종결. 임계값(NonFoodThreshold 0.5/MinConf 0.55/Retry 0.35)은 그대로 유지. 진짜 이상한 케이스가 나오면 사진을 다운로드 폴더에 받아 `ModelTraining/validate_model.py`(게임과 동일 멀티크롭 재현)로 분석하기로 함. "생선≠고기" 분리는 5번째 식단 클래스 추가(재학습)라 별도 대형 작업 — 사용자가 현행 유지 선택.

## 같은 세션 기타 작업
- **농장 기분 기능 삭제**(사용자 요청 "필요없음"): Farm.unity의 우상단 `MoodButton`(":(" 버튼)+`EmotionPanel` 오브젝트 삭제, FarmDecorate.cs 숨김목록에서 "MoodButton" 제거, FarmIncome.cs 주석 정리. 컴파일·씬 검증 완료. `Assets/_Recovery/`의 옛 씬 백업 2개엔 흔적 남음(미사용이라 방치).

## 파이프라인 메모 (함정)
- datasets 5.0은 스크립트 데이터셋 미지원 → imagenette는 `revision="refs/convert/parquet"` + 컨피그 없이 로드(train 28,407 = 3해상도 합본, 캡으로 무관).
- 학습 로그 리다이렉트 시 stdout 버퍼링으로 실시간 안 보임 → `best.pt` mtime으로 진행 추정.
- 백업: `ModelTraining/food_run3_4class.onnx` / `best_run3_4class.pt` (롤백용), 로그 `train_run4.log`.
- 옛 4클래스 best.pt를 export하려면 `export_onnx.py`의 NUM_CLASSES=4로.
