---
name: project-session35-fixes
description: "세션35 수정 목록: 해칠링 아트 22종·8종 삭제·bv1/bv2 500px 버그·bv2 눈 하이라이트·진화 걷기 프레임 폴백 버그·시크릿 보내기 제거. 전부 실기기 확인 대기."
metadata: 
  node_type: memory
  type: project
  originSessionId: b7ab036b-e49e-4281-9b1d-4bd6439cda55
---

# 세션35 수정 (2026-07-09)

1. **해칠링 아트 22종 교체** — [[feature-hatchling-art-s35]]
2. **생물 8종 삭제(41→33)** + dex_30 목표 자동추종화 — [[feature-creature-species]]
3. **bv1·bv2 성장 스프라이트 500px 버그** → 128px 복원 — [[reference-sprite-size-uniform]]
4. **콩콩(bv2) 성장 눈 하이라이트** — 정지+걷기 2프레임에 2×2 흰 점(눈 bbox 좌 `(62,66)`, 우 `(84,66)`). 수면은 눈 감아 제외. 백업 `ArtBackups/s35_bv2_eye_highlight`.
5. **진화(stage2) 걷기 프레임 폴백 버그** — `FarmSpawner.RefreshWorldCreature`가 새 단계에 걷기 프레임이 없을 때 기존 `CreatureWalkAnim`을 그대로 둬서, 제자리 진화한 생물이 **이동 중엔 성장(5레벨) 프레임**을 재생하고 멈출 때만 진화 모습이 됐다. 프레임 없으면 `frames=null` 후 `Destroy`하도록 수정.
   - ⚠️ 씬 리로드 후엔 애초에 부착이 안 돼 증상이 안 보여서 재현이 까다롭다 — 제자리 진화 직후에만 나타남.
   - ✅ **세션38에서 bm2·rd2·rd3의 stage2 걷기 프레임을 신설**해 이 결손 자체가 해소됐다([[project_session38_cleanup]]). 이제 시크릿 4종 외 전 종이 stage2 걷기 프레임을 갖는다.
6. **기본 단계(stage0) 걷기 프레임 신설** — pv1(양상추)·pv3(무무)·rare6(산호)가 이동 중 다리가 안 움직였다. 원래 `Resources/CreaturesWalk/`엔 snow_spirit 2장뿐이라 기본 단계는 전부 정지형이었음.
   - 생성법(`scratchpad/basewalk.py`): 실루엣이 2개 이상 run으로 갈라지는 첫 행 = 다리 밴드 시작 → 밴드 내 연결 성분(발) 추출(높이 4px 미만은 꼬리 끝이라 제외) → **walk1=가장 왼쪽 발, walk2=가장 오른쪽 발만 2px 들어올림**(둘 다 들면 점프로 보임. 발 3개인 pv1은 가운데를 심는다).
   - `.meta`는 snow_spirit_walk1 메타 복제 + 새 GUID(중복 검사 완료). 변경 픽셀은 y102~113 밴드에만 국한.
   - **나머지 기본 단계 종은 여전히 정지형**. 요청 시 같은 스크립트로 추가 생성 가능.
