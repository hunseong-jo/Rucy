---
name: fbx-inspect-s59
description: FBX 검수 노하우(세션59) — 블렌더 5.0.1 헤드리스 FBX 임포트 라이트 버그 우회 + 플레인 데칼은 굽기 불필요
metadata: 
  node_type: memory
  type: reference
  originSessionId: ab507824-39df-409b-9daa-ec0fb6481c10
  modified: 2026-07-18T19:59:15.805Z
---

세션59(2026-07-16) injector.fbx 검수에서 얻은 재사용 지식:

1. **블렌더 5.0.1 헤드리스 FBX 임포트 버그**: FBX에 라이트가 들어 있으면 `blen_read_light`에서 `AttributeError: 'CyclesLightSettings' object has no attribute 'cast_shadow'`로 죽음. 우회 = `io_scene_fbx.import_fbx.blen_read_light`를 try/except로 몽키패치(실패 시 `bpy.data.lights.new(name,'POINT')` 반환). FBX 검수 스크립트에 항상 넣을 것.

2. **플레인+슈링크랩 데칼은 굽기(bake_decal) 불필요**: 사용자 워크플로 = 로고를 별도 plane에 만들어 슈링크랩으로 몸체에 부착 → FBX에 별도 머티리얼 슬롯으로 들어감 → 유니티에서 그 머티리얼만 **Alpha Clipping** 체크하면 끝. [[project-my-agent]]의 bake_decal은 '몸체 재질에 직접 얹은 투명 PNG'(표준 셰이더가 바탕색+데칼 합성 불가) 전용. 주의: 슈링크랩 Offset 0.001~0.005로 Z-파이팅 방지, 데칼 플레인 Cast Shadows Off.

3. **FBX 검수 체크리스트**: 텍스처 외부파일(fbm 폴더 또는 옆 PNG) 여부·ASCII명·존재, 부품 월드좌표를 **원본 blend와 대조**(자식 오브젝트의 로컬좌표가 0.01 스케일 부모 때문에 -51 같이 커 보여도 월드는 정상일 수 있음), 카메라/라이트 딸림(유니티 Model 탭 Import Cameras/Lights 해제로 무해화 가능), 머티리얼 누락.

4. **납품 규칙**: FBX+사용 PNG를 한 세트로 전달, 파일명 변경 금지, Assets 같은 폴더에. FBX 단독은 색만 나오고 텍스처 빠짐(임베드 아니면 참조 주소만 저장됨).

injector.fbx(알약게임 주사기) 검수 결과: 형상·텍스처 정상, 카메라/라이트 포함·Cube 머티리얼 없음·전장 ~2.2m.

