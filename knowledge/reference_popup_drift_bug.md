---
name: reference-popup-drift-bug
description: "팝업이 열 때마다 아래로 밀려 화면 밖으로 사라지는 버그 — Popup 등장 애니가 현재 위치를 안착점으로 읽던 문제, 세션29 수정."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3b13e08c-9eb4-4830-b0e3-b77e059978a2
---

# 팝업 '아래에서 나와 안 보임' 드리프트 버그 (2026-07-05 세션29 수정)

**증상**: "보내기" 확인 팝업(인벤 CreatureDetailPopup, 부화 HatcheryManager 둘 다)이 열면 화면 아래에서 나와 보이지 않음. 씬/코드상 박스는 중앙(anchor 0.5,0.5, anchoredPos 0)인데도.

**원인**: `UITween.PopupOpenRoutine`(UITween.cs:73)이 **매 등장마다 `target = box.anchoredPosition`(현재 위치)을 안착점으로 읽음**. 등장 코루틴은 영속 TweenRunner(DontDestroyOnLoad)에서 돌아 팝업이 비활성돼도 계속 실행됨. 열기/닫기가 겹치면(확인팝업은 SetActive true/false로 자주 여닫힘, 게다가 씬에 active=1로 시작→Start에서 SetActive(false)) 애니 **중간 위치**를 target으로 오인 → 매번 riseFrom(80px)씩 아래로 누적 드리프트 → 화면 밖.

**수정**(Popup.cs): 박스의 원래 안착 위치를 **최초 1회 `_boxRest`에 저장**(Resolve에서 _box 처음 찾을 때, 애니 전), OnEnable에서 **열 때마다 `_box.anchoredPosition=_boxRest`로 복구 후** PopupOpenRoutine 호출. 모든 Popup 공용이라 전 팝업 일괄 해결. 컴파일 OK(실기기 확인은 다음 빌드).

**2차 증상(같은 세션)**: 위치는 고쳐졌는데 확인 팝업이 **다른 팝업 뒤에 숨음**(상세카드/부화팝업과 둘 다 canvas sortingOrder=100이라 tie-break로 안정적으로 위에 안 옴). **수정**: Popup에 `public int sortingOrder=100`(EnsureAboveNavBar에서 `>0?order:100`로 역직렬화 0 방어) 추가 → 확인 팝업은 210으로. ConfirmPopup.EnsureBuilt에서 pop.sortingOrder=210, 부화 씬 ConfirmPopup은 HatcheryManager가 Find 직후 210 설정. **추가(같은 세션)**: HatcheryManager의 자체 제작 `_farmFullPopup`("농장 꽉참→상점 이동?", 부화 후 '농장 배치' 시)도 부화 팝업 뒤에 깔려서 210으로 올림. 인벤 place-full은 _confirm.ShowInfo(=210)라 이미 정상. 결론: **다른 팝업 위에 뜨는 모든 서브/확인 팝업은 sortingOrder 210**. (검증: Popup.sortingOrder 필드 컴파일 OK).

**교훈**: ①영속 러너 코루틴 + '현재값을 기준점으로 읽는' 애니는 중단/재진입 시 값이 누적 오염됨(기준점은 별도 저장값에서). ②팝업 위 팝업은 같은 order면 계층 tie-break라 불안정 — 서브/확인 팝업은 명시적으로 더 높은 sortingOrder를.
관련: [[project-ui-redesign]] [[feature-creature-evolution]]