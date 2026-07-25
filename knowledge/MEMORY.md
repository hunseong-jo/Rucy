# Memory Index

## 루시(내 AI 비서)
- [나만의 AI 비서 루시](project_my_agent.md) — C:\Users\user\my-agent, start.bat. 두뇌 11단·도구 77종·doctor 11종·블렌더 51동작. ⭐분업: 시각/조형/설계=클로드, 기계적/수치/반복=루시. ⭐manual_루시_사용설명서.md가 유일 원본 — 새 기능 시 반드시 갱신. 🔎s75 점검 미결(승인 필요): **자동 후순위가 실제 대화엔 안 걸림**(pick_order가 늘 order를 넘겨 rank 우회 — /상태가 사실과 다른 말을 함)·**눈 3개 중 쓸 만한 건 Gemini뿐**. 함정·도구목록·세션이력 전부 파일에.
- [루시 기능 백로그](todo_lucy_feature_backlog.md) — 파일 맨 위 '다음에 할 것' 절이 최신. 다음 후보=실전 한 바퀴·웨이크워드·지하철 키. ⛔폰 원격 개발 중단.
- [루시 사고력 강화 4중 장치](project_lucy_thinking_s70.md) — 추론 모드·deep 확대·독립감수·분해 지시. config deliberate로 전부 끔.
- [강의 PDF RAG 학습](feature_lecture_rag.md) · [게임 기획 학습](feature_lucy_gamedesign.md) · [✅기능 5종 완료](todo_lucy_next_features.md) · [✅구글 연동 완료](todo_google_oauth_setup.md) · [Oracle Cloud VPS 24/7 배포 매뉴얼](manual_oracle_cloud_deploy.md)

## 피드백 · 원칙
- [⚠️루시는 형태를 설계 못 한다](feedback_lucy_cannot_design_form.md) — 도구 늘리기 전에 형태 설계 문제인지 갈라라. 자기 진단도 못 믿음.
- [⚠️사진+제작 요청 뒤집기](feedback_image_turn_tools_off.md) — 사진 붙은 턴=도구 꺼짐. 눈+도구 동시는 아직 불가.
- [⚠️애니는 대칭 키프레임=로봇](feedback_animation_not_robotic.md) — 4포즈·오버랩·무게이동·접지 비대칭, 검증은 GIF로.
- [⚠️단위테스트 통과 ≠ 작동](feedback_verify_by_actually_running.md) — 실물로 돌리고 결과를 되읽을 것.
- [⚠️나쁜 점수는 시험지를 먼저 의심](feedback_suspect_the_rubric.md) — 문항은 직접 눈으로 볼 것.
- [⚠️초안 위에 계산을 쌓지 말 것](feedback_verify_draft_before_building_on_it.md) — 사용자가 준 값과 내가 메운 값을 구분.
- [모든 대화 내용 저장 요청](feedback_save_everything.md) · [일일 퀘스트 금지](feedback_no_daily_quests.md) · [생물 이미지 표준 파이프라인](feedback_creature_art_pipeline.md)

## 알약 협동 게임 (Pill Agents) — 개발은 친구, 사용자=기획
- [게임 기획서](project_pill_coop_game.md) — Unity 3D 2~4인 협동. 기획서 v1.2 30장 + 와이어프레임 v0.6. 남은 것·결정 경위는 파일에.
- [보스 「기생충」 3D](project_boss_parasite.md) — ✅**완료**. 전장 20m·34,284tri·본286·모션 10종·텍스처 3장·부위파괴 분리. 🚨FBX는 절차 셰이더를 못 실음→반드시 베이크, 미리보기는 GLB. 미착수=촉수 경량판.
- [연출 에셋(게임필)](project_pill_juice_assets.md) — ✅에셋 10종 + 5B 허브 완료. 🚨유니티 실물 임포트가 블렌더로는 못 잡는 결함을 잡는다(유리 불투명·텍스처 미결합). 임시 프로젝트+배치모드 검증법.
- [대형 음식물 더미](feature_pill_food_props.md) — 파괴 대상 5종 중 3종 완료. 🔜**다음 세션: 텍스처 + 파괴 3단계.** ⭐파괴 연출 확정=침식이 아니라 「부수면 조각나 소화가 쉬워진다」(온전한 게 결함이 아니라 임무의 이유).
- [플레이어 얼굴 이모트 v4.1](feature_player_face_emote_s65.md) — 유리돔+내부셸+표정 아틀라스 8종, 리깅·애니 완료(v3.5). 🚧팔 주름 미해결. 함정 다수 파일에.
- [유니티 도구 레이어 규격](project_player_anim_layer_spec.md) — 플레이어 애니 계약서. 도구 상태 클립="이미 그 자세인 채로의 순환". Avatar Mask 2종.
- [✅아이템 사용 애니](todo_item_use_animation.md) — player@{Idle,Walk,Run,Jump}Use. ⭐오버레이 제스처는 고정 프레임 수로 타이밍 잡을 것.
- [알약 기지(캡슐)](project_pill_base_model.md) — 🚨사용자 조형물은 고치지 말 것. 무기 테이블은 클로드 제작.
- [초록 배기구 블롭몬](project_vent_blob_monster.md) — ✅유니티 납품. 🚨부착물 1개=웨이트 1벌. '따로 노는가'는 거리 말고 아핀 잔차로.
- [보라 가시 기뢰형 sed](project_sed_angry_blob.md) · [보라 버섯 적](project_mushroom_enemy.md)

