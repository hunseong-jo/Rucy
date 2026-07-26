# -*- coding: utf-8 -*-
"""
나만의 AI 비서 — 두뇌 교체형 에이전트

구조:
  [사용자] → [에이전트 루프] → [라우터: Gemini → Groq → 로컬 Ollama]
                    ↕
              [도구: 파일·검색·기억·명령 실행]

특징:
  - 파이썬 표준 라이브러리만 사용 (pip 설치 불필요 → 의존성이 썩지 않음)
  - 모든 공급자를 OpenAI 호환 규격으로 통일 → 서비스가 끝나면 config.json에서 그 줄만 삭제
  - 로컬 Ollama가 맨 아래에 있어서, 무료 API가 전부 죽어도 비서는 계속 작동함

실행:  python agent.py   (또는 start.bat 더블클릭)
종료:  exit  또는 Ctrl+C
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import bench
import computer
import consolidate
import daily
import doctor
import docsearch
import knowledge
import lessons
import memory_search
import screen
import session
import status
import study
import talk
import tools
import tts
import vision
import voice
import watch
import worker
import youtube

# 윈도우 콘솔 기본 인코딩(cp949)에서 한글·기호 출력 시 죽는 것을 막습니다.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


# ── 설정과 키 ─────────────────────────────────────────────────────
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tts(config):
    """
    읽어주기 설정만 config.json에 되돌려 씁니다(다음 실행에도 켜짐이 남도록).

    ⚠️ config를 통째로 덮어쓰면 안 됩니다 — '--local' 모드에서는 메모리 위의 config가
    로컬 모델 하나짜리로 바뀌어 있어서, 그대로 저장하면 두뇌 6단이 파일에서 지워집니다.
    파일을 다시 읽어 tts 블록만 갈아 끼웁니다.
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        raw["tts"] = config.get("tts", {})
        tmp_file = CONFIG_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, CONFIG_FILE)
    except (OSError, ValueError) as e:
        print(f"  (설정을 저장하지 못했습니다: {e} — 이번 실행에만 적용됩니다)")


def agent_name(config):
    """비서의 이름. config.json의 name 한 줄이 화면·기록·자기소개를 전부 결정합니다."""
    return config.get("name") or "비서"


def load_key(entry):
    """키 파일이 없으면 None. 로컬 모델(key_file: null)은 키가 필요 없습니다."""
    key_file = entry.get("key_file")
    if not key_file:
        return None
    path = os.path.join(BASE_DIR, key_file)
    if os.path.exists(path):
        # utf-8-sig: 메모장이나 PowerShell이 붙이는 BOM을 제거합니다.
        # BOM이 남아 있으면 HTTP 헤더에 들어가 UnicodeEncodeError로 터집니다.
        with open(path, "r", encoding="utf-8-sig") as f:
            key = f.readline().strip()
        if key:
            return key
    return None


# ── 라우터: 위에서부터 시도하고, 실패하면 다음 모델로 ─────────────────
class AllModelsFailed(Exception):
    pass


# 한도가 찬 모델은 잠시 기억해뒀다가 건너뜁니다.
# 이게 없으면 질문할 때마다 죽은 모델을 한 번씩 찔러보고 429를 맞은 뒤에야 다음으로 내려갑니다.
# (실제로 Gemini 무료 일일 한도가 마르면 모든 질문이 그 헛발질을 한 번씩 거쳤습니다.)
_cooldown = {}   # {label: 이 시각까지는 건너뛴다}


def _resting(label):
    until = _cooldown.get(label, 0)
    return until > time.time()


def _rest(label, minutes):
    _cooldown[label] = time.time() + minutes * 60


# 추론 모드(reasoning) 인자를 얹었더니 400으로 거부한 두뇌를 기억합니다.
# 한 번 거부당하면 이번 실행 동안은 그 두뇌에 추론 인자를 다시 얹지 않습니다 —
# 안 그러면 어려운 질문마다 400을 한 번 맞고 인자를 떼어 재시도하느라 시간을 버립니다.
# (추론 인자를 못 받는다고 두뇌를 **버리는 게 아니라**, 인자만 빼고 그대로 씁니다.)
_no_reason = set()   # {label} — 추론 인자를 거부한 두뇌


def _reasoning_for(entry, deep_think):
    """이 두뇌에 얹을 추론 설정을 돌려줍니다. 없으면 None.
    (system 키는 페이로드가 아니라 시스템 메시지로 따로 처리하므로 여기선 분리해 줍니다.)"""
    if not deep_think or entry["label"] in _no_reason:
        return None, None
    r = entry.get("reasoning")
    if not r:
        return None, None
    r = dict(r)
    sys_msg = r.pop("system", None)      # "detailed thinking on" 같은 시스템 지시
    return (r or None), sys_msg          # (페이로드에 병합할 키, 시스템 메시지)


def resting_until(label):
    """이 두뇌가 한도로 쉬는 중이면 '언제까지'(epoch), 아니면 0.
    눈 신뢰도 시험(eyecheck)이 한도로 날아간 문항을 쿨다운이 풀린 뒤 다시 묻는 데 씁니다."""
    until = _cooldown.get(label, 0)
    return until if until > time.time() else 0


# 최후의 보루인 로컬 ollama가 꺼져 있으면 자동으로 켭니다 — 클라우드 두뇌가 전부
# 한도·오류로 막혀도 루시가 "모든 모델이 실패"로 멈추지 않게 하는 안전망입니다.
# doctor는 시작 시·새벽에만 돌아 '대화 도중 ollama가 죽는' 창을 못 막으므로,
# 로컬 두뇌를 부르기 직전에 매번 여기서 확인합니다. serve는 프로세스당 한 번만 띄웁니다.
_OLLAMA_PORT = 11434
_ollama_started = False


def _ollama_up(timeout=0.4):
    try:
        with socket.create_connection(("127.0.0.1", _OLLAMA_PORT), timeout):
            return True
    except OSError:
        return False


