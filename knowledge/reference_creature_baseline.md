---
name: reference-creature-baseline
description: "생물 스프라이트 발 높이(bbox 하단)·방향 기준: 기본 114 / 성장 118 / 진화 123, 시크릿 120, 원본은 반드시 우향."
metadata: 
  node_type: memory
  type: reference
  originSessionId: b7ab036b-e49e-4281-9b1d-4bd6439cda55
---

# 발/방향 기준 수치 (128×128 캔버스)

**발** = PNG의 bbox 하단(불투명 픽셀 최하단 행). 스프라이트 피벗이 중앙이고 `FarmSpawner`가 단계별 y 보정을 하지 않으므로, **bbox 하단이 곧 화면상의 발 높이**다.

| 단계 | 폴더 | 목표 하단 |
|---|---|---|
| 기본(stage0) | `Assets/Art/Creatures` | **114** |
| 성장(stage1) | `Resources/CreaturesEvolved` | **118** |
| 진화(stage2) | `Resources/CreaturesEvolved2` | **123** |
| 시크릿(stage0) | 〃 기본 | **120** (snow_spirit 관례) |

- 한 종의 **idle·sleep·walk 프레임은 반드시 같은 dy로 함께** 옮긴다. 따로 옮기면 걷는 중에 위아래로 튄다.
- 걷기 프레임은 의도적으로 하단이 다르다(다리 들기 −2, 부유 ±2). 목표 하단은 **idle 기준**으로만 계산.
- 검증: 이동 후 불투명 픽셀 수가 변하면 잘린 것. y=127 행에 불투명 픽셀이 있으면 하단 잘림.

**방향**: `CreatureWander.cs:173`이 `_sr.flipX = dx < 0f` — 즉 **원본 PNG는 우향**이어야 한다(좌로 갈 때만 뒤집힘). 단, 정면 뷰 생물은 뒤집혀도 무방하므로 억지로 미러링하지 말 것. 기계적으로 우향 규칙을 적용했다가 bv3·pd3·rare6를 잘못 뒤집은 적 있음 — **반드시 이미지를 눈으로 비교하고 뒤집는다**.

관련: [[feedback-creature-art-pipeline]], [[project-session35-fixes]]
