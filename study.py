# -*- coding: utf-8 -*-
"""
스스로 배우기 — 복습(자기 반성)과 자가 공부.

지금까지 루시가 배우는 길은 셋 다 수동적이었습니다: 사용자가 "틀렸어"라고 지적하거나
(lessons), 일꾼의 검사관에게 퇴짜를 맞거나(learn_from_work), 대화가 끝날 때 사실을
받아 적거나(session). 여기는 **아무도 시키지 않아도** 배우는 두 길을 놓습니다.

  ① 복습(reflect) — 매일 새벽, 어제 대화를 되읽고 스스로 아쉬웠던 순간을 찾습니다.
     사용자가 지적하지 않았어도: 같은 걸 두 번 묻게 만들었다, 의도를 오해했다,
     확인 없이 추측으로 답했다 → 교훈으로 만들어 실수 노트(lessons.md)에 적습니다.
     사람이 자기 전에 하루를 돌아보는 것과 같습니다.

  ② 자가 공부(study) — 어제 대화에서 얕게 답했던 주제를 하나 골라 스스로 깊이
     조사하고(research), 지식 창고에 노트로 정리합니다. 같은 주제를 다시 물으면
     검색부터 하는 대신 공부해 둔 노트로 답합니다.

지어내기 방지: 공부 노트는 **조사 자료에 있는 내용만** 쓰게 하고, 파일 머리에
'자가 학습·검증 안 됨'을 밝혀 둡니다. 복습 교훈은 하루 최대 몇 개로 묶고(노트가
잔소리통이 되지 않게), 이미 아는 교훈과 겹치면 안 적습니다. 억지로 만들지 않는 것
— "없으면 없다"가 — 이 통들의 품질을 지킵니다.
"""
import datetime
import os
import re

import lessons
import memory_search
import session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(BASE_DIR, "memory", "history")
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
STUDY_PREFIX = "selfstudy_"     # 클로드가 안 쓰는 접두사 — knowledge.sync()가 덮어쓰지 않습니다


# ── 대화 기록 읽기 ────────────────────────────────────────────────
def _history(day):
    path = os.path.join(HISTORY_DIR, day + ".md")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def last_day(include_today=False):
    """복기할 가장 최근 날. 새벽에 돌 때는 어제(가장 최근의 지난날)를 봅니다."""
    if not os.path.isdir(HISTORY_DIR):
        return ""
    today = datetime.date.today().isoformat()
    days = sorted(f[:-3] for f in os.listdir(HISTORY_DIR) if f.endswith(".md"))
    if not include_today:
        days = [d for d in days if d != today]
    return days[-1] if days else ""


# ── ① 복습: 지적받지 않은 실수에서도 배우기 ────────────────────────
REFLECT_PROMPT = """너는 AI 비서 '{name}'의 하루를 복기하는 감독자다.
아래는 {day}에 비서와 사용자가 나눈 대화 기록이다.

비서가 잘못했거나 아쉬웠던 순간을 찾아라. 이런 신호를 봐라:
- 사실을 틀리게 말했다가 나중에 고침(또는 사용자가 고쳐줌)
- 사용자가 같은 것을 다시 묻거나, 요청을 고쳐 말해야 했음
- 하겠다고 말해 놓고 하지 않았거나, 확인 없이 '했다'고 답함
- 의도를 오해해 엉뚱한 답을 함, 원하는 것보다 장황하게 답함
- 확인(도구·검색)이 필요한 것을 추측으로 답함

각 순간에서 **다음에 같은 실수를 막을 교훈**을 한 줄로 뽑아라. 두 부분으로 쓴다:
(1) 무엇이 아쉬웠는가 (2) 다음엔 어떻게 할 것인가.
예: "사용자가 '짧게'라고 두 번 말하게 함. 답이 5줄을 넘기면 먼저 요점만 말하고 원하면 풀어쓸 것"

규칙:
- 최대 {max_lessons}개. **없으면 빈 배열 []이 정답이다** — 억지로 만들지 마라.
- 그날 하루만 유효한 일(일시적 서버 오류, 오타)은 빼라. 다음에 도움이 되는 것만.
- [이미 아는 교훈]과 같은 내용은 다시 만들지 마라.
- 반드시 JSON 배열 하나만 출력하라. 설명·코드블록 금지. 예: ["교훈1", "교훈2"]

[이미 아는 교훈]
{existing}

[대화 기록]
{transcript}"""