def _ensure_ollama(wait=15):
    """로컬 두뇌를 부르기 직전에 ollama 서버가 살아있게 합니다(꺼졌으면 켜고 잠깐 기다림)."""
    global _ollama_started
    if _ollama_up():
        return True
    exe = shutil.which("ollama") or os.path.expandvars(
        r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    if not exe or not os.path.exists(exe):
        return False                      # 설치가 없으면 어쩔 수 없음(doctor가 설치를 안내)
    if not _ollama_started:               # 이미 한 번 띄웠으면 중복 기동하지 않고 뜨기만 기다림
        _ollama_started = True
        try:
            subprocess.Popen(
                [exe, "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0)
                               | getattr(subprocess, "DETACHED_PROCESS", 0)))
        except OSError:
            return False
    deadline = time.time() + wait
    while time.time() < deadline:
        if _ollama_up():
            return True
        time.sleep(0.5)
    return False


# 추론형 모델(qwen3 등)은 생각 과정을 <think>...</think>로 함께 뱉습니다.
# 도구를 쓸 때는 알아서 감춰지지만, 순수 텍스트 응답(검토·교차검증 판단)에서는 그대로 새어 나옵니다.
_THINK = re.compile(r"<think>.*?</think>\s*", re.S | re.I)


def _clean(text):
    """모델의 속마음과 터미널에서 깨져 보이는 LaTeX 기호를 걷어냅니다."""
    if not text:
        return text
    text = _THINK.sub("", text)
    text = re.sub(r"<think>.*", "", text, flags=re.S | re.I)   # 닫는 태그가 잘린 경우
    text = re.sub(r"\\times", "×", text)
    text = re.sub(r"\\div", "÷", text)
    text = re.sub(r"\$+([^$\n]+?)\$+", r"\1", text)            # $...$ 수식 껍데기 제거
    return text.strip()


def call_model(config, messages, use_tools=True, order=None, force_tool=False, deep_think=False):
    """살아있는 첫 번째 모델의 응답을 돌려줍니다. (응답, 모델 이름, 모델 설정)

    deep_think=True이면 그 두뇌에 추론 모드(reasoning) 설정이 있을 때 얹어 더 깊게
    생각하게 합니다 — 어려운 질문에서만 켭니다(토큰·속도를 그때만 씁니다)."""
    problems = []
    cool = config.get("quota_cooldown_min", {})

    # 부른 쪽이 순서를 직접 준 경우(눈 전용 순서 등)는 그대로 씁니다 — 그쪽이 더 잘 압니다.
    # 기본 순서일 때만 계측을 보고 만성 고장·만성 지연 두뇌를 뒤로 미룹니다(config는 안 고침).
    if order is None:
        order = status.rank(config, config["models"])
    for i_entry, entry in enumerate(order):
        label = entry["label"]
        key = load_key(entry)
        is_local = entry.get("key_file") is None

        if not is_local and not key:
            problems.append(f"{label}: API 키 없음 (keys/ 폴더 확인)")
            continue

        if _resting(label):
            problems.append(f"{label}: 한도 초과로 쉬는 중 (건너뜀)")
            continue

        # 최후의 보루(로컬 ollama)는 부르기 직전에 서버가 켜져 있는지 확인하고, 꺼져 있으면
        # 자동으로 켜서 기다립니다 — 위 클라우드 두뇌가 다 막혀도 이 두뇌만은 답하게 합니다.
        if is_local and not _ensure_ollama():
            problems.append(f"{label}: ollama를 켜지 못했습니다 (설치를 확인하세요)")
            continue

        # 작은 로컬 모델은 "모르면 검색하라"는 지시를 흘려듣고 사실을 지어냅니다
        # (실제로 북한산 높이를 2,743m라고 답한 적이 있음 — 정답은 836m).
        # 그래서 해당 모델을 쓸 때만 경고를 생성 직전에 한 번 더 박아 넣습니다.
        msgs = messages
        if entry.get("reminder") and use_tools:
            msgs = messages + [{"role": "system", "content": entry["reminder"]}]

        # 추론 모드: 이 두뇌가 어려운 질문을 더 깊게 생각하도록 켭니다(deep_think일 때만).
        # reason_payload = 페이로드에 병합할 키(예: reasoning_effort). 아래 400 안전망이 지킵니다.
        # reason_sys = 시스템 메시지로 켜는 방식(nemotron의 "detailed thinking on") — 무해하므로 항상 유지.
        reason_payload, reason_sys = _reasoning_for(entry, deep_think)
        if reason_sys:
            msgs = msgs + [{"role": "system", "content": reason_sys}]

        # 컨텍스트 제한이 있는 두뇌(Cerebras 8192 등)는 메시지 프루닝을 먼저 수행하여 400 에러를 전면 방지합니다.
        ctx_limit = entry.get("context")
        if ctx_limit:
            msgs_to_send = session.prune_for_context_limit(msgs, max_tokens=ctx_limit)
        else:
            msgs_to_send = msgs

        # OpenAI 규격에 없는 필드(우리가 붙인 메모 등)를 떼어냅니다.
        # ⚠️ 반복 변수 이름에 key를 쓰면 위에서 읽은 API 키를 덮어써서 401이 납니다(실제로 겪음).
        clean_msgs = []
        for m in msgs_to_send:
            if m.get("_from") == label and m.get("_raw"):
                # 이 메시지를 만든 바로 그 두뇌에게는 원문 그대로 —
                # Gemini는 자기가 붙인 thought_signature를 못 돌려받으면 400을 냅니다.
                clean_msgs.append(m["_raw"])
                continue
            clean_m = {"role": m["role"]}
            for field in ("content", "tool_calls", "name", "tool_call_id"):
                if field in m:
                    clean_m[field] = m[field]
            clean_msgs.append(clean_m)

        payload = {"model": entry["model"], "messages": clean_msgs}
        if use_tools:
            payload["tools"] = tools.specs_for(entry, msgs_to_send)   # 작은 두뇌엔 요약+질문 관련 도구만
            if force_tool:
                if isinstance(force_tool, str):
                    payload["tool_choice"] = {"type": "function", "function": {"name": force_tool}}
                else:
                    payload["tool_choice"] = "required"   # 반드시 도구를 쓰게 강제

        # 추론 인자를 얹은 body를 만듭니다. with_reasoning=False면 인자를 빼고 만듭니다
        # (400 안전망이 재시도할 때 씁니다 — 이 두뇌가 추론 인자를 못 받아도 답은 받아냅니다).
        def _make_body(with_reasoning):
            p = dict(payload)
            if with_reasoning and reason_payload:
                p.update(reason_payload)
            return json.dumps(p, ensure_ascii=False).encode("utf-8")

        use_reasoning = bool(reason_payload)
        body = _make_body(use_reasoning)

        # User-Agent가 없으면 Groq 등의 Cloudflare가 403으로 막습니다(파이썬 기본 UA는 봇 취급).
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        }
        if key:
            headers["Authorization"] = f"Bearer {key}"

        url = entry["base_url"].rstrip("/") + "/chat/completions"

        fail_kind = None                      # 이 두뇌가 왜 못 답했나(계측용) — 성공하면 None
        has_alternatives = any(not _resting(m["label"]) for m in order[i_entry + 1:])

        for attempt in range(3):
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            t0 = time.time()                  # 이 두뇌가 답하는 데 걸린 시간을 잽니다
            try:
                with urllib.request.urlopen(req, timeout=entry.get("timeout", 45)) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if not data.get("choices"):
                    # OpenRouter(무료 라우터)는 위쪽 모델이 죽으면 **200인데 error 몸통**을
                    # 줍니다 — 그대로 두면 KeyError '연결 실패'로 뭉개져 원인이 안 보입니다.
                    err = data.get("error") or {}
                    note = str(err.get("message") or data)[:160]
                    problems.append(f"{label}: 응답에 답이 없음 ({note})")
                    fail_kind = "noanswer"
                    break
                message = data["choices"][0]["message"]
                message["content"] = _clean(message.get("content"))
                status.record(label)          # '/상태'의 '오늘 몇 번 썼나' — 실패해도 조용합니다
                # i_entry>0이면 폴백: 위 두뇌들이 못 답해 여기까지 내려온 것입니다.
                status.record_call(label, time.time() - t0, i_entry)
                return message, label, entry

            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="replace")[:200]
                # 안전망: 추론 인자를 얹었는데 이 두뇌가 거부(대개 400/422)하면,
                # 두뇌를 **버리지 말고** 인자만 빼서 같은 두뇌로 다시 부릅니다.
                if use_reasoning and e.code in (400, 422) and attempt < 2:
                    _no_reason.add(label)
                    use_reasoning = False
                    body = _make_body(False)
                    print(f"    -> {label}: 추론 인자를 못 받음 → 빼고 재시도(두뇌는 유지)")
                    continue
                if e.code in (500, 502, 503, 504):
                    if has_alternatives and attempt >= 1:
                        _rest(label, 2)
                        problems.append(f"{label}: 서버 혼잡({e.code}) → 대체 두뇌로 빠른 전환")
                        fail_kind = "busy"
                        break
                    elif attempt < 2:
                        wait = 1.5
                        print(f"    -> {label}: 서버 혼잡({e.code}) — {wait}초 후 재시도")
                        time.sleep(wait)
                        continue
                if e.code == 429:
                    if entry.get("vision") and attempt < 1:
                        print(f"    -> {label}: 비전 한도 초과(429) → 1.5초 후 1회 재시도")
                        time.sleep(1.5)
                        continue
                    rest = cool.get("quota", 15)
                    _rest(label, rest)
                    problems.append(f"{label}: 무료 한도 초과 → {rest}분간 건너뜁니다")
                    fail_kind = "quota"
                    break
                elif e.code == 413:
                    rest = cool.get("too_big", 2)
                    _rest(label, rest)
                    problems.append(f"{label}: 분당 토큰 한도 초과 → {rest}분간 건너뜁니다")
                    fail_kind = "too_big"
                    break
                elif e.code in (401, 403):
                    problems.append(f"{label}: 키가 거부됨 ({e.code})")
                    fail_kind = "authkey"
                    break
                elif "context_length_exceeded" in detail or "reduce the length" in detail or (e.code == 400 and any(w in detail.lower() for w in ("context", "too long", "length"))):
                    if attempt < 2:
                        print(f"    -> {label}: 컨텍스트 초과 감지 → 대화 비상 축소 후 재시도")
                        emergency_ctx = entry.get("context", 8192)
                        msgs_to_send = session.prune_for_context_limit(msgs, max_tokens=emergency_ctx, reserved_tokens=4000)
                        clean_msgs = []
                        for m in msgs_to_send:
                            if m.get("_from") == label and m.get("_raw"):
                                clean_msgs.append(m["_raw"])
                                continue
                            clean_m = {"role": m["role"]}
                            for field in ("content", "tool_calls", "name", "tool_call_id"):
                                if field in m:
                                    clean_m[field] = m[field]
                            clean_msgs.append(clean_m)
                        payload["messages"] = clean_msgs
                        if use_tools:
                            payload["tools"] = tools.specs_for(entry, msgs_to_send)
                        body = _make_body(use_reasoning)
                        continue
                    rest = cool.get("too_long", 10)
                    _rest(label, rest)
                    problems.append(f"{label}: 대화가 이 두뇌의 한계보다 김 → {rest}분간 건너뜁니다")
                    fail_kind = "too_long"
                    break
                else:
                    problems.append(f"{label}: HTTP {e.code} {detail}")
                    fail_kind = "http"
                    break

            except Exception as e:
                if has_alternatives:
                    _rest(label, 2)
                    problems.append(f"{label}: 연결/타임아웃 ({type(e).__name__}) → 대체 두뇌로 빠른 전환")
                    fail_kind = "timeout"
                    break
                problems.append(f"{label}: 연결 실패 ({type(e).__name__})")
                fail_kind = "conn"
                break

        if fail_kind:
            status.record_fail(label, fail_kind)   # 계측 — 왜 못 답했나(조용)
        print(f"    -> {problems[-1]}")

    raise AllModelsFailed("\n".join("  · " + p for p in problems))


# ── 난이도 라우팅: 쉬운 질문에 좋은 모델을 낭비하지 않습니다 ──────────
HARD_MARKERS = (
    "왜", "어떻게", "설계", "분석", "비교", "추천", "계획", "기획", "정리", "요약",
    "코드", "짜줘", "만들어", "고쳐", "설명", "차이", "장단점", "방법", "전략",
    # 코딩·디버깅은 짧게 물어도(“이 에러 뭐야?”) 추론이 필요한 질문입니다.
    "버그", "에러", "오류", "수정", "구현", "리팩", "아키텍처", "최적화", "성능", "테스트",
)


def is_hard(user_text, config):
    routing = config.get("routing", {})
    text = (user_text or "").strip()
    return len(text) > routing.get("easy_max_len", 30) or any(k in text for k in HARD_MARKERS)


# '여러 갈래를 한 번에 묻는' 큰 질문인지. 이런 건 통째로 답하면 한 갈래를 빠뜨립니다 —
# 하위 문제로 쪼개 각각 확인한 뒤 종합하게 지시합니다(아래 DECOMPOSE_HINT). 추가 호출은 없습니다.
def is_very_hard(user_text, config):
    routing = config.get("routing", {})
    text = (user_text or "").strip()
    if len(text) > routing.get("complex_len", 140):
        return True
    hits = sum(1 for k in HARD_MARKERS if k in text)          # 어려운 요청 키워드가 몇 개나 겹쳤나
    parts = sum(text.count(w) for w in ("그리고", "또", "각각", "단계", "그다음", "이후"))
    return hits >= 2 or parts >= 2


def pick_order(user_text, config):
    """
    질문 난이도에 따라 두뇌 순서를 바꿉니다.

    쉬운 질문은 빠른 주력(Groq, 2초)으로 즉답하고,
    어려운 질문만 느리지만 깊게 생각하는 모델("deep": true)을 앞으로 당깁니다.
    어느 쪽이든 실패하면 나머지 모델로 그대로 내려가므로 답을 못 받는 일은 없습니다.
    """
    models = config["models"]
    routing = config.get("routing", {})
    if not routing.get("enabled", True) or len(models) < 2:
        return models, "기본"

    if not is_hard(user_text, config):
        return models, "쉬움 → 빠른 주력부터"

    deep = [m for m in models if m.get("deep")]
    if not deep:
        return models, "어려움 → 주력부터 (깊은 생각용 모델 없음)"
    return deep + [m for m in models if not m.get("deep")], "어려움 → 깊은 생각용 두뇌부터"


