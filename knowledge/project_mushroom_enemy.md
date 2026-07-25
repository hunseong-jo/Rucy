---
name: project_mushroom_enemy
description: 알약게임 보라 버섯 적 몬스터 3D 에셋 (Untitled_디테일.blend) — 리그·바운스 애니 완료
metadata: 
  node_type: memory
  type: project
  originSessionId: 73e8cebc-ecd4-4177-b782-c413fa4891d8
  modified: 2026-07-22T10:23:00.561Z
---

알약게임(C:\Users\user\Desktop\알약게임)의 **보라 버섯 적 몬스터** 3D 에셋. 작업 파일 `Untitled_디테일.blend` (원본 `Untitled.blend`은 보존). 참조 = 로우폴리 보라 갓 + 베이지 기둥 + 화난 눈 + 밑동 다육이/열매. Blender D:\blander\blender.exe 5.0.1.

⭐**분업(중요)**: 조형·소켓·눈알은 **사용자 본인이 직접** 만든다. 클로드는 **머티리얼 분리·텍스처·리깅·애니메이션** 담당. [[feedback_lucy_cannot_design_form]] 취지대로 사용자 조형물은 안 건드림.

**구성 오브젝트**:
- `Mushroom_Body` — 사용자 조형(537v). 면별 머티리얼 분리: `Stem_Beige`/`Cap_Purple`/`Cap_Gill`(갓밑 주름).
- `Sphere`(Material.002) — **사용자가 만든 눈알 2개**(좌 x−0.126 / 우 +0.126, y−0.24, z≈0.0). ⚠️내 앰버 슬릿 데칼(mushroom_eye.png)은 사용자가 지우고 자기 눈으로 교체함. ⭐**세션70(2026-07-22): 바운스 때 눈이 떨어지길래 사용자가 눈을 몸통 메시에 조인함** — 이제 별도 Stem2 강체 바인딩이 아니라 몸통 자동웨이트 흐름을 그대로 탐. 검수 스트립으로 30프레임 내내 얼굴 고정 확인됨. 재렌더는 anim 없이 blend에 저장된 Bounce 액션 그대로 render_anim.py→make_gif.py만 돌리면 됨.
- 밑동: `Leaf_0..11`·`LeafF_0..3`·`Berry_0..6`.

**리그**(`Rig` 아마추어, 4본): Root→Stem1→Stem2→Cap. 몸통=자동 웨이트(ARMATURE_AUTO), 밑동 잎/열매=Root 강체(단일 그룹 w1), **눈(Sphere)=Stem2 강체**(바운스 때 얼굴 따라감).

**Bounce 액션**(사용자가 승인한 그 바운스): 30프레임 심리스 루프 @30fps. `rig.location.z = 0.16*sin(π t)`(땅 접촉 V자 홉) + Root 본 스쿼시&스트레치(세로 0.90~1.08, 가로 1/√ 부피보존, 지면 피벗) + Cap 본 지연 오버랩. 스크립트 scratchpad/anim_bounce.py.

⚠️**함정**: Blender 5.0은 슬롯형 Action이라 `action.fcurves`가 **없음**(AttributeError로 저장 전 크래시). fcurve 보간 손대지 말 것. / 눈 소켓은 갓 바로 아래 **얕은 각진 인셋 아몬드**라 거리/깊이 휴리스틱으로 면 자동검출 계속 실패 → **와이어프레임 렌더로 토폴로지를 눈으로 봐야** 파악됨.

