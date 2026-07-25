---
name: feature_four_systems_s20
description: 출석체크/재화치트/날씨환경음/날씨생산시너지 4개 시스템 구현·컴파일검증 완료 (세션20)
metadata: 
  node_type: memory
  type: project
  originSessionId: fbbd8d3a-fd38-4751-a174-5b126c834d6c
---

세션20(2026-07-02): `C:\this.txt` 요청으로 4개 핵심 시스템 추가. 전부 컴파일 검증 완료(에러 없음). 가이드=`Documents/DietCreature/NEW_SYSTEMS_GUIDE.md`.

**공용 기반 `Weather.cs`(신규)**: 기존 `FarmWeather`는 날씨(Mode)가 private이라 다른 시스템이 못 읽었음 → `WeatherState` enum + `WeatherSystem`(Current/Changed 이벤트, SSOT) + `WeatherSynergy`(날씨×식단 생산배율 규칙) 분리. FarmWeather는 Start에서 `WeatherSystem.Set`, OnDisable(농장이탈)에서 None 발행만 추가. [[feature_farm_weather]]

1. **출석 AttendanceManager.cs**: 7일 누적(하루 걸러도 이어짐, 연속 아님). 1·3·5=골드/2·4·6=다이아/7=프리미엄알. HatcheryManager가 자동 부착, 우측 '출석' 버튼+빨간배지, 매일 첫접속 자동팝업(온보딩 중엔 미룸). SaveData: attendanceDay/lastAttendanceDate.
2. **치트 DebugManager.cs**: Enable=실제재화 백업+9999, Disable=복구. 설정창 '관리자모드' 토글에 묶음(ON=즉시부화+9999). 백업을 SaveData(cheatActive/cheatBackupGold/Dia)에 저장→GameState 로드 시 RestoreIfNeeded로 자동복구(세이브 오염방지, 세션한정).
3. **환경음 WeatherSoundManager.cs**: WeatherSystem.Changed 구독, AudioSource 2개 크로스페이드(1.4s). Resources/Audio/amb_rain·amb_storm·amb_wind 파일 있으면 쓰고 없으면 절차생성 노이즈 폴백. Sfx/Bgm처럼 자동부팅 싱글턴(배선불필요). 볼륨=sfx설정×0.55. [[reference_audio_sfx]]
4. **생산시너지 FarmIncome.cs 리팩터**: 매프레임 WeatherSystem.Current 반영. 햇살→채식골드×2, 노을→육류×1.5, 천둥→일반×0.5+시크릿이 다이아생산(1개/시간). 수급버튼이 골드+다이아 동시수령(💎N 표시). 오프라인은 날씨보정 없이 기본율. SaveData: pendingDia/diaEarnedTotal. [[feature_synergy_ecosystem]]

확장: 새 날씨=WeatherState+ToState+각 분기. 생산규칙=WeatherSynergy만. 출석보상=AttendanceManager.Rewards 배열만.

세션20 후속 조정(사용자 요청, 전부 MCP 플레이 검증 완료):
- 출석 버튼: 부화화면 우측→**좌상단 재화 아래**(anchor0,1 pos24,-205). 그리고 **일차 셀 직접 클릭으로도 수령**(OnCellClick, 오늘 받을 일차만).
- 농장 BGM 정지: Bgm.ApplyForScene가 "Farm"에서 Stop()→환경음/효과음 잘 들림.
- 날씨별 바람 차등: WeatherState에 **Calm 추가**(농장 기본=특수날씨없음). Calm=amb_wind_soft(약함 rel0.45)/Sunny=amb_wind/Golden=amb_wind_strong(강함 rel1.0). FarmWeather는 Decide==None일 때 Set(Calm)+오버레이 안 만들고 컴포넌트는 살려둠(OnDisable에서만 None). None=농장밖 무음.
- 천둥소리: 절차생성 sfx_thunder 클랩을 WeatherSoundManager.PlayThunder()(원샷 3번째 소스)로, FarmWeather 섬광 시 호출(기존 Sfx.Play("thunder") 대체).
- MCP검증 함정: enum 재정렬(Calm 삽입) 후 recompile 완료 전 플레이 진입하면 스테일. isCompiling=False 확인 후 진입할 것. HideAndDontSave 싱글턴은 반복 플레이 시 GameObject.Find가 옛 잔여물 잡을 수 있음→_inst(static)로 접근. [[reference_mcp_stale_compile]]
