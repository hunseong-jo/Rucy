---
name: feature-meal-ai-v5-chicken
description: "식사 AI v5 — 치킨(튀김) 근접샷 오분류 해결. Food-101 부스트+타이트크롭 증강, RetryThreshold 0.35→0.30. E2E 완료."
metadata: 
  node_type: memory
  type: project
  originSessionId: b3c6f279-9972-44b9-87c0-9fd336978432
---

# 식사 AI v5: 치킨/근접샷 부스트 (2026-07-09 세션33)

사용자 보고 "프라이드 치킨→디저트 오분류"의 원인과 해결:

- **원인**: kfood 치킨 사진 15장이 전부 '접시 전체' 구도 → 근접 촬영(화면 가득 튀김옷)에서 무너짐. 재현: 홀드아웃 실사 치킨(Food-101 chicken_wings 100장, 학습 미사용)에서 구모델 정답률 원본 34%/근접 15~16%, 디저트 오답 9%.
- **해결(run5)**: ①Food-101에서 **스트리밍 수집**(전체 5GB 다운로드 없이 — `ethz/food101` + streaming=True, 클래스가 파일 내 정렬돼 있어 조기 종료 가능) chicken_wings 600장→extra_data/instant, donuts 200장→extra_data/dessert ②train_food4.py에 **TF_TRAIN_TIGHT**(RandomResizedCrop scale 0.12~0.5) 추가 — extra_data를 일반+타이트 2패스로 학습 ③12에폭 GTX1650 약 45분, val_acc 0.819.
- **결과**: 홀드아웃 치킨 원본 97%/근접50% 97%/근접35% 89%. kfood 스트레스(양념치킨 근접) 12/15 오분류→2/15. 비음식 5/5·음식 9/12(구모델과 동일) 회귀 없음. **에디터 Sentis E2E 완료**(치킨→인스턴트 0.82~1.00).
- **부작용 보정**: 신모델은 혼합 밥상에서 확률이 더 납작해짐(콜라주 conf 0.31~0.39) → **MealCaptureUI.RetryThreshold 0.35→0.30** 완화(validate_model.py도 동기화). 비음식은 별도 관문(NONFOOD_TH 0.5)이라 안전.
- 파일: ModelTraining/food.onnx(run5)=게임 적용본, 구모델 백업 best_run4_5class.pt/food_run4_5class.onnx, 로그 train_run5.log. 홀드아웃 100장은 스크래치패드(세션 소멸 주의 — 재평가 시 fetch 스크립트로 재수집).
- 다음 개선 여지: 실기기 실사진 확인([[project-flip4-responsive-s31]]의 새 APK 빌드에 포함됨), 한식 치킨무·소스 조합.

⚠️ **부작용**: 도넛200+타이트크롭이 "베이지 둥근 덩어리=디저트" 편향을 키워 **주먹(쥔 손)→디저트 오분류**를 유발 → 세션38 [[feature_meal_ai_v6_nonfood]]에서 비음식 보강 재학습으로 해결. 현재 게임 모델은 run6(v6).

관련: [[feature-meal-ai-v4-nonfood]] [[feature_meal_ai_v6_nonfood]] [[todo-korean-food-model]]
