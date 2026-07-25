---
name: todo-ai-bench-and-data-day
description: "✅세션39 실행 완료 — 정량 벤치 구축+run6 baseline OK. run7(Food-101)은 회귀로 폐기(run6 유지). 결과는 [[feature-meal-ai-bench-s39]]."
metadata: 
  node_type: memory
  type: project
  originSessionId: 4eae42bb-c73d-4bdf-b637-e8ca68b73cbd
---

# 하루짜리 AI 학습 세션 계획 (2026-07-11 세션38에 합의, 다음 세션에 실행)

사용자가 "하루종일 AI 학습만 하고 싶다"고 해서 잡은 계획. **선택지 중 '정량 벤치 구축'+'데이터 대폭 확충' 두 트랙 승인.** 순서는 **벤치 먼저 → 데이터 확충**(자가 있어야 개선을 숫자로 판정). 작업 폴더 `Documents/DietCreature/ModelTraining/`, 현재 게임 모델 = run6([[feature_meal_ai_v6_nonfood]]).

## 왜 이 순서
벤치(measuring tool)가 없으면 데이터를 늘려도 좋아졌는지 알 수 없다. 오늘 주먹 문제도 홀드아웃 40장이 있어서 "60→10% 개선"을 확언할 수 있었다. 지금은 **손(hands_holdout/fist)만 정량 홀드아웃이 있고 나머지는 눈대중**이라 이게 최우선.

## 오전 — 정량 벤치 구축
- 5개 클래스(채식·육류·인스턴트·디저트·비음식) 각각 **학습 미사용** 홀드아웃 세트 확보.
  - 손: 이미 `hands_holdout/fist` 40장 있음(주먹). palm 등 추가하면 좋음.
  - 음식: kfood/Food-101에서 학습에 안 쓴 것 떼어내기. ⚠️학습 스트림과 겹치지 않게 **내용 MD5로 겹침 0 확인**(오늘 그 방식으로 검증).
  - 비음식: 손 외 얼굴·반려동물·실내도 홀드아웃 분리.
- 현재 run6로 baseline 점수 측정 → 표로 고정. 재사용 스크립트로 만들 것(`eval_bench.py` 같은).
- 기존 자산: `eval_hands.py`(손 멀티크롭 평가), `validate_model.py`(합성 비음식+kfood+콜라주). 이걸 클래스별 recall 벤치로 일반화.

## 오후 — 데이터 확충 + 재학습(run7)
- `train_food4.py`의 **`USE_FOOD101=False`→True** 켜기(지금 꺼져 있어 서양 음식·디저트 다양성 얇음). ⚠️GTX1650 4GB라 Food-101 전체(10만장)면 에폭당 시간 급증 → **`MAX_PER_SOURCE` 캡** 조정 필수.
- 비음식 카테고리 더(전자기기·식기·옷 등). `fetch_nonfood.py` 확장.
- run7 학습 → **같은 벤치로 run6 대비 before/after 숫자 비교**. 약점 클래스 보강 반복.

## 목표·한계(과약속 금지)
- 현실적 성과 = **재사용 벤치 확보 + 약점 클래스(육류 0.76·인스턴트 0.75 recall) 몇 %p 개선**. 극적 도약 아님.
- 데이터 늘린다고 정확도가 항상 오르진 않음 → 벤치로 판정하고, 회귀(다른 클래스 하락) 즉시 확인.
- **생선≠고기 5번째 클래스 분리는 이날 범위 밖**(재라벨링+게임 RecordMeal/종 매핑까지 바뀌는 대형 작업, 예전에도 현행 유지 선택). 원하면 별도 날 잡기.

## 실행 함정(오늘 겪은 것)
- 학습 로그 리다이렉트 시 **`PYTHONIOENCODING=utf-8`** 로 실행(cp949 em-dash 에러 회피).
- 코드 편집 후 **RequestScriptCompilation** 필요할 수 있음(MCP 스테일 컴파일, [[reference_mcp_stale_compile]]).
- HF 스트리밍은 뒤쪽 parquet 파티션에서 `Server disconnected` 잦음 → 앞쪽 위주 수집·재시도.
- ⚠️**장시간 학습은 백그라운드(nohup)로**. MCP script-execute 동기 장시간 호출은 타임아웃→재시도 폭주(오늘 APK 빌드가 10번 중복 실행됨).

관련: [[feature_meal_ai_v6_nonfood]] [[feature_meal_ai_v5_chicken]] [[feature_meal_ai_v4_nonfood]] [[project_meal_capture]] [[todo_korean_food_model]]
