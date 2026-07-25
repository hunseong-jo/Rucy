# -*- coding: utf-8 -*-
"""
놀고 있는 두뇌 생사 확인 — 폴백 사슬 **아래쪽**에서 조용히 죽은 두뇌를 찾아냅니다.

조용한 고장 경보(status.silent_faults)는 '불려본 두뇌'만 봅니다. 그런데 폴백 사슬은
위가 건강하면 아래를 부르지 않습니다 — 다섯 번째 두뇌가 공급자에게서 폐기돼도 호출이
0회라 경보 문턱(4회)에 영영 닿지 않습니다. **위가 건강할수록 더 안 보이고**, 드러나는
순간은 위가 전부 죽었을 때, 즉 예비가 가장 필요한 때입니다.
(2026-07-23 실측: Groq이 qwen3-32b를 폐기해 404를 돌려주는데도 순위 5위에 멀쩡히
남아 있었고, 경보는 '만성 고장 없음'이라 답했습니다.)

그래서 여기서는 **안 불린 두뇌만 골라** 짧은 인사를 보내 생사만 확인합니다.

원칙 넷:
  1. **자주 쓰이는 두뇌는 건드리지 않습니다** — 이미 계측이 보고 있고, 무료 한도는 아낍니다.
  2. **죽음과 못 잰 것을 구분합니다** — 404·폐기는 죽음이지만, 429(한도)는 내일이면
     풀리고 타임아웃은 느린 것이지 죽은 게 아닙니다. 못 잰 것을 '죽었다'고 적으면
     멀쩡한 두뇌를 버리게 됩니다(벤치와 눈 시험이 같은 자리에서 배운 원칙).
  3. **고치지 않습니다** — 죽은 두뇌를 코드가 말없이 지우면 안 됩니다(모델 교체는
     사람과 상의할 일). doctor와 같은 방침입니다: 알리기만 합니다.
  4. **읽기와 재기를 나눕니다** — 실제 호출은 daily가 주 1회 새벽에 하고, doctor는
     적어둔 결과를 **읽기만** 합니다. 안 그러면 루시를 켤 때마다 네트워크를 두드려
     시작이 느려집니다(브리핑이 유니티를 직접 켜지 않는 것과 같은 이유).
"""
import datetime
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "memory", "brain_probe.json")

# 계측·사용량에 남을 임시 라벨의 접두사. 진짜 두뇌 통계를 더럽히지 않으려고 이름을
# 바꿔 부릅니다(벤치가 '시험 …'을 쓰는 것과 같은 방식). status가 이 접두사를 걸러냅니다.
PROBE_PREFIX = "점검 "

# 판정: 이 두 가지만 경보를 울립니다 — 기다린다고 낫지 않고, 사람이 손대야 풀립니다.
ALARM_STATES = ("dead", "authkey")

STATE_KO = {
    "alive": "살아있음",
    "dead": "죽음(공급자가 내림)",
    "authkey": "키 거부",
    "quota": "한도 — 판단 보류",
    "slow": "응답 없음(느림) — 판단 보류",
    "unknown": "못 쟀음 — 판단 보류",
}


# ── 적어둔 결과 ───────────────────────────────────────────────────
def load():
    try:
        with open(STATE_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)          # 쓰다 죽어도 원본이 남게(daily._mark와 같은 방식)


# ── 누구를 찌를 것인가 ────────────────────────────────────────────
def idle_entries(config, days=None, min_attempts=None):
    """최근 며칠 동안 거의 안 불린 두뇌들 — 계측이 못 보는 사각지대가 정확히 여기입니다.

    로컬 최후의 보루는 뺍니다: 인터넷이 아니라 포트라 doctor가 이미 보고 있고,
    한 번 부르면 몇 분이 걸립니다."""
    import status
    j = dict(status._JUDGE, **(config.get("metrics", {}) or {}))
    days = days or j["days"]
    floor = j["alert_min"] if min_attempts is None else min_attempts

    stats = status._recent(days)
    out = []
    for entry in config.get("models", []):
        if entry.get("key_file") is None:
            continue                     # 로컬(최후의 보루)은 대상 아님
        seen = stats.get(entry.get("label", ""), {}).get("attempts", 0)
        if seen < floor:
            out.append(entry)
    return out


