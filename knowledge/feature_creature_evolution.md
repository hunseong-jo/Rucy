---
name: feature-creature-evolution
description: "생명체 레벨·성장·진화 시스템 — 3단계(기본→성장 lv5→진화 lv10), 성장 아이템 4종, 골드 성장1.5·진화2배, 도감 3단계 진행도."
metadata: 
  node_type: memory
  type: project
  originSessionId: a5b0be76-a8df-44d1-96a8-31ce5b4f3d9b
---

# ★세션29 3단계 개편: 기본 → 성장(lv5) → 진화(lv10)

사용자 요청으로 2단계(기본→진화 lv10)에서 **3단계**로 확장. **기존 진화 스프라이트(CreaturesEvolved 61종)는 이제 '성장(lv5)' 모습으로 재활용**, 진화(lv10)는 **더 화려한 신규 도트**를 사용자가 종별로 직접 보내주면 적용(진행 중).

- **stage**: 0기본 / 1성장(GrowLevel=5) / 2진화(EvolveLevel=10). 성장 후에도 레벨업 계속(5→10), 진화 시 xp=0·종료.
- **골드 배수**: GrowthCatalog.StageGoldMult — 성장 ×1.5, 진화 ×2. FarmIncome.TierGold가 float로 반영.
- **스프라이트 폴더**: 성장=`Resources/CreaturesEvolved/`(기존), 진화=**`Resources/CreaturesEvolved2/`(신규)**, 수면은 `CreaturesEvolvedSleep/`·`CreaturesEvolved2Sleep/`. CreatureCatalog.GetSprite(id,stage)/GetSleepSprite 폴백: 진화→성장→기본.
- **진화 PNG 임포트 규격**(기존 evolved .meta 기준): 128×128, textureType=Sprite, spriteMode=Single, filterMode=0(Point/도트필수), spritePixelsToUnits=110, pivot 0.5/0.5, alphaIsTransparency=1, 무압축. **파일명 = 그 종의 기본 스프라이트명과 동일**(GetSprite(id).name). 새 폴더는 첫 이미지 때 생성.
- **데이터**: SpeciesRecord에 growCount 추가(+MaxStage 프로퍼티=evolveCount>0?2:growCount>0?1:0). AddXp/Feed 시그니처 `out bool grew, out bool evolved`(호출부 CreatureDetailPopup·FarmIncome 갱신).
- **도감**: 카드=그 종 최고단계 모습(SpeciesMaxStage), 뱃지 진화=금★·성장=연두✦. **카드 클릭 팝업=3칸 진행도(기본▶성장▶진화)**, 달성=컬러·미달성=검은 실루엣(CollectionManager.ShowInfo 재작성, _stageIcons[3]).
- **마이그레이션**: GameState.MigrateStages — 구 진화(stage1&&level≥10)→stage2 승격(골드2배·★ 유지), record.growCount=max(,evolveCount). Load/Reload에 연결.
- **좌우 반전 이동은 이미 구현돼 있었음**(CreatureWander.cs:118 `_sr.flipX=dx<0`). 애니메이션(표정·움직임) 생물은 나중에 정지 이미지부터 적용 후 프레임 추가 예정.
- **E2E**: 컴파일 OK, AddXp 드라이런(lv10→stage2, grew&evolved), 도감 팝업 캡처 검증(star=3칸 컬러, slime=진화 실루엣). RT카메라 캡처법은 [[reference-screen-definition-ppt]] 참고.

## 진화 아트 적용 진행(세션29, 사용자 제공 도트)
사용자가 종별 진화 도트를 하나씩 보내면 → 배경제거 후 임포트(Sprite/Point/PPU110/무압축/알파) → CreaturesEvolved2/<기본스프라이트명>.png. **적용됨**: rd3 초코, bd3 컵케익, premium10 오로라, rd2 솜사탕, premium5 무지개, **rd1 만쥬(도넛→만쥬 개명), bv2 콩콩, pv3 무무**(각각 진화+걷기+자는 전부).

