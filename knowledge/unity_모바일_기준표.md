# 유니티 모바일 기준표 (세션63 4부, 2026-07-18)

루시가 유니티 수치를 판정할 때 대는 자. **unity_build_report·unity_scene_lint·unity_models·
unity_sprites·unity_shot이 이 기준과 자동 대조**한다. 수치 변경은 config `unity.budgets`
(코드 수정 불필요), 이 문서는 근거와 예외의 유일 원본.

## 빌드 크기 (unity_build_report가 자동 대조)

- **150MB 이하** ← 자동 경고 기준 `apk_mb`. 근거: 구글 플레이 AAB 다운로드 한도 200MB —
  150을 넘기 시작하면 다음 업데이트 몇 번 만에 한도에 부딪힌다(샐러드팜 현재 82MiB=여유).
- 처방: 리포트의 '큰 에셋 상위'부터 — 텍스처면 `unity_tex_fix`(maxTextureSize 하향),
  전수 스캔은 `unity_audit`, 3D 모델은 블렌더 `tex_resize`/`decimate`.

## 씬 성능 (unity_scene_lint의 임계값 근거)

- 카메라 1대·AudioListener 1개(중복=경고). 실시간 그림자 **금지**(2D·모바일 — Farm.unity에서
  실검출·수리했던 그것). 조명 과다·Canvas 과다·문서 수 과다는 scene_lint 임계값 그대로.
- Canvas는 통합이 원칙 — Canvas 하나가 드로우콜 묶음 하나. 자주 갱신되는 UI(점수 등)만
  작은 Canvas로 분리(전체 리빌드 방지).

## 텍스처·스프라이트 (unity_sprites·unity_audit·unity_tex_fix)

- maxTextureSize: UI·배경 2048, 일반 스프라이트 1024. 원본 픽셀이 그보다 작으면 놔둠.
- 같은 폴더의 통일 무리는 크기·PPU 통일(swamp.png 941↔940 오프바이원 같은 것도 잡음).
- 밉맵: 2D/UI는 끔(용량+번짐만 남음).

## 3D 모델 반입 (unity_models + 블렌더 기준표와 짝)

- 폴리 예산은 [[blender_모바일_기준표]]와 같은 수치(소품 5,000tri·캐릭터 30,000tri).
- Read/Write 끔(메모리 2배), 스케일 팩터=1(아니면 블렌더 apply 누락 신호), 카메라/조명 임포트 끔.

## 씬 화면 (unity_shot이 자동 판정)

- **분홍(마젠타) 픽셀 0.5% 초과 = 재질/셰이더 실종 신호** — URP에서 머티리얼이 깨졌거나
  셰이더가 플랫폼에 없음. Extract Materials·셰이더 확인(세션58~61 데칼 사고들의 그 증상).
- 통째로 검은 화면 = 카메라가 아무것도 못 봄(레이어·위치) 또는 셰이더 미컴파일.
- ⚠️배치모드 렌더 함정(세션58 실측): 비동기 셰이더 컴파일=검정 플레이스홀더 →
  unity_shot이 allowAsyncCompilation=false+예열 3회로 회피. -nographics면 렌더 자체 불가.

## 예외

- 개발용(dev) 빌드 크기는 프로파일러 포함이라 기준 무관.
- 에디터 전용 씬(테스트 씬)은 빌드 씬에서 빼면 검사 대상에서 빠진다.

## 기준 변경

config `unity.budgets`: `apk_mb`(기본 150). 씬 린트 임계값은 unity_scene_lint 코드 내
(필요해지면 budgets로 승격).
