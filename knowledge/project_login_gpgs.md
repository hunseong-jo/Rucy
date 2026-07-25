---
name: project-login-gpgs
description: 로그인 방향 확정 — GPGS 자동 로그인 + Saved Games 백업(UGS 아님). 힐링게임이라 단순하게.
metadata: 
  node_type: memory
  type: project
  originSessionId: b3c6f279-9972-44b9-87c0-9fd336978432
---

로그인/클라우드 세이브 방향 (2026-07-08 세션33 결정):

- **GPGS(Google Play Games Services) v2로 확정.** UGS(익명+Cloud Save, 친구 확장 유리)도 검토했지만 사용자가 "힐링게임이니 단순하게" GPGS 선택. 친구농장·랭킹은 어차피 후순위 백로그.
- 구성: 앱 시작 시 조용한 자동 로그인(실패해도 로컬 플레이 지속, 로그인 강제 금지 — [[feedback-no-daily-quests]]의 무마찰 철학과 동일 맥락), Saved Games API로 save.json 통째 백업/복원.
- 설정 화면 "로그아웃" 버튼은 현재 Intro 씬 이동뿐인 자리표시자 → 로그인 상태 표시/계정 전환으로 대체 예정.
- **세션33에서 코드 전부 구현 완료 (2026-07-09)**:
  - GooglePlayGamesPlugin **v2.1.0** 임포트(Assets/GooglePlayGames + EDM4U 동봉). GPGSAndroidSetupUI.PerformSetup을 **자리표시자 AppId "1234567890"** 으로 실행해 둠 — 실제 ID 받으면 같은 방법으로 재실행.
  - `GpgsCloudSave.cs`: RuntimeInitializeOnLoadMethod 부트스트랩, 조용한 자동 로그인→성공 시 백업, OnApplicationPause 백업, SignIn/Backup/Restore(슬롯 "saladfarm-save", UseMostRecentlySaved). 에디터=Available false 폴백.
  - `SaveSystem.ExportRaw/ImportRaw`(원자적 저장 경로 재사용), SettingsPanel 로그아웃 자리표시자→**Google 로그인/백업 + 클라우드에서 복원** 버튼(에디터 클릭=실기기 전용 안내). 에디터 E2E 검증 완료.
  - EDM4U Force Resolve 완료 — mainTemplate.gradle에 gpgs-plugin-support:2.1.0 주입됨(커스텀 gradle 템플릿 신규 활성화 — 다음 APK 빌드 시 유의).
- **남은 것(사용자)**: Play Console 개발자 등록($25)→앱 생성→Play Games Services 구성→OAuth(SHA-1)→**Saved Games 켜기**→테스터 등록→Application ID 전달. 가이드: `Desktop\GPGS_콘솔설정_가이드.md`. 이후 실제 AppId로 PerformSetup 재실행+APK 빌드+실기기 E2E.

**Why:** 로그인 목적이 세이브 백업/기기 이전뿐이고, 힐링게임 철학상 유저에게 보이는 마찰 최소화가 우선.
**How to apply:** 로그인 관련 작업 제안 시 UGS/Firebase 재검토를 다시 꺼내지 말 것(이미 결정됨). GPGS 범위 내에서 진행.
