---
name: project-session33-fixes
description: "세션33: 설정 초기화 버튼·도전과제 정렬·모두 받기·출석 순환 UI·관리자 스위치 잔존·시크릿 보관/도감 단일화 + 다음 APK 실기기 대기 목록."
metadata: 
  node_type: memory
  type: project
  originSessionId: b3c6f279-9972-44b9-87c0-9fd336978432
---

# 세션33 소수정 2건 + 실기기 확인 대기 목록 (2026-07-09)

1. **설정 '데이터 초기화' 무반응 수정**: SettingsPanel의 자체 확인 팝업이 sortingOrder 기본 100(설정 팝업과 동일)이라 위로 못 떠서 무반응처럼 보임 → 공용 ConfirmPopup(order 210)으로 교체하고 자체 팝업 코드 삭제. **규칙 재확인: 팝업 위 확인 팝업은 반드시 공용 ConfirmPopup 사용**(order 100 겹침 함정, [[feature-xp-growth-system]]에도 기록). 플레이모드 E2E 완료(초기화 시 에디터 세이브 백업→복원).
2. **도전과제 정렬**: 달성(받기 가능) 최상단 → 미달성 진행도 높은 순 → 수령 완료 맨 아래. AchievementBook.RebuildList에 LINQ OrderBy(안정 정렬, List.Sort는 불안정이라 회피). E2E 완료.

## 세션33 2차분 4건 (2026-07-09, 컴파일+RestoreIfNeeded 단위검증 완료, 플레이모드 E2E는 미실시)
3. **도전과제 '모두 받기' 버튼**: 팝업 하단 좌측(닫기와 나란히 340px 2개). AchievementBook.ClaimAll — 달성·미수령 전부 합산 1회 저장, HasClaimable()로 interactable 토글(RebuildList 끝에서 갱신).
4. **출석 순환 UI 버그 수정**: 7일차 수령 후 다음 날 attendanceDay=7 그대로라 7칸 전부 체크+1일차 링 겹침 → RefreshCells에서 `if (claimed >= 7 && can) claimed = 0`.
5. **관리자 모드 스위치 잔존 수정**: Settings.adminMode와 cheatActive가 별개 플래그 — 재시작 시 RestoreIfNeeded가 재화만 복구하고 스위치(+즉시부화 치트)는 ON 잔존 → RestoreIfNeeded에서 adminMode도 무조건 false(관리자 모드=세션 한정 확정).
6. **시크릿 생물 정책**: 성장은 원래 차단돼 있었음(GrowthCatalog.CanGrow가 유일한 레벨업 경로 게이트). 신규: 농장 시크릿의 '보관' 버튼 숨김(CreatureDetailPopup.Refresh, 구세이브 보관분의 '농장에 배치'는 유지), 도감 상세는 3단 진행도 대신 기본 컷 1장 가운데 표시(CollectionManager._stageArrows 신설, 아이콘0 x를 -250↔0 이동).

## 다음 APK 빌드에 포함될 미확인 항목(몰아서 실기기 확인 권장)
> ✅ 세션38(2026-07-10)에 **APK 빌드 완료** — `Desktop\SaladFarm.apk` 82MiB, 릴리스 서명. 아래 항목 전부 이 APK에 들어 있다. 이제 남은 건 **실기기에 설치해 확인**하는 일. ([[project_session38_cleanup]])
- 식사 AI v5 모델([[feature-meal-ai-v5-chicken]]) — 실사진 치킨 확인
- Z플립4 반응형 3건([[project-flip4-responsive-s31]])
- GPGS 로그인/백업([[project-login-gpgs]]) — 단, 콘솔 설정+실제 AppId 교체 후에만 동작
- 농장 사진 미리보기 팝업([[feature-farm-photo]], 세션28부터 대기)
- 세션32 버그픽스 4건([[todo-feature-backlog]]) 중 마이그레이션 동작
- ⚠️ GPGS로 커스텀 gradle 템플릿(mainTemplate.gradle 등)이 새로 활성화됨 — 빌드 실패 시 여기부터 의심
