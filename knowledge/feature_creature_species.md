---
name: feature-creature-species
description: "생명체 다종(species) 시스템 - 세션35 기준 총 32종, 부화가 식단(가장 많이 먹은 분류) 기반으로 작동"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4002085b-8eb6-4dc3-a299-5f10ed0ec3c8
---

## ★세션35 종 정리: 41 → 33종 (8종 삭제) — 최신
사용자 요청 8종 삭제. 이름→id: 호박석=premium8, 불곰=bm1, 멧돼지=bm3, 글리치=pi3, 칩스=ri2, 젤리=bi3, 바닐라=pd1, 푸딩=bd2.
- 삭제 후 tier: basic 11 / rare 7 / premium 11 / secret 4 = 33 → 세션35 후반 **랩터(pm2) 추가 삭제로 premium 10, 총 32종**. (tier×식단) 16조합 모두 ≥1종이라 부화 풀 안전.
- 코드에 종 id 하드코딩 없음(DB 엔트리 삭제만). 아트 PNG는 orphan으로 남김(세션29·32 전례와 동일, 무해).
- **도전과제 연쇄 수정**: 비시크릿이 29종이 되어 `dex_30`(30종) 고정 목표가 시크릿 없이는 달성 불가 → `DexDoctorGoal = clamp(전체×3/4, 5, 30)`(=24)로 자동 추종화. `dex_50`은 이미 `AllSpeciesCount` 추종 중이라 33으로 자동 갱신.
- 구세이브: `GameState.MigrateRemovedSpecies`가 이미 삭제종 생물을 제거+마리당 다이아1 보상, `SpeciesDiscovered`가 삭제종 도감기록 제외. 추가 작업 불필요.
- 백업: `Assets/Resources/CreatureDatabase.asset.bak_s35_delete8`.
- ⚠️ 기획서/화면정의서 "41종" 표기 stale.

---

## ★세션29 종 정리: 65 → 49종 (16종 삭제)
개발 관리 부담으로 사용자가 16종 삭제 요청 → CreatureDatabase.asset에서 제거(script-execute로 db.species.RemoveAll+SaveAssets)+세이브의 해당 생물/도감기록도 정리. 백업: `Documents/DietCreature/CreatureDatabase.asset.bak_s29`, save.json.delbak.
- 삭제된 id(이름): rv1완두 rv2브로콜리 rv3시금치 pv2당근 / rm3들소 rm1사자 pm1코뿔 premium1황금이 / rare1보라요정 **bi1라면** premium3사파이어 premium7크리스탈 / rare8로즈 pd2딸기 bunny토끼 rare4하늘토끼.
- 삭제 후 식단×등급: veg 4/3/4, meat 4/3/3, instant 3/4/4, dessert 4/4/5, secret 4 = **49**. 빈 풀 없음(부화 정상). 코드 하드코딩 참조 없음.
- ⚠️ **기획서/화면정의서의 "총 65종" 표기 stale** → 갱신 필요(도감 X/65 → X/49). [[reference-design-doc-ppt]] [[reference-screen-definition-ppt]]
- ⚠️ 삭제 종의 base/성장/수면 스프라이트 파일은 orphan으로 남김(무해). 필요 시 별도 정리.
- displayName은 asset에 \uXXXX(JSON escape)로 저장 — 이름↔id 매핑 시 json.loads로 디코드 후 대조(오삭제 방지).

---

## ✅ 현재 상태 (2026-06-27 세션5 기준, 최신)

세션5에서 종 시스템이 세션4 기록(5종/랜덤)에서 크게 발전함. **이 섹션이 최신 사실이고, 아래 세션4 내용은 히스토리**.