def reflect(config, call_model, day=None, notify=print):
    """
    그날 대화를 되읽고 스스로 교훈을 뽑아 실수 노트에 적습니다. (적은 교훈 목록)
    day가 없으면 가장 최근의 지난날(보통 어제)을 봅니다.
    """
    day = day or last_day()
    if not day:
        return []
    transcript = _history(day)
    if len(transcript) < 200:            # 인사 몇 마디뿐인 날은 복기할 게 없습니다
        return []

    existing = lessons.load()
    max_lessons = config.get("daily", {}).get("study", {}).get("max_lessons", 2)
    prompt = REFLECT_PROMPT.format(
        name=config.get("name", "루시"),
        day=day,
        max_lessons=max_lessons,
        existing="\n".join("- " + e for e in existing) or "(없음)",
        transcript=transcript[-15000:],  # 하루가 길면 뒷부분 위주 — 최근 대화가 더 배울 게 많습니다
    )
    message, _used, _entry = call_model(config, [{"role": "user", "content": prompt}],
                                        use_tools=False)
    found = session._extract_json_array(message.get("content"))

    added = []
    for lesson in found[:max_lessons]:
        if len(lesson) < 10:
            continue
        if lessons._is_duplicate(lesson, existing + added, config):
            continue
        lessons._append(lesson)
        added.append(lesson)
    for lesson in added:
        notify(f"  [복습] {lesson}")
    return added


# ── ② 자가 공부: 얕았던 주제를 스스로 조사해 노트로 ────────────────
PICK_PROMPT = """아래는 {day}에 AI 비서와 사용자가 나눈 대화다.
비서가 **더 공부해 두면 좋을 주제 하나**를 골라라.

고르는 기준:
- 사용자가 물었는데 비서가 얕게 답했거나, 검색 결과를 옮겨 읽는 데 그친 주제
- 사용자의 관심사·프로젝트와 닿아 있어 **다시 물을 법한** 것
- 한 번의 조사로 정리할 수 있는 범위로 좁혀라
  (예: "게임 밸런싱" 말고 "협동 게임의 난이도 곡선 설계")

이미 공부한 주제는 다시 고르지 마라:
{studied}

공부할 만한 것이 없으면 topic을 빈 문자열로 하라. 일상 잡담·개인사는 공부 주제가 아니다.
반드시 JSON 하나만 출력하라. 형식: {{"topic": "주제 또는 빈 문자열", "why": "고른 이유 한 줄"}}

[대화 기록]
{transcript}"""

NOTE_PROMPT = """너는 AI 비서다. 방금 '{topic}'을(를) 조사했다.
아래 조사 자료를 바탕으로, 나중에 이 주제를 다시 물으면 꺼내 쓸 **학습 노트**를 써라.

규칙:
- **조사 자료에 있는 내용만 써라.** 자료에 없는 것을 아는 척 채우지 마라 — 그럴 바엔 짧게 써라.
- 핵심 사실·수치·방법 위주로. 마크다운 소제목과 목록을 써라.
- 자료에 출처(사이트·URL)가 있으면 끝에 '출처' 절로 남겨라.
- 500~1500자. 노트 본문만 출력하라(인사말·설명 금지).

[조사 자료]
{research}"""


def studied_topics():
    """이미 공부한 주제들(파일명에서). 같은 걸 또 공부하지 않기 위해."""
    if not os.path.isdir(KNOWLEDGE_DIR):
        return []
    out = []
    for name in os.listdir(KNOWLEDGE_DIR):
        if name.startswith(STUDY_PREFIX) and name.endswith(".md"):
            out.append(re.sub(r"_\d{8}$", "", name[len(STUDY_PREFIX):-3]).replace("_", " "))
    return out


