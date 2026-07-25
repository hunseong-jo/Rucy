---
name: feature-release-gift
description: "생물 보내기 작별 선물 — 다이아 1 + 레벨 구간별 성장 아이템(5렙↑ 5개/10렙↑ 10개), '○○가 선물을 주고 떠났어요' 팝업. 부화 직후 보내기는 다이아 1만."
metadata: 
  node_type: memory
  type: project
  originSessionId: 4d233b42-22c0-4e53-b42e-a324948bc5a4
---

# 생물 보내기 작별 선물 (2026-07-08 세션32)

- **CreatureDetailPopup.ReleaseCreature**: 보내기 확정 시 다이아 1개 + 생물 식단의 성장 아이템 — 레벨 <5는 0개(다이아만), ≥GrowLevel(5) 5개, ≥EvolveLevel(10) 10개. 시크릿(식단 인덱스 -1)은 다이아만. 팝업 `"{이름}{이/가} 선물을 주고 떠났어요.\n\n다이아 1개\n{아이템명} N개"` → 확인 시 CloseAll+_onMoved.
- **HatcheryManager.OnConfirmYes**(부화 직후 보내기): 다이아 1개 + 동일 문구 팝업(ConfirmPopup.Get(this,_font)). 기본알 무한이지만 부화에 식사 10회 필요해 악용 여지 낮다고 판단.
- Iga() 조사 헬퍼를 internal로 승격(CreatureDetailPopup.Iga — 받침 유무 이/가).
- E2E: lv10 만쥬(+10)·lv5 새싹(+5) 보내기 → 지급·목록 제거·팝업 문구 확인, 테스트 보상 롤백 완료.
- **사후 버그: "재화가 안 늘어요" — 데이터는 정상, TopStatusBar가 Start/OnEnable에만 갱신**되던 것. Update에서 Gold/Dia 변화 감지 시에만 Refresh(int 비교 2회, 문자열 갱신은 변화 시만)로 수정 → 이제 씬 내 어떤 재화 변동도 즉시 표시. 표시 안 바뀌는 버그는 항상 '데이터 vs 표시' 분리 확인부터.
- 기획서 PPT([[reference-design-doc-ppt]]) **s16에 반영됨**(세션39 확인): "보내기 시 작별 선물(다이아 1 + 5렙↑ 성장아이템 5개 / 10렙↑ 10개)", s14에 작별 팝업 문구. (초기 '미반영' 메모는 세션35/37 PPT 갱신 때 이미 해소됨.)

관련: [[feature-xp-growth-system]] [[feature-creature-evolution]]