## 3D · 파이프라인 공통
- [블렌더 3D 파이프라인](feature_blender_pipeline.md) — D:\blander\blender.exe 5.0.1, 헤드리스 조형→렌더→눈검수→FBX.
- [FBX 검수 노하우](reference_fbx_inspect_s59.md) — 🚨FBX 머티리얼은 읽기전용→**Extract Materials가 열쇠**. 노멀 뒤집힘 진단=signed volume. 데칼 함정 3종.

## 샐러드팜 (식단 육성 게임)
- [게임 개요](project_diet_creature_game.md) · [기획서 PPT](reference_design_doc_ppt.md) · [화면 정의서 PPT](reference_screen_definition_ppt.md)
- [출시 준비 상태](project_release_prep.md) — 블로커 해소, 릴리스 빌드 가능. ⚠️AAB 전 buildAppBundle 복원.
- [로그인 GPGS](project_login_gpgs.md) · [기능 추가 백로그](todo_feature_backlog.md) · [진위 검증 안 함](project_no_authenticity_verification.md)
- 식사 AI: [벤치+run7~9](feature_meal_ai_bench_s39.md)(run8 채택) · [v6 비음식](feature_meal_ai_v6_nonfood.md) · [v5 치킨](feature_meal_ai_v5_chicken.md) · [v4](feature_meal_ai_v4_nonfood.md) · [한식 4종](todo_korean_food_model.md) · [한식 143종](todo_extra_data_korean_boost.md) · [✅AI 하루](todo_ai_bench_and_data_day.md)
- 촬영/입력: [식사 사진→AI](project_meal_capture.md) · [갤러리](feature_meal_gallery_s37.md) · [수동 입력](feature_manual_diet_input_s37.md)
- 생물: [다종 시스템](feature_creature_species.md) · [성장·진화](feature_creature_evolution.md) · [해칠링 아트](feature_hatchling_art_s35.md) · [성장 아트](feature_stage1_art_s33.md) · [발/방향 기준](reference_creature_baseline.md) · [스프라이트 128 통일](reference_sprite_size_uniform.md) · [크리처 아트](reference_creature_art.md) · [도트화](reference_dot_art_conversion.md) · [✅자는 얼굴 수정](todo_evolved_sleep_face_fix.md)
- 농장: [배경](reference_farm_backgrounds.md) · [폴리시](project_farm_polish_s32.md) · [꾸미기](feature_farm_decorate.md) · [시너지 생태계](feature_synergy_ecosystem.md) · [날씨](feature_farm_weather.md) · [밤낮](feature_day_night_cycle.md) · [취침](feature_creature_sleep.md) · [사진 찍기](feature_farm_photo.md) · [디저트 시너지](feature_dessert_snow_synergy.md)
- 시스템: [경험치](feature_xp_growth_system.md) · [작별 선물](feature_release_gift.md) · [도전과제+리포트](feature_achievements_dietreport.md) · [4개 시스템 s20](feature_four_systems_s20.md) · [가이드북](feature_guidebook.md) · [✅가이드북 미기재](todo_guidebook_missing_pages.md)
- UI: [리디자인](project_ui_redesign.md) · [Z플립4 반응형](project_flip4_responsive_s31.md) · [실기기 버그픽스+정렬 규칙](project_device_bugfix_s26.md) · [팝업 드리프트 버그](reference_popup_drift_bug.md)
- 기타: [최적화 패스](project_optimization_pass.md) · [효과음](reference_audio_sfx.md) · [세션38 정리](project_session38_cleanup.md) · [세션35 수정](project_session35_fixes.md) · [세션33 수정](project_session33_fixes.md)

## 환경 · 도구 함정
- [APK 개발자 모드 선택](reference_apk_dev_mode_toggle.md) · [C 드라이브 공간](reference_disk_space.md)
- [MCP assets-refresh 스테일 컴파일](reference_mcp_stale_compile.md) · [에디터 멈춤=MCP 연결폭주](reference_unity_mcp_hang.md) · [터미널 튕김=conhost 크래시](reference_conhost_crash.md)
- [Gemini 웹 챗봇](project_gemini_chatbot.md)