# ── 에이전트 루프 ─────────────────────────────────────────────────
def build_system_prompt(config):
    # 기억은 여기 전부 싣지 않습니다. 매 질문마다 관련된 것만 골라 넣습니다(아래 recall_for).
    return config["persona"].replace("{name}", agent_name(config))


REPHRASE_PROMPT = """아래 질문으로 개인 비서의 장기 기억(사용자에 대한 사실들)을 검색하려 한다.
질문에 지시대명사나 생략이 많아 그대로는 잘 찾지 못한다.

무엇을 찾아야 하는지 검색어로 바꿔라. 명사 위주로, 쉼표로 구분해 한 줄만 출력하라.
예: "저번에 그 프로젝트 폴더 어디였지?" -> 사용자 프로젝트 경로, 폴더 위치, 작업 중인 개발

[질문]
{question}"""


def recall_for(user_text, config):
    """
    이번 질문과 관련된 기억만 골라 대화에 끼워 넣습니다.

    "앱 서명할 때 그거 필요하지 않았나?" 같은 질문은 문장 그대로 임베딩하면 빗나갑니다.
    빈손으로 끝나는 게 아니라 '엉뚱한 기억을 낮은 점수로' 가져오는 게 문제입니다.
    그래서 1등 유사도가 기준(memory_confident_score)에 못 미치면, 모델에게 검색어를
    다시 뽑게 해서 한 번 더 찾고 두 결과를 합칩니다.

    확신이 있을 때는 부르지 않으므로, 무료 한도는 거의 그대로입니다.
    """
    picked, method, best = memory_search.search_scored(user_text, config)

    confident = config.get("memory_confident_score", 0.60)
    if (config.get("memory_rephrase", True) and best < confident and len(user_text) > 5):
        try:
            message, _used, _entry = call_model(
                config,
                [{"role": "user", "content": REPHRASE_PROMPT.format(question=user_text)}],
                use_tools=False,
            )
            query = (message.get("content") or "").strip().splitlines()[0][:120]
        except (AllModelsFailed, IndexError):
            query = ""

        if query and query != user_text:
            again, _m, best2 = memory_search.search_scored(query, config)
            added = [n for n in again if n not in picked]
            if added:
                picked += added
                method += f" + 재정의(\"{query}\") {len(added)}개 추가 (최고 {best2:.2f})"

    if not picked:
        return None
    print(f"    [기억] {method}")
    return {
        "role": "system",
        "content": "[관련 기억 — 이미 아는 사실로 취급한다]\n" + "\n".join("- " + n for n in picked),
    }


def local_only(config):
    """--local: 외부로 아무것도 보내지 않고 로컬 모델만 사용합니다."""
    # 읽어주기도 마찬가지입니다. 온라인 목소리는 읽을 문장을 밖으로 보내므로,
    # 이 모드에서는 config가 뭐라고 적혀 있든 윈도우 내장 목소리만 씁니다.
    # (config["tts"]를 고치지 않는 이유: save_tts가 그걸 파일에 되돌려 써서
    #  다음 실행에도 구글이 지워진 채로 남습니다)
    tts.privacy_mode(True)
    models = [m for m in config["models"] if m.get("key_file") is None]
    if not models:
        print("config.json에 로컬 모델이 없습니다.")
        sys.exit(1)
    config["models"] = models
    # 4B급 소형 모델은 긴 지시문에 쉽게 압도당하므로 성격을 짧게 줄입니다. 이름은 유지합니다.
    config["persona"] = (
        f"너는 한국어 개인 비서 '{agent_name(config)}'다. 짧고 정확하게 존댓말로 답한다.\n"
        "날짜·파일·검색이 필요하면 추측하지 말고 반드시 도구를 쓴다. 모르면 모른다고 말한다.\n"
        "일정·약속·수요일 할 일 등 일정 질문 시 캘린더/알림뿐 아니라 장기 메모(notes.md)와 대화록(search_memory/read_notes)을 반드시 함께 조회하여 다중 검증한다.\n"
        "너는 그림·이미지 생성 능력(draw 도구)을 가지고 있으므로 그림 요청이 오면 거절하지 말고 반드시 draw 도구를 써라.\n"
        "네 목소리 볼륨은 사용자가 '/읽기 볼륨 0~100'으로 조절한다(예: /읽기 볼륨 50). "
        "'목소리가 크다/작다·볼륨 줄여·키워'라고 하면 윈도우 볼륨이 아니라 이 명령을 먼저 안내하라.\n"
        "네가 무엇을 할 수 있는지·사용법을 물으면 상식으로 지어내거나 '없다'고 하지 말고, "
        "먼저 search_knowledge로 네 사용설명서(manual_루시_사용설명서)를 찾아 그 근거로 답하라."
    )
    return config


# 사실을 묻는 질문인지 판별합니다. 작은 모델이 여기에 답을 지어내는 게 가장 위험합니다.
FACT_QUESTION = re.compile(
    r"(얼마|몇\s|몇[가-힣]|언제|어디|누구|높이|길이|무게|인구|가격|나이|버전|최신|날씨|주소|뜻이|무엇)"
)

DRAW_QUESTION = re.compile(
    r"(그려|그림|이미지\s*생성|일러스트|그려서|그려줘|그려봐|그려주라|그림체|화풍|디자인|바탕화면에\s*저장|사진|생성해|만들어줘\s*그림|저장해줘|캐릭터|퍼리|draw|restyle)"
)

SCHEDULE_QUESTION = re.compile(
    r"(일정|약속|할\s*일|스케줄|캘린더|알림|수요일|월요일|화요일|목요일|금요일|토요일|일요일|이번\s*주|다음\s*주|몇\s*시|언제)"
)

REFUSAL_TEXT = re.compile(
    r"(그림을\s*(그리거나|생성|못|그릴)|생성할\s*수\s*없|도구를\s*제공하지|직접\s*그림|파일을\s*생성해|바탕화면에\s*저장할\s*수|이미지를\s*생성|그림\s*생성\s*능력|그림을\s*그릴\s*수|할\s*수\s*없습)"
)

# 어려운 질문에서 곧바로 답을 쓰기 시작하면 도구를 빼먹고 기억에 의존합니다.
# 답하기 전에 "무엇을 확인할지"부터 정하게 만듭니다. 추가 호출 없이 지시문 한 줄로 끝납니다.
PLAN_HINT = (
    "이 질문은 한 번에 답하지 마라. 먼저 답에 필요한 사실이 무엇인지 정하고, "
    "그것을 어떤 도구로 확인할지 한 줄로 계획한 뒤 그대로 실행하라.\n"
    "일정, 약속, 수요일 할 일 등 일정 관련 질문이 들어왔을 때는 캘린더/알림 도구(list_events, list_reminders)뿐만 아니라 "
    "장기 메모(notes.md, read_notes) 및 대화 검색(search_memory)을 반드시 함께 조회하여 다중 검증 후 답변하라. "
    "구글 캘린더나 알림 결과가 비어있거나 연동 에러가 나더라도 메모/대화록을 반드시 확인하여 놓친 일정이 없는지 검증하라.\n"
    "숫자 계산은 암산하지 말고 calc 또는 run_python을 쓴다. "
    "정확도가 중요한 조사는 web_search 대신 research를 쓴다. "
    "날씨·기온·비 예보는 web_search가 아니라 get_weather를 쓴다. "
    "버스 도착·정류장 정보는 web_search가 아니라 get_bus를 쓴다. "
    "지하철·전철 도착은 get_subway를 쓴다. "
    "보고서·기획서·발표자료(PPT)·엑셀 시트 등 문서 작성 요청 시 마크다운 헤더(#/##), 구조화된 표(| a | b |), PPT 발표자 노트('노트: ...'), 깔끔한 글머리표를 사용해 전문적으로 작성하고 write_document를 쓴다. "
    "이미 있는 문서를 고치는 요청은 edit_document를 쓴다. "
    "동영상 자르기·소리 추출·변환·움짤은 edit_video를 쓴다. "
    "여러 파일짜리 프로그램을 짓거나 에러를 고쳐가며 완성하는 일은 code_write→code_run→code_edit(코딩 작업실)로 하고, "
    "run_python은 한 번 돌리고 버리는 계산에만 쓴다(code_run은 .py는 파이썬·.cs는 C#으로 돌린다). "
    "유니티 C# 작업은 먼저 unity_find로 기존 코드를 확인하고, 새 스크립트는 unity_new_script로 골격을 만든 뒤 edit_document로 채우고, "
    "unity_run으로 컴파일·테스트를 확인해 에러가 나면 그 file(줄,칸)을 보고 고쳐 다시 unity_run을 돌린다. "
    "에디터를 켜둔 채 컴파일 에러만 빠르게 볼 땐 unity_status(에디터 안 닫아도 됨), APK·빌드는 unity_build를 쓴다. "
    "여러 3D 파일에 같은 작업(변환·경량화·유니티용 정리)을 한꺼번에 할 땐 blender_batch, 한 파일에 여러 작업을 몰아 할 땐 blender_3d의 chain을 쓴다. "
    "3D 모델이 유니티에 잘 들어갈지 진단은 blender_3d의 check, 유니티 프로젝트의 깨진 참조·큰 텍스처 감사는 unity_audit를 쓴다. "
    "그림·일러스트·캐릭터·이미지 그리기/생성 요청은 거절하지 말고 draw 도구를 쓴다. "
    "확인하지 못한 것은 추측하지 말고 모른다고 말한다."
)

SCHEDULE_HINT = (
    "⚠️[일정 및 약속 관련 다중 검증 지침]\n"
    "일정, 약속, 요일별 할 일 등 일정 관련 질문이 들어왔을 때, 캘린더/알림 도구(list_events, list_reminders)뿐만 아니라 "
    "장기 메모(notes.md, read_notes) 및 대화 검색(search_memory)을 반드시 함께 조회하여 다중 검증 후 답변하라.\n"
    "구글 캘린더나 알림 결과가 비어있거나 연동 에러/토큰 만료가 발생하더라도 메모 및 대화록(search_memory, read_notes)을 반드시 확인하여 놓친 일정이 없는지 검증하라."
)