**썩은 숲 결 텍스처**(세션70·2026-07-22, 사용자가 방향 선택): 절차 노드 머티리얼로 **갓=초록 이끼 얼룩**(Cap_Purple: Object 좌표 노이즈 블롯치×Generated Z 상단 바이어스, 두 톤 이끼 0.11,0.17,0.055 / 0.06,0.10,0.03, 드문 다크로트 패치)+**기둥=밑동부터 타고 오르는 곰팡이**(Stem_Beige: 초록그레이 0.30,0.36,0.20, ⚠️눈 조인으로 몸통 Generated Z가 잎~갓 전체(genZ 0.057~0.997)로 늘어남 → 기둥 실제 밴드는 **genZ 0.057~0.632**·보이는 부분은 잎에 안 가린 0.25~0.63이라 그라데이션을 그 범위로 재조정해야 곰팡이가 보임)+거친 무광(rough 0.92~0.95)+미세 범프. 스크립트 scratchpad/rot_mats.py(`-- <dest.blend>`로 저장 경로 지정, 없으면 프리뷰 사본). 눈(Material/Material.002)·Cap_Gill·잎·열매·형태는 안 건드림. 🚨**텍스처 스위밍 함정(사용자 지적: 점프마다 이끼 위치 바뀜)**: Object/Generated 좌표는 **아마추어로 변형된** 메시에서 매 프레임 재계산돼 표면을 미끄러짐 → 반드시 rest(정지) 좌표로 배치해야 표면에 붙어 스쿼시와 같이 눌림. ⚠️이 몸통엔 `rest_position` 속성이 **자동 생성 안 됨**(아마추어가 안 만들어줌, EVAL 메시에도 없음) → rot_mats.py가 `me.vertices[i].co`(항상 rest 로컬좌표)를 `rest_position` FLOAT_VECTOR POINT 속성으로 **직접 구워 넣고** Attribute 노드(GEOMETRY)로 읽음. Z 그라데이션은 그 rest Z를 MapRange(ZMIN -2.103, ZMAX 1.0001→0,1)로 정규화해 genZ로 재사용. UVMap은 이미 있음(눈 매핑용). ⚠️**절차 노드는 FBX로 유니티에 안 실려감** — 유니티 납품하려면 UV 펴서 텍스처 베이크 필요(아직 안 함).

**밑동 수풀 다듬기**(세션70, 사용자 지적 "너무 뾰족"): 잎 16개(Leaf_0..11·LeafF_0..3, 각 12정점 방추형=위아래 뾰족점+5각 링 2개, 긴축=로컬 z)를 다육이처럼 부드럽게 — 끝점 z 0.5배 압축(뭉툭)+링을 짧은 두 축으로 1.42배 확장(도톰)+use_smooth(각 죽임). 스크립트 reshape_leaves.py(긴축 자동검출·유니크 메시별 1회·`-- <dest>`). 리깅 불변(잎=Root 강체 유지→바운스 정상). ⚠️도톰해지며 **보라 열매(Berry) 가려짐** — 원하면 위로 올려 재노출. 형태 변경이지만 사용자가 명시적으로 요청함(조형물 불가침 예외).

**백업**: `.bak_socket`(사용자 소켓 카빙), `.bak_usereyes`(눈 바인딩 직전), `.bak_beforerot`(썩은 결 적용 직전), `.bak_beforeleaf`(잎 다듬기 직전). 미리보기 `bounce_preview.gif`(썩은 결+수풀 반영).

