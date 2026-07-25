---
name: reference-disk-space
description: "C 드라이브 공간 관리 — 드라이브 구성(C=SSD/D=HDD), ML 캐시가 C를 먹는 문제, 안전하게 비우는 법. 세션39에 Food-101 캐시 ~15GB 정리."
metadata:
  node_type: memory
  type: reference
  originSessionId: 4eae42bb-c73d-4bdf-b637-e8ca68b73cbd
---

# C 드라이브 공간 관리 (2026-07-11 세션39)

세션39에 C 여유가 **1GB 미만**까지 떨어져 정리함. 원인=AI 학습용 HuggingFace 캐시.

## 드라이브 구성 (중요 — 어디에 뭘 둘지 결정)
- **C: 238GB = Samsung NVMe SSD (빠름, 시스템)**. 여유가 늘 빠듯.
- **D: 932GB = Seagate ST1000LM035 HDD (5400rpm, 느림), 여유 ~650GB 넉넉**.
- E: 14GB = SanDisk USB 메모리(Cruzer Blade).
- ⚠️**D는 기계식 HDD** → Unity 프로젝트(특히 랜덤 I/O 심한 `Library`)를 D에 두면 임포트·컴파일·플레이 진입이 느려짐. **프로젝트 본체는 C(SSD)에 유지가 정답.**

## C를 먹는 것들 (세션39 실측)
- `C:/Users/user/.cache/huggingface/` — HF 데이터셋/hub 캐시. Food-101이 **hub 10GB + Arrow 5GB = ~15GB**였음. run7 폐기했으므로 **삭제함**([[feature_meal_ai_bench_s39]]). 남은 것: imagenette 2GB·kfood 0.63GB·Kaludi 0.21GB(현행 학습 파이프라인용, 보존).
- `Documents/DietCreature/` 프로젝트 = 11.7GB인데 **그중 11.3GB가 `Library`(재생성 캐시)**. 실제 원본(Assets 등)은 ~0.4GB.

## 공간 비우는 법 (안전 순)
1. **폐기된 ML 캐시 삭제**: `.cache/huggingface`에서 안 쓰는 데이터셋 폴더 rmtree(재다운로드 가능). Food-101은 이미 삭제.
2. **Library 비우기** = 즉시 ~11GB. 단점: 다음 Unity 실행 때 **전체 재임포트+재컴파일(수 분~십수 분, 1회)** + **어차피 다시 커짐**(일시적). Assets/.meta/ProjectSettings는 안전(원본 보존). **반드시 Unity 닫고** 삭제.
3. **지속 해결**: ML 캐시를 D로 리다이렉트(`HF_HOME`/pip cache dir을 D:로) → 앞으로 학습 다운로드가 C를 안 먹음. HDD여도 데이터라 무방.

## 세션39 조치 결과
Food-101 캐시(hub+Arrow ~15GB) 삭제 → **여유 1.0GB → 11.18GB**. Library 삭제·캐시 리다이렉트는 사용자가 "나중에" 함(미실행).

관련: [[feature_meal_ai_bench_s39]] [[project_meal_capture]]
