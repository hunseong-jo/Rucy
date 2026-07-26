# -*- coding: utf-8 -*-
"""
대화 기억 + 종료 시 자동 요약

지금까지는 exit 하면 대화가 증발했습니다. 남는 건 비서가 remember로 직접 적은 것뿐인데,
그건 모델 재량이라 잘 안 적습니다. 그래서:

  1) 모든 대화를 memory/history/날짜.md 에 그대로 남기고
  2) 종료할 때 "앞으로도 계속 알아야 할 사실"만 모델이 골라 notes.md 에 넣습니다.

notes.md 에 들어간 것은 임베딩 검색 대상이 되므로, 다음 실행부터 관련 질문에 자동으로 딸려옵니다.
"""
import datetime
import json
import os
import re
import subprocess
import threading

import memory_search

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(BASE_DIR, "memory", "history")
NOTES_FILE = os.path.join(BASE_DIR, "memory", "notes.md")

SUMMARY_PROMPT = """아래는 사용자와 비서의 대화 기록이다.

이 대화에서 **앞으로의 대화에서도 계속 알아야 할 사실**만 골라내라.

포함할 것: 사용자의 상황·선호·결정·일정·목표, 사용자가 명시적으로 기억하라고 한 것.
제외할 것: 일회성 질문과 답(예: "북한산 높이는?"), 비서가 한 말, 오늘만 유효한 잡담,
          이미 [기존 기억]에 있는 내용.

각 항목은 한 문장으로, 나중에 봐도 이해되게 주어를 포함해서 써라.
(예: "사용자는 매주 토요일에 등산을 감")

기억할 것이 없으면 빈 배열을 반환하라.
반드시 JSON 배열 하나만 출력하라. 설명·코드블록·다른 말 금지.
예: ["사용자는 매운 음식을 못 먹음", "사용자의 발표는 8월 3일"]

[기존 기억]
{existing}

[대화 기록]
{transcript}"""


def _today():
    return datetime.date.today().isoformat()


