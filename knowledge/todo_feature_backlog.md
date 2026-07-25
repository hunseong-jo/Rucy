---
name: todo-feature-backlog
description: 앞으로 추가할 기능 후보 목록(게임플레이/소셜/수집성장/식단연동) - 사용자가 다 좋다고 승인
metadata: 
  node_type: memory
  type: project
  originSessionId: 11189010-28a4-4bf7-ad2d-c47124f40766
---

Salad Farm 게임에 추가할 기능 후보. 2026-07-02 세션에서 사용자가 4방향 모두 좋다고 승인. 2026-07-04 세션에서 아래 구체 항목으로 다듬었고 사용자가 "전부 좋다"고 재승인 — 전부 나중에 만들 것.

1. ~~일일 퀘스트/도전과제~~ → **도전과제만 완료**(세션25, [[feature-achievements-dietreport]]). 일일 퀘스트는 사용자가 거절([[feedback-no-daily-quests]]) — 다시 제안하지 말 것.
2. ~~생명체 진화 시스템~~ → **완료**(세션26, [[feature-creature-evolution]]). 2차 진화는 추후 확장 여지.
3. ~~식단 통계/영양 리포트~~ → **완료**(세션25, [[feature-achievements-dietreport]]).
4. ~~스크린샷 공유~~ → **완료**(세션27, [[feature-farm-photo]]). 확장 여지: **촬영 후 미리보기 팝업(저장/삭제/다시 찍기 — 사용자 요청, 우선)**, 생물 카드 개별 촬영, NativeShare 공유 시트.
5. (소셜 확장, 원방향에 있던 것) 친구 농장 방문·랭킹 등 외부 연동 — 서버 필요라 후순위.

**Why:** 출시 준비는 거의 끝났고([[project_release_prep]]) 다음 단계로 기능 확장을 원함. 사용자가 후보 전부 승인했으므로 순서만 정해 하나씩 진행하면 됨.
**How to apply:** 다음에 "기능 추가" 얘기가 나오면 이 목록에서 우선순위를 정해 진행. 착수한 항목은 별도 메모리로 분리하고 여기서 제거.

**다음 세션 시작 포인트 (2026-07-04 세션27 종료 시점):** 남은 후보 = 친구농장·랭킹(5, 서버 필요 후순위) / 2차 진화 확장 / 다이아 2차 획득수단. 세션27에서 출시 블로커 전해소([[project-release-prep]])+경험치 성장([[feature-xp-growth-system]])+농장 사진([[feature-farm-photo]])+기획서 PPT 완료. 출시 잔여는 릴리스 AAB 빌드+Play Console. **다음 APK 빌드에 스플래시·경험치·사진 기능 포함해 실기기 확인 필요.**

## ✅ 세션32 점검 버그 4건 — 세션33에서 전부 수정·E2E 검증 완료 (2026-07-09)
1. **dex_50**: goal을 카탈로그 전체 종 수 동적 계산(41)으로 + "도감에 모든 종(41종) 등록하기" — 종 수가 또 바뀌어도 자동 추종.
2. **SpeciesDiscovered**: 카탈로그 존재 종만 카운트(삭제종은 슬라임 폴백 id 불일치로 판별). 에디터 세이브 기준 40→37.
3. **구세이브 마이그레이션**: GameState Load/Reload 파이프라인에 MigrateRemovedSpecies 추가 — 삭제종 생물 제거+마리당 다이아 1(작별 보상). rare9 주입 테스트로 검증.
4. **ApkBuilder**: 빌드 후 buildAppBundle 원복(try/finally) + "Build ▸ Android AAB (Release) to Desktop" 메뉴 신설(키스토어 비번은 Player Settings에 세션마다 입력 필요).
선택 항목(가이드북에 작별 선물 규칙 추가)은 미착수.
성능 점검 결과는 양호(텍스처 캐시·Update 청결·예외 0건)라 별도 조치 불요.
