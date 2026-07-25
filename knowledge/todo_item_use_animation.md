---
name: todo-item-use-animation
description: 내일(2026-07-23) 만들 아이템 사용 애니메이션 사양 — 반동 없이 팔 뻗어 쓰고 내리기
metadata: 
  node_type: memory
  type: project
  originSessionId: bde6d017-c02b-46d1-b981-ffd120d25900
  modified: 2026-07-23T00:49:06.171Z
---

# 아이템 사용 애니메이션 ✅완료 (2026-07-22)

🔁**세션72(2026-07-23) 대체됨**: 유니티 쪽 요구가 "제스처 클립"이 아니라 **"정점 자세 유지 루프"**로 확정 — 아래 GDUR 제스처(올림→뻗음→내림) 구조는 Use/Shoot 전 클립에서 삭제됐다. 현행 규격은 [[project-player-anim-layer-spec]] 참조. 이 문서의 Q_AIM·Q_READY 값과 GDUR 교훈은 여전히 유효.

✅**완료(2026-07-22)**: `player@{Idle,Walk,Run,Jump}Use.fbx` 4종 납품(`player_유니티용\`). 총 Shoot에서 반동 구간만 제거 = 준비자세(euler 10,0,12/팔꿈치-55) → 앞으로 뻗어 사용(Q_AIM, 팔꿈치 0=폄) → 유지 → 준비자세 복귀(AIM→READY 단일 세그먼트). 왼팔 bob=LBOB(14°)*sin(2πap) 양끝0. 스크립트=`player_리깅\build_use.py`(build_gun.py에서 Q_RECOIL/RECOIL_ELB 삭제·ease_seg 전구간 smooth). 검증(FBX 재임포트)=팔꿈치 X 범위 [-55..0]로 **-55 아래 안 내려감=반동 없음** 확인·첫/끝 손위치 loopgap 0.0000(무장세트와 준비자세 공유=전환 매끄러움). 개발자_안내.txt에 Swing/Shoot/Use 3세트 전부 문서화(기존엔 Armed까지만 있었음). blend 백업=player_애니.blend.bak_before_use.

🔧**세션69 후속 개선(2026-07-22)**: ①팔 내리기 빠르게(KEYS 복귀 세그먼트 앞당김) ②앞뒤 대기 줄임 ③🚨**상태별 속도 통일 — 가장 중요**. 원래 제스처가 `SPAN`(사이클 길이 비율)에 묶여 있어서 **같은 동작인데 상태마다 속도 6배 차이**(대기 1.6초 vs 달리기 0.27초 — 실측). 원인=사이클 프레임 수가 상태마다 다름(Idle90/Walk25/Run17/Jump45)→짧은 클립일수록 제스처 압축. ⭐**해결=제스처를 사이클 비율이 아니라 고정 프레임(`GDUR=0.5*FPS=15`)에 박음** → 4종 전부 0.43초로 동일(뻗음0.17/복귀0.27), 나머지 프레임은 준비자세 유지라 루프도 안전. **재생방식=one-shot**(버튼→1회 재생→이동 복귀, 사용자 확정). 속도 조정은 `GDUR`의 `0.5`만 바꾸면 됨(one-shot이라 더 길게도 안전). ⭐**교훈: 오버레이/원샷 제스처는 사이클 비율(SPAN)로 타이밍 잡으면 상태마다 속도가 달라진다 — 반드시 고정 프레임 수로 박을 것.** 검증법=`dur.py`(ready로부터 각거리로 제스처 총시간 실측)·`seamcheck.py`(팔 본 경계각: 루프이음매·Armed진입/복귀·Shoot/Swing 준비자세 일치)·대기vs달리기 프레임별 비교 시트. Armed 진입 최대 1.83°(Walk/Run/Jump는 Armed 팔이 이동에 맞춰 bob 중이라 f1 위치 살짝 다른 것뿐, 유니티 0.1초 블렌드로 흡수).

---
## (원본 사양 — 참고용)

알약 플레이어(C:\Users\user\Desktop\알약게임\납품완료\player_리깅)에 **아이템 사용** 동작 추가 예정.

**동작**: 준비자세 → 팔을 앞으로 뻗어 아이템 사용 → 팔 내림(준비자세 복귀). **반동(팔꿈치 굽힘 튕김) 없음.** 왼팔은 자연스럽게 들썩임.

**만드는 법 = 오늘(총 사격) 방식 그대로.** 총 발사(Shoot)에서 **반동 구간만 빼면** 사실상 완성:
- 기반 스크립트: `build_gun.py`(scratchpad에 있었음 — 없으면 [[feature_player_face_emote_s65]]의 Shoot/Swing 항목 참고해 재작성). Idle/Walk/Run/Jump 4종.
- 어깨 포즈: 사용자가 `player_rigged_수정.blend`에 데모(Arm_R 쿼터니언)를 만들어 줄 수 있음 — 있으면 dump_raw.py로 fcurve 읽어 그대로 이식(쿼터니언→to_euler로 프레임마다 슬러프 베이크, 짐벌 방지). GIF도 줄 수 있음.
- **준비자세 공유 필수**: 시작·끝 = Q_READY=Euler(10,0,12,'XYZ') / 팔꿈치 -55. → Armed/Swing/Shoot과 전환 0.00m로 매끄러움.
- KEYS 구조(반동 제거판): ready→(빠르게 뻗어)AIM 사용→AIM 잠깐 유지→ready로 복귀. 사용 순간에 팔꿈치 굽힘 넣지 말 것.
- 속도: SPAN(동작을 사이클 앞쪽 %에 압축, 0.68 정도). 내림은 AIM→READY **단일 세그먼트**라야 버벅임 없음(중간 포즈 넣으면 이징 멈칫).
- 왼팔 bob=LBOB*sin(2π*ap), 양끝 0.
- 검증: pen_shoot류로 팔뚝-몸통 관통 0, boundary2.py로 다른 무기셋과 경계 손위치 0 확인, 앞뻗음은 **측면(-X쪽 카메라)** 렌더로 눈검수.

⭐사용자 작업 방식: 애매하면 blend 데모+GIF 받는 게 가장 빠르고 정확. 조정은 값만 바꿔 export(렌더 눈검수는 사용자가 필요할 때만 요청).
