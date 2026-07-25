---
name: project-optimization-pass
description: 전체 코드 최적화·정리 패스 완료 — 텍스처 캐싱/ConfirmPopup 공용화/입력 API 통일 (2026-07-03 세션24 후반)
metadata: 
  node_type: memory
  type: project
  originSessionId: 5d7cacef-5e6f-4476-8f1c-18808b5b88c1
---

전 스크립트(43개) 최적화 점검 후 일괄 수정 (2026-07-03). 전반 상태는 원래 양호(Find류 전부 일회성, Update 무할당, 카탈로그 캐싱).

수정한 것:
- **텍스처 누수**: 무지개(FarmWeather)·해달/별 원반(DayNightCycle)을 static 캐시로 — 런타임 생성 Texture2D는 씬 언로드로 해제 안 되는 게 원인. 새 절차 스프라이트 만들 땐 CreatureSleep.ZzzSprite 패턴 따를 것.
- **ConfirmPopup.cs 신설**: 예/아니오·확인1버튼 공용 팝업. CreatureDetailPopup·FarmBackground의 중복 구현 제거. '예'는 자동 닫힘 후 onYes 실행. 새 확인 팝업 필요하면 ConfirmPopup.Get(host, font) 사용.
- **입력 통일**: FarmDecorate를 구형 Input→신형 InputSystem(Pointer.current)으로. 프로젝트는 신/구 둘 다 켜져 있지만 이제 코드는 신형만 사용.
- 죽은 코드 SynergyRule.threshold 삭제(실 로직은 SpawnTiers), 이모트 스프라이트 캐시, 관리자 시간라벨 변경시에만 갱신, 생물들 CreatureRoot 부모로 정리.
- 검증: 플레이모드에서 보관 확인/배경 확인 팝업 동작, 씬 재입장 시 스프라이트 인스턴스ID 동일(캐시 적중), 꾸미기 편집 진입 확인.