- **총 61종 / 3티어**: basic 17 · rare 22 · premium 22. 모두 `Assets/Resources/CreatureDatabase.asset`에 등록됨
- **종마다 식단 분류(dietCategory)**: veg(채식)/meat(육류)/instant(인스턴트)/dessert(디저트)
- **`CreatureSpeciesDef`에 필드 추가됨**: `tier`(basic/rare/premium, 어떤 알에서 나오는지) + `dietCategory`
- **부화가 더 이상 단순 랜덤이 아님 — 식단 기반 탄생이 실제로 연결됨**:
  - `GameState.RecordMeal(int categoryIndex)` → `Data.dietCounts[4]` 누적
  - `GameState.DominantDietCategory()` → 가장 많이 먹은 식단 인덱스 반환
  - `HatcheryManager.OnHatch()`(line~421): `tier = GameState.EggType` + `domDiet = DominantDietCategory()` → `_pendingSpecies = CreatureCatalog.RandomIdByDiet(tier, domDiet)`
- **CreatureCatalog 신규 API**: `RandomId(tier)`, `RandomIdByDiet(tier, dietIndex)`(조합 없으면 티어내 랜덤 폴백), `DietCats={veg,meat,instant,dessert}`
- 부화 흐름은 OnHatch에서 종 확정 → OnPlaceFarm/OnStore가 `_pendingSpecies` 그대로 사용(팝업=배치 종 일치, 세션4 버그픽스 유지)
- ⚠️ 아직 남은 것: 식사 사진 촬영/업로드/AI분석은 미구현. `RecordMeal`은 호출되지만 실제 사진→식단분류 매핑(MealCapture 씬)은 추후 작업. 즉 "식단 기반" 뼈대는 완성, 입력원(사진분석)만 비어있음
- 검증(세션5 확인): 스크립트24개 컴파일0, 콘솔 빨간에러는 전부 MCP 연결끊김 노이즈(게임코드 무관)

---

## 생명체 다종(species) 시스템 (2026-06-27 세션4 — 히스토리)

식단게임([[project-diet-creature-game]])의 핵심 메커니즘: 식사 10번 촬영 → 식습관에 맞는 생명체 탄생.
하지만 사진촬영/업로드 기능이 아직 없어서, **현재는 부화 시 종(species)을 랜덤 결정**한다.

### 중요 제약 (사용자 요청)
- 지금은 랜덤이지만, **나중에 식습관 데이터 기반으로 언제든 교체 가능하게** 구조를 짜둘 것
- 교체 지점(seam): `GameState.AddCreature(string species = null)` — null이면 랜덤(`CreatureCatalog.RandomId()`), 식습관 분석 완성 시 분석결과 species id를 넘기면 됨
- 종 목록/한글이름/희귀도/식습관매핑은 `CreatureCatalog`에 모음

### 종 (5종)
slime(슬라임), chick(병아리), frog(개구리), bunny(토끼), star(별돌이)

### 🗂️ 구조 (2026-06-27 세션4 리팩터 - "커지기 전 정리" 요청)
- **아트 위치**: `Assets/Art/Creatures/<id>.png` (5종 한곳에 모음). 코드로 절차생성한 PNG
- **데이터**: `Assets/Resources/CreatureDatabase.asset` (ScriptableObject, Resources엔 이 DB 하나만). 인스펙터에서 종 추가/편집 가능 (CreateAssetMenu: DietCreature/Creature Database)
- **스크립트**:
  - `CreatureDatabase.cs`: `CreatureSpeciesDef{ id, displayName, sprite (+추후 rarity/dietTags 주석) }`, `CreatureDatabase : ScriptableObject { List<CreatureSpeciesDef> species }`
  - `CreatureCatalog.cs` (static): DB를 `Resources.Load<CreatureDatabase>("CreatureDatabase")`로 1회 로드(캐시). API: `Get/GetName/GetSprite/RandomId/All`. **소비측(FarmSpawner/CollectionManager/HatcheryManager/CreatureData) API 동일** — 리팩터해도 그쪽 수정 불필요