### 세션30 발/이동 방향 교정 + 자는 눈 v3
- **좌향 아트 미러링(최종 6종)**: bv2 콩콩·pv3 무무·rd1 만쥬·rare2 애플·bv3 풀잎·**frog 프록(재보고로 추가 — 덩굴꼬리 오른쪽=좌향인데 발이 웅크려 있어 정면 오판)**. **premium5 무지개는 원래 우향이었는데 오판으로 미러했다 재보고 받고 원복**(정면 유지: bd3·premium10·rd2·rd3). CreatureWander(flipX=dx<0)는 아트가 **오른쪽을 본다고 가정**. **판정은 눈대중 말고 수치로**: 발 클러스터의 발목(위3행) 중심 vs 발끝(아래2행) 중심 오프셋(+=우향), 꼬리/덩굴 위치(꼬리 오른쪽=좌향)도 참고. walk-vs-base 방향 일치는 IoU 비교(±3px 시프트 허용)로 전수 감사 가능. fix_facing_sleep.py MIRROR 리스트는 토글(멱등 아님)+main 가드 필수.
- 자는 눈은 v3로 전면 재생성([[todo-evolved-sleep-face-fix]] 참고: 승인된 기본 스타일 템플릿+가로 미러 채움).

### 세션30 추가: 산호·눈꽃정령
- **rare6 산호**(육식 레어) = meat01.png 여우. 좌향(꼬리 오른쪽)이라 미러 후 적용, 진화+수면v3+걷기2프레임.
- **snow_spirit 눈꽃정령**(시크릿) = 시크릿 디저트.png 흰토끼. **시크릿은 진화 없음 → 기본 모습 자체를 교체**(Art/Creatures/snow_spirit.png를 PNG만 덮어써 guid 보존, CreaturesSleep/도 v3 재생성). 이동은 부유형이라 **파티클 반짝임 2프레임**: 신설 `Resources/CreaturesWalk/<기본명>_walk1,2` + **GetWalkFrames 확장**(stage≥2=CreaturesEvolved2, 미만=CreaturesWalk, 캐시키=폴더+이름). 파티클=본체 제외 소성분(≤80px)을 위치해시로 2그룹, 프레임별 밝게(×1.25)/흐리게(×0.75·α0.55) 교차.
- ⚠️ **파이프라인 모듈 import 함정**: fix_facing_sleep.py 본문이 모듈 레벨이라 run_coral이 import하며 sys.argv 'apply'를 물려받아 **6종이 이중 미러(좌향 원복)**된 사고 → main 가드 추가+재적용으로 복구. 스크래치패드 스크립트는 반드시 `if __name__=='__main__'` 가드.
- 눈꽃정령 눈은 진보라(~110)라 눈검출 dark_max 완화 파라미터 추가(make_sleep_v3(dark_max=115)).

