---
name: reference-sprite-size-uniform
description: "생물 스프라이트는 반드시 128×128 — 농장은 고정 스케일이라 원본 크기가 그대로 화면 크기가 된다(세션35 '커졌다 작아졌다' 버그)."
metadata: 
  node_type: memory
  type: reference
  originSessionId: b7ab036b-e49e-4281-9b1d-4bd6439cda55
---

# 생물 스프라이트 크기는 128×128로 통일 (2026-07-09 세션35)

`FarmSpawner.cs:83`은 생물마다 `localScale = Random(0.9~1.2)`만 주고 **스프라이트 픽셀 크기로 정규화하지 않는다**. PPU가 110으로 같으므로 **PNG 해상도가 곧 화면 크기**다.

- **증상**: 성장(5레벨) 생물이 농장에서 커졌다 작아졌다 반복. 원인은 `Resources/CreaturesEvolved/bv1.png`·`bv2.png`만 **500×500**(세션34에 도트 변환 전 removebg 원본이 그대로 들어감)이고, 걷기 프레임·수면은 128px이라 프레임이 바뀔 때마다 3.9배↔1배로 튐.
- **해결**: `ArtBackups/s34_bv_pd3_fix/CreaturesEvolved/`의 128px 버전으로 복원(현재 sleep·walk와 bbox 완전 일치). 500px 원본은 `ArtBackups/s35_bv_500px_bug/`에 보관.
- **점검 명령**: 아트 교체 후 `Art/Creatures`, `Resources/Creatures*`(Sleep/Walk/Evolved/Evolved2/Evolved2Sleep/EvolvedWalk) 전 PNG의 `Image.size == (128,128)`를 확인할 것. 한 장만 어긋나도 그 종만 크기가 튄다.
- 같은 이유로 정지/걷기/수면 3종 세트는 bbox(특히 하단 여백)도 맞춰야 한다. 어긋나면 프레임 전환 시 위아래로 흔들린다.
- 관련: [[feature-stage1-art-s33]], [[feature-hatchling-art-s35]], [[feedback-creature-art-pipeline]]

**세션61(2026-07-17) unity_sprites 감사→수리 완료**: 아이콘 126×126 10장(Art/Icons 6+Resources/Icons 4)→투명 1px 패딩으로 128 통일(코드가 rect에 늘려 그리므로 1.6% 축소=무감지), camera.png 96→128은 패딩 아닌 **NEAREST 리스케일**(패딩하면 rect 안에서 25% 작아 보임), swamp.png 940→941은 오른쪽 열 복제 패딩(배경=불투명이라 투명 패딩 금지). app_icon.png 1024는 정상(스토어용)→Icons 폴더 밖 Assets/Art/로 .meta 동반 이동(guid 보존, ProjectSettings 참조 무사). **의도된 예외라 안 고친 것**: Resources/Decor 크기 제각각(bench 가로형·tree 세로형 등 종류별 rect를 코드가 따로 잡음)·Assets/Art PPU 64(울타리·Square)↔100(Egg)(월드 스프라이트 크기를 PPU로 잡음 — 바꾸면 화면 크기 변함). 원본 백업=my-agent/memory/unity_snapshots/dietcreature/edits/20260717_110926_png. 실기기 확인은 다음 APK에.