# ── 한 두뇌 찔러보기 ──────────────────────────────────────────────
def _classify(err_text):
    """실패 사유 글에서 판정을 뽑습니다.

    ⚠️여기가 이 파일에서 제일 조심할 곳입니다 — 애매하면 전부 '판단 보류'로 보냅니다.
    '죽었다'는 판정만이 사람을 움직이게 하므로, 틀리면 멀쩡한 두뇌를 버리게 됩니다."""
    t = (err_text or "")
    low = t.lower()
    if "한도" in t or "429" in t or "413" in t or "쉬는 중" in t:
        return "quota"
    if "키가 거부" in t or "401" in t or "403" in t:
        return "authkey"
    # 공급자가 모델을 내린 신호. 404(없음)와 400+decommissioned(폐기)가 실제로 관측됩니다.
    if ("http 404" in low or "does not exist" in low or "model_not_found" in low
            or "decommissioned" in low or "has been retired" in low):
        return "dead"
    if "연결 실패" in t or "timeout" in low:
        return "slow"
    return "unknown"


def _tidy(text, shadow_label):
    """실패 글을 사람이 읽을 한 줄로. 원본은 '· 점검 아무개: HTTP 404 {"error":{...}}'처럼
    껍데기가 겹겹이라, 그대로 두면 경보 한 줄이 화면을 다 먹습니다."""
    t = " ".join((text or "").split())
    t = t.lstrip("· ").strip()
    if t.startswith(shadow_label + ":"):
        t = t[len(shadow_label) + 1:].strip()
    # 공급자가 준 진짜 사유만 뽑아냅니다(없으면 원문 그대로).
    brace = t.find("{")
    if brace >= 0:
        try:
            err = json.loads(t[brace:]).get("error") or {}
            msg = err.get("message") or err.get("detail")
            if msg:
                return f"{t[:brace].strip()} {msg}".strip()
        except ValueError:
            pass
    return t[:160]


def probe_one(agent, config, entry, timeout=45):
    """두뇌 하나에 짧은 인사를 보냅니다. 돌려주기: (판정, 사유 한 줄).

    라벨을 바꿔 부르는 이유: 이 호출이 진짜 두뇌의 평균 응답시간·실패율에 섞이면
    계측이 오염돼 자동 후순위가 엉뚱하게 움직입니다. 또 여기서 429를 맞아도
    **진짜 두뇌가 30분 쉬러 가지 않습니다**(쿨다운도 라벨을 따라가므로)."""
    real = entry.get("label", "?")

    # 이미 한도로 쉬는 중이면 찌르지 않습니다 — 어차피 한도라 판정이 안 나오고,
    # 쓸데없이 한 번 더 두드리는 셈입니다.
    try:
        if agent._resting(real):
            return "quota", "한도로 쉬는 중이라 건너뜀"
    except Exception:
        pass

    shadow = dict(entry)
    shadow["label"] = PROBE_PREFIX + real
    shadow["timeout"] = timeout
    shadow.pop("deep", None)             # 생사만 보면 되므로 깊게 생각시키지 않습니다

    try:
        answer, _label, _e = agent.call_model(
            config, [{"role": "user", "content": "ok"}],
            use_tools=False, order=[shadow], deep_think=False)
    except Exception as e:
        text = f"{e}"
        return _classify(text), _tidy(text, shadow["label"])

    body = (answer.get("content") or "").strip() if isinstance(answer, dict) else str(answer)
    # 답이 비어도 200이면 살아는 있습니다(빈 답은 눈 시험에서 따로 다루는 문제).
    return "alive", (body[:60] or "(빈 답이지만 응답함)")


