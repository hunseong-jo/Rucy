---
name: feature_creature_sleep
description: 밤이 되면 생물이 눈 감고 취침. Zzz 효과 + 터치 시 10초 기상. 자는 스프라이트 61종 자동생성.
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e3f6f28-2ea9-4139-b96c-c267a2acfd5f
---

농장 취침 시스템(세션22, 2026-07-02). [[feature_day_night_cycle]]의 밤 시간대와 연동.

**자는 스프라이트 생성**: 원본 도트 PNG(Assets/Art/Creatures, 128px RGBA)에서 실루엣 내부의 진한 '눈' 블롭을 감지 → 주변 몸 색으로 지우고 감은 눈 아치(‿)를 그려 자동 생성. Python+PIL 스크립트(scratchpad/gen_sleep.py). 64종 처리, 대부분 완벽. dust_monster만 원래 흰 눈+화난 눈썹이라 반쯤 감긴 뚱한 느낌(허용). 결과는 `Assets/Resources/CreaturesSleep/<기본스프라이트명>.png`로 배치, .meta는 원본 bunny.png.meta(point 필터/PPU 110) 복제 + uuid4로 guid·spriteID 새로 생성.

**코드**:
- `CreatureCatalog.GetSleepSprite(id)`: `Resources.Load("CreaturesSleep/"+baseSprite.name)`, 없으면 평상시로 폴백, 캐시.
- `GameClock.IsNight`: 19시~06시.
- `CreatureSleep.cs`(FarmSpawner가 각 생물에 부착, species 주입): 밤이면 눈감은 스프라이트 교체+CreatureWander 정지+Zzz 생성. `WakeFor(10f)`로 10초 강제 기상. 절차생성 Zzz 스프라이트(폰트 의존 없이 z 3개 그림), ZzzBubble이 위로 떠오르며 알파 0→1→0 반복.
- `CreatureInteract.Interact()` 맨 앞에 `_sleep?.WakeFor()` 추가 → 자는 생물 터치 시 평소 반응 + 10초 기상 후 재취침. **부착 순서 주의**: FarmSpawner에서 CreatureSleep을 CreatureInteract보다 먼저 AddComponent해야 Interact.Awake가 참조 확보.

검증: 강제 동기 재컴파일 통과(error CS 0), 64 PNG 정상 임포트. 실기기 플레이 눈검증은 미완(관리자 슬라이더로 밤 옮겨 확인 가능). 쇼케이스 아티팩트 제작함.
