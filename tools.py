# -*- coding: utf-8 -*-
"""비서의 손발. 도구를 추가하려면 아래 TOOLS 딕셔너리에 함수 하나만 더 넣으면 됩니다."""
import ast
import datetime
import fnmatch
import shutil
import html
import json
import math
import operator
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from xml.etree import ElementTree

import coding
import docs
import knowledge
import reminders

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
NOTES_FILE = os.path.join(MEMORY_DIR, "notes.md")

_config = {}


def init(config):
    """agent.py가 시작할 때 설정을 넘겨줍니다."""
    global _config
    _config = config
    os.makedirs(MEMORY_DIR, exist_ok=True)


# ── 안전장치 ──────────────────────────────────────────────────────
def _check_path(path):
    """config의 allowed_dirs 밖은 건드리지 못하게 막습니다.
    allowed_dirs와 입력 경로의 ~·환경변수·다른 사용자 이름은 portable.expand가 지금 PC에
    맞게 풉니다 — 그래서 config에 "~"만 적어두면 어느 계정으로 옮겨도 홈이 허용됩니다."""
    import portable
    full = os.path.abspath(portable.expand(path))
    allowed = [os.path.abspath(portable.expand(d)) for d in _config.get("allowed_dirs", [])]
    norm_full = os.path.normcase(full)
    norm_allowed = [os.path.normcase(a) for a in allowed]
    if not any(os.path.commonpath([norm_full, a]) == a for a in norm_allowed):
        raise PermissionError(f"허용되지 않은 경로입니다: {full}")
    return full


def _ask_terminal(question):
    answer = input(f"\n  [확인] {question} [y/N] ").strip().lower()
    return answer == "y"


# 확인을 받는 방법은 화면마다 다릅니다. 터미널은 물어보면 되지만, 웹 화면에서는
# input()이 서버를 통째로 멈춰 세웁니다 → web.py가 이걸 갈아끼웁니다(거부).
CONFIRM = _ask_terminal

# 예약한 지시를 배경에서 수행할 때(사람이 화면 앞에 없을 때) 켜집니다.
# 물어볼 사람이 없으므로 미리 정한 선을 따릅니다:
#   · 파일·문서 쓰기 = 허용  — 사용자가 "문서로 만들어놔"라고 **지시할 때 이미 허락한 일**입니다.
#   · 코드·명령 실행 = 거부  — 지시문에 숨어든 위험한 코드를 아무도 못 보고 실행하게 둘 수는 없습니다.
# 이 구분이 없으면 둘 중 하나가 됩니다: 전부 막아서 예약 지시가 무용지물이 되거나,
# 전부 열어서 배경에서 임의 코드가 도는 물건이 되거나.
UNATTENDED = False


def _confirm(question, risk="write"):
    """위험한 동작(파일 쓰기·코드 실행) 전에 사람의 허락을 받습니다."""
    if UNATTENDED:
        allowed = (risk == "write")
        print(f"  [무인] {question} → {'허용(쓰기)' if allowed else '거부(실행은 배경에서 하지 않습니다)'}")
        return allowed
    return CONFIRM(question)


# ── 도구 구현 ─────────────────────────────────────────────────────
def now(_):
    t = datetime.datetime.now()
    return t.strftime("%Y년 %m월 %d일 %H:%M (%A)")


def read_file(args):
    path_arg = args.get("path")
    if not path_arg:
        return "오류: 'path' 매개변수가 필요합니다."
    path = _check_path(path_arg)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return text[:20000] if len(text) > 20000 else text


def write_file(args):
    path_arg = args.get("path")
    if not path_arg:
        return "오류: 'path' 매개변수가 필요합니다."
    if "content" not in args:
        return "오류: 'content' 매개변수가 필요합니다."
    path = _check_path(path_arg)
    content = args.get("content", "")
    exists = os.path.exists(path)
    verb = "덮어쓸까요" if exists else "새로 만들까요"
    if not _confirm(f"{path} 파일을 {verb}? ({len(content)}자)"):
        return "사용자가 거부했습니다. 파일을 쓰지 않았습니다."
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"저장 완료: {path}"


DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")


def _doc_path(raw):
    """
    저장 위치를 정합니다.

    모델은 "바탕화면에 만들어줘"라는 말을 듣고도 그냥 'report.docx'라고 넘기는 일이 잦습니다.
    그러면 현재 폴더(my-agent)에 떨어져서 사용자는 문서를 찾지 못하고, 루시는 바탕화면 경로를
    찾겠다며 list_dir("C:\\") 같은 헛걸음을 합니다(실제로 겪음).
    폴더를 안 적었으면 바탕화면에 둡니다 — 사람이 바로 볼 수 있는 곳이 기본값이어야 합니다.
    """
    raw = str(raw).strip().strip('"\'')
    if not os.path.dirname(raw):
        raw = os.path.join(DESKTOP, raw)
    return _check_path(raw)


def write_document(args):
    """
    워드·파워포인트·엑셀·한글 문서를 만듭니다(docs.py). read_document의 반대쪽 —
    읽기가 zip+xml만으로 됐듯 쓰기도 그렇습니다(설치할 것 없음. 한글도 마찬가지라
    한글이 안 깔린 PC에서도 .hwpx가 만들어집니다 — 세션65).
    """
    path_arg = args.get("path")
    if not path_arg:
        return "오류: 'path' 매개변수가 필요합니다."
    path = _doc_path(path_arg)
    content = args.get("content") or ""
    if not content.strip():
        return "오류: content(문서에 담을 내용)가 비어 있습니다."

    kind = os.path.splitext(path)[1].lower()
    exists = os.path.exists(path)
    verb = "덮어쓸까요" if exists else "새로 만들까요"
    if not _confirm(f"{path} 문서를 {verb}? ({len(content)}자)"):
        return "사용자가 거부했습니다. 문서를 만들지 않았습니다."

    try:
        made = docs.write(path, content, title=args.get("title"), sheet=args.get("sheet"))
    except ValueError as e:
        return f"오류: {e}"
    size = os.path.getsize(made) // 1024
    return (f"문서를 만들었습니다: {made} ({size}KB)\n"
            f"사용자에게 이 경로를 알려줘라. 형식: {kind}")


def edit_document(args):
    """
    이미 있는 워드·PPT 문서를 고칩니다(docs.edit). 새로 만들 때는 write_document —
    이 도구는 원본의 서식·표·그림을 살린 채 글자만 바꾸거나 끝에 덧붙입니다.
    """
    path = str(args.get("path") or "").strip().strip('"\'')
    find = str(args.get("find") or "")
    replace = str(args.get("replace") or "")
    append = str(args.get("append") or "")
    if not path:
        return "오류: path(고칠 문서 경로)가 필요합니다."
    if not find and not append.strip():
        return "오류: find(바꿀 문구)나 append(덧붙일 내용) 중 하나는 있어야 합니다."

    if not os.path.isfile(path):
        # 파일명만 말했으면 흔한 곳에서 찾아봅니다(transcribe_audio와 같은 예의)
        base = os.path.basename(path)
        for root in (DESKTOP,
                     os.path.join(os.path.expanduser("~"), "Documents"),
                     os.path.join(os.path.expanduser("~"), "Downloads"),
                     os.path.join(BASE_DIR, "uploads")):
            cand = os.path.join(root, base)
            if os.path.isfile(cand):
                path = cand
                break
        else:
            return (f"문서를 찾지 못했습니다: {path} "
                    "(경로를 모르면 search_files로 먼저 찾고, 없는 문서면 write_document로 새로 만드세요)")
    path = _check_path(path)

    # 먼저 몇 군데가 바뀔지 세봅니다 — 사용자에게 '무엇을 얼마나'를 보여주고 허락을 받습니다.
    try:
        peek = docs.edit(path, find=find, replace=replace, dry=True) if find else {"replaced": 0, "skipped": 0}
    except (ValueError, OSError, zipfile.BadZipFile) as e:
        return f"오류: {e}"
    if find and not peek["replaced"] and not append.strip():
        why = ("수식·형식 보호로 건너뛴 셀" if path.lower().endswith(".xlsx")
               else "그림·링크가 든 문단")
        hint = f" ({why} {peek['skipped']}곳)" if peek["skipped"] else ""
        return (f"'{find}'를 문서에서 찾지 못했습니다{hint}. "
                "read_document로 실제 문구를 확인하고 그대로 다시 넣어보세요."
                + (" 숫자 셀은 값 전체가 정확히 같아야 바뀝니다."
                   if path.lower().endswith(".xlsx") else ""))

    jobs = []
    if find and peek["replaced"]:
        jobs.append(f"'{find}' → '{replace}' {peek['replaced']}군데")
    if append.strip():
        jobs.append("끝에 새 슬라이드 추가" if path.lower().endswith(".pptx")
                    else f"끝에 {len(append)}자 덧붙임")
    if not _confirm(f"{path} 문서를 고칠까요? ({', '.join(jobs)}) — 고치기 전 원본은 자동 백업됩니다"):
        return "사용자가 거부했습니다. 문서를 고치지 않았습니다."

    try:
        done = docs.edit(path, find=find, replace=replace, append=append)
    except Exception as e:
        return f"문서를 고치지 못했습니다: {type(e).__name__}: {e} (원본은 그대로입니다)"

    # 되읽어 확인합니다 — "고쳤습니다"는 파일이 증명해야 합니다.
    try:
        low = path.lower()
        with zipfile.ZipFile(path) as zf:
            if low.endswith(".docx"):
                text = _read_docx(zf)
            elif low.endswith(".xlsx"):
                text = _read_xlsx(zf)
            else:
                text = _read_pptx(zf)
    except Exception:
        text = None
    msg = f"고쳤습니다: {path} ({', '.join(jobs)})"
    if text is not None:
        if replace.strip() and replace not in text:
            msg += "\n⚠ 되읽기에서 바꾼 문구가 보이지 않습니다 — read_document로 직접 확인해 보세요."
        if find and not done["skipped"] and find in text and find not in replace:
            msg += f"\n⚠ '{find}'가 아직 문서에 남아 있습니다 — read_document로 확인해 보세요."
    if done.get("slides_added"):
        msg += f"\n슬라이드 {done['slides_added']}장을 덱 끝에 추가했습니다."
    if done.get("skipped"):
        msg += f"\n그림·링크가 든 문단 {done['skipped']}곳은 서식 보호를 위해 건너뛰었습니다."
    if done.get("backup"):
        msg += f"\n원본 백업: {done['backup']}"
    return msg


def _find_media(path, exts=()):
    """전체 경로가 아니면 흔한 곳에서 찾아봅니다(동영상은 Videos 폴더까지)."""
    path = str(path or "").strip().strip('"\'')
    if os.path.isfile(path):
        return path
    base = os.path.basename(path)
    for root in (DESKTOP,
                 os.path.join(os.path.expanduser("~"), "Videos"),
                 os.path.join(os.path.expanduser("~"), "Downloads"),
                 os.path.join(os.path.expanduser("~"), "Documents"),
                 os.path.join(BASE_DIR, "uploads")):
        cand = os.path.join(root, base)
        if os.path.isfile(cand):
            return cand
    return None


# 수술별 자가검수 체크포인트 — 눈 달린 두뇌에게 "이것만" 판정시킵니다(미적 평가 금지).
# 루시 판단력의 1층: 미리보기를 찍기만 하던 것을 스스로 보고 명백한 실패를 잡게(세션63 2부).
_EYE_POINTS = {
    "physics_bake": "물체들이 바닥이나 다른 물체 위에 놓여 있는가(허공에 떠 있지 않은가)?",
    # cloth는 모서리가 허공에 늘어지는 게 정상 — 오탐 실측(세션63 2부)으로 별도 문구.
    "physics_bake_cloth": "천이 받침을 덮고 있는가? 천 모서리·자락이 옆으로 늘어져 허공에 있는 것과 "
                          "주름이 지는 것은 정상이다. 천이 통째로 허공에 떠 있거나 받침을 지나쳐 "
                          "바닥까지 완전히 떨어진 경우에만 문제로 판정하라.",
    "align": "위에서 내려본 그림이다. 오브젝트들이 정렬돼 있는가? 여러 개가 완전히 한 자리에 "
             "포개져 있을 때만 문제로 판정하라(원근상 일부 맞닿아 보이는 것은 정상).",
    "array": "위에서 내려본 그림이다. 복제본들이 간격을 두고 배열됐는가? 전부 한 점에 뭉쳐 "
             "있을 때만 문제로 판정하라.",
    "scatter": "위에서 내려본 그림이다. 뿌린 것들이 영역에 흩어져 있는가? 전부 한 점에 뭉쳐 "
               "있을 때만 문제로 판정하라.",
    "mirror": "대칭 결과가 한 몸으로 이어져 보이는가(반쪽이 어긋나거나 떨어져 있지 않은가)?",
    "boolean": "뚫기/합치기 자리가 보이는가(모델이 통째로 사라지거나 깨지지 않았는가)?",
    "pose_apply": "모델이 부러지거나 심하게 꼬인 곳 없이 포즈를 취했는가?",
    "join": "모델이 온전한가(부품이 사라지지 않았는가)?",
    "split": "모델이 온전한가(조각이 사라지거나 어긋나지 않았는가)?",
    "curve_path": "경로를 따라 형태가 이어져 보이는가(끊기거나 뭉치지 않았는가)?",
    "build": "부품들이 스펙대로 조립돼 보이는가(한 점에 뭉치거나 소실되지 않았는가)?",
    # 요철은 '변한 것'이 정답 — 매끈하면 실패, 형태가 뭉개져도 실패(양쪽 다 물음).
    "sculpt_displace": "표면에 요철·주름이 생겼는가? 반대로 원래 형태를 알아볼 수 없을 만큼 "
                       "뭉개지거나 가시처럼 삐죽삐죽해지지는 않았는가?",
    "assemble": "배치된 것들이 각자 자리에 있는가(한 점에 뭉치거나 소실되지 않았는가)?",
}
_EYE_DEFAULT = "명백한 파손이 보이는가(구멍·검게 뒤집힌 면·부품 겹침·소실)?"


# 모바일 3D 에셋 예산 기본값 — 판단력 2층: 수치를 기준과 대조해 경고(세션63 3부).
# 근거·예외는 knowledge/blender_모바일_기준표.md(유일 원본). config blender.budgets로 덮어씀.
_BUDGETS = {
    "prop_tris": 5000,        # 소품(비리깅) 삼각형 상한
    "char_tris": 30000,       # 캐릭터(리깅) 삼각형 상한
    "materials": 8,           # 파일 전체 재질 수(드로우콜 신호)
    "bones": 75,              # 본 수(모바일 스키닝 상한 신호)
}


def _budget(key):
    v = _config.get("blender", {}).get("budgets", {}).get(key)
    return int(v) if v else _BUDGETS[key]


def _budget_notes_info(r):
    """info 결과 수치를 모바일 예산과 대조 — 넘은 것만 경고 줄로. 판단이 아니라 자 대기."""
    L = []
    tris = r.get("total_tris")
    if tris:
        is_char = bool(r.get("bones"))            # 뼈대가 있으면 캐릭터 기준, 없으면 소품 기준
        cap = _budget("char_tris" if is_char else "prop_tris")
        kind = "캐릭터" if is_char else "소품"
        if tris > cap:
            L.append(f"  📏 삼각형 {tris:,} — 모바일 {kind} 기준({cap:,})의 {tris / cap:.1f}배, "
                     "decimate/lod 권장")
    mats = len(r.get("materials", []))
    if mats > _budget("materials"):
        L.append(f"  📏 재질 {mats}종 — 기준({_budget('materials')}종) 초과, "
                 "materials(병합)/uv_atlas 권장(드로우콜)")
    if r.get("bones") and r["bones"] > _budget("bones"):
        L.append(f"  📏 본 {r['bones']}개 — 모바일 기준({_budget('bones')}개) 초과")
    return ("\n" + "\n".join(L)) if L else ""


def _budget_note_polys(faces):
    """수술 결과의 면 수를 예산과 대조(면→삼각형은 약 2배 추정 — 정밀값은 info로)."""
    if not faces:
        return ""
    est = faces * 2
    cap = _budget("prop_tris")
    if est > cap:
        return (f"\n  📏 약 {est:,} tri 추정({faces:,}면) — 모바일 소품 기준({cap:,}) 초과, "
                "decimate 권장(리깅 캐릭터라면 기준 " + f"{_budget('char_tris'):,})")
    return ""


# ── 👁 자가검수: 눈 2개에게 묻고 엇갈리면 사람에게 (세션64) ─────────
# 세션64 눈 신뢰도 시험에서 등록된 눈이 **검은 화면을 '정상'이라 답하는 것**을 실측했습니다.
# 눈 하나의 "정상"은 통과 증거가 못 됩니다. 그래서 **서로 다른 두 눈**에게 묻고:
#   · 둘 다 정상 → 정상(합의)          · 둘 다 문제 → 문제(합의, 신뢰도 높음)
#   · 엇갈림     → **판정하지 않고 사람에게 넘깁니다**(🙋). 기계가 어림짐작으로 한쪽을
#                  고르면, 애초에 눈 하나만 쓰던 때와 똑같은 위험으로 되돌아갑니다.
# 눈이 하나뿐이거나 둘째 눈이 한도에 걸리면 단독 판정으로 두되 **혼자 본 판정임을 밝힙니다**.
def _verdict_of(text):
    """모델 답에서 판정만 뽑습니다('정상'·'문제'·None). eyecheck._verdict와 같은 방침."""
    t = (text or "").strip().replace("\n", " ")
    if not t:
        return None
    head = t[:40]
    if "문제" in head or "이상" in head:
        return "문제"
    if "정상" in head:
        return "정상"
    return "문제" if "문제" in t else ("정상" if "정상" in t else None)


def _eye_want():
    """이번 검수에 물어볼 눈의 수. `vision.eyes`(기본 3), `two_eyes:false`면 1."""
    v = _config.get("vision", {}) or {}
    if not v.get("two_eyes", True):
        return 1
    try:
        return max(1, int(v.get("eyes", 3)))
    except (TypeError, ValueError):
        return 3


def _eye_panel(eyes):
    """물어볼 눈의 순서 — **판정권이 있는 눈**(강등되지 않은 눈)을 앞에, 강등된 눈은 맨 뒤.

    ⭐사용자 결정(2026-07-23): 믿는 눈 여러 개의 **다수결**로 판정하고, 강등된 눈은
      명단에 남기되 **판정권을 주지 않습니다**.
      예전에는 '가장 믿는 눈 + 가장 못 믿는 눈'을 일부러 짝지어 이견을 끌어냈습니다. 그
      취지는 옳았지만(비슷한 두 눈은 같이 틀려서 조용히 통과함), 그 자리의 눈이 5문제 중
      **놓침 2·오탐 1**까지 나빠지자 검수 2건 중 1건이 🙋 사람에게 올라와(엇갈림 50% 실측)
      자동 검수의 뜻이 옅어졌습니다. 이견은 **믿는 눈들 사이에서** 갈릴 때 받는 편이 낫습니다.
    ⚠️강등된 눈도 명단에서 빼지 않습니다 — 판정권 있는 눈이 전부 한도에 걸렸을 때는
      답이 있는 편이 없는 편보다 낫습니다(그때는 '혼자 본 판정'으로 표시됩니다).
    """
    try:
        import eyecheck
        grade = eyecheck.load()
    except Exception:
        grade = {}
    ok = [e for e in eyes if grade.get(e.get("label")) != "demoted"]
    benched = [e for e in eyes if grade.get(e.get("label")) == "demoted"]
    return ok + benched          # vision.capable이 이미 믿는 눈부터 정렬해 줍니다


def _eye_tally(seen):
    """판정들을 모아 다수결. 돌려주기: (결정된 판정 or None, 대표 답글, 라벨들).
    과반이 없으면(1:1, 1:1:1 …) None — 기계가 어림짐작으로 고르지 않고 사람에게 넘깁니다."""
    votes = {}
    for got, text, label in seen:
        votes.setdefault(got, []).append((text, label))
    top = max(votes, key=lambda k: len(votes[k]))
    labels = [l for _t, l in votes[top]]
    if len(votes[top]) * 2 <= len(seen):          # 과반이 아니면 판정하지 않습니다
        return None, "", labels
    # '문제'로 모이면 이유가 있는 답글을, '정상'이면 그냥 정상.
    text = votes[top][0][0] if top == "문제" else "정상"
    return top, text, labels


def _ask_eye(entry, question, image_paths):
    """눈 하나에게 묻습니다. (판정, 답글, 라벨) — 실패면 (None, "", 라벨)."""
    import agent
    import vision
    try:
        msg = vision.user_message(question, list(image_paths))
        answer, label, _e = agent.call_model(_config, [msg], use_tools=False, order=[entry])
        text = (answer.get("content") or "").strip().replace("\n", " ")
        return _verdict_of(text), text, label
    except Exception:
        return None, "", entry.get("label", "?")


def _eye_look(intro, checkpoint, image_path, gate_key="blender"):
    """그림 한 장을 **눈 두 개**에게 보여 판정을 받습니다(판단력 1층 공용).
    어떤 실패도 본 작업 결과를 가리면 안 됩니다 — 못 보면 못 봤다고 한 줄 남기고 끝."""
    try:
        if not _config.get(gate_key, {}).get("eye_check", True):
            return ""
        if not (image_path and os.path.isfile(image_path)):
            return ""
        import vision
        # ⭐먼저 기계에게 묻습니다 — 검은 화면·단색·마젠타 범벅은 픽셀만 세면 틀릴 수가 없고,
        #   눈 두뇌는 이런 것도 '정상'이라 답한 전력이 있습니다(세션64 nemotron 마젠타 실측).
        #   확실한 것은 여기서 끝내고, 애매한 것만 눈에게 넘깁니다.
        mv, why = vision.machine_verdict(image_path, context=gate_key)
        if mv:
            return f"\n  · 🔧 기계 판정: **문제** — {why}\n      · 그림: {image_path}"
        eyes = _eye_panel(vision.capable(_config))   # 판정권 있는 눈부터
        if not eyes:
            return "\n  · 👁 자가검수 생략 — 눈 달린 두뇌가 없습니다(그림을 직접 확인하세요)"
        q = (intro + " 다음만 판정하세요: " + checkpoint
             + " 첫 단어를 '정상' 또는 '문제:'로 시작해 한두 문장으로만 답하세요.")
        want = _eye_want()

        seen = []                               # [(판정, 답글, 라벨)] — 답한 눈만
        for entry in eyes:
            if len(seen) >= want:
                break
            got, text, label = _ask_eye(entry, q, [image_path])
            if got:                             # 실패·빈답은 '다음 눈'으로(한도 등)
                seen.append((got, text, label))
        if not seen:
            return "\n  · 👁 자가검수 못 함(눈이 답하지 않음) — 그림을 직접 확인하세요"

        if len(seen) == 1:
            got, text, label = seen[0]
            solo = " ⚠혼자 본 판정입니다(다른 눈이 답하지 못함) — 정상이라도 그림을 한 번 보세요"
            return f"\n  · 👁 자가검수({label}): {text[:200]}{solo}"

        verdict, text, winners = _eye_tally(seen)
        who = "+".join(l for _v, _t, l in seen)
        try:                                    # 조합별 합의/엇갈림 세기(🙋 빈도 관찰용)
            import status
            status.record_panel([l for _v, _t, l in seen], verdict is not None)
        except Exception:
            pass
        if verdict:
            agreed = len(winners)
            tag = "만장일치" if agreed == len(seen) else f"다수결 {agreed}/{len(seen)}"
            return f"\n  · 👁 자가검수(눈 {len(seen)}개 {tag} · {who}): {str(text)[:200]}"
        # ⭐과반이 없음 — 기계가 어림짐작으로 고르지 않고 사람에게 넘깁니다
        detail = "".join(f"\n      · {l}: {t[:120]}" for _v, t, l in seen)
        return ("\n  · 🙋 **눈 판정에 과반이 없습니다 — 사람이 직접 확인해 주세요**"
                + detail + f"\n      · 그림: {image_path}")
    except Exception as e:
        return f"\n  · 👁 자가검수 못 함({type(e).__name__}) — 그림을 직접 확인하세요"


