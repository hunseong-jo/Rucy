---
name: todo-korean-food-model
description: 완료 - 커스텀 4종 food.onnx 학습+게임 통합+전처리 파리티 검증까지 끝남. 남은 건 한식 데이터 부스트(선택)뿐.
metadata: 
  node_type: memory
  type: project
  originSessionId: df03e458-2b68-4fa5-a953-cc8538870c5a
---

## ✅ 완료: 커스텀 4종 food.onnx 학습·통합 (2026-06-30 학습실행, 2026-07-01 검증)

[[project-meal-capture]]의 "정확도 개선". 원래 "보류 TODO"였으나 **세션14(튕긴 세션)에서 실제로 학습·통합까지 완료됨.** 세션15에서 그 결과를 복구·검증.

### 끝난 것
- `ModelTraining/best.pt`(9MB, 학습된 4종 가중치) + `ModelTraining/food.onnx` 생성됨.
- `Assets/Resources/Models/food.onnx`(8.8MB) **드롭인 완료**, `labels.txt` 없음(=4종 직접 argmax 경로 정상).
- `SentisMealAnalyzer.BuildInput`(149-194)+`Bilerp`(197-202) 디스크 정상. 학습 전처리 `TF_EVAL`(Resize256→CenterCrop224→ImageNet정규화)과 알고리즘 동일.
- **전처리 파리티 수치검증**(Python으로 BuildInput 재현 vs torchvision TF_EVAL): 실사진(부드러운 이미지)에선 정규화텐서 max차 0.042/평균 0.0035 ≈ **동일**, 추론 로짓도 일치. → 전처리 정확.

### ⚠️ 알게 된 함정 (antialiasing)
- C# `Bilerp`은 단순 2x2 바이리니어 / torchvision `T.Resize`는 다운스케일 시 **area-평균(antialias)**. 큰 축소(예 975→256, 3.8배)에서 **고주파(글자·격자) 이미지**는 max차 1.3까지 벌어짐. 실제 음식 사진은 부드러워 영향 거의 없음. 정확도가 의심되면 학습을 `T.Resize(256, antialias=False)`로 맞추거나 C#에 박스다운샘플 추가 고려.

### 남은 선택 작업 (정확도 더 올리려면)
- **한식 부스트(선택)**: AI-Hub "한국 음식 이미지"를 `ModelTraining/extra_data/{veg,meat,instant,dessert}/`에 분류해 넣고 `train_food4.py` 재학습 → 비빔밥/삼겹살/떡볶이 정확도 향상. (현재 모델은 Kaludi 카테고리셋 기반.)
- 매핑이 게임 취향과 다르면 `train_food4.py`의 FOOD101_MAP/KALUDI_MAP 수정 후 재학습.

### 실행 시 마지막 단계
- Unity 포커스 → 재컴파일(또는 Ctrl+R). 콘솔 stale 에러는 MCP degraded 때문이지 코드 문제 아님([[reference-unity-mcp-hang]]). 재컴파일 후 Play로 식사 촬영하면 실제 추론 동작.