# 여러 갈래를 한꺼번에 묻는 큰 질문에만 덧붙입니다(is_very_hard). 통째로 답하다 한 갈래를
# 빠뜨리는 걸 막습니다 — 하위 문제로 쪼개, 각각 확인한 뒤 종합하게 합니다. 추가 호출은 없습니다.
DECOMPOSE_HINT = (
    "이 요청은 여러 갈래가 섞여 있다. 곧바로 답하지 말고, 먼저 답해야 할 하위 질문을 "
    "2~5개로 쪼개 번호로 적어라. 그런 다음 하나씩 필요한 도구로 확인하며 풀고, "
    "마지막에 그 결과들을 합쳐 하나의 답으로 정리하라. "
    "어느 한 갈래라도 확인 못 하면, 무엇을 아직 못 했는지 분명히 밝혀라."
)

# 참조 그림을 '보고' 3D로 만들어 달라는 요청에 붙는 안내(세션68). 이 턴은 눈으로 보는 턴이라
# 도구가 꺼져 있으므로, 루시가 "기능이 없다"고 부정하는 대신 그림을 읽고 만들기를 제안하게 한다.
# ⚠️도구가 이 턴엔 없으니 여기서 실제 조립을 시키지 않는다 — 본 것을 설명하고 다음 단계로 넘긴다.
MODEL_FROM_REF = (
    "지금은 참조 그림을 눈으로 '보는' 턴이라 이 턴에는 도구가 꺼져 있다. "
    "너는 3D 모델링 도구(blender_3d의 build로 프리미티브 조립, sculpt_displace로 표면 요철 등)를 "
    "실제로 가지고 있으니 '그런 기능이 없다'고 말하지 마라. "
    "이 그림을 직접 보고 ①무엇인지 ②전체 형태와 비율(부위별 대략적인 크기 관계) ③눈에 띄는 특징을 "
    "네가 본 대로 설명하라. 그런 다음 이걸 어떤 치수의 그레이박스로 만들면 좋을지 네가 먼저 제안하고, "
    "사용자가 좋다고 하면 다음 단계에서 blender_3d로 실제 조립하겠다고 안내하라. "
    "파일 이름은 이 그림에서 본 대상으로 정하고, 기억 속 다른 프로젝트 이름을 쓰지 마라. "
    "⚠️사진을 그대로 자동 재현하는 기능은 없다 — 네가 본 형태를 치수로 옮겨 근사하는 것이다. "
    "그러니 사용자에게 텍스트로 치수를 불러 달라고 요구하기 전에, 먼저 그림을 보고 네가 읽어낸 형태와 "
    "제안 치수를 내놓아라(사용자는 그걸 고쳐주기만 하면 되게)."
)

# 비전 턴에서 3D 분석 후 텍스처 모델로 교체되었을 때 맥락 단절을 방지하는 지침
VISION_CONTINUE_HINT = (
    "이전 턴에서 이미지를 성공적으로 분석하여 3D 모델링/제작 지침과 제안 수치가 이미 대화에 수립되어 있다. "
    "사용자가 이에 동의하여 진행을 승인했으므로, 이미지를 볼 수 없다거나 능력이 없다고 거절하지 말고 "
    "이전 대화에서 이미 수립된 분석 내용과 제안 수치/스펙을 바탕으로 blender_3d(build action 또는 3D 관련 도구)를 즉시 실행하라."
)

DRAW_HINT = (
    "⚠️[필수 도구 지침: 이미지 생성 능력보유]\n"
    "사용자가 그림/이미지/일러스트/캐릭터 생성 또는 바탕화면 저장을 요청했습니다.\n"
    "너는 draw 도구를 호출하여 직접 그림을 그려 바탕화면 또는 저장소에 생성·저장하는 능력이 있습니다.\n"
    "'그림을 직접 그릴 수 없다', '파일을 생성해 바탕화면에 저장할 수 없다', '이미지 생성 도구가 없다'고 부정하거나 거짓 거절 텍스트를 출력하지 마라.\n"
    "텍스트로 거절하거나 설명하기 전에 반드시 draw 도구를 호출하세요! (draw의 prompt는 사용자의 요청을 영문 묘사로 변환하여 전달합니다.)"
)


def _has_vision_3d_ref(messages):
    """이전 대화에 비전 3D 이미지 분석 지침이 포함되어 있는지 확인합니다."""
    for m in messages:
        content = str(m.get("content", ""))
        if "MODEL_FROM_REF" in content or "참조 그림을 눈으로 '보는' 턴이라" in content:
            return True
    return False

REVIEW_PROMPT = """너는 방금 작성된 답변을 검토하는 감수자다.

[사용자 질문]
{question}

[도구로 확인한 근거]
{evidence}

[검토할 답변]
{answer}

다음을 확인하라:
- 근거에 없는 내용을 단정하지 않았는가 (지어낸 사실)
- 계산이나 숫자가 틀리지 않았는가
- 질문에 실제로 답했는가 (곁길로 새지 않았는가)

문제가 없으면 'OK' 한 단어만 출력하라.
문제가 있으면 고친 최종 답변만 출력하라. 설명이나 사과는 쓰지 마라."""


def _evidence(messages, limit=3000):
    """마지막 턴에서 도구가 돌려준 것들 — 감수자가 답과 대조할 근거입니다."""
    bits = [str(m.get("content", "")) for m in messages if m.get("role") == "tool"]
    return ("\n---\n".join(bits))[-limit:] if bits else "(도구를 쓰지 않음)"


def review(config, messages, question, answer, order=None, author=None):
    """답을 내보내기 전에 한 번 더 훑습니다. 고칠 게 있으면 고친 답을 돌려줍니다.

    author(답을 낸 두뇌)를 주면, 감수는 **다른 두뇌**가 하도록 순서를 바꿉니다.
    자기 답을 자기가 검토하면 같은 착각을 그대로 넘기기 쉽습니다 — 두 번째 시선이
    지어냄·계산오류를 더 잘 잡습니다. 추가 호출 수는 그대로(감수 1회)입니다."""
    rorder = order
    if author and config.get("deliberate", {}).get("review_independent", True):
        base = order or status.rank(config, config["models"])
        # 답을 낸 두뇌는 맨 뒤로 — 다른 두뇌가 다 막혔을 때만 자기가 검토합니다.
        rorder = ([e for e in base if e["label"] != author]
                  + [e for e in base if e["label"] == author])
    prompt = REVIEW_PROMPT.format(
        question=question,
        evidence=_evidence(messages),
        answer=answer,
    )
    try:
        message, _used, _entry = call_model(
            config, [{"role": "user", "content": prompt}], use_tools=False, order=rorder
        )
    except AllModelsFailed:
        return answer, False          # 검토를 못 해도 원래 답은 그대로 내보냅니다

    verdict = (message.get("content") or "").strip()
    if not verdict or verdict.upper().startswith("OK") or len(verdict) < 10:
        return answer, False
    return verdict, True


def sanitize(message, from_label=None):
    """
    모델이 돌려준 답을 **대화에 남기기 전에** 규격에 맞는 최소한으로 깎습니다.

    ⚠️ 이걸 안 하면 두뇌를 갈아탈 수 없습니다(실제로 겪음). 공급자마다 tool_calls에 자기만의
       여분 필드를 얹어 보내는데(Gemini는 extra_content), 그걸 그대로 다음 요청에 되실으면
       **Cerebras가 400 "property ... is unsupported"로 대화를 통째로 거부**합니다.
       한도 초과로 폴백이 일어난 순간부터 도구를 쓴 대화는 그 두뇌에서 영영 못 이어집니다 —
       벤치 1위 두뇌가 조용히 무용지물이 되는 셈입니다.
       규격에 있는 것만 남기면 어느 두뇌든 남의 대화를 이어받을 수 있습니다.

    ⚠️ 그런데 **만든 본인에게는 원문을 돌려줘야** 합니다(이것도 실제로 겪음). Gemini 3는
       자기가 tool_calls에 붙인 thought_signature를 다음 요청에서 되돌려 받지 못하면
       400으로 거절합니다 — 깎은 것만 남기면 이번엔 Gemini가 자기 대화를 못 잇습니다.
       그래서 원문을 _raw에 접어 두고, call_model이 **그 두뇌에게 보낼 때만** 원문을 씁니다.
       (_로 시작하는 필드는 요청에 실리지 않으므로 다른 두뇌는 볼 일이 없습니다)
    """
    clean = {"role": message.get("role", "assistant")}
    if message.get("content") is not None:
        clean["content"] = message["content"]
    calls = message.get("tool_calls")
    if calls:
        # ⚠️ arguments는 그대로 두지 말고 반드시 유효한 JSON으로 다듬습니다(실제로 겪음).
        #    모델이 인자 문자열 안에 생 줄바꿈을 뱉으면(긴 본문 인자에서 잘 남),
        #    그 메시지가 대화에 남는 순간부터 Groq·Ollama가 **대화 전체를 400으로 거부** —
        #    한도 폴백과 겹치면 '모든 두뇌 실패'로 대화가 통째로 죽습니다(2026-07-14 실사).
        #    본인에게 돌아가는 _raw 안의 arguments도 같이 고칩니다(본인 서버도 되받으면 검증함).
        for c in calls:
            fn = c.get("function") or {}
            fn["arguments"] = _safe_args(fn.get("arguments"))
        clean["tool_calls"] = [{
            "id": c.get("id"),
            "type": "function",
            "function": {
                "name": (c.get("function") or {}).get("name"),
                "arguments": (c.get("function") or {}).get("arguments") or "{}",
            },
        } for c in calls]
        if from_label:
            clean["_from"] = from_label
            clean["_raw"] = message
    return clean