### 세션31 추가 5종 (2026-07-08)
- **pd3 크림**=그리핀(우향) — 이동은 **날개짓**: 날개 열(x<58,y<74)을 어깨 힌지로 열별 세로시프트(±(58-x)//12~16). / **bv1 새싹**=튤립 — 이동은 **풀잎 일렁임**: y≥64 행을 아래로 갈수록 ±3px 가로 스웨이. / **pv1 양상추**=거북(주변 잎·물방울 장식 유지) / **rare5 라임**=공룡 — 둘 다 걷기(발 교차 2px 들기).
- **bm2 늑대→스핑크스 개명** + 진화 적용. **정지형 생물 신설**: CreatureSpeciesDef.stationary(bool) 필드 추가, asset에 `stationary: 1`, FarmSpawner가 def.stationary면 CreatureWander.enabled=false(생성 자리 고정). DecorFx 벤치 섭외는 `!w.enabled` 검사로 자동 제외. 걷기 프레임 없음.
- **고개 숙인 수면(스핑크스)**: 눈만 감기지 않고 머리 블록(40,4,106,56)을 7px 아래로 시프트(비운 자리 투명, 본체 위 겹침) 후 눈 감김 — 자연스러움 확인됨. 다른 종에도 쓸 수 있는 패턴.
- 수면 눈 처리 v4: ①단색 채움(샘플점 주의 — 그림자/등껍질 밟으면 검은 사각형) ②**선택적 치환**(눈픽셀만: max<130 or 하이라이트 or 살색과 dr>150 저채도)이 볼터치·등껍질 경계 보존에 최선. **눈 좌표는 눈대중 말고 어두운 클러스터 검출로**(rare5에서 눈대중 오판으로 1회 재작업, pd3 그리핀도 오판—실제 눈은 (83,21)~(93,29)였는데 크레스트를 눈으로 착각). ⚠️**살색 샘플점이 투명이면 눈이 '투명 구멍'이 됨** — 회색 확인시트에선 안 보이니 **게임 배경색 시트로 검사**하고 `assert skin.a>200 and min(rgb)>180`. ⚠️그리핀처럼 외곽선이 눈과 연결된 아트는 클러스터 검출 실패 → 행별 텍스트 덤프(#/+/-/공백)로 실측이 확실.
- **사후 보고 3건(같은 세션)**: pv1 거북 좌향(꼬리 오른쪽)인데 미러 안 함→4장 전부 미러 재배포 / pd3 수면 얼굴 구멍(위 함정) / **스핑크스 이동 버그 — '무조건 배회 되켜기' 패턴이 2곳**: ①CreatureSleep.Apply(`enabled=!sleep`) → stationary 제외로 수정 ②**CreatureInteract.React가 터치 반응 후 `enabled=true`** → 반응 전 상태 기억·복원(wanderWas)으로 수정. E2E: 임시 bm2 스폰→Interact()→8초 후 위치 불변+enabled=False, 일반종은 복귀 True 확인, e2e 임시생물 세이브 정리 완료. **교훈: 컴포넌트를 끄는 기능을 넣으면 그걸 켜는 모든 코드(grep `enabled = true`)를 전수 점검할 것.**
- 진화 도트 누적 **17종**(rd3·bd3·premium10·rd2·premium5·rd1·bv2·pv3·rare2·frog·bv3·rare6 + pd3·bv1·pv1·rare5·bm2).

### 세션32 추가 4종 + 개명
- **pd3 크림→그리핀 개명**(전 세션에 그리핀 도트 적용했던 종). **bi2 콜라**=보라 유령(반짝임) / **premium2 루비**=불꽃몬(**불꽃 일렁임**: 따뜻한 색(R>195,G>90,B<130) 픽셀 마스크 → f1=꼭대기 위 1px 핥아오름+밝게, f2=꼭대기 1줄 깎임+어둡게) / **premium4 에메랄드**=바위몬(반짝임) / **rare10 푸른별**=날개천사(반짝임+파티클 부족 시 본체 주위 합성). 진화 도트 누적 **21종**.
- **눈 쌍 자동검출 안정화**: 어두운 클러스터(8~260px, 폭·높이≤26) 중 수평분리 2~40+유사y(≤5)+크기비≤2.6 쌍 → 4종 전부 자동 성공. 수면은 선택치환+눈클러스터 최암색 ‿. gen4.py(스크래치패드) 파이프라인 재사용 가능.
- ⚠️**또 방향 검사 생략 사고**: 4종 모두 꼬리·망토가 오른쪽(=좌향)인데 미러 없이 적용 → 사용자 재보고 후 16장 일괄 미러. **파이프라인 첫 단계에서 무조건 방향 판정**(꼬리/망토/불꽃트레일 오른쪽=좌향=미러) — 정면 얼굴이어도 부속 방향으로 판단할 것.

### 세션30 추가 3종(Downloads\새로운 배경없는 도트\)
- **rare2 민트→애플 개명** + leaf03 / **frog 개구리→프록 개명** + leaf04 / **bv3 풀잎**(이름 유지) + leaf05. 각각 진화+수면+2프레임 적용.
- **bv3는 걷기 대신 날개짓**: 무당벌레 날개가 몸(하단 12행 단일 런=x42~85) 힌지로 위/아래(바깥일수록 최대 5px) — `_walk1`=UP, `_walk2`=DOWN으로 저장해 기존 CreatureWalkAnim이 그대로 순환.
- **개명 방법**: CreatureDatabase.asset은 YAML이지만 한글이 `\uXXXX`(대문자 hex) escape — 문자 그대로 치환하면 0건, escape 문자열로 치환해야 함. 편집 후 에디터에선 ImportAsset(ForceUpdate)+CreatureCatalog static 캐시(_db/_byId/_stageCache/_walkCache/_sleepCache) 리플렉션 리셋 필요(빌드/플레이 재진입은 자연 해결). **주의: _stageCache 등에 null이 캐시돼 있으면 새 파일 추가해도 계속 null** → 캐시 클리어 필수.
- meta는 bd3.png.meta 복제+새 guid(uuid4)로 생성(규격 그대로). 소스는 도트셀 자동감지(cell=2)→진픽셀 축소→128 캔버스 bottom-margin 5 정렬. 수면은 세션30 파이프라인(H+V 인페인트+‿), 걷기는 기존 스타일(1px 바운스+좌우 발 교차) 재현.
- ⚠️ **주변 장식 절대 지우지 말 것**(하트·별·반짝이·공·숟가락 전부 alpha>16로 포함). 처음 성분필터로 지웠다 재작업.
- ⚠️ **본체(메인 연결 덩어리) 기준 중앙 정렬**(세션29 사용자 지적: 공이 오른쪽에 있으면 전체 bbox 중앙정렬 시 몸이 왼쪽으로 밀림). 방법: 8-connect 라벨링→최대 덩어리 bbox중심을 프레임(64,64)에 놓고, **전체 opaque의 본체중심 대비 최대 half-extent로 scale**(target_half=60)해서 액세서리·장식도 안 잘리게 fit. rd2·premium5는 장식 spread로 본체가 약간 작아짐(수용).
- **⚠️수면 폴백 버그(세션29)**: '눈 뜨고 자는' 증상 = GetSleepSprite가 해당 단계 수면 스프라이트 로드 실패 시 **평상시(awake) 컷으로 폴백**하던 것. 수정: 폴백 체인을 **항상 하위 단계 '자는' 컷으로**(stage2→ev2Sleep→evSleep→baseSleep→최후awake, stage1→evSleep→baseSleep→최후awake). baseSleep(CreaturesSleep)는 전 종 존재→사실상 눈 뜨고 자는 일 없음. LoadSleepCached 헬퍼. **에디터 프로젝트는 성장 수면 전 종 정상**(감사: 49종 중 누락=시크릿4=성장불가뿐, 이름·임포트 정상)이라 이 증상은 **구 APK 빌드 탓 → 재빌드 필요**.
- **진화 자는 모습(세션29)**: 5종 전부 `CreaturesEvolved2Sleep/<기본명>.png` 생성 — PIL로 근흑(RGB<60) 눈 blob 검출→대칭 눈쌍(좌우반대·유사크기·얼굴대 18~75%) 선택→눈bbox 스킨색 채움(하이라이트 제거)→평온한 U자(‿) 눈꺼풀 아치 그림. 볼터치·입·장식 유지. GetSleepSprite(id,stage2)가 자동 로드. **눈검출 보강(만쥬 계기)**: dark 임계 완화(R<72), 쌍 판정을 좌우중심 의존 대신 **수평분리(sep)+유사y+유사크기**로(몸에 꼬리/비대칭 있어 중심 치우쳐도 검출), 실패 시 얼굴대 최대 2개 폴백. 걷기·자는 생성 파이프라인은 스크래치패드 스크립트 재사용(process_evolve/make_walk/make_sleep).
- **걷기 애니메이션(세션29)**: 다리 있는 진화형만 자동 2프레임 워크사이클 생성 — 다리영역 감지(바닥부터 폭<55%bodymax 행, ≤28px)→좌우 발 번갈아 3px 들기+몸통 1px 바운스 → `_walk1/_walk2.png`. 적용: bd3·premium10·premium5(초코·솜사탕은 다리 없어 스킵). 코드: CreatureCatalog.GetWalkFrames(id,stage), CreatureWalkAnim.cs(이동중&깨어있을때만 순환, 수면 시 CreatureSleep이 관리→가드), CreatureWander.IsMoving 노출, FarmSpawner가 walk프레임 있으면 부착. 좌우반전 유지.
- ⚠️ **종 id 혼동 주의**(displayName은 asset에 \uXXXX JSON escape로 저장 → json.loads로 디코드): 디저트 rd1=도넛, rd2=솜사탕, rd3=**초코**(처음 rd1로 잘못 넣었다 정정). bd1마카롱 bd2푸딩 bd3컵케익. premium10=오로라 premium5무지개 premium6별빛천사.
- ⚠️ 사용자 제공 이미지가 500px·수천색(안티에일리어싱)이라 128 축소 시 기존(15~25색 굵은 도트)보다 약간 촘촘·부드러움. **권장 규격 안내함: 64×64 논리도트→128 저장, 16~24색, 하드엣지.** 그래도 적용은 정상.
- 쇼케이스 시 플레이모드에서 farm 씬 FarmIncome이 GameState.Save()로 주입데이터를 디스크에 저장함 → 검증 후 save.json에서 임시 생물(showcase-*)·가짜 도감기록 제거 필수. (star/chick이 stage2로 승격된 건 실제 진화 생물 마이그레이션이라 유지)

---
# (구) 생명체 진화 시스템 (2026-07-04 세션26)

> **세션27 개편**: "1개=1레벨"은 경험치제로 대체됨([[feature-xp-growth-system]] — 아이템 1개=+500xp, 레벨업 필요치 1000+200/레벨, 날씨 자동 경험치). 진화 레벨 10·스프라이트·골드 2배 등 나머지는 그대로.

사용자 설계: 상점에서 식단별 성장 아이템 판매 → 매칭 생물에게 먹여 레벨업 → **10레벨 = 1차 진화**(처음 15에서 사용자 요청으로 10으로 하향, GrowthCatalog.EvolveLevel 상수 하나만 바꾸면 됨. 2차 확장 여지).

- **아이템 4종**(각 150골드, 1개=1레벨, 상점 '성장' 탭): 채식=신비한 잎 / 육류=고대용의 어금니 / 인스턴트=정화된 에너지 / 디저트=메이플 시럽. 아이콘 Icons/growth_leaf·fang·energy·syrup. 시크릿 생물은 성장 대상 아님.
- **데이터**: CreatureData.level(기본1)·stage(0/1), SaveData.growthItems[4], SpeciesRecord.evolveCount. 규칙은 GrowthCatalog.cs(Feed/CanGrow/Owned) 단일 출처.
- **진화 스프라이트 61종+수면 61종**: 스크래치패드 gen_evolved.py로 자동 생성(이번엔 **스크립트 파일 보존됨** — 재생성 가능, 세션 스크래치패드라 소멸 주의. 필요하면 이 메모 기준 재작성). 종별 개성: 식단 테마 장식 3변형×종 해시 선택+팔레트 혼합색, 몸집 1.1~1.18배, 체커보드 오라, 반짝이. Resources/CreaturesEvolved/, CreaturesEvolvedSleep/(같은 시드로 장식 짝 맞춤). **함정**: 오라 그릴 때 스캔 중 픽셀을 바로 쓰면 번짐 — 위치 수집 후 일괄 기록.
- **게임 반영**: CreatureCatalog.GetSprite(CreatureData)/GetSleepSprite(id,stage) 폴백 체인, 농장 월드·하단카드·인벤 아이콘, CreatureSleep.stage, FarmIncome.TierGold ×2, 도감 카드 ★배지+상세 '진화 N번', 디테일 팝업(카드 1240으로 확대) 레벨 행+아이템 주기 버튼+진화 축하(ConfirmPopup.ShowInfo(msg, onOk) 오버로드 신설, 확인 시 onMoved→농장 씬 리로드로 월드 스프라이트 갱신).
- **함정 재확인**: 새 PNG는 임포트 설정 수동 적용 필요(TextureImporter Sprite/Point/PPU110/무압축 — 기본이 Sprite가 아니라 Resources.Load<Sprite> null). ✨ 이모지는 malgun에 없어 ★ 사용.
- 에디터 dev 세이브에 테스트 잔여: 골드 850으로 덮임, 성장아이템(잎5·시럽1) 남음. 도감 기록은 원복함.

후속 조정(같은 세션): ①아이템 없을 때 안내를 예/아니오 "구매하시겠습니까?"로 바꾸고 예→ShopManager.autoTab="growth"+씬 이동(1회성 static). ②ConfirmPopup 확인 1버튼일 때 중앙 정렬(ShowInternal에서 yes 위치 지정). ③재화 치트 중 GameState.SpendGold/SpendDia가 차감 없이 항상 성공(9999 유지).

**MCP 검증 함정 추가 확인**: script-execute가 예외로 실패하면 MCP 플러그인이 LogError를 찍는데, 에디터 **Error Pause**가 켜져 있으면 그 순간 플레이가 일시정지돼 이후 LoadScene한 씬의 Start()가 안 돈다(UI 없음, 에러 로그도 없음). `EditorApplication.isPaused=false`로 해제. 관련: [[reference-unity-mcp-hang]]

관련: [[feature-creature-species]] [[project-device-bugfix-s26]] [[todo-feature-backlog]]
