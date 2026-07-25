---
name: feature-meal-ai-bench-s39
description: "식사 AI 정량 벤치(재사용 홀드아웃 eval_bench) + run6 baseline. run7(Food-101) 회귀 폐기. run8(양념육류 오버샘플)이 육류 0.447→0.760·macro 최고 0.775로 채택·게임 교체. run9(경계강화) 실패."
metadata:
  node_type: memory
  type: project
  originSessionId: 4eae42bb-c73d-4bdf-b637-e8ca68b73cbd
---

# 식사 AI 정량 벤치 + run7(Food-101) 회귀 (2026-07-11 세션39)

[[todo_ai_bench_and_data_day]] 계획대로 '벤치 먼저 → 데이터 확충' 실행. **핵심 성과 = 재사용 벤치 확보**. run7(Food-101 추가)은 벤치로 회귀 확인 후 **폐기, run6 현행 유지**.

## 재사용 벤치 (ModelTraining/)
- **`build_bench.py`**: 홀드아웃을 `bench/<veg,meat,instant,dessert,nonfood>/`에 JPG로 1회 동결(오프라인·재현). 음식=kfood test분할(seed42, 학습은 train만)+Kaludi validation분할, 비음식=`hands_holdout/fist`40 + 얼굴·반려동물·손을 학습 미사용 뒤쪽 스트림 구간(offset 350/350/500~)에서 신규 수집. **MD5 오염검사 0건 확인**. 최종 채식150·육류150·인스턴트150·디저트115·비음식220.
- **`eval_bench.py`**: `python eval_bench.py <onnx> --tag <name>`. 게임(SentisMealAnalyzer)과 동일 멀티크롭(전체1+4구역60%)·임계값(NONFOOD_TH .5/MIN_CONF .55/RETRY_TH .30). 지표=**pred5 recall**(5-way argmax==정답, 학습로그 클래스별 val과 동일 정의)+확정정답률+5x5 혼동표. 결과→`bench/results_<tag>.md`·`.json`, `bench/COMPARISON.md`에 한 줄 누적.
- ⚠️낙관 편향 주의: 벤치의 kfood test·Kaludi val은 run6·run7 **양쪽 모델선택(val)에 동일 노출** → 절대값 약간 낙관. 단 before/after는 대칭이라 비교는 공정. fist·프레시 비음식은 어느 val에도 없는 완전 미사용본.

## run6 baseline (현행 게임 모델, pred5 recall)
| 채식 | 육류 | 인스턴트 | 디저트 | 비음식 | macro | 음식macro |
|---|---|---|---|---|---|---|
| 0.693 | **0.447** | 0.827 | 0.765 | 0.991 | 0.745 | 0.683 |
- **최대 약점=육류 0.447**. 혼동표: 육류 150장 중 **60장이 인스턴트로 오분류**(튀김·가공과 혼동). 학습 val(0.76)이 게임 실제 성능을 과대평가하고 있었음 — 벤치가 이 갭을 드러낸 게 핵심.

## run7 = Food-101 켬 → 회귀, 폐기
- `USE_FOOD101=True`+`MAX_PER_SOURCE=24000`(Food-101만, 비음식 확충 없음). 학습 train=27269(육류 7827로 최대 바구니), 12에폭 ~2h, val_acc 0.808.
- **벤치 결과 전 클래스 회귀**: 채식 .693→.613, **육류 .447→.253(-19pp!)**, 인스턴트 .827→.773, 디저트 .765→.817(유일 +), 비음식 .991→1.0, macro .745→**.691**. 육류→인스턴트 오분류 60→78장.
- **원인(구조적)**: 서양 Food-101 육류(steak/ribs)가 한식 육류(갈비·삼겹·찜) 분포로 전이 안 됨 + `FOOD101_MAP`의 coarse instant 편중(fried류 다수 →2)이 '인스턴트 어트랙터'를 키워 saucy/fried 한식 육류를 빨아들임. 에폭 더 늘려도 안 풀리는 매핑/분포 미스매치. → 세션33에 `USE_FOOD101=False` 둔 판단이 옳았음을 정량 확인.
- **조치**: food.onnx 교체 안 함(게임 사본 run6 그대로, MD5 1ba7a8…). `train_food4.py` USE_FOOD101 False·MAX_PER_SOURCE 12000으로 되돌림(주석에 회귀 근거). run7은 `food_run7_5class.onnx`/`best_run7_5class.pt`로 보관.

