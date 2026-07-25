---
name: feature-meal-ai-v6-nonfood
description: "식사 AI v6 — 주먹→디저트 오분류 해결. 비음식에 손·얼굴·반려동물 1210장 보강 재학습(run6). 주먹 비음식 35→88%, 음식 회귀 없음, 게임 적용 완료."
metadata: 
  node_type: memory
  type: project
  originSessionId: 4eae42bb-c73d-4bdf-b637-e8ca68b73cbd
---

# 식사 AI v6: 비음식 대폭 보강 (2026-07-10~11 세션38)

사용자 실기기 보고 "**주먹(쥔 손)→디저트로 인식**, 편 손은 비음식으로 정상".

## 원인 (재현으로 확정)
- 비음식 학습 데이터가 imagenette 800 + 합성 텍스처 400뿐이라 **손·신체가 전혀 없었다.**
- 게다가 **v5([[feature_meal_ai_v5_chicken]])가 이 문제를 악화시켰다** — 도넛 200장 + 타이트크롭(0.12~0.5)이 "화면 가득 찬 베이지색 둥근 덩어리 = 디저트" 편향을 강화. 주먹이 정확히 그 모양.
- HaGRID 홀드아웃 주먹 40장 재현(게임과 동일 멀티크롭 추론):
  | 모델 | 비음식(정답) | 디저트 오분류 | 전체컷 p4 |
  |---|---|---|---|
  | run4(v5 이전) | 68% | 32% | 0.71 |
  | run5(문제 모델) | **35%** | **60%** | 0.41 |
  | **run6(신규)** | **88%** | **10%** | 0.84 |

## 해결 (run6)
1. **`ModelTraining/fetch_nonfood.py`(신규)**: HF 스트리밍으로 `extra_nonfood/<cat>/` 수집 — 손(HaGRID `cj-mills/hagrid-classification-512p-no-gesture-150k`) 500 · 얼굴(`nielsr/CelebA-faces`) 350 · 반려동물(`Bingsu/Cat_and_Dog`) 350 · 실내(`nateraw/ade20k-tiny`) 10 = **1210장**. 실내 사물/전자기기는 학습에 이미 든 imagenette(교회·주유소·카세트플레이어 등)가 커버.
2. **`train_food4.py`에 `FolderNonFoodDataset` 추가**: `extra_nonfood/*`를 전부 비음식(4)으로, 카테고리별 시드 분할(train 85%/val 15%, 같은 카테고리가 train↔val에 새지 않게). 손 근접샷 대응으로 **일반+타이트크롭 2패스**. `USE_NONFOOD_DIR`/`NONFOOD_DIR` 설정.
3. 비음식 표본 1200 → **3260장**(extra_nonfood 1030×2패스 + imagenette 800 + 합성 400). 클래스 가중치가 자동 보정.
4. GTX1650 12에폭 약 1시간, **val_acc 0.859**(v5 0.819보다↑). 최종 클래스별 recall: 채식0.86 육류0.76 인스턴트0.75 디저트0.76 **비음식0.99**.

## 검증 (전부 통과)
- **홀드아웃 주먹**: 비음식 35→88%, 디저트 오분류 60→10%(위 표). 남은 5장은 확률 애매한 경계.
- **음식 회귀 없음**(`validate_model.py`): 합성 텍스처 비음식 5/5, kfood 실사 10/12 일치(2장은 비음식 아닌 인접 음식 오분류=soft), 4식단 콜라주→균형(중립) 정상.
- Unity 임포트 에러 0. **`Assets/Resources/Models/food.onnx` 교체 완료**(MD5 일치). 실기기 확인은 다음 APK.

## 파일·백업
- 게임 적용본 = `ModelTraining/food.onnx`(run6) = `Assets/Resources/Models/food.onnx`.
- 백업: `best_run5_5class.pt` / `food_run5_5class.onnx`(run5 파라미터·onnx), `food_run5_gamecopy.onnx.bak`(교체 전 게임 사본). 로그 `train_run6.log`.
- 홀드아웃 `hands_holdout/fist` 40장(학습 미사용), 진단 스크립트 `eval_hands.py`, 수집 `fetch_hands.py`.

## 함정
- **홀드아웃 오염 주의**: 같은 HaGRID 스트림에서 학습용(fetch_nonfood 앞 500장)과 홀드아웃(fetch_hands가 fist만 골라 40장)을 뽑아 겹칠 위험 → **내용 MD5로 겹침 0 확인** 후 검증. (주먹이 스트림에 드물어 앞 500장엔 안 들어감.)
- **학습 로그 리다이렉트 시 `PYTHONIOENCODING=utf-8` 필수**: 코드/print의 `—`(em-dash) 등이 cp949로 못 나가 UnicodeEncodeError로 죽는다([[reference_conhost_crash]]와 별개, [[project_session38_cleanup]]에도 기록).
- 임계값(NONFOOD_TH 0.5 / MIN_CONF 0.55 / RETRY_TH 0.30)은 그대로 유지. 비음식은 평균 p4·전체컷 p4 둘 다 0.5 넘어야 성립(중앙에 음식 작게 찍힌 사진 보호).

관련: [[feature_meal_ai_v5_chicken]] [[feature_meal_ai_v4_nonfood]] [[project_meal_capture]] [[todo_korean_food_model]]
