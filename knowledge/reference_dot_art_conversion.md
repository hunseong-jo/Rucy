---
name: reference-dot-art-conversion
description: 전 아트 도트화 완료 상태 + 스무스→도트 변환 파이프라인(팩터/판별 스크립트). 새 아트 만들 땐 도트로.
metadata: 
  node_type: memory
  type: reference
  originSessionId: 9ca63411-2201-48d1-b953-3f6ff440d717
---

## 아트 도트화 전수 완료 (2026-07-04 세션25)
사용자 방향: **게임 전체 아트를 도트 그림체로 통일**. 남아 있던 스무스 아트 23종을 일괄 변환, 이제 전 아트 도트.

### 변환한 것 (원본 백업: 스크래치패드 art_backup/, 세션 종료 후 소멸 가능)
- Resources/Icons 11종: book·cake·calendar·chart·decorate·flour·grass·meat·scenery·secret·trophy (128px→32그리드 ×4)
- Resources/Emotes 5종: exclaim·heart·note·smile·sparkle (64px→**32그리드 ×2** — 16그리드는 느낌표 점이 뭉개져 ×2로 재작업)
- Resources/Eggs 4종: add·basic·premium·rare (256px→64그리드 ×4)
- Resources/Decor 3종: tree·lake·flower (→64그리드 ×4)

### 이미 도트였던 것(건드리지 않음)
Art/Creatures 65종+CreaturesSleep, Art/Icons(내비·gear·gold·dia 등+app_icon), 울타리, Backgrounds 6종(snowfield·swamp 포함 — 눈검증 완료).

### 변환 파이프라인 (PIL, 파일 제자리 덮어쓰기 = .meta/GUID 유지)
```
RGBA → factor로 BOX 다운스케일 → 알파 이진화(>=96 → 255) → RGB MEDIANCUT 16색 양자화(디더 없음) → NEAREST 업스케일(원 크기 유지)
```
- 도트 여부 자동 판별: k∈{2,3,4,6,8} 블록 NEAREST 왕복 재구성 오차 diff<1.5면 도트(境界 1.2~1.6은 눈으로).
- **How to apply:** 앞으로 새 아이콘/아트를 만들 땐 처음부터 도트로(32그리드 아이콘 기준) 만들거나 이 파이프라인 통과시킬 것. [[reference-creature-art]] [[reference-farm-backgrounds]] 연계.