def _safe_args(raw):
    """tool_calls의 arguments를 어느 두뇌든 받아줄 유효한 JSON 문자열로 다듬습니다."""
    if isinstance(raw, dict):                     # 문자열 대신 dict로 주는 공급자도 있습니다
        return json.dumps(raw, ensure_ascii=False)
    raw = raw or "{}"
    try:
        json.loads(raw)
        return raw                                # 멀쩡하면 원문 그대로
    except ValueError:
        pass
    # 가장 흔한 고장 = 문자열 안의 생 줄바꿈·탭 → 이스케이프하면 대개 살아납니다
    fixed = (raw.replace("\r\n", "\\n").replace("\n", "\\n")
             .replace("\r", "\\n").replace("\t", "\\t"))
    try:
        json.loads(fixed)
        return fixed
    except ValueError:
        pass
    try:                                          # 마지막 시도: 괄호 짝 세기로 JSON 덩어리 건지기
        import worker
        got = worker.json_from(raw)
        if isinstance(got, dict):
            return json.dumps(got, ensure_ascii=False)
    except Exception:
        pass
    return "{}"      # 못 고치면 빈 인자 — 그 도구 호출은 실패해도 **대화와 폴백은 살아야 합니다**


# ── 메모리 저장 / 대화 동기화 (Auto Git Sync) ─────────────────────
MEMORY_TOOL_NAMES = {
    "add_note", "add_reminder", "add_todo", "done_todo", "add_event",
    "cancel_reminder", "save_memory", "update_memory", "write_note", "save_note"
}

AUTO_SYNC_USER_PATTERN = re.compile(
    r"("
    r"기억\s*해|기억\s*해줘|기억\s*하자|기억\s*해두|기억\s*해둔|기억\s*해\s*줘|"
    r"저장\s*해|저장\s*해줘|저장\s*하자|저장\s*해두|저장\s*해\s*줘|"
    r"기록\s*해|기록\s*해줘|기록\s*하자|기록\s*해두|기록\s*해\s*줘|"
    r"메모리.*(저장|기록|기억|남겨)|"
    r"수고\s*(했어|했네|하세요|해|고|했음)|고생\s*(했어|했네|하세요|해|고|했음)|"
    r"다음에\s*(이어서|보자|하자)|나중에\s*보자|"
    r"종료|끝"
    r")",
    re.IGNORECASE
)

def _is_memory_tool(tool_name):
    if not tool_name:
        return False
    name_lower = tool_name.lower()
    if name_lower in MEMORY_TOOL_NAMES:
        return True
    return any(k in name_lower for k in ("note", "reminder", "todo", "memory"))

def check_auto_git_sync_user_input(text):
    if not text:
        return False
    if AUTO_SYNC_USER_PATTERN.search(text):
        return True
    keywords = ["기억", "저장", "기록", "메모리", "수고", "고생", "다음에", "나중에", "종료", "끝"]
    for kw in keywords:
        if kw in text:
            return True
    return False


def run_turn(config, messages, order=None, use_tools=True, force_tool=False, deep_think=False):
    """모델이 '도구 그만 쓰고 답하겠다'고 할 때까지 돌립니다.
    deep_think=True면 추론 모드를 켤 수 있는 두뇌에 얹습니다(어려운 질문에서만)."""
    last_user = next((session.text_of(m) for m in reversed(messages) if m.get("role") == "user"), "")
    empty = 0           # 본문 없이 '생각'만 돌아온 횟수

    for step in range(config.get("max_steps", 8)):
        message, used, entry = call_model(config, messages, order=order,
                                          use_tools=use_tools, force_tool=force_tool if step == 0 else False,
                                          deep_think=deep_think)

        # 사실 질문인데 도구를 안 쓰고 첫 턴에 바로 답하려 하면 도구 사용을 강제해 다시 부릅니다.
        if (
            use_tools
            and step == 0
            and entry.get("reminder")
            and not message.get("tool_calls")
            and FACT_QUESTION.search(str(last_user))
        ):
            print("    [안전장치] 사실 질문인데 도구를 안 씀 → 도구 사용을 강제해 재요청")
            message, used, entry = call_model(config, messages, order=[entry],
                                              force_tool=True, deep_think=deep_think)
        # 그림/이미지 요청인데 도구를 부르지 않고 거절 텍스트를 출력하거나 텍스트 답변만 내놓은 경우 draw 호출 강제
        elif (
            use_tools
            and step == 0
            and not message.get("tool_calls")
            and DRAW_QUESTION.search(str(last_user))
        ):
            print("    [안전장치] 그림 요청인데 도구(draw) 미호출 발생 → draw 호출 강제 재요청")
            message, used, entry = call_model(config, messages, order=[entry],
                                              force_tool="draw", deep_think=deep_think)

        message = sanitize(message, used)  # 남에겐 규격만, 본인에겐 원문을(둘 다 안 하면 400)
        messages.append(message)

        calls = message.get("tool_calls")
        if not calls:
            content = (message.get("content") or "").strip()
            if content:
                return content, used

            # 추론형 모델은 가끔 '생각'(reasoning)만 채우고 본문을 비운 채 돌려줍니다(zai-glm에서 실측).
            # 그걸 그대로 내보내면 사용자에게는 "(빈 응답)"만 보이고 대화가 끊깁니다.
            # 빈 답은 기록에 남기지 않고, 그 두뇌를 빼고 다시 묻습니다.
            messages.pop()
            empty += 1
            if empty >= 3:
                return "(두뇌가 빈 답을 돌려줬습니다. 다시 물어봐 주세요.)", used
            print("    [빈 답] 본문 없이 생각만 돌아옴 → 다른 두뇌에게 다시 묻습니다")
            order = [e for e in (order or config["models"]) if e is not entry] or None
            continue

        for c in calls:
            name = c["function"]["name"]
            args = c["function"].get("arguments", "{}")
            print(f"    [도구] {name}({args[:80]})")
            result = tools.call(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": c["id"],
                "content": result,
            })
            if _is_memory_tool(name):
                print(f"    [Git Sync] 메모리 도구({name}) 실행 완료 → 백그라운드 Git Sync(Push) 자동 실행")
                session.auto_git_sync("push")

    return "(도구를 너무 많이 사용해서 중단했습니다. 질문을 좀 더 좁혀서 다시 물어봐 주세요.)", "중단"