def auto_git_push():
    """
    기억이나 대화 기록이 새로 축적되었을 때 비동기 백그라운드로 깃허브에 자동 업로드합니다.
    대화 응답 속도나 UI 흐름에 0.001초의 영향도 주지 않습니다.
    """
    def _run():
        try:
            subprocess.run(["git", "add", "memory/"], cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            subprocess.run(["git", "commit", "-m", f"Auto sync memory [{stamp}]"], cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def log_turn(role, text):
    """대화를 날짜별 파일에 그대로 남깁니다(사람이 읽을 수 있는 원본 기록)."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, _today() + ".md")
    stamp = datetime.datetime.now().strftime("%H:%M")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"**{role}** ({stamp})\n{text}\n\n")


def text_of(message):
    """
    메시지의 사람이 읽을 수 있는 부분만.

    이미지가 실린 메시지의 content는 문자열이 아니라 [{type:text},{type:image_url}] 목록이고,
    image_url 안에는 base64 수 MB가 들어 있습니다. 그걸 그대로 str()로 세거나 요약에 넣으면
    글자수가 폭발해 "대화가 길다"고 오판하고, 요약 프롬프트에 base64를 쏟아붓게 됩니다.
    """
    content = message.get("content")
    if isinstance(content, list):
        bits = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                bits.append(part.get("text", ""))
            elif part.get("type") == "image_url":
                bits.append("[이미지]")
        return " ".join(b for b in bits if b)
    return str(content or "")


def _transcript(messages):
    """모델에 넘길 대화 요약본. 도구 호출 내역은 빼고 사람의 말만 남깁니다."""
    lines = []
    for m in messages:
        role = m.get("role")
        text = text_of(m)
        if role == "user":
            lines.append("사용자: " + text)
        elif role == "assistant" and text:
            lines.append("비서: " + text)
        elif role == "system" and text.startswith(SUMMARY_MARK):
            lines.append(text)          # 앞서 압축해둔 요약도 함께 넘겨야 내용이 유실되지 않습니다
    return "\n".join(lines)


# ── 컨텍스트 자동 압축 ────────────────────────────────────────────
# 대화가 길어지면 요청이 토큰 한도를 넘어 거절당합니다(무료 Cerebras는 컨텍스트 8192라 가장 먼저 죽음).
# 오래된 턴을 요약 한 덩어리로 갈아끼우고 최근 몇 턴만 원문으로 남깁니다.
SUMMARY_MARK = "[이전 대화 요약]"

COMPRESS_PROMPT = """아래는 사용자와 AI 비서의 지난 대화다. 대화가 길어져서 압축해야 한다.

**뒤에 이어질 대화에서 필요한 것만** 남겨라. 다음을 반드시 보존하라:
- 사용자가 요구한 것과 아직 끝나지 않은 일
- 결정된 사항, 합의된 방침, 사용자가 알려준 사실(이름·경로·수치·일정)
- 비서가 이미 확인한 결과(파일 내용, 검색 결과의 결론, 계산 값)

버려도 되는 것: 인사말, 중복된 설명, 이미 폐기된 시도, 비서의 장황한 서술.

3인칭 요점 정리로 15줄 이내. 다른 말 없이 요약만 출력하라.

[지난 대화]
{transcript}"""


def _chars(messages):
    return sum(len(text_of(m)) for m in messages)


def compress(messages, config, call_model):
    """
    필요하면 오래된 대화를 요약으로 갈아끼웁니다. (새 messages, 압축했나?)

    자를 위치는 반드시 '사용자 발언' 경계입니다. 도구 결과(tool)는 자신을 부른 assistant의
    tool_calls와 짝이 맞아야 하는데, 아무 데서나 자르면 그 짝이 깨져 400이 납니다.
    """
    cfg = config.get("context", {})
    if not cfg.get("enabled", True):
        return messages, False

    if _chars(messages) <= cfg.get("max_chars", 12000):
        return messages, False

    keep = cfg.get("keep_recent_turns", 6)
    user_at = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    if len(user_at) <= keep:
        return messages, False          # 최근 턴만으로도 이미 긴 경우 — 자를 게 없습니다

    cut = user_at[-keep]                # 이 위치부터는 원문 그대로 둡니다
    old, recent = messages[1:cut], messages[cut:]
    if not old:
        return messages, False

    transcript = _transcript(old)
    try:
        message, _used, _entry = call_model(
            config,
            [{"role": "user", "content": COMPRESS_PROMPT.format(transcript=transcript[:20000])}],
            use_tools=False,
        )
        summary = (message.get("content") or "").strip()
    except Exception:
        summary = ""

    if not summary:
        # 요약을 못 해도 대화는 계속돼야 합니다. 오래된 원문을 버리되 버렸다는 사실은 남깁니다.
        summary = "(요약에 실패해 오래된 대화는 생략되었습니다. 필요하면 사용자에게 다시 물어보라.)"

    head = messages[0]
    folded = {"role": "system", "content": f"{SUMMARY_MARK}\n{summary}"}
    return [head, folded] + recent, True


def prune_for_context_limit(messages, max_tokens=8192, reserved_tokens=2500):
    """
    특정 두뇌의 컨텍스트 한도(예: Cerebras 8192)에 맞추어 메시지 목록을 안전하게 자르고 압축합니다.
    - system 메시지(0번)와 직전 사용자 메시지는 항상 유지.
    - 중간 턴 중 긴 tool 응답이나 텍스트는 내용 줄임 처리.
    - tool_calls 와 tool role 간의 짝(pair)이 깨지지 않도록 유의하여 자름.
    """
    if not messages:
        return messages

    budget_tokens = max(1000, max_tokens - reserved_tokens)
    max_chars = int(budget_tokens * 1.8)

    sanitized = []
    for m in messages:
        m_copy = dict(m)
        content = m_copy.get("content")
        if isinstance(content, str) and len(content) > 1500 and m_copy.get("role") != "system":
            m_copy["content"] = content[:1000] + "\n...[컨텍스트 제한으로 내용 일부 생략]...\n" + content[-200:]
        sanitized.append(m_copy)

    if _chars(sanitized) <= max_chars:
        return sanitized

    head = sanitized[0] if (sanitized and sanitized[0].get("role") == "system") else None
    rest = sanitized[1:] if head else sanitized[:]

    if not rest:
        return [head] if head else []

    selected = []
    curr_chars = len(text_of(head)) if head else 0

    idx = len(rest) - 1
    while idx >= 0:
        group = [rest[idx]]
        idx -= 1
        while idx >= 0 and (group[0].get("role") == "tool" or group[0].get("role") == "assistant"):
            group.insert(0, rest[idx])
            idx -= 1
            if group[0].get("role") == "user":
                break

        group_chars = sum(len(text_of(m)) for m in group)
        if selected and (curr_chars + group_chars > max_chars):
            break

        selected = group + selected
        curr_chars += group_chars

    res = [head] + selected if head else selected
    if not any(m.get("role") == "user" for m in res) and sanitized:
        res.append(sanitized[-1])
    return res


def _extract_json_array(text):
    """모델이 코드블록이나 군말을 붙여도 배열만 뽑아냅니다."""
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [str(x).strip() for x in data if isinstance(x, (str, int, float)) and str(x).strip()]


def _is_duplicate(fact, existing, config):
    """이미 비슷한 기억이 있으면 저장하지 않습니다(임베딩 기준, 실패하면 문자열 비교)."""
    if fact in existing:
        return True
    try:
        model = config.get("embed_model", "bge-m3")
        vecs = memory_search._embed([fact] + existing, model)
        fv, others = vecs[0], vecs[1:]
        threshold = config.get("memory_dedupe_score", 0.90)
        return any(memory_search._cosine(fv, ov) >= threshold for ov in others)
    except Exception:
        return any(fact.lower() in e.lower() or e.lower() in fact.lower() for e in existing)


# 짧은 대화에도 이런 신호가 있으면 반드시 요약합니다.
# ("다음 주 수요일 치과 예약이야" 한마디만 하고 끄는 경우가 실제로 있습니다 — 이걸 놓치면 안 됩니다)
WORTH_KEEPING = re.compile(
    r"(기억|예약|일정|약속|계획|목표|마감|생일|좋아|싫어|선호|알레르기|못 먹|취향|"
    r"사는|주소|전화|이름은|버릇|습관|앞으로|늘 |항상|매주|매일|매달)"
)


def _should_summarize(messages, config):
    """
    요약도 모델 호출이라 무료 한도를 씁니다. 인사만 하고 끈 대화까지 요약하면 낭비입니다.
    다만 '짧다'는 이유만으로 건너뛰면 한마디로 던진 중요한 사실을 놓치므로,
    짧으면서 '기억할 만한 신호'도 없을 때만 건너뜁니다.
    돌려주는 값: (요약할까?, 건너뛴 이유)
    """
    cfg = config.get("summary", {})
    said = [str(m.get("content", "")) for m in messages if m.get("role") == "user"]
    text = " ".join(said)

    if WORTH_KEEPING.search(text):
        return True, ""
    if len(said) < cfg.get("min_user_turns", 3):
        return False, f"대화가 {len(said)}턴뿐이고 기억할 만한 내용이 없음"
    if len(text) < cfg.get("min_chars", 60):
        return False, "짧은 잡담뿐이라 기억할 게 없음"
    return True, ""


def summarize_and_save(messages, config, call_model):
    """
    종료 시 호출됩니다. call_model 은 agent.py 의 라우터 함수를 그대로 받습니다
    (그래야 Gemini가 죽어도 Groq·로컬로 요약이 됩니다).
    돌려주는 값: 새로 저장한 기억 목록
    """
    worth, why = _should_summarize(messages, config)
    if not worth:
        print(f"  (요약 건너뜀 — {why})")
        return []

    transcript = _transcript(messages)
    if len(transcript) < 40:          # 인사만 하고 끈 경우
        return []

    existing = memory_search.load_notes()
    prompt = SUMMARY_PROMPT.format(
        existing="\n".join("- " + e for e in existing) or "(없음)",
        transcript=transcript[-8000:],   # 너무 길면 뒷부분 위주로
    )

    try:
        # 도구 없이 순수 텍스트 요약만 시킵니다.
        message, _used, _entry = call_model(config, [{"role": "user", "content": prompt}], use_tools=False)
    except Exception:
        return []

    facts = _extract_json_array(message.get("content"))
    saved = []
    for fact in facts:
        if _is_duplicate(fact, existing + saved, config):
            continue
        saved.append(fact)

    if saved:
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            for fact in saved:
                f.write(f"- {fact}  ({_today()})\n")
        auto_git_push()
    return saved


# ── 대화 유실 안전망 (낙수받이) ───────────────────────────────────
# 종료 요약은 exit·Ctrl+C만 잡습니다. 터미널 창을 X로 닫거나 정전이 나면 그날 대화의
# 원문(history)은 남지만 '기억할 사실'은 뽑히지 않은 채 증발합니다. 웹(web.py) 대화는
# exit 자체가 없어 지금까지 한 번도 요약된 적이 없습니다.
# 그래서 매일 새벽(daily.tick), 아직 거두지 않은 지난날 대화를 여기서 받아냅니다.
#
# '어디까지 거뒀나'는 memory/summarized.json에 날짜별 바이트 위치로 적습니다.
# exit 요약이 이미 다룬 날을 새벽에 또 요약해도 괜찮습니다 — 프롬프트의 [기존 기억]과
# 임베딩 중복 제거가 이중으로 걸러 줍니다. 터미널과 웹이 같은 날짜 파일에 섞여 쓰므로
# '정확히 어느 문장까지 요약됐나'를 쫓는 것보다 걸러냄을 믿는 쪽이 단순하고 안전합니다.
COVERED_FILE = os.path.join(BASE_DIR, "memory", "summarized.json")


def _covered():
    try:
        with open(COVERED_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _mark_covered(day, size):
    data = _covered()
    data[day] = size
    data = {d: data[d] for d in sorted(data)[-14:]}   # 이 파일은 '최근에 놓친 것'만 기억하면 됩니다
    tmp = COVERED_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, COVERED_FILE)


def uncovered_days(days=3):
    """아직 거두지 않은 지난 날짜 목록('/상태'가 보여줍니다). 오늘은 아직 진행 중이라 제외."""
    out = []
    today = datetime.date.today()
    for back in range(days, 0, -1):
        day = (today - datetime.timedelta(days=back)).isoformat()
        path = os.path.join(HISTORY_DIR, day + ".md")
        if os.path.exists(path) and os.path.getsize(path) > int(_covered().get(day, 0)):
            out.append(day)
    return out


def catch_up(config, call_model, notify=print, days=3):
    """
    지난 며칠 중 요약 안 된 대화를 찾아 기억으로 거둡니다. 새로 저장한 사실 목록을 돌려줍니다.

    실패한 날은 표시를 남기지 않습니다 — 다음 새벽에 다시 옵니다.
    """
    saved_all = []
    today = datetime.date.today()
    for back in range(days, 0, -1):
        day = (today - datetime.timedelta(days=back)).isoformat()
        path = os.path.join(HISTORY_DIR, day + ".md")
        if not os.path.exists(path):
            continue
        size = os.path.getsize(path)
        done = int(_covered().get(day, 0))
        if size <= done:
            continue

        with open(path, "rb") as f:           # 바이트 위치로 세므로 바이너리로 열어 자릅니다
            f.seek(done)
            tail = f.read().decode("utf-8", errors="replace")
        # 인사 몇 마디뿐이면 모델을 부를 가치가 없습니다 — 단, 짧아도 '기억/예약/매주...'
        # 신호가 있으면 요약합니다(한마디로 던진 치과 예약을 놓친 적이 있어 배운 규칙).
        if len(tail.strip()) < 120 and not WORTH_KEEPING.search(tail):
            _mark_covered(day, size)
            continue

        notify(f"  {day} 대화에 거두지 않은 부분이 있어 요약합니다")
        existing = memory_search.load_notes()
        prompt = SUMMARY_PROMPT.format(
            existing="\n".join("- " + e for e in existing) or "(없음)",
            transcript=tail[-8000:],
        )
        try:
            message, _used, _entry = call_model(
                config, [{"role": "user", "content": prompt}], use_tools=False)
        except Exception as e:
            notify(f"  ({day} 요약 실패: {type(e).__name__} — 다음 새벽에 다시 시도합니다)")
            continue

        facts = _extract_json_array(message.get("content"))
        saved = [x for x in facts if not _is_duplicate(x, existing + saved_all, config)]
        if saved:
            with open(NOTES_FILE, "a", encoding="utf-8") as f:
                for fact in saved:
                    f.write(f"- {fact}  ({day})\n")
            notify(f"  {day} 대화에서 {len(saved)}개를 기억했습니다")
            auto_git_push()
        saved_all += saved
        _mark_covered(day, size)
    return saved_all
