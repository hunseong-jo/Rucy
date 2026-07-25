---
name: reference-apk-dev-mode-toggle
description: APK 빌드 시 개발자(관리자) 모드 포함 여부를 다이얼로그로 고른다. 파일명도 갈린다.
metadata: 
  node_type: memory
  type: reference
  originSessionId: 5925c7df-2e07-4655-b6e1-0c94d1f71752
---

세션37부터 Unity 메뉴 **Build ▸ Android APK to Desktop**을 누르면 다이얼로그가 뜬다:

- **포함** → `BuildOptions.Development` (즉 `DEVELOPMENT_BUILD` 정의) → 설정 창에 '관리자 모드' 토글이 나타남(재화 9999 치트·식단 1번 선택 즉시 부화·시간 조작). 출력 파일 **`SaladFarm_dev.apk`**
- **미포함** → 기존과 동일한 배포용 → **`SaladFarm.apk`**
- 취소 → 빌드 안 함

파일명을 나눈 이유: 테스터에게 dev 빌드를 잘못 건네는 사고 방지.

**Build ▸ Android AAB (Release)** 는 항상 개발자 모드 제외.

관리자 모드 토글 자체는 원래부터 `SettingsPanel.cs`의 `#if UNITY_EDITOR || DEVELOPMENT_BUILD`로 감싸져 있었다. 새로 만든 게 아니라 **빌드 시점에 켤 수 있게 스위치를 노출**한 것.

CLI(배치 모드)는 물을 수 없으므로:
- `-executeMethod DietCreature.EditorTools.ApkBuilder.BuildApk` → 개발자 모드 **제외**(안전한 기본값)
- `-executeMethod DietCreature.EditorTools.ApkBuilder.BuildApkDev` → **포함**

여전히 유효한 주의사항: ApkBuilder가 `buildAppBundle`을 빌드 후 원래대로 복원한다([[project_release_prep]]의 AAB 플래그 함정 대응).
