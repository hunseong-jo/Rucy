---
name: todo-evolved-sleep-face-fix
description: "✅해결(v3): 진화 자는 눈 — 승인된 기본 CreaturesSleep 스타일(15px 실측 아치 템플릿+눈색 그대로)+가로 미러 질감 채움으로 11종 재생성(세션30)."
metadata: 
  node_type: memory
  type: project
  originSessionId: 3b13e08c-9eb4-4830-b0e3-b77e059978a2
---

# ✅ 진화 생물 자는 얼굴 수정 — 완료 (2026-07-07 세션30)

`Resources/CreaturesEvolved2Sleep/` 8종(bd3 bv2 premium5 premium10 pv3 rd1 rd2 rd3) 자는 눈 어색함 해결.

**최종 방식 v3(적용됨, v2 H+V블렌드+2px포물선도 "여전히 어색" 피드백 받아 재작업)**: 깬 스프라이트(CreaturesEvolved2/*)에서 재생성.
1. 눈 검출(어두운 blob, 얼굴 밴드 cy 25~100, 좌우 쌍 점수 선택)은 동일.
2. 채움 = **같은 행 좌/우 텍스처 가로 하드 미러**(스무스 블렌드 금지 — 도트 질감·얼굴 가로 밴드 보존. 세로 복사는 bd3처럼 눈이 프로스팅 경계에 붙으면 위 색이 흘러내림).
3. 감은눈 = **승인된 기본 CreaturesSleep 스타일 실측 템플릿**(bunny 15×5 아치: `#.............# / ###.........### / .######...##### / ...##########.. / ......####.....`)을 눈폭+4(9~17)로 가로 스케일, **색은 눈동자색 그대로**(밝히지 말 것). 폭 좁은 2px 포물선은 어색했음.

- 파이프라인: 스크래치패드 `fix_facing_sleep.py`(preview/apply 모드). 백업 `facing_backup/`.
- 수정 후 assets-refresh로 재임포트 완료. 자는 스프라이트는 밤에 GetSleepSprite(id,stage2)로 로드. 관련 [[feature-creature-evolution]] [[feature-creature-sleep]].
- 같은 세션 걷기 도트 6종 하부 가로 투명 seam도 인페인트 수정(별건, [[reference-dot-art-conversion]] 계열).
