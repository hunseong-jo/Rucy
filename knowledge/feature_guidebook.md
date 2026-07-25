---
name: feature_guidebook
description: 알 키우기 화면 우상단 설정버튼 아래 책 버튼 → 공략/팁 세로스크롤 팝업. Guidebook.cs.
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e3f6f28-2ea9-4139-b96c-c267a2acfd5f
---

가이드북(공략·팁) 기능(세션22, 2026-07-02). 알 키우기(Hatchery) 화면 우상단 설정 버튼 바로 아래에 책 아이콘 버튼 → 누르면 세로 스크롤 팝업으로 게임 팁 안내.

**Guidebook.cs** (신규): HatcheryManager.Start에서 `AddComponent<Guidebook>()`(AttendanceManager 옆). 자기완결 — 버튼+팝업 런타임 생성.
- 책 버튼: `TopStatusBar`의 설정 버튼과 동일 스타일(UITheme.RoundedBox/Stone + AddShadow, 96px, 우상단 앵커). 위치 `(-28, -(36+96+16))`로 설정 버튼 아래. 아이콘=`Resources/Icons/book.png`(PIL로 그린 열린 책, 기어와 동일 갈색 솔리드/PPU100 meta 복제).
- 팝업: dim+Box(880x1180)+Popup 애니, 제목 '가이드북'. **페이지 방식**(팁 1개=1페이지): 중앙 PageCard에 제목+본문, 양옆 ‹/› 원형버튼(MakeArrow, UITheme.RoundedBox/Stone)으로 넘김, 하단 'n / 7' 페이지번호, 끝에서 화살표 클램프+dim. Refresh()가 Tips[_page] 반영. 닫기 버튼+바깥클릭 닫기.
- 팁 내용은 실제 규칙 기반: 부화/식단4종/[[feature_farm_weather]] 날씨배율(WeatherSynergy: 채식→햇살×2·육류→노을×1.5·인스턴트5→천둥×0.5+시크릿다이아)/[[feature_synergy_ecosystem]] 특수생물(3·5·8마리)/[[feature_creature_sleep]] 밤낮취침/재화/꾸미기·출석.

검증: 강제 동기 재컴파일 통과(error CS 0), book.png 정상 임포트. 실기기 눈검증 미완(MCP 미연결). 팁 문구·항목은 배열 Tips 수정으로 쉽게 추가/변경.

**세션27 갱신(2026-07-04)**: 도전과제·리포트 카드가 그새 추가돼 있었고(8장), 이번에 **'성장과 진화' 카드 신설**(3페이지: 경험치 바/아이템+500/필요치 1000+200/자동 경험치 분당5·날씨2배/10레벨 진화, [[feature-xp-growth-system]]) → **총 9페이지**. 날씨 카드에 경험치 한 줄 추가+압축, 시크릿 카드도 압축(둘 다 본문 rect 600px 초과 상태였음). ⚠️본문 Text는 verticalOverflow=Overflow라 rect(600px)를 넘어도 카드 하단 패딩(~34px)까지는 그려짐 — preferredHeight 614까지는 시각적으로 안전, 그 이상이면 문구 압축 필요. 플레이모드 9페이지 전수 측정+스크린샷 검증 완료.