# ── 새벽에 한 바퀴 ────────────────────────────────────────────────
def run(config, notify=print, timeout=None, pause=2.0):
    """안 불린 두뇌들을 차례로 찔러 결과를 적습니다. 돌려주기: {label: {state, detail}}"""
    import time
    import agent

    conf = (config.get("daily", {}) or {}).get("brain_probe", {}) or {}
    timeout = timeout or conf.get("timeout", 45)

    targets = idle_entries(config)
    if not targets:
        notify("  두뇌 생사 확인: 최근에 다들 한 번씩은 불렸습니다 — 찌를 대상 없음")
        # 대상이 없다는 것도 '오늘 봤다'는 기록입니다(빈 결과로 덮어쓰지는 않습니다).
        data = load()
        data["at"] = datetime.datetime.now().isoformat(timespec="seconds")
        _save(data)
        return {}

    notify(f"  두뇌 생사 확인: 최근 안 불린 {len(targets)}개를 찔러봅니다")
    results = {}
    for entry in targets:
        label = entry.get("label", "?")
        state, detail = probe_one(agent, config, entry, timeout)
        results[label] = {"state": state, "detail": detail,
                          "at": datetime.date.today().isoformat()}
        mark = "⚠" if state in ALARM_STATES else " "
        notify(f"   {mark} {label}: {STATE_KO.get(state, state)}")
        time.sleep(pause)                # 연달아 두드려 스스로 분당 한도를 터뜨리지 않게

    data = load()
    data["at"] = datetime.datetime.now().isoformat(timespec="seconds")
    brains = data.setdefault("brains", {})
    brains.update(results)               # 안 찌른 두뇌의 옛 기록은 남겨 둡니다
    _save(data)
    return results


# ── doctor가 읽는 문 ──────────────────────────────────────────────
def alarm_lines(config, max_age_days=30):
    """죽은 두뇌 경보 — 네트워크를 쓰지 않고 적어둔 것만 읽습니다.

    config에 없는 두뇌(이미 사람이 교체한 뒤)는 건너뜁니다 — 고쳐 놓은 문제를
    계속 일러바치면 다음부터 아무도 안 봅니다."""
    data = load()
    labels = {m.get("label") for m in config.get("models", [])}
    today = datetime.date.today()
    out = []
    for label, r in (data.get("brains") or {}).items():
        if label not in labels or r.get("state") not in ALARM_STATES:
            continue
        try:
            age = (today - datetime.date.fromisoformat(str(r.get("at")))).days
        except (TypeError, ValueError):
            age = 0
        if age > max_age_days:
            continue                     # 너무 오래된 기록은 판단 보류(곧 다시 잽니다)
        out.append(f"{label}: {STATE_KO.get(r['state'], r['state'])}"
                   f" — {r.get('detail', '')[:90]} ({r.get('at')} 확인)")
    return out


def status_line(config):
    """'/점검'의 정상 줄 — 마지막으로 언제 봤고 죽은 게 있었는지."""
    data = load()
    at = str(data.get("at", ""))[:10]
    if not at:
        return "두뇌 생사 확인: 아직 한 번도 안 함 (새벽 일과에서 곧 봅니다)"
    n = len(data.get("brains") or {})
    return f"두뇌 생사 확인: 죽은 두뇌 없음 (안 불린 {n}개를 {at}에 확인)"


def self_diagnosis_health_check(config):
    """자동화 자가진단 헬스케어 커버리지 — 두뇌, DB, 인덱스, 서브시스템 상태를 한 번에 검증합니다."""
    import lessons
    report = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "brain_alarms": alarm_lines(config),
        "db_health": "ok",
        "lessons_index_ok": bool(lessons._load_index() is not None),
    }
    try:
        import lucy_db
        db_path = os.path.join(BASE_DIR, "memory", "lucy.db")
        notes = lucy_db.get_notes(db_path=db_path)
        report["db_notes_count"] = len(notes)
    except Exception as e:
        report["db_health"] = f"error: {e}"
    return report