# ── 한 번의 문답 ───────────────────────────────────────────────────
def _ask_terminal(question):
    """터미널에서 y/N을 받습니다. 마우스를 움직이기 전 허락을 받는 데 씁니다."""
    try:
        return input(f"\n  {question} [y/N] ").strip().lower() == "y"
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def respond(config, state, user, notify=print, force_screen=False, confirm=_ask_terminal):
    """
    질문 하나를 받아 답을 돌려줍니다. 터미널(main)과 웹 화면(web.py)이 **함께** 씁니다.

    양쪽이 각자 이 흐름을 베껴 쓰면, 한쪽만 고쳐져서 '웹 루시는 기억을 못 하는'
    반쪽짜리가 됩니다. 그래서 흐름은 여기 한 벌만 둡니다.

    state는 이 대화의 살아 있는 부분입니다(messages·직전 문답·직전에 본 그림).
    notify는 진행 상황을 어디에 보여줄지 — 터미널은 print, 웹은 화면에 흘립니다.
    """
    if check_auto_git_sync_user_input(user):
        notify("    [Git Sync] 동기화 관련 키워드 감지 → 백그라운드 Git Sync(Push) 자동 실행")
        session.auto_git_sync("push")

    messages = state["messages"]

    # 대화가 길어지면 오래된 부분을 요약으로 접습니다(안 하면 토큰 한도를 넘겨 요청 자체가 거절됨).
    state["messages"], squeezed = session.compress(messages, config, call_model)
    messages = state["messages"]
    if squeezed:
        notify("[압축] 대화가 길어져 오래된 부분을 요약으로 접었습니다")

    # '/컴퓨터 ...' — 도구가 없는 프로그램은 손으로 만져야 합니다.
    # 화면을 찍어 보고 → 다음 한 동작을 정하고 → 진짜 마우스·키보드를 움직입니다.
    # 일꾼(worker)보다 먼저 봅니다: "/컴퓨터 ... 알아서 다 해줘"는 손으로 하는 일이지
    # 도구로 하는 일이 아니기 때문입니다(두 트리거가 겹치면 앞의 것이 이깁니다).
    if computer.enabled(config) and computer.wants(user):
        return computer.run(config, state, computer.strip_request(user), call_model,
                            notify=notify, confirm=confirm, log=session.log_turn)

    # '/일 ...' — 여러 단계짜리 일은 한 번의 문답으로 끝나지 않습니다.
    # 계획을 세우고 한 단계씩 실행·검증하는 바깥 루프(worker)에 넘깁니다.
    # respond() 안에 두는 이유: 터미널과 웹이 이 함수 하나를 공유하므로 여기 두면 양쪽이 함께 얻습니다.
    if worker.enabled(config) and worker.wants(user):
        goal = worker.strip_request(user)
        preface = []
        recalled = recall_for(goal, config)
        if recalled:
            preface.append(recalled)
        learned, how = lessons.recall_for(goal, config)
        if learned:
            notify(f"[실수 노트] {how}")
            preface.append(lessons.as_message(learned))
        return worker.run(config, state, goal, call_model, run_turn,
                          notify=notify, preface=preface, log=session.log_turn)

    # 이미지 경로가 섞여 있으면 '보는 턴'으로 바뀝니다. (예: "바탕화면\에러.png 이거 무슨 오류야?")
    question, images = user, []

    # "지금 화면 좀 봐줘" — 파일이 아니라 지금 모니터에 떠 있는 것을 봅니다.
    # 찍은 그림은 아래 비전 흐름을 그대로 타므로, 보는 턴 규칙(도구·감수 끔)이 공짜로 적용됩니다.
    if (screen.enabled(config) and (force_screen or screen.wants(user))
            and not vision.wants_edit(user)):
        if not vision.capable(config):
            notify("[화면] 눈이 달린 두뇌가 없어 화면을 볼 수 없습니다 (config의 vision: true 확인)")
        else:
            try:
                images = [screen.capture(config, mode=screen.mode_for(user), notify=notify)]
                question = screen.strip_request(user)
            except RuntimeError as e:
                notify(f"[화면] {e}")

    # "이 그림 화풍 바꿔줘"는 보는 요청이 아니라 고치는 요청입니다.
    # 보는 턴으로 만들면 도구가 꺼져서 restyle을 못 부르고 감상만 합니다(실제로 겪음).
    if not images and config.get("vision", {}).get("enabled", True) and not vision.wants_edit(user):
        question, images = vision.find_images(user)
        # 경로 없이 "이 그림에서 왼쪽 버튼은?"이라고 물으면 방금 본 그림을 다시 붙여줍니다.
        if not images and state.get("last_images") and vision.refers_back(user):
            images = state["last_images"]
        if images and not vision.capable(config):
            notify("[비전] 눈이 달린 두뇌가 없습니다 (config에서 vision: true 확인)")
            question, images = user, []

    # 이미지는 딱 한 턴만 삽니다. 대화에 남겨두면 (1) 매 요청마다 base64가 다시 실려 토큰 한도를
    # 태우고 (2) 눈 없는 모델이 "content must be a string" 400·403으로 전부 거절합니다(실제로 겪음).
    vision.strip_history_images(messages)

    if images:
        try:
            user_msg = vision.user_message(question, images)
        except (OSError, ValueError) as e:
            raise ImageUnreadable(str(e))
        notify(f"[비전] {vision.describe(images)}")
    else:
        user_msg = {"role": "user", "content": user}

    added = []

    recalled = recall_for(question, config)
    if recalled:
        added.append(recalled)

    # 예전에 이 비슷한 걸 틀린 적이 있으면 그 교훈을 먼저 읽힙니다.
    learned, how = lessons.recall_for(question, config)
    if learned:
        notify(f"[실수 노트] {how}")
        added.append(lessons.as_message(learned))

    hard = is_hard(question, config)
    think = config.get("deliberate", {})
    # 보는 턴에는 도구를 끄므로, 도구를 쓰라는 계획 지시는 넣지 않습니다.
    planned = hard and think.get("plan", True) and not images
    if planned:
        added.append({"role": "system", "content": PLAN_HINT})
        # 여러 갈래가 섞인 큰 질문이면 '쪼개서 각각 풀고 종합' 지시를 한 줄 더 얹습니다(호출 추가 없음).
        if think.get("decompose", True) and is_very_hard(question, config):
            added.append({"role": "system", "content": DECOMPOSE_HINT})

    is_draw = bool(DRAW_QUESTION.search(user))
    is_schedule = bool(SCHEDULE_QUESTION.search(user))
    if is_schedule:
        added.append({"role": "system", "content": SCHEDULE_HINT})

    # 참조 그림을 보고 3D로 만들어 달라는 요청이면, '기능 없다'고 부정하지 말고 본 것을 설명하며
    # 만들기를 제안하도록 안내를 심습니다(도구는 이 턴에 꺼져 있으니 실제 조립은 다음 턴). 세션68.
    if images and vision.wants_make(question):
        added.append({"role": "system", "content": MODEL_FROM_REF})
    elif not images and _has_vision_3d_ref(messages):
        added.append({"role": "system", "content": VISION_CONTINUE_HINT})
    elif is_draw and not images:
        added.append({"role": "system", "content": DRAW_HINT})

    added.append(user_msg)
    messages += added
    session.log_turn("나", user)

    if images:
        # 이미지를 못 보는 두뇌에 보내면 400으로 거절하거나, 더 나쁘게는 이미지를 무시하고 지어냅니다.
        order, why = vision.capable(config), "이미지 → 눈 달린 두뇌만"
    else:
        order, why = pick_order(question, config)
    # 어려운 질문에서만 추론 모드를 켭니다(토큰·속도를 그때만 씁니다). 보는 턴은 제외.
    deep_think = hard and think.get("reasoning", True) and not images
    notify(f"[라우팅] {why}" + ("  + 계획 세우기" if planned else "")
           + ("  + 깊게 생각" if deep_think else ""))

    try:
        # 이미지가 실린 요청에 도구 명세까지 함께 실으면 거절하는 모델이 있습니다.
        answer, used = run_turn(config, messages, order=order,
                                use_tools=not images, force_tool=is_draw, deep_think=deep_think)
    except AllModelsFailed:
        del messages[-len(added):]          # 이번 턴에 끼워 넣은 것들을 전부 되돌립니다
        raise

    # 감수자는 그림을 볼 수 없습니다. 보는 턴에 감수를 붙이면 맞는 답을 엉뚱하게 '고칩니다'.
    if hard and think.get("review", True) and not images:
        notify("[검토] 답을 스스로 감수하는 중...")
        # author=used → 답을 낸 두뇌 말고 다른 두뇌가 감수하도록(독립 시선).
        answer, fixed = review(config, messages, question, answer, order=order, author=used)
        if fixed:
            notify("[검토] 문제를 찾아 답을 고쳤습니다")
            messages[-1] = {"role": "assistant", "content": answer}

    session.log_turn(agent_name(config), answer)

    # 사용자가 방금 한 말이 지적이었다면, 직전 문답을 교훈으로 남깁니다.
    # (답을 다 내보낸 뒤에 해야 하지만, 웹은 답을 한 번에 보내므로 여기서 적습니다)
    # 판단력 3층(세션63 5부): "틀렸어"뿐 아니라 "천이 너무 뻣뻣해" 같은 **작품 품질 지적**도
    # 신호 — 이때는 도구 인자를 어떻게 바꿀지(kind=craft)로 교훈을 뽑습니다.
    if state.get("last_q") and state.get("last_a"):
        craft = lessons.is_craft_complaint(user, state["last_a"])
        if craft or lessons.is_correction(user):
            lesson = lessons.learn(config, call_model, state["last_q"], state["last_a"],
                                   user, answer, kind="craft" if craft else "answer")
            if lesson:
                notify(f"[실수 노트] 적었습니다 — {lesson}")

    state["last_q"], state["last_a"], state["last_images"] = question, answer, images
    return answer, used


class ImageUnreadable(Exception):
    """그림 파일을 열지 못했습니다."""


def new_state(config):
    # 오프라인 푸시 큐 재시도 처리
    try:
        session.process_pending_sync()
    except Exception:
        pass
    return {
        "messages": [{"role": "system", "content": build_system_prompt(config)}],
        "last_q": "",           # 직전 문답 — 사용자가 지적하면 이걸로 실수 노트를 씁니다
        "last_a": "",
        "last_images": [],      # 직전에 본 그림 — "이 그림에서 ~는?" 후속 질문에 다시 붙입니다
    }