## 라벨 경계 진단 → 현행 매핑 확정(변경 없음)
`diag_meat.py`로 kfood test 육류를 요리명 단위 진단: **누수는 전부 '빨간 양념·볶음·조림·찜'**(닭갈비·닭볶음탕·주꾸미볶음·양념게장·고등어조림·해물찜·보쌈·떡갈비·육개장 등). 깨끗한 육류(삼겹살·갈비구이·불고기·설렁탕·삼계탕)는 0% 누수. 원인=모델이 "빨간 양념=인스턴트"(떡볶이·양념치킨 지배) 지름길 학습. 사용자와 3갈래 라벨 결정 → **모두 현행 유지**(양념 홈메이드 육류=육류·데이터로 해결 / 튀김 프랜차이즈=인스턴트 / 전·패티·순대=인스턴트). 매핑 불변이라 벤치·run6 baseline 재사용.

## run8: 양념육류 오버샘플 → 채택·게임 교체 ✅
- `train_food4.py`에 `HFStringBucketDataset(only_bucket/only_heads)` 필터 추가. `CONFUSABLE_MEAT` 23종을 kfood train에서 3패스(일반2+타이트1) + 전체 kfood육류 1패스 오버샘플(육류 바구니 →2898). Food-101 off, 매핑 불변.
- 벤치: **육류 0.447→0.760(+31pp)**, macro 0.745→**0.775(최고)**. 대가=인스턴트 0.827→0.680(-15pp, meat↔instant가 빨간양념 시각공간 공유). 채식·디저트·비음식 거의 불변.
- 사용자 결정으로 **채택**: `Assets/Resources/Models/food.onnx`=run8(MD5 788559e6…) 교체 완료. 실기기는 다음 APK. run6는 `food_run6_gamecopy.onnx.bak`로 롤백 보관.

## run9: 경계 양쪽 강화 → 실패(불채택)
- `CONFUSABLE_INSTANT`(떡볶이·양념치킨·라볶이·김치볶음밥 등 8종) 2패스 추가 + 육류 3x→2x로 완화. 의도=경계 밀지 말고 선명화.
- 결과 실패: 인스턴트 0.680 그대로(오류가 육류→디저트로 이동만), **채식 0.693→0.587 새 회귀**, macro 0.756(run8보다↓). → run8이 최선.

## 결론: meat↔instant는 데이터 한계 프론티어
kfood 요리당 ~13장뿐이라 오버샘플만으론 둘 다 못 올림(run6=육류0.45/인스0.83 ↔ run8=육류0.76/인스0.68은 같은 프론티어 위 점들). **진짜로 프론티어를 밀려면 실사 증량뿐** → 다음 레버=사용자가 `extra_data/{meat,instant}/`에 한식 실사진 넣고 재학습(run10). `EXTRA_FOLDER_MAP`이 meat/instant 폴더 지원. (생선≠고기 5번째 클래스는 여전히 범위 밖.)

## 백업/파일
- **게임 현행=run8** (`food_run8_5class.onnx`=`Assets/Resources/Models/food.onnx`, MD5 788559e6).
- 백업: run6 `food_run6_5class.onnx`·`best_run6_5class.pt`·`food_run6_gamecopy.onnx.bak`(롤백용), run7 `food_run7_5class.onnx`, run8 `best_run8_5class.pt`, run9 `food_run9_5class.onnx`·`best_run9_5class.pt`.
- 스크립트: `build_bench.py`·`eval_bench.py`·`diag_meat.py`(신규). 로그 `train_run{7,8,9}.log`. 벤치 `bench/`(MANIFEST.json·COMPARISON.md 4자 비교). **`train_food4.py`는 run8(현행 모델) 재현 상태로 정리됨**: USE_FOOD101=False·양념육류 3패스+전체육류1패스. CONFUSABLE_INSTANT는 정의만 두고 미사용(run9 재시도용 주석 포함). only_bucket/only_heads 필터는 HFStringBucketDataset에 상주.

관련: [[feature_meal_ai_v6_nonfood]] [[feature_meal_ai_v5_chicken]] [[todo_ai_bench_and_data_day]] [[project_meal_capture]]
