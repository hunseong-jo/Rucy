---
name: feature-dessert-snow-synergy
description: 디저트 시너지 완성 — 눈꽃 정령(snow_spirit) 시크릿 + 눈/함박눈 날씨 + 설원 배경 (2026-07-03 세션24)
metadata: 
  node_type: memory
  type: project
  originSessionId: 5d7cacef-5e6f-4476-8f1c-18808b5b88c1
---

디저트 식단이 유일하게 시크릿/날씨가 없던 것을 다른 식단과 동일 매커니즘으로 완성 (2026-07-03).

- **시크릿**: snow_spirit(눈꽃 정령), 디저트 3+→1 / 5+→2 / 8+→3마리(기존 SpawnTiers 공용). SynergyManager.Rules에 한 줄 추가 + CreatureDatabase.asset 등록(guid 7234183b…). 아트는 PIL 절차생성(64px→x2 nearest, 귀마개+눈결정 더듬이), 수면 스프라이트도 Resources/CreaturesSleep에 생성.
- **날씨**: WeatherState.Snow/SnowHeavy 추가. 디저트 3+→눈(살살, 60개), 5+→함박눈(130개+수평 드리프트+강한 틴트). 우선순위 인스턴트>디저트>육류>채식. 재화: 눈 디저트×1.5, 함박눈 ×2 (WeatherSynergy). 환경음 amb_snow(포근 미풍)/amb_blizzard(눈보라) 절차생성. 가이드북 카드 갱신.
- **배경**: snowfield(설원) 941x1672 PIL 생성, BackgroundCatalog 50골드, 울타리색 잿빛(0.62,0.68,0.78). 상점·픽커 자동 노출.
- **부수 버그픽스**: FarmSpawner._font가 null이면 시너지 팝업 텍스트가 안 보이던 문제 → UITheme.Body 폴백 추가([[reference_creature_art]] 스타일, 다른 시크릿 팝업에도 해당되던 잠재 버그).
- **검증**: 세이브 백업→디저트 5마리/3마리 시나리오 플레이모드 E2E(스폰 수·날씨·팝업·수급 +28/분·+6/분 배율 확인)→세이브 복원. 플레이 진입 시 Intro로 시작하므로 런타임에 SceneManager.LoadScene("Farm") 필요.
