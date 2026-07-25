---
name: reference_farm_backgrounds
description: 농장 배경 5종 도트 아트 원본 위치·교체 방법·규격(9:16). 사용자가 직접 준비.
metadata: 
  node_type: memory
  type: reference
  originSessionId: fbbd8d3a-fd38-4751-a174-5b126c834d6c
---

농장 배경(BackgroundCatalog 5종: default/meadow/swamp/desert/rocky)은 **사용자가 직접 도트 아트로 준비**한다.

- **원본 폴더**: `G:\내 드라이브\도트로 변환\` (파일명이 타깃 id와 동일: default.png/meadow.png/swamp.png/desert.png/rocky.png).
- **교체 방법**: `Assets/Resources/Backgrounds/<id>.png`에 **PNG 내용만 덮어쓰고 `.meta`는 유지**(에셋 GUID/임포트 설정 보존 → 상점·선택 팝업 참조 안 깨짐). 그 후 Unity assets-refresh.
- **규격**: 9:16 세로(현재 941×1672, swamp 940). `FarmBackground.ApplyBackground`가 `sp.bounds.size` 기준 **cover-fit**(Mathf.Max(wW/sz.x, wH/sz.y)*1.02)이라 **비율만 9:16이면** 해상도 달라도 잘림/여백 없이 들어감. maxTextureSize 2048이라 1672 클램프 안 됨, Sprite 타입은 NPOT 리사이즈 없음.
- 2026-07-02 세션21에 5종 전부 신규 도트로 교체 완료(원본 백업 scratchpad). 기존은 360×640 절차생성이었음. [[reference_creature_art]]

**알·울타리 도트 교체 (2026-07-04 세션24)**: 사용자 폴더 `C:\Users\user\Downloads\도트변환\`의 Egg/fence-h/fence_v를 `Assets/Art/{Egg,fence_h,fence_v}.png`에 같은 방식(PNG만 덮어쓰기·meta 유지)으로 교체. 셋 다 filterMode 0(Point)로 변경(도트 선명). fence_v는 64×1024로 원본(100×1600)과 해상도가 달라 **meta의 spritePixelsToUnits를 100→64로** 조정해 월드 크기 1×16 유지 — 해상도 다른 도트 교체 시 이 PPU 트릭 사용. 울타리는 FenceColor 틴트를 받으므로 흰/회색 계열이어야 함.

**아이콘 도트 교체 (2026-07-04)**: `Downloads\아이콘도트\` 13종 → `Assets/Art/Icons/`(13개 전부) + `Assets/Resources/Icons/`(겹치는 9종: bag/dex/dia/farm/gear/gold/meal/nest/shop — 두 폴더는 동일 파일 중복본이라 양쪽 다 교체해야 함). PNG만 덮어쓰기·meta 유지·filterMode 0(app_icon 제외). Resources 전용 6종(book/cake/flour/grass/meat/secret)은 미교체(사용자가 안 그림). 원본 백업 scratchpad/icons_backup.

**가로 울타리 픽셀 밀도 통일 (2026-07-04)**: 가로(900px/9u=100px/u)가 세로(64px/u)보다 도트가 잘아 작아 보임 → fence_h를 **픽켓 경계 피해 132~708px 크롭(576px=정확히 9u @PPU64)** + PPU 64로 통일. 두께 1→1.5625u가 되므로 Farm씬 Fence_North y=8.28125 / Fence_South y=-4.98125로 이동(안쪽 경계 7.5/-4.2 유지, 씬 저장). 원본 900px는 scratchpad에 백업(세션 임시라 필요시 도트변환 폴더 원본 사용). 픽켓 간격 60px·폭 26px(x=18+60k~43+60k).
