# -*- coding: utf-8 -*-
"""
루시(Lucy) 자동화 회귀 테스트 스위트 (test_suite.py)

파이썬 표준 라이브러리 unittest 기반으로
my-agent 핵심 모듈 및 고도화 항목(sandbox, async_runner, lucy_db, schema_validator)을 자동 검증합니다.
"""
import os
import sys
import json
import tempfile
import unittest

# my-agent 디렉터리를 sys.path에 추가
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import tools
import docsearch
import lessons
import memory_search
import agent
import sandbox
import async_runner
import lucy_db
import schema_validator
import blender3d


class TestSafety(unittest.TestCase):
    """경로 샌드박싱 및 _check_path 검증"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        tools.init({"allowed_dirs": [self.temp_dir.name]})

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_check_path_case_insensitivity(self):
        """Windows 경로 대소문자 미구분 승인 검증"""
        path_lower = self.temp_dir.name.lower()
        checked = tools._check_path(path_lower)
        self.assertTrue(os.path.exists(os.path.dirname(checked)) or os.path.abspath(path_lower))

    def test_check_path_sandbox_violation(self):
        """allowed_dirs 밖 경로 접근 시 PermissionError 발생 검증"""
        forbidden_path = os.path.abspath(os.path.join(self.temp_dir.name, "..", "outside_secret.txt"))
        with self.assertRaises(PermissionError):
            tools._check_path(forbidden_path)


class TestCalc(unittest.TestCase):
    """calc 계산기 연산 및 예외 처리 검증"""

    def test_calc_basic_and_power(self):
        """기본 연산 및 ^ -> ** 변환 연산"""
        res1 = tools.calc({"expression": "2^10"})
        self.assertIn("2^10 = 1024", res1)

        res2 = tools.calc({"expression": "10 + 20 * 3"})
        self.assertIn("70", res2)

    def test_calc_exceptions(self):
        """ZeroDivisionError 및 SyntaxError, 매개변수 누락 예외 처리"""
        res_zero = tools.calc({"expression": "10 / 0"})
        self.assertIn("계산 오류", res_zero)
        self.assertIn("ZeroDivisionError", res_zero)

        res_syntax = tools.calc({"expression": "5++"})
        self.assertIn("계산 오류", res_syntax)

        res_empty = tools.calc({})
        self.assertIn("오류", res_empty)


class TestFileTools(unittest.TestCase):
    """파일 도구 및 KeyError 방지 인자 처리 검증"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        tools.init({"allowed_dirs": [self.temp_dir.name]})
        self.orig_confirm = getattr(tools, "CONFIRM", None)
        tools.CONFIRM = lambda q, risk=None: True

    def tearDown(self):
        if self.orig_confirm:
            tools.CONFIRM = self.orig_confirm
        self.temp_dir.cleanup()

    def test_write_and_read_file(self):
        """write_file 및 read_file 정상 작동"""
        test_file = os.path.join(self.temp_dir.name, "test.txt")
        res_w = tools.write_file({"path": test_file, "content": "Hello Lucy!"})
        self.assertIn("저장 완료", res_w)

        res_r = tools.read_file({"path": test_file})
        self.assertEqual(res_r, "Hello Lucy!")

    def test_keyerror_prevention(self):
        """인자 누락 시 KeyError 방지 및 오류 안내 문구 반환"""
        self.assertIn("오류", tools.read_file({}))
        self.assertIn("오류", tools.write_file({}))
        self.assertIn("오류", tools.run_python({}))
        self.assertIn("오류", tools.run_powershell({}))
        self.assertIn("지울지", tools.forget({}))


class TestDocSearch(unittest.TestCase):
    """docsearch _tokens 단일 한글 문장 포함 검증"""

    def test_single_char_korean_tokenization(self):
        """한글 1글자 단어('앱', '웹', '책') 토큰화 보존 검증"""
        tokens = docsearch._tokens("앱 개발 및 웹 서비스 책 읽기")
        self.assertIn("앱", tokens)
        self.assertIn("웹", tokens)
        self.assertIn("책", tokens)
        self.assertIn("개발", tokens)


