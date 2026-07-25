---
name: todo-guidebook-missing-pages
description: "✅완료(세션38): 가이드북에 수동입력·갤러리·보내기 선물 반영, 꾸미기 8종·다이아 획득원 갱신. 본문 높이 측정법 기록."
metadata:
  node_type: memory
  type: project
  originSessionId: 5925c7df-2e07-4655-b6e1-0c94d1f71752
---

# ✅ 가이드북 미기재 항목 — 세션38에 전부 반영 (2026-07-10)

`Assets/Scripts/Guidebook.cs`의 `Tips` 배열, 9 → **11페이지**.

- 신설 **'식사 기록하기'**(3페이지): 수동 입력 5종 + 갤러리(확인한 사진만 앱 내부 저장, 기기 사진첩 아님, 사진 지워도 끼니 기록은 남음). 원래 계획대로 [[feature_manual_diet_input_s37]]·[[feature_meal_gallery_s37]]을 한 페이지로 묶었다.
- 신설 **'생물 보내기'**(5페이지): 다이아 1 + 5렙↑ 성장아이템 5개 / 10렙↑ 10개, 시크릿은 보내기 불가. [[feature_release_gift]]
- 갱신 **'꾸미기 & 출석'**: 3종 → **8종 + 가격표**(꽃100·버섯150·나무200·호수300·벤치300·랜턴300·풍차500·우물800) + 밤 점등·풍차·벤치 연출. [[feature_farm_decorate]]
- 갱신 **'재화 모으기'**: 다이아 획득원에 '생물 보내기 +1' 추가.

## 본문 높이(614px) 다루는 법 — 다음에 페이지 손볼 때
`Text.preferredHeight`로 실측한다. 폰트 `Resources/Fonts/NanumPenScript-Regular`, fontSize 34, rect 폭 624. 한계는 **614px**(본문 상단에서 페이지 번호 상단까지). 11페이지 현재 최대 550px이라 여유 있음.

⚠️ **폰트를 잘못 집으면 측정이 전부 헛것이다.** 씬에서 아무 `Text`나 가져오면 malgun이 잡혀 810px 같은 가짜 오버플로가 나온다. 본문 폰트는 `UITheme.Body`(NanumPenScript).

관련: [[feature_guidebook]], [[project_session38_cleanup]]
