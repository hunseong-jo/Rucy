# -*- coding: utf-8 -*-
"""
실수 노트 — 틀린 적이 있는 것을 다시 틀리지 않기 위한 기억

세 번째 기억 통입니다. 앞의 둘과 성격이 다르므로 섞지 않습니다.

  notes.md    = 사용자에 관한 사실      ("사용자는 홍차를 좋아함")
  knowledge/  = 프로젝트 지식           ("premium9 아트는 기린으로 리디자인")
  lessons.md  = 내가 틀렸던 것          ("샐러드팜 종 수를 41종이라 답했으나 32종. 종 수는 추측 말고 search_knowledge로 확인할 것")

왜 통을 나누는가: 실수 노트는 '사실'이 아니라 '행동 지침'입니다. notes.md에 섞으면
"사용자는 ~를 좋아함" 사이에 "내가 ~를 틀렸음"이 끼어 검색 공간이 흐려지고,
무엇보다 매 질문에 딸려가는 개인 사실과 달리 이건 '비슷한 실수 상황'에서만 나와야 합니다.

루시는 자기가 틀렸는지 스스로 모릅니다. 그래서 신호는 사용자의 지적입니다
("아니야", "틀렸어", "그거 아닌데") → 그 직전의 질문·답·지적을 모델이 한 줄 교훈으로 뽑아 적습니다.
"""
import datetime
import json
import os
import re

import memory_search

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
LESSONS_FILE = os.path.join(MEMORY_DIR, "lessons.md")
INDEX_FILE = os.path.join(MEMORY_DIR, "lessons_index.json")


# ── 사용자가 "틀렸다"고 말한 것인가 ────────────────────────────────
# 너무 넓게 잡으면(예: "아니"만) 평범한 대화까지 실수로 기록돼 노트가 쓰레기통이 됩니다.
# 지적임이 분명한 표현만 신호로 씁니다.
CORRECTION = re.compile(
    r"(틀렸|틀린|잘못|아니야|아닌데|아니라|아냐|그게 아니|그거 아니|사실이 아니|"
    r"지어냈|헛소리|거짓말|오답|정정|다시 확인|잘 못 알|잘못 알)"
)

# 지적처럼 보여도 실수 노트감이 아닌 것들 — 사용자가 자기 얘기를 하는 경우입니다.
# ("내가 잘못 눌렀어", "이 코드가 틀렸어" 등은 루시의 실수가 아닙니다)
NOT_MINE = re.compile(r"(내가 (잘못|틀렸)|제가 (잘못|틀렸))")


def is_correction(text):
    text = (text or "").strip()
    if not text or NOT_MINE.search(text):
        return False
    return bool(CORRECTION.search(text))


# ── 작품(3D·유니티 결과물) 품질 지적인가 — 판단력 3층(세션63 5부) ──
# "틀렸어"는 아니지만 "천이 너무 뻣뻣해" 같은 품질 불만도 배울 신호입니다.
# 낱말만으로 잡으면 평범한 대화가 오염되므로("오늘 날씨 이상해"), 두 조건을 다 요구합니다:
#   ① 품질 불만 표현  +  ② 직전 답이 실제로 뭔가를 만든 결과 보고였음(표식 문구).
CRAFT_COMPLAINT = re.compile(
    r"(어색|부자연|뻣뻣|과해|과하|밋밋|뭉개|미끄러|로봇 같|티가 나|"
    r"겹쳐|겹친|깨져 보|잘려 보|이상해 보|이상하게 보|안 어울|"
    r"너무 (크|작|두꺼|얇|길|짧|많|적|세|약|빨라|느려|밝|어두|둥글|각지)|"
    r"별로(야|다|네|인데)|마음에 안 들|다시 (해|만들|찍|뽑))"
)
CRAFT_MARKERS = ("사본에 반영했습니다", "조립했습니다", "씬 스크린샷", "미리보기",
                 "렌더", ".blend", ".fbx", "GIF로", "3D 글자", "내보내기", "굽",
                 "키프레임", "빌드했")


def is_craft_complaint(text, last_answer):
    """직전에 만든 3D·유니티 결과물에 대한 품질 지적인가."""
    text = (text or "").strip()
    if not text or NOT_MINE.search(text):
        return False
    if not CRAFT_COMPLAINT.search(text):
        return False
    la = str(last_answer or "")
    return any(m in la for m in CRAFT_MARKERS)