5. **세션60 추가(주사기 데칼 '아예 안 보임' 사건)**: bar(갈색=텍스처 미바인딩)와 달리 **데칼 면이 통째로 투명**해지는 증상의 뿌리 = 블렌더 머티리얼의 **Alpha 소켓에 텍스처가 연결**돼 있으면 FBX가 투명 재질로 기록되고, 유니티가 그 머티리얼을 투명 서피스로 임포트(텍스처까지 못 물리면 완전 투명). 그리고 **"Alpha Clipping 체크박스가 회색 비활성"은 버그가 아니라 FBX 딸림 머티리얼이 읽기 전용**이라서 — Materials 탭 **Extract Materials...**로 추출해야 편집 가능. 표준 처방(개발자 전달용): ①FBX+PNG 같은 폴더 반입 ②Extract Materials ③데칼 머티리얼에 Base Map=PNG 확인+Alpha Clipping ✓(Threshold 0.5)+Render Face Both. injector는 데칼이 별도 플레인이 아니라 **몸통 Cylinder의 면 231개에 2번 슬롯**으로 붙은 구조. 재납품=`Desktop\알약게임\injector_유니티용\`(카메라/라이트 제거·머티리얼 InjectorBody/InjectorSub/**InjectorDecal** 개명·외부 PNG 동봉, 재임포트 검증✅). ⚠️path_mode='COPY'는 텍스처를 `<이름>.fbm` 하위폴더에 넣음 → 납품 시 FBX 옆으로 꺼낼 것. Cube 부품은 원본부터 머티리얼 없음(유니티선 기본 회색).

6. **세션60 2차(진짜 뿌리): 데칼 면 노멀 뒤집힘** — "겉에선 안 보이고 **안쪽에서 투시하면 좌우반전으로 보임**" = 노멀이 안쪽을 향한다는 결정적 증상(유니티 기본=앞면만 렌더). 실측 dot(평균노멀·바깥방향)=-1.000. 수리=bmesh로 해당 머티리얼 슬롯 면만 `normal_flip()` → 재수출 → **바깥에서 렌더해 글자 반전 없는지 눈검수**(decal_preview.png ✅). 진단 공식: 데칼 면들의 평균노멀과 원통 중심→면중심 방사방향의 내적이 음수면 뒤집힘. ⚠️블렌더 5.0 `save_as_mainfile`에 save_version 인자 없어짐. ⚠️사용자 blend가 실시간 편집 중이면 오브젝트 이름 바뀜(Cylinder→Cylinder.002) — **이름 말고 '이미지 텍스처 가진 머티리얼'로 데칼을 찾을 것**. ⚠️blend에 유실 참조 '완성된 데칼.png'(한글명!) 생김 — 한글 텍스처명은 유니티 반입 금물, 쓰게 되면 ASCII 개명 필요. injector2.fbx(사용자 자체 수출 시도)는 노멀 미수정 구본.

8. **2026-07-19 무기 테이블 납품 — `.fbm` 문제의 정답은 `path_mode='STRIP'`**: 6번의 "COPY가 만든 .fbm에서 텍스처를 옆으로 꺼낼 것"보다 근본 해법. COPY는 텍스처 사본을 `<이름>.fbm\`에 넣고 **FBX에 그 하위폴더 경로를 기록**해서, FBX+PNG만 보내면 참조가 깨짐(재임포트로 실측 확인). `path_mode='STRIP'`이면 파일명만 기록 → FBX 옆의 PNG를 그대로 찾음. 납품 폴더엔 `.fbm`·`.blend1` 잔여물도 지울 것. **납품 전 반드시 납품본 FBX를 되읽어** 텍스처 filepath·존재·Base Color 연결·크기·스케일 1.0·플랫셰이딩(smooth face 0개)·signed volume을 찍고 **렌더까지 눈검수**할 것([[project-pill-base-model]] 무기 테이블이 이 절차로 PASS). 수출 인자: `use_selection=True, path_mode='STRIP', embed_textures=False, apply_scale_options='FBX_SCALE_ALL', mesh_smooth_type='FACE'`.

7. **세션61(2026-07-17) 종결: 노멀 전수진단+데칼 굽기로 근절** — 사용자가 Face Orientation으로 피스톤 손잡이(Cube) 전체 빨강 발견 + 방패(shield.fbm\shild.blend) 몸통도 뒤집힘 + "데칼 여전히 안 보임". ①**전수진단 공식=부호 있는 부피(signed volume, 발산정리)**: 음수=노멀 안쪽 — 원통 방사방향 내적보다 일반적(아무 형상이나 됨). 방패 몸통은 슬롯별로 뒤집힘/정상 혼재(signed_vol -0.80)였음 → 수리=`bmesh.ops.recalc_face_normals`(전 면) 후 signed_vol 음수면 reverse_faces. ②**데칼 안 보임 근절=불투명 굽기**: PIL로 데칼 PNG를 몸통색(Principled linear→sRGB 변환) 위에 합성→불투명 PNG, Alpha 링크 해제+OPAQUE → 유니티 쪽 설정(Extract Materials·Alpha Clipping) 자체가 불필요. 데칼 면=몸체 표면 자체라 바탕색만 맞으면 시각 동일(이음새 없음, 렌더 실검증). ③**재발 뿌리 후보=구본 잔존**: 납품 폴더에 노멀 수정 전 FBX가 남아 친구가 그걸 사용 + 유니티에 Extract했던 투명 머티리얼 연결이 .meta에 남으면 덮어쓰기 후에도 예전 머티리얼 사용 → 안내=구 FBX만 삭제(방법A) 또는 덮어쓰기 시 Materials 탭 Remapped Materials 매핑 제거(방법B). ⚠️**공용 decal.png는 다른 아이템들(bar 등)이 쓰므로 삭제 금지**(사용자 정정) — 그래서 납품 텍스처는 반드시 아이템 전용 이름(injector_decal.png 등)으로 굽는 게 정답(충돌 원천 차단). 납품=injector_유니티용(injector.fbx+injector_decal.png)·shield_유니티용(shield.fbx+shield_decal.png)+개발자_안내.txt, 재임포트 검증 PASS+4방향 눈검수✅. 방패 머티리얼 Material.00X→Shield* 개명·빈 슬롯 26면 ShieldBody 채움·카메라/라이트 제거. ⚠️수출 blend에 이미지가 auto-pack될 수 있음("Packed 1 file(s)") — path_mode='COPY'가 외부 PNG를 .fbm에 또 쓰므로 결과 무해.