# ── 대화 화면 ─────────────────────────────────────────────────────
def main():
    config = load_config()
    if "--local" in sys.argv:
        config = local_only(config)
    tools.init(config)
    os.makedirs(os.path.join(BASE_DIR, "keys"), exist_ok=True)
    name = agent_name(config)

    print("=" * 60)
    print(f"  {name}"
          + ("  [로컬 전용 모드 — 외부로 전송 안 함]" if "--local" in sys.argv else ""))
    print("  모델 우선순위:")
    for i, entry in enumerate(config["models"], 1):
        key = load_key(entry)
        state = "준비됨" if (key or entry.get("key_file") is None) else "키 없음"
        print(f"    {i}. {entry['label']}  [{state}]")
    eyes = ", ".join(m["label"] for m in vision.capable(config)) or "없음"
    print(f"  눈(이미지): {eyes}")
    mouth = " → ".join(tts.ENGINE_KO[e] for e in tts.engines(config)) if tts.enabled(config) else "꺼짐"
    print(f"  목소리(읽어주기): {mouth}")
    print("  /일 <시킬 일>      ← 여러 단계짜리 일을 계획하고 끝까지 해냅니다 (도구로)")
    print("  /컴퓨터 <시킬 일>  ← 화면을 보며 마우스·키보드를 직접 움직입니다 (허락을 받고)")
    print("  /보기 <그림> · /화면 <질문> · /감시 <조건> · /유튜브 <주소> · /브리핑 · /읽기 · /교훈 · /검증 <질문> · /벤치 · /지식갱신 · /문서색인 · /기억정리 · /점검 · /상태 · /복습 · /공부 · 음성 · /음성모드")
    print("  종료하려면 exit 입력")
    print("=" * 60)

    # 제 몸 점검 — 문제가 있으면 말하고, 켜서 고칠 수 있는 건 그 자리에서 켭니다.
    # 전부 정상이면 아무 말 없습니다. 점검이 죽어도 비서는 켜져야 하므로 감쌉니다.
    try:
        doctor.run(config, notify=lambda m: print(f"  {m}"))
    except Exception:
        pass

    # 이 대화의 살아 있는 부분. respond()가 여기에 이어 씁니다(웹 화면도 같은 모양을 씁니다).
    state = new_state(config)
    messages = state["messages"]

    while True:
        try:
            # BOM·제로폭 문자가 앞에 붙으면 '/검증' 같은 명령이 인식되지 않습니다.
            # (파일이나 파이프로 입력을 흘려 넣을 때 실제로 생깁니다)
            user = input("\n나 > ").strip().lstrip("﻿​").strip()
        except (EOFError, KeyboardInterrupt):
            user = "exit"
            print()

        # 사용자가 무언가 입력했다는 것은 더 들을 생각이 없다는 뜻입니다.
        # 엔터만 쳐도 말이 멈추므로, 긴 답을 끝까지 듣고 있을 필요가 없습니다.
        tts.stop()

        if not user:
            continue
        if user.lower() in ("exit", "quit", "종료"):
            finish(config, messages)
            return

        # '/읽기' — 답을 소리로 읽어줄지 켜고 끕니다. '/읽기 목록'으로 목소리를 고릅니다.
        if user.startswith("/읽기"):
            rest = user[3:].strip()
            conf = config.setdefault("tts", {})
            if rest.startswith("엔진"):
                # 목소리 엔진 갈아끼우기. 이름 없이 '/읽기 엔진'만 치면 지금 순서를 보여줍니다.
                pick = rest[2:].strip()
                aliases = {"구글": "google", "google": "google", "온라인": "google",
                           "윈도우": "sapi", "sapi": "sapi", "heami": "sapi",
                           "로컬": "melo", "melo": "melo", "멜로": "melo", "오프라인": "melo"}
                if not pick:
                    now = tts.engines(config)
                    print("  지금 순서: " + " → ".join(tts.ENGINE_KO[e] for e in now))
                    print("  바꾸려면: /읽기 엔진 구글   또는   /읽기 엔진 윈도우")
                elif pick in aliases:
                    first = aliases[pick]
                    # 고른 엔진을 맨 앞에 두되 나머지는 뒤에 남깁니다 — 구글이 안 될 때
                    # 조용해지는 것보다 딱딱한 목소리라도 읽어주는 편이 낫습니다.
                    conf["engines"] = [first] + [e for e in tts.ALL_ENGINES if e != first]
                    conf["enabled"] = True
                    save_tts(config)
                    used = tts.engines(config)
                    print(f"  목소리 엔진: {tts.ENGINE_KO[used[0]]}")
                    if used[0] != first:
                        print("  (로컬 전용 모드라 온라인 목소리는 쓰지 않습니다)")
                    tts.speak("네, 이 목소리로 읽어드릴게요.", config)
                else:
                    print(f"  '{pick}'은(는) 모르는 엔진입니다. (구글 / 윈도우)")
                continue
            if rest.startswith("볼륨"):
                # 목소리 크기(0~100). '/읽기 볼륨'만 치면 지금 값을 보여줍니다.
                num = rest[2:].strip().rstrip("%").strip()
                if not num:
                    print(f"  지금 목소리 볼륨: {int(conf.get('volume', 100))} "
                          "(0=무음 ~ 100=원음). 바꾸려면: /읽기 볼륨 60")
                elif num.lstrip("-").isdigit():
                    conf["volume"] = max(0, min(int(num), 100))
                    conf["enabled"] = True
                    save_tts(config)
                    print(f"  목소리 볼륨을 {conf['volume']}(으)로 맞췄습니다."
                          + ("  (원음보다 더 키우려면 윈도우/장치 볼륨을 올리세요)"
                             if conf["volume"] >= 100 else ""))
                    tts.speak("이 크기로 읽어드릴게요.", config)
                else:
                    print("  숫자로 주세요 (0~100). 예: /읽기 볼륨 60")
                continue
            if rest in ("목록", "목소리"):
                found = tts.voices()
                if not found:
                    print("  이 PC에서 음성을 찾지 못했습니다.")
                else:
                    print("  깔려 있는 목소리:")
                    for vname, culture in found:
                        mark = " ←지금" if vname == conf.get("voice") else ""
                        print(f"    - {vname}  ({culture}){mark}")
                    print("  바꾸려면: /읽기 <이름 일부>   (예: /읽기 Heami)")
            elif rest:
                picked, culture = tts.pick_voice(rest)
                if not picked:
                    print(f"  '{rest}'과(와) 맞는 목소리가 없습니다. (/읽기 목록)")
                else:
                    conf["voice"] = picked
                    conf["enabled"] = True
                    save_tts(config)
                    print(f"  목소리를 '{picked}'({culture})(으)로 바꿨습니다. 읽어주기 켜짐.")
                    tts.speak("네, 이제부터 이 목소리로 읽어드릴게요.", config)
            else:
                conf["enabled"] = not conf.get("enabled", False)
                save_tts(config)
                if conf["enabled"]:
                    print("  읽어주기 켜짐 — 말하는 중에 엔터를 치면 멈춥니다.")
                    tts.speak("읽어주기를 켰어요.", config)
                else:
                    print("  읽어주기 꺼짐.")
            continue

        if user.lower() in ("음성", "/v"):
            user = listen_once(config)
            if not user:
                continue
            print(f"나 (음성) > {user}")

        # '/음성모드' — 연속 음성 대화: 말이 끝나면 알아서 답하고, 다 읽으면 다시 듣습니다.
        # '/음성모드 시험'은 마이크 음량을 실시간으로 보여줍니다(문턱값 맞추기용, 전송 없음).
        if user.startswith("/음성모드") or user in ("음성모드", "연속음성"):
            if "시험" in user or "음량" in user:
                talk.meter(notify=print, config=config)
            else:
                print("  " + talk.run(config, state, respond))
                messages = state["messages"]
            continue

        # '/지식갱신' — 클로드가 새로 정리한 노트를 지식 창고로 다시 가져옵니다.
        if user.startswith("/지식"):
            count, where = knowledge.sync()
            if not count:
                print(f"  가져오지 못했습니다: {where}")
            else:
                print(f"  노트 {count}개를 가져왔습니다 → {where}")
                print("  (임베딩 인덱스는 다음 검색 때 다시 만듭니다 — 몇 분 걸릴 수 있습니다)")
            continue

        # '/문서색인' — PC 문서 색인을 지금 다시 만듭니다(평소엔 검색할 때 알아서 갱신됩니다).
        if user.startswith("/문서색인") or user.startswith("/색인"):
            force = "전체" in user or "처음부터" in user
            print("  PC 문서를 훑는 중입니다" + (" (전체 다시 읽기)" if force else "")
                  + " — 처음이면 몇 분 걸릴 수 있습니다...")
            added, total, failed = docsearch.build(config, force=force)
            print(f"  문서 {total}개를 색인했습니다 (새로 읽음 {added}개"
                  + (f", 못 읽음 {failed}개" if failed else "") + ")")
            print("  이제 '작년에 쓴 그 계약서 찾아줘' 처럼 물어보세요.")
            continue

        # '/복습' — 최근 대화를 되읽고, 지적받지 않은 실수에서도 스스로 교훈을 뽑습니다.
        # (평소엔 매일 새벽에 어제치를 알아서 합니다 — 이건 지금 바로 돌아보고 싶을 때)
        if user.startswith("/복습"):
            day = study.last_day(include_today=True)
            if not day:
                print("  복기할 대화 기록이 없습니다.")
                continue
            print(f"  {day} 대화를 되읽는 중...")
            added = study.reflect(config, call_model, day, notify=lambda m: print(m))
            if not added:
                print("  새로 배울 교훈이 없습니다. (없으면 없는 게 정답입니다)")
            continue

        # '/공부 <주제>' — 주제를 스스로 조사해 지식 창고에 노트로 남깁니다.
        # 주제를 안 주면 최근 대화에서 얕게 답했던 주제를 스스로 고릅니다.
        if user.startswith("/공부"):
            topic = user[3:].strip()
            if not topic:
                day = study.last_day(include_today=True)
                topic, why = study.pick_topic(config, call_model, day) if day else ("", "")
                if not topic:
                    print("  공부할 주제를 못 골랐습니다. 직접 주세요: /공부 <주제>")
                    continue
                print(f"  스스로 고른 주제: {topic}" + (f" ({why})" if why else ""))
            path = study.study(config, call_model, topic, notify=lambda m: print(m))
            if path:
                print("  이제 이 주제를 물으면 공부한 노트로 답합니다.")
            continue

        # '/점검' — 제 몸(목소리 서버·기억 검색·알림·구글)을 점검하고 고칠 수 있는 건 고칩니다.
        if user.startswith("/점검"):
            doctor.run(config, notify=lambda m: print(f"  {m}"), verbose=True)
            continue

        # '/상태' — 살림 현황판. '/점검'이 몸이라면 이건 가계부입니다:
        # 두뇌별 오늘 사용횟수·쿨다운, 기억·지식·교훈 수, 새벽 일과가 언제 돌았나.
        if user.startswith("/상태"):
            print(status.report(config, cooldown=_cooldown))
            continue

        # '/감시 <무엇이 되면>' — 화면을 지켜보다 이루어지면 소리+창으로 알립니다
        # (유니티 빌드·다운로드처럼 화면으로만 알 수 있는 일의 끝을 대신 기다립니다).
        if user.startswith("/감시"):
            rest = user[3:].strip()
            if rest in ("", "상태"):
                print("  " + watch.status_text().replace("\n", "\n  "))
            elif rest in ("중지", "취소", "그만"):
                print("  " + watch.stop())
            else:
                print("  " + watch.start(config, rest).replace("\n", "\n  "))
            continue

        # '/유튜브 <주소>' — 영상 자막을 받아 요약하고 지식 창고에 넣습니다.
        # 말로 시켜도 됩니다: 주소 + '요약/정리/공부' 낱말이 함께 있으면 알아듣습니다.
        yt = user[4:].strip() if user.startswith("/유튜브") else youtube.wants(user)
        if user.startswith("/유튜브") or yt:
            if not yt:
                print("  사용법: /유튜브 <영상 주소>   (자막을 요약해 지식 창고에 넣습니다)")
                continue
            try:
                path, note = youtube.summarize(config, call_model, yt,
                                               notify=lambda m: print(f"  {m}"))
            except Exception as e:
                print(f"  요약하지 못했습니다: {e}")
                continue
            print(f"\n{name} (유튜브 요약) > {note}")
            print(f"\n  → {os.path.basename(path)} — 이제 이 영상 내용을 물어보면 찾아서 답합니다.")
            # 요약을 대화에도 남깁니다 — "방금 그 영상에서 ~는 뭐래?" 같은 후속 질문이 되게.
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": note[:2000]})
            session.log_turn("나", user)
            session.log_turn(name, note)
            tts.speak("영상 요약을 마쳤어요. 자세한 내용은 화면을 보세요.", config)
            continue

        # '/기억정리' — 쌓인 기억을 지금 훑어 같은 주제는 합치고 지난 일정은 지웁니다.
        # (평소엔 일주일에 한 번 새벽에 알아서 합니다 — 이건 미리 보고 골라서 적용하고 싶을 때)
        if user.startswith("/기억정리"):
            consolidate.run_interactive(config, call_model)
            continue

        # '/벤치' — 두뇌들을 직접 시험해 순위를 다시 매기고 config.json을 고쳐 씁니다.
        if user.startswith("/벤치") or user.lower().startswith("/bench"):
            run_bench(config)
            continue

        # '/교훈' — 실수 노트를 보거나 지웁니다. 사람이 직접 적어 넣을 수도 있습니다.
        if user.startswith("/교훈"):
            rest = user[3:].strip()
            if rest.startswith("삭제"):
                needle = rest[2:].strip()
                gone = lessons.remove(needle) if needle else []
                print("  지웠습니다:\n" + "\n".join("    - " + g for g in gone) if gone
                      else f"  '{needle}'과(와) 일치하는 교훈이 없습니다.")
            else:
                items = lessons.load()
                if not items:
                    print("  아직 적힌 교훈이 없습니다. (사용자가 '그거 틀렸어'라고 지적하면 적힙니다)")
                else:
                    print(f"  실수 노트 {len(items)}개:")
                    for item in items:
                        print(f"    - {item}")
                    print("  지우려면: /교훈 삭제 <교훈에 든 말>")
            continue

        # '/보기 <경로> <질문>' — 그림을 보여주며 묻습니다. (경로만 적어도 자동으로 알아봅니다)
        if user.startswith("/보기"):
            user = user[3:].strip()
            if not user:
                print("  사용법: /보기 <이미지 경로> <질문>   (예: /보기 에러.png 이거 무슨 오류야?)")
                continue

        # '/브리핑' — 아침 브리핑을 지금 받아봅니다(정한 시각에는 알림 일꾼이 알아서 합니다).
        if user.startswith("/브리핑"):
            try:
                text = daily.briefing(config, notify=lambda m: print(f"  {m}"))
            except Exception as e:
                print(f"  브리핑을 만들지 못했습니다: {type(e).__name__}: {e}")
                continue
            print(f"\n{name} (브리핑) > {text}")
            session.log_turn(name, text)
            tts.speak(text, config)
            continue

        # '/화면 <질문>' — 지금 모니터에 떠 있는 것을 찍어서 보여주며 묻습니다.
        # (그냥 "지금 화면 좀 봐줘"라고 해도 respond()가 알아서 찍습니다. 이건 확실하게 찍고 싶을 때)
        screen_now = False
        if user.startswith("/화면"):
            user = user[3:].strip() or "이 화면을 설명해줘."
            screen_now = True

        # '/검증 질문' — 두 두뇌에게 따로 묻고 답을 대조합니다(중요한 질문용).
        if user.startswith("/검증") or user.lower().startswith("/x"):
            question = user.split(maxsplit=1)[1] if len(user.split(maxsplit=1)) > 1 else ""
            if not question:
                print("  사용법: /검증 <질문>   (두 모델에게 따로 묻고 답을 대조합니다)")
                continue
            session.log_turn("나", question)
            answer = crosscheck(config, question)
            if answer:
                messages.append({"role": "user", "content": question})
                messages.append({"role": "assistant", "content": answer})
                print(f"\n{name} (교차검증) > {answer}")
                session.log_turn(name, answer)
                tts.speak(answer, config)
                continue
            user = question   # 교차검증이 불가능하면 평소대로 진행

        # "빌드 끝나면 알려줘" — 명령이 아니라 말로 시켜도 화면 지켜보기를 제안합니다.
        # 오발동하면 한 시간짜리 감시가 돌므로 자연어 트리거는 시작 전에 한 번 묻습니다.
        if watch.wants(user):
            picked = input("  화면을 지켜보다 알려드릴까요? [y/N] ").strip().lower()
            if picked in ("y", "yes", "ㅇ", "네", "응"):
                print("  " + watch.start(config, user).replace("\n", "\n  "))
                continue
            # 아니라면 평소처럼 대화로 흘려보냅니다.

        try:
            answer, used = respond(config, state, user, notify=lambda m: print(f"    {m}"),
                                   force_screen=screen_now)
        except ImageUnreadable as e:
            print(f"  이미지를 읽지 못했습니다: {e}")
            continue
        except AllModelsFailed as e:
            print("\n[모든 모델이 실패했습니다]")
            print(str(e))
            print("\n  → 인터넷이 끊겼다면 Ollama만 있으면 됩니다: ollama serve")
            continue

        print(f"\n{name} ({used}) > {answer}")
        tts.speak(answer, config)     # 기다리지 않습니다 — 읽는 동안에도 바로 다음 질문을 할 수 있습니다
        messages = state["messages"]