**✅유니티 FBX 납품**(세션70): `Desktop\버섯몬\` — `버섯몬.fbx`(모델+리그) + `버섯몬@이동.fbx`(바운스=액션명 '이동'으로 개명, 30f·30fps·심리스 루프) + `개발자_안내.txt`. 재임포트 검증 PASS(메시24=몸통+잎16+열매7·2197정점·4본 Root/Stem1/Stem2/Cap·'이동' 클립 변형 정상). export_fbx.py(object_types={ARMATURE,MESH}로 카메라/라이트 제외·add_leaf_bones=False·-Z fwd/Y up·@규칙). ⚠️**절차 이끼/곰팡이는 FBX에 안 실림** — Cap_Purple 등 base color가 노드 연결이라 exporter가 흰색 폴백으로 뽑음(검증샷서 갓 흰색 확인). 유니티에 이끼 재현하려면 UV 펴서 albedo 베이크 필요(아직 안 함). 원본 blend 액션도 '이동'으로 개명 저장됨.

**✅이끼 텍스처 베이크+재납품**(세션70, 사용자 "텍스처 안 딸려왔어"): 폴더는 사용자가 `Desktop\알약게임\버섯몬`으로 이동함. bake_body.py — 몸통 Smart UV Project(기존 UVMap은 눈 전용이라 새로 펴야 함)→1024 이미지 생성→5개 몸통 머티리얼 각각에 활성 Image 노드 꽂고→**Cycles DIFFUSE COLOR 패스 베이크**(순수 albedo, 조명無, samples 4·margin 10)→PNG 저장→몸통을 단일 `버섯몬_Body`(Base Color=텍스처)로 collapse(전 face material_index=0)→**path_mode='COPY'+embed_textures=True로 FBX 재export**. 산출: `버섯몬_albedo.png`(1024, 기둥 베이지+이끼/갓 보라+이끼/눈·주름 다 구워짐) + FBX 2종(텍스처 임베드, ~1MB). 재임포트 검증서 이끼 딸려옴 확인. 유니티서 텍스처 안 뜨면 Materials탭 Extract Textures. ⚠️절차 노드는 rest_position 좌표라 UV 없어도 렌더되지만 **베이크엔 non-overlap UV 필수** → Smart Project 먼저. 원본 blend는 절차 노드 유지(재굽기 가능).

**✅애니 4종 추가 납품**(세션70, 사용자 "공격·피격·사망·대기 만들어줘"): `버섯몬@{대기,공격,피격,사망}.fbx`(+기존 이동). 전부 텍스처 임베드·같은 리그·30fps. 대기60f루프(호흡=Root scale.y±0.028 스쿼시+Cap 미세 sway)·공격26f(웅크림 anticipation→앞으로 갓 박치기→복귀)·피격20f(뒤로 움찔→감쇠 복귀)·사망42f(헐떡→바람빠지듯 주저앉음, 마지막 유지). ⭐**본 축(rig_axes.py 실측)**: 전 본 공통 로컬 Y=위(월드+Z)·**로컬 X 회전 양수=앞으로(얼굴 -Y) 숙임**·음수=뒤로 젖힘, Root.scale.y=수직 스쿼시. 얼굴=−Y. 🚨**UV/텍스처 어긋남 함정**: bake_body.py의 Smart UV Project를 마스터에 저장 안 해서, 마스터(옛 눈전용 UV)에서 애니 뽑으니 텍스처가 검은/흰/보라로 스크램블됨 → **UV+텍스처 일치하는 베이크 블렌더 저장이 답**(scratchpad/버섯몬_baked.blend=Smart UV+베이크PNG팩+단일 머티리얼, 이걸로 build_anims2.py·build_death.py 실행). ⚠️사망 v1은 Root flatten 과해 팬케이크(밟힌 느낌)·v2도 갓 앞으로 과회전해 카메라쪽 엎어짐→v3=제자리 주저앉음+옆으로 살짝. ⭐애니 성격 카메라 의존 주의(넘어지는 방향이 카메라 향하면 납작해 보임). 스크립트: rig_axes.py·bake2.py·build_anims2.py·build_death.py. 마스터엔 4종 액션 저장 안 함(재export는 베이크 블렌더로).

🚨**눈 떨어짐 = 웨이트 불일치 수정**(세션70, 사용자 "격한 움직임에 눈이 떨어져"): 진단(diag_eye_weights.py)에서 **눈 정점 978개가 Stem2 0.986에 물렸는데 눈이 박힌 얼굴 소켓 표면은 Cap 0.65+Stem1 0.35**(Stem2 거의 0) — 서로 다른 본이라 공격 박치기(Cap 대회전)에 눈만 뒤처져 떨어짐. [[feedback_creature_art_pipeline]] 취지의 player 교훈과 동일("붙어 있어야 할 것끼리 웨이트 불일치→KDTree 이웃 복사"). 수정(fix_eye_weights.py): 눈 정점을 material(Material/Material.002)로 식별→edge union-find로 4덩어리 클러스터(눈알 482v×2+하이라이트 7v×2)→각 덩어리 centroid의 최근접 non-eye 12정점 웨이트 평균을 **덩어리 전체에 통째 REPLACE(강체 유지)**. 결과 눈=소켓과 같은 Stem1 0.35+Cap 0.65. 공격 웅크림/스트라이크/피격 렌더로 눈 부착 검증. ⭐**조인한 눈은 웨이트를 자동으로 안 물려받음 — 소켓 표면 웨이트로 강제 복사 필수**. 마스터 수정 저장(bak_beforeeyefix)→bake2 재베이크→rebuild_all.py로 6 FBX 전부 재export(base+5클립). rebuild_all.py=이동 bounce 인라인+4클립 key()+base, 베이크 블렌더에서 실행.

✅**내부 스피어 삭제**(세션70, 사용자 "몸속 스피어 지워줘"): Mushroom_Body 안에 조인돼 있던 떨어진 덩어리 — 242정점 완전 구형(0.583³)·중심축 위(x0,y0,z-0.46)·Stem_Beige, 눈 만들 때 남은 원본 프리미티브로 추정. islands.py 유니온파인드로 4섬 판별(눈알 482×2·본체 295·**스피어 242**)→delete_sphere.py가 시그니처(dim<1.0 전부·|cx|,|cy|<0.12·cz<-0.2)로 그것만 bmesh 삭제(1501→1259정점). 눈은 앞쪽 y-0.33이라 안전 제외. 마스터 삭제(bak_beforespheredel)→bake2 재베이크→rebuild_all 6 FBX 재export. ⭐rebuild_all.py의 render_frames 호출 빼면 렌더 없이 FBX만 빠르게.

✅**갓 색 통일 + 포자/이끼 강화**(2026-07-22, 사용자 "갓 뒷부분 진한 보라 경계 어색 → 색 통일 + 포자·이끼 더 쎄게"): **원인=Cap_Gill**(갓 밑/림 18면)이 base color (0.09,0.012,0.07) **진한 보라 단색**이라 밝은 Cap_Purple 돔과 딱딱한 경계 seam을 냄(조명 아닌 실제 다른 머티리얼). 수리=Cap_Gill을 Cap_Purple과 **같은 PURPLE(0.24,0.035,0.19) 베이스로 재빌드**(seam 소멸) + 이끼 강화(coverage↑·MOSS 밝게 0.13,0.22,0.07·밝은 fuzzy tip MOSS_B 신설·mossfac 0.55→0.85·top bias 완화) + **포자 신규 레이어**(pale ashy SPORE 0.56,0.58,0.50, 고주파 speckle×클럼프 마스크, ⭐**갓 밑동/gill은 포자를 더 진하게**=포자는 주름에서 나오므로 thematically 맞음, gill은 이끼 거의 없고 포자 dense). 스크립트=scratchpad `mat_v2.py`(build_cap(matname, gill=Bool) 함수화, stem은 rot_mats 그대로 유지, `-- <dest>`). 백업 `.bak_beforemoss2`. 파이프라인=마스터 적용→bake2.py 재베이크(albedo 1.10MB)→rebuild_all.py 6 FBX 재export(전부 19:21 갱신·~1.4MB). 재임포트 검증 렌더 PASS(텍스처 임베드 정상·눈 유지·seam 사라짐·이끼/포자 강함). ⭐머티리얼 seam 문제는 조명 탓처럼 보여도 **base color 실측으로 다른 머티리얼인지 먼저 갈라볼 것**(여기선 Cap_Gill 0.09 단색이 범인).

**다음 후보**: 등장/스폰 애니 / 텍스처 해상도·결 조정 후 재굽기 / 노멀맵 등 추가 텍스처.
