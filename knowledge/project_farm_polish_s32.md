---
name: project-farm-polish-s32
description: "세션32: 생물 8종 삭제(49→41), 만쥬·초코·산호·애플 축소, 작은 폰트 상향, 농장 생물 겹침 방지(분리 로직). 프리팹 직렬화 기본값 함정 기록."
metadata: 
  node_type: memory
  type: project
  originSessionId: 4d233b42-22c0-4e53-b42e-a324948bc5a4
---

# 농장 폴리시 4건 (2026-07-08 세션32)

1. **크기 축소**: rd1 만쥬·rd3 초코·rare6 산호·rare2 애플 진화 도트(Evolved2+Sleep+walk 전부) 콘텐츠 0.86배(바닥 중앙 기준). 백업: 스크래치패드 shrink_backup/(세션 소멸 주의).
2. **8종 삭제(49→41)**: rare9 아쿠아(veg) / rare3 자수정·rm2 호랑(meat) / ri1 사탕팝·ri3 버블·pi2 픽셀(instant) / rare7 라벤더·premium6 별빛천사(dessert). 백업 `CreatureDatabase.asset.bak_s32_delete8`. 코드 하드코딩 참조 없음 확인. **에디터 세이브(Team_HS)의 보관함 4마리도 제거**(save.json.bak_s32_delete8). 삭제종 조회는 slime 폴백.
3. **폰트 상향 28곳**: NewText 크기 22→26, 25→28, 26→29, 27→30, 28→31, 30→32 (`, NN, TextAnchor` 패턴 일괄 치환).
4. **겹침 방지**: ①FarmSpawner.PickSpawnPos — 스폰 시 12회 샘플링 최원거리(목표 2.0) ②CreatureWander.ApplySeparation — separation 1.6 안이면 서로 밀어냄(push 1.4/s, 벤치 앉기 중 제외, 비활성=정지형·자는 생물도 '피할 대상'에 포함(static _all, Awake/OnDestroy 등록)) ③PickNewTarget이 남의 옆(separation 안) 목적지 회피(8회 시도). 지나칠 때 순간 근접은 자연스러운 것으로 수용.

## ⚠️ 프리팹 직렬화 기본값 함정 (겹침 방지에서 2연속 헛발)
- **스테일 컴파일**: assets-refresh만으론 재컴파일 안 될 수 있음 → CompilationPipeline.RequestScriptCompilation 필수([[reference-mcp-stale-compile]]).
- **핵심 함정**: 프리팹(Creature.prefab)에 이미 있는 컴포넌트에 **새 필드를 추가하면, 임포트 시점의 클래스 기본값이 프리팹 인메모리 객체에 구워짐**. 이후 클래스 기본값을 바꿔도 (프리팹 파일에 그 필드 라인이 없어도!) 인스턴스는 옛 값을 씀. 새 GameObject.AddComponent는 새 기본값을 받아 검증이 어긋남. **해결: 프리팹 YAML에 필드 값을 명시적으로 추가**(separation: 1.6, separationPush: 1.4). 튜닝값은 프리팹이 SSOT.

관련: [[feature-creature-species]] [[feature-creature-evolution]] [[project-flip4-responsive-s31]]