# ── 읽기·쓰기 ─────────────────────────────────────────────────────
def load():
    """'- 내용  (날짜)' 줄들을 리스트로. notes.md와 같은 형식이라 눈으로 읽고 손으로 고칠 수 있습니다."""
    if not os.path.exists(LESSONS_FILE):
        return []
    out = []
    with open(LESSONS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("- "):
                out.append(line[2:].strip())
    return out


def _append(lesson):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    new = not os.path.exists(LESSONS_FILE)
    with open(LESSONS_FILE, "a", encoding="utf-8") as f:
        if new:
            f.write("# 실수 노트\n\n"
                    "사용자가 지적한 잘못을 한 줄씩 적어둡니다. 비슷한 질문이 오면 자동으로 다시 읽습니다.\n"
                    "손으로 고치거나 지워도 됩니다(줄 단위).\n\n")
        f.write(f"- {lesson}  ({datetime.date.today().isoformat()})\n")


def remove(needle):
    """실수 노트에서 한 줄을 지웁니다. (지운 줄 목록)"""
    if not os.path.exists(LESSONS_FILE):
        return []
    with open(LESSONS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    hits = [l for l in lines if l.strip().startswith("- ") and needle.lower() in l.lower()]
    if not hits:
        return []
    with open(LESSONS_FILE, "w", encoding="utf-8") as f:
        f.writelines(l for l in lines if l not in hits)
    return [l.strip()[2:].strip() for l in hits]


# ── 교훈 뽑아내기 ─────────────────────────────────────────────────
LEARN_PROMPT = """너는 AI 비서의 실수를 기록하는 감독자다. 비서가 방금 사용자에게 지적을 받았다.

[사용자가 물은 것]
{question}

[비서가 한 답 — 사용자가 이걸 지적했다]
{answer}

[사용자의 지적]
{correction}

[지적을 받은 뒤 비서가 다시 한 답]
{fixed}

이 일에서 **다음에 같은 실수를 막을 교훈**을 한 줄로 뽑아라.

교훈은 두 부분으로 쓴다: (1) 무엇을 틀렸는가 — 사실이면 올바른 값까지 적는다. (2) 다음엔 어떻게 할 것인가 — 행동 지침.
예: "샐러드팜 생물 종 수를 41종이라 답했으나 실제 32종. 프로젝트 수치는 기억에 의존하지 말고 search_knowledge로 확인할 것"
예: "사용자가 '짧게'라고 했는데 장문으로 답함. 사용자는 간결한 답을 선호하므로 요청 없으면 5줄을 넘기지 말 것"

규칙:
- 사용자의 지적이 비서의 잘못이 아니거나(단순 말투 차이, 사용자의 착각, 화제 전환),
  일회성이라 다음에 도움이 안 되면 빈 문자열을 반환하라. 억지로 만들지 마라.
- 반드시 JSON 하나만 출력하라. 설명·코드블록 금지.

출력 형식: {{"lesson": "교훈 한 줄 또는 빈 문자열"}}"""


# 작품 지적 전용 — 일반 교훈과 달리 '다음에 그 도구를 어떻게 부를지'가 핵심입니다.
CRAFT_PROMPT = """너는 AI 비서의 작업 일지를 관리하는 감독자다.
비서가 3D(블렌더)·유니티 도구로 결과물을 만들었고, 사용자가 품질을 지적했다.

[사용자가 시킨 것]
{question}

[비서의 결과 보고 — 어떤 도구를 어떤 인자로 썼는지 단서가 있다]
{answer}

[사용자의 품질 지적]
{correction}

[지적 후 비서의 답]
{fixed}

다음에 같은 지적을 안 받기 위한 교훈을 한 줄로 뽑아라.
교훈은 두 부분: (1) 무엇이 지적됐는가 (2) **다음에 그 작업을 할 때 도구 인자·방법을 어떻게
바꿀 것인가** — 결과 보고에 보이는 도구 이름(physics_bake·bevel 등)·인자 이름을 그대로 써라.
예: "천 드리움이 뻣뻣하다고 지적받음. physics_bake cloth는 frames를 기본 60에서 120으로 늘려 충분히 가라앉힌 뒤 고정할 것"
예: "챔퍼가 과하다고 지적받음. 작은 소품은 bevel width를 물체 크기의 2% 이하로 줄여서 부를 것"

규칙:
- 사용자 취향이 아니라 비서가 조절할 수 있는 것(인자·순서·검증)으로 써라.
- **도구 이름(영문 그대로, 예: physics_bake·bevel)을 교훈 문장에 반드시 포함하라** —
  나중에 같은 도구를 쓸 때 이 교훈을 다시 찾는 열쇠다.
- 일회성이거나 도구로 막을 수 없는 지적이면 빈 문자열을 반환하라. 억지로 만들지 마라.
- 반드시 JSON 하나만 출력하라. 설명·코드블록 금지.

출력 형식: {{"lesson": "교훈 한 줄 또는 빈 문자열"}}"""


def _extract(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return ""
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return ""
    return str(data.get("lesson") or "").strip()


def _is_duplicate(lesson, existing, config):
    """이미 같은 교훈이 있으면 또 적지 않습니다(임베딩 기준, 실패하면 문자열 비교)."""
    if not existing:
        return False
    if lesson in existing:
        return True
    try:
        model = config.get("embed_model", "bge-m3")
        vecs = memory_search._embed([lesson] + existing, model)
        threshold = config.get("lessons", {}).get("dedupe_score", 0.90)
        return any(memory_search._cosine(vecs[0], v) >= threshold for v in vecs[1:])
    except Exception:
        return any(lesson.lower() in e.lower() or e.lower() in lesson.lower() for e in existing)


def learn(config, call_model, question, answer, correction, fixed="", kind="answer"):
    """
    지적받은 일에서 교훈을 뽑아 적습니다. (적은 교훈 또는 "")

    call_model은 agent.py의 라우터를 그대로 받습니다 — 한 두뇌가 죽어도 기록은 남아야 하니까요.
    모델이 "교훈감이 아니다"라고 판단하면 아무것도 적지 않습니다(빈 노트가 오염된 노트보다 낫습니다).
    kind="craft"면 작품 품질 지적용 프롬프트(도구 인자를 어떻게 바꿀지)로 뽑습니다.
    """
    prompt = (CRAFT_PROMPT if kind == "craft" else LEARN_PROMPT).format(
        question=str(question)[:1500],
        answer=str(answer)[:2000],
        correction=str(correction)[:1500],
        fixed=str(fixed)[:2000] or "(아직 다시 답하지 않음)",
    )
    try:
        message, _used, _entry = call_model(
            config, [{"role": "user", "content": prompt}], use_tools=False
        )
    except Exception:
        return ""

    lesson = _extract(message.get("content"))
    if not lesson or len(lesson) < 10:
        return ""

    if _is_duplicate(lesson, load(), config):
        return ""

    _append(lesson)
    _invalidate()
    return lesson


# ── 일에서 스스로 배우기 ──────────────────────────────────────────
# 지금까지 교훈의 신호는 '사용자의 지적' 하나였습니다. 그런데 일꾼 모드에는 이미
# 검사관이 있습니다 — 퇴짜(왜 부족한지) → 다시 시도 → 통과. 이건 사용자가 없어도
# 일어나는 '지적과 교정' 한 쌍이므로, 여기서도 배울 수 있습니다.
# 사람이 시행착오에서 배우는 것과 같습니다: 같은 일을 다음엔 처음부터 제대로.
WORK_PROMPT = """너는 AI 비서의 작업 일지를 관리하는 감독자다.
비서가 일을 하다 검사관에게 한 번 퇴짜를 맞았고, 고쳐서 통과했다.

[전체 목표]
{goal}

[하던 단계]
{step}

[검사관이 퇴짜 놓은 이유]
{why}

[고친 뒤 통과한 결과 보고]
{fixed}

다음에 비슷한 일을 할 때 **처음부터 퇴짜 없이 하기 위한 교훈**을 한 줄로 뽑아라.
교훈은 두 부분: (1) 무엇이 부족했는가 (2) 다음엔 처음부터 어떻게 할 것인가.
예: "뉴스 정리에서 출처 링크 없이 제출해 퇴짜. 조사 단계에서 링크를 함께 수집해 둘 것"

규칙:
- 그 파일·그 날짜에만 해당하는 일회성 실수(오타, 우연한 네트워크 실패, 한도 초과)면
  빈 문자열을 반환하라. 다음 일에 도움이 되는 것만 적는다.
- 반드시 JSON 하나만 출력하라. 설명·코드블록 금지.

출력 형식: {{"lesson": "교훈 한 줄 또는 빈 문자열"}}"""


def learn_from_work(config, call_model, goal, step, why, fixed):
    """
    일꾼 모드의 '퇴짜 → 재시도 → 통과'에서 교훈을 뽑아 적습니다. (적은 교훈 또는 "")

    learn()과 통(lessons.md)을 같이 씁니다 — 어느 쪽에서 배웠든 '다음에 조심할 것'이라는
    성격이 같고, recall_for가 한 곳만 뒤지면 되기 때문입니다.
    """
    if not config.get("lessons", {}).get("from_work", True):
        return ""
    prompt = WORK_PROMPT.format(
        goal=str(goal)[:800],
        step=str(step)[:400],
        why=str(why)[:800],
        fixed=str(fixed)[:1500],
    )
    try:
        message, _used, _entry = call_model(
            config, [{"role": "user", "content": prompt}], use_tools=False
        )
    except Exception:
        return ""

    lesson = _extract(message.get("content"))
    if not lesson or len(lesson) < 10:
        return ""
    if _is_duplicate(lesson, load(), config):
        return ""

    _append(lesson)
    _invalidate()
    return lesson


# ── 검색: 이 질문에서 조심할 것이 있는가 ───────────────────────────
_INDEX_CACHE = None
_INDEX_MTIME = 0


def _load_index():
    global _INDEX_CACHE, _INDEX_MTIME
    if os.path.exists(INDEX_FILE):
        try:
            mtime = os.path.getmtime(INDEX_FILE)
            if _INDEX_CACHE is not None and _INDEX_MTIME == mtime:
                return _INDEX_CACHE
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                _INDEX_CACHE = json.load(f)
                _INDEX_MTIME = mtime
                return _INDEX_CACHE
        except (json.JSONDecodeError, OSError):
            pass
    _INDEX_CACHE = {}
    _INDEX_MTIME = 0
    return {}


def _invalidate():
    global _INDEX_CACHE, _INDEX_MTIME
    _INDEX_CACHE = None
    _INDEX_MTIME = 0


def recall_for(user_text, config):
    """
    이번 질문과 비슷한 상황에서 틀린 적이 있으면 그 교훈을 돌려줍니다. (교훈 목록, 방식)

    기준선(min_score)을 기억 검색(0.45)보다 높게 잡습니다.
    관련도 낮은 교훈이 딸려오면 매 질문마다 엉뚱한 잔소리가 붙어 오히려 답을 흐립니다.
    """
    cfg = config.get("lessons", {})
    if not cfg.get("enabled", True):
        return [], ""

    items = load()
    if not items:
        return [], ""

    top_k = cfg.get("top_k", 2)
    floor = cfg.get("min_score", 0.55)
    model = config.get("embed_model", "bge-m3")

    try:
        index = _load_index()
        missing = [t for t in items if memory_search._key(t) not in index]
        if missing:
            for text, vec in zip(missing, memory_search._embed(missing, model)):
                index[memory_search._key(text)] = vec
            os.makedirs(MEMORY_DIR, exist_ok=True)
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(index, f)

        qvec = memory_search._embed([user_text], model)[0]
        scored = [(memory_search._cosine(qvec, index[memory_search._key(t)]), t) for t in items]
        method = f"임베딩({model})"
    except Exception:
        scored = list(zip(memory_search._keyword_scores(user_text, items), items))
        method = "단어겹침"
        floor = 0.25          # 폴백은 점수 분포가 달라 기준선도 달라야 합니다

    scored.sort(key=lambda x: -x[0])
    # 작품 교훈(도구 이름이 든 것)은 기준선을 낮춥니다 — 지시문 어법("frames를 늘려라")과
    # 요청 어법("천 드리워줘")은 임베딩이 0.5 언저리라 0.55에 영원히 안 걸리는 걸 실측(세션63 5부).
    # 무관 질문과는 0.38 vs 0.47로 갈라져 0.45면 안전. 낱말 폴백은 분포가 달라 그대로 둡니다.
    crafty = re.compile(r"[a-z][a-z0-9]+_[a-z0-9_]+|블렌더|유니티")
    craft_floor = cfg.get("craft_min_score", 0.45) if method.startswith("임베딩") else floor
    picked = [t for s, t in scored[:top_k]
              if s >= (min(craft_floor, floor) if crafty.search(t) else floor)]
    if not picked:
        return [], ""
    return picked, f"{method} · {len(picked)}/{len(items)}개 (최고 {scored[0][0]:.2f})"


def as_message(picked):
    """모델에게 끼워 넣을 system 메시지."""
    return {
        "role": "system",
        "content": (
            "[과거에 이 비슷한 것을 틀린 적이 있다 — 같은 실수를 반복하지 마라]\n"
            + "\n".join("- " + p for p in picked)
            + "\n이 교훈이 이번 질문과 무관하면 무시하고, 관련되면 반드시 지켜라."
        ),
    }
