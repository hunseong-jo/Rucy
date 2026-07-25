---
name: feature-synergy-ecosystem
description: 농장 생태계 시너지 - 특정 식단 속성 생물 3마리+ 배치 시 특수(시크릿) 생물 자연발생. 부화 5번으로 단축. 도감 시크릿 섹션.
metadata: 
  node_type: memory
  type: project
  originSessionId: df03e458-2b68-4fa5-a953-cc8538870c5a
---

## 농장 시너지 생태계 + 부화 단축 (2026-06-30 세션13)
[[project-diet-creature-game]] [[feature-creature-species]]의 기획 변경. **기획 충돌 해결**: '힐링 팜'인데 도감 100%를 위해 억지로 인스턴트를 먹어야 하는 모순 → 단순 수집 대신 **농장 배치 조합(시너지)으로 특수 생물이 자연발생**하는 생태계로 전환.

### 구현 (5가지 요청 전부 완료·런타임 검증)
1. **`SynergyManager.cs`(신규, static)**: `EvaluateFarm()` — 농장(location=farm) 생물의 dietCategory를 세어 규칙 충족 시 특수종 스폰. 규칙 `Rules[]`: veg≥3→worldtree_fairy, meat≥3→flame_lion, instant≥3→dust_monster(패널티/히든). 최적화: 농장 1패스 카운트 + 보유종 1패스 + 규칙 평가. 반환=이번에 새로 스폰된 종 id 리스트.
2. **카운트+스폰**: threshold=3. `GameState.AddCreature(special, farm)` + `RecordHatch`(도감 등록). 특수생물은 농장 용량 무시(자연발생 보너스). 트리거 카운트에서 secret 종은 제외.
3. **중복 방어**: 같은 특수종을 이미 보유(농장+보관 어디든)하면 스폰 안 함(`owned` HashSet). 삭제(보내기) 후엔 조건 충족 시 재등장 가능. (쿨타임 대신 보유체크 방식.) `SpeciesExists`: Get은 미존재시 기본종 폴백하므로 `def.id==id`로 실존 확인.
4. **도감 시크릿 섹션**: `CollectionManager` DietKeys/DietKor/DietIcon 배열에 `secret/시크릿/secret` 추가 → 기존 BuildSection이 5번째 섹션 자동 생성. 미발견은 ??? 실루엣(히든 힌트).
5. **부화 5번으로 단축**: `HatcheryManager.maxGrowth` 10→5(필드 기본값 + `Scenes/Hatchery.unity` 직렬화값 둘 다 수정). `DominantDietCategory`(가장 많이 먹은 식단→종) 유지.

### 특수 생물 3종 (CreatureDatabase에 추가, 총 61→64종)
- id `worldtree_fairy`(세계수 요정), `flame_lion`(**레온** — 세션35에 '불꽃 꼬리 사자'에서 개명), `dust_monster`(먼지 몬스터). 전부 **tier="secret", dietCategory="secret"** → 알 부화 풀(RandomId는 basic/rare/premium만)·도감 4분류에서 자동 제외, 시크릿 섹션에만.
- 스프라이트: 절차생성 128px PNG(`Assets/Art/Creatures/{id}.png`, MCP script-execute로 생성·Sprite 임포트 PPU110). placeholder 품질이나 테마별 구분 명확(초록 잎정령/주황 갈기사자/보라 먼지뭉치). 도감 시크릿 아이콘 `Assets/Resources/Icons/secret.png`도 생성.

### 배선 (FarmSpawner)
- `FarmSpawner.Start` 맨 앞에서 `SynergyManager.EvaluateFarm()` 호출 → 새 스폰을 그 프레임 농장 표시에 즉시 반영. **배치/회수가 농장 씬 리로드(또는 다음 진입)를 거치므로 단일 훅으로 모든 변경 커버.**
- 새로 스폰되면 `ShowSynergyPopup` 알림(먼지몬스터=경고톤 보라/그 외=축하톤 초록, 아이콘+이름+설명+확인).

### 검증 (MCP script-execute, 에러0)
- 채식 frog 3 배치→EvaluateFarm→worldtree_fairy 스폰+농장배치+도감hatchCount=1 확인. 2차 평가=0(중복방지 OK). 테스트 후 추가분 전부 제거+Save로 **유저 저장 원상복구**.
- ⚠️ 발견: **유저 현재 농장 식단구성 veg=1/meat=1/instant=3/dessert=0** → 농장 씬 열면 dust_monster 즉시 자연발생(기능 라이브 동작). 테스트 잔여 도감기록 cleanup 완료.

### 다중 스폰으로 확장 (2026-07-01 세션15)
- 요청: "3마리 이상 1마리"였던 걸 **구간별 다중 스폰**으로. `SynergyManager.SpawnTiers={3,5,8}` → 3↑1마리/5↑2마리/8↑3마리. `SpawnTargetFor(n)`=충족 구간 수.
- `EvaluateFarm` 재작성: 보유종을 HashSet→**종별 개수 Dictionary(`ownedCount`)**로 세고 `target - have`만큼 채움(이미 1마리 있고 목표2면 1마리만 추가). 삭제 후 재충전 동작 유지.
- 카운트 로직은 `CountFarmDiets()`로 분리(날씨 시스템과 공용). `ShowSynergyPopup`은 같은 종 여러 마리 시 "이름 x개수"로 묶어 표기.

### 먼지몬스터 패널티 + 양방향 시너지(떠남) (2026-07-04 세션25)
- **먼지 패널티 구현됨**: `SynergyManager.DustGoldMultiplier()` = 농장 먼지몬스터 마리당 골드 생산 -10%, 최저 ×0.5(`DustGoldPenaltyEach`/`DustGoldMultiplierFloor`). FarmIncome이 실시간 골드율(`RecomputeRates`)과 **오프라인 정산(`ComputeBaseRate`, int→float 변경)** 양쪽에 곱함. 날씨 배율과 중첩. 힌트에 "먼지↓" 표기, 스폰 팝업·가이드북에 안내 추가. 보관(storage)의 먼지는 패널티 없음(농장만 카운트).
- **양방향 시너지**: `EvaluateFarm()`이 `FarmEvalResult{spawned, departed}` 반환으로 변경(구 List 반환 아님). 보유 수(농장+보관)를 SpawnTiers 목표에 맞춤 — 부족하면 스폰, **조건 해제로 초과하면 떠남**(RemoveOne: 농장 배치분 우선 제거, 도감 기록은 유지, 재충족 시 재등장). FarmSpawner에 작별 팝업 `ShowFarewellPopup`("친구가 떠났어요…"/"잘 가!", 반투명 아이콘) 추가 — 등장·작별 동시 발생 시 작별이 위에 겹침.
- 검증: 에디터 인메모리 E2E 8케이스 ALL PASS(3→스폰1/5→2·배율 0.9/0.8, 축소 시 농장분 우선 제거, 전부 보관 시 전멸, 재충족 재등장) + 플레이모드 E2E(스폰 팝업 새 문구·힌트 "먼지↓"·+4/분(=4×0.9 반올림)·작별 팝업·복원 후 배율 1.0). 세이브 백업→복원 완료.

### 미해결/후속
- 스프라이트는 placeholder → 정식 아트로 교체 가능(같은 경로 PNG 덮어쓰기).
- 특수생물 농장 용량 초과 허용(예: 11/10 표시 가능) — 의도된 보너스. 다중 스폰이면 더 초과 가능.
- 관련 연출: [[feature-farm-weather]](식단 조합 날씨).