7. **마카롱(bd1) 성장·진화 신규 아트 + 슬라임(slime) 진화 신규 아트** — `Downloads\새로운 디자인\`. 원본이 이미 128px 도트지만 완전한 2×2 블록이 아니라(체리 줄기 등 1px 디테일) **도트 축약 금지**, 128px 원해상도에서 처리(`scratchpad/hatch/macaron.py`, `slime.py`).
   - 배치: 세로만 이동해 bbox 하단을 115로 정렬(형제 진화 bd3=115). 슬라임은 원본 그대로(109).
   - 수면: sleep_v6 규칙을 픽셀 단위로 이식. 패딩은 **비대칭 (좌3,우3,위3,아래4)** — 좌우를 넓히면 입('w')의 양 끝이 지워진다. **저채도 밝은 광택(shine)** 도 지워야 인페인팅 소스로 흰 줄무늬가 번지지 않는다.
   - ‿ 곡선: 도트 스냅 대칭 포물선, **깊이 = max(2도트, 눈폭/4)** — 최소 2도트가 없으면 좁은 눈(슬라임)에서 납작한 막대가 된다.
   - 걷기: 다리가 없어 **마카롱=크림 필링 띠(y72~83)에서 2px 빼고/더해 바닥 고정 스쿼시·스트레치**, **슬라임=전체 ±2px 부유 바운스**.
   - 신규 파일: `CreaturesEvolved2/{bd1,slime}.png`, `CreaturesEvolved2Sleep/{bd1,slime}.png`, `CreaturesEvolved2/{bd1,slime}_walk1/2.png`, `CreaturesEvolvedWalk/bd1_walk1/2.png`(+ .meta 새 GUID). bd1·slime은 stage2 아트가 원래 없었다. 백업 `ArtBackups/s35_macaron_old`.
8. **2차 신규 아트 9장 일괄 적용** (`Downloads\새로운 디자인\`, 이 폴더는 사용자가 계속 갈아끼움 — 마카롱·슬라임 원본은 이미 사라짐):
   - 네온(pi1) 기본/성장/진화 · 병아리(chick) 성장/진화 · 별돌이(star) 진화 · 시크릿 3종(레온·먼지 몬스터·세계수 요정) 기본. **pi1·chick·star은 stage2 아트가 처음 생김.**
   - 변환: 고해상도 스무스 → 도트 파이프라인. 그리드는 기본 48, 성장·진화 56, **시크릿은 56~58**(기존 시크릿 아트가 크고 디테일이 얇아서. 세계수 요정은 56에선 사슴이 뭉개져 이끼만 남음).
   - baseline: 한 종의 세 단계가 튀지 않게 base 114 / stage1·2 115로 통일. ⚠️**별돌이 진화본만 사용자가 준 128px 도트 원본을 그대로 써서 bbox 하단 125**(중심이 9px 낮음).
   - **눈 검출 v2(`scratchpad/hatch/eyes2.py`)**: 기존 '전역 어두움 + 외곽선 flood' 방식은 **검은 로브(먼지 몬스터)·짙은 사슴은 몸 전체가 외곽선으로 번지고, 흰 여우는 눈이 외곽선에 닿아 한쪽만 감김**. → **지역 대비(가우시안 블러 배경보다 drop 이상 어두움)** + 후보 쌍 점수(크기·높이·y겹침·좌우 간격) + **낮은 문턱 영역 성장**(해골 눈구멍처럼 일부만 잡히는 경우). 외곽선은 flood 없이 1px 테두리만.
   - ‿ 곡선: **눈 폭 ≤16px이면 깊이 1도트**(깊게 파면 체크(✓)처럼 보임), 넓으면 2도트.
   - 이동: **다리 있는 종은 발(하단 연결 성분)을 번갈아 2px 들어올림** — 4족(네온 성장·진화)은 대각 교대 트롯, 2족(병아리 진화·레온)은 한 발씩. 다리 밴드 y는 종별 하드코딩(네온 103, 병아리 107, 레온 102 — 밴드를 위로 잡으면 앞다리 둘이 붙어 3개로 잡힘). **다리 없는 종은 부유 ±2px**, star는 **반짝임 조각 점멸** 추가.
   - **세계수 요정 = 정지형**: DB에 `stationary: 1`(bm2에 이어 두 번째). 걷기 프레임 없음. 사슴 눈이 도트 크기에서 사라져 **자는 스프라이트는 평상시 컷 복사**.
   - 백업 `ArtBackups/s35_newart_old`. 34파일 128×128·meta GUID 중복 없음 확인.
9. **시크릿 개명: 불꽃 꼬리 사자 → 레온** (`flame_lion`). DB `displayName`(escape `레온`) + **`Guidebook.cs`의 하드코딩 문구 "· 육류 → 불꽃 사자"**(유저 노출) + SynergyManager 주석. id는 그대로라 세이브·도감 기록 영향 없음. ~~기획서 PPT s12에 옛 이름 잔존~~ → 세션38 전수 검색 결과 **두 PPT 모두 이미 깨끗함**(세션36~37 갱신 때 함께 수정된 듯).
9. **시크릿 보내기 제거** — `CreatureDetailPopup.Refresh`에서 `isSecret`이면 ReleaseButton 숨김(보관 버튼은 이미 숨기고 있었음). 시크릿은 시너지 조건이 풀리면 SynergyManager가 알아서 떠나보낸다. 보내기 진입점은 이 버튼 하나뿐(부화 직후 보내기는 시크릿과 무관).

10. **발 높이 정렬** — 기준 수치는 [[reference-creature-baseline]]. 이번에 손댄 종만 정렬(pi1·chick·star·bd1·slime 3단계 + 레온·먼지 몬스터). idle·sleep·walk를 같은 dy로 이동, 백업 `ArtBackups/s35_feet_align`.
    - **별돌이 진화**만 아트가 세로 124px라 위로 못 올림 → 하단 123에 맞추되 **부유 폭을 4px→2px(123↔125)** 로 줄임(반짝임 점멸이 남아 움직임은 유지).
    - 방향은 손댈 것 없음: pi1(여우)만 옆모습이고 이미 우향, 나머지는 정면 뷰.
    - ~~**미정리 잔존**: 성장 폴더에 하단 128(잘림) 스프라이트 8장~~ → ✅ 세션38에 삭제종 7종의 잔존 아트 21장 전부 제거([[project_session38_cleanup]]).

11. **시크릿 농장 크기 1.5배** — `FarmSpawner.SpeciesScale(def)`(dietCategory==secret → ×1.5). 랜덤 0.9~1.2에 곱한다. 전 종 스프라이트가 128px 동일 해상도라 배율=화면 크기.
12. **세계수 요정 반짝임** — 정지형이라 `CreatureWalkAnim`이 안 돌던 문제. `alwaysPlay` 필드 신설(정지형이면 제자리 재생, frameDuration 0.35s). 프레임 3장은 본체를 안 건드리고 **투명 영역에만** 십자 반짝임(도트 2px)을 위상 다르게 찍은 것(`scratchpad/hatch/worldtree.py`).
13. **랩터(`pm2`) 삭제** — 33→**32종**. premium/meat 버킷엔 매머드(pm3)가 남아 비지 않음. dex_30 목표는 자동추종(=24). 백업 `ArtBackups/CreatureDatabase.asset.bak_s35_raptor`.
14. **먼지 몬스터 → 삿싱** 개명. id는 `dust_monster` 유지. DB displayName + **유저 노출 하드코딩 3곳**: `Guidebook.cs`(시너지 목록·설명), `FarmSpawner.cs` 등장 팝업, `FarmIncome.cs` 힌트 "먼지↓"→"삿싱↓".
15. **매머드(pm3) 3단계 신규 아트** — 원본 3장 모두 **좌향이라 변환 전에 좌우 반전**. 그리드 48/56/60, baseline 114/118/123. stage2는 처음 생김.
    - 자는 눈: **성장·진화는 완전 옆모습이라 눈이 1개**인데 eyes2의 쌍 점수가 이마 털 그늘 둘을 눈으로 오인 → `EYE_SEED` 좌표로 단일 눈 검출(`mammoth2.py`). 씨앗이 흰 하이라이트에 떨어지면 주변 5px 중 최암점으로 재선택.
    - 걷기: 다리가 발끝에서 붙어 연결 성분이 하나가 되므로, **밴드 시작 행의 x구간(run)** 으로 다리를 나눠 바깥 둘을 번갈아 든다(밴드 y = 102/108/109).
16. **좌향 아트 반전** — 병아리 성장·진화, 레온, 삿싱. (병아리 기본은 정면 뷰라 제외.) 백업 `ArtBackups/s35_flip`.

17. **QA 보고서 대응 3건** (외부 QA 5건 중 검증 결과 3건 실재·1건 부분·1건 오진)
    - (a) **관리자 모드 상용 배제** — `SettingsPanel.cs`의 토글 행 + `ToggleAdmin()`을 `#if UNITY_EDITOR || DEVELOPMENT_BUILD`로 감쌈. ⚠️`DebugManager.Disable()`은 **재화만** 되돌리고 치트로 산 아이템·생물·농장 확장은 영구히 남는다 → 이게 진짜 위험. `DebugManager` 클래스 자체는 상용에도 남긴다(구 세이브의 9999 복구용 `RestoreIfNeeded`).
    - (b) **출석 시간 조작** — `CanClaimToday`가 `lastAttendanceDate != Today` 문자열 비교라 기기 날짜를 아무 날로 바꿔도 수령 열림 → `DateTime.TryParseExact` 후 `TodayDate > lastDate` 선후 비교. **미래로 감는 건 서버 시간 없이 못 막음**(오프라인 단일 플레이어라 감수).
    - (c) **성장/진화 팝업 큐** — 같은 프레임 다중 성장 시 `ConfirmPopup` 하나를 재사용해 메시지가 덮였다. `Queue<string>`+`_growthPopupOpen`으로 직렬화, **큐가 빈 뒤에만 씬 리로드**. 팝업이 떠 있는 동안에도 AccrueXp가 계속 돌아 덮이던 게 더 잦은 경로였음.
    - **오진**: FarmWeather `OnDisable`의 MissingReferenceException — `_cam`은 `Camera`(UnityEngine.Object)라 `!= null`이 파괴된 객체에 false를 준다. 기존 가드가 이미 정답.
    - ~~**보류**: `hideFlags = HideAndDontSave` 에디터 유령 오브젝트~~ → ✅ 세션38에 `HideInHierarchy`로 교체(Sfx·Bgm·UITween·WeatherSoundManager 4곳), 플레이 종료 후 유령 0개 E2E 검증([[project_session38_cleanup]]).

에디터 컴파일/플레이 검증·실기기 확인은 다음 APK에서. Roslyn 문법 검사만 통과 상태.