def run_bench(config):
    """
    두뇌들을 실제로 시험해 순위를 다시 매깁니다.

    무료 모델판은 계속 바뀝니다 — 어제 빠르던 게 오늘 한도에 걸리고, 서비스가 막히기도 합니다.
    그때마다 사람이 config를 손보는 대신 루시가 스스로 재보고 정하게 합니다.
    """
    print("\n  두뇌 벤치를 시작합니다. 모델마다 4가지를 실제로 시킵니다 —")
    print("  검색·도구2개·추론(순위) + 그림을 볼 수 있는지(눈 명단 갱신).")
    print("  모델 수에 따라 2~6분 걸립니다.\n")

    results = bench.run(sys.modules[__name__], config)   # 벤치가 이 모듈의 루프를 그대로 씁니다
    if not results:
        print("  시험할 두뇌가 없습니다(키를 확인하세요).")
        return

    ranked = bench.rank(results)
    bench.report(ranked)

    # 한도 초과처럼 '오늘만 실패'인 경우가 있어, 결과를 자동 반영하기 전에 사람에게 묻습니다.
    if input("\n  이 순위대로 config.json을 고칠까요? [y/N] ").strip().lower() != "y":
        print("  그대로 두었습니다.")
        return

    order, deep, eye_changes = bench.apply(ranked, config)
    print("\n  새 순서로 저장했습니다 (원본은 config.json.bak):")
    for i, label in enumerate(order, 1):
        mark = "  ← 어려운 질문 담당(deep)" if label == deep else ""
        print(f"    {i}. {label}{mark}")
    if eye_changes:
        print("\n  눈(그림) 명단이 실측과 달라서 고쳤습니다:")
        for label, eye in eye_changes:
            print(f"    {label} → {'눈 있음(그림 질문에 씁니다)' if eye else '눈 없음(그림에서 뺍니다)'}")
    print("\n  다음 실행부터 적용됩니다. (지금 대화는 기존 순서로 계속됩니다)")


JUDGE_PROMPT = """서로 다른 두 AI가 같은 질문에 답했다. 최종 답을 정리하라.

[질문]
{question}

[A의 답 — {a_label}]
{a}

[B의 답 — {b_label}]
{b}

두 답이 일치하면 그대로 하나의 답으로 정리하라.
어긋나는 부분이 있으면 그 부분을 분명히 짚고, 어느 쪽이 맞는지 근거를 들어 판단하라.
판단할 수 없으면 "두 모델의 답이 엇갈립니다"라고 솔직히 밝히고 양쪽을 다 보여줘라.
답변만 출력하라."""


def crosscheck(config, question):
    """
    중요한 질문을 서로 다른 두 두뇌에게 따로 묻고 대조합니다.

    모델 '합치기'(가중치 병합)는 부모보다 똑똑해지지 않지만,
    각자 답하게 한 뒤 대조하는 건 실제로 오류를 잡아냅니다. 둘 다 무료라 비용도 0입니다.
    대신 느리고 무료 한도를 두 배로 씁니다 — 그래서 '/검증'을 붙일 때만 작동합니다.
    """
    models = [m for m in config["models"] if not _resting(m["label"])]
    if len(models) < 2:
        print("    [교차검증] 쓸 수 있는 두뇌가 하나뿐이라 일반 답변으로 진행합니다")
        return None

    # 깊은 두뇌 하나 + 빠른 두뇌 하나로 시작하되, 한쪽이 죽으면 남은 모델로 채웁니다.
    picks = [m for m in models if m.get("deep")][:1] + [m for m in models if not m.get("deep")][:1]
    picks += [m for m in models if m not in picks]

    answers = []
    for entry in picks:
        if len(answers) >= 2:
            break
        print(f"    [교차검증] {entry['label']}에게 묻는 중...")
        msgs = [{"role": "system", "content": build_system_prompt(config)},
                {"role": "user", "content": question}]
        try:
            answer, _used = run_turn(config, msgs, order=[entry])
        except AllModelsFailed:
            continue
        if answer:
            answers.append((entry["label"], answer))

    if len(answers) < 2:
        print("    [교차검증] 두 번째 두뇌를 못 구해 단독 답변으로 진행합니다")
        return answers[0][1] if answers else None

    print("    [교차검증] 두 답을 대조하는 중...")
    prompt = JUDGE_PROMPT.format(
        question=question,
        a_label=answers[0][0], a=answers[0][1],
        b_label=answers[1][0], b=answers[1][1],
    )
    try:
        message, _used, _entry = call_model(config, [{"role": "user", "content": prompt}], use_tools=False)
        return message.get("content") or answers[0][1]
    except AllModelsFailed:
        return answers[0][1]


def listen_once(config):
    """마이크로 듣고 받아쓴 글자를 돌려줍니다. 문제가 생겨도 비서는 계속 굴러갑니다."""
    cfg = config.get("voice", {})
    if not cfg.get("enabled", True):
        return ""

    path = os.path.join(BASE_DIR, cfg.get("key_file", "keys/groq.txt"))
    if not os.path.exists(path):
        print("  음성 인식에는 Groq 키가 필요합니다 (keys/groq.txt).")
        return ""
    with open(path, "r", encoding="utf-8-sig") as f:
        key = f.readline().strip()

    try:
        text = voice.listen(
            key,
            model=cfg.get("model", "whisper-large-v3"),
            language=cfg.get("language", "ko"),
        )
    except Exception as e:
        print(f"  음성 인식 실패: {type(e).__name__} — {e}")
        return ""

    if not text:
        print("  아무 소리도 들리지 않았습니다.")
    return text


def finish(config, messages):
    """종료할 때 이번 대화에서 기억할 만한 것을 골라 저장합니다."""
    print("\n대화를 정리하는 중...")
    try:
        saved = session.summarize_and_save(messages, config, call_model)
    except Exception as e:
        print(f"  (정리 실패: {type(e).__name__} — 대화 기록은 memory/history 에 남아 있습니다)")
        saved = []

    if saved:
        print("  새로 기억한 것:")
        for fact in saved:
            print(f"    · {fact}")
    else:
        print("  새로 기억할 만한 것은 없었습니다.")

    session.auto_git_sync("push")
    print("안녕히 계세요.")


if __name__ == "__main__":
    sys.exit(main())
