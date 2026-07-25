---
name: reference-audio-sfx
description: "효과음 시스템 - 절차생성 WAV(저작권프리), Sfx 재생 매니저, 버튼/이벤트 배선"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0b880453-c193-4ef9-93dc-415751995e0c
---

## 효과음(SFX) 시스템 (2026-06-28 세션8) — [[project-diet-creature-game]]

사용자 요청 "저작권 없는 배경음/효과음". 음원 다운로드 불가 → **절차 합성**(코드로 파형 계산, 아트 PNG 방식과 동일). 우선 **효과음만** 구현(BGM은 추후).

- **클립**: `Assets/Resources/Audio/{tap,buy,hatch,place,pickup,pop}.wav` 6종, 44100Hz 모노 16bit PCM. 사인/노이즈+엔벨로프로 합성, 양끝 페이드로 클릭음 제거. ⚠️ 생성 스크립트는 일회성(script-execute, 미저장) — 재생성/튜닝 시 새로 합성. importer: forceToMono, DecompressOnLoad, PCM.
- **재생 매니저** `Assets/Scripts/Sfx.cs`(static): `Sfx.Play(id, vol)` — Resources/Audio 캐시 로드, `~Sfx`(DontDestroyOnLoad) AudioSource로 PlayOneShot. 볼륨 = `Settings.sfx`×vol. **`Application.isPlaying` 가드**(에디트 모드 DontDestroyOnLoad 예외 방지). `Sfx.WireButtons(root)`=트리의 모든 Button에 "tap" 1회 부착(SfxClickMark로 멱등).
- **배선**:
  - 버튼 탭음: **UIPolish.PolishTree 끝에서 Sfx.WireButtons(root)** 호출 → 전 씬·팝업 버튼 자동(멱등). 동적 재생성되는 상점 카드는 ShopManager.Populate 끝에서도 WireButtons.
  - 구매 성공: ShopManager DoBuyEgg/DoBuyDecor/DoBuyFarmExpansion/DoBuyBackground → "buy".
  - 부화: HatcheryManager.OnHatch → "hatch". 꾸미기 배치/회수: FarmDecorate → "place"/"pickup". 생물 터치: CreatureInteract.Interact → "pop".
- **마스터 볼륨 변경**: `GameState.ApplyAudio`가 이전엔 `AudioListener.volume=bgm`(BGM 없어 sfx까지 음소거시키는 혼란)이었음 → **`=1f`**로 변경. 이제 sfx는 sfx슬라이더만 따름.
- ⚠️ 제약: 합성 SFX라 실제 음색 검증은 사용자 청취 필요(개발 환경에서 소리 못 들음). 클립 로드/길이/컴파일만 검증함.

## ✅ BGM 배경음악 구현 (2026-06-28 세션9)
- **트랙 2종**(둘 다 절차합성 PowerShell+Add-Type C#, 생성스크립트 scratchpad GenBgm.ps1/GenBgmMain.ps1 일회성·미저장. 44100Hz 모노 16bit, importer meta 직접작성: loadInBackground1/preloadAudioData1/forceToMono1/normalize0/3D0):
  - `Resources/Audio/bgm_intro.wav` — **인트로 화면 전용**. 잔잔, 72BPM 8마디 26.67초, 진행 C-G-Am-F-C-G-F-G. 브리딩 패드(마디마다 half-sine 스웰로 양끝 0→심리스 루프)+뮤직박스 아르페지오(exp decay 펜타토닉, 기음+2배음). (원래 bgm.wav였는데 세션9 후반 인트로 전용으로 리네임)
  - `Resources/Audio/bgm_main.wav` — **GAME START 이후 모든 화면**. 살짝 빠름 90BPM 8마디 21.33초, 진행 C-Am-F-G-C-Em-F-G, 패드+아르페지오에 **베이스 펄스(매 비트)** 추가로 추진력. 피크 0.72 정규화.
- **매니저** `Assets/Scripts/Bgm.cs`(static, Sfx와 병렬): `~Bgm`(DontDestroyOnLoad) AudioSource loop=true. `[RuntimeInitializeOnLoadMethod(AfterSceneLoad)] Bootstrap`에서 `SceneManager.sceneLoaded` 구독 + `ApplyForScene`. **씬별 트랙 전환**: `sceneName=="Intro"?bgm_intro:bgm_main`. `Play(id)`는 같은 클립 재생중이면 재시작 안 함 → **GAME START 이후 Hatchery/Farm/Shop 등 오가도 bgm_main 끊김없이 루프**, Intro 복귀(로그아웃) 시 bgm_intro로 전환. `Stop`, `ApplyVolume`(=Settings.bgm). `Application.isPlaying` 가드.
- **볼륨연결**: `GameState.ApplyAudio`에 `Bgm.ApplyVolume()` 추가 → 설정 bgm 슬라이더(SettingsPanel.ChangeBgm가 ApplyAudio 호출)가 BGM 볼륨 실시간 반영. **bgm 슬라이더 더 이상 무음 아님**.
- ⚠️ 컴파일/청취 검증 못함(이 세션 Unity MCP 미연결) — 정적검토만. 사용자가 에디터 Play로 확인 필요. WAV 헤더는 둘 다 검증함(유효).