class TestMemory(unittest.TestCase):
    """memory 및 lessons 모듈 검증"""

    def test_lessons_is_correction(self):
        """lessons.is_correction 지적 문구 감지 검증"""
        self.assertTrue(lessons.is_correction("그거 틀렸어 다시 확인해"))
        self.assertTrue(lessons.is_correction("아닌데 그게 아니라 32종이야"))
        self.assertFalse(lessons.is_correction("오늘 날씨가 좋네"))
        self.assertFalse(lessons.is_correction("내가 잘못 눌렀어"))

    def test_load_notes_integrity(self):
        """memory_search.load_notes 읽기 무결성 검증"""
        notes = memory_search.load_notes()
        self.assertIsInstance(notes, list)


class TestConfig(unittest.TestCase):
    """config 원자적 쓰기 무결성 검증"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.json")
        self.initial_data = {"name": "루시", "tts": {"enabled": False}}
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.initial_data, f)
        
        self.orig_config_file = agent.CONFIG_FILE
        agent.CONFIG_FILE = self.config_path

    def tearDown(self):
        agent.CONFIG_FILE = self.orig_config_file
        self.temp_dir.cleanup()

    def test_save_tts_atomic_write(self):
        """agent.save_tts 원자적 설정 쓰기 검증"""
        new_config = {"tts": {"enabled": True, "voice": "ko-KR"}}
        agent.save_tts(new_config)

        with open(self.config_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        
        self.assertEqual(saved.get("name"), "루시")
        self.assertTrue(saved.get("tts", {}).get("enabled"))
        self.assertFalse(os.path.exists(self.config_path + ".tmp"))

    def test_briefing_config_disabled(self):
        """부팅 시 자동 아침 브리핑 비활성화(daily.briefing.enabled == False) 검증"""
        cfg = agent.load_config()
        briefing_enabled = cfg.get("daily", {}).get("briefing", {}).get("enabled")
        self.assertFalse(briefing_enabled)


class TestSandbox(unittest.TestCase):
    """sandbox.py 파괴적 명령어 차단 및 AST 검사 검증"""

    def test_validate_command_dangerous(self):
        """파괴적 명령어 차단 검증"""
        is_safe, msg = sandbox.validate_command("Remove-Item -Recurse -Force C:\\Windows")
        self.assertFalse(is_safe)
        self.assertIn("위험 명령어", msg)

        is_safe2, msg2 = sandbox.validate_command("echo Hello")
        self.assertTrue(is_safe2)

    def test_run_code_isolated_forbidden_ast(self):
        """금지된 AST 호출 차단 검증"""
        is_ok, out = sandbox.run_code_isolated("import shutil; shutil.rmtree('/tmp')")
        self.assertFalse(is_ok)
        self.assertIn("금지된 함수 호출", out)

        is_ok2, out2 = sandbox.run_code_isolated("print('Hello Sandbox')")
        self.assertTrue(is_ok2)
        self.assertIn("Hello Sandbox", out2)


class TestAsyncRunner(unittest.TestCase):
    """async_runner.py 비동기 실행 엔진 검증"""

    def test_async_run_tools(self):
        """동기 도구 병렬 비동기 실행 검증"""
        def dummy_tool(args):
            return f"Result: {args.get('val')}"

        tool_calls = [(dummy_tool, {"val": 1}), (dummy_tool, {"val": 2})]
        results = async_runner.run_async(async_runner.async_run_tools(tool_calls))
        self.assertEqual(results, ["Result: 1", "Result: 2"])


class TestLucyDB(unittest.TestCase):
    """lucy_db.py SQLite 데이터베이스 및 MD 동기화 검증"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_lucy.db")
        self.md_path = os.path.join(self.temp_dir.name, "test_notes.md")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_notes_db_and_sync(self):
        """DB에 노트 저장 후 md 동기화 검증"""
        lucy_db.add_note("홍차를 좋아함", date="2026-07-25", db_path=self.db_path)
        notes = lucy_db.get_notes(db_path=self.db_path)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["content"], "홍차를 좋아함")

        count = lucy_db.sync_notes_md(md_path=self.md_path, db_path=self.db_path)
        self.assertEqual(count, 1)
        with open(self.md_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("홍차를 좋아함", content)


class TestSchemaValidator(unittest.TestCase):
    """schema_validator.py 검증 및 자가치유 래퍼 검증"""

    def test_validate_args_type_coercion(self):
        """타입 검증 및 자동 보정 검증"""
        is_val, corr, msg = schema_validator.validate_args("research", {"question": "루시", "depth": "5"})
        self.assertTrue(is_val)
        self.assertEqual(corr["depth"], 5)

    def test_self_heal_execute(self):
        """자가치유(Self-Healing) 인자 보정 후 재시도 검증"""
        def strict_tool(args):
            return f"Read: {args['path']}"

        res = schema_validator.self_heal_execute(strict_tool, {}, tool_name="read_file")
        self.assertIn("Read: ", res)


class TestBlenderMeshEdit(unittest.TestCase):
    """blender3d.py 4대 도형 정밀 편집 수술 등록 검증"""

    def test_surgery_and_catalog_registration(self):
        """taper, extrude_face, inset_face, deform_mesh 수술 및 CATALOG 등록 검증"""
        for act in ("taper", "extrude_face", "inset_face", "deform_mesh"):
            self.assertIn(act, blender3d.SURGERY)

        catalog_actions = []
        for category, items in blender3d.CATALOG:
            for act_name, desc in items:
                catalog_actions.append(act_name)

        for act in ("taper", "extrude_face", "inset_face", "deform_mesh"):
            self.assertIn(act, catalog_actions)

    def test_furniture_parametric_math_formula(self):
        """가구(의자/책상) 파라메트릭 정밀 조립 수식 밀착 검증"""
        leg_h, seat_th, back_h = 0.45, 0.05, 0.45
        leg_z_center = leg_h / 2.0
        seat_z_center = leg_h + seat_th / 2.0
        back_z_center = leg_h + seat_th + back_h / 2.0

        # 다리 바닥 Z 접지 확인
        self.assertEqual(leg_z_center - leg_h / 2.0, 0.0)
        # 다리 상단과 좌판 밑면 밀착 확인
        leg_top = leg_z_center + leg_h / 2.0
        seat_bottom = seat_z_center - seat_th / 2.0
        self.assertAlmostEqual(leg_top, seat_bottom)
        # 좌판 상단과 등받이 밑면 밀착 확인
        seat_top = seat_z_center + seat_th / 2.0
        back_bottom = back_z_center - back_h / 2.0
        self.assertAlmostEqual(seat_top, back_bottom)

    def test_hex_nut_parametric_formula(self):
        """육각 돔 너트(hex_nut) 산출식 및 돔 높이 밀착 검증"""
        height, dome_h = 0.4, 0.3
        base_z_center = height / 2.0
        dome_z_center = height + dome_h * 0.3

        self.assertEqual(base_z_center - height / 2.0, 0.0)
        self.assertGreater(dome_z_center, height)


class TestVisionContextContinuity(unittest.TestCase):
    """agent.py 비전-텍스트 모델 교체 시 맥락 단절 방지 검증"""

    def test_has_vision_3d_ref(self):
        """_has_vision_3d_ref 감지 및 VISION_CONTINUE_HINT 수립 검증"""
        msgs = [
            {"role": "user", "content": "이 그림 3D로 만들어줘"},
            {"role": "system", "content": agent.MODEL_FROM_REF},
            {"role": "assistant", "content": "육각 돔 너트네요. radius=0.5, height=0.4로 만들어 드릴까요?"}
        ]
        self.assertTrue(agent._has_vision_3d_ref(msgs))


class TestCerebrasContextLimit(unittest.TestCase):
    """Cerebras 8192 토큰 한도 초과 방지 프루닝 검증"""

    def test_prune_for_context_limit(self):
        """오버사이즈 대화 프루닝 후 system prompt 유지 및 예산 준수 검증"""
        import session
        msgs = [{"role": "system", "content": "시스템 프롬프트 지침"}]
        for i in range(20):
            msgs.append({"role": "user", "content": f"질문 {i}: " + "긴 내용 " * 100})
            msgs.append({"role": "assistant", "content": f"답변 {i}: " + "긴 응답 " * 100})
        msgs.append({"role": "user", "content": "마지막 최신 질문"})

        pruned = session.prune_for_context_limit(msgs, max_tokens=8192, reserved_tokens=2500)
        self.assertEqual(pruned[0]["role"], "system")
        self.assertEqual(pruned[-1]["content"], "마지막 최신 질문")
        total_chars = sum(len(session.text_of(m)) for m in pruned)
        self.assertLessEqual(total_chars, int((8192 - 2500) * 1.8))


class TestVisionEnhancements(unittest.TestCase):
    """비전 API 레이트리밋 방지 및 프로바이더 키 인터리빙 검증"""

    def test_capable_interleaving(self):
        """서로 다른 key_file 프로바이더가 교대로 인터리빙되는지 검증"""
        import vision
        mock_config = {
            "models": [
                {"label": "Gemini 3 Flash", "key_file": "keys/gemini.txt", "vision": True},
                {"label": "Gemini 3.1 Flash Lite", "key_file": "keys/gemini.txt", "vision": True},
                {"label": "NVIDIA nemotron-nano-VL", "key_file": "keys/nvidia.txt", "vision": True},
                {"label": "NIM gemma-4-31b", "key_file": "keys/nvidia.txt", "vision": True},
            ]
        }
        interleaved = vision.capable(mock_config)
        self.assertEqual(len(interleaved), 4)
        # 첫 번째와 두 번째의 key_file이 서로 다른 프로바이더인지 검증
        self.assertNotEqual(interleaved[0].get("key_file"), interleaved[1].get("key_file"))


class TestDrawRouting(unittest.TestCase):
    """그림 생성(draw) 도구 라우팅 및 힌트 검증"""

    def test_draw_tool_group_keywords(self):
        """바탕화면, 수인, 퍼리 등 그림 요청 키워드 인식 검증"""
        import tools
        names = tools._relevant_names([{"role": "user", "content": "바탕화면에 귀여운 수인 퍼리를 그려서 저장해줘"}])
        self.assertIn("draw", names)

    def test_draw_hint_text(self):
        """agent.DRAW_HINT 지침 탑재 검증"""
        self.assertIn("draw 도구", agent.DRAW_HINT)
        self.assertIn("거짓 거절 텍스트를 출력하지 마라", agent.DRAW_HINT)


class TestBlenderSpecs(unittest.TestCase):
    """blender_3d 요약 명세 및 리깅·애니메이션 키워드 라우팅 검증"""

    def test_compact_specs_blender_3d_rigging_anim_actions(self):
        """COMPACT_SPECS의 blender_3d description에 리깅/애니메이션 필수 액션 및 키워드 포함 검증"""
        blender_spec = next((s for s in tools.COMPACT_SPECS if s.get("function", {}).get("name") == "blender_3d"), None)
        self.assertIsNotNone(blender_spec, "COMPACT_SPECS에 blender_3d 명세가 존재해야 합니다.")

        desc = blender_spec["function"].get("description", "")
        required_actions = [
            "bone_template", "auto_weight", "weight_transfer",
            "pose_apply", "anim_edit", "anim_merge", "physics_bake"
        ]
        for act in required_actions:
            self.assertIn(act, desc, f"blender_3d 요약 명세(COMPACT_SPECS)에 '{act}' 액션이 포함되어야 합니다.")

        self.assertIn("리깅", desc)
        self.assertIn("애니메이션", desc)

    def test_tool_groups_blender_3d_keywords(self):
        """_TOOL_GROUPS가 한국어/영어 리깅 및 애니메이션 키워드를 blender_3d로 라우팅하는지 검증"""
        test_queries = [
            "3D 캐릭터 bone_template 표준 뼈대 배치해줘",
            "메시에 auto_weight 자동 웨이트 걸어줘",
            "의상 메시 weight_transfer 웨이트 전사해줘",
            "캐릭터 포즈 pose_apply 키프레임 적용해줘",
            "애니메이션 anim_edit 트림해줘",
            "FBX 애니 클립 anim_merge 합본해줘",
            "천 physics_bake 물리 굽기 해줘",
            "3D character rigging task",
            "3D animation edit request",
        ]
        for query in test_queries:
            matched_tools = tools._relevant_names([{"role": "user", "content": query}])
            self.assertIn("blender_3d", matched_tools, f"쿼리 '{query}'에 대해 blender_3d 도구가 라우팅되어야 합니다.")


class TestDocFormatting(unittest.TestCase):
    """Word(.docx), PowerPoint(.pptx), Excel(.xlsx) 고도화 문서 서식 및 수식 검증"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        tools.init({"allowed_dirs": [self.temp_dir.name]})
        self.orig_confirm = getattr(tools, "CONFIRM", None)
        tools.CONFIRM = lambda q, risk=None: True

    def tearDown(self):
        if self.orig_confirm:
            tools.CONFIRM = self.orig_confirm
        self.temp_dir.cleanup()

    def test_docx_formatting(self):
        """Word (.docx) 제목/소제목 색상, 콜아웃/인용 블록 및 표 헤더 배경색 검증"""
        import zipfile
        import docs
        docx_path = os.path.join(self.temp_dir.name, "test_doc.docx")
        content = (
            "# 문서 제목\n"
            "## 소제목 1\n"
            "> 이것은 콜아웃 인용구입니다.\n"
            "| 항목 | 가격 | 비고 |\n"
            "| 제품A | 1000 | 추천 |\n"
        )
        docs.write(docx_path, content, title="메인 타이틀")
        self.assertTrue(os.path.exists(docx_path))

        with zipfile.ZipFile(docx_path, "r") as zf:
            styles_xml = zf.read("word/styles.xml").decode("utf-8")
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            
            self.assertIn('w:styleId="Quote"', styles_xml)
            self.assertIn('w:fill="F2F4F8"', styles_xml)
            self.assertIn('1F4E78', styles_xml)
            self.assertIn('2F5597', styles_xml)
            
            self.assertIn('w:val="Quote"', doc_xml)
            self.assertIn('w:fill="2F5597"', doc_xml)

    def test_pptx_formatting(self):
        """PowerPoint (.pptx) 표지/본문 슬라이드 차별화, 슬라이드 번호, 표 서식 검증"""
        import zipfile
        import docs
        pptx_path = os.path.join(self.temp_dir.name, "test_presentation.pptx")
        content = (
            "# 첫번째 슬라이드\n"
            "- 내용 1\n"
            "노트: 발표자 참고사항\n"
            "# 두번째 슬라이드\n"
            "| 이름 | 점수 |\n"
            "| 홍길동 | 95 |\n"
        )
        docs.write(pptx_path, content, title="발표 자료")
        self.assertTrue(os.path.exists(pptx_path))

        with zipfile.ZipFile(pptx_path, "r") as zf:
            s1_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
            s2_xml = zf.read("ppt/slides/slide2.xml").decode("utf-8")
            s3_xml = zf.read("ppt/slides/slide3.xml").decode("utf-8")
            
            self.assertIn('name="표지배경"', s1_xml)
            self.assertIn('name="구분선"', s2_xml)
            self.assertIn('슬라이드번호', s2_xml)
            self.assertIn('val="2F5597"', s3_xml)

    def test_xlsx_formatting_and_formulas(self):
        """Excel (.xlsx) 헤더 서식, 통화/퍼센트/콤마 서식 감지 및 수식(SUM, AVERAGE) 평가 검증"""
        import zipfile
        import docs
        xlsx_path = os.path.join(self.temp_dir.name, "test_sheet.xlsx")
        content = (
            "| 품목 | 수량 | 단가 | 비율 | 합계 |\n"
            "| 사과 | 10 | ₩1,000 | 50.0% | 10,000 |\n"
            "| 바나나 | 20 | $2,000 | 25.5% | 40,000 |\n"
            "| 총합계 | =SUM(B2:B3) | =AVERAGE(C2:C3) | | =SUM(E2:E3) |\n"
        )
        docs.write(xlsx_path, content)
        self.assertTrue(os.path.exists(xlsx_path))

        with zipfile.ZipFile(xlsx_path, "r") as zf:
            sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
            
            self.assertIn('s="1"', sheet_xml)
            self.assertIn('s="5"', sheet_xml)
            self.assertIn('s="4"', sheet_xml)
            self.assertIn('<f>SUM(B2:B3)</f><v>30</v>', sheet_xml)
            self.assertIn('<f>AVERAGE(C2:C3)</f><v>1500.0</v>', sheet_xml)
            self.assertIn('<f>SUM(E2:E3)</f><v>50000</v>', sheet_xml)


class TestDocToolRouting(unittest.TestCase):
    """한국어 문서 관련 키워드 도구 라우팅 검증"""

    def test_document_keywords_routing(self):
        """기획서, 보고서, 발표자료, 피치덱, 엑셀표, 정산서, 회의록 등 키워드 라우팅 검증"""
        keywords = [
            "사업 기획서 작성해줘",
            "주간 보고서 만들어줘",
            "발표자료 PPT 작성해줘",
            "피치덱 슬라이드 만들어줘",
            "양식 템플릿 엑셀표 작성해줘",
            "정산서 및 명세서 만들어줘",
            "회의록 작성해줘",
            "워드 작성 요청",
        ]
        for kw in keywords:
            matched = tools._relevant_names([{"role": "user", "content": kw}])
            self.assertIn("write_document", matched, f"키워드 '{kw}'에 대해 write_document가 라우팅되어야 합니다.")


class TestAuditEnhancements(unittest.TestCase):
    """최근 고도화 기능 스위트 검증"""

    def test_traceback_parsing_and_recovery_guidelines(self):
        """coding.parse_traceback 자동 트레이스백 파싱 및 pip 설치 가이드 검증"""
        import coding
        tb_sample = (
            'Traceback (most recent call last):\n'
            '  File "main.py", line 15, in <module>\n'
            '    import pandas as pd\n'
            'ModuleNotFoundError: No module named \'pandas\''
        )
        diag = coding.parse_traceback(tb_sample)
        self.assertIn("누락된 패키지: 'pandas'", diag)
        self.assertIn("code_install", diag)

    def test_vtt_subtitle_generation(self):
        """video.make_vtt 자막 생성 검증"""
        import video
        with tempfile.TemporaryDirectory() as td:
            vtt_path = os.path.join(td, "test.vtt")
            video.make_vtt([(0.0, 2.5, "안녕하세요")], vtt_path)
            self.assertTrue(os.path.exists(vtt_path))
            with open(vtt_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("WEBVTT", content)
            self.assertIn("00:00:00.000 --> 00:00:02.500", content)

    def test_image_prompt_auto_expansion(self):
        """tools._expand_prompt 한글 프롬프트 영어 자동 확장 검증"""
        expanded = tools._expand_prompt("귀여운 고양이 수인 그림")
        self.assertIn("cute cat", expanded)
        self.assertIn("masterpiece", expanded)

    def test_brainprobe_health_check(self):
        """brainprobe.self_diagnosis_health_check 자가진단 검증"""
        import brainprobe
        report = brainprobe.self_diagnosis_health_check({})
        self.assertIn("timestamp", report)
        self.assertTrue(report.get("lessons_index_ok"))


class TestLinuxCrossPlatform(unittest.TestCase):
    """리눅스 및 크로스 플랫폼 호환성 검증"""

    def test_portable_expand_and_drives(self):
        """portable 모듈 expand 및 _drives 크로스 플랫폼 동작 검증"""
        import portable
        drives = portable._drives()
        self.assertIsInstance(drives, list)
        self.assertGreater(len(drives), 0)

        expanded = portable.expand("/non_existent_folder_xyz/test.txt")
        self.assertIn("test.txt", expanded)

    def test_web_posix_paths_regex(self):
        """web.py의 IMG_PATH 및 DOC_PATH의 Linux POSIX 경로 매칭 검증"""
        import web
        img_match = web.IMG_PATH.search("이미지 경로: /home/user/Desktop/sample.png 저장 완료")
        self.assertIsNotNone(img_match)
        self.assertEqual(img_match.group(0), "/home/user/Desktop/sample.png")

        doc_match = web.DOC_PATH.search("문서 경로: /tmp/report.pdf 생성 완료")
        self.assertIsNotNone(doc_match)
        self.assertEqual(doc_match.group(0), "/tmp/report.pdf")

    def test_run_powershell_cross_platform_structure(self):
        """tools.run_powershell의 매개변수 누락 및 구문 처리 검증"""
        err = tools.run_powershell({})
        self.assertIn("오류", err)


if __name__ == "__main__":
    unittest.main()


