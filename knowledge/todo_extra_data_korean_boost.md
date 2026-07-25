---
name: todo-extra-data-korean-boost
description: 나중에 할 일 - 한식 정확도 부스트용 extra_data 수집해서 4종 모델 재학습.
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f782284-0ba3-4cfd-a6aa-9b972ae4055b
---

## 한식 정확도 부스트 — HF 한식 데이터셋 자동연동 완료 (세션16)

[[todo-korean-food-model]]의 4종 모델이 Kaludi 카테고리셋만 기반이라 한식이 약했던 문제 해결.
**수동 extra_data 수집 대신** HF에 올라온 AI-Hub 한식 데이터셋을 스크립트에 자동연동함(2026-07-01 세션16, 사용자가 "HF 한식 데이터셋 자동연동" 선택).

### 무엇을 했나 (train_food4.py 수정 완료)
- 데이터셋 `Jiho0o0/kfood_image_englabel` (AI-Hub 한국음식 **143종×15장=2145장**, 영문 문자열 라벨) 자동 로드. `USE_KFOOD=True`, 가입·수동다운 불필요, Colab에서 그냥 돌리면 Kaludi+한식 합쳐짐.
- 라벨이 ClassLabel(int) 아니라 **문자열** → `HFStringBucketDataset` 클래스 추가(자체 88/12 train/val 분할).
- 한식 접미사 모호성(`tteok`=떡볶이2 vs 송편3, `jorim`=감자0 vs 고등어1) 때문에 **명시적 `KFOOD_MAP` 125종** 작성 + 로마자/영문 키워드 폴백(`kfood_bucket()`). 실제 라벨 검증 통과(떡볶이→instant, 송편→dessert, 감자조림→veg, 고등어조림→meat 등 정상).
- 클래스가중치 카운트 루프를 `hasattr(part,"idx")`로 일반화. `py_compile` 통과.

### 남은 것 (사용자가 Colab에서 실행)
1. Colab(GPU T4) → `train_food4.py` 업로드 → `!python train_food4.py` → `food.onnx` 생성.
2. `food.onnx` → `Assets/Resources/Models/food.onnx` 덮어쓰기 → Unity 재컴파일 → Play 검증(val_acc 0.85+ 목표).

### 참고
- 여전히 사진 직접 넣고 싶으면 `extra_data/{veg,meat,instant,dessert}` 폴더 방식도 그대로 동작(`FolderBucketDataset`).
- 매핑이 게임 취향과 다르면 `KFOOD_MAP` 딕셔너리만 고치고 재학습.

### ✅세션17 완료: 로컬 CPU 학습→블루스크린→재학습→게임적용 (2026-07-01)
- 실제로는 Colab 아니라 **로컬 PC(CPU, Python312)에서** `train_food4.py` 돌림. train=4307/val=808.
- **1차 시도**: 5 epoch(val_acc 0.797)까지 가다 블루스크린 강제종료 → `best.pt` 저장 중이라 0바이트 손상, `last.pt` 없어 재개 불가.
- **2차 재학습**: 8 epoch 완주. val_acc 0.731→0.759→0.757→0.786→0.797→0.807→0.809→**0.811(최종)**. `best.pt` 8.9MB 정상 저장.
- **ONNX export 함정**: `train_food4.py`의 기본 익스포터(torch 2.9+ dynamo)가 성공메시지에 ✅(✅) 이모지를 찍는데 **한글 콘솔 cp949가 인코딩 못 해 UnicodeEncodeError로 export만 실패**(모델은 멀쩡). → 해결책: 폴더의 `export_onnx.py`(`dynamo=False` 레거시 익스포터)로 재export, `PYTHONUTF8=1`도 세팅. 성공(8.9MB, 출력 shape (1,4)).
- **게임 적용 완료**: 새 food.onnx → `Assets/Resources/Models/food.onnx` 덮어씀(`.meta`는 GUID 유지 위해 안 건드림, 해시검증 동일). Unity(실행중) assets-refresh ForceUpdate → 콘솔 Error/Exception 0건.
- 베이스라인 백업: `ModelTraining/food_baseline_0630.onnx`(롤백용). 학습로그: `ModelTraining/train_run2.log`.
- **참고: val_acc 0.811로 README의 0.85+ 목표엔 살짝 못 미침(CPU 학습 한계). 정확도 더 필요하면 Colab GPU + USE_FOOD101=True로 볼륨 보강.** 하지만 한식 143종 포함돼 베이스라인보다 한식 인식은 개선.