def _eye_look_many(intro, checkpoint, items, gate_key="unity"):
    """그림 여러 장을 **한 턴**에 보여 장별 판정 — 무료 눈 한도 절약(씬 7개=호출 7→2회).
    items=[(이름, 경로)…] 최대 3장/턴(Groq 눈이 3장 상한 — 400 실측). 돌려주기:
    (두뇌 라벨, {이름: 판정문}) — 실패면 (None, {}).
    ⚠️여기엔 🔧기계 판정 관문이 없습니다 — 지금 유일한 호출부(unity_shot)가 부르기 **전에**
      vision.machine_verdict로 걸러 보내기 때문입니다(마젠타 범벅·검은 화면은 눈에게 안 물음).
      새 호출부를 만들면 그쪽에서도 반드시 먼저 거를 것. 단독 그림은 _eye_look이 알아서 겁니다."""
    try:
        if not _config.get(gate_key, {}).get("eye_check", True):
            return None, {}
        items = [(n, p) for n, p in items if p and os.path.isfile(p)][:3]
        if not items:
            return None, {}
        import vision
        eyes = _eye_panel(vision.capable(_config))   # 판정권 있는 눈부터
        if not eyes:
            return None, {}
        names = [n for n, _ in items]
        q = (intro + f" 그림 {len(items)}장이 순서대로 실려 있다: "
             + ", ".join(f"{i + 1}번={n}" for i, n in enumerate(names))
             + ". 각 그림마다 다음만 판정하라: " + checkpoint
             + " 답은 그림마다 정확히 한 줄, '이름: 정상' 또는 '이름: 문제: 이유' 형식으로만.")
        import agent
        paths = [p for _, p in items]

        def _one_pass(entry):
            """눈 하나에게 묶음으로 묻고 {이름: 판정문}을 뽑습니다. 실패면 (라벨, {})."""
            try:
                msg = vision.user_message(q, paths)
                answer, label, _e = agent.call_model(_config, [msg], use_tools=False,
                                                     order=[entry])
            except Exception:
                return entry.get("label", "?"), {}
            got = {}
            # 모델마다 형식이 제멋대로라('1: Intro, 정상 = …' 실측) 엄격 파싱 대신
            # 줄 안에 이름이 있으면 '문제/정상' 낱말로 판정을 뽑습니다.
            # ⚠️이름 대신 **'1번:'·'2.'처럼 번호로 답하는 두뇌가 많습니다**(세션64 실측:
            #   Groq·nemotron 둘 다 번호로 답해 판정이 통째로 버려지고 있었음) — 번호도 받습니다.
            for line in (answer.get("content") or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                hit = next((n for n in names if n.lower() in line.lower()), None)
                if hit is None:
                    m = re.match(r"^\**\s*(\d+)\s*(?:번|\.|:|\))", line)
                    if m and 1 <= int(m.group(1)) <= len(names):
                        hit = names[int(m.group(1)) - 1]
                if hit is None:
                    continue
                if "문제" in line:
                    got.setdefault(hit, line[line.index("문제"):][:180])
                elif "정상" in line:
                    got.setdefault(hit, "정상")
            return label, got

        want = _eye_want()
        passes = []                              # [(라벨, {이름: 판정문})] — 답한 눈만
        for entry in eyes:
            if len(passes) >= want:
                break
            label, got = _one_pass(entry)
            if got:
                passes.append((label, got))
        if not passes:
            return None, {}
        if len(passes) == 1:
            label, got = passes[0]
            return label, got                    # 혼자 본 판정 — 부른 쪽이 라벨로 표시

        out = {}
        # 장별로 다수결. 어떤 장에 대해 한 눈만 답했으면 그 판정을 쓰되 혼자 본 것으로 둡니다
        # (묶음 답은 모델이 한두 장을 통째로 빠뜨리는 일이 잦습니다).
        for n in names:
            said = [(label, got[n]) for label, got in passes if got.get(n)]
            if not said:
                continue
            if len(said) == 1:
                out[n] = said[0][1]
                continue
            seen = [("정상" if t == "정상" else "문제", t, l) for l, t in said]
            verdict, text, winners = _eye_tally(seen)
            try:                                 # 장별 합의/엇갈림 세기(🙋 빈도 관찰용)
                import status
                status.record_panel([l for _v, _t, l in seen], verdict is not None)
            except Exception:
                pass
            if verdict:
                out[n] = text
            else:                                # ⭐과반 없음 → 사람에게
                out[n] = ("🙋 눈 판정에 과반 없음 — 사람이 직접 확인 필요 ("
                          + " / ".join(f"{l}: {str(t)[:50]}" for _v, t, l in seen) + ")")
        return "+".join(l for l, _g in passes), out
    except Exception:
        return None, {}


def _blender_eye(action, preview_path, point=None):
    return _eye_look(
        "블렌더에서 '" + action + "' 작업 직후 자동으로 찍은 점검용 미리보기입니다"
        "(회색 재질·단순 조명 — 미적 평가는 하지 마세요).",
        point or _EYE_POINTS.get(action, _EYE_DEFAULT), preview_path, gate_key="blender")


# 만들기(build·assemble·sculpt_displace) 결과가 **무엇으로 보이는지** 묻는 검수 — 세션67.
# ⭐왜 따로 있나: 기존 _blender_eye는 '파손'만 묻습니다("부품이 뭉치거나 소실됐는가?").
#   토마호크 스테이크를 시켰더니 큐브 40개를 쌓아 **망치**가 나왔는데, 부품은 멀쩡히 다
#   제자리에 있었으므로 눈은 '정상'을 냈습니다 — 파손 검사는 닮음을 못 잡습니다.
#   그래서 정답을 알려주지 않고 열린 질문으로 **먼저 말하게 한 뒤** 대조합니다
#   (무엇인지 알려주고 물으면 눈이 그냥 동의해 버림 — 유도신문 방지).
def _blender_eye_recognize(subject, preview_path):
    if not subject:
        return ""
    # 라벨을 '👁 자가검수'와 다르게 붙입니다 — 파손검수 줄과 나란히 나오면 구분이 안 됨(실측).
    got = _eye_look(
        "3D 모델을 회색 재질·단순 조명으로 찍은 렌더입니다. 질감·색·조명은 아직 없으니 "
        "**형태(실루엣)만** 보고 답하세요.",
        "이 물체는 무엇으로 보입니까? 가장 그럴듯한 이름 하나를 먼저 대고, 그 다음 줄에 "
        f"'{subject}'로 보이면 '정상', 전혀 다른 것으로 보이면 '문제: (보이는 것)'라고 "
        "적으세요. 디테일이 거칠거나 단순한 것은 문제가 아닙니다 — 아예 **다른 물건으로 "
        "보일 때만** 문제로 판정하세요.",
        preview_path, gate_key="blender")
    return got.replace("👁 자가검수", f"🪞 닮음검수('{subject}')", 1)


def _subject_of(args, dest):
    """'무엇을 만드는 것인가'를 뽑습니다 — subject 인자가 우선, 없으면 파일 이름에서.
    (작은 두뇌가 subject를 자주 빠뜨려서 파일명 폴백이 실질 기본값입니다.)"""
    s = str(args.get("subject") or "").strip()
    if s:
        return s[:40]
    stem = os.path.splitext(os.path.basename(str(dest or "")))[0]
    # 'tomahawk_highpoly' → 'tomahawk' / '감시탑_v2' → '감시탑' 처럼 군더더기를 떨궈냅니다.
    stem = re.sub(r"[_\-\s]*(highpoly|lowpoly|high|low|final|test|temp|wip|"
                  r"v\d+|\d{6}|수정\d*|사본)$", "", stem, flags=re.I).strip("_- ")
    return stem[:40] if len(stem) >= 2 else ""


# 전/후 비교가 판정에 도움 되는(형태가 눈에 띄게 변하는) 수술들 — 세션63 6부.
# 배치류(align·array·scatter)는 후 미리보기가 부감이라 앵글이 달라 비교 불성립 → 제외.
_COMPARE_ACTIONS = ("boolean", "repair", "decimate", "bevel", "solidify", "mirror",
                    "curve_path", "physics_bake", "pose_apply", "join", "split",
                    "scale_to", "normals", "shade", "sculpt_displace")


# 전/후 비교 때 눈에게 미리 일러둘 '정상인 변화'들 — 불리언 도구 소멸을 파손으로 오판한 실측.
_COMPARE_NOTES = {
    "boolean": "불리언의 도구 오브젝트가 오른쪽에서 사라진 것은 정상이다(뚫고 나서 치워짐).",
    "join": "여러 조각이 하나로 합쳐 보이는 것이 의도다.",
    "split": "한 덩어리가 여러 조각으로 나뉘어 보이는 것이 의도다.",
    "decimate": "면이 다소 각져 보이는 것은 감폴리의 정상 결과다.",
    "sculpt_displace": "오른쪽 표면이 거칠어진 것이 의도다 — 매끈한 채 그대로면 실패다.",
}


def _gif_strip(gif_path, folder, stem):
    """GIF에서 고르게 4프레임을 뽑아 가로로 붙인 그림 경로. 실패하면 None."""
    try:
        from PIL import Image, ImageSequence
        im = Image.open(gif_path)
        frames = [f.convert("RGB") for f in ImageSequence.Iterator(im)]
        if len(frames) < 2:
            return None
        picks = [frames[round(i * (len(frames) - 1) / 3)] for i in range(4)]
        w, h = picks[0].size
        canvas = Image.new("RGB", (w * 4 + 15, h), (30, 30, 30))
        for i, f in enumerate(picks):
            canvas.paste(f, (i * (w + 5), 0))
        dest = os.path.join(folder, stem + "_프레임띠.png")
        canvas.save(dest)
        return dest
    except Exception:
        return None


def _blender_before_after(orig_path, after_png, folder, stem):
    """원본을 한 컷 렌더해 후 미리보기와 좌우로 붙인 '전후' 그림 경로. 실패하면 None.
    앵글은 후 미리보기(쿼터 40°)와 맞추기 위해 렌더 2컷 중 quarter를 씁니다."""
    try:
        import blender3d
        rv = blender3d.run("render", orig_path, _config, out_dir=folder,
                           stem=stem + "_전", angles=2, size=512)
        rends = rv.get("renders") or []
        before = rends[1] if len(rends) > 1 else (rends[0] if rends else None)
        if not (before and os.path.isfile(before) and os.path.isfile(after_png)):
            return None
        from PIL import Image
        a = Image.open(before).convert("RGB").resize((512, 512))
        b = Image.open(after_png).convert("RGB").resize((512, 512))
        canvas = Image.new("RGB", (1029, 512), (30, 30, 30))
        canvas.paste(a, (0, 0))
        canvas.paste(b, (517, 0))
        dest = os.path.join(folder, stem + "_전후.png")
        canvas.save(dest)
        for f in rends:                            # 낱장은 합성본에 담겼으니 치움
            try:
                os.remove(f)
            except OSError:
                pass
        return dest
    except Exception:
        return None


def blender_3d(args):
    """
    블렌더 3D 파일 다루기(blender3d.py가 블렌더를 부림). 원본 .blend는 절대 안 고칩니다.
    info·render·export는 읽기만. 수술(apply·origin·scale_to·cleanup·uv·decimate·join)은
    원본을 복사한 **사본**에서만 하고, convert는 다른 형식 파일을 새 파일로 바꿉니다.
    """
    import blender3d

    action = str(args.get("action") or "").strip().lower()
    _ALL = ("info", "render", "export", "convert", "prep_unity", "unity_export",
            "check", "chain", "anim_preview", "lod", "build", "assemble",
            "text3d", "compare", "anim_merge", "bake", "beauty_render",
            "help") + blender3d.SURGERY
    if action not in _ALL:
        return "action은 " + ", ".join(_ALL) + " 중 하나여야 합니다."

    # help — 블렌더를 켜지 않고 기능 목록만 돌려줍니다(파일도 확인도 불필요).
    # ⭐"이 기능이 있나?"를 회상으로 답하지 말고 이걸로 조회할 것(세션67: bake·uv_atlas가
    #   있는데 "없다"고 답한 실측 때문에 생긴 동작).
    if action == "help":
        return blender3d.catalog_text()

    def _json_arg(v):
        """작은 두뇌가 배열을 JSON 문자열로 줄 때가 있어 — 문자열이면 풀어준다."""
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                return None
        return v if isinstance(v, list) else None

    def _new_path(raw, ext=".blend"):
        """새로 만들 파일의 자리 — 폴더를 안 주면 바탕화면, 확장자를 안 주면 붙여준다."""
        raw = str(raw or "").strip().strip('"\'')
        if not raw:
            return None
        if not os.path.splitext(raw)[1]:
            raw += ext
        if not os.path.dirname(raw):
            raw = os.path.join(DESKTOP, raw)
        if os.path.exists(raw):
            stem0, e0 = os.path.splitext(raw)
            raw = f"{stem0}_{time.strftime('%H%M%S')}{e0}"
        return raw

    if action == "build":                        # 치수 스펙 → 프리미티브 조립(그레이박스) 새 .blend
        parts = _json_arg(args.get("parts"))
        if not parts or not all(isinstance(p, dict) for p in parts):
            return ("build는 parts에 부품 목록이 필요합니다. 예: parts=[{\"shape\":\"cube\","
                    "\"name\":\"벽\",\"size\":[4,0.2,2.5],\"pos\":[0,2,1.25],\"color\":[0.7,0.7,0.75]}] "
                    "(shape는 cube·cylinder·sphere·cone·torus·plane, size/pos 단위는 미터, "
                    "rot_deg는 도 단위 회전)")
        dest = _new_path(args.get("path"))
        if not dest:
            return "build는 path에 만들 파일 이름이 필요합니다(예: 감시탑.blend — 폴더 없으면 바탕화면)."
        if not _confirm(f"부품 {len(parts)}개로 '{os.path.basename(dest)}'를 조립할까요? "
                        "(새 파일만 만들고 미리보기 2장을 같이 찍습니다)"):
            return "사용자가 거부했습니다."
        stem = os.path.splitext(os.path.basename(dest))[0]
        try:
            r = blender3d.run("build", None, _config, parts=parts, dest=dest,
                              preview_dir=os.path.dirname(dest), stem=stem)
        except subprocess.TimeoutExpired:
            return "블렌더가 5분 안에 끝나지 않아 중단했습니다."
        except RuntimeError as e:
            return str(e)
        if not os.path.isfile(dest) or os.path.getsize(dest) < 1024:
            return f"⚠ 조립했다고 했지만 결과 파일이 이상합니다({dest})."
        msg = (f"조립했습니다: {dest}\n  · 부품 {len(r.get('parts', []))}개 "
               f"({', '.join(r.get('parts', [])[:8])}) · 폴리 {r.get('polys', 0):,}")
        for pv in r.get("previews", []):
            msg += f"\n  · 미리보기: {pv}"
        if r.get("previews"):
            msg += _blender_eye("build", r["previews"][-1])
            # ⭐파손 검사와 별개로 '무엇으로 보이나'를 묻습니다 — 부품이 다 제자리여도
            #   엉뚱한 물건이 나올 수 있음(세션67 토마호크→망치 실측).
            msg += _blender_eye_recognize(_subject_of(args, dest), r["previews"][-1])
        return msg + "\n(웹에서는 미리보기가 바로 보입니다. 모양이 어긋나면 수치를 고쳐 다시 부르세요.)"

    if action == "text3d":                       # 3D 글자 간판 — 새 .blend (한글 폰트 자동)
        text = str(args.get("text") or "").strip()
        if not text:
            return "text3d는 text(새길 글)가 필요합니다. 예: text=\"응급 구역\", path=간판.blend"
        dest = _new_path(args.get("path"))
        if not dest:
            return "text3d는 path에 만들 파일 이름이 필요합니다(예: 간판.blend)."
        if not _confirm(f"3D 글자 '{text[:30]}'를 '{os.path.basename(dest)}'로 만들까요? "
                        "(새 파일과 미리보기만 생성)"):
            return "사용자가 거부했습니다."
        kw = {"text": text, "dest": dest, "preview_dir": os.path.dirname(dest),
              "stem": os.path.splitext(os.path.basename(dest))[0]}
        for k in ("size", "depth", "font"):
            if args.get(k) is not None:
                kw[k] = args[k]
        if args.get("color"):
            kw["color"] = args["color"]
        try:
            r = blender3d.run("text3d", None, _config, **kw)
        except subprocess.TimeoutExpired:
            return "블렌더가 5분 안에 끝나지 않아 중단했습니다."
        except RuntimeError as e:
            return str(e)
        msg = f"3D 글자를 만들었습니다: {dest} (폴리 {r.get('polys', 0):,})"
        for pv in r.get("previews", []):
            msg += f"\n  · 미리보기: {pv}"
        return msg + "\n(assemble로 씬에 배치하거나 prep_unity로 FBX로 뽑으면 됩니다.)"

    if action == "assemble":                     # 여러 3D 파일을 좌표대로 한 씬에 배치(키트배시)
        items = _json_arg(args.get("items"))
        if not items or not all(isinstance(i, dict) and i.get("file") for i in items):
            return ("assemble은 items에 배치 목록이 필요합니다. 예: items=[{\"file\":\"C:/…/나무.blend\","
                    "\"pos\":[2,0,0],\"rot_deg\":[0,0,45],\"scale\":1.2}] "
                    "(file은 blend·fbx·obj·glb·stl, 같은 파일을 여러 번 놓아도 됩니다)")
        exts = (".blend", ".fbx", ".obj", ".glb", ".gltf", ".stl")
        fixed = []
        for it in items:
            f = _find_media(it.get("file"), exts)
            if not f:
                return f"배치할 파일을 찾지 못했습니다: {it.get('file')} (전체 경로를 주세요)"
            it = dict(it)
            it["file"] = f
            fixed.append(it)
        dest = _new_path(args.get("path"))
        if not dest:
            return "assemble은 path에 만들 씬 파일 이름이 필요합니다(예: 마을광장.blend)."
        export = str(args.get("export", "")).lower()
        export = export if export in ("fbx", "glb") else ""
        exp_dest = os.path.splitext(dest)[0] + "." + export if export else None
        what = f"파일 {len(fixed)}개를 '{os.path.basename(dest)}' 한 씬에 배치"
        if export:
            what += f" 후 {export.upper()}로도 내보내기"
        if not _confirm(f"{what}? 원본들은 읽기만 하고 새 파일만 만듭니다."):
            return "사용자가 거부했습니다."
        stem = os.path.splitext(os.path.basename(dest))[0]
        kw = {"items": fixed, "dest": dest,
              "preview_dir": os.path.dirname(dest), "stem": stem}
        if export:
            kw["export"] = export
            kw["export_dest"] = exp_dest
        try:
            r = blender3d.run("assemble", None, _config, timeout=420, **kw)
        except subprocess.TimeoutExpired:
            return "블렌더가 7분 안에 끝나지 않아 중단했습니다."
        except RuntimeError as e:
            return str(e)
        L = [f"씬을 조립했습니다: {dest}"]
        for p in r.get("placed", []):
            L.append(f"  · {p['name']} ← {p['file']} (오브젝트 {p['objects']}개)")
        if r.get("exported"):
            L.append(f"  · 내보내기: {r['exported']}")
        for pv in r.get("previews", []):
            L.append(f"  · 미리보기: {pv}")
        eye = _blender_eye("assemble", r["previews"][-1]) if r.get("previews") else ""
        if eye:
            L.append(eye.strip("\n"))
        if r.get("previews"):
            rec = _blender_eye_recognize(_subject_of(args, dest), r["previews"][-1])
            if rec:
                L.append(rec.strip("\n"))
        return "\n".join(L)

    # convert는 .blend가 아니라 fbx/obj/glb/stl을 받습니다 — 별도 처리 후 반환.
    if action == "convert":
        src = _find_media(args.get("path") or args.get("src"),
                          (".fbx", ".obj", ".glb", ".gltf", ".stl"))
        if not src:
            return (f"바꿀 3D 파일을 찾지 못했습니다: {args.get('path') or args.get('src')} "
                    "(fbx·obj·glb·stl 지원, 전체 경로를 주세요)")
        fmt = str(args.get("format", "")).lower()
        if fmt not in ("fbx", "obj", "glb"):
            return "convert는 format을 fbx·obj·glb 중 하나로 정해 주세요."
        folder = os.path.dirname(src)
        stem = os.path.splitext(os.path.basename(src))[0]
        dest = os.path.join(folder, f"{stem}.{fmt}")
        if os.path.abspath(dest) == os.path.abspath(src) or os.path.exists(dest):
            dest = os.path.join(folder, f"{stem}_{time.strftime('%H%M%S')}.{fmt}")
        if not _confirm(f"{os.path.basename(src)} → {fmt.upper()}로 변환할까요? (새 파일: {dest})"):
            return "사용자가 거부했습니다."
        try:
            r = blender3d.run("convert", None, _config, src=src, format=fmt, dest=dest)
        except subprocess.TimeoutExpired:
            return "블렌더가 5분 안에 끝나지 않아 중단했습니다."
        except RuntimeError as e:
            return str(e)
        out = r.get("exported", dest)
        if not os.path.isfile(out) or os.path.getsize(out) < 512:
            return f"⚠ 변환됐다고 했지만 결과 파일이 이상합니다({out}) — 블렌더에서 직접 확인해 보세요."
        mb = os.path.getsize(out) / (1024 * 1024)
        return f"변환했습니다: {out} ({mb:.1f}MB, 메시 {r.get('objects', '?')}개)"

    path = _find_media(args.get("path"), (".blend",))
    if not path:
        # 바탕화면 바로 아래 폴더 한 층까지 뒤집니다(작업 폴더에 두는 일이 흔함)
        base = os.path.basename(str(args.get("path") or "").strip().strip('"\''))
        if base:
            import glob as _glob
            hits = _glob.glob(os.path.join(DESKTOP, "*", base))
            path = hits[0] if hits else None
    if not path:
        return (f"파일을 찾지 못했습니다: {args.get('path')} "
                "(전체 경로를 주거나 find_files로 먼저 찾아보세요)")
    if not path.lower().endswith(".blend"):
        return ".blend 파일만 다룰 수 있습니다 (FBX 확인은 유니티에서, 만들기는 export로)."

    folder = os.path.dirname(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        if action == "info":                     # 읽기만 — 확인 안 물음
            r = blender3d.run("info", path, _config)
            return (f"[{os.path.basename(path)}]\n" + blender3d.summarize_info(r)
                    + _budget_notes_info(r))

        if action == "check":                    # 유니티 반입 린트 — 읽기만, 안 고침
            r = blender3d.run("check", path, _config)
            c = r["check"]
            L = [f"[{os.path.basename(path)}] 유니티 반입 점검"]
            L.append("  ⚠ 스케일 미적용: " + ", ".join(c["unapplied_scale"][:6])
                     + " (apply 필요 — 유니티 크기 어긋남의 주범)" if c["unapplied_scale"]
                     else "  ✅ 스케일 적용됨")
            L.append("  ⚠ UV 없는 메시: " + ", ".join(c["no_uv"][:6]) + " (텍스처 못 입힘 — uv 필요)"
                     if c["no_uv"] else "  ✅ UV 있음")
            L.append(f"  ⚠ n-gon {c['ngons']}개 (유니티가 삼각화 — 의도치 않은 음영 가능)"
                     if c["ngons"] else "  ✅ n-gon 없음")
            L.append(f"  ⚠ 비매니폴드 엣지 {c['nonmanifold_edges']}개 · 뜬 정점 {c['loose_verts']}개"
                     " (cleanup 권장)" if (c["nonmanifold_edges"] or c["loose_verts"])
                     else "  ✅ 지오메트리 깨끗")
            off = (abs(c["bottom_z"]) > 0.01 or abs(c["center_xy"][0]) > 0.01
                   or abs(c["center_xy"][1]) > 0.01)
            L.append(f"  ⚠ 원점 어긋남: 바닥 z={c['bottom_z']}, 중심 xy={c['center_xy']} (origin 권장)"
                     if off else "  ✅ 원점 정렬(바닥 중앙 ≈ 0)")
            if len(c["materials"]) > 4:
                L.append(f"  ⚠ 재질 {len(c['materials'])}종 (드로우콜↑ — join/합치기 고려)")
            L.append(f"  ℹ 메시 {c['meshes']} · 폴리 {c['polys']:,}(삼각 {c['tris']}·n-gon {c['ngons']})"
                     f" · 재질 {len(c['materials'])}종")
            # ⚠check의 'tris'는 삼각형 '면'의 개수(쿼드 파일=0)라 예산 대조엔 못 씀 — 면×2 추정으로.
            pb = _budget_note_polys(c.get("polys"))
            if pb:
                L.append(pb.strip("\n"))
            warns = sum(1 for x in L if x.lstrip().startswith("⚠"))
            L.append(f"  → 문제 {warns}건" if warns else "  → 반입 준비 완료 ✅")
            return "\n".join(L)

        if action == "compare":                  # 두 .blend 차이표 — 읽기만(버전 감사)
            path2 = _find_media(args.get("path2"), (".blend",))
            if not path2:
                return (f"비교할 두 번째 파일을 찾지 못했습니다: {args.get('path2')} "
                        "(compare는 path와 path2에 .blend 두 개가 필요합니다)")
            a = blender3d.run("info", path, _config)
            b = blender3d.run("info", path2, _config)
            na = {o["name"]: o for o in a["objects"]}
            nb = {o["name"]: o for o in b["objects"]}
            L = [f"[{os.path.basename(path)}] ↔ [{os.path.basename(path2)}]"]
            added = sorted(set(nb) - set(na))
            removed = sorted(set(na) - set(nb))
            if added:
                L.append(f"  + 두 번째에만 있음: {', '.join(added[:10])}"
                         + (f" 외 {len(added)-10}" if len(added) > 10 else ""))
            if removed:
                L.append(f"  - 첫 번째에만 있음: {', '.join(removed[:10])}"
                         + (f" 외 {len(removed)-10}" if len(removed) > 10 else ""))
            changed = [n for n in set(na) & set(nb)
                       if na[n].get("polys") != nb[n].get("polys")]
            for n in changed[:8]:
                L.append(f"  ~ {n}: 폴리 {na[n].get('polys', 0):,} → {nb[n].get('polys', 0):,}")
            if len(changed) > 8:
                L.append(f"  ~ …외 {len(changed)-8}개 폴리 변화")
            L.append(f"  · 총폴리 {a['total_polys']:,} → {b['total_polys']:,} · "
                     f"최대 크기 {a['max_dimension']}m → {b['max_dimension']}m · "
                     f"재질 {len(a['materials'])} → {len(b['materials'])} · "
                     f"애니 {len(a['actions'])} → {len(b['actions'])}")
            ma, mb2 = set(a["materials"]), set(b["materials"])
            if ma != mb2:
                if mb2 - ma:
                    L.append(f"  · 재질 추가: {', '.join(sorted(mb2 - ma)[:8])}")
                if ma - mb2:
                    L.append(f"  · 재질 삭제: {', '.join(sorted(ma - mb2)[:8])}")
            if set(a["actions"]) != set(b["actions"]):
                L.append(f"  · 애니: {', '.join(a['actions'][:6]) or '없음'} → "
                         f"{', '.join(b['actions'][:6]) or '없음'}")
            if len(L) == 2:
                L.append("  → 구성 차이 없음(오브젝트·폴리·재질·애니 동일)")
            return "\n".join(L)

        if action == "render":
            n = max(1, min(int(args.get("angles", 4)), 4))
            if not _confirm(f"{os.path.basename(path)}의 미리보기 {n}장을 렌더할까요? "
                            f"(원본은 안 건드리고 {folder}에 그림만 저장)"):
                return "사용자가 거부했습니다."
            r = blender3d.run("render", path, _config, out_dir=folder,
                              stem=f"{stem}_미리보기", angles=n,
                              size=int(args.get("size", 512)))
            files = r.get("renders", [])
            return ("미리보기를 만들었습니다:\n" + "\n".join(files)
                    + "\n(웹에서는 그림이 바로 뜹니다. 파일에 카메라가 있으면 그 시점 1장)")

        if action == "anim_preview":             # 움직임을 GIF로 — 애니가 없으면 턴테이블
            import video
            n = max(4, min(int(args.get("frames", 12)), 24))
            fps = max(2, min(int(args.get("fps", 8)), 15))
            if not _confirm(f"{os.path.basename(path)}의 움직임 미리보기 GIF를 만들까요? "
                            f"(프레임 {n}장 렌더 — 원본은 안 건드리고 {folder}에 GIF만 저장)"):
                return "사용자가 거부했습니다."
            fr_dir = os.path.join(folder, f"{stem}_frames_{time.strftime('%H%M%S')}")
            os.makedirs(fr_dir, exist_ok=True)
            try:
                r = blender3d.run("anim_frames", path, _config, timeout=420,
                                  out_dir=fr_dir, stem=stem, frames=n,
                                  size=int(args.get("size", 384)),
                                  mode=str(args.get("mode", "")))
            except Exception:
                shutil.rmtree(fr_dir, ignore_errors=True)
                raise
            frames = r.get("frames", [])
            mode_ko = "애니메이션" if r.get("mode") == "anim" else "턴테이블(제자리 한 바퀴)"
            ff = video._find("ffmpeg", _config)
            if not ff:
                return (f"프레임 {len(frames)}장을 찍었지만 ffmpeg가 없어 GIF로 못 묶었습니다: "
                        f"{fr_dir}\n({video.INSTALL_GUIDE})")
            gif_path = os.path.join(folder, f"{stem}_움직임.gif")
            if os.path.exists(gif_path):
                gif_path = os.path.join(folder, f"{stem}_움직임_{time.strftime('%H%M%S')}.gif")
            proc = subprocess.run(
                [ff, "-y", "-framerate", str(fps),
                 "-i", os.path.join(fr_dir, f"{stem}_f%02d.png"),
                 "-vf", "split[a][b];[a]palettegen[p];[b][p]paletteuse", gif_path],
                capture_output=True, timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if proc.returncode != 0 or not os.path.isfile(gif_path):
                return (f"프레임은 찍었는데 GIF 조립이 실패했습니다 — 프레임 폴더: {fr_dir}\n"
                        + (proc.stderr or b"").decode("utf-8", "replace").strip()[-200:])
            shutil.rmtree(fr_dir, ignore_errors=True)          # GIF가 됐으니 낱장은 정리
            msg = f"{mode_ko} GIF를 만들었습니다: {gif_path} (프레임 {len(frames)}장, {fps}fps)"
            if r.get("actions"):
                msg += f"\n  · 담긴 애니메이션: {', '.join(r['actions'][:6])}"
                if r.get("frame_range"):
                    msg += f" (프레임 {r['frame_range'][0]}~{r['frame_range'][1]})"
            # 애니 눈검수(세션63 6부): GIF에서 4프레임을 뽑아 한 줄로 붙여 명백한 파손만 판정.
            # '자연스러움'은 미적 판단이라 사람 몫 — 관통·바닥 뚫림·심한 대칭만 본다.
            if r.get("mode") == "anim":
                strip = _gif_strip(gif_path, folder, stem)
                if strip:
                    msg += _eye_look(
                        "캐릭터 애니메이션에서 시간 순서대로 뽑은 4프레임을 왼쪽부터 붙인 "
                        "그림입니다(회색 재질 — 미적 평가 금지).",
                        "팔다리가 몸통을 뚫고 들어갔는가? 발이 바닥 아래로 꺼졌는가? "
                        "네 프레임이 전부 거의 같은 포즈(안 움직임)인가? "
                        "그 정도의 명백한 파손이 없으면 '정상'으로 — 동작이 로봇 같은지는 "
                        "판정하지 말 것(사람이 GIF로 봄).", strip, gate_key="blender")
            return msg + "\n(웹에서는 GIF가 바로 움직입니다 — 걷기가 로봇 같은지 여기서 보세요.)"

        if action == "lod":                      # LOD 0/1/2를 유니티 자동 인식 이름으로 한 FBX에
            lods = _json_arg(args.get("lods")) or [1.0, 0.5, 0.25]
            dest = os.path.join(folder, f"{stem}_LOD.fbx")
            if os.path.exists(dest):
                dest = os.path.join(folder, f"{stem}_LOD_{time.strftime('%H%M%S')}.fbx")
            if not _confirm(f"{os.path.basename(path)}의 LOD {len(lods)}단계"
                            f"(비율 {', '.join(str(x) for x in lods)})를 만들어 "
                            f"{os.path.basename(dest)} 하나에 담을까요? 원본은 안 건드립니다."):
                return "사용자가 거부했습니다."
            r = blender3d.run("lod", path, _config, lods=lods, dest=dest)
            v = r.get("verify", {})
            L = [f"LOD FBX를 만들었습니다: {r.get('dest', dest)}"]
            for lv in r.get("levels", []):
                L.append(f"  · LOD{lv['level']} (비율 {lv['ratio']}) — 폴리 {lv['polys']:,}")
            if v.get("error"):
                L.append(f"  · 검증 실패: {v['error']}")
            else:
                mark = "✅" if v.get("ok") else "⚠"
                L.append(f"  · 검증(FBX 재확인): 메시 {v.get('meshes')}개 중 "
                         f"LOD 이름 {v.get('lod_named')}개 {mark}")
            L.append("  → 유니티에 넣으면 _LOD0/1/2 이름을 보고 LOD Group이 자동으로 잡힙니다.")
            return "\n".join(L)

        if action == "anim_merge":               # 애니 FBX 여러 개 → 캐릭터 하나의 FBX 합본
            raw = args.get("anims")
            raw = [x.strip() for x in raw.split(",")] if isinstance(raw, str) else (raw or [])
            anims = []
            for a in raw:
                f = _find_media(a, (".fbx",))
                if not f:
                    return f"애니메이션 FBX를 찾지 못했습니다: {a} (전체 경로를 주세요)"
                anims.append(f)
            if not anims:
                return ("anim_merge는 anims에 애니메이션 FBX 목록이 필요합니다. "
                        "예: anims=[\"C:/…/walk.fbx\", \"C:/…/run.fbx\"] — path의 캐릭터 "
                        ".blend(리깅된 뼈대)에 클립으로 합쳐 한 FBX로 내보냅니다.")
            dest = os.path.join(folder, f"{stem}_anims.fbx")
            if os.path.exists(dest):
                dest = os.path.join(folder, f"{stem}_anims_{time.strftime('%H%M%S')}.fbx")
            if not _confirm(f"{os.path.basename(path)}에 애니메이션 {len(anims)}개"
                            f"({', '.join(os.path.basename(a) for a in anims[:4])})를 합본해 "
                            f"{os.path.basename(dest)}로 내보낼까요? 원본 .blend는 그대로입니다."):
                return "사용자가 거부했습니다."
            r = blender3d.run("anim_merge", path, _config, timeout=420,
                              anims=anims, dest=dest)
            v = r.get("verify", {})
            L = [f"애니메이션을 합본했습니다: {r.get('dest', dest)}"]
            for m in r.get("merged", []):
                L.append(f"  · 클립 '{m['clip']}' (본 일치 {m['bones_matched']})")
            for s in r.get("skipped", []):
                L.append(f"  · ⚠ 건너뜀: {s['file']} — {s['reason']}"
                         + (f" (그쪽 본: {', '.join(s['their_bones'])}…)"
                            if s.get("their_bones") else ""))
            if v.get("error"):
                L.append(f"  · 검증 실패: {v['error']}")
            else:
                mark = "✅" if v.get("ok") else "⚠"
                L.append(f"  · 검증(FBX 재확인): 클립 {v.get('clips')}개 "
                         f"({', '.join(v.get('names', [])[:6])}) {mark}")
            L.append("  → 유니티에 넣으면 Animation 탭에 클립이 여러 개로 뜹니다.")
            return "\n".join(L)

        if action == "bake":                     # 하이폴리 디테일을 로우폴리 노멀/AO PNG로 굽기
            maps = args.get("maps")
            maps = [x.strip().lower() for x in maps.split(",")] if isinstance(maps, str) \
                else [str(x).lower() for x in (maps or ["normal", "ao"])]
            maps = [m for m in maps if m in ("normal", "ao")] or ["normal", "ao"]
            size = int(args.get("size", 1024))
            if not _confirm(f"{os.path.basename(path)} — 하이폴리 디테일을 로우폴리에 "
                            f"{'·'.join(maps)} 맵({size}px)으로 구울까요? "
                            f"원본은 안 건드리고 {folder}에 PNG만 만듭니다(Cycles라 수 분 걸릴 수 있음)."):
                return "사용자가 거부했습니다."
            kw = {"out_dir": folder, "stem": f"{stem}_baked", "maps": maps, "size": size}
            for k in ("high", "low", "extrusion", "samples"):
                if args.get(k) is not None:
                    kw[k] = args[k]
            r = blender3d.run("bake", path, _config, timeout=600, **kw)
            L = [f"베이킹 완료: 하이폴리 '{r.get('high')}'({r.get('high_polys', 0):,}폴리) → "
                 f"로우폴리 '{r.get('low')}'({r.get('low_polys', 0):,}폴리)"]
            for b in r.get("baked", []):
                okf = os.path.isfile(b["file"]) and os.path.getsize(b["file"]) > 1024
                L.append(f"  · {b['map']} 맵: {b['file']} ({b['size']}px) {'✅' if okf else '⚠파일 이상'}")
            if r.get("uv_added"):
                L.append("  · 로우폴리에 UV가 없어 자동으로 폈습니다.")
            L.append(f"  · 케이지 여유 {r.get('extrusion')}m — 맵이 얼룩지면 extrusion을 키워 다시.")
            L.append("  → 유니티에서 로우폴리 재질의 Normal Map/Occlusion에 이 PNG를 넣으면 "
                     "하이폴리 디테일이 살아납니다.")
            return "\n".join(L)

        if action == "beauty_render":            # 기획서용 렌더(3점 조명+그림자+투명 배경)
            dest = os.path.join(folder, f"{stem}_beauty.png")
            if os.path.exists(dest):
                dest = os.path.join(folder, f"{stem}_beauty_{time.strftime('%H%M%S')}.png")
            if not _confirm(f"{os.path.basename(path)}의 기획서용 렌더를 찍을까요? "
                            f"(3점 조명+바닥 그림자+투명 배경 PNG — 원본은 안 건드리고 "
                            f"{os.path.basename(dest)}만 저장, Cycles라 1~2분)"):
                return "사용자가 거부했습니다."
            kw = {"dest": dest}
            for k in ("width", "height", "size", "samples", "angle"):
                if args.get(k) is not None:
                    kw[k] = args[k]
            r = blender3d.run("beauty_render", path, _config, timeout=600, **kw)
            outp = r.get("dest", dest)
            if not os.path.isfile(outp) or os.path.getsize(outp) < 1024:
                return f"⚠ 렌더했다고 했지만 결과 파일이 이상합니다({outp})."
            res = r.get("resolution", ["?", "?"])
            return (f"기획서용 렌더를 찍었습니다: {outp} ({res[0]}×{res[1]}, "
                    f"샘플 {r.get('samples')})\n"
                    "  · 배경이 투명(PNG 알파)이라 기획서·PPT에 바로 얹을 수 있습니다. "
                    "바닥 그림자도 같이 담겨 있습니다.\n"
                    "(웹에서는 그림이 바로 보입니다. 각도를 바꾸려면 angle=도 를 주세요.)")

        if action in blender3d.SURGERY:          # 모델을 실제로 바꿈 — 반드시 사본에서만
            _WHAT = {"apply": "스케일·회전 적용(유니티 크기 어긋남 방지)",
                     "origin": "바닥 중심을 원점으로 옮기기",
                     "scale_to": f"전체 키를 {args.get('height')}m로 맞추기",
                     "cleanup": "중복 정점 합치기·법선 정리·부스러기 제거",
                     "uv": "UV 자동 펼치기(텍스처 입힐 준비)",
                     "decimate": f"폴리곤 줄이기(비율 {args.get('ratio', 0.5)})",
                     "join": "메시를 한 덩어리로 합치기",
                     "auto_weight": "기존 뼈대에 자동으로 살 붙이기(자동 웨이트) — 메시가 본을 따라 움직이게",
                     "bone_template": f"{'네발' if str(args.get('kind', '')).lower() == 'quadruped' else '두발'} "
                                      "표준 뼈대를 몸 크기에 맞춰 배치"
                                      + (" 후 자동 웨이트까지" if args.get("bind") else ""),
                     "tex_resize": f"{args.get('max_px', 1024)}px 넘는 텍스처 줄이기(용량 다이어트)",
                     "mirror": f"{str(args.get('axis', 'x')).upper()}축 대칭 복제로 완성(원점 기준)",
                     "array": (f"원형 배열 {args.get('count', 4)}개(반지름 {args.get('radius')}m)"
                               if str(args.get('mode', '')).lower() == 'radial'
                               else f"선형 배열 {args.get('count', 4)}개"),
                     "scatter": f"{args.get('count', 20)}개 랜덤 뿌리기(시드 {args.get('seed', 0)} — "
                                "같은 시드면 같은 배치)",
                     "collider": "유니티 콜라이더용 저폴리 헐 생성"
                                 + ("(전체 하나로)" if args.get("combined") else "(메시마다)"),
                     "materials": "재질 정리(중복 병합"
                                  + ("+ASCII 이름" if args.get("ascii") else "")
                                  + ("+색 변경" if args.get("colors") else "") + ")",
                     "split": ("재질별로" if str(args.get('mode', '')).lower() == 'material'
                               else "떨어진 조각별로") + " 메시 분리",
                     "anim_edit": "애니메이션 손질("
                                  + "·".join(x for x in (
                                      f"트림 {args.get('trim')}" if args.get("trim") else "",
                                      "루프화" if args.get("loop") else "",
                                      f"이름→{args.get('new_name')}" if args.get("new_name") else "")
                                      if x) + ")",
                     "weight_transfer": "본체 웨이트를 옷·장비 메시에 근접 전사",
                     "repair": "메시 수리(구멍 메우기·퇴화면 정리·비매니폴드"
                               + (" — 심하면 복셀 리메시까지" if args.get("remesh") else "") + ")",
                     "boolean": f"불리언 CSG {len(_json_arg(args.get('items')) or [])}건"
                                "(뚫기·합치기·교차)",
                     "curve_path": {"pipe": "좌표 경로를 따라 관(파이프) 만들기",
                                    "ribbon": "좌표 경로를 따라 띠(리본) 만들기",
                                    "array": "오브젝트를 커브 경로 따라 배열"}
                                   .get(str(args.get("mode", "pipe")).lower(),
                                        "좌표 경로로 커브 만들기"),
                     "sockets": f"부착점(Empty) {len(_json_arg(args.get('items')) or [])}개 심기"
                                " — 유니티 장착 포인트",
                     "uv_atlas": f"재질·UV를 아틀라스 한 장({args.get('size', 2048)}px)으로 합치기"
                                 "(드로우콜 절약, Cycles 굽기라 수 분)",
                     "material_pbr": f"텍스처 폴더({os.path.basename(str(args.get('tex_dir') or ''))})의 "
                                     "PBR 맵을 자동 매칭해 재질 배선",
                     "bevel": f"모서리 챔퍼(폭 {args.get('width', 0.02)}m·{args.get('segments', 2)}단)",
                     "solidify": f"두께 {args.get('thickness', 0.02)}m 입히기(종이장 메시 보강)",
                     "shade": {"flat": "플랫 셰이딩(전부 각지게)",
                               "smooth": "스무스 셰이딩(전부 부드럽게)"}
                              .get(str(args.get("mode", "auto")).lower(),
                                   f"자동 스무스({args.get('angle', 30)}° 기준 — 급한 모서리만 각지게)"),
                     "lightmap_uv": "라이트맵용 두 번째 UV(UV2) 깔기 — 유니티 베이크 대비",
                     "rename": "오브젝트·재질 이름 ASCII 일괄 개명(유니티 위생"
                               + (f", 접두사 {args.get('prefix')}" if args.get("prefix") else "") + ")",
                     "normals": "법선 전수진단·수리(뒤집힌 메시 바깥으로 — '안쪽이 비쳐 보임' 방지)",
                     "align": {"row": "오브젝트들을 한 줄로 정렬(+바닥 스냅)",
                               "grid": "오브젝트들을 격자로 정렬(+바닥 스냅)"}
                              .get(str(args.get("mode", "ground")).lower(),
                                   "각 오브젝트를 바닥(z=0)에 스냅"),
                     "purge": "미사용(고아) 데이터 청소 — 파일 다이어트"
                              + ("(fake user 방패 찌꺼기까지)" if args.get("include_fake") else ""),
                     "pose_apply": f"포즈 {len(_json_arg(args.get('poses')) or [])}개를 키프레임으로 적용",
                     "physics_bake": ("천 드리우기 시뮬 후 모양 고정"
                                      if str(args.get("mode", "rigid")).lower() == "cloth"
                                      else "떨어뜨리기(강체) 시뮬을 키프레임으로 굽기"),
                     "sculpt_displace": (f"표면에 '{args.get('pattern', 'bumpy')}' 유기적 요철 새기기"
                                         f"(면 분할 {args.get('subdiv', 2)}단 — 면이 크게 늘어남)")}[action]
            if action == "scale_to" and not args.get("height"):
                return "scale_to는 height(목표 키, 미터)가 필요합니다. 예: height=1.6"
            copy = blender3d.work_copy(path)     # 원본 옆에 사본 생성 — 원본은 여기서부터 안 건드림
            if not _confirm(f"{os.path.basename(path)} — {_WHAT}. 원본은 그대로 두고 "
                            f"사본 '{os.path.basename(copy)}'에만 반영합니다. 진행할까요?"):
                os.remove(copy)
                return "사용자가 거부했습니다."
            kw = {"preview_dir": folder, "stem": os.path.splitext(os.path.basename(copy))[0]}
            if action == "scale_to":
                kw["height"] = float(args["height"])
            if action == "decimate":
                kw["ratio"] = float(args.get("ratio", 0.5))
            if action == "uv" and args.get("force"):
                kw["force"] = True
            if action == "bone_template":
                kw["kind"] = str(args.get("kind", "humanoid")).lower()
                if args.get("bind"):
                    kw["bind"] = True
            if action == "tex_resize":
                kw["max_px"] = int(args.get("max_px", 1024))
            if action == "mirror":
                kw["axis"] = str(args.get("axis", "x")).lower()
            if action == "array":
                kw["mode"] = str(args.get("mode", "linear")).lower()
                kw["count"] = int(args.get("count", 4))
                for k in ("offset", "radius", "center"):
                    if args.get(k) is not None:
                        kw[k] = args[k]
            if action == "scatter":
                kw["count"] = int(args.get("count", 20))
                kw["seed"] = int(args.get("seed", 0))
                for k in ("area", "jitter"):
                    if args.get(k) is not None:
                        kw[k] = args[k]
            if action == "collider":
                kw["max_tris"] = int(args.get("max_tris", 255))
                if args.get("combined"):
                    kw["combined"] = True
            if action == "materials":
                kw["dedupe"] = bool(args.get("dedupe", True))
                if args.get("ascii"):
                    kw["ascii"] = True
                if isinstance(args.get("colors"), dict):
                    kw["colors"] = args["colors"]
            if action == "sculpt_displace":
                kw["pattern"] = str(args.get("pattern", "bumpy")).lower()
                for k in ("strength", "feature", "subdiv", "targets", "seed",
                          "max_tris", "smooth"):
                    if args.get(k) is not None:
                        kw[k] = args[k]
            if action == "split":
                kw["mode"] = str(args.get("mode", "loose")).lower()
            if action == "anim_edit":
                for k in ("name", "new_name", "trim", "loop", "shift"):
                    if args.get(k) is not None:
                        kw[k] = args[k]
            if action == "weight_transfer":
                for k in ("source", "targets"):
                    if args.get(k) is not None:
                        kw[k] = args[k]
            if action == "repair":
                if args.get("remesh"):
                    kw["remesh"] = True
                if args.get("sides") is not None:
                    kw["sides"] = int(args["sides"])
            if action in ("boolean", "sockets"):
                items = _json_arg(args.get("items"))
                if not items:
                    os.remove(copy)
                    return (action + "는 items 목록이 필요합니다. 예: "
                            + ('items=[{"target":"Wall","tool":"Hole","mode":"difference"}]'
                               if action == "boolean" else
                               'items=[{"name":"Socket_Muzzle","pos":[0,-0.5,0.1],'
                               '"parent":"총몸"}]'))
                kw["items"] = items
                if action == "boolean" and args.get("keep_tools"):
                    kw["keep_tools"] = True
            if action == "curve_path":
                pts = _json_arg(args.get("points"))
                if not pts:
                    os.remove(copy)
                    return ("curve_path는 points=[[x,y,z]…] 경로 좌표가 필요합니다. "
                            "mode=pipe(관, radius)·ribbon(띠, width)·array(커브 따라 배열, object)")
                kw["points"] = pts
                for k in ("mode", "radius", "width", "smooth", "cyclic", "object", "name"):
                    if args.get(k) is not None:
                        kw[k] = args[k]
            if action == "uv_atlas":
                kw["size"] = int(args.get("size", 2048))
                if args.get("samples") is not None:
                    kw["samples"] = int(args["samples"])
                kw["png_dest"] = os.path.join(
                    folder, os.path.splitext(os.path.basename(copy))[0] + "_atlas.png")
            if action == "material_pbr":
                if not args.get("tex_dir") or not os.path.isdir(str(args.get("tex_dir"))):
                    os.remove(copy)
                    return "material_pbr는 tex_dir(텍스처가 든 폴더 경로)가 필요합니다."
                kw["tex_dir"] = str(args["tex_dir"])
                for k in ("name", "targets"):
                    if args.get(k) is not None:
                        kw[k] = args[k]
            if action == "bevel":
                for k, cast in (("width", float), ("segments", int), ("angle", float)):
                    if args.get(k) is not None:
                        kw[k] = cast(args[k])
            if action == "solidify":
                if args.get("thickness") is not None:
                    kw["thickness"] = float(args["thickness"])
                if args.get("targets") is not None:
                    kw["targets"] = _json_arg(args["targets"]) or args["targets"]
            if action == "shade":
                kw["mode"] = str(args.get("mode", "auto")).lower()
                if args.get("angle") is not None:
                    kw["angle"] = float(args["angle"])
            if action == "lightmap_uv" and args.get("margin") is not None:
                kw["margin"] = float(args["margin"])
            if action == "rename" and args.get("prefix"):
                kw["prefix"] = str(args["prefix"])
            if action == "purge" and args.get("include_fake"):
                kw["include_fake"] = True
            if action == "align":
                kw["mode"] = str(args.get("mode", "ground")).lower()
                for k, cast in (("gap", float), ("cols", int)):
                    if args.get(k) is not None:
                        kw[k] = cast(args[k])
                if args.get("axis"):
                    kw["axis"] = str(args["axis"]).lower()
            if action == "pose_apply":
                poses = _json_arg(args.get("poses"))
                if not poses or not all(isinstance(p, dict) for p in poses):
                    os.remove(copy)
                    return ('pose_apply는 poses 목록이 필요합니다. 예: poses=[{"frame":1,'
                            '"bones":{"UpperArm.L":{"rot_deg":[0,0,45]},"Spine":{"rot_deg":[10,0,0]}}}] '
                            "(본 이름은 info나 bone_template 결과에서, rot_deg는 도 단위·loc는 선택)")
                kw["poses"] = poses
                if args.get("name"):
                    kw["name"] = str(args["name"])
            if action == "physics_bake":
                kw["mode"] = str(args.get("mode", "rigid")).lower()
                if args.get("frames") is not None:
                    kw["frames"] = int(args["frames"])
                if args.get("target"):
                    kw["target"] = str(args["target"])
                if args.get("ground") is not None:
                    kw["ground"] = bool(args["ground"])
            try:
                r = blender3d.run(action, copy, _config,
                                  timeout=600 if action in ("uv_atlas", "repair",
                                                            "physics_bake") else 300,
                                  **kw)
                if action == "uv_atlas":         # 미리보기는 새 부팅으로(러너 주석의 크래시 회피)
                    try:
                        pv = blender3d.run("render", copy, _config, out_dir=folder,
                                           stem=os.path.splitext(os.path.basename(copy))[0]
                                           + "_미리보기", angles=1, size=512)
                        r["preview"] = (pv.get("renders") or [None])[0]
                    except Exception:
                        pass                     # 미리보기 실패가 수술 성공을 가리면 안 됨
                if action == "tex_resize" and not r.get("resized"):
                    os.remove(copy)          # 줄일 게 없었으면 사본도 안 남김
                    if r.get("preview") and os.path.isfile(r["preview"]):
                        os.remove(r["preview"])
                    return (f"{r.get('max_px')}px를 넘는 텍스처가 없습니다 — "
                            "줄일 게 없어 사본을 만들지 않았습니다.")
            except Exception:
                if os.path.isfile(copy):
                    os.remove(copy)          # 실패한 수술 사본은 원본 옆에 남기지 않음
                raise
            note = {"apply": lambda: f"적용한 메시 {len(r.get('applied', []))}개",
                    "origin": lambda: f"이동량 {r.get('moved_by')}",
                    "scale_to": lambda: f"{r.get('height_before')}m → {r.get('height_after')}m",
                    "cleanup": lambda: f"정점 {r.get('removed_verts', 0)}개 정리",
                    "uv": lambda: f"UV 추가 {len(r.get('uv_added', []))}개",
                    "decimate": lambda: f"폴리 {r.get('polys_before'):,} → {r.get('polys_after'):,}",
                    "join": lambda: f"{r.get('joined')}개 → 1개({r.get('result')})",
                    "auto_weight": lambda: (f"뼈대 '{r.get('armature')}'({r.get('bones')}본)에 "
                                            f"메시 {len(r.get('bound_meshes', []))}개 결합"),
                    "bone_template": lambda: (f"{r.get('kind')} 뼈대 {r.get('bones')}본 배치"
                                              + (f" + 메시 {len(r['bound_meshes'])}개 자동 웨이트"
                                                 if r.get("bound_meshes") else
                                                 " (관절 위치는 블렌더에서 다듬은 뒤 auto_weight)")),
                    "mirror": lambda: (f"{r.get('axis', 'x').upper()}축 대칭 — "
                                       f"폴리 {r.get('polys_before', 0):,} → {r.get('polys_after', 0):,}"),
                    "array": lambda: f"{r.get('mode')} 배열 — 복제 {r.get('copies')}개(총 {r.get('count')}자리)",
                    "scatter": lambda: (f"{r.get('count')}개 뿌림 — 영역 {r.get('area', ['?', '?'])[0]}×"
                                        f"{r.get('area', ['?', '?'])[1]}m·시드 {r.get('seed')}"),
                    "collider": lambda: ("콜라이더 " + ", ".join(
                                         f"{c['name']}({c['tris']}tri)" for c in r.get("colliders", [])[:5])
                                         + (f" 외 {len(r.get('colliders', [])) - 5}개"
                                            if len(r.get("colliders", [])) > 5 else "")),
                    "materials": lambda: (f"병합 {len(r.get('merged', {}))}건"
                                          + (f"·ASCII 개명 {len(r.get('renamed', {}))}건" if r.get("renamed") else "")
                                          + (f"·색 변경 {len(r.get('recolored', []))}건" if r.get("recolored") else "")
                                          + f" → 재질 {r.get('materials_left')}종 남음"),
                    "split": lambda: f"메시 {r.get('before')} → {r.get('after')}개 ({r.get('mode')} 분리)",
                    "anim_edit": lambda: (f"{r.get('action_name')}: " + " · ".join(r.get("did", []))
                                          + f" (프레임 {r.get('range_before')} → {r.get('range_after')})"),
                    "weight_transfer": lambda: (f"'{r.get('source')}' → {', '.join(r.get('targets', [])[:6])} "
                                                f"({r.get('groups')}그룹"
                                                + (f", 뼈대 {r.get('armature')}" if r.get("armature") else "")
                                                + ")"),
                    "repair": lambda: " / ".join(
                        f"{x['name']}: 비매니폴드 {x['before']['nonmanifold']}→{x['after']['nonmanifold']}"
                        f"·경계엣지 {x['before']['boundary']}→{x['after']['boundary']}"
                        f"·뜬점 {x['before']['loose']}→{x['after']['loose']}"
                        + ("(복셀 리메시함 — UV·재질 배치는 다시)" if x['after'].get('remeshed') else "")
                        for x in r.get("repair", [])[:4]),
                    "boolean": lambda: ("적용 " + "; ".join(r.get("ops_done", [])[:5])
                                        + f" → 폴리 {r.get('polys', 0):,}"),
                    "curve_path": lambda: (f"{r.get('mode')} — 좌표 {r.get('points')}개 → "
                                           f"'{r.get('result')}' (폴리 {r.get('polys', 0):,})"),
                    "sockets": lambda: "부착점 " + ", ".join(
                        f"{s['name']}" + (f"(부모 {s['parent']})" if s.get("parent") else "")
                        for s in r.get("sockets", [])[:8]) + " — FBX로 내보내면 유니티에 빈 오브젝트로 뜸",
                    "uv_atlas": lambda: (f"재질 {r.get('materials_before')}종 → 1종(Atlas) · "
                                         f"아틀라스 {r.get('size')}px: {r.get('atlas')}"),
                    "material_pbr": lambda: (f"재질 '{r.get('material')}' 배선: "
                                             + ", ".join(f"{k}={v}" for k, v in
                                                         r.get("channels", {}).items())
                                             + (f" · UV 자동 폄: {', '.join(r['uv_added'])}"
                                                if r.get("uv_added") else "")),
                    "tex_resize": lambda: (("텍스처 " + ", ".join(
                                            f"{x['name']} {x['from'][0]}×{x['from'][1]}→{x['to'][0]}×{x['to'][1]}"
                                            for x in r.get("resized", [])[:6])
                                            + f" — 파일 {os.path.getsize(path) / 1048576:.1f}MB→"
                                              f"{os.path.getsize(copy) / 1048576:.1f}MB")
                                           if r.get("resized") else
                                           f"{r.get('max_px')}px를 넘는 텍스처가 없어 그대로입니다"),
                    "bevel": lambda: (f"챔퍼 {r.get('width')}m·{r.get('segments')}단 — "
                                      f"폴리 {r.get('polys_before', 0):,} → {r.get('polys_after', 0):,}"),
                    "solidify": lambda: (f"두께 {r.get('thickness')}m — "
                                         f"{', '.join(r.get('solidified', [])[:6])} "
                                         f"(폴리 {r.get('polys_before', 0):,} → {r.get('polys_after', 0):,})"),
                    "shade": lambda: (f"{r.get('mode')} 셰이딩"
                                      + (f"({r.get('angle')}°)" if r.get("mode") == "auto" else "")
                                      + f" — 메시 {len(r.get('shaded', []))}개"),
                    "lightmap_uv": lambda: ((f"UV2 추가 {len(r.get('lightmap_added', []))}개"
                                             + (f"·이미 있음 {len(r['already'])}개" if r.get("already") else "")
                                             + " — 유니티에서 Generate Lightmap UVs 없이 바로 베이크 가능")
                                            if r.get("lightmap_added") else
                                            "전부 이미 Lightmap UV가 있어 그대로입니다"),
                    "rename": lambda: ((f"오브젝트 {len(r.get('objects', {}))}건·재질 {len(r.get('materials', {}))}건 개명: "
                                        + ", ".join(f"{a}→{b}" for a, b in
                                                    list({**r.get('objects', {}), **r.get('materials', {})}.items())[:6])
                                        + " (본 이름은 애니·웨이트 연결 탓에 안 건드림)")
                                       if (r.get("objects") or r.get("materials")) else
                                       "전부 이미 ASCII 이름이라 그대로입니다"),
                    "normals": lambda: ((f"뒤집힌 메시 수리: {', '.join(r.get('fixed', []))} "
                                         "(signed volume 음수→양수 실측)")
                                        if r.get("fixed") else
                                        f"메시 {len(r.get('normals', []))}개 전부 법선 정상(수리할 것 없음)"),
                    "align": lambda: (f"{r.get('mode')} 정렬 — " + ", ".join(
                                      (f"{p['name']}(z{p['moved_z']:+})" if "moved_z" in p
                                       else f"{p['name']}{tuple(p['pos'])}")
                                      for p in r.get("aligned", [])[:6])
                                      + (f" 외 {len(r.get('aligned', [])) - 6}개"
                                         if len(r.get("aligned", [])) > 6 else "")),
                    "purge": lambda: (((f"고아 데이터 {r.get('purged')}건 청소("
                                        + ", ".join(f"{k} {v}" for k, v in r.get("detail", {}).items())
                                        + f") — 파일 {os.path.getsize(path) / 1048576:.2f}MB→"
                                          f"{os.path.getsize(copy) / 1048576:.2f}MB")
                                       if r.get("purged") else "지운 고아 데이터가 없습니다")
                                      + (f"\n  · fake user로 살아있는 후보 {len(r['fake_only_left'])}건"
                                         f"({', '.join(r['fake_only_left'][:4])}…) — 지우려면 include_fake=true"
                                         if r.get("fake_only_left") else "")),
                    "pose_apply": lambda: (f"프레임 {r.get('frames')}에 본 {len(r.get('keyed_bones', []))}개 "
                                           f"키프레임(액션 '{r.get('action')}')"
                                           + (f" ⚠못 찾은 본: {', '.join(r['missing_bones'][:5])}"
                                              if r.get("missing_bones") else "")
                                           + " — 움직임 확인은 anim_preview로"),
                    "physics_bake": lambda: ((f"천 '{r.get('target')}' {r.get('frames')}프레임 드리움 — "
                                              f"꼭대기 z {r.get('top_z_before')}→{r.get('top_z_after')}m 고정")
                                             if r.get("mode") == "cloth" else
                                             (f"강체 {len(r.get('settled', []))}개 {r.get('frames')}프레임 낙하→"
                                              "키프레임 굽기 완료 — 안착 z: "
                                              + ", ".join(f"{s['name']}={s['z']}" for s in r.get("settled", [])[:5]))),
                    "sculpt_displace": lambda: (
                        f"'{r.get('pattern')}' 요철을 {len(r.get('displaced', []))}개 메시 표면에 새김 "
                        f"(깊이 {r.get('strength')}m · 무늬 크기 {r.get('feature')}m · "
                        f"면 분할 {r.get('subdiv')}단) — 면 {r.get('polys_before', 0):,}→"
                        f"{r.get('polys_after', 0):,}"
                        "\n  · ⚠표면만 거칠게 한 것입니다 — 형태 자체가 틀렸다면 이걸로는 안 고쳐집니다. "
                        "폴리가 많이 늘었으니 유니티로 보낼 때는 decimate+bake(노멀맵)를 세트로 쓰세요.")}[action]()
            msg = f"사본에 반영했습니다: {copy}\n  · {note}"
            # 폴리를 바꾸는 수술은 결과를 모바일 예산과 대조(판단력 2층 — 자 대기)
            if action in ("bevel", "solidify", "decimate", "boolean", "mirror", "curve_path",
                          "sculpt_displace"):
                msg += _budget_note_polys(r.get("polys_after") or r.get("polys"))
            if r.get("preview"):
                msg += f"\n  · 미리보기: {r['preview']} (웹에서 바로 보임)"
                eye_point = (_EYE_POINTS["physics_bake_cloth"]
                             if action == "physics_bake" and r.get("mode") == "cloth" else None)
                eye = ""
                # 전/후 비교 판정(세션63 6부): "의도한 변화가 실제로 일어났나"는 후 한 장의
                # 절대 판단보다 전후 비교가 훨씬 정확함 — 형태 바뀌는 수술만, 렌더 1회 추가 비용.
                if (action in _COMPARE_ACTIONS
                        and _config.get("blender", {}).get("eye_compare", True)):
                    pair = _blender_before_after(
                        path, r["preview"], folder, os.path.splitext(os.path.basename(copy))[0])
                    if pair:
                        msg += f"\n  · 전/후 비교: {pair}"
                        eye = _eye_look(
                            "블렌더 작업 **전(왼쪽)과 후(오른쪽)**를 나란히 붙인 점검용 렌더입니다"
                            "(회색 재질·단순 조명, 앵글이 약간 다를 수 있음 — 미적 평가 금지). "
                            "의도한 변화: " + _WHAT + ". "
                            + _COMPARE_NOTES.get(action, ""),
                            "그 변화가 오른쪽에 실제로 보이는가? 의도 밖의 파손(사라짐·깨짐·"
                            "엉뚱한 변형)이 생겼는가?" + ((" " + eye_point) if eye_point else ""),
                            pair, gate_key="blender")
                if not eye:
                    eye = _blender_eye(action, r["preview"], eye_point)
                msg += eye
            return msg + "\n(원본 .blend는 그대로입니다. 확인 후 원본을 이 사본으로 바꾸시면 됩니다.)"

        if action == "prep_unity":               # 유니티용 한 방(적용+원점+정리+FBX) + 자동 검증
            copy = blender3d.work_copy(path)
            fbx_dest = os.path.join(folder, f"{stem}.fbx")
            if os.path.exists(fbx_dest):
                fbx_dest = os.path.join(folder, f"{stem}_{time.strftime('%H%M%S')}.fbx")
            if not _confirm(f"{os.path.basename(path)} — 유니티용 정리(스케일·회전 적용+바닥 원점"
                            "+정리) 후 FBX로 내보낼까요? 원본은 그대로, 사본과 FBX만 만듭니다."):
                os.remove(copy)
                return "사용자가 거부했습니다."
            try:
                r = blender3d.run("prep_unity", copy, _config, fbx_dest=fbx_dest,
                                  preview_dir=folder,
                                  stem=os.path.splitext(os.path.basename(copy))[0])
            except Exception:
                if os.path.isfile(copy):
                    os.remove(copy)
                raise
            out_fbx = r.get("exported", fbx_dest)
            ok_fbx = os.path.isfile(out_fbx) and os.path.getsize(out_fbx) >= 1024
            verify = ("스케일 1로 적용됨 ✅" if r.get("scale_ok")
                      else f"⚠스케일이 안 맞는 메시: {r.get('bad_scale')}")
            msg = (f"유니티용 정리 완료 (사본: {os.path.basename(copy)})\n"
                   f"  · 적용 메시 {r.get('applied')}개 · 정점 {r.get('removed_verts', 0)}개 정리 "
                   f"· 폴리 {r.get('polys', 0):,}\n"
                   f"  · 바닥 원점 이동 {r.get('moved_by')}\n"
                   f"  · 검증: {verify}\n")
            if ok_fbx:
                sz = os.path.getsize(out_fbx)
                human = f"{sz / (1024 * 1024):.1f}MB" if sz >= 1024 * 1024 else f"{sz / 1024:.0f}KB"
                msg += f"  · FBX: {out_fbx} ({human}) — 유니티에 끌어다 놓으면 됩니다."
            else:
                msg += f"  · ⚠FBX 결과가 이상합니다({out_fbx}) — 블렌더에서 확인하세요."
            return msg

        if action == "unity_export":             # 유니티 안전 익스포트(텍스처가 갈색으로 사라지는 문제 방지)
            bake = bool(args.get("bake_decal"))
            dest = os.path.join(folder, f"{stem}_unity.fbx")
            if os.path.exists(dest):
                dest = os.path.join(folder, f"{stem}_unity_{time.strftime('%H%M%S')}.fbx")
            what = ("텍스처 이름을 ASCII로 고치고, FBX에 텍스처를 박아(embed) 내보냅니다"
                    + (", 투명 데칼은 색 위에 구워 불투명화합니다" if bake else "")
                    + ". 내보낸 뒤 다시 불러 검증까지 합니다")
            if not _confirm(f"{os.path.basename(path)} — 유니티 안전 익스포트? {what}. "
                            f"원본 .blend는 그대로, FBX만 새로 만듭니다 → {os.path.basename(dest)}"):
                return "사용자가 거부했습니다."
            kw = {"dest": dest}
            if bake:
                kw["bake_decal"] = True
                if args.get("bg"):               # [r,g,b] 0~1 배경색(선택) — 없으면 재질 기본색
                    kw["bg"] = args["bg"]
            r = blender3d.run("unity_export", path, _config, **kw)
            out_fbx = r.get("dest", dest)
            ok = os.path.isfile(out_fbx) and os.path.getsize(out_fbx) >= 1024
            v = r.get("verify", {})
            L = [f"유니티 안전 익스포트 완료 (원본 .blend는 그대로)"]
            if r.get("renamed_textures"):
                L.append(f"  · 텍스처 ASCII화: {', '.join(r['renamed_textures'][:6])}")
            if r.get("baked_materials"):
                L.append(f"  · 투명 데칼 구움(불투명화): {', '.join(r['baked_materials'])} "
                         "— 유니티에서 투명 설정 필요 없음 ✅")
            if r.get("missing_images"):
                L.append(f"  · ⚠ 픽셀이 없어 못 담은 텍스처: {', '.join(r['missing_images'])} "
                         "(블렌더에서 이미지 경로를 고쳐야 함)")
            if ok:
                sz = os.path.getsize(out_fbx)
                human = f"{sz / 1048576:.1f}MB" if sz >= 1048576 else f"{sz / 1024:.0f}KB"
                L.append(f"  · FBX: {out_fbx} ({human})")
            else:
                L.append(f"  · ⚠ FBX 결과가 이상합니다({out_fbx}) — 블렌더에서 확인하세요.")
            if v.get("error"):
                L.append(f"  · 검증 실패: {v['error']}")
            elif "count" in v:
                mark = "✅" if (v.get("all_ascii") and v.get("all_packed")) else "⚠"
                L.append(f"  · 검증(FBX 재확인): 텍스처 {v['count']}개 박힘 "
                         f"{mark} 이름 ASCII={v.get('all_ascii')}·픽셀 포함={v.get('all_packed')}")
            if r.get("alpha_materials"):
                L.append(f"  · ⚠ 투명 재질 {', '.join(r['alpha_materials'])} 남아 있음 — 유니티에서 "
                         "재질을 Transparent로 바꾸거나, bake_decal=true로 다시 내보내면 그 설정도 불필요")
            L.append("  → 이 FBX 하나만 개발자에게 넘기면 됩니다. 텍스처 따로 안 보내도 됨.")
            return "\n".join(L)

        if action == "chain":                    # 여러 작업을 한 부팅에(콜드부팅 세금 절약)
            raw = args.get("ops")
            ops = [o.strip().lower() for o in
                   (raw.split(",") if isinstance(raw, str) else (raw or [])) if str(o).strip()]
            valid = ("apply", "cleanup", "decimate", "uv", "origin", "join")
            ops = [o for o in ops if o in valid]
            if not ops:
                return ("chain은 ops에 순서대로 할 작업을 주세요(쉼표 구분): "
                        + ", ".join(valid) + ". 예: ops=\"apply,cleanup,decimate\"")
            export = str(args.get("export", "")).lower()
            export = export if export in ("fbx", "glb") else ""
            copy = blender3d.work_copy(path)
            fbx_dest = None
            if export:
                fbx_dest = os.path.join(folder, f"{stem}.{export}")
                if os.path.exists(fbx_dest):
                    fbx_dest = os.path.join(folder, f"{stem}_{time.strftime('%H%M%S')}.{export}")
            desc = " → ".join(ops) + (f" → {export.upper()} 내보내기" if export else "")
            if not _confirm(f"{os.path.basename(path)} — [{desc}]를 한 번에? "
                            "원본은 그대로, 사본에만 반영합니다."):
                os.remove(copy)
                return "사용자가 거부했습니다."
            kw = {"ops": ops, "preview_dir": folder,
                  "stem": os.path.splitext(os.path.basename(copy))[0]}
            if "decimate" in ops:
                kw["ratio"] = float(args.get("ratio", 0.5))
            if export:
                kw["export"] = export
                kw["export_dest"] = fbx_dest
            try:
                r = blender3d.run("chain", copy, _config, **kw)
            except Exception:
                if os.path.isfile(copy):
                    os.remove(copy)
                raise
            msg = f"한 번에 처리했습니다 (사본: {os.path.basename(copy)})\n  · 순서: {' → '.join(ops)}"
            if r.get("exported"):
                out_f = r["exported"]
                if os.path.isfile(out_f) and os.path.getsize(out_f) >= 1024:
                    sz = os.path.getsize(out_f)
                    human = f"{sz / 1048576:.1f}MB" if sz >= 1048576 else f"{sz / 1024:.0f}KB"
                    msg += f"\n  · 내보냄: {out_f} ({human})"
                else:
                    msg += f"\n  · ⚠내보내기 결과가 이상합니다({out_f})"
            return msg + "\n(원본 .blend는 그대로입니다.)"

        fmt = "glb" if str(args.get("format", "")).lower() == "glb" else "fbx"
        dest = os.path.join(folder, f"{stem}.{fmt}")
        if os.path.exists(dest):
            dest = os.path.join(folder, f"{stem}_{time.strftime('%H%M%S')}.{fmt}")
        if not _confirm(f"{os.path.basename(path)}를 {fmt.upper()}로 내보낼까요? → {dest}"):
            return "사용자가 거부했습니다."
        r = blender3d.run("export", path, _config, format=fmt, dest=dest)
        out = r.get("exported", dest)
        if not os.path.isfile(out) or os.path.getsize(out) < 1024:
            return f"⚠ 내보내기가 됐다고 했지만 파일이 이상합니다({out}) — 블렌더에서 직접 확인해 보세요."
        mb = os.path.getsize(out) / (1024 * 1024)
        return f"내보냈습니다: {out} ({mb:.1f}MB) — 유니티에 끌어다 놓으면 됩니다."
    except subprocess.TimeoutExpired:
        return "블렌더가 5분 안에 끝나지 않아 중단했습니다 — 파일이 너무 크거나 걸린 것 같습니다."
    except RuntimeError as e:
        return str(e)


def _mmss(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


def edit_video(args):
    """
    동영상 편집(video.py가 ffmpeg를 부림). 원본은 안 건드리고 항상 새 파일을 만듭니다.
    인코딩은 몇 분씩 걸릴 수 있어 확인 게이트 뒤에 둡니다.
    """
    import video

    if not video.ready(_config):
        return video.INSTALL_GUIDE

    action = str(args.get("action") or "").strip().lower()
    if action not in video.ACTIONS:
        return f"오류: action은 {', '.join(video.ACTIONS)} 중 하나여야 합니다."

    if action == "join":
        raw = args.get("paths") or []
        if isinstance(raw, str):
            raw = [p for p in re.split(r"[,\n]", raw) if p.strip()]
        paths = []
        for p in raw:
            found = _find_media(p)
            if not found:
                return f"이어붙일 파일을 찾지 못했습니다: {p}"
            paths.append(found)
        if len(paths) < 2:
            return "오류: join은 paths에 파일 2개 이상이 필요합니다."
        src, kw = paths[0], {"paths": paths}
        what = f"{len(paths)}개 영상 이어붙이기"
    else:
        src = _find_media(args.get("path"))
        if not src:
            return (f"동영상을 찾지 못했습니다: {args.get('path')} "
                    "(경로를 모르면 find_files로 먼저 찾으세요)")
        kw = {"path": src}
        what = {"trim": f"{args.get('start')}~{args.get('end')} 구간 자르기",
                "audio": "소리만 추출(mp3)",
                "convert": "형식 변환/압축",
                "speed": f"{args.get('rate')}배속",
                "gif": "GIF 만들기",
                "frame": f"{args.get('at') or '0'} 지점 장면 캡처",
                "subtitle": (f"자막 입히기(SRT: {args.get('srt')})" if args.get("srt")
                             else "말소리를 받아써 자막 만들어 입히기")}[action]

    before = video.probe(src, _config)
    length = f", 원본 {_mmss(before.get('duration'))} · {before.get('size', 0) // 1048576}MB" if before else ""
    if not _confirm(f"{src} — {what}{length} (몇 분 걸릴 수 있음)"):
        return "사용자가 거부했습니다. 편집하지 않았습니다."

    try:
        made = video.edit(action, config=_config, output=args.get("output"),
                          start=args.get("start"), end=args.get("end"),
                          rate=args.get("rate"), width=args.get("width"),
                          at=args.get("at"), srt=args.get("srt"), **kw)
    except subprocess.TimeoutExpired:
        return "시간 초과 — 영상이 너무 깁니다. config의 video.timeout을 늘리거나 구간을 줄여 보세요."
    except (ValueError, RuntimeError) as e:
        msg = str(e)
        if action == "join" and "ffmpeg 실패" in msg:
            msg += "\n(형식이 서로 다른 영상은 못 이어붙입니다 — convert로 같은 형식으로 맞춘 뒤 다시)"
        return f"편집하지 못했습니다: {msg} (원본은 그대로입니다)"

    # 되읽어 확인 — 파일이 실제로 생겼고 깡통(0초·0바이트)이 아닌지.
    after = video.probe(made, _config)
    if not os.path.isfile(made) or os.path.getsize(made) < 100:
        return f"편집 결과가 비어 있습니다: {made} — 다른 조건으로 다시 시도해 보세요."
    detail = ""
    if after.get("duration"):
        detail = f" ({_mmss(after['duration'])}, {max(1, after.get('size', 0) // 1048576)}MB)"
    elif after.get("size"):
        detail = f" ({max(1, after['size'] // 1048576)}MB)"
    tip = " 받아쓰려면 이 mp3로 transcribe_audio를 부르면 됩니다." if action == "audio" else ""
    if action == "subtitle" and not args.get("srt"):
        auto_srt = os.path.splitext(made)[0] + ".srt"
        if os.path.isfile(auto_srt):
            tip = (f"\n자막 원고도 남겼습니다: {auto_srt} — 받아쓰기가 틀린 데가 있으면 "
                   "사용자가 이 파일을 고친 뒤 srt로 지정해 다시 입힐 수 있습니다(둘 다 알려줘라).")
    return f"편집했습니다: {made}{detail}\n사용자에게 이 경로를 알려줘라.{tip}"


def list_dir(args):
    path_arg = args.get("path")
    if not path_arg:
        return "오류: 'path' 매개변수가 필요합니다."
    path = _check_path(path_arg)
    entries = []
    for name in sorted(os.listdir(path))[:200]:
        full = os.path.join(path, name)
        entries.append(f"{name}/" if os.path.isdir(full) else f"{name}  ({os.path.getsize(full)}바이트)")
    return "\n".join(entries) or "(빈 폴더)"


UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def _get_json(url, data=None, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    if data is not None:
        data = json.dumps(data).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _search_tavily(query, key):
    d = _get_json("https://api.tavily.com/search",
                  data={"query": query, "max_results": 5},
                  headers={"Authorization": f"Bearer {key}"})
    return [(r["title"], r.get("content", "")[:300], r["url"]) for r in d.get("results", [])]


def _search_brave(query, key):
    url = "https://api.search.brave.com/res/v1/web/search?count=5&q=" + urllib.parse.quote(query)
    d = _get_json(url, headers={"X-Subscription-Token": key, "Accept": "application/json"})
    out = []
    for r in d.get("web", {}).get("results", []):
        desc = html.unescape(re.sub(r"<[^>]+>", "", r.get("description", "")))
        out.append((r["title"], desc[:300], r["url"]))
    return out


def _search_wikipedia(query, _key):
    """키가 필요 없는 최후의 검색 수단. 백과사전이라 시사·최신 정보엔 약합니다."""
    api = "https://ko.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=5&srsearch="
    d = _get_json(api + urllib.parse.quote(query))
    out = []
    for r in d.get("query", {}).get("search", []):
        title = r["title"]
        snippet = html.unescape(re.sub(r"<[^>]+>", "", r.get("snippet", "")))
        out.append((title, snippet, "https://ko.wikipedia.org/wiki/" + urllib.parse.quote(title)))
    return out


_SEARCH_FUNCS = {"tavily": _search_tavily, "brave": _search_brave, "wikipedia": _search_wikipedia}


def _search(query):
    """
    검색 백엔드를 순서대로 시도합니다(모델 라우터와 같은 철학).
    돌려주는 값: (백엔드 이름, [(제목, 요약, 주소), ...], 실패한 백엔드 목록)

    HTML을 긁는 방식(DuckDuckGo 등)은 전부 봇 차단으로 막혔습니다 — 그래서 쓰지 않습니다.
    Tavily는 무료 키가 있으면 진짜 웹 검색이 되고, 키가 없어도 위키백과가 항상 받쳐줍니다.
    """
    problems = []
    for backend in _config.get("search_backends", [{"type": "wikipedia"}]):
        kind = backend["type"]
        fn = _SEARCH_FUNCS.get(kind)
        if not fn:
            continue

        key = None
        if backend.get("key_file"):
            path = os.path.join(BASE_DIR, backend["key_file"])
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8-sig") as f:
                    key = f.readline().strip()
            if not key:
                problems.append(f"{kind}: 키 없음")
                continue

        try:
            results = fn(query, key)
        except Exception as e:
            problems.append(f"{kind}: {type(e).__name__}")
            continue

        if results:
            return kind, results, problems
        problems.append(f"{kind}: 결과 없음")

    return None, [], problems


def web_search(args):
    """빠른 검색. 제목·요약·주소만 돌려줍니다."""
    query = args.get("query")
    if not query:
        return "오류: 'query' 매개변수가 필요합니다."
    kind, results, problems = _search(query)
    if not results:
        return ("검색에 실패했습니다. 이 정보는 알 수 없습니다. 추측하지 말고 모른다고 답하세요.\n"
                "(시도한 백엔드: " + ", ".join(problems) + ")")
    body = "\n".join(f"- {t}\n  {s}\n  {u}" for t, s, u in results)
    return f"[{kind} 검색 결과]\n{body}"


def _page_text(url, limit=6000):
    """웹페이지 본문을 텍스트로. 실패하면 빈 문자열(리서치가 중간에 죽지 않게)."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return ""
            page = resp.read(600000).decode("utf-8", errors="replace")
    except Exception:
        return ""
    page = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _relevant_bits(text, terms, span=400, keep=3):
    """페이지 전문을 다 싣지 않고, 검색어가 나온 대목만 앞뒤로 잘라 담습니다."""
    if not text:
        return ""
    low = text.lower()
    bits, used = [], []
    for term in terms:
        idx = low.find(term.lower())
        if idx < 0 or any(abs(idx - u) < span for u in used):
            continue
        used.append(idx)
        bits.append("…" + text[max(0, idx - span // 3): idx + span] + "…")
        if len(bits) >= keep:
            break
    return " ".join(bits) or text[:span * 2]


def research(args):
    """
    깊은 조사. 검색 한 번으로 끝내지 않고:
      1) 검색어를 여러 개(질문 그대로 + 사용자가 준 보조 검색어)로 돌리고
      2) 상위 결과 페이지를 실제로 열어 본문을 읽고
      3) 검색어가 나온 대목만 추려 출처와 함께 돌려줍니다.
    스니펫만 보고 답하는 것보다 훨씬 정확합니다. 대신 20~40초 걸립니다.
    """
    question = args.get("question")
    if not question:
        return "오류: 'question' 매개변수가 필요합니다."
    queries = [question] + [q for q in (args.get("queries") or []) if q][:3]
    depth = int(args.get("depth", 3))          # 실제로 열어볼 페이지 수

    seen, blocks, sources = set(), [], []
    terms = [w for w in re.split(r"[\s,?!]+", question) if len(w) > 1][:6]

    for query in queries:
        kind, results, _ = _search(query)
        for title, snippet, url in results:
            if url in seen or len(sources) >= depth:
                continue
            seen.add(url)
            body = _relevant_bits(_page_text(url), terms) or snippet
            sources.append(url)
            blocks.append(f"[출처 {len(sources)}] {title}\n{body}\n{url}")
        if len(sources) >= depth:
            break

    if not blocks:
        return "조사에 실패했습니다(검색 결과 없음). 추측하지 말고 모른다고 답하세요."

    return (
        f"[조사 결과 — 검색어 {len(queries)}개, 페이지 {len(sources)}개를 직접 읽음]\n\n"
        + "\n\n".join(blocks)
        + "\n\n위 내용만 근거로 답하되, 출처들이 서로 어긋나면 그 사실을 밝혀라. "
          "답에는 근거가 된 주소를 함께 적어라. 여기 없는 내용은 지어내지 마라."
    )


def fetch_url(args):
    """웹페이지 본문을 텍스트로 가져옵니다."""
    url = args.get("url")
    if not url:
        return "오류: 'url' 매개변수가 필요합니다."
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        page = resp.read().decode("utf-8", errors="replace")
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:15000]


# ── 오피스 문서 읽기 ──────────────────────────────────────────────
# docx·xlsx·pptx는 사실 ZIP 안에 XML이 든 파일입니다. 그래서 표준 라이브러리(zipfile+xml)만으로
# 읽을 수 있습니다 — python-docx·openpyxl·python-pptx를 설치하지 않아도 됩니다.
# ("pip 설치 불필요"가 이 비서의 핵심 설계라, 그걸 깨지 않으려고 직접 파싱합니다)
# PDF만 예외입니다. 압축된 바이너리라 표준 라이브러리로는 무리라서, pypdf가 있으면 쓰고 없으면 안내합니다.

def _xml_texts(zf, name, tag):
    """ZIP 안의 XML에서 특정 태그의 글자만 뽑아냅니다."""
    try:
        root = ElementTree.fromstring(zf.read(name))
    except (KeyError, ElementTree.ParseError):
        return []
    # 네임스페이스가 {...}t 형태로 붙어 있어서 뒤쪽 이름만 비교합니다.
    return [(e.text or "") for e in root.iter() if e.tag.rsplit("}", 1)[-1] == tag]


def _read_docx(zf):
    root = ElementTree.fromstring(zf.read("word/document.xml"))
    lines = []
    for para in root.iter():
        if para.tag.rsplit("}", 1)[-1] != "p":
            continue
        text = "".join(e.text or "" for e in para.iter()
                       if e.tag.rsplit("}", 1)[-1] == "t")
        if text.strip():
            lines.append(text)
    return "\n".join(lines)


def _read_pptx(zf):
    slides = sorted(n for n in zf.namelist()
                    if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
    slides.sort(key=lambda n: int(re.search(r"(\d+)", n).group(1)))

    out = []
    for i, name in enumerate(slides, 1):
        texts = [t for t in _xml_texts(zf, name, "t") if t.strip()]
        notes_name = f"ppt/notesSlides/notesSlide{i}.xml"
        notes = [t for t in _xml_texts(zf, notes_name, "t") if t.strip()]
        block = [f"── 슬라이드 {i} ──"] + texts
        if notes:
            block.append("[발표자 노트] " + " ".join(notes))
        out.append("\n".join(block))
    return "\n\n".join(out)


def _read_hwpx(zf):
    """한글(HWPX)을 읽습니다. HWPX = zip 속 OWPML(XML) — 본문은 Contents/section*.xml의
    <hp:t> 텍스트에 삽니다. 태그 이름 끝만 보고 관대하게 뽑아 한컴 버전 차이를 흡수합니다
    (docx의 w:t를 읽는 것과 같은 사상). 표 안 글자도 같은 t 노드라 함께 나옵니다."""
    sections = sorted(n for n in zf.namelist()
                      if re.fullmatch(r"Contents/section\d+\.xml", n))
    sections.sort(key=lambda n: int(re.search(r"(\d+)", n).group(1)))
    if not sections:
        raise KeyError("Contents/section0.xml")
    lines = []
    for name in sections:
        root = ElementTree.fromstring(zf.read(name))
        # ⚠️한글은 표가 문단 **안에** 삽니다(hp:p > run > tbl > 셀 > hp:p) — docx처럼
        # '문단마다 t를 다 모으면' 바깥 문단이 표 전체를 또 한 줄로 만들어 겹칩니다.
        # 그래서 t마다 '가장 가까운 조상 문단'을 찾아 그 문단에만 넣습니다.
        parent = {child: el for el in root.iter() for child in el}
        buckets = {}                          # p 노드 → [글자들] (파이썬 dict = 문서 순서 유지)
        for el in root.iter():
            if el.tag.rsplit("}", 1)[-1] == "p":
                buckets.setdefault(el, [])
        for el in root.iter():
            if el.tag.rsplit("}", 1)[-1] != "t":
                continue
            node = parent.get(el)
            while node is not None and node.tag.rsplit("}", 1)[-1] != "p":
                node = parent.get(node)
            if node is not None:
                buckets.setdefault(node, []).append(el.text or "")
        for texts in buckets.values():
            line = "".join(texts)
            if line.strip():
                lines.append(line)
        if not buckets:                       # 문단이 아예 없는 희귀 변형 — t라도 긁습니다
            lines += [t for t in _xml_texts(zf, name, "t") if t.strip()]
    return "\n".join(lines)


def _col_index(ref):
    """'BC12' → 열 번호(0부터). 빈 칸을 건너뛴 자리를 맞추기 위해 필요합니다."""
    letters = re.match(r"([A-Z]+)", ref or "")
    if not letters:
        return 0
    n = 0
    for ch in letters.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _read_xlsx(zf, max_rows=200):
    shared = _xml_texts(zf, "xl/sharedStrings.xml", "t")
    names = [(e.get("name"), e.get("sheetId"))
             for e in ElementTree.fromstring(zf.read("xl/workbook.xml")).iter()
             if e.tag.rsplit("}", 1)[-1] == "sheet"]

    sheets = sorted(n for n in zf.namelist()
                    if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
    out = []
    for idx, path in enumerate(sheets):
        title = names[idx][0] if idx < len(names) else path
        root = ElementTree.fromstring(zf.read(path))
        rows = []
        for row in root.iter():
            if row.tag.rsplit("}", 1)[-1] != "row":
                continue
            cells = {}
            for c in row:
                ref = c.get("r", "")
                value = ""
                for child in c:
                    tag = child.tag.rsplit("}", 1)[-1]
                    if tag == "v":
                        value = child.text or ""
                    elif tag == "is":                    # 인라인 문자열
                        value = "".join(t.text or "" for t in child.iter()
                                        if t.tag.rsplit("}", 1)[-1] == "t")
                if c.get("t") == "s" and value.isdigit():   # 공유 문자열 테이블 참조
                    value = shared[int(value)] if int(value) < len(shared) else ""
                if value:
                    cells[_col_index(ref)] = value
            if cells:
                width = max(cells) + 1
                rows.append("\t".join(cells.get(i, "") for i in range(width)))
            if len(rows) >= max_rows:
                rows.append(f"... ({max_rows}행까지만 표시)")
                break
        if rows:
            out.append(f"── 시트: {title} ──\n" + "\n".join(rows))
    return "\n\n".join(out)


def _read_pdf(path):
    try:
        from pypdf import PdfReader                       # 있으면 쓰고
    except ImportError:
        try:
            from PyPDF2 import PdfReader                  # 옛 이름도 받아줍니다
        except ImportError:
            return ("PDF를 읽으려면 pypdf가 필요합니다(이것만 표준 라이브러리로 안 됩니다).\n"
                    "설치: pip install pypdf\n"
                    "설치하기 싫으면, 그 PDF를 워드나 브라우저로 열어 텍스트로 저장한 뒤 읽어달라고 하세요.")
    reader = PdfReader(path)
    return "\n\n".join(f"── {i}쪽 ──\n{(p.extract_text() or '').strip()}"
                       for i, p in enumerate(reader.pages, 1))


def read_document(args):
    """워드·엑셀·파워포인트·PDF를 읽습니다. 설치할 것 없이 표준 라이브러리로 파싱합니다(PDF 제외)."""
    path = _check_path(args["path"])
    if not os.path.exists(path):
        return f"파일이 없습니다: {path}"

    ext = os.path.splitext(path)[1].lower()
    limit = int(args.get("limit", 20000))

    if ext == ".pdf":
        text = _read_pdf(path)
    elif ext in (".docx", ".xlsx", ".pptx", ".hwpx"):
        try:
            with zipfile.ZipFile(path) as zf:
                if ext == ".docx":
                    text = _read_docx(zf)
                elif ext == ".pptx":
                    text = _read_pptx(zf)
                elif ext == ".hwpx":
                    text = _read_hwpx(zf)
                else:
                    text = _read_xlsx(zf)
        except zipfile.BadZipFile:
            return (f"{ext} 파일이 아니거나 손상됐습니다. "
                    "(구버전 .doc/.xls/.ppt는 형식이 완전히 달라서 읽을 수 없습니다 — "
                    "오피스에서 열어 최신 형식으로 저장해 주세요)")
    elif ext == ".hwp":
        return ("구형 .hwp(바이너리)는 못 읽습니다 — 한글에서 열어 '다른 이름으로 저장'에서 "
                "HWPX 형식으로 저장하면 읽을 수 있습니다(2014 이후 한글은 기본 지원).")
    else:
        return f"{ext}는 read_document로 못 읽습니다. 텍스트 파일이면 read_file을 쓰세요."

    if not text.strip():
        return "문서에서 글자를 찾지 못했습니다(그림만 든 문서일 수 있습니다)."
    if len(text) > limit:
        return text[:limit] + f"\n\n... (전체 {len(text)}자 중 {limit}자까지만 표시)"
    return text


def search_files(args):
    """
    PC에 널려 있는 문서를 내용으로 찾습니다. "작년에 쓴 그 계약서 어디 있지?"

    색인은 처음 부를 때 만듭니다. 시작할 때 미리 만들지 않는 이유: 루시를 켤 때마다
    수백 개 파일을 파싱하면 켜는 데만 몇 분이 걸립니다. 정작 문서를 찾는 일은 가끔이므로,
    필요할 때 만들고 그다음부터는 바뀐 파일만 다시 읽습니다(증분).
    """
    import docsearch

    if not docsearch.enabled(_config):
        return "문서 검색이 꺼져 있습니다 (config의 filesearch.enabled)."

    query = str(args.get("query", "")).strip()
    if not query:
        return "무엇을 찾을지 검색어가 필요합니다."

    hours = _config.get("filesearch", {}).get("refresh_hours", 24)
    rebuilt = False
    if docsearch.stale(_config, hours=hours):
        print("  [문서색인] 색인을 갱신합니다 (처음이면 몇 분 걸릴 수 있습니다)...")
        added, total, failed = docsearch.build(_config)
        print(f"  [문서색인] 문서 {total}개 (새로 읽음 {added}개"
              + (f", 못 읽음 {failed}개" if failed else "") + ")")
        rebuilt = True

    hits = docsearch.search(_config, query, top_k=int(args.get("top_k", 5)))
    if not hits and not rebuilt:
        # 색인이 24시간 규칙으로는 '신선'해도 방금 받은 파일은 아직 색인 밖입니다.
        # 빈손일 때만 증분 색인(바뀐 파일만 — 대개 1~2초)을 돌리고 한 번 더 찾습니다.
        docsearch.build(_config)
        hits = docsearch.search(_config, query, top_k=int(args.get("top_k", 5)))
    if not hits:
        return (f"'{query}'와 맞는 문서를 PC에서 찾지 못했습니다. "
                "다른 낱말로 다시 찾아보거나, 검색 범위(config filesearch.roots) 밖일 수 있습니다.")

    lines = [f"'{query}' 검색 결과 {len(hits)}건 (내용을 보려면 read_document에 경로를 넘겨라):"]
    for i, h in enumerate(hits, 1):
        lines.append(f"\n{i}. {h['name']}  (수정 {h['when']})\n"
                     f"   경로: {h['path']}\n"
                     f"   내용: {h['snippet']}")
    return "\n".join(lines)


# ── 메일·캘린더 ───────────────────────────────────────────────────
def _google_off():
    return not _config.get("google", {}).get("enabled", True)


def check_mail(args):
    """지메일을 읽습니다(읽기 전용 — 루시는 사용자 이름으로 메일을 보내지 않습니다)."""
    import gmail_calendar as gc
    if _google_off():
        return "메일 연동이 꺼져 있습니다 (config의 google.enabled)."
    if not gc.ready():
        return gc.SETUP_GUIDE

    query = str(args.get("query") or "is:unread").strip()
    try:
        found = gc.mail(query, limit=int(args.get("limit", 10)))
    except Exception as e:
        return f"메일을 읽지 못했습니다: {type(e).__name__}: {e}"

    if not found:
        return f"'{query}'에 해당하는 메일이 없습니다."

    lines = [f"메일 {len(found)}통 ({query}):"]
    for i, m in enumerate(found, 1):
        lines.append(f"\n{i}. {m['subject']}\n   보낸이: {m['from']}\n"
                     f"   날짜: {m['date']}\n   내용: {m['snippet'][:200]}")
    return "\n".join(lines)


def list_events(args):
    """구글 캘린더의 앞으로의 일정을 봅니다."""
    import gmail_calendar as gc
    if _google_off():
        return "캘린더 연동이 꺼져 있습니다 (config의 google.enabled). 장기 메모(notes.md)나 대화록(search_memory / read_notes)을 확인하십시오."
    if not gc.ready():
        return gc.SETUP_GUIDE + "\n(구글 캘린더 미연동 상태입니다. 장기 메모(notes.md)나 대화록(search_memory / read_notes)에서 일정을 확인하십시오.)"

    days = int(args.get("days", 7))
    try:
        found = gc.events(days=days)
    except Exception as e:
        return f"일정을 읽지 못했습니다: 캘린더 연동 에러/토큰 만료 (메모 확인 필요): {e}"

    if not found:
        return f"앞으로 {days}일간 구글 캘린더에 등록된 일정이 없습니다. (장기 메모 notes.md 나 대화록 search_memory / read_notes 도 함께 확인하십시오.)"

    lines = [f"앞으로 {days}일간 구글 캘린더 일정 {len(found)}건:"]
    for e in found:
        when = e["when"][:10] if e["allday"] else e["when"][:16].replace("T", " ")
        lines.append(f"  · {when}  {e['title']}" + (f"  @{e['where']}" if e["where"] else ""))
    lines.append("\n(참고: 구글 캘린더 외에 장기 메모나 대화록 search_memory / read_notes 도 다중 검증하세요.)")
    return "\n".join(lines)


def add_event(args):
    """캘린더에 일정을 넣습니다. 되돌릴 수 있는 일이지만 그래도 확인을 받고 넣습니다."""
    import gmail_calendar as gc
    if _google_off():
        return "캘린더 연동이 꺼져 있습니다 (config의 google.enabled)."
    if not gc.ready():
        return gc.SETUP_GUIDE

    title = str(args.get("title") or "").strip()
    start = str(args.get("start") or "").strip()
    if not title or not start:
        return "일정 제목(title)과 시작 시각(start)이 필요합니다."

    # 참석자를 넣으면 구글이 초대 메일을 **보냅니다** — 밖으로 나가는 일이므로
    # 확인 문구에 반드시 명시합니다(일정만 넣는 줄 알고 y를 누르면 안 됩니다).
    guests = [a.strip() for a in str(args.get("attendees") or "").replace(";", ",").split(",")
              if "@" in a]
    ask = f"캘린더에 '{title}' ({start}) 일정을 넣을까요?"
    if guests:
        ask = (f"캘린더에 '{title}' ({start}) 일정을 넣고, "
               f"{', '.join(guests)} 에게 **초대 메일을 보낼까요**?")
    if not _confirm(ask, risk="write"):
        return "사용자가 거절했습니다."
    try:
        link = gc.add_event(title, start, args.get("end"),
                            str(args.get("description") or ""), attendees=guests)
    except Exception as e:
        return f"일정을 넣지 못했습니다: {type(e).__name__}: {e}"
    invited = f" 참석자 {len(guests)}명에게 초대장을 보냈습니다." if guests else ""
    return f"'{title}' 일정을 {start}에 넣었습니다.{invited} {link}"


def draft_mail(args):
    """메일 초안을 초안함에 만듭니다 — 보내지 않습니다(발송 버튼은 사람 몫)."""
    import gmail_calendar as gc
    if _google_off():
        return "메일 연동이 꺼져 있습니다 (config의 google.enabled)."
    if not gc.ready():
        return gc.SETUP_GUIDE

    subject = str(args.get("subject") or "").strip()
    body = str(args.get("body") or "").strip()
    to = str(args.get("to") or "").strip()
    if not subject and not body:
        return "제목(subject)이나 본문(body)이 필요합니다."
    try:
        gc.create_draft(to, subject, body)
    except Exception as e:
        return f"초안을 만들지 못했습니다: {type(e).__name__}: {e}"
    return (f"'{subject or '(제목 없음)'}' 초안을 지메일 초안함에 만들었습니다"
            + (f" (받는이: {to})" if to else "")
            + ". 내용을 확인하고 보내기는 지메일에서 직접 누르세요 — 저는 보낼 수 없습니다.")


def transcribe_audio(args):
    """녹음 파일을 글로 받아씁니다(마이크가 아니라 **이미 있는 파일**용)."""
    import voice

    path = str(args.get("path") or "").strip().strip('"')
    if not path:
        return "받아쓸 녹음 파일 경로(path)가 필요합니다."
    if not os.path.isfile(path):
        # 파일명만 말했으면 올린 파일·바탕화면·다운로드에서 찾아봅니다(vision과 같은 예의)
        base = os.path.basename(path)
        for root in (os.path.join(BASE_DIR, "uploads"),
                     os.path.join(os.path.expanduser("~"), "Desktop"),
                     os.path.join(os.path.expanduser("~"), "Downloads")):
            cand = os.path.join(root, base)
            if os.path.isfile(cand):
                path = cand
                break
        else:
            return f"파일을 찾지 못했습니다: {path}"

    if os.path.getsize(path) > 24 * 1024 * 1024:
        return "파일이 24MB를 넘어 받아쓸 수 없습니다(Groq 상한). 잘라서 다시 시도해 주세요."

    conf = _config.get("voice", {})
    key_file = conf.get("key_file") or "keys/groq.txt"
    try:
        with open(os.path.join(BASE_DIR, key_file), "r", encoding="utf-8-sig") as f:
            key = f.read().strip()
    except OSError:
        key = ""
    if not key:
        return "받아쓰기 키(keys/groq.txt)가 없어 쓸 수 없습니다."

    try:
        text = voice.transcribe(path, key,
                                model=conf.get("model", "whisper-large-v3"),
                                language=str(args.get("language") or conf.get("language", "ko")))
    except Exception as e:
        return f"받아쓰지 못했습니다: {type(e).__name__}: {e}"
    return text or "(아무 말도 알아듣지 못했습니다)"


# ── 그림 그리기 (하이브리드 2단계) ────────────────────────────────
# 4GB VRAM으로는 Flux를 로컬에서 돌릴 수 없습니다. 그래서 역할을 나눕니다.
#   1단계 draw   : 온라인 Flux가 구도·손가락·글자가 멀쩡한 뼈대를 그린다 (내 GPU 연산 0)
#   2단계 restyle: 그 그림을 로컬 SD 1.5 병합 모델에 던져 내 화풍으로 덧칠한다 (약한 img2img)
# WebUI가 꺼져 있어도 1단계 결과가 그대로 최종본이 되므로, 그림 기능은 항상 작동합니다.

def _img_cfg(section):
    return _config.get("image", {}).get(section, {})


def _save_dir():
    path = _config.get("image", {}).get("save_dir") or os.path.join(BASE_DIR, "images")
    path = _check_path(path)
    os.makedirs(path, exist_ok=True)
    return path


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _ext_of(data):
    """확장자는 실제 바이트를 보고 정합니다. Pollinations는 이름과 달리 JPEG를 돌려줍니다."""
    if data[:4] == b"\x89PNG":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".img"


_KO_ENG_MAP = {
    "고양이": "cute cat",
    "강아지": "cute dog",
    "수인": "anthropomorphic furry character",
    "퍼리": "furry character",
    "바탕화면": "desktop wallpaper background",
    "풍경": "scenic landscape wallpaper",
    "노을": "sunset warm glow lighting",
    "바다": "ocean beach waves",
    "하늘": "blue sky clouds",
    "소녀": "anime girl illustration",
    "소년": "anime boy illustration",
    "캐릭터": "detailed character concept art",
    "우주": "cosmic galaxy nebula background",
    "도시": "futuristic cyberpunk city skyline",
}


def _expand_prompt(prompt):
    """한국어 그림 요청을 영어 프롬프트로 자동 확장·보정합니다."""
    text = str(prompt or "").strip()
    if not text:
        return "a beautiful detailed illustration, masterpiece, 8k resolution"
    has_ko = bool(re.search(r"[\uac00-\ud7a3]", text))
    if has_ko:
        matched = [eng for ko, eng in _KO_ENG_MAP.items() if ko in text]
        if matched:
            return ", ".join(matched) + ", highly detailed illustration, masterpiece, 8k resolution"
        return f"{text}, highly detailed illustration, masterpiece, 8k resolution"
    if len(text) < 30 and "masterpiece" not in text.lower():
        text += ", highly detailed, masterpiece, 8k resolution"
    return text


def _save_image_file(data, prefix="lucy_draft", save_to_desktop=False):
    """그림 바이트 데이터를 파일로 저장합니다. 바탕화면 지정 시 권한/경로 오류를 안전하게 예외처리합니다."""
    ext = _ext_of(data)
    filename = f"{prefix}_{_stamp()}{ext}"
    primary_dir = _save_dir()
    
    if save_to_desktop:
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        desktop_path = os.path.join(desktop_dir, filename)
        try:
            os.makedirs(desktop_dir, exist_ok=True)
            with open(desktop_path, "wb") as f:
                f.write(data)
            return desktop_path, True, ""
        except (OSError, PermissionError) as e:
            fallback_path = os.path.join(primary_dir, filename)
            with open(fallback_path, "wb") as f:
                f.write(data)
            return fallback_path, False, f"💡 [안내] 바탕화면 저장 권한 제한으로 저장소에 대체 저장되었습니다 ({type(e).__name__})"
    
    path = os.path.join(primary_dir, filename)
    with open(path, "wb") as f:
        f.write(data)
    return path, True, ""


def draw(args):
    """
    [1단계] 온라인 Flux(Pollinations)로 그림의 뼈대를 그립니다. 무료·키 불필요·GPU 연산 0.
    prompt는 반드시 영어로. 한국어로 요청받았으면 모델이 영어 묘사로 옮겨서 넣어야 합니다.
    """
    raw_prompt = str(args.get("prompt") or "").strip()
    if not raw_prompt:
        return "오류: 'prompt' 매개변수가 필요합니다."
    prompt = _expand_prompt(raw_prompt)
    cfg = _img_cfg("flux")
    params = {
        "width": int(args.get("width", cfg.get("width", 1024))),
        "height": int(args.get("height", cfg.get("height", 1024))),
        "model": cfg.get("model", "flux"),
        "nologo": "true",
    }
    if args.get("seed") is not None:
        params["seed"] = int(args["seed"])

    url = (cfg.get("endpoint", "https://image.pollinations.ai/prompt/")
           + urllib.parse.quote(prompt, safe="")
           + "?" + urllib.parse.urlencode(params))

    print(f"\n  [그림] 뼈대를 그리는 중... ({params['width']}x{params['height']}, 온라인 Flux)")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=cfg.get("timeout", 180)) as resp:
        data = resp.read()
    if len(data) < 1000:
        return "그림 생성에 실패했습니다(응답이 너무 작음). 잠시 후 다시 시도하세요."

    want_desktop = bool(args.get("save_to_desktop") or "desktop" in raw_prompt.lower() or "바탕화면" in raw_prompt)
    path, ok, err_msg = _save_image_file(data, prefix="lucy_draft", save_to_desktop=want_desktop)
    
    res_msg = f"뼈대 그림을 저장했습니다: {path}\n({len(data)//1024}KB)"
    if err_msg:
        res_msg += f"\n{err_msg}"
    res_msg += ("\n이 그림을 사용자의 화풍으로 덧칠하려면 restyle 도구에 이 경로를 넘겨라. "
               "사용자가 화풍 변환을 원하지 않으면 이 경로를 그대로 알려줘라.")
    return res_msg


def restyle(args):
    """
    [2단계] 로컬 SD 1.5 WebUI(img2img)로 덧칠합니다. denoising을 약하게 줘서 구도는 지키고 화풍만 바꿉니다.
    WebUI가 꺼져 있으면 1단계 그림을 최종본으로 삼고 켜는 법을 안내합니다(그림 기능이 죽지 않게).
    """
    import base64

    img_path = args.get("image_path")
    if not img_path:
        return "오류: 'image_path' 매개변수가 필요합니다."
    src = _check_path(img_path)
    if not os.path.exists(src):
        return f"그림 파일이 없습니다: {src}"

    cfg = _img_cfg("local_sd")
    size = int(args.get("size", cfg.get("size", 512)))
    raw_prompt = str(args.get("prompt", ""))
    prompt = _expand_prompt(raw_prompt) if raw_prompt else "masterpiece, highly detailed, best quality"
    neg_prompt = args.get("negative_prompt") or cfg.get("negative_prompt") or "blurry, low quality, distorted, bad anatomy"

    payload = {
        "init_images": [base64.b64encode(open(src, "rb").read()).decode()],
        "prompt": prompt,
        "negative_prompt": neg_prompt,
        "denoising_strength": float(args.get("denoising_strength", cfg.get("denoising_strength", 0.35))),
        "steps": int(cfg.get("steps", 20)),
        "cfg_scale": float(cfg.get("cfg_scale", 7.0)),
        "width": size,
        "height": size,
    }

    url = cfg.get("url", "http://127.0.0.1:7860").rstrip("/") + "/sdapi/v1/img2img"
    print(f"\n  [그림] 로컬 SD로 덧칠하는 중... (denoise {payload['denoising_strength']}, {size}px)")
    print("         4GB VRAM이라 1~3분 걸릴 수 있습니다.")

    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={**UA, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=cfg.get("timeout", 600)) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        hint = ""
        if "NaN" in detail:
            hint = ("\n  → GTX 16xx의 fp16 결함입니다. webui-user.bat의 COMMANDLINE_ARGS에 "
                    "--upcast-sampling --no-half-vae 를 넣고 WebUI를 다시 켜세요.")
        return (f"WebUI가 덧칠을 거부했습니다 (HTTP {e.code}).\n{detail}{hint}\n"
                f"뼈대 그림은 그대로 있습니다: {src}")
    except urllib.error.URLError as e:
        return (f"로컬 SD WebUI에 연결하지 못했습니다({url}).\n"
                f"뼈대 그림은 이미 완성돼 있으니 이걸 최종본으로 쓰면 됩니다: {src}\n\n"
                "화풍 덧칠을 쓰려면 WebUI를 먼저 켜세요:\n"
                "  webui-user.bat 의 COMMANDLINE_ARGS 에 --medvram --xformers --api 를 넣고 실행\n"
                "  (--api 가 없으면 루시가 접속할 수 없습니다)\n"
                f"  원인: {type(e).__name__}")
    except Exception as e:
        return f"덧칠에 실패했습니다: {type(e).__name__}: {e}\n뼈대 그림은 그대로 있습니다: {src}"

    images = out.get("images") or []
    if not images:
        return f"WebUI가 그림을 돌려주지 않았습니다. 뼈대 그림은 그대로 있습니다: {src}"

    data = base64.b64decode(images[0].split(",", 1)[-1])
    want_desktop = bool(args.get("save_to_desktop") or "desktop" in raw_prompt.lower() or "바탕화면" in raw_prompt)
    path, ok, err_msg = _save_image_file(data, prefix="lucy_final", save_to_desktop=want_desktop)
    res_msg = f"화풍 덧칠까지 마친 최종 그림을 저장했습니다: {path}"
    if err_msg:
        res_msg += f"\n{err_msg}"
    return res_msg


def remember(args):
    """장기 기억에 한 줄 추가. 다음 실행부터 시스템 프롬프트에 자동으로 실립니다."""
    fact = str(args.get("fact") or "").strip()
    if not fact:
        return "오류: 'fact' 매개변수가 필요합니다."
    today = datetime.date.today().isoformat()
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"- {fact}  ({today})\n")
    return f"기억했습니다: {fact}"


def recall(_):
    if not os.path.exists(NOTES_FILE):
        return "저장된 기억이 없습니다."
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        return f.read() or "저장된 기억이 없습니다."


# ── 클로드와의 기록 ───────────────────────────────────────────────
# 두 종류가 있고 성격이 다릅니다.
#   knowledge/  = 클로드가 세션마다 정제해 적어둔 노트(62개, 330KB). 압축돼 있어 바로 쓸 수 있음.
#   .jsonl 원본 = 54세션 253MB. 도구 로그·파일 전문·실패한 시도까지 든 날것.
# 원본을 기억에 부으면 노이즈에 파묻혀 오히려 못 찾습니다. 그래서 원본은 '필요할 때 뒤지는' 도구로만 씁니다.

# 폴더명은 홈 경로를 인코딩한 것이라 현재 홈에서 계산합니다(다른 PC/계정 대비, 없으면 조용히 빈손).
_CLAUDE_HOME = os.path.expanduser("~")
CLAUDE_LOGS = os.path.join(
    _CLAUDE_HOME, ".claude", "projects",
    _CLAUDE_HOME.replace(":", "-").replace("\\", "-").replace("/", "-"))


def search_knowledge(args):
    """클로드가 정리해둔 프로젝트 노트에서 관련 대목을 찾아옵니다."""
    query = str(args.get("query") or "").strip()
    if not query:
        return "오류: 'query' 매개변수가 필요합니다."
    body, method = knowledge.search(query, _config)
    if not body:
        return f"관련 노트를 찾지 못했습니다. ({method})"
    return f"[지식 창고 — {method}]\n\n{body}"


def search_history(args):
    """
    클로드와 나눈 원본 대화(.jsonl)를 키워드로 뒤집니다.

    253MB를 통째로 읽으면 메모리가 터지므로, 줄 단위로 훑으면서 키워드가 들어간 줄만 JSON으로 풉니다
    (대부분의 줄은 문자열 검사에서 바로 탈락하므로 빠릅니다).
    """
    needle = str(args.get("keyword") or "").strip()
    if not needle:
        return "무엇을 찾을지 키워드를 주세요."
    limit = int(args.get("limit", 8))

    if not os.path.isdir(CLAUDE_LOGS):
        return f"클로드 대화 기록 폴더가 없습니다: {CLAUDE_LOGS}"

    files = sorted(
        (os.path.join(CLAUDE_LOGS, n) for n in os.listdir(CLAUDE_LOGS) if n.endswith(".jsonl")),
        key=os.path.getmtime, reverse=True,      # 최근 대화부터 봅니다
    )

    hits = []
    for path in files:
        when = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if needle.lower() not in line.lower():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg = row.get("message") or {}
                    role = msg.get("role") or row.get("type") or "?"
                    content = msg.get("content")

                    # content는 문자열이거나 [{type: text, text: ...}, ...] 형태입니다.
                    if isinstance(content, list):
                        text = " ".join(c.get("text", "") for c in content
                                        if isinstance(c, dict) and c.get("type") == "text")
                    else:
                        text = str(content or "")

                    if needle.lower() not in text.lower():
                        continue          # 도구 로그 등에만 걸린 경우는 버립니다
                    idx = text.lower().find(needle.lower())
                    snippet = " ".join(text[max(0, idx - 200): idx + 400].split())
                    hits.append(f"[{when} · {role}] …{snippet}…")
                    if len(hits) >= limit:
                        break
        except OSError:
            continue
        if len(hits) >= limit:
            break

    if not hits:
        return f"'{needle}'이(가) 나오는 대화를 찾지 못했습니다."
    return (f"[클로드와의 대화 기록에서 '{needle}' — {len(hits)}건]\n\n" + "\n\n".join(hits)
            + "\n\n(원본 대화의 일부만 잘라온 것이라 앞뒤 맥락이 없을 수 있습니다.)")


def search_my_history(args):
    """
    **루시와 나눈** 대화 기록(memory/history/날짜.md)을 뒤집니다.

    search_history(클로드와의 기록)와 짝입니다. 이게 없던 동안 루시는 자기가 어제 무슨 말을
    했는지 물어보면 답하지 못했습니다 — 기록은 남기고 있었는데 찾을 방법이 없었을 뿐입니다.
    (장기 기억 notes.md는 '앞으로도 알아야 할 사실'만 걸러 담으므로, 흘러간 이야기는 여기에만 있습니다)
    """
    needle = str(args["keyword"]).strip()
    if not needle:
        return "무엇을 찾을지 키워드를 주세요."
    limit = int(args.get("limit", 8))

    history_dir = os.path.join(MEMORY_DIR, "history")
    if not os.path.isdir(history_dir):
        return "아직 대화 기록이 없습니다."

    hits = []
    # ① 낱말 정확 일치 — 이름·명령어처럼 글자 그대로 찾을 때 가장 강한 신호.
    # 최근 날짜부터 — 오래된 이야기보다 어제 이야기를 찾을 때가 훨씬 많습니다.
    for name in sorted(os.listdir(history_dir), reverse=True):
        if not name.endswith(".md"):
            continue
        try:
            with open(os.path.join(history_dir, name), "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue

        # 기록은 '**나** (14:03)\n내용' 형태의 덩어리입니다. 덩어리째 보여줘야 맥락이 삽니다.
        for turn in text.split("\n\n"):
            if needle.lower() not in turn.lower():
                continue
            snippet = " ".join(turn.split())
            hits.append(f"[{name[:-3]}] {snippet[:500]}")
            if len(hits) >= limit:
                break
        if len(hits) >= limit:
            break

    # ② 의미 검색(임베딩) — 낱말이 달라도 찾습니다("버즈 문제"→"음량 문턱" 대화).
    # Ollama가 꺼져 있으면 조용히 건너뜁니다(위의 낱말 검색이 받쳐줌 — 강등이지 고장이 아님).
    how = "낱말"
    if len(hits) < limit:
        try:
            import histsearch
            seen = {h[:120] for h in hits}
            for score, day, chunk in histsearch.search(_config, needle, top_k=limit):
                line = f"[{day}] {chunk[:500]}"
                if line[:120] in seen:
                    continue
                hits.append(line + f"  (의미 {score:.2f})")
                seen.add(line[:120])
                if len(hits) >= limit:
                    break
            how = "낱말+의미"
        except Exception:
            pass

    if not hits:
        return (f"'{needle}'이(가) 나오는 대화를 찾지 못했습니다. "
                "다른 낱말로 다시 찾아보세요.")
    return f"[루시와의 대화 기록에서 '{needle}' — {len(hits)}건, {how} 검색]\n\n" + "\n\n".join(hits)


def read_clipboard(_args):
    """
    지금 복사해 둔 것을 읽습니다. 화면 캡처의 짝 — 눈으로 보는 것 / 복사해 온 것.

    사용자가 오류 메시지나 긴 글을 복사해 놓고 "이거 요약해줘"라고 할 때, 붙여넣기 없이 바로 됩니다.
    (윈도우 Get-Clipboard / 리눅스 xclip·xsel·wl-paste 지원)
    """
    try:
        if sys.platform == "win32":
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "Get-Clipboard -Raw"],
                capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace",
            )
        else:
            if shutil.which("xclip"):
                cmd = ["xclip", "-selection", "clipboard", "-o"]
            elif shutil.which("xsel"):
                cmd = ["xsel", "-o", "--clipboard"]
            elif shutil.which("wl-paste"):
                cmd = ["wl-paste"]
            else:
                return "클립보드를 읽을 수 있는 유틸리티(xclip, xsel, wl-paste)가 설치되어 있지 않습니다."
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"클립보드를 읽지 못했습니다: {e}"

    text = (proc.stdout or "").strip()
    if not text:
        return "클립보드가 비어 있습니다(또는 글자가 아닌 것이 들어 있습니다)."
    if len(text) > 20000:
        return text[:20000] + f"\n\n(…{len(text) - 20000}자 더 있음 — 앞부분만 읽었습니다)"
    return text


def forget(args):
    """
    장기 기억에서 한 줄을 지웁니다.

    이 도구가 없던 시절, 모델은 "기억에서 삭제했습니다"라고 답해놓고 실제로는 아무것도 지우지
    못했습니다(지울 방법 자체가 없었으니까요). 못 지우는 것보다 지웠다고 거짓말하는 게 더 나쁩니다.
    """
    needle = str(args.get("about") or "").strip()
    if not needle:
        return "무엇을 지울지 알려주세요."
    if not os.path.exists(NOTES_FILE):
        return "저장된 기억이 없습니다."

    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    hits = [l for l in lines if l.strip().startswith("-") and needle.lower() in l.lower()]
    if not hits:
        return (f"'{needle}'과(와) 일치하는 기억이 없습니다. 지운 것이 없습니다. "
                "recall로 저장된 기억을 먼저 확인하세요.")

    print("\n  지우려는 기억:")
    for line in hits:
        print(f"    {line.strip()}")
    if not _confirm(f"이 기억 {len(hits)}건을 지울까요?"):
        return "사용자가 거부했습니다. 아무것도 지우지 않았습니다."

    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        f.writelines(l for l in lines if l not in hits)
    return "다음 기억을 지웠습니다:\n" + "\n".join("- " + l.strip().lstrip("- ") for l in hits)


# ── 할 일(Todo) ───────────────────────────────────────────────────
# 장기 기억(notes)은 '사실'을, 예약(reminder)은 '시각'을 맡습니다. 할 일은 그 사이 —
# 시각은 없지만 끝내야 하는 것들입니다. 파일은 그냥 마크다운이라 사용자가 직접 열어 고쳐도 됩니다.
TODO_FILE = os.path.join(MEMORY_DIR, "todo.md")


def _todo_lines():
    if not os.path.exists(TODO_FILE):
        return []
    with open(TODO_FILE, "r", encoding="utf-8") as f:
        return [l.rstrip("\n") for l in f if l.strip()]


def _todo_save(lines):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def add_todo(args):
    what = str(args.get("what") or "").strip()
    if not what:
        return "무엇을 할 일로 넣을지 알려주세요."
    today = datetime.date.today().isoformat()
    lines = _todo_lines()
    lines.append(f"- [ ] {what}  (등록 {today})")
    _todo_save(lines)
    open_count = sum(1 for l in lines if l.startswith("- [ ]"))
    return f"할 일에 넣었습니다: {what} (미완료 {open_count}개)"


def list_todos(_args):
    lines = _todo_lines()
    open_items = [l for l in lines if l.startswith("- [ ]")]
    done_items = [l for l in lines if l.startswith("- [x]")]
    if not open_items and not done_items:
        return "할 일 목록이 비어 있습니다."
    out = []
    if open_items:
        out.append("미완료:")
        out += [f"  {i}. {l[6:]}" for i, l in enumerate(open_items, 1)]
    else:
        out.append("미완료 할 일이 없습니다. 전부 끝냈습니다!")
    if done_items:
        out.append(f"완료 {len(done_items)}개 (최근): " +
                   " · ".join(l[6:].split("  (")[0] for l in done_items[-3:]))
    return "\n".join(out)


def done_todo(args):
    """번호('2')나 내용 일부('우유')로 미완료 항목을 완료 처리합니다."""
    needle = str(args.get("about") or "").strip()
    if not needle:
        return "어느 할 일을 완료 처리할지 알려주세요 (번호나 내용 일부)."
    lines = _todo_lines()
    open_idx = [i for i, l in enumerate(lines) if l.startswith("- [ ]")]
    if not open_idx:
        return "미완료 할 일이 없습니다."

    target = None
    if needle.isdigit() and 1 <= int(needle) <= len(open_idx):
        target = open_idx[int(needle) - 1]
    else:
        matches = [i for i in open_idx if needle.lower() in lines[i].lower()]
        if len(matches) > 1:
            return ("여러 개가 걸립니다 — 번호로 다시 알려주세요:\n" +
                    "\n".join(f"  {open_idx.index(i)+1}. {lines[i][6:]}" for i in matches))
        target = matches[0] if matches else None
    if target is None:
        return f"'{needle}'에 해당하는 미완료 할 일이 없습니다. list_todos로 확인하세요."

    today = datetime.date.today().isoformat()
    lines[target] = lines[target].replace("- [ ]", "- [x]", 1) + f"  (완료 {today})"
    _todo_save(lines)
    return "완료 처리했습니다: " + lines[target][6:]


# ── 자가 진단 ─────────────────────────────────────────────────────
def self_check(_args):
    """
    루시가 제 몸을 점검하고 고칩니다. 사용자가 "목소리가 왜 이래?"라고 물으면
    모델이 이걸 불러 실제 상태를 확인합니다 — 폴백은 조용해서, 묻지 않으면 모릅니다.
    """
    import doctor
    return doctor.report(_config)


# ── 날씨 ──────────────────────────────────────────────────────────
def get_weather(args):
    import weather
    return weather.forecast(str(args.get("location") or ""), _config)


# ── 버스 ──────────────────────────────────────────────────────────
def get_bus(args):
    import transit
    stop = str(args.get("stop") or "").strip()
    if stop.replace(" ", "") in ("", "집", "집앞"):
        return transit.home(_config)
    return transit.arrivals(stop,
                            str(args.get("bus") or ""),
                            str(args.get("region") or ""))


# ── 지하철 ────────────────────────────────────────────────────────
def get_subway(args):
    import transit
    return transit.subway(str(args.get("station") or ""),
                          str(args.get("line") or ""), _config)


# ── 계산기 ────────────────────────────────────────────────────────
# 언어모델은 자릿수가 큰 산수를 자주 틀립니다(그럴듯한 숫자를 만들어냄).
# eval()은 임의 코드 실행이라 절대 쓰지 않고, 수식 트리를 직접 걸어가며 계산합니다.
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "log": math.log, "log10": math.log10, "exp": math.exp, "floor": math.floor, "ceil": math.ceil,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "pi": math.pi, "e": math.e,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Name) and node.id in _FUNCS and not callable(_FUNCS[node.id]):
        return _FUNCS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval_node(a) for a in node.args])
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval_node(e) for e in node.elts]
    raise ValueError("계산할 수 없는 식입니다(허용되지 않은 문법).")


def calc(args):
    expr = str(args.get("expression") or "").strip()
    if not expr:
        return "오류: 계산할 수식이 필요합니다."
    try:
        parsed_expr = expr.replace("^", "**").replace(",", "")
        value = _eval_node(ast.parse(parsed_expr, mode="eval").body)
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{expr} = {value}"
    except Exception as e:
        return f"계산 오류 ({type(e).__name__}): {e}"


# ── 내 파일 뒤지기 ────────────────────────────────────────────────
_SKIP_DIRS = {".git", "node_modules", "__pycache__", "Library", "Temp", "obj", "venv", ".venv", "AppData"}
_TEXT_EXT = {".txt", ".md", ".py", ".json", ".cs", ".js", ".ts", ".html", ".css", ".csv",
             ".xml", ".yml", ".yaml", ".bat", ".ps1", ".ini", ".cfg", ".log"}


def find_files(args):
    """이름(name)이나 내용(contains)으로 파일을 찾습니다. 둘 다 주면 둘 다 만족하는 것만."""
    root = _check_path(args.get("path") or _config.get("allowed_dirs", ["."])[0])
    name_pat = args.get("name")
    needle = args.get("contains")
    if not name_pat and not needle:
        return "오류: name(파일명 패턴) 또는 contains(찾을 내용) 중 하나는 있어야 합니다."

    hits, scanned, truncated = [], 0, False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if name_pat and not fnmatch.fnmatch(fname.lower(), name_pat.lower()):
                continue
            full = os.path.join(dirpath, fname)
            if not needle:
                hits.append(full)
            elif os.path.splitext(fname)[1].lower() in _TEXT_EXT:
                scanned += 1
                if scanned > 3000:          # 온 디스크를 다 읽지 않도록 상한
                    truncated = True
                    break
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        for n, line in enumerate(f, 1):
                            if needle.lower() in line.lower():
                                hits.append(f"{full}:{n}: {line.strip()[:120]}")
                                break
                except OSError:
                    continue
            if len(hits) >= 50:
                return "\n".join(hits) + f"\n(50개까지만 표시. 더 좁혀서 다시 찾으세요)"
        if truncated:
            # 안쪽 break만으로는 os.walk가 남은 폴더를 계속 헛돌고, 사용자는 검색이
            # 잘렸는지도 모릅니다 — 못 찾았다고 믿게 됩니다. 여기서 멈추고 잘렸다고 말합니다.
            break
    out = "\n".join(hits) or "찾은 파일이 없습니다."
    if truncated:
        out += ("\n⚠ 파일 3000개까지만 내용을 확인하고 멈췄습니다 — 여기 없다고 없는 게 아닙니다. "
                "path를 더 좁혀서(예: 특정 하위 폴더) 다시 찾아보세요.")
    return out


# ── 파이썬 실행 ───────────────────────────────────────────────────
def run_python(args):
    """
    계산·데이터 처리·파일 변환처럼 말로 하기 힘든 일을 코드로 시킵니다.
    실행 전 코드를 그대로 보여주고 사용자 확인을 받습니다(파워셸과 같은 원칙).
    """
    code = args.get("code")
    if not code:
        return "오류: 'code' 매개변수가 필요합니다."
    print("\n  실행하려는 파이썬 코드:")
    for line in code.splitlines()[:40]:
        print(f"    {line}")
    if not _confirm("이 코드를 실행할까요?", risk="exec"):
        return "사용자가 거부했습니다. 실행하지 않았습니다."

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        proc = subprocess.run([sys.executable, path], capture_output=True, text=True,
                              timeout=60, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return "60초를 넘겨 중단했습니다."
    finally:
        os.unlink(path)

    out = (proc.stdout or "") + (proc.stderr or "")
    formatted = out[:10000] or f"(출력 없음, 종료코드 {proc.returncode}) — print()로 결과를 찍어야 보입니다."
    diag = coding.parse_traceback(out)
    if diag:
        formatted += f"\n\n{diag}"
    return formatted


def run_powershell(args):
    """실행 전 반드시 사용자 확인을 받습니다. (윈도우 파워셸, 리눅스 bash/sh)"""
    command = args.get("command")
    if not command:
        return "오류: 'command' 매개변수가 필요합니다."
    print(f"\n  실행하려는 명령:\n    {command}")
    if not _confirm("이 명령을 실행할까요?", risk="exec"):
        return "사용자가 거부했습니다. 실행하지 않았습니다."
    if sys.platform == "win32":
        shell_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        shell_bin = shutil.which("bash") or shutil.which("sh") or "/bin/sh"
        shell_cmd = [shell_bin, "-c", command]
    proc = subprocess.run(
        shell_cmd,
        capture_output=True, text=True, timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return out[:10000] or f"(출력 없음, 종료코드 {proc.returncode})"


# ── 코딩 작업실 (coding.py) ───────────────────────────────────────
# 여러 파일짜리 프로그램을 짓고·돌려보고·고쳐가며 완성합니다. 파일 조작은 workspace/
# 밖을 못 건드리므로(coding.ws_path가 막음) 사용자의 진짜 파일을 덮어쓸 위험이 없어
# 확인 없이 씁니다 — 안 그러면 에러 한 줄 고칠 때마다 물어봐서 루프가 못 굴러갑니다.
# 위험한 건 '실행'뿐이라, 실행은 프로젝트마다 세션에 한 번만 허락을 받습니다.
_approved_runs = set()          # 이 프로세스에서 실행을 이미 허락받은 프로젝트 이름들


def _project_of(rel):
    rel = str(rel).replace("\\", "/").strip("/")
    return rel.split("/")[0] if "/" in rel else "(작업실 루트)"


def code_write(args):
    path = args.get("path")
    if not path:
        return "오류: 'path' 매개변수가 필요합니다."
    return coding.write(path, args.get("content", ""))


def code_read(args):
    path = args.get("path")
    if not path:
        return "오류: 'path' 매개변수가 필요합니다."
    return coding.read(path)


def code_edit(args):
    path = args.get("path")
    find_str = args.get("find")
    if not path or find_str is None:
        return "오류: 'path'와 'find' 매개변수가 필요합니다."
    return coding.edit(path, find_str, args.get("replace", ""),
                       bool(args.get("all")))


def code_list(args):
    return coding.list_tree(args.get("path"))


def code_run(args):
    rel = args["path"]
    proj = _project_of(rel)
    if proj not in _approved_runs:
        if not _confirm(f"코딩 작업실의 '{proj}' 프로젝트를 실행할까요?"
                        " (허락하면 이 프로젝트 실행은 이번 세션 동안 다시 안 물어봅니다)",
                        risk="exec"):
            return "사용자가 실행을 거부했습니다. 코드는 작업실에 그대로 있습니다."
        _approved_runs.add(proj)
    raw = args.get("args")
    arglist = raw.split() if isinstance(raw, str) else (raw or [])
    to = args.get("timeout")
    return coding.run(rel, arglist, int(to) if to else None)   # None이면 파이썬60·C#180 자동


def code_install(args):
    package = str(args["package"]).strip()
    if not _confirm(f"pip로 '{package}'를 설치할까요?", risk="exec"):
        return "사용자가 거부했습니다. 설치하지 않았습니다."
    return coding.pip_install(package)


def unity_run(args):
    """유니티를 배치모드로 돌려 컴파일·테스트를 시킨다(unity.py). 사용자 프로젝트를
    건드리고 수 분 걸리므로 반드시 확인을 받는다 — 배경·웹에서는 exec 거부로 막힌다."""
    import unity
    project = args.get("project")
    method = args.get("method")
    tests = args.get("tests")
    what = (f"{tests} 테스트" if tests else
            (f"메서드 {method} 실행" if method else "컴파일 점검(열고 닫기)"))
    if not _confirm(f"유니티 프로젝트 '{project or '기본'}'에서 {what}을(를)"
                    " 배치모드로 실행할까요? (수 분 걸릴 수 있고, 에디터는 닫혀 있어야 합니다)",
                    risk="exec"):
        return "사용자가 거부했습니다. 실행하지 않았습니다."
    to = int(args.get("timeout") or 600)
    return unity.run_batch(_config, project=project, method=method, tests=tests, timeout=to)


def unity_new_script(args):
    """유니티 프로젝트 Assets에 컴파일 되는 C# 골격을 만든다(unity.py). 진짜 프로젝트에
    새 파일을 쓰므로 확인을 받는다(위험한 실행은 아님 → risk=write)."""
    import unity
    name = (args.get("name") or "").strip()
    if not name:
        return "오류: 클래스 이름(name)이 필요합니다."
    project = args.get("project")
    kind = args.get("kind", "mono")
    if not _confirm(f"유니티 프로젝트 '{project or '기본'}'에 {kind} 스크립트 '{name}.cs'를 만들까요?"):
        return "사용자가 거부했습니다. 만들지 않았습니다."
    return unity.new_script(_config, project, name, kind, args.get("folder"))


def unity_find(args):
    import unity
    return unity.find_in_code(_config, args.get("project"), args.get("query"))


def unity_audit(args):
    """프로젝트 파일 감사 — 유니티 안 띄우고 읽기만 하므로 확인 없음."""
    import unity
    return unity.audit(_config, args.get("project"))


def unity_status(args):
    """에디터를 닫지 않고 Editor.log로 현재 컴파일 상태만 읽는다(읽기전용 → 확인 없음)."""
    import unity
    return unity.read_status(_config)


def eye_trust(args):
    """눈 신뢰도 시험 — 정답을 아는 그림으로 눈 달린 두뇌들을 검증(모델을 여러 번 부름).
    읽기전용이고 config를 안 고치므로 확인 없이 돕니다(결과는 memory/eye_trust.json)."""
    import agent as _agent
    import eyecheck
    if str(args.get("action") or "").strip() in ("last", "결과", "지난"):
        lines = eyecheck.status_lines()
        return "\n".join(lines).strip() or "아직 눈 신뢰도 시험을 본 적이 없습니다."
    text, _res = eyecheck.run(_agent, _config, notify=lambda m: None)
    return text


def unity_health(args):
    """등록된 프로젝트들이 지금 컴파일 되는지 점검(배치모드로 열고 닫기 — 몇 분 걸림).
    에디터가 열린 프로젝트는 자동으로 정적 점검으로 대체되므로 잠금 사고는 없습니다."""
    import unity
    projects = args.get("project")
    projects = [projects] if projects else None
    text, _res = unity.health(_config, projects=projects,
                              timeout=int(args.get("timeout") or 900))
    return text


def unity_build(args):
    import unity
    project = args.get("project")
    method = args.get("method")
    kind = args.get("kind")
    label = method or (kind or "기본 빌드")
    if not _confirm(f"유니티 프로젝트 '{project or '기본'}' 빌드({label})를 실행할까요?"
                    " (몇 분~수십 분 걸릴 수 있고, 에디터는 닫혀 있어야 합니다)", risk="exec"):
        return "사용자가 거부했습니다. 빌드하지 않았습니다."
    to = int(args.get("timeout") or 1800)
    return unity.build(_config, project=project, method=method, kind=kind, timeout=to)


def unity_scene(args):
    """씬·프리팹 YAML 파싱으로 계층·컴포넌트 보기 — 유니티 안 띄우고 읽기만(확인 없음)."""
    import unity
    to = args.get("limit")
    return unity.scene_outline(_config, args.get("project"), args.get("path"),
                               int(to) if to else 150)


def unity_refs(args):
    """에셋 guid 참조 추적/미사용 후보 — 파일 스캔만(읽기전용 → 확인 없음)."""
    import unity
    return unity.find_refs(_config, args.get("project"), args.get("asset"))


def unity_settings(args):
    """프로젝트 설정·빌드 씬·패키지 요약 — 읽기전용(확인 없음)."""
    import unity
    return unity.settings_summary(_config, args.get("project"))


def unity_log(args):
    """Editor.log/Player.log의 런타임 예외 집계 — 읽기전용(확인 없음)."""
    import unity
    return unity.game_log(_config, args.get("project"), args.get("source") or "editor")


def unity_outline(args):
    """C# 클래스·메서드·필드 개요 — 읽기전용(확인 없음)."""
    import unity
    to = args.get("limit")
    return unity.code_outline(_config, args.get("project"), args.get("path"),
                              int(to) if to else 150)


def unity_build_report(args):
    """마지막 빌드의 용량 리포트 분석 — 로그 파싱만(읽기전용 → 확인 없음)."""
    import unity
    return unity.build_report(_config, args.get("project"))


def unity_yaml_edit(args):
    """씬·프리팹·에셋 텍스트 치환 — 진짜 프로젝트 파일을 고치므로 확인을 받는다(자동 백업)."""
    import unity
    path = args.get("path")
    find = args.get("find")
    if not (path and find):
        return "오류: path(파일)와 find(찾을 문구)가 필요합니다."
    if not _confirm(f"유니티 프로젝트 '{args.get('project') or '기본'}'의 {path}에서 문구를 바꿀까요?"
                    " (원본은 자동 백업됩니다)"):
        return "사용자가 거부했습니다. 고치지 않았습니다."
    return unity.yaml_edit(_config, args.get("project"), path, find,
                           args.get("replace") or "", bool(args.get("all")))


def unity_snapshot(args):
    """씬·프리팹·설정 스냅샷. take/list는 읽기·저장뿐이라 확인 없음, restore만 확인."""
    import unity
    act = (args.get("action") or "take").strip().lower()
    if act == "restore":
        sid = args.get("id") or "최신"
        if not _confirm(f"유니티 프로젝트 '{args.get('project') or '기본'}'을 스냅샷 {sid}(으)로 "
                        "되돌릴까요? (복원 직전 상태도 자동 백업됩니다)"):
            return "사용자가 거부했습니다. 복원하지 않았습니다."
    return unity.snapshot(_config, args.get("project"), act, args.get("id"), args.get("file"))


def unity_diff(args):
    """씬·프리팹을 다른 파일/스냅샷과 비교 — 읽기전용(확인 없음)."""
    import unity
    if not args.get("path"):
        return "오류: 비교할 파일(path)이 필요합니다."
    return unity.diff_assets(_config, args.get("project"), args["path"],
                             args.get("path2"), args.get("snapshot"))


def unity_sprites(args):
    """스프라이트/텍스처 임포트 설정 감사 — 읽기전용(확인 없음)."""
    import unity
    return unity.sprites_audit(_config, args.get("project"), args.get("folder"))


def unity_tex_fix(args):
    """텍스처 임포트 설정(maxTextureSize) 일괄 하향 — 감사(audit·sprites)의 수리 짝.
    진짜 프로젝트의 .meta를 고치므로 후보를 먼저 세고 확인을 받는다(자동 백업)."""
    import unity
    project = args.get("project")
    folder = args.get("folder")
    max_px = int(args.get("max_px") or 1024)
    proj, hits, err = unity.tex_fix_candidates(_config, project, folder, max_px)
    if err:
        return err
    if not hits:
        return f"maxTextureSize {max_px} 초과 텍스처가 없습니다 — 고칠 게 없어요."
    sample = ", ".join(r.rsplit("/", 1)[-1] for r, _d, _o in hits[:4])
    if not _confirm(f"유니티 프로젝트 '{project or '기본'}'의 텍스처 {len(hits)}개"
                    f"({sample}…) maxTextureSize를 {max_px}로 낮출까요? "
                    "(.meta만 수정·원본 그림 불변·자동 백업, 에디터는 닫혀 있어야 합니다)"):
        return "사용자가 거부했습니다. 고치지 않았습니다."
    return unity.tex_fix_apply(_config, project, folder, max_px)


def unity_models(args):
    """3D 모델(FBX 등) 임포트 감사 — 읽기전용(확인 없음)."""
    import unity
    return unity.models_audit(_config, args.get("project"), args.get("folder"))


def unity_scene_lint(args):
    """씬 성능 린트(모바일 기준) — YAML 집계만(읽기전용 → 확인 없음)."""
    import unity
    return unity.scene_lint(_config, args.get("project"), args.get("path"))


def unity_scene_smoke(args):
    """빌드 씬을 배치모드로 실제 로드해 누락 스크립트·끊긴 참조·예외를 잡는다.
    유니티를 띄우고 수 분 걸리므로 확인을 받는다 — 배경·웹에서는 exec 거부로 막힌다."""
    import unity
    project = args.get("project")
    if not _confirm(f"유니티 프로젝트 '{project or '기본'}'의 빌드 씬 전부를 배치모드로 "
                    "열어 스모크 테스트할까요? (수 분 걸리고, 에디터는 닫혀 있어야 합니다. "
                    "임시 검사 스크립트를 심었다가 끝나면 지웁니다)", risk="exec"):
        return "사용자가 거부했습니다. 실행하지 않았습니다."
    to = int(args.get("timeout") or 900)
    return unity.scene_smoke(_config, project, timeout=to)


def unity_fbx_check(args):
    """블렌더 납품 FBX를 **진짜 유니티**에 넣어 왕복 검증 — 임포트→재질 바인딩 실측→렌더.
    '갈색 덩어리·통째 투명' 사고 클래스(세션58~61)를 납품 전에 잡는 마지막 검문소."""
    import unity
    fbx = _find_media(args.get("path"), (".fbx",))
    if not fbx:
        return f"검증할 FBX를 찾지 못했습니다: {args.get('path')} (전체 경로를 주세요)"
    if not _confirm(f"{os.path.basename(fbx)}(+옆의 텍스처)를 검증용 유니티 프로젝트에 넣어 "
                    "임포트·렌더 검증할까요? (수 분, 에디터 닫힘 필요, 흔적은 지웁니다)",
                    risk="exec"):
        return "사용자가 거부했습니다. 실행하지 않았습니다."
    r = unity.fbx_verify(_config, fbx, project=args.get("project"),
                         timeout=int(args.get("timeout") or 900))
    if isinstance(r, str):
        return r
    if r.get("error"):
        return f"검증 실패: {r['error']}"
    L = [f"[{os.path.basename(fbx)}] 유니티 왕복 검증(프로젝트 {r['project']})"]
    unbound = [m for m, t in r["materials"] if t == "NULL"]
    for m, t in r["materials"]:
        L.append(f"  {'⚠' if t == 'NULL' else '✅'} 재질 {m} ← 텍스처 "
                 + (t if t != "NULL" else "없음(NULL)"))
    if unbound:
        L.append(f"  📏 텍스처 안 물린 재질 {len(unbound)}개 — 일부러 단색 재질이면 정상, "
                 "텍스처를 기대했다면 '갈색 덩어리' 신호(파일명 ASCII·FBX 옆 같은 폴더 확인)")
    if r.get("shot"):
        L.append(f"  · 렌더: {r['shot']} (웹에서 바로 보임)")
        m_ratio, _flat = unity._pixel_stats(r["shot"])
        if isinstance(m_ratio, float) and m_ratio > 0.005:
            L.append(f"  📏 분홍(마젠타) 픽셀 {m_ratio * 100:.1f}% — 셰이더 실종 신호")
        eye = _eye_look(
            "블렌더에서 만든 3D 소품을 유니티에 임포트해 렌더한 검증 사진입니다(미적 평가 금지).",
            "텍스처·무늬가 입혀져 보이는가, 아니면 민무늬 단색 덩어리인가? "
            "분홍(마젠타)이나 통째 투명(배경색만)인가?", r["shot"], gate_key="unity")
        if eye:
            L.append("  " + eye.strip("\n"))
    ok = not unbound and r.get("shot")
    L.append("  → 왕복 검증 통과 ✅ (유니티에 이대로 드롭하면 됩니다)" if ok
             else "  → 위 항목 확인 필요")
    return "\n".join(L)


def unity_shot(args):
    """빌드 씬을 배치모드로 실제 렌더해 PNG로 찍고, 분홍(재질 실종) 픽셀 스캔 + 눈 두뇌
    자가검수까지 — 루시의 유니티 눈(판단력 1층). 씬은 절대 저장하지 않는다."""
    import unity
    project = args.get("project")
    scene = args.get("scene")
    play = bool(args.get("play"))
    what = f"'{scene}' 씬" if scene else "빌드 씬 전부"
    how = "플레이모드로 실제 실행해" if play else "배치모드로 렌더해"
    if not _confirm(f"유니티 프로젝트 '{project or '기본'}'의 {what}을 {how} "
                    "스크린샷을 찍을까요? (수 분 걸리고, 에디터는 닫혀 있어야 합니다. "
                    "씬은 저장하지 않습니다)", risk="exec"):
        return "사용자가 거부했습니다. 실행하지 않았습니다."
    w, h = (1280, 720) if args.get("landscape") else (720, 1280)
    fn = unity.play_shot if play else unity.scene_shot
    r = fn(_config, project, scene=scene, width=w, height=h,
           timeout=int(args.get("timeout") or (1200 if play else 900)))
    if isinstance(r, str):                        # 잠금·씬 없음 등 초기 실패
        return r
    head, shots = r
    L = [f"{head} 씬 스크린샷 {sum(1 for _, p, *_ in shots if p)}장 "
         f"({w}×{h}, 오버레이 UI 포함·씬 저장 안 함"
         + ("·런타임 상태=스폰·데이터 UI 보임)" if play
            else "·에디트 모드=런타임 생성물은 안 보임)")]
    bad = empty = 0
    blocks = []                                   # (줄들, 눈검수 대상 stem 또는 None, png)
    for spath, png, extra, flat in shots:
        if not png:
            blocks.append(([f"  ✗ {spath} — 못 찍음({extra}: 카메라 없음이면 NOCAM)"], None, None))
            bad += 1
            continue
        row = f"  · {os.path.basename(spath)} → {png} (웹에서 바로 보임)"
        # 리그레션 감시(세션63 6부): 같은 씬의 직전 샷과 픽셀 비교 — 기계 판단, 눈 불필요.
        dr, prev_dir = unity.prev_shot_diff(png)
        if dr is not None and dr > 0.05:
            row += (f"\n    📏 지난 샷({prev_dir}) 대비 {dr * 100:.0f}% 달라짐 — "
                    "의도한 변경이면 정상, 아니면 최근 수정을 의심")
        # 🔧 기계 판정 — 마젠타 범벅·검은 화면은 픽셀만 세면 확실합니다. 눈에게 묻지 않습니다
        # (세션64 실측: nemotron이 온통 마젠타인 그림을 '정상'이라 통과시킴 — 그 경로를 막음).
        import vision
        mv, why = vision.machine_verdict(png, context="unity")
        if mv:
            row += f"\n    🔧 기계 판정: **문제** — {why}"
            bad += 1
            blocks.append(([row], None, None))
            continue
        if isinstance(flat, float) and flat > 0.98:
            # 단색 화면은 기계 판별로 끝 — UI를 런타임에 만드는 씬이면 정상이라 '문제'가 아님.
            row += ("\n    ℹ 단색 화면(정적 콘텐츠 없음) — UI를 런타임에 만드는 씬이면 정상, "
                    "아니면 카메라 위치·레이어 확인")
            empty += 1
            blocks.append(([row], None, None))
            continue
        if isinstance(extra, float) and extra > 0.005:
            # 기계가 확답 못 한 어중간한 분홍 — 분홍 소품일 수 있어 메모만 달고 눈에게 넘깁니다.
            row += f"\n    📏 분홍(마젠타) 픽셀 {extra * 100:.1f}% — 재질/셰이더 실종 신호"
            bad += 1
        blocks.append(([row], os.path.splitext(os.path.basename(png))[0], png))
    # 눈검수는 여러 장을 한 턴에 묶어서(무료 한도 절약, 세션63 7부) — 3장씩(Groq 상한).
    elig = [(s, p) for _lines, s, p in blocks if s]
    verdicts, eye_label = {}, None
    for i in range(0, len(elig), 3):
        lb, vd = _eye_look_many(
            ("유니티 게임 씬을 플레이모드로 실제 실행 중에 찍은 스크린샷들입니다(미적 평가 금지)."
             if play else
             "유니티 게임 씬을 에디트 모드에서 카메라 그대로 렌더한 스크린샷들입니다"
             "(미적 평가 금지. 런타임 생성물은 원래 안 보입니다)."),
            "화면이 통째로 검은가? 분홍(마젠타) 덩어리가 보이는가? "
            "UI 글자·버튼이 심하게 겹치거나 화면 밖으로 잘렸는가? "
            "게임 화면으로 정상 범위면 '정상'으로.", elig[i:i + 3], gate_key="unity")
        verdicts.update(vd)
        eye_label = eye_label or lb
    for lines, stem, _png in blocks:
        L += lines
        if stem and stem in verdicts:
            L.append(f"    · 👁 자가검수({eye_label}): {verdicts[stem]}")
            if verdicts[stem].startswith("문제"):
                bad += 1
    missing = [s for s, _p in elig if s not in verdicts]
    if missing:                                   # 누락을 침묵하면 '정상'으로 오해됨 — 정직 표기
        L.append("  · 👁 판정 못 받은 씬: " + ", ".join(missing[:6])
                 + " (눈 두뇌 한도/형식 불일치 — 그림을 직접 확인하세요)")
    tail = []
    if bad:
        tail.append(f"확인 필요 {bad}건")
    if empty:
        tail.append(f"단색(정적 콘텐츠 없음) {empty}건")
    L.append("  → " + " · ".join(tail) if tail else "  → 전 샷 정상 ✅")
    return "\n".join(L)


def unity_code_lint(args):
    """C# 위생 린트(매 프레임 비용·빈 catch 등) — 읽기전용(확인 없음)."""
    import unity
    return unity.code_lint(_config, args.get("project"), args.get("folder"))


def unity_cs_check(args):
    """dotnet 고속 컴파일 검사 — 프로젝트 파일은 안 건드림(작업 파일은 루시 memory 안)."""
    import unity
    if not args.get("path"):
        return "오류: 검사할 .cs 파일(path)이 필요합니다."
    return unity.cs_check(_config, args.get("project"), args["path"])


def unity_cs_write(args):
    """프로젝트 Assets에 .cs 생성/교체 + 자동 컴파일 검사. 진짜 프로젝트 파일이라 확인."""
    import unity
    path = args.get("path")
    if not (path and args.get("content")):
        return "오류: path(파일)와 content(전체 내용)가 필요합니다."
    if not _confirm(f"유니티 프로젝트 '{args.get('project') or '기본'}'의 {path}를 쓰고 "
                    "바로 컴파일 검사할까요? (기존 파일이면 자동 백업)"):
        return "사용자가 거부했습니다. 쓰지 않았습니다."
    return unity.cs_write(_config, args.get("project"), path, args["content"])


def unity_cs_edit(args):
    """프로젝트 .cs find→replace + 자동 컴파일 검사. 진짜 프로젝트 파일이라 확인(백업)."""
    import unity
    path = args.get("path")
    find = args.get("find")
    if not (path and find):
        return "오류: path(파일)와 find(찾을 코드)가 필요합니다."
    if not _confirm(f"유니티 프로젝트 '{args.get('project') or '기본'}'의 {path} 코드를 고치고 "
                    "바로 컴파일 검사할까요? (원본 자동 백업)"):
        return "사용자가 거부했습니다. 고치지 않았습니다."
    return unity.cs_edit(_config, args.get("project"), path, find,
                         args.get("replace") or "", bool(args.get("all")))


def unity_context(args):
    """클래스·주제 관련 코드 맥락 팩 — 읽기전용(확인 없음)."""
    import unity
    return unity.context_pack(_config, args.get("project"), args.get("query"))


def blender_batch(args):
    """폴더의 여러 3D 파일에 같은 블렌더 작업을 한 번에. 원본은 안 건드림(수술=사본·convert=새 파일)."""
    import blender3d
    import glob as _glob
    folder = str(args.get("folder") or "").strip().strip('"\'')
    if not os.path.isdir(folder):
        return f"폴더를 찾지 못했습니다: {folder} (전체 경로를 주세요)"
    action = str(args.get("action") or "").strip().lower()
    # 파일별 스펙이 필요한 수술(boolean·경로·부착점·PBR·포즈·물리)은 일괄이 성립 안 함 — 제외.
    batchable = ("info", "convert", "prep_unity", "contact_sheet") + tuple(
        a for a in blender3d.SURGERY
        if a not in ("boolean", "curve_path", "sockets", "material_pbr",
                     "pose_apply", "physics_bake"))
    if action not in batchable:
        return "batch로 할 수 있는 action: " + ", ".join(batchable)

    if action == "contact_sheet":                # 폴더의 3D 파일 전부 1컷씩 → 몽타주 한 장
        exts = (".blend", ".fbx", ".obj", ".glb", ".gltf", ".stl")
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(exts))[:36]
        if not files:
            return f"{folder}에 3D 파일(blend·fbx·obj·glb·stl)이 없습니다."
        if not _confirm(f"{folder}의 3D 파일 {len(files)}개를 1컷씩 렌더해 "
                        "'뭐가 뭔지 한눈에' 시트 한 장으로 만들까요? (원본은 읽기만, 파일당 ~10초)"):
            return "사용자가 거부했습니다."
        size = min(max(int(args.get("size", 384)), 128), 768)
        tmp = os.path.join(folder, f"_sheet_{time.strftime('%H%M%S')}")
        os.makedirs(tmp, exist_ok=True)
        shots = []                               # (파일명, png경로 또는 None, 실패 사유)
        try:
            for i, fn in enumerate(files):
                src = os.path.join(folder, fn)
                stem2 = f"s{i:02d}"
                try:
                    if fn.lower().endswith(".blend"):
                        r = blender3d.run("render", src, _config, out_dir=tmp,
                                          stem=stem2, angles=1, size=size)
                        shot = (r.get("renders") or [None])[0]
                    else:
                        shot = os.path.join(tmp, stem2 + ".png")
                        blender3d.run("shot", None, _config, src=src, dest=shot, size=size)
                    ok = bool(shot) and os.path.isfile(shot)
                    shots.append((fn, shot if ok else None, "" if ok else "렌더 실패"))
                except Exception as e:
                    shots.append((fn, None, str(e)[:60]))
            from PIL import Image, ImageDraw, ImageFont
            import math as _math
            cols = max(1, _math.ceil(_math.sqrt(len(shots))))
            rows = _math.ceil(len(shots) / cols)
            label_h = 22
            sheet = Image.new("RGB", (cols * size, rows * (size + label_h)), (24, 24, 28))
            try:                                 # 한글 파일명 라벨 — 맑은고딕
                font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 14)
            except OSError:
                font = ImageFont.load_default()
            d = ImageDraw.Draw(sheet)
            for i, (fn, shot, err) in enumerate(shots):
                x = (i % cols) * size
                y = (i // cols) * (size + label_h)
                if shot:
                    im = Image.open(shot).convert("RGB")
                    im.thumbnail((size, size))
                    sheet.paste(im, (x + (size - im.width) // 2, y + (size - im.height) // 2))
                else:
                    d.text((x + 8, y + size // 2), "X " + err, fill=(230, 120, 120), font=font)
                d.text((x + 6, y + size + 3), fn[:40], fill=(235, 235, 235), font=font)
            dest = os.path.join(folder, f"{os.path.basename(folder)}_한눈에.png")
            if os.path.exists(dest):
                dest = os.path.join(folder,
                                    f"{os.path.basename(folder)}_한눈에_{time.strftime('%H%M%S')}.png")
            sheet.save(dest)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ok_n = sum(1 for _, s, _ in shots if s)
        L = [f"컨택트 시트를 만들었습니다: {dest} ({ok_n}/{len(shots)}컷, {cols}×{rows}칸)"]
        for fn, s, err in shots:
            if not s:
                L.append(f"  ✗ {fn} — {err}")
        return ("\n".join(L)
                + "\n(웹에서는 시트가 바로 보입니다 — 그림 밑에 파일명이 적혀 있습니다.)")

    if action == "convert":
        fmt = str(args.get("format", "")).lower()
        if fmt not in ("fbx", "obj", "glb"):
            return "convert 일괄은 format(fbx·obj·glb)이 필요합니다."
        srcs = []
        for e in (".fbx", ".obj", ".glb", ".gltf", ".stl"):
            srcs += _glob.glob(os.path.join(folder, "*" + e))
        srcs = sorted(s for s in srcs if not s.lower().endswith("." + fmt))
    else:
        srcs = sorted(_glob.glob(os.path.join(folder, "*.blend")))
    if not srcs:
        return f"{folder}에서 '{action}' 대상 파일을 못 찾았습니다."

    if not _confirm(f"{folder}의 파일 {len(srcs)}개에 '{action}'을 한 번에 적용할까요? "
                    "원본은 그대로 두고 각 파일 옆에 결과물만 만듭니다(파일당 최대 5분)."):
        return "사용자가 거부했습니다."

    results = []
    for src in srcs:
        stem = os.path.splitext(os.path.basename(src))[0]
        try:
            if action == "info":
                r = blender3d.run("info", src, _config)
                results.append((src, True, f"폴리 {r['total_polys']:,}·오브젝트 "
                                           f"{len(r['objects'])}·최대 {r['max_dimension']}m"))
            elif action == "convert":
                dest = os.path.join(folder, f"{stem}.{fmt}")
                if os.path.exists(dest):
                    dest = os.path.join(folder, f"{stem}_{time.strftime('%H%M%S')}.{fmt}")
                r = blender3d.run("convert", None, _config, src=src, format=fmt, dest=dest)
                results.append((src, True, os.path.basename(r.get("exported", dest))))
            else:                                # 수술·prep_unity — 사본에서만
                copy = blender3d.work_copy(src)
                kw = {"preview_dir": folder,
                      "stem": os.path.splitext(os.path.basename(copy))[0]}
                if action == "scale_to":
                    kw["height"] = float(args.get("height", 1.0))
                if action == "decimate":
                    kw["ratio"] = float(args.get("ratio", 0.5))
                if action == "tex_resize":
                    kw["max_px"] = int(args.get("max_px", 1024))
                if action == "bone_template":
                    kw["kind"] = str(args.get("kind", "humanoid")).lower()
                if action == "repair" and args.get("remesh"):
                    kw["remesh"] = True
                if action == "uv_atlas":
                    kw["size"] = int(args.get("size", 2048))
                    kw["png_dest"] = os.path.join(
                        folder, os.path.splitext(os.path.basename(copy))[0] + "_atlas.png")
                if action == "prep_unity":
                    kw["fbx_dest"] = os.path.join(folder, f"{stem}.fbx")
                try:
                    blender3d.run(action, copy, _config,
                                  timeout=600 if action in ("uv_atlas", "repair") else 300,
                                  **kw)
                    tail = " → " + os.path.basename(kw["fbx_dest"]) if action == "prep_unity" else ""
                    results.append((src, True, os.path.basename(copy) + tail))
                except Exception as e:
                    if os.path.isfile(copy):
                        os.remove(copy)
                    results.append((src, False, str(e)[:80]))
        except Exception as e:
            results.append((src, False, str(e)[:80]))

    ok = sum(1 for _, s, _ in results if s)
    lines = [f"일괄 '{action}' — {ok}/{len(results)}개 성공"]
    for src, s, note in results:
        lines.append(f"  {'✓' if s else '✗'} {os.path.basename(src)} — {note}")
    return "\n".join(lines)


def add_reminder(args):
    """예약을 잡습니다. 실제로 알리거나 수행하는 것은 notify.py(작업 스케줄러)입니다."""
    what = (args.get("what") or "").strip()
    at = (args.get("at") or "").strip()
    repeat = (args.get("repeat") or "once").strip()
    kind = (args.get("kind") or "notify").strip()
    if not what or not at:
        return "오류: what(무엇을)과 at(언제)이 필요합니다."
    try:
        item = reminders.add(what, at, repeat, kind)
    except ValueError as e:
        return f"오류: {e}"
    return "예약했습니다 → " + reminders.describe(item)


def list_reminders(args):
    items = reminders.all_items()
    if not items:
        return "예약된 알림이 없습니다."
    return "예약 목록:\n" + "\n".join("  " + reminders.describe(i) for i in items)


def cancel_reminder(args):
    needle = (args.get("about") or "").strip()
    if not needle:
        return "오류: 지울 예약의 번호나 내용 일부가 필요합니다."
    gone = reminders.cancel(needle)
    if not gone:
        return f"'{needle}'에 해당하는 예약을 찾지 못했습니다."
    return "지웠습니다:\n" + "\n".join("  " + reminders.describe(i) for i in gone)


# (옛 generate_image는 삭제했습니다 — draw와 하는 일이 같은데 Pollinations가 돌려주는
#  JPEG를 무조건 .png로 저장해서, 루시가 이쪽을 고르면 restyle 2단계가 깨졌습니다.
#  그림은 draw(뼈대) → restyle(화풍) 한 길만 남깁니다.)


# ── 모델에게 알려줄 도구 명세 ──────────────────────────────────────
def _spec(name, desc, props, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


_S = {"type": "string"}
_N = {"type": "integer"}

SPECS = [
    _spec("now", "현재 날짜와 시각을 확인한다. 날짜·요일·시간이 관련되면 추측하지 말고 반드시 이걸 쓴다.", {}, []),
    _spec("read_file", "파일 내용을 읽는다.", {"path": _S}, ["path"]),
    _spec("write_file", "파일에 내용을 저장한다(사용자 확인 후 실행됨).", {"path": _S, "content": _S}, ["path", "content"]),
    _spec("list_dir", "폴더 안의 파일 목록을 본다.", {"path": _S}, ["path"]),
    _spec("read_document",
          "워드(.docx)·엑셀(.xlsx)·파워포인트(.pptx)·한글(.hwpx)·PDF를 읽는다. 문서를 요약하거나 분석해달라는 요청에 쓴다. "
          "PPTX는 슬라이드별로, 엑셀은 시트별로 정리해서 돌려준다. 구형 .hwp는 못 읽는다(한글에서 HWPX로 재저장 안내).",
          {"path": _S, "limit": _N}, ["path"]),
    _spec("write_document",
          "워드(.docx)·파워포인트(.pptx)·엑셀(.xlsx)·한글(.hwpx) 문서를 만든다(사용자 확인 후 저장됨). "
          "'기획서/보고서/발표자료/표로 정리해줘', '한글 파일로 만들어줘' 같은 요청에 쓴다. path의 확장자가 형식을 정한다. "
          "content는 마크다운으로 쓴다:\n"
          "  '# 제목'  → 워드는 큰 제목, PPT는 **새 슬라이드의 시작**(슬라이드마다 '# 제목'을 하나씩 둔다)\n"
          "  '## 소제목', '- 글머리표', 그냥 문장 → 본문\n"
          "  '노트: ...' → PPT의 발표자 노트\n"
          "엑셀은 대신 마크다운 표(| 항목 | 값 |)나 CSV로 준다. title은 문서 제목(엑셀은 시트 이름). "
          "워드 본문에 마크다운 표를 넣으면 진짜 표가 된다(PPT에서는 글줄로 펴짐). "
          "슬라이드는 글머리표 5~6줄을 넘기지 마라(넘치면 화면 밖으로 나간다).\n"
          "한글(.hwpx)은 제목·소제목·글머리표·문단이 되고 표는 아직 글줄로 펴진다(구형 .hwp로는 못 만든다 — 한글에서 열어 다른 이름으로 저장). "
          "path에 폴더를 안 적으면 바탕화면에 저장된다(바탕화면 = C:/Users/user/Desktop). "
          "바탕화면에 두라는 말을 들었으면 파일명만 넘겨도 되고, 폴더를 찾겠다고 list_dir을 쓰지 마라. "
          "⚠️이미 있는 문서를 고칠 때는 이걸로 덮어쓰지 말고 edit_document를 써라(서식이 산다).",
          {"path": _S, "content": _S, "title": _S, "sheet": _S}, ["path", "content"]),
    _spec("edit_document",
          "이미 있는 워드(.docx)·PPT(.pptx)·엑셀(.xlsx)을 고친다 — find의 문구를 replace로 바꾸고, append의 "
          "마크다운을 끝에 덧붙인다(워드=문단, PPT=새 슬라이드, 엑셀=바꾸기만. 사용자 확인 후). "
          "'문서/PPT/엑셀 고쳐줘·바꿔줘·슬라이드 추가해줘'면 새로 만들지 말고 이걸 써라 — 원본의 서식·표·그림이 그대로 산다. "
          "append는 '# 제목'마다 슬라이드 한 장, '노트:'는 발표자 노트. "
          "find는 문서에 실제로 있는 문구를 정확히 그대로 넣어야 한다 — 모르면 먼저 read_document로 확인해라. "
          "엑셀 숫자 셀은 값 전체가 정확히 일치해야 바뀌고 수식 셀은 건드리지 않는다. "
          "문단 하나를 통째로 다시 쓰려면 find에 그 문단 전체를 넣어라. 고치기 전 원본이 자동 백업된다.",
          {"path": _S, "find": _S, "replace": _S, "append": _S}, ["path"]),
    _spec("blender_3d",
          "블렌더 3D: 리깅(rigging: bone_template, auto_weight, weight_transfer)·애니메이션(animation: pose_apply, anim_edit, anim_merge, physics_bake)·모델링·렌더 수행. "
          "⭐**어떤 기능이 있는지 기억으로 답하지 말 것 — action=help로 전체 목록을 조회한 뒤 답한다**"
          "(설명이 길어 빠뜨리기 쉽다. '그 기능은 없다/추가해야 한다'고 말하기 전에 반드시 help를 먼저 부른다). "
          "확인·미리보기·유니티 내보내기·LOD·조형·씬 조립·재질/애니/웨이트 손질에 더해 애니 합본·베이킹·아틀라스·불리언·메시 수리·부착점·기획서용 렌더까지. "
          "action: help(기능 목록 — 파일 없이 즉시)·info(구성확인)·check(유니티 반입 점검=진단만)·compare(두 .blend 차이표, path2 필요)·render(미리보기)·"
          "anim_preview(애니메이션을 GIF로, 애니 없으면 턴테이블)·export(FBX/GLB)·unity_export(텍스처가 갈색으로 사라지는 문제 방지)·"
          "convert(fbx·obj·glb·stl 형식변환)·lod(LOD0/1/2를 유니티 자동 인식 _LODn 이름으로 한 FBX에)·"
          "build(치수 스펙으로 프리미티브 소품·그레이박스 조립)·text3d(3D 글자 간판, text+path, 한글 됨)·"
          "assemble(여러 3D 파일을 좌표대로 한 씬에 배치)·chain(여러 수술 한 번에)·prep_unity(유니티용 원클릭 정리+FBX)·"
          "anim_merge(믹사모류 애니 FBX 여러 개를 path의 리깅된 캐릭터에 클립으로 합본해 한 FBX로, anims=[fbx…] — 본 이름이 다르면 정직하게 건너뜀)·"
          "bake(하이폴리 디테일을 로우폴리의 normal/AO PNG로 굽기 — decimate·lod와 세트로 '폴리 줄여도 디테일 유지', high·low 이름 생략하면 폴리 수로 자동)·"
          "beauty_render(기획서용 렌더 — 3점 조명+바닥 그림자+투명 배경 PNG, 점검용 render와 별개), "
          "수술=apply·origin·scale_to·cleanup·uv·decimate·join·auto_weight·bone_template·tex_resize·"
          "mirror·array·scatter·collider·materials·split·anim_edit·weight_transfer·"
          "repair(check가 찾은 구멍·퇴화면·비매니폴드를 단계 수리, 전/후 수치 비교·remesh=true면 복셀 리메시까지)·"
          "boolean(items=[{target,tool,mode:union/difference/intersect}] CSG — 그레이박스에 창문 뚫기, tool은 기본 삭제)·"
          "curve_path(points=[[x,y,z]…] 경로로 mode=pipe 관/ribbon 띠/array 오브젝트 배열, radius·width·cyclic)·"
          "sockets(items=[{name,pos,rot_deg,parent}] 부착점 Empty 심기 — FBX에 포함되어 유니티 장착 포인트(손·총구)로)·"
          "uv_atlas(여러 오브젝트 재질·UV를 아틀라스 한 장으로 구워 합침=드로우콜 절약, size 기본 2048)·"
          "material_pbr(tex_dir 폴더의 albedo/normal/rough/metal/ao를 파일명 규칙으로 자동 매칭해 Principled 배선, Non-Color·ASCII 처리 — '갈색 덩어리' 예방)·"
          "bevel(모서리 챔퍼 width·segments·angle 제한=각진 티 제거)·solidify(thickness m 두께 입히기=종이장 벽 보강)·"
          "shade(mode=auto 각도 기준 자동 스무스/smooth/flat, angle 기본 30)·"
          "lightmap_uv(유니티 라이트맵용 UV2 깔기, margin)·rename(오브젝트·재질 ASCII 일괄 개명, prefix 선택 — 본은 안 건드림)·"
          "normals(법선 전수진단+수리: signed volume 음수=뒤집힌 메시를 바깥으로 — '안쪽이 비쳐 보임·데칼 안 보임' 근절)·"
          "align(mode=ground 바닥 스냅/row 일렬/grid 격자, gap·axis·cols)·purge(미사용 고아 데이터 청소=파일 다이어트, fake user 찌꺼기는 include_fake=true)·"
          "pose_apply(poses=[{frame,bones:{본:{rot_deg,loc}}}] 포즈를 키프레임으로 — 포즈 수치는 설계자가, 확인은 anim_preview)·"
          "physics_bake(mode=rigid 떨어뜨려 안착을 키프레임으로 굽기/cloth 천 드리워 고정, frames·target)·"
          "sculpt_displace(⭐표면에 유기적 요철 — pattern=bumpy 뭉실한 요철(빵·반죽)/wrinkle 불규칙 주름(토마토·채소)/"
          "groove 결·골(빵 골결·고기 결)/cell 오돌토돌 알갱이(참깨·치즈)/rough 미세 거칠기, "
          "strength 깊이 m·feature 무늬 크기 m·subdiv 면 분할 0~4(기본 2, 레벨당 면 4배)·targets·seed. "
          "브러시 스컬프가 아니라 절차적 변위다 — **형태는 안 만들고 표면만 거칠게 한다**. "
          "build로 덩어리를 먼저 맞춘 뒤 쓴다. 면이 크게 늘므로 유니티행은 decimate+bake(노멀맵)와 세트로). "
          "원본 .blend는 절대 안 고친다 — 수술은 원본을 복사한 사본에만 반영. "
          "anim_preview는 움직임을 GIF로 만들어 사람이 눈으로 확인하게 한다(frames 4~24, fps). "
          "bone_template은 휴머노이드/네발(kind) 표준 뼈대를 몸 크기에 맞춰 놓는다(bind=true면 자동 웨이트까지) — 출발점용. "
          "tex_resize는 max_px(기본 1024) 초과 텍스처 축소. lod는 lods(비율, 기본 [1,0.5,0.25]). "
          "build는 parts=[{shape:cube·cylinder·sphere·cone·torus·plane, size,pos는 [x,y,z]미터, rot_deg, color:[r,g,b] 0~1, name}]와 path(새 파일명). "
          "assemble은 items=[{file,pos,rot_deg,scale}]와 path(새 씬 이름), export=fbx/glb면 내보내기까지. "
          "mirror(axis=x 대칭 완성=반쪽만 모델링했을 때), array(mode=linear는 offset 간격·radial은 radius 원형, count개), "
          "scatter(count개를 area [가로,세로]m 안에 랜덤 배치, seed 같으면 같은 배치=나무·돌 뿌리기. "
          "오브젝트가 여럿인 파일은 그중 하나씩 골라 뿌리니 한 세트로 뿌리려면 join 먼저), "
          "collider(메시마다 저폴리 콘벡스 헐 '이름_collider' 생성, combined=true면 전체 하나·max_tris 상한), "
          "materials(중복 재질 .001 병합, ascii=true면 이름 영문화, colors={재질명:[r,g,b]}로 색 변경), "
          "split(join의 역 — mode=loose 떨어진 조각/material 재질별 분리), "
          "anim_edit(액션 손질: new_name 개명·trim=[시작,끝] 구간만 남기기·loop=true 첫=끝 프레임 루프화), "
          "weight_transfer(source 메시의 본 웨이트를 targets(기본: 웨이트 없는 메시들)에 근접 전사=옷·장비 입히기). "
          "각 수술: apply(스케일·회전 적용=유니티 크기 어긋남 방지), origin(바닥중심을 원점으로), scale_to(키를 height m로), "
          "cleanup(중복정점·법선 정리), uv(UV 자동펼침), decimate(폴리 줄이기 ratio 0~1), join(메시 한 덩어리로), "
          "auto_weight(이미 본이 놓인 리그에 살 붙이기), unity_export(bake_decal=true면 투명 데칼 구워 불투명화). "
          "build·assemble에는 subject(무엇을 만드는 것인지 한 낱말: 예 '토마호크 스테이크')를 같이 준다 — "
          "만든 뒤 눈이 '무엇으로 보이는지' 대조해 엉뚱한 물건이 나온 걸 잡는다(안 주면 파일 이름으로 대신함). "
          "⭐**subject·path(파일 이름)는 반드시 지금 사용자가 만들라고 한 그 대상에서 따온다** — "
          "기억·문맥에 떠 있는 다른 프로젝트 이름(예 '샐러드팜' 등)을 파일명으로 쓰지 마라(엉뚱한 이름 사고 실측). "
          "무엇을 만들지·어떤 이름으로 저장할지 분명치 않으면 지어내지 말고 **사용자에게 되물어라**. "
          "⭐**사진을 그대로 3D 모델로 뽑아주는 기능은 없다** — 참조 사진을 받아도 build는 사진을 보고 자동 재현하지 못한다. "
          "사진처럼 만들어 달라는 요청에는 정직하게 그 한계를 먼저 말하고, 치수·형태를 설명받거나 그레이박스 근사로 할지 확인한다. "
          "info·check·compare·help 빼고 사용자 확인 후 실행. "
          "⭐**유기적 '형태'는 못 만든다** — build는 각진 프리미티브 조립, sculpt_displace는 표면 요철까지다. "
          "브러시 스컬프·리토폴로지·헤어·텍스처 페인팅은 없다. 형태 설계가 필요한 일은 도구를 늘려도 안 되니 사람(설계자)에게 넘긴다.",
          {"action": _S, "path": _S, "path2": _S, "angles": _N, "size": _N, "format": _S,
           "height": _N, "ratio": {"type": "number"}, "force": {"type": "boolean"},
           "ops": _S, "export": _S, "bake_decal": {"type": "boolean"},
           "bg": {"type": "array", "items": {"type": "number"}},
           "frames": _N, "fps": _N, "mode": _S, "kind": _S, "bind": {"type": "boolean"},
           "max_px": _N, "lods": {"type": "array", "items": {"type": "number"}},
           "parts": {"type": "array", "items": {"type": "object"}},
           "items": {"type": "array", "items": {"type": "object"}},
           "text": _S, "depth": {"type": "number"}, "font": _S,
           "color": {"type": "array", "items": {"type": "number"}},
           "axis": _S, "count": _N, "offset": {"type": "array", "items": {"type": "number"}},
           "radius": {"type": "number"}, "center": {"type": "array", "items": {"type": "number"}},
           "area": {"type": "array", "items": {"type": "number"}}, "seed": _N,
           "jitter": {"type": "number"}, "combined": {"type": "boolean"}, "max_tris": _N,
           "dedupe": {"type": "boolean"}, "ascii": {"type": "boolean"},
           "colors": {"type": "object"}, "name": _S, "new_name": _S,
           "trim": {"type": "array", "items": {"type": "number"}}, "loop": {"type": "boolean"},
           "shift": {"type": "boolean"}, "source": _S,
           "targets": {"type": "array", "items": _S},
           "anims": {"type": "array", "items": _S}, "maps": {"type": "array", "items": _S},
           "high": _S, "low": _S, "extrusion": {"type": "number"}, "samples": _N,
           "width": {"type": "number"}, "angle": {"type": "number"},
           "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
           "smooth": {"type": "boolean"}, "cyclic": {"type": "boolean"}, "object": _S,
           "sides": _N, "remesh": {"type": "boolean"}, "keep_tools": {"type": "boolean"},
           "tex_dir": _S, "segments": _N, "thickness": {"type": "number"},
           "margin": {"type": "number"}, "prefix": _S, "gap": {"type": "number"},
           "cols": _N, "poses": {"type": "array", "items": {"type": "object"}},
           "ground": {"type": "boolean"}, "target": _S,
           "include_fake": {"type": "boolean"},
           # 세션67: sculpt_displace(표면 요철) + subject(만든 것이 무엇으로 보이나 대조용)
           "pattern": _S, "strength": {"type": "number"}, "feature": {"type": "number"},
           "subdiv": _N, "subject": _S},
          ["action", "path"]),
    _spec("edit_video",
          "동영상 편집 — action은 trim(자르기,start·end)·subtitle(자막)·audio(소리 mp3 추출)·join(이어붙이기,paths)·"
          "convert(변환/압축,width)·speed(배속,rate)·gif(움짤)·frame(장면을 사진으로,at) 중 하나다(사용자 확인 후 실행). "
          "'영상 잘라줘/자막 넣어줘/소리만 뽑아줘/움짤 만들어줘/배속해줘'에 쓴다. 원본은 안 건드리고 새 파일을 만든다. "
          "subtitle은 srt(자막 파일 경로)를 주면 그걸 입히고, 안 주면 영상의 말소리를 받아써 자막을 자동으로 만들어 입힌다. "
          "'회의 영상 받아써줘'는 두 단계: audio로 mp3를 뽑고 그 경로로 transcribe_audio. "
          "시각은 '90'(초)이나 '1:30' 모양. 폰에서 올린 영상이면 uploads 경로가 대화에 적혀 있다.",
          {"action": _S, "path": _S, "paths": {"type": "array", "items": _S}, "output": _S,
           "start": _S, "end": _S, "rate": {"type": "number"}, "width": _N, "at": _S, "srt": _S},
          ["action"]),
    _spec("find_files",
          "내 컴퓨터에서 파일을 찾는다. name은 파일명 패턴(예: *.py, 예산*.xlsx), "
          "contains는 파일 안에 든 문구. 경로를 모를 때 이걸로 먼저 찾는다.",
          {"path": _S, "name": _S, "contains": _S}, []),
    _spec("search_files",
          "사용자의 PC에 있는 문서를 **내용으로** 찾는다(바탕화면·문서·다운로드). "
          "PDF·워드·엑셀·PPT 속 글자까지 뒤지므로, 파일명을 모르고 '작년에 쓴 그 계약서', "
          "'예산 정리한 엑셀' 처럼 내용만 기억날 때 이걸 써라. "
          "(find_files는 파일명을 알 때, search_files는 내용만 알 때. "
          "search_knowledge는 사용자가 일부러 넣어둔 학습 자료 전용이라 여기와 다르다.) "
          "찾은 뒤 내용을 자세히 봐야 하면 그 경로로 read_document를 부른다. "
          "'폰으로 줘/보내줘'라고 하면 찾은 파일의 **전체 경로를 답에 그대로 적어라** — "
          "웹 화면이 그 경로를 내려받기 링크로 바꿔준다.",
          {"query": _S, "top_k": _N}, ["query"]),
    _spec("check_mail",
          "사용자의 지메일을 읽는다(읽기 전용 — 보내지는 못한다). "
          "query는 지메일 검색 문법을 그대로 쓴다: 안 읽은 메일=is:unread, "
          "특정인=from:홍길동, 최근 이틀=newer_than:2d, 중요=is:important. "
          "'메일 왔어?', '안 읽은 메일 요약해줘' 같은 부탁에 쓴다.",
          {"query": _S, "limit": _N}, []),
    _spec("list_events",
          "사용자의 구글 캘린더에서 앞으로의 일정을 본다. days는 며칠 앞까지 볼지(기본 7일, 오늘만 보려면 1). "
          "'오늘 일정 뭐 있지?', '이번 주 뭐 있어?' 같은 부탁에 쓴다.",
          {"days": _N}, []),
    _spec("add_event",
          "구글 캘린더에 일정을 넣는다(사용자 확인 후 등록됨). "
          "start는 '2026-07-15 14:00' 형식, 시각 없이 '2026-07-15'만 주면 종일 일정이 된다. "
          "⚠️ 날짜를 짐작하지 마라 — '다음 주 화요일' 같은 말을 들으면 먼저 now로 오늘이 며칠인지 확인하고 계산해라. "
          "attendees에 이메일(쉼표 구분)을 주면 초대 메일이 발송된다 — 사용자가 '초대해줘'라고 했을 때만.",
          {"title": _S, "start": _S, "end": _S, "description": _S, "attendees": _S},
          ["title", "start"]),
    _spec("draft_mail",
          "'메일 써줘/회신 초안 잡아줘'면 글을 화면에만 쓰지 말고 **반드시 이 도구로** 지메일 초안함에 넣어라. "
          "보내지는 않는다 — 발송은 사용자가 지메일에서 직접 누른다. "
          "to는 받는이 이메일(모르면 비워도 됨), subject는 제목, body는 본문 전체(네가 정중하게 작성). "
          "보냈다고 말하지 마라 — 초안함에 넣었다고만 말해라.",
          {"to": _S, "subject": _S, "body": _S}, ["subject", "body"]),
    _spec("transcribe_audio",
          "녹음 파일(m4a·mp3·wav 등)을 글로 받아쓴다. '이 녹음 받아써줘', '음성메모 정리해줘'처럼 "
          "**파일이 이미 있을 때** 쓴다(그 자리에서 말하는 건 도구 없이 '음성' 입력). "
          "path는 파일 경로 — 폰에서 올린 파일이면 uploads 폴더 경로가 대화에 적혀 있다. "
          "받아쓴 글을 그대로 두지 말고 요청에 맞게 정리(요약·할 일 추출)해서 답해라.",
          {"path": _S, "language": _S}, ["path"]),
    _spec("web_search", "웹을 빠르게 검색해 제목·요약·주소를 본다. 간단한 사실 확인용.", {"query": _S}, ["query"]),
    _spec("research",
          "깊이 조사한다. 검색어 여러 개로 찾고 상위 페이지를 실제로 열어 읽은 뒤 출처와 함께 정리해준다. "
          "정확도가 중요하거나 여러 곳을 비교해야 하는 질문에 쓴다(20~40초 걸림). "
          "queries에는 서로 다른 각도의 검색어를 2~3개 넣어라.",
          {"question": _S, "queries": {"type": "array", "items": _S}, "depth": _N}, ["question"]),
    _spec("fetch_url", "특정 웹페이지의 본문을 읽는다. 보통 web_search로 주소를 찾은 뒤 사용한다.", {"url": _S}, ["url"]),
    _spec("calc",
          "숫자 계산을 한다. 암산하지 말고 반드시 이걸 써라(언어모델은 큰 수 계산을 자주 틀린다). "
          "예: (1234*56)/7, sqrt(2), 2^10",
          {"expression": _S}, ["expression"]),
    _spec("run_python",
          "파이썬 코드를 실행한다(사용자 확인 후 실행됨). 여러 단계 계산, 데이터 처리, 파일 변환처럼 "
          "말로 하기 힘든 일에 쓴다. 결과는 print()로 찍어야 보인다.",
          {"code": _S}, ["code"]),
    _spec("draw",
          "[그림 1단계] 그림을 그린다. 온라인 Flux로 구도·손가락·글자가 멀쩡한 뼈대를 만든다(무료, 내 GPU를 쓰지 않음). "
          "prompt는 반드시 영어로 상세하게 써라(피사체, 구도, 조명, 배경, 화풍 순으로). "
          "사용자가 한국어로 요청해도 영어 묘사로 옮겨서 넣는다.",
          {"prompt": _S, "width": _N, "height": _N, "seed": _N}, ["prompt"]),
    _spec("restyle",
          "[그림 2단계] draw로 만든 그림을 로컬 SD 1.5 병합 모델로 덧칠해 사용자의 화풍으로 바꾼다. "
          "image_path에는 draw가 돌려준 경로를, prompt에는 원하는 화풍을 영어로 넣는다. "
          "denoising_strength는 0.3~0.4가 기본(높이면 원본 구도가 무너진다). "
          "사용자가 '내 화풍으로', '스타일 바꿔줘'라고 할 때만 쓴다. 로컬 GPU를 쓰므로 1~3분 걸린다.",
          {"image_path": _S, "prompt": _S, "denoising_strength": {"type": "number"}, "size": _N},
          ["image_path", "prompt"]),
    _spec("remember", "앞으로도 계속 알아야 할 사실을 장기 기억에 저장한다.", {"fact": _S}, ["fact"]),
    _spec("recall", "장기 기억에 저장된 내용을 전부 불러온다.", {}, []),
    _spec("search_knowledge",
          "사용자의 지식 창고를 찾아본다 — 자기 프로젝트(샐러드팜·알약 게임·루시 사용법)나 게임 기획(재미·밸런스·수치·레벨·보상) "
          "질문이면 답하기 전에 언제나 먼저 이걸 찾아라(추측 금지). 들어 있는 세 종류마다 쓰는 규칙이 다르다.\n"
          "\n①프로젝트 노트 (샐러드팜 게임, 알약 게임 기획, AI 모델 학습, 빌드·아트 규칙 등 작업 내역) "
          "— 사용자가 자기 프로젝트를 물으면 **언제나 먼저** 이걸 찾아라. 추측해서 답하지 마라. "
          "예전에 종 수를 기억으로 답했다가 틀린 적이 있다. "
          "**유니티 C#을 짜기 전엔 '유니티 치트시트'를 찾아라**(unity_csharp_치트시트 — Unity 6 폐기 API·프로젝트 관례·작업 순서). "
          "**3D 에셋의 폴리·텍스처·재질이 적당한지 물으면 '모바일 기준표'를 찾아라**(blender_모바일_기준표 — 예산 수치·근거·처방).\n"
          "\n②게임 기획 교재 (공개 강의 슬라이드 13종) — 이상균의 기획 튜토리얼·기획서 작성법, GDC2008 기획서 작성법, "
          "구승모의 '게임제작개론' 시리즈 #1 구성요소·#2 세부디자인(레벨·전투·UI)·#4 밸런싱·#5 플레이어 이해·#6 시스템 구조·#7 팀과 리소스, "
          "김준태의 레벨 디자인의 구성, 모바일 기획 실습, 매출 시뮬레이션, 밸런싱 핸드북(수치 계산법).\n"
          "— 게임 기획을 물으면(재미·시스템·밸런스·수치·기획서·레벨·보상·경제·유저 동기·팀) **언제나 먼저** 이걸 찾아라. "
          "③과 달리 사용자가 먼저 '교재로'라고 말하지 않아도 쓴다. 사용자는 게임을 만드는 사람이므로 "
          "기획 이야기는 곧 자기 일 이야기다.\n"
          "  인용할 때 저자는 **파일명 끝에 붙어 있다**(예: gamedesign_기획튜토리얼_이상균 → 저자는 이상균). "
          "본문에 나오는 인명은 대개 사례로 언급된 개발자·연구자이지 저자가 아니다. 그걸 저자로 적지 마라. "
          "파일명에서 확인되지 않으면 저자를 지어내지 말고 그냥 '지식 창고의 게임 기획 교재'라고만 말하라.\n"
          "\n③수업 자료 (2026년 1학기 '디지털마케팅 트렌드' 강의 15주차) "
          "— **사용자가 수업 자료를 원한다고 밝힐 때만** 쓴다. 예: '수업에서 배운', '학습한 내용으로', "
          "'메모리/지식창고에 있는 걸로', '교수님이', 'N주차', 시험·과제 이야기. "
          "그냥 마케팅을 물어보는 것(용어 뜻, 최신 트렌드, 업계 사례)이라면 수업 자료를 뒤지지 말고 "
          "web_search나 research로 최신 정보를 찾아 답하라. 강의는 2026년 1학기에 끝났으므로 "
          "그 뒤의 일은 여기 없고, '미래 전망' 슬라이드가 있어도 그건 예측이지 최신 소식이 아니다.\n"
          "\n④네가 스스로 공부해 둔 노트(selfstudy_*) — 예전에 조사해 정리해 둔 주제면 여기 걸린다. "
          "웹을 새로 뒤지기 전에 먼저 찾아보고, 인용할 때는 '전에 조사해 둔 것'임을 밝혀라.\n"
          "\n⑤유튜브 영상 요약(youtube_*) — 사용자가 '/유튜브'로 반입한 강연·수업 영상의 자막 요약. "
          "사용자가 '그 영상에서 뭐랬지', 'GDC 강연 내용'처럼 영상 내용을 물으면 여기 걸린다. "
          "자막 기반 자동 요약이므로 세세한 수치는 노트의 [mm:ss] 시각으로 원본 확인을 권하라.\n"
          "\n⑥너 자신의 사용설명서(manual_루시_사용설명서) — 네 명령어·도구·새벽 일과·제약이 전부 적혀 있다. "
          "사용자가 '너 뭐 할 수 있어', '그 명령어 뭐였지', '이 기능 어떻게 써', '폰에서 어떻게 접속해'처럼 "
          "**네 능력이나 사용법**을 물으면 반드시 먼저 이걸 찾아라. 추측으로 답하지 마라.",
          {"query": _S}, ["query"]),
    _spec("search_history",
          "클로드와 나눈 원본 대화 기록 전체를 키워드로 뒤진다. search_knowledge에 없는 세세한 내용"
          "(그때 무슨 오류였는지, 왜 그렇게 정했는지)이 필요할 때만 쓴다. 결과가 길고 맥락이 잘려 있다.",
          {"keyword": _S, "limit": _N}, ["keyword"]),
    _spec("search_my_history",
          "**너와 사용자가** 나눈 지난 대화를 찾는다(낱말+의미 검색 — 말이 정확히 안 겹쳐도 찾음). "
          "사용자가 '지난번에 내가 뭐라고 했지', '어제 얘기한 그거', '전에 말한 그 식당' 처럼 "
          "**너와 나눈 이야기**를 물으면 이걸 써라. "
          "장기 기억(recall)에는 '앞으로도 알아야 할 사실'만 남아서, 흘러간 이야기는 여기에만 있다. "
          "클로드와의 기록을 뒤지는 search_history와 혼동하지 마라.",
          {"keyword": _S, "limit": _N}, ["keyword"]),
    _spec("read_clipboard",
          "사용자가 방금 복사(Ctrl+C)해 둔 글을 읽는다. '이거 요약해줘', '복사한 거 봐줘', "
          "'클립보드에 있는 오류 뭐야' 처럼 붙여넣지 않고 가리키기만 할 때 쓴다.",
          {}, []),
    _spec("forget",
          "장기 기억을 지운다. 사용자가 '그거 틀렸어', '그 기억 지워'라고 하면 반드시 이 도구를 써라. "
          "about에는 지울 기억에 들어 있는 말을 넣는다(예: '치과'). "
          "이 도구를 쓰지 않고 '지웠다'고 답하는 것은 거짓말이다 — 절대 하지 마라.",
          {"about": _S}, ["about"]),
    _spec("run_powershell", "윈도우 파워셸 명령을 실행한다(사용자 확인 후 실행됨).", {"command": _S}, ["command"]),
    _spec("code_write",
          "코딩 작업실(workspace)에 코드 파일을 만들거나 통째로 덮어쓴다. '프로그램/앱 만들어줘'처럼 여러 파일로 짓는 일에 이걸로 파일을 쌓아라. "
          "path는 작업실 기준 상대경로(예: dedup/main.py) — 프로그램 하나는 폴더 하나로 묶어라. 확인 없이 저장된다(작업실 밖은 못 건드림).",
          {"path": _S, "content": _S}, ["path", "content"]),
    _spec("code_read", "코딩 작업실의 파일 내용을 읽는다. 고치기 전에 지금 코드를 확인할 때 쓴다.",
          {"path": _S}, ["path"]),
    _spec("code_edit",
          "코딩 작업실 파일에서 find에 준 부분만 replace로 바꾼다(파일을 통째로 다시 안 써도 됨). 에러 한두 줄 고칠 때 쓴다. "
          "같은 내용이 여러 곳이면 앞뒤를 더 붙여 범위를 넓히거나 all=true. 못 찾으면 code_read로 원문부터 확인해라.",
          {"path": _S, "find": _S, "replace": _S, "all": {"type": "boolean"}}, ["path", "find", "replace"]),
    _spec("code_run",
          "코딩 작업실의 프로그램을 실행하고 출력·에러(트레이스백)·종료코드를 돌려준다. 만든 프로그램을 돌려보고, 에러가 나면 code_edit로 고쳐 다시 실행하며 완성해라. "
          ".py는 파이썬으로, .cs는 dotnet(C# 콘솔)으로 자동 실행한다(C#은 첫 빌드가 느리니 timeout을 넉넉히). "
          "ModuleNotFoundError면 code_install로 라이브러리를 깔고 다시 실행. 실행은 프로젝트마다 처음 한 번만 사용자 확인을 받는다. "
          "⚠️유니티(UnityEngine 참조) C#은 이걸로 못 돌린다 — 그건 unity_run을 써라.",
          {"path": _S, "args": _S, "timeout": _N}, ["path"]),
    _spec("code_list", "코딩 작업실에 지금 어떤 파일들이 있는지 본다.", {"path": _S}, []),
    _spec("unity_run",
          "유니티 프로젝트를 배치모드(창 없이)로 돌려 스크립트 컴파일 점검·테스트 실행·특정 메서드 실행을 시키고 결과 로그를 돌려준다. "
          "여러 파일이 얽힌 변경·테스트의 **최종 검증**용이다 — 파일 하나 고친 직후의 빠른 확인은 unity_cs_check(몇 초, 에디터 열려도 됨)를 먼저 써라. "
          "project는 별칭(saladfarm·onlyuprat) 또는 폴더 경로. tests에 'EditMode'/'PlayMode'를 주면 테스트, method에 'Class.Method'를 주면 그 메서드, 둘 다 없으면 열고 닫으며 컴파일 에러만 확인. "
          "수 분 걸리고 사용자 확인을 받으며, 에디터가 이미 열려 있으면 실패한다. 컴파일 에러는 file(줄,칸) CS코드로 정리해서 돌려주니 그걸 보고 고쳐라.",
          {"project": _S, "method": _S, "tests": _S, "timeout": _N}, []),
    _spec("unity_new_script",
          "유니티 프로젝트에 컴파일 되는 C# 스크립트 골격을 만든다(사용자 확인 후). kind로 종류를 고른다: mono(MonoBehaviour, 기본)·scriptable(ScriptableObject)·editor(EditorWindow)·test(EditMode 테스트+어셈블리)·plain. "
          "만든 뒤 내용은 unity_cs_write/unity_cs_edit로 채워라(저장 직후 자동 컴파일 검사됨). 짜기 전엔 unity_context로 관련 코드 맥락부터. project는 별칭·경로, name은 클래스 이름, folder는 기본 Assets/Scripts.",
          {"project": _S, "name": _S, "kind": _S, "folder": _S}, ["name"]),
    _spec("unity_find",
          "유니티 프로젝트의 C# 코드(Assets의 .cs)에서 낱말·이름을 찾아 파일:줄로 돌려준다. 스크립트를 새로 짜거나 고치기 전에 기존 클래스·메서드·필드가 실제로 어떻게 생겼는지 확인해 환각을 줄인다. "
          "지금 이 순간의 코드를 바로 훑는다(색인을 안 쓰므로 방금 고친 것도 잡힘). project는 별칭·경로.",
          {"project": _S, "query": _S}, ["query"]),
    _spec("unity_audit",
          "유니티 프로젝트를 감사해 문제를 찾아준다(유니티 안 띄우고 파일만 스캔 — 빠르고 안전). 깨진 스크립트 참조(누락 컴포넌트)·큰 텍스처(빌드 용량)·.meta 누락을 잡는다. "
          "리팩터·git 머지 뒤 '왜 프리팹이 깨졌지'를 확인하거나 프로젝트를 정리할 때 쓴다. project는 별칭·경로.",
          {"project": _S}, []),
    _spec("unity_status",
          "실행 중인(또는 마지막) 유니티 에디터의 컴파일 상태를 Editor.log를 읽어 확인한다. **에디터를 닫지 않고** 지금 컴파일 에러가 있는지 빠르게 볼 때 쓴다(unity_run은 에디터가 열려 있으면 실패하지만 이건 됨). "
          "'에디터의 마지막 컴파일' 기준이라, 확실한 검증은 unity_run.",
          {}, []),
    _spec("eye_trust",
          "루시의 '눈'(그림 보는 두뇌)이 믿을 만한지 시험한다('눈 믿을 만해?·눈 시험해줘·자가검수 믿어도 돼?'). 정답을 아는 그림들(정상·문제 섞음)을 보여주고 '정상/문제' 판정이 맞는지 채점한다. "
          "⭐문제인데 '정상'이라 답하는 놓침은 치명(불량이 조용히 통과)이라 2배 벌점, 반대(오탐)는 가볍게 본다. 결과대로 자가검수 때 믿는 눈부터 묻는다(명단에서 빼지는 않음). "
          "action='last'면 새로 시험하지 않고 지난 결과만 본다. 모델을 여러 번 부르니 자주 돌리지 마라(월 1회 자동).",
          {"action": _S}, []),
    _spec("unity_health",
          "작업 중인 유니티 프로젝트들이 지금 컴파일 되는 상태인지 점검한다('프로젝트 괜찮아?·건강 점검'). 등록된 프로젝트를 하나씩 배치모드로 열고 닫아 컴파일 에러를 잡는다(몇 분 걸림). "
          "에디터가 열려 있는 프로젝트는 자동으로 정적 점검(코드가 마지막 컴파일보다 새것인지)으로 대체하니 잠금 걱정 없다. 새벽 일과가 매일 자동으로 돌려 아침 브리핑에 한 줄 싣는다. "
          "project를 주면 그것만.",
          {"project": _S, "timeout": _N}, []),
    _spec("unity_build",
          "유니티 프로젝트를 배치모드로 빌드한다(APK·AAB 등, 사용자 확인 후·오래 걸림·에디터 닫혀 있어야 함). kind로 등록된 빌드를 고르거나(apk·aab·dev) method='Class.Method'로 빌드 스크립트를 직접 지정한다. "
          "project는 별칭·경로.",
          {"project": _S, "kind": _S, "method": _S, "timeout": _N}, []),
    _spec("unity_scene",
          "유니티를 안 띄우고 씬(.unity)·프리팹(.prefab)의 게임오브젝트 계층과 컴포넌트를 읽는다(읽기전용·빠름). '씬에 뭐 있어·이 프리팹 구조 봐줘'에 쓴다. "
          "path 없으면 프로젝트의 씬·프리팹 목록. MonoBehaviour는 스크립트 클래스 이름으로 보여주니 어떤 오브젝트에 어떤 스크립트가 붙었는지 파악할 수 있다. project는 별칭·경로.",
          {"project": _S, "path": _S, "limit": _N}, []),
    _spec("unity_refs",
          "유니티 에셋이 어디서 쓰이는지 참조(guid)를 추적한다(읽기전용). asset을 주면 그걸 참조하는 씬·프리팹·머티리얼 목록('이 스크립트/텍스처 어디서 써?'), 비우면 미사용 에셋 후보 보고서('안 쓰는 에셋 찾아줘'). "
          "⚠️코드에서 이름으로 로드(Resources.Load)하는 건 못 잡으니 지우기 전 unity_find로 이중 확인하라고 안내해라.",
          {"project": _S, "asset": _S}, []),
    _spec("unity_settings",
          "유니티 프로젝트 설정 요약(읽기전용) — 제품명·버전(bundleVersion)·안드로이드 버전코드·번들ID·에디터 버전·빌드에 포함된 씬 목록·define 심볼·패키지. '버전 몇이야·빌드에 씬 뭐 들어가·패키지 뭐 깔렸어'에 쓴다.",
          {"project": _S}, []),
    _spec("unity_log",
          "게임을 돌리다 난 런타임 예외(NullReference 등)를 유니티 로그에서 뽑아 종류별 횟수·스택으로 집계한다(읽기전용). '게임 실행하다 에러 났어'면 이걸 써라 — unity_status/unity_run은 컴파일 에러만 본다. "
          "source=editor(기본, 에디터 플레이)·player(빌드된 게임 실행 로그, project 필요). Assets/ 스택 프레임의 파일:줄부터 고치면 된다.",
          {"project": _S, "source": _S}, []),
    _spec("unity_outline",
          "유니티 C# 코드의 구조 개요(클래스·메서드·직렬화 필드)를 뽑는다(읽기전용). 코드를 고치기 전 전체 구조를 파악할 때 써라 — unity_find는 낱말 위치 검색, 이건 뼈대 보기. "
          "path를 주면 그 파일 상세, 없으면 프로젝트 전체 파일별 요약. project는 별칭·경로.",
          {"project": _S, "path": _S, "limit": _N}, []),
    _spec("unity_build_report",
          "유니티 빌드(APK 등) 용량을 분석한다(읽기전용) — 카테고리별(텍스처·메시…) 크기·큰 에셋 상위·직전 빌드와의 증감. '빌드 왜 커졌어·용량 뭐가 먹어'에 쓴다. "
          "unity_build로 빌드하면 리포트가 자동 저장되고, 에디터 GUI 빌드는 Editor.log에서 읽는다(에디터 재시작 전까지만 남음).",
          {"project": _S}, []),
    _spec("unity_yaml_edit",
          "씬(.unity)·프리팹(.prefab)·에셋(.asset·.mat 등)의 직렬화 값을 find→replace로 바꾼다(자동 백업+사용자 확인). 프리팹에 새 필드 기본값 명시·guid 치환 같은 기계적 수정에 쓴다. "
          "find는 파일에 실제로 있는 그대로(모르면 read_file로 확인), 여러 곳이면 all=true. ⚠️에디터가 그 파일을 열고 있으면 에디터 저장이 덮어쓸 수 있다. C# 코드는 이걸로 말고 edit_document로.",
          {"project": _S, "path": _S, "find": _S, "replace": _S, "all": {"type": "boolean"}},
          ["path", "find"]),
    _spec("unity_snapshot",
          "유니티 프로젝트의 씬·프리팹·에셋(.asset)·설정을 통째로 백업/복원한다. action=take(찍기, 기본)·list(목록)·restore(id 시점으로 되돌리기, 확인 후·복원 직전 상태도 자동 백업). "
          "큰 수정·머지 전에 찍어두고, 사고 나면 되돌린다. '백업해줘·아까로 되돌려줘'에 쓴다. id는 list의 시각(비우면 최신).",
          {"project": _S, "action": _S, "id": _S, "file": _S}, []),
    _spec("unity_diff",
          "씬·프리팹·에셋이 무엇이 달라졌는지 비교한다(읽기전용) — 추가/삭제된 게임오브젝트·바뀐 컴포넌트 값을 요약. path2를 주면 두 파일 비교, 비우면 스냅샷(snapshot=시각, 기본 최신)과 현재를 비교. "
          "'어제랑 뭐가 달라졌어·복원해도 돼?'에 쓴다. 먼저 unity_snapshot으로 찍어둔 게 있어야 스냅샷 비교가 된다.",
          {"project": _S, "path": _S, "path2": _S, "snapshot": _S}, ["path"]),
    _spec("unity_sprites",
          "스프라이트/텍스처 임포트 설정을 감사한다(읽기전용) — 같은 폴더인데 크기 제각각(도트 통일 규칙 깨짐, 프레임 전환 시 크기 널뜀)·PPU 불일치·스프라이트에 밉맵 켜짐·maxTextureSize 초과 원본. "
          "아트 반입 후 점검이나 '스프라이트 설정 확인해줘'에 쓴다. folder로 범위를 좁힐 수 있다(예: Art/Creatures).",
          {"project": _S, "folder": _S}, []),
    _spec("unity_tex_fix",
          "unity_audit·unity_sprites가 잡은 큰 텍스처를 실제로 고친다 — maxTextureSize가 max_px(기본 1024)를 넘는 .meta를 일괄 하향(원본 그림 불변·자동 백업·확인 후). "
          "'텍스처 용량 낮춰줘·임포트 설정 고쳐줘'에 쓴다. 원본 픽셀이 이미 작은 건 건너뛰고, 플랫폼 오버라이드까지 같이 낮춘다. folder로 범위 제한. ⚠️에디터가 열려 있으면 거절(수정이 덮어써짐).",
          {"project": _S, "folder": _S, "max_px": _N}, []),
    _spec("unity_models",
          "3D 모델(FBX·obj·blend·glb) 임포트 설정을 감사한다(읽기전용) — Read/Write 켜짐(메모리 2배)·스케일 팩터≠1(블렌더 apply 누락 신호)·카메라/조명 임포트 켜짐·Legacy 애니·.meta 누락·5MB↑ 모델. "
          "블렌더에서 FBX를 넣은 뒤 '모델 설정 봐줘'나 3D 에셋 반입 점검에 쓴다. unity_sprites의 3D판. folder로 범위 제한.",
          {"project": _S, "folder": _S}, []),
    _spec("unity_scene_lint",
          "씬을 모바일 성능 관점으로 린트한다(읽기전용, 유니티 안 띄움) — 카메라 여러 대·AudioListener 중복·실시간 그림자 조명·조명 과다·깨진 스크립트·Canvas 과다·무거운 씬을 씬별로 집계. "
          "'씬 성능 봐줘·왜 무거워'에 쓴다. path 없으면 빌드에 켜진 씬 전부. unity_audit(파일 무결성)·unity_scene(구조 보기)과 역할이 다르다.",
          {"project": _S, "path": _S}, []),
    _spec("unity_scene_smoke",
          "빌드 씬을 배치모드로 하나씩 실제 로드해 컴파일로는 안 잡히는 문제를 잡는다 — 누락 스크립트, 끊긴 참조(있던 에셋이 지워져 None이 된 직렬화 필드), 로드 중 예외. "
          "'빌드 전에 씬 전부 열어봐줘·씬 깨진 데 없나 검사해줘'에 쓴다. 임시 검사 스크립트를 심었다 지운다. 수 분 걸리고 사용자 확인·에디터 닫힘 필요.",
          {"project": _S, "timeout": _N}, []),
    _spec("unity_fbx_check",
          "블렌더에서 내보낸 FBX를 **진짜 유니티 프로젝트에 임포트해 왕복 검증**한다 — 재질에 텍스처가 실제로 물렸는지(_BaseMap NULL='갈색 덩어리' 신호) + 렌더 사진 + 눈검수. "
          "'이 FBX 유니티에서 잘 보일지 확인해줘·납품 전 검증'에 쓴다. FBX 옆의 텍스처(PNG 등)도 같이 넣어 외부 파일 방식 그대로 재현. 흔적은 지운다. 수 분·에디터 닫힘 필요.",
          {"path": _S, "project": _S, "timeout": _N}, ["path"]),
    _spec("unity_shot",
          "빌드 씬을 배치모드로 실제 렌더해 스크린샷 PNG로 찍는다 — '씬 어떻게 보이는지 찍어봐줘·게임 화면 보여줘·씬 스샷'에 쓴다. "
          "분홍(마젠타=재질 실종) 픽셀 자동 스캔 + 눈 달린 두뇌의 1차 검수(검은 화면·UI 깨짐)까지 붙는다. 오버레이 UI 포함, 씬은 절대 저장 안 함. "
          "scene에 이름 일부를 주면 그 씬만, landscape=true면 가로. **play=true면 플레이모드로 실제 실행해** 런타임 UI·스폰까지 찍는다('실행 화면 보여줘', 더 오래 걸림). 수 분 걸리고 사용자 확인·에디터 닫힘 필요.",
          {"project": _S, "scene": _S, "landscape": {"type": "boolean"},
           "play": {"type": "boolean"}, "timeout": _N}, []),
    _spec("unity_code_lint",
          "C# 코드를 위생 린트한다(읽기전용, 유니티 안 띄움) — Update류 안의 GameObject.Find/GetComponent/Camera.main/Instantiate(매 프레임 비용), 빈 Update(호출 비용만 냄), 빈 catch(예외 삼킴), SendMessage, Debug.Log 잔재. "
          "'코드 성능 문제 찾아줘·릴리스 전 코드 점검'에 쓴다. Editor 폴더는 제외. folder로 범위 제한. 위치는 파일:줄로 준다.",
          {"project": _S, "folder": _S}, []),
    _spec("unity_cs_check",
          "유니티 C# 파일 하나를 **몇 초 만에** 컴파일 검사한다(유니티 안 띄움·에디터 열려 있어도 됨) — 유니티 DLL과 게임 어셈블리를 참조해 문법·타입 오류를 파일(줄,칸) CS코드로. "
          "C# 스크립트를 쓰거나 고친 **직후마다** 이걸로 확인해라(unity_run은 수 분+에디터 닫힘 필요 — 최종 확인용). ⚠️검사 파일만 새로 컴파일하므로 여러 파일이 얽힌 변경의 최종 검증은 unity_run.",
          {"project": _S, "path": _S}, ["path"]),
    _spec("unity_cs_write",
          "유니티 프로젝트 Assets에 C# 파일을 만들거나 통째로 교체하고 **저장 직후 자동으로 컴파일 검사까지**(백업+확인). 스크립트 전체 내용이 준비됐을 때 쓴다(골격만 만들 땐 unity_new_script). "
          "path는 Assets/ 기준(폴더 없으면 Assets/Scripts/), content는 파일 전체. 검사에서 에러가 나오면 unity_cs_edit로 고쳐 다시 — 몇 초 루프다.",
          {"project": _S, "path": _S, "content": _S}, ["path", "content"]),
    _spec("unity_cs_edit",
          "유니티 프로젝트의 .cs에서 find의 코드를 replace로 바꾸고 **곧바로 컴파일 검사까지**(백업+확인). 컴파일 에러 한두 줄 고칠 때 쓴다 — 코딩 작업실 code_edit의 유니티판. "
          "find는 파일에 실제로 있는 그대로(모르면 unity_find·read_file 먼저), 여러 곳이면 all=true. C# 전용 — 씬·프리팹은 unity_yaml_edit.",
          {"project": _S, "path": _S, "find": _S, "replace": _S, "all": {"type": "boolean"}},
          ["path", "find"]),
    _spec("unity_context",
          "유니티 C#을 짜기 **전에** 클래스·타입 하나의 맥락을 한 방에 모은다(읽기전용) — 정의 파일의 전체 개요(메서드·직렬화 필드)+그걸 쓰는 곳들+프로젝트 네임스페이스·using 관례. "
          "'Player를 고치자/CreatureInteract에 기능 추가' 같은 작업 시작 때 먼저 이걸 불러 실제 코드 모양을 보고 짜라(없는 메서드를 지어내는 환각 방지). query는 클래스·타입 이름.",
          {"project": _S, "query": _S}, ["query"]),
    _spec("blender_batch",
          "폴더의 여러 3D 파일에 같은 블렌더 작업을 일괄로 — action=info·convert·prep_unity·수술들, contact_sheet면 전부 1컷씩 렌더해 '뭐가 뭔지' 시트 한 장(원본 불가침). "
          "수술 일괄=decimate·apply·cleanup·origin·scale_to·uv·join·tex_resize·repair·uv_atlas. "
          "여러 에셋을 한꺼번에 변환·경량화·정리할 때 쓴다. contact_sheet는 폴더의 3D 파일 전부를 1컷씩 렌더해 파일명 라벨이 붙은 시트 한 장으로 — '받은 에셋 뭐가 뭔지 한눈에 보여줘'에 쓴다. "
          "convert면 format(fbx·obj·glb), decimate면 ratio, scale_to면 height, tex_resize면 max_px(기본 1024)를 함께 준다.",
          {"folder": _S, "action": _S, "format": _S, "ratio": {"type": "number"}, "height": {"type": "number"}, "max_px": _N, "size": _N, "remesh": {"type": "boolean"}}, ["folder", "action"]),
    _spec("code_install",
          "코딩에 필요한 파이썬 라이브러리를 pip로 설치한다(사용자 확인 후). code_run에서 ModuleNotFoundError가 나면 이걸로 설치하고 다시 실행해라.",
          {"package": _S}, ["package"]),
    _spec("add_reminder",
          "정해진 때에 알려달라는 요청, 또는 정해진 때에 **네가 할 일**을 예약한다. "
          "⚠️at은 반드시 'YYYY-MM-DD HH:MM' 형식의 절대 시각이다. '내일'·'다음 주' 같은 말은 "
          "**먼저 now 도구로 오늘 날짜·요일을 확인한 뒤** 계산해서 넣어라(추측하면 엉뚱한 날에 울린다). "
          "repeat은 once(기본)·daily·weekly·monthly. 반복이면 at에는 첫 번째 차례를 넣는다.\n"
          "kind는 두 가지다:\n"
          "  notify(기본) — 그 시각에 what을 소리와 창으로 **알려준다**. ('3시에 약 먹으라고 알려줘')\n"
          "  task — 그 시각에 네가 **실제로 그 일을 한다**(도구를 쓰고 결과를 파일로 남긴다). "
          "'매주 월요일에 AI 소식 조사해서 문서로 만들어놔' 처럼 **알림이 아니라 일**을 시키면 이걸 써라. "
          "이때 what에는 나중의 네가 읽고 그대로 수행할 수 있게 지시를 온전한 문장으로 적어라.\n"
          "⚠️task는 사람이 없을 때 도는 일이라 코드·명령 실행은 거부된다(조사·문서 만들기·파일 쓰기는 된다).",
          {"what": _S, "at": _S, "repeat": _S, "kind": _S}, ["what", "at"]),
    _spec("list_reminders", "예약해 둔 알림을 전부 본다.", {}, []),
    _spec("cancel_reminder",
          "예약한 알림을 지운다. about에는 번호(예: '2')나 내용의 일부(예: '치과')를 넣는다.",
          {"about": _S}, ["about"]),
    _spec("get_weather",
          "지금·오늘·내일 날씨(기온·하늘·강수확률)와 우산 조언. 사용자가 날씨·기온·비·눈·우산을 "
          "물으면 web_search가 아니라 **반드시 이걸** 써라(더 빠르고 정확하다). "
          "location은 '수원', '부산 해운대'처럼 지역 이름. 비우면 사용자의 기본 지역.",
          {"location": _S}, []),
    _spec("get_bus",
          "버스 실시간 도착 정보(인천·부천 등 경기·서울). '버스 언제 와', '몇 분 남았어'에 "
          "web_search가 아니라 **반드시 이걸** 써라. '집 앞 버스'·'집에 갈 버스'는 "
          "stop에 '집'만 넣어라(단골 정류장을 본다). stop은 정류장 이름(예: 부평역, 부천역). "
          "bus는 버스 번호(선택 — 그 번호만 걸러 보여줌). region은 사용자가 지역을 말했을 때만 "
          "'인천'/'부천'/'서울'처럼 넘긴다(안 주면 인천→경기→서울 순으로 찾음).",
          {"stop": _S, "bus": _S, "region": _S}, ["stop"]),
    _spec("get_subway",
          "지하철(수도권 전철) 실시간 도착. '지하철/전철/1호선 언제 와'면 web_search 말고 반드시 이걸 써라. "
          "'집/우리 역'이면 station을 비워라(단골 역을 본다). station은 역 이름(예: 동암, 부평). "
          "line은 사용자가 노선을 말했을 때만(예: 1호선). 버스는 get_bus가 따로 있다.",
          {"station": _S, "line": _S}, []),
    _spec("add_todo",
          "할 일 목록에 항목을 넣는다. '~해야 해', '~ 까먹지 말아야지', '할 일에 넣어줘' 처럼 "
          "**시각이 정해지지 않은** 해야 할 일에 쓴다. 시각이 정해져 있으면 add_reminder를 써라.",
          {"what": _S}, ["what"]),
    _spec("list_todos", "할 일 목록을 본다. '할 일 뭐 있지', '뭐 하기로 했지'에 쓴다.", {}, []),
    _spec("done_todo",
          "할 일을 완료 처리한다. about에는 번호(예: '2')나 내용의 일부(예: '우유')를 넣는다. "
          "사용자가 '그거 했어', '끝냈어'라고 하면 이걸 써라 — 쓰지 않고 완료했다고 답하지 마라.",
          {"about": _S}, ["about"]),
    _spec("self_check",
          "사용자가 '목소리가 왜 이래', '알림이 안 와', '메일이 안 보여', '밖에서 접속이 안 돼', "
          "'너 고장났어?'처럼 너의 상태를 지적하면 반드시 이걸 먼저 써라 — 네 몸을 점검하고 고칠 수 있으면 고친다. "
          "'기억 검색이 이상해', '받아쓰기가 안 돼'도 마찬가지다. "
          "점검 대상: 로컬 목소리 서버·Ollama(기억 검색)·알림 스케줄러·구글 연동(토큰 권한 포함)·"
          "웹 화면 서버·디스크 여유·받아쓰기 키·ffmpeg·Tailscale(외부 접속). "
          "결과를 읽고 무엇이 문제였고 무엇을 고쳤는지 사용자에게 설명하라 — 추측으로 답하지 마라.",
          {}, []),
]


# ── 컨텍스트가 작은 두뇌용 요약 명세 ─────────────────────────────
# 명세 전체가 12,800자를 넘으면서 Cerebras(8192 토큰)가 도구 턴을 통째로 거부하게 됐습니다.
# 조향 문구를 전부 줄이면 모든 두뇌의 도구 선택이 나빠지므로, **원본은 그대로 두고**
# 작은 두뇌에게만 문장 경계로 줄인 사본을 보냅니다. 무엇이 '작은지'는 config 모델
# 블록의 "context" 필드가 정합니다(벤치의 apply가 블록을 통째로 보존해 살아남음).
def _compact(spec, limit=160):
    s = json.loads(json.dumps(spec, ensure_ascii=False))     # 깊은 복사
    text = " ".join((s["function"].get("description") or "").split())
    sents = re.split(r"(?<=[.!?])\s+", text)
    out = sents[0] if sents else ""
    for sen in sents[1:]:
        if len(out) + len(sen) + 1 > limit:
            break
        out += " " + sen
    s["function"]["description"] = out
    return s


COMPACT_SPECS = [_compact(s) for s in SPECS]

# ── 작은 두뇌용 도구 선별 ────────────────────────────────────────────
# 작은 컨텍스트 두뇌(Cerebras 8192)는 도구 41개 명세만으로 예산의 58%를 먹어
# 대화가 조금만 길어도 한계를 넘겨 느린 두뇌로 추락합니다. 그래서 이런 두뇌에는
# **핵심 도구 + 이번 질문에 관계있는 도구**만 보냅니다. 큰 두뇌엔 늘 전부 보냅니다.
# 안전장치: ①핵심은 주제 안 가리고 항상 ②키워드는 넉넉히 ③이 대화에서 이미 부른
# 도구는 계속 열어둠(다단계 작업 연속성) ④폴백(큰 두뇌)은 41개 전부라 놓쳐도 복구됨.

_CORE_TOOLS = {                                  # 주제 안 가리고 자주 쓰이는 것 — 항상 보냄
    "recall", "remember", "search_history", "now", "calc", "get_weather",
    "add_todo", "list_todos", "done_todo", "add_reminder", "list_reminders",
    "cancel_reminder", "find_files", "search_files", "read_document",
    "search_knowledge", "web_search",
}

_TOOL_GROUPS = [                                 # (키워드들, 딸린 도구들) — 하나라도 걸리면 추가
    (("블렌더", "blender", "blend", ".fbx", ".glb", "3d", "모델링", "폴리", "리깅", "rigging",
      "리그", "rig", "웨이트", "weight", "weights", "렌더", "매핑", "본", "bone", "bones", "뼈대", "메시", "decimate", "uv",
      "일괄", "여러 파일", "폴더", "배치", "유니티", "유니티용", "경량화",
      "데칼", "텍스처", "익스포트", "갈색", "임포트",
      "점검", "감사", "린트", "반입", "한번에", "한 번에", "체인",
      "애니메이션", "animation", "애니", "anim", "움직임", "턴테이블", "걷기", "lod", "그레이박스", "소품",
      "조립", "키트배시", "씬 조립", "본 배치", "뼈대 생성", "표준 뼈대", "표준뼈대",
      "bone_template", "auto_weight", "weight_transfer", "pose_apply", "anim_edit", "anim_merge", "physics_bake",
      "자동 웨이트", "자동웨이트", "웨이트 전사", "웨이트전사", "살 붙이기", "살붙이기", "옷 입", "옷 입히기", "옷입히기",
      "포즈", "pose", "포즈 적용", "포즈적용", "키프레임", "애니 편집", "애니편집", "애니 합본", "애니합본",
      "대칭", "미러", "배열", "뿌려", "흩뿌", "콜라이더", "재질", "분리",
      "간판", "3d 글자", "글자 세워", "비교", "차이", "루프",
      "합본", "클립", "믹사모", "mixamo", "베이킹", "베이크", "노멀맵", "노멀 맵",
      "ao", "아틀라스", "드로우콜", "불리언", "뚫어", "구멍", "수리", "고쳐줘 메시",
      "파이프", "관 만들", "경로 따라", "부착점", "소켓", "총구", "장착",
      "한눈에", "시트", "몽타주", "뭐가 뭔지", "기획서용 렌더", "그림자 렌더",
      "pbr", "텍스처 연결", "텍스처 입혀",
      "챔퍼", "모서리", "두께", "스무스", "셰이딩", "라이트맵", "개명", "이름 바꿔",
      "법선", "노멀", "뒤집", "정렬", "바닥에", "일렬", "격자", "청소", "다이어트",
      "떨어뜨", "낙하", "천 ", "드리워", "물리", "physics", "물리 베이크", "물리베이크"),
     {"blender_3d", "blender_batch"}),
    (("영상", "동영상", "자막", "배속", "움짤", "gif", "mp4", "받아쓰", "녹음",
      "자르", "이어붙", "소리만", "오디오", "음성 파일", "m4a"),
     {"edit_video", "transcribe_audio"}),
    (("그림", "그려", "이미지", "일러스트", "그림체", "리스타일", "restyle", "그려줘", "그려서", "그려봐", "그려주라", "화풍", "짤", "디자인", "바탕화면", "수인", "퍼리", "생성해", "만들어줘 그림", "저장해줘", "사진", "그려라", "캐릭터", "draw"),
     {"draw", "restyle"}),
    (("메일", "지메일", "이메일", "gmail", "캘린더", "일정", "초대", "약속", "미팅"),
     {"check_mail", "list_events", "add_event", "draft_mail"}),
    (("문서", "워드", "엑셀", "ppt", "파워포인트", "보고서", "기획서", "발표자료",
      "피치덱", "슬라이드", "양식", "템플릿", "엑셀표", "정산서", "명세서", "회의록",
      "문서 작성", "문서 만들어줘", "워드 작성", "PPT 만들어줘", "docx", "xlsx",
      "pptx", "hwpx", "표 만들", "덱"),
     {"write_document", "edit_document", "write_file", "read_file"}),
    (("실행", "파이썬", "python", "파워셸", "powershell", "스크립트", "명령어", "코드 돌"),
     {"run_python", "run_powershell"}),
    # 코딩 작업실 — '프로그램을 짓고 고쳐가며 완성'하는 일. 위 run_python(1회용 계산)과
    # 겹치는 낱말이 있어도 둘 다 켜지면 되니 넉넉히 잡습니다(모델이 상황 보고 고름).
    (("프로그램", "코딩", "코드", "파이썬", "python", "스크립트", "작업실", "workspace",
      "디버그", "디버깅", "버그", "에러", "오류 고", "traceback", "짜줘", "짜 줘",
      "만들어줘 프로그램", "앱 만들", "고쳐가", "리팩", "함수 만들", "클래스 만들"),
     {"code_write", "code_read", "code_edit", "code_run", "code_list", "code_install"}),
    # 유니티 — C# 스크립트를 쓰고(code_*) 배치모드로 컴파일·테스트 검증(unity_run)까지.
    (("유니티", "unity", "씬 ", "프리팹", "prefab", "배치모드", "playmode", "editmode",
      "유니티 빌드", "유니티 테스트", "유니티 스크립트", "c# 스크립트", "monobehaviour",
      "샐러드팜", "dietcreature", "onlyuprat", "게임 스크립트", "빌드", "apk", "aab",
      "에러 확인", "컴파일", "감사", "깨진", "참조", "프리팹", "용량", "정리",
      "씬에 뭐", "계층", "구조 봐", "미사용", "안 쓰는", "예외", "nullreference",
      "널레퍼", "런타임", "번들", "버전 몇", "빌드 씬", "define",
      "스냅샷", "백업", "복원", "되돌", "달라졌", "차이", "커졌", "리포트",
      "스프라이트", "ppu", "밉맵", "임포트 설정", "치환",
      "텍스처 낮춰", "텍스처 줄", "임포트 하향", "모델 설정", "fbx 설정", "read/write",
      "씬 성능", "무거워", "린트", "스모크", "씬 검사", "끊긴 참조", "열어봐",
      "코드 점검", "성능 문제", "매 프레임", "update 안",
      "스크린샷", "스샷", "씬 찍어", "화면 찍어", "어떻게 보이", "분홍", "마젠타",
      "왕복", "납품", "잘 보일지", "fbx 검증",
      "건강", "괜찮아", "이상 없", "상태 점검", "프로젝트 점검"),
     {"unity_run", "unity_new_script", "unity_find", "unity_audit", "unity_status", "unity_build",
      "unity_scene", "unity_refs", "unity_settings", "unity_log", "unity_outline",
      "unity_build_report", "unity_yaml_edit", "unity_snapshot", "unity_diff", "unity_sprites",
      "unity_tex_fix", "unity_models", "unity_scene_lint", "unity_scene_smoke", "unity_code_lint",
      "unity_cs_check", "unity_cs_write", "unity_cs_edit", "unity_context", "unity_shot",
      "unity_fbx_check", "unity_health",
      "code_write", "code_read", "code_edit", "read_document", "edit_document"}),
    (("파일", "폴더", "디렉터리", "목록", "저장해", "써줘", "읽어"),
     {"write_file", "read_file", "list_dir"}),
    (("버스", "지하철", "정류장", "호선", "몇 분 후", "도착 시간", "탈"),
     {"get_bus", "get_subway"}),
    (("조사", "리서치", "알아봐", "자세히 조사", "깊게 찾", "찾아봐"),
     {"research", "fetch_url", "web_search"}),
    (("예전", "지난번", "언제 말", "대화에서", "이전에 얘기", "말했었", "지난 대화"),
     {"search_my_history"}),
    (("고장", "안 돼", "안돼", "점검", "진단", "왜 이래", "목소리가", "먹통"),
     {"self_check"}),
    (("눈 믿", "눈 시험", "눈 검사", "눈 신뢰", "자가검수 믿", "제대로 보", "눈이 정확"),
     {"eye_trust"}),
    (("클립보드", "방금 복사", "복사한 거", "복사한거"),
     {"read_clipboard"}),
    (("잊어", "기억 지워", "기억 삭제", "지워줘"),
     {"forget"}),
    (("링크", "http", "url", "웹페이지", "가져와", "이 주소"),
     {"fetch_url"}),
]

_SKIP_ROLES = {"system"}                         # 페르소나 텍스트가 키워드를 잘못 건드리지 않게


def _relevant_names(messages):
    """최근 대화에서 필요한 도구 이름 집합(핵심 + 키워드 그룹 + 이미 쓰인 도구)."""
    text = ""
    for m in (messages or [])[-6:]:              # 최근 몇 개면 충분(길수록 오탐만 늘어남)
        if m.get("role") in _SKIP_ROLES:
            continue
        c = m.get("content")
        if isinstance(c, str):
            text += " " + c
    low = text.lower()
    names = set(_CORE_TOOLS)
    for kws, group in _TOOL_GROUPS:
        if any(k in low for k in kws):
            names |= group
    for m in (messages or []):                   # 이 대화에서 이미 부른 도구는 계속 열어둠
        for tc in (m.get("tool_calls") or []):
            fn = (tc.get("function") or {}).get("name")
            if fn:
                names.add(fn)
    return names


def specs_for(entry, messages=None):
    """이 두뇌에 보낼 도구 명세.
    - 큰 컨텍스트 두뇌: 늘 전부(SPECS).
    - 작은 두뇌(context ≤ 16384) 또는 `tool_budget: "compact"`: 요약본(COMPACT).
      messages를 주면 관계있는 것만 골라 더 줄임.

    ⚠️둘은 **다른 이유로** 줄입니다. `context`는 '담을 자리가 좁아서'이고,
    `tool_budget`은 '**분당 토큰 한도(TPM)**가 좁아서'입니다. Groq 무료 티어가 후자입니다:
    컨텍스트는 넉넉한데 분당 한도가 좁아, 전체 명세(약 15,700토큰)를 실으면 질문 한 번에
    413을 맞습니다(2026-07-23 실측 — 후보 3종 전부 즉시 413). 자리가 좁은 것과 한도가
    좁은 것을 같은 항목으로 뭉뚱그리면, 나중에 컨텍스트를 늘려도 413이 안 풀려서 헤맵니다.
    """
    entry = entry or {}
    limit = entry.get("context")
    small = (limit and limit <= 16384) or entry.get("tool_budget") == "compact"
    if not small:
        return SPECS
    if not messages:
        return COMPACT_SPECS                     # 질문 없이 부르면 안전하게 요약본 전체
    want = _relevant_names(messages)
    subset = [s for s in COMPACT_SPECS if s["function"]["name"] in want]
    return subset or COMPACT_SPECS               # 최소 핵심은 늘 있으니 빈 경우는 없음


TOOLS = {
    "now": now,
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "read_document": read_document,
    "write_document": write_document,
    "edit_document": edit_document,
    "edit_video": edit_video,
    "blender_3d": blender_3d,
    "find_files": find_files,
    "search_files": search_files,
    "check_mail": check_mail,
    "list_events": list_events,
    "add_event": add_event,
    "draft_mail": draft_mail,
    "transcribe_audio": transcribe_audio,
    "web_search": web_search,
    "research": research,
    "fetch_url": fetch_url,
    "calc": calc,
    "run_python": run_python,
    "draw": draw,
    "generate_image": draw,
    "restyle": restyle,
    "search_knowledge": search_knowledge,
    "search_history": search_history,
    "search_my_history": search_my_history,
    "read_clipboard": read_clipboard,
    "remember": remember,
    "recall": recall,
    "forget": forget,
    "run_powershell": run_powershell,
    "code_write": code_write,
    "code_read": code_read,
    "code_edit": code_edit,
    "code_run": code_run,
    "code_list": code_list,
    "code_install": code_install,
    "unity_run": unity_run,
    "unity_new_script": unity_new_script,
    "unity_find": unity_find,
    "unity_audit": unity_audit,
    "unity_status": unity_status,
    "unity_health": unity_health,
    "eye_trust": eye_trust,
    "unity_build": unity_build,
    "unity_scene": unity_scene,
    "unity_refs": unity_refs,
    "unity_settings": unity_settings,
    "unity_log": unity_log,
    "unity_outline": unity_outline,
    "unity_build_report": unity_build_report,
    "unity_yaml_edit": unity_yaml_edit,
    "unity_snapshot": unity_snapshot,
    "unity_diff": unity_diff,
    "unity_sprites": unity_sprites,
    "unity_tex_fix": unity_tex_fix,
    "unity_models": unity_models,
    "unity_scene_lint": unity_scene_lint,
    "unity_scene_smoke": unity_scene_smoke,
    "unity_shot": unity_shot,
    "unity_fbx_check": unity_fbx_check,
    "unity_code_lint": unity_code_lint,
    "unity_cs_check": unity_cs_check,
    "unity_cs_write": unity_cs_write,
    "unity_cs_edit": unity_cs_edit,
    "unity_context": unity_context,
    "blender_batch": blender_batch,
    "get_bus": get_bus,
    "get_subway": get_subway,
    "add_reminder": add_reminder,
    "list_reminders": list_reminders,
    "cancel_reminder": cancel_reminder,
    "get_weather": get_weather,
    "add_todo": add_todo,
    "list_todos": list_todos,
    "done_todo": done_todo,
    "self_check": self_check,
}


def call(name, arguments):
    """모델이 고른 도구를 실제로 실행합니다. 실패해도 죽지 않고 오류 내용을 모델에게 돌려줍니다."""
    fn = TOOLS.get(name)
    if fn is None:
        return f"오류: '{name}'이라는 도구는 없습니다."
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    except json.JSONDecodeError:
        return "오류: 도구 인자가 올바른 JSON이 아닙니다."
    try:
        return str(fn(args))
    except Exception as e:
        return f"오류: {type(e).__name__}: {e}"