- **종 추가 방법(앞으로)**: ① Art/Creatures에 png 추가 ② CreatureDatabase.asset에 항목(id/이름/스프라이트) 추가. 끝.
- 이전 방식이던 `Resources/Creatures/<id>.png` + 하드코딩 리스트는 폐기됨
- 중복이던 옛 `Art/Slime.png`(prefab+3씬 참조)는 새 슬라임아트로 덮어쓰고 GUID 보존하며 Art/Creatures/slime.png로 이동 → 참조 안 깨짐. CollectionManager의 미사용 creatureSprite 필드도 제거
- 검증: DB로드5종, 종별 스프라이트OK, Creature.prefab→Art/Creatures/slime.png 정상, 옛경로/Resources폴더 제거 확인, 컴파일0

### ✅ 구현 완료 (2026-06-27 세션4)
- `Assets/Scripts/CreatureCatalog.cs` 신규: 종 단일출처. `All`(id+한글이름 리스트), `Get/GetName/GetSprite`(Resources/Creatures/<id> 캐시로드), `RandomId()`. DefaultId="slime"
- `CreatureData`(SaveData.cs): `speciesName` 필드 제거 → `species`(id, 기본 "slime") 추가. 계산프로퍼티 `SpeciesName`(카탈로그 한글이름), `DisplayName`(별명>종이름). **구버전 저장본 호환**: species 누락 시 초기값 "slime" 유지(JsonUtility가 필드초기화자 보존)
- `GameState.AddCreature(string species=null)`: null이면 RandomId. **이게 식습관 연동 교체지점** — 분석결과 id 넘기면 됨
- `FarmSpawner`: GameState.Creatures 순회하며 각 인스턴스 SpriteRenderer.sprite = CreatureCatalog.GetSprite(species)
- `CollectionManager`: 엔트리 아이콘+상세 큰아이콘을 종별 스프라이트로. 상세에 "종류" 줄(_detailSpecies) 추가. creatureSprite 필드는 이제 미사용(dead, 씬 할당 남아있음)
- 스프라이트 절차생성: script-execute로 Texture2D에 Ellipse/FillPoly(별=10정점 point-in-polygon)/Eye 헬퍼로 그림→EncodeToPNG→Resources/Creatures/, importer Sprite/PPU110/alphaIsTransparency. 128px. Read도구(이미지)로 5종 시각확인 완료(귀여움). 별돌이 입 처음 시무룩→웃는입(∪, yy=50-4*sin)으로 FixStar 재생성
- 검증: 컴파일0. 스프라이트5종 로드OK, 랜덤30회 5종 골고루, AddCreature("frog")→개구리 정상. 저장파일 무오염
- 주의: 기존 Creature.prefab은 Art/Slime.png 참조 유지하나 FarmSpawner가 종별로 덮어씀. 슬라임은 새 Resources/Creatures/slime.png로 표시됨(도감과 일관)

### 🐛 버그픽스: 부화팝업=배치 종 불일치 (2026-06-27 세션4)
- 증상: 부화팝업(BornPopup)엔 고정 슬라임이 떠있는데 농장 배치하면 다른 종(랜덤)이 나옴
- 원인: 종 결정이 OnPlaceFarm(AddCreature 랜덤)에서 일어나 팝업 표시 이후였음
- 해결: HatcheryManager에서 **OnHatch(부화 순간)에 종 결정**. `_pendingSpecies = CreatureCatalog.RandomId()` → 팝업 이미지(`BornPopup/BornBox/BornSlime` Image) 스프라이트 교체 + BornTitle "OO 탄생!" 텍스트. OnPlaceFarm은 `AddCreature(_pendingSpecies)`로 같은 종 사용. Start에서 BornSlime/BornTitle을 이름으로 찾아 보관
- Hatchery 씬 BornPopup 구조: Canvas/BornPopup/BornBox/{BornTitle, BornSlime(생물이미지), PlaceFarmButton, ReleaseButton}
- 검증: reflection으로 OnHatch 3회→매번 팝업이미지==GetSprite(pending), 제목 정상(토끼탄생!/별돌이탄생!) 전부 일치. 테스트후 scene-open으로 씬 원복
- ★ 식습관 연동 시: OnHatch의 RandomId() 자리를 분석결과로 바꾸면 됨 (여기와 AddCreature 둘 다 _pendingSpecies로 흐름 통일됨)
