---
name: feature-stage1-art-s33
description: "세션33: 성장(5레벨, stage1) 아트 21종 사용자 신규 이미지로 전면 교체 + 수면/걷기 프레임 + CreaturesEvolvedWalk 폴더 신설."
metadata: 
  node_type: memory
  type: project
  originSessionId: 504d9c26-d2f6-45f0-9649-1c09b93b3492
---

# 성장(stage1) 아트 21종 교체 (2026-07-09 세션33)

사용자가 가져온 5레벨 진화(성장) 이미지 21종(진화 21종과 동일 목록: bd3 bi2 bm2 bv1 bv2 bv3 frog pd3 premium2/4/5/10 pv1 pv3 rare2/5/6/10 rd1/2/3)을 128px 도트 규격으로 변환·교체.

- **파이프라인**: 500px removebg PNG → 알파 정리 → bbox 크롭 → 56그리드 BOX 다운스케일+32색 양자화 → ×2 NEAREST → 128 캔버스(콘텐츠 최대 112, 하단 여백 10). rd1은 removebg 실패분(흰 배경 alpha128)이라 저알파 전면 제거로 해결.
- **수면 21종(v4까지 재작업)**: 사용자 지적 2회 반영. 최종 방식(sleep_v4.py) = **실측 눈 박스(12종 하드코딩) + 링 중앙값 필터 채움(좌→우 선형보간, 어두운 외곽선 색 유입 차단) + 1px 매끄러운 포물선 ‿(계단꺾쇠 금지) + 눈색 75%+살색 25% 블렌드(순검정 금지)**. 소용돌이 파스텔 얼굴(premium5·rd2)은 보간 대신 **무늬 거울/스트립 복사**(premium5는 입 복제 자국 후처리 필요했음). **pd3는 우향 옆모습이라 눈 하나만**.
- **⚠️내부 투명 구멍 함정**: removebg 원본의 반투명 스파클이 알파 이진화(≥128→255, 미만→0)에서 **얼굴 속 투명 구멍**이 됨(bi2·bv1·bv2·pd3·premium5, bv2는 눈 안!). 외곽 플러드필로 내부 구멍 검출→이웃색 메움(find_holes.py/sleep_v4.py). 기존 절차생성 40종의 구멍(~100px씩)은 원래 스타일이므로 건드리지 말 것.
- **걷기 프레임**: `Resources/CreaturesEvolvedWalk/<이름>_walk1/2` 신설(42파일, .meta는 기존 walk 메타 복제+새 GUID). 다리 없는 종: squash(블롭·슬라임)/float+반짝(bi2·premium2·rd2)/sway(bv1·rare5). **다리 9종(bd3 bm2 bv2 bv3 frog pd3 pv1 pv3 rare6)은 스텝 모션**: 다리 영역(종별 leg_h 5~12px, pd3_walklegs.py)을 좌/우 절반 번갈아 2px 들어올림(walk1=왼발, walk2=오른발, 정지=기본 컷). pd3 수면은 눈 폭 11px 큰 ‿로 별도 재수정.
- **코드**: `CreatureCatalog.GetWalkFrames` stage1→CreaturesEvolvedWalk 분기 추가(기존엔 stage0·1이 CreaturesWalk 공유라 성장 프레임이 없었음). 도입 시 stage0이 성장 프레임 집어가지 않는 것 검증(rd1 s0=0).
- **방향**: bm2(고양이)만 검토 중 오반전 → 본체+수면+걷기 4파일 재반전으로 우향 복구. 나머지 20종은 정면/우향 정상.
- **백업**: 교체 전 원본 `Documents\DietCreature\ArtBackups\evolved_s33_old`, `evolvedsleep_s33_old`.
- 에디터 검증: 21/21 성장·수면·걷기(2프레임) 로드, 컴파일 무오류. **실기기/플레이모드 육안 확인은 다음 기회**.
- 관련: [[feature-creature-evolution]], [[feedback-creature-art-pipeline]], [[project-session33-fixes]]
