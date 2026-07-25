---
name: feature-farm-weather
description: 농장 날씨 시스템 - 배치 생물 식단 조합에 따라 햇살·무지개/황금노을/비/천둥 연출. FarmWeather.cs.
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f782284-0ba3-4cfd-a6aa-9b972ae4055b
---

## 농장 날씨/분위기 시스템 (2026-07-01 세션15)

[[feature-synergy-ecosystem]]와 같은 "농장 식단 조합" 트리거를 분위기 연출로 확장. 사용자 요청.

### 규칙 (농장 배치 생물 dietCategory 기준, 특수생물 제외)
- **채식 3+**: 따스한 노란빛 필터 + 잎새 햇살(God Ray 5개, 폭 W*0.12·최대α0.24·`_rayPhase*1.7` 속도로 0에 닿게 또렷이 점멸) + 18초 주기 무지개(세션15-3: 우상단 1/4호가 직선으로 잘려 어색→**상단 중앙 반원 아치**로 재설계, GenRainbowSprite 256x150 하단중앙 중심·다리끝 legFade로 투명).
- **육류 3+**: (세션15-3 변경) 기존 '하단 노을 글로우 박스'가 경계가 뚜렷해 부자연스러움→**제거**. 따뜻한 모래빛 틴트(DustTint) + **수평 모래바람**(BuildDust/UpdateDust: 모래줄기 90개가 좌→우 650~1300px/s로 흐르며 위아래 sway, 우측 이탈 시 좌측 재투입).
- **인스턴트 3+**: 우중충한 회색 틴트 + 빗방울(64개 낙하).
- **인스턴트 5+**: 거센 비(110개·빠르고 길고 기욺) + 주기적 번개 섬광(풀스크린 흰 플래시) + 카메라 흔들림.
- 여러 조건 동시 충족 시 **우선순위 1개만** 적용 — 개수 무관 **인스턴트>육류>채식** (세션15-2, 사용자 요청으로 '최다 속성'→'고정 우선순위'로 변경). `Decide()`는 inst≥5 천둥/inst≥3 비/meat≥3 노을/veg≥3 햇살 순.

### 구현 — `FarmWeather.cs` (신규 MonoBehaviour)
- `FarmSpawner.Start`에서 `gameObject.AddComponent<FarmWeather>()`로 부착(FarmTouch 옆).
- 연출은 **Canvas 최하위 형제(`SetAsFirstSibling`) 풀스크린 오버레이** = 월드 스프라이트 위·UI 버튼/카드/네비 아래. 모든 이미지 `raycastTarget=false`(월드 탭·버튼 입력 안 막음).
- 전부 **절차 생성**(프리팹/텍스처 의존 없음, 프로젝트 스타일): 틴트=빈 sprite Image 색칠, 햇살=회전한 얇은 Image, 비=Image 풀 낙하(Update 재활용), 무지개=`GenRainbowSprite()` Texture2D 호 7색, 번개=풀스크린 흰 Image 알파 펄스.
- 카메라 흔들림=`Camera.main.localPosition`을 흔듦(배경 오버스캔 1.02 안 넘게 진폭 0.1·세로 절반). `OnDisable`에서 원위치 복구.
- 캔버스 픽셀크기 의존 요소(햇살/무지개/비)는 `_canvasRT.rect.height>1` 되는 첫 Update에 lazy 생성(`_sized`).
- 식단 카운트는 `SynergyManager.CountFarmDiets()` 공용 사용. 날씨 판정은 `Decide()`.
- 번개음 `Sfx.Play("thunder")` — `Resources/Audio/thunder.*` 넣으면 자동 재생, 없으면 무음(Play가 null-safe).

### 후속
- 정식 천둥 효과음(`Resources/Audio/thunder`) 추가하면 번개 연출 완성.
- 현재 씬 진입 시 1회 판정(배치 변경은 농장 리로드로 반영) — 시너지와 동일 모델.