def pick_topic(config, call_model, day=None):
    """어제 대화에서 공부할 주제 하나를 고릅니다. (주제 또는 "", 이유)"""
    day = day or last_day()
    if not day:
        return "", ""
    transcript = _history(day)
    if len(transcript) < 200:
        return "", ""

    prompt = PICK_PROMPT.format(
        day=day,
        studied="\n".join("- " + t for t in studied_topics()) or "(없음)",
        transcript=transcript[-15000:],
    )
    message, _used, _entry = call_model(config, [{"role": "user", "content": prompt}],
                                        use_tools=False)
    m = re.search(r"\{.*\}", message.get("content") or "", re.S)
    if not m:
        return "", ""
    try:
        import json
        data = json.loads(m.group(0))
    except ValueError:
        return "", ""
    return str(data.get("topic") or "").strip(), str(data.get("why") or "").strip()


def study(config, call_model, topic, notify=print):
    """
    주제를 깊이 조사해(research) 지식 창고에 노트로 남깁니다. (노트 경로 또는 "")

    조사가 빈손이면 노트를 만들지 않습니다 — 자료 없는 노트는 지어낸 노트입니다.
    """
    import tools
    notify(f"  [공부] '{topic}' 조사 중... (20~40초)")
    found = tools.research({"question": topic})
    if not found or "검색에 실패" in found[:100]:
        notify("  [공부] 조사가 빈손이라 노트를 만들지 않습니다.")
        return ""

    message, _used, _entry = call_model(
        config,
        [{"role": "user", "content": NOTE_PROMPT.format(topic=topic, research=found[:12000])}],
        use_tools=False,
    )
    note = (message.get("content") or "").strip()
    if len(note) < 200:                  # 자료가 있는데도 이만큼도 못 쓰면 배운 게 없는 것입니다
        notify("  [공부] 정리할 내용이 부족해 노트를 만들지 않습니다.")
        return ""

    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    slug = re.sub(r"[^가-힣A-Za-z0-9 ]", "", topic).strip().replace(" ", "_")[:30] or "노트"
    stamp = datetime.date.today().strftime("%Y%m%d")
    path = os.path.join(KNOWLEDGE_DIR, f"{STUDY_PREFIX}{slug}_{stamp}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {topic} — 루시 자가 학습 노트 ({datetime.date.today().isoformat()})\n\n"
                f"> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니\n"
                f"> 수치·사실을 인용할 때는 출처를 함께 말할 것.\n\n{note}\n")

    # 다음 검색이 느려지지 않게 새 조각을 미리 임베딩해 둡니다(실패해도 검색은 됩니다).
    try:
        import knowledge
        knowledge.search(topic, config, top_k=1)
    except Exception:
        pass
    notify(f"  [공부] 노트를 적었습니다: {os.path.basename(path)}")
    return path


# ── 새벽에 도는 문 (daily.tick이 부릅니다) ─────────────────────────
def nightly(config, notify=print):
    """어제를 복습하고, 주제 하나를 공부합니다. (한 일 목록 — did에 그대로 들어갑니다)"""
    import agent
    cfg = config.get("daily", {}).get("study", {})
    did = []

    day = last_day()
    if not day:
        return did

    try:
        added = reflect(config, agent.call_model, day, notify)
        if added:
            did.append(f"복습(교훈 {len(added)}개)")
    except Exception as e:
        notify(f"  복습 오류: {type(e).__name__}: {e}")

    if cfg.get("research", True):
        try:
            import tools
            tools.init(config)           # 배경 프로세스에는 아직 도구 설정이 없을 수 있습니다
            topic, why = pick_topic(config, agent.call_model, day)
            if topic:
                notify(f"  [공부] 오늘의 주제: {topic}" + (f" ({why})" if why else ""))
                if study(config, agent.call_model, topic, notify):
                    did.append(f"자가 공부({topic})")
        except Exception as e:
            notify(f"  자가 공부 오류: {type(e).__name__}: {e}")

    return did
