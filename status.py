# -*- coding: utf-8 -*-
"""
'/상태' — 루시의 가계부.

'/점검'(doctor.py)이 몸(서버·연동이 살아 있나)을 본다면, 이건 살림살이를 봅니다:
두뇌별로 오늘 몇 번 썼고 지금 쉬는 중인지, 기억·지식·교훈이 얼마나 쌓였는지,
새벽 일과(동기화·점검·거두기·정리·공부)가 언제 마지막으로 돌았는지.

"요즘 어느 두뇌로 사는가"는 여기서만 보입니다 — 폴백은 조용히 일어나므로,
주력이 한도에 자주 걸리면 사용자는 모른 채 예비 두뇌와 대화하고 있을 수 있습니다.

사용 횟수는 memory/usage.json에 날짜별로 셉니다. 터미널·웹·배경 알림이 전부
agent.call_model을 지나므로 한 군데(record)만 세면 빠지는 곳이 없습니다.
"""
import datetime
import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USAGE_FILE = os.path.join(BASE_DIR, "memory", "usage.json")
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
DAILY_FILE = os.path.join(BASE_DIR, "memory", "daily.json")
TODO_FILE = os.path.join(BASE_DIR, "memory", "todo.md")
HISTORY_DIR = os.path.join(BASE_DIR, "memory", "history")


# ── 사용 횟수 세기 ────────────────────────────────────────────────
def _usage():
    try:
        with open(USAGE_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record(label):
    """모델 호출 성공을 하나 셉니다. 세는 일이 대화를 죽이면 안 되므로 무슨 일이 있어도 조용합니다."""
    try:
        data = _usage()
        today = datetime.date.today().isoformat()
        day = data.setdefault(today, {})
        day[label] = int(day.get(label, 0)) + 1
        cutoff = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
        data = {d: v for d, v in data.items() if d >= cutoff}   # 2주 지난 날은 지웁니다
        tmp = USAGE_FILE + ".tmp"
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, USAGE_FILE)
    except Exception:
        pass


# ── 계측(관측성): 두뇌별 응답시간·실패·폴백 ──────────────────────
# record(label)가 '몇 번 썼나'만 센다면, 여기는 '얼마나 빠른가·얼마나 자주
# 실패하나·주력이 못 답해 예비로 내려간 적이 있나'를 봅니다. "느려/이상해"에
# 근거가 없던 것을 메꾸는 자료입니다. usage.json과 똑같이 14일만 보관합니다.
METRICS_FILE = os.path.join(BASE_DIR, "memory", "metrics.json")

# 실패 종류를 짧은 한글로 (report에서 보여줄 때 씀)
FAIL_KO = {"quota": "한도", "too_big": "토큰초과", "too_long": "길이초과",
           "authkey": "키거부", "http": "HTTP", "conn": "끊김", "noanswer": "빈답"}


def _metrics():
    try:
        with open(METRICS_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_metrics(data):
    cutoff = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    data = {d: v for d, v in data.items() if d >= cutoff}
    tmp = METRICS_FILE + ".tmp"
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, METRICS_FILE)


def _today_brain(data, label):
    today = datetime.date.today().isoformat()
    day = data.setdefault(today, {})
    return day.setdefault(label, {"ok": 0, "fb": 0, "s_sum": 0.0,
                                  "s_n": 0, "s_max": 0.0, "fail": {}})


def record_call(label, seconds, position=0):
    """모델이 답한 시간(초)을 잽니다. position>0이면 폴백 — 주력이 못 답해
    예비 두뇌로 내려온 답입니다. 세는 일이 대화를 죽이면 안 되니 조용합니다."""
    try:
        data = _metrics()
        b = _today_brain(data, label)
        b["ok"] = int(b.get("ok", 0)) + 1
        if position > 0:
            b["fb"] = int(b.get("fb", 0)) + 1
        b["s_sum"] = float(b.get("s_sum", 0.0)) + float(seconds)
        b["s_n"] = int(b.get("s_n", 0)) + 1
        b["s_max"] = max(float(b.get("s_max", 0.0)), float(seconds))
        _save_metrics(data)
    except Exception:
        pass


def record_fail(label, kind):
    """모델 호출 실패를 종류별로 셉니다(quota·too_long·conn 등). 조용합니다."""
    try:
        data = _metrics()
        b = _today_brain(data, label)
        fails = b.setdefault("fail", {})
        fails[kind] = int(fails.get(kind, 0)) + 1
        _save_metrics(data)
    except Exception:
        pass


# ── 👁 눈 2개 자가검수: 짝별 합의/엇갈림 세기 (세션68) ────────────
# 눈 두 개(믿는 눈 + 못 믿는 눈)에게 물어 판정이 엇갈리면 🙋 사람에게 넘깁니다
# (tools._eye_look / _eye_look_many). 그 엇갈림이 얼마나 잦은지 여태 아무도 세지 않아,
# "🙋가 잦으면 짝을 조절"할 근거가 없었습니다(세션64가 남긴 관찰 항목). 여기서 **짝별로**
# 합의/엇갈림을 셉니다. 엇갈림 절대수만 보면 검수를 많이 한 날 무조건 커지므로, 합의도 같이
# 세어 **비율**을 봅니다. usage·metrics와 똑같이 14일만 보관합니다.
CONSENSUS_FILE = os.path.join(BASE_DIR, "memory", "eye_consensus.json")


def _consensus():
    try:
        with open(CONSENSUS_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record_panel(labels, agreed):
    """눈 여러 개의 자가검수 한 건을 **조합별로** 셉니다. agreed=False면 🙋 사람호출.

    라벨은 정렬해 순서를 없앱니다(누구를 먼저 물었든 같은 조합). 2026-07-23에 검수가
    2개 합의제에서 **3개 다수결**로 바뀌면서 짝이 아니라 조합을 세게 일반화했습니다 —
    옛 이름 record_consensus는 이 함수의 2개짜리 입구로 남겨 뒀습니다.
    세는 일이 검수를 죽이면 안 되니 무슨 일이 있어도 조용합니다."""
    try:
        pair = " | ".join(sorted(str(l or "?") for l in labels)) or "?"
        data = _consensus()
        today = datetime.date.today().isoformat()
        day = data.setdefault(today, {})
        c = day.setdefault(pair, {"agree": 0, "split": 0})
        c["split" if not agreed else "agree"] += 1
        cutoff = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
        data = {d: v for d, v in data.items() if d >= cutoff}
        tmp = CONSENSUS_FILE + ".tmp"
        os.makedirs(os.path.dirname(CONSENSUS_FILE), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONSENSUS_FILE)
    except Exception:
        pass


def record_consensus(label_a, label_b, agreed):
    """(옛 이름) 눈 2개짜리 record_panel — 바깥에서 부르던 곳들을 위해 남겨 둡니다."""
    record_panel([label_a, label_b], agreed)


def consensus_lines(config=None, days=7, hint_min=8, hint_rate=0.4):
    """'/상태'용 — 최근 며칠 눈 자가검수의 짝별 합의/엇갈림과 🙋사람호출 빈도.
    표본이 충분한데(hint_min건 이상) 엇갈림 비율이 높으면(hint_rate 이상) 짝을
    손보라고 귀띔합니다 — 검수를 거의 안 한 날 1건 엇갈렸다고 호들갑 떨지 않도록."""
    data = _consensus()
    if not data:
        return []
    today = datetime.date.today()
    keep = {(today - datetime.timedelta(days=d)).isoformat() for d in range(days)}
    agg = {}
    for day, pairs in data.items():
        if day not in keep:
            continue
        for pair, c in (pairs or {}).items():
            a = agg.setdefault(pair, {"agree": 0, "split": 0})
            a["agree"] += int(c.get("agree", 0))
            a["split"] += int(c.get("split", 0))
    if not agg:
        return []
    lines = ["", f"[눈 자가검수] — 최근 {days}일 눈 조합별 합의/엇갈림"
                 " (엇갈림=과반 없음=🙋 사람 확인 요청)"]
    hint = False
    for pair, c in sorted(agg.items(), key=lambda x: -(x[1]["agree"] + x[1]["split"])):
        n = c["agree"] + c["split"]
        rate = c["split"] / n if n else 0.0
        flag = ""
        if n >= hint_min and rate >= hint_rate:
            flag = "  ⚠ 엇갈림이 잦습니다 — 눈 조합 조절 검토"
            hint = True
        lines.append(f"  {pair}: {n}건 중 🙋엇갈림 {c['split']} ({rate * 100:.0f}%){flag}")
    if hint:
        lines.append("    · 판정단은 **믿음 등급 눈 vision.eyes개**(기본 3)이고 과반이 없으면"
                     " 사람에게 올라옵니다. 엇갈림이 잦으면 '/도구 eye_trust'로 신뢰도를 다시"
                     " 재보세요 — 강등된 눈은 자동으로 판정권을 잃습니다.")
    return lines


# ── 계측을 실제로 쓰기: 자동 후순위 + 조용한 고장 경보 ────────────
# 여태 metrics.json은 쌓기만 하고 아무도 안 읽었습니다(순위는 여전히 손으로 정한 config).
# 여기서 두 가지를 합니다:
#   ① 자동 후순위 — 만성적으로 실패하거나 유독 느린 두뇌를 **이번 실행 동안만** 뒤로 미룹니다.
#      ⚠️config는 절대 안 고칩니다(사람이 정한 순위를 조용히 덮어쓰면 안 됨). 왜 밀렸는지는
#      '/상태'에 그대로 보입니다.
#   ② 조용한 고장 경보 — 특정 두뇌만 계속 죽는데 폴백 사슬이 매번 받아내서 사람이 모르는 상태.
# 판단은 **보수적으로**만 합니다. 계측은 하루 몇십 번짜리 표본이라, 과감하게 굴면 우연히
# 한두 번 실패한 주력을 밀어내고 오히려 느려집니다.
_JUDGE = {"days": 3,            # 며칠치를 보나
          "min_attempts": 6,    # 이만큼 불려본 두뇌만 판단(표본 부족은 판단 안 함)
          "fail_rate": 0.5,     # 절반 넘게 실패하면 만성 고장
          "slow_factor": 3.0,   # 다른 두뇌 중앙값의 3배 넘게 느리면 만성 지연
          "slow_floor": 15.0,   # 그래도 15초는 넘어야 '느리다'고 함
          "alert_rate": 0.6,    # 조용한 고장 경보 문턱(후순위보다 엄격)
          "alert_min": 4}


def _recent(days=3):
    """최근 며칠치 계측을 두뇌별로 합칩니다. label -> {ok, fails, attempts, rate, avg, fb}."""
    data = _metrics()
    today = datetime.date.today()
    keep = {(today - datetime.timedelta(days=d)).isoformat() for d in range(days)}
    out = {}
    for day, brains in data.items():
        if day not in keep:
            continue
        for label, b in brains.items():
            r = out.setdefault(label, {"ok": 0, "fails": 0, "s_sum": 0.0, "s_n": 0,
                                       "fb": 0, "kinds": {}})
            r["ok"] += int(b.get("ok", 0))
            r["fb"] += int(b.get("fb", 0))
            r["s_sum"] += float(b.get("s_sum", 0.0))
            r["s_n"] += int(b.get("s_n", 0))
            for k, v in (b.get("fail") or {}).items():
                r["kinds"][k] = r["kinds"].get(k, 0) + int(v)
                r["fails"] += int(v)
    for r in out.values():
        r["attempts"] = r["ok"] + r["fails"]
        r["rate"] = (r["fails"] / r["attempts"]) if r["attempts"] else 0.0
        r["avg"] = (r["s_sum"] / r["s_n"]) if r["s_n"] else 0.0
    return out


def judge(config, days=None):
    """두뇌별 판정 — label -> 이유 문자열(뒤로 미룰 두뇌만). 없으면 빈 dict.
    ⚠️'시험 …' 같은 임시 라벨(벤치 프로브)은 실제 두뇌가 아니라 제외합니다."""
    j = dict(_JUDGE, **(config.get("metrics", {}) or {}))
    stats = _recent(days or j["days"])
    labels = [m["label"] for m in config.get("models", [])]
    stats = {k: v for k, v in stats.items() if k in labels}

    # '느리다'는 절대 초가 아니라 **다른 두뇌들과 견줘** 판단합니다(그날 인터넷이 느릴 수도).
    avgs = sorted(v["avg"] for v in stats.values() if v["s_n"] >= 5 and v["avg"] > 0)
    median = avgs[len(avgs) // 2] if avgs else 0.0

    out = {}
    for label, v in stats.items():
        if v["attempts"] < j["min_attempts"]:
            continue                      # 표본이 적으면 아무 판단도 안 합니다
        if v["rate"] >= j["fail_rate"]:
            kinds = "·".join(f"{FAIL_KO.get(k, k)} {n}" for k, n in v["kinds"].items())
            out[label] = f"최근 {j['days']}일 실패율 {v['rate']*100:.0f}% ({kinds})"
        elif (median and v["s_n"] >= 5 and v["avg"] >= max(j["slow_floor"],
                                                          median * j["slow_factor"])):
            out[label] = f"최근 {j['days']}일 평균 {v['avg']:.0f}초 (다른 두뇌 중앙값 {median:.0f}초)"
    return out


_RANK_CACHE = {"at": 0.0, "bad": {}}


def rank(config, models):
    """만성 문제 두뇌를 뒤로 미룬 순서를 돌려줍니다(원본 리스트·config는 그대로).
    최후의 보루(로컬 ollama)는 자리를 지킵니다 — 인터넷이 끊겼을 때의 마지막 답이라,
    앞으로 당겨도 뒤로 밀어도 안 됩니다."""
    if not (config.get("metrics", {}) or {}).get("auto_demote", True):
        return models
    now = time.time()
    if now - _RANK_CACHE["at"] > 60:        # 매 호출마다 파일을 읽지 않게(계측은 조용·가벼워야)
        try:
            _RANK_CACHE["bad"] = judge(config)
        except Exception:
            _RANK_CACHE["bad"] = {}
        _RANK_CACHE["at"] = now
    bad = _RANK_CACHE["bad"]
    if not bad:
        return models
    tail = []
    body = list(models)
    if body and body[-1].get("key_file") is None:   # 로컬 최후의 보루는 붙박이
        tail = [body.pop()]
    ok = [m for m in body if m["label"] not in bad]
    demoted = [m for m in body if m["label"] in bad]
    return ok + demoted + tail


def demoted_lines(config):
    """'/상태'용 — 지금 자동으로 뒤로 밀린 두뇌와 그 이유."""
    if not (config.get("metrics", {}) or {}).get("auto_demote", True):
        return ["", "[자동 후순위] 꺼져 있습니다 (config metrics.auto_demote=false)"]
    bad = judge(config)
    if not bad:
        return []
    lines = ["", "[자동 후순위] — 계측을 보고 이번 실행 동안만 뒤로 미룬 두뇌 (config는 그대로)"]
    lines += [f"  ↓ {label} — {why}" for label, why in bad.items()]
    return lines


def silent_faults(config, days=None):
    """조용한 고장 경보 — 계속 죽는데 폴백이 가려줘 사람이 모르는 두뇌.
    후순위(judge)보다 엄격하게 봅니다: 경보는 자주 울리면 아무도 안 봅니다."""
    j = dict(_JUDGE, **(config.get("metrics", {}) or {}))
    labels = {m["label"] for m in config.get("models", [])}
    out = []
    for label, v in _recent(days or j["days"]).items():
        if label not in labels or v["attempts"] < j["alert_min"]:
            continue
        if v["rate"] < j["alert_rate"]:
            continue
        kinds = "·".join(f"{FAIL_KO.get(k, k)} {n}" for k, n in v["kinds"].items())
        covered = " (폴백이 받아내 대화는 이어졌습니다)" if v["ok"] or v["fb"] else ""
        out.append(f"{label}: 최근 {j['days']}일 {v['attempts']}번 중 {v['fails']}번 실패"
                   f" — {kinds}{covered}")
    return out


TEMP_PREFIXES = ("시험 ", "점검 ")   # 벤치·생사확인이 임시로 쓰는 라벨(진짜 두뇌가 아님)


def _metrics_lines():
    """오늘 두뇌별 성능을 현황판 줄로 만듭니다(활동이 있는 두뇌만).

    ⚠️'시험 …'(벤치가 후보 모델을 재볼 때)·'점검 …'(생사 확인)은 진짜 두뇌가 아니라
    임시 라벨입니다 — 섞어 보여주면 쓰지도 않는 모델이 현황판에 두뇌인 척 올라옵니다.
    judge·silent_faults는 config의 라벨만 보므로 이미 걸러지지만, 여기만 안 걸렀습니다."""
    today = datetime.date.today().isoformat()
    day = {k: v for k, v in _metrics().get(today, {}).items()
           if not str(k).startswith(TEMP_PREFIXES)}
    if not day:
        return []
    lines = ["", "[계측] — 오늘 두뇌 성능 (응답시간·폴백·실패)"]
    total_fb = 0
    for i, (label, b) in enumerate(day.items(), 1):
        ok = int(b.get("ok", 0))
        fb = int(b.get("fb", 0))
        total_fb += fb
        n = int(b.get("s_n", 0))
        parts = [f"{ok}회" + (f"(폴백 {fb})" if fb else "")]
        if n:
            avg = float(b.get("s_sum", 0.0)) / n
            parts.append(f"평균 {avg:.1f}초(최대 {float(b.get('s_max', 0.0)):.1f})")
        fails = b.get("fail") or {}
        nfail = sum(int(v) for v in fails.values())
        if nfail:
            detail = "·".join(f"{FAIL_KO.get(k, k)} {v}" for k, v in fails.items())
            parts.append(f"실패 {nfail} {{{detail}}}")
        if ok or nfail:
            lines.append(f"  {i}. {label} — " + " · ".join(parts))
    lines.append(f"  오늘 폴백 총 {total_fb}회"
                 + ("  (주력이 못 답해 예비로 내려간 횟수)" if total_fb else ""))
    return lines


# ── 살림살이 세기 ─────────────────────────────────────────────────
def _count(fn, fallback="?"):
    """세다 죽어도 현황판 전체가 죽으면 안 됩니다 — 못 세면 ?로 표시합니다."""
    try:
        return fn()
    except Exception:
        return fallback


def _uploads_line():
    folder = os.path.join(BASE_DIR, "uploads")
    if not os.path.isdir(folder):
        return "0개"
    files = [os.path.join(folder, n) for n in os.listdir(folder)]
    files = [p for p in files if os.path.isfile(p)]
    mb = sum(os.path.getsize(p) for p in files) / (1024 * 1024)
    return f"{len(files)}개 ({mb:.0f}MB)" if mb >= 1 else f"{len(files)}개"


def _open_todo_count():
    if not os.path.exists(TODO_FILE):
        return 0
    with open(TODO_FILE, "r", encoding="utf-8") as f:
        return sum(1 for l in f if l.strip().startswith("- [ ]"))


def _knowledge_notes():
    if not os.path.isdir(KNOWLEDGE_DIR):
        return []
    return sorted(f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith(".md"))


def _daily_done():
    try:
        with open(DAILY_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


BENCH_DIR = os.path.join(BASE_DIR, "memory", "bench_reports")


def _bench_alert(config):
    """자동 벤치(월 1회·보고만)가 순위 변동을 봤으면 여기서 알립니다.
    보고서의 '측정 순위'를 **지금 config와 다시 대조**합니다 — 사용자가 그 사이 '/벤치'로
    적용했으면 경보가 저절로 꺼져야지, 다음 달까지 낡은 경고가 붙어 있으면 안 됩니다."""
    if not os.path.isdir(BENCH_DIR):
        return ""
    files = sorted(f for f in os.listdir(BENCH_DIR) if f.endswith(".md"))
    if not files:
        return ""
    with open(os.path.join(BENCH_DIR, files[-1]), "r", encoding="utf-8") as f:
        text = f.read()
    measured = ""
    for line in text.splitlines():
        if line.startswith("측정 순위: "):
            measured = line[len("측정 순위: "):].strip()
            break
    if not measured:
        return ""
    order = [x.strip() for x in measured.split(">")]
    current = [m["label"] for m in config.get("models", []) if m["label"] in set(order)]
    if order == current:
        return ""
    return (f"  ⚠ {files[-1][:-3]} 자동 벤치: 순위 변동 감지 — '/벤치'로 재보고 적용을 검토하세요")


# ── 현황판 ────────────────────────────────────────────────────────
def report(config, cooldown=None):
    """현황판 글을 만들어 돌려줍니다(출력은 부른 쪽이 합니다)."""
    now = time.time()
    today = datetime.date.today()
    usage = _usage()
    tu = usage.get(today.isoformat(), {})
    yu = usage.get((today - datetime.timedelta(days=1)).isoformat(), {})

    lines = ["[두뇌] — 오늘 부른 횟수 (어제)"]
    for i, entry in enumerate(config.get("models", []), 1):
        label = entry["label"]
        key_file = entry.get("key_file")
        ready = "준비됨" if (not key_file
                          or os.path.exists(os.path.join(BASE_DIR, key_file))) else "키 없음"
        resting = ""
        until = (cooldown or {}).get(label, 0)
        if until > now:
            left = int((until - now + 59) // 60)          # 올림 — 30초 남아도 '1분'
            resting = f" · 쉬는 중({left}분 남음 — 한도)"
        marks = "·".join(m for m, on in (("deep", entry.get("deep")),
                                         ("눈", entry.get("vision"))) if on)
        tag = f" [{marks}]" if marks else ""
        lines.append(f"  {i}. {label}{tag} — 오늘 {tu.get(label, 0)}회"
                     f" ({yu.get(label, 0)}) · {ready}{resting}")
    lines.append(f"  합계: 오늘 {sum(tu.values())}회 · 어제 {sum(yu.values())}회")

    # 계측 — 두뇌별 응답시간·폴백·실패 (활동 없으면 통째로 빠집니다)
    lines += _count(_metrics_lines, [])
    # 계측을 실제로 쓴 결과: 지금 뒤로 밀린 두뇌 + 조용한 고장 경보
    lines += _count(lambda: demoted_lines(config), [])
    # 눈 신뢰도 — 시험을 본 적 없으면 통째로 빠집니다
    try:
        import eyecheck
        lines += _count(eyecheck.status_lines, [])
    except Exception:
        pass
    # 눈 2개 자가검수의 짝별 합의/엇갈림 — 검수를 한 적 없으면 통째로 빠집니다
    lines += _count(lambda: consensus_lines(config), [])
    faults = _count(lambda: silent_faults(config), [])
    if faults:
        lines += ["", "[조용한 고장 경보] — 폴백이 가려주고 있어 눈치채기 어려운 문제"]
        lines += [f"  ⚠ {f}" for f in faults]

    # 기억·지식 — 통마다 얼마나 쌓였나
    import lessons
    import memory_search
    import reminders
    know = _count(_knowledge_notes, [])
    self_notes = [n for n in know if n.startswith("selfstudy_")]
    lines += [
        "",
        "[기억]",
        "  개인 기억 " + str(_count(lambda: len(memory_search.load_notes())))
        + "개 · 실수 노트 " + str(_count(lambda: len(lessons.load())))
        + "개 · 지식 창고 " + str(len(know)) + "개",
        "  할 일(미완료) " + str(_count(_open_todo_count))
        + "개 · 예약 " + str(_count(lambda: len(reminders.all_items())))
        + "개 · 대화 기록 " + str(_count(lambda: len(os.listdir(HISTORY_DIR)))) + "일치",
        # 업로드는 사용자가 폰에서 올린 파일이라 루시가 안 지웁니다 — 크기만 보여줘서
        # 커지면 사람이 정리하게. (캡처·문서백업 찌꺼기는 새벽 cleanup이 알아서)
        "  폰 업로드(uploads) " + _count(_uploads_line, "?"),
    ]
    if self_notes:
        lines.append(f"  자가 학습 노트 {len(self_notes)}개:")
        for name in self_notes[-8:]:
            lines.append(f"    - {name[:-3]}")
        if len(self_notes) > 8:
            lines.append(f"    …외 {len(self_notes) - 8}개")

    # 새벽 일과 — 마지막으로 한 날 (여기가 며칠씩 밀려 있으면 스케줄러가 죽은 것)
    done = _daily_done()
    jobs = [("knowledge_sync", "지식 동기화"), ("filesindex", "문서·대화 색인"),
            ("cleanup", "찌꺼기 청소"), ("selfcheck", "자가 점검"),
            ("recover", "놓친 대화 거두기"), ("consolidate", "기억 정리"),
            ("study", "스스로 배우기"), ("backup", "기억 백업(주 1회)"),
            ("bench", "두뇌 벤치(월 1회 · 보고만)"),
            ("brain_probe", "두뇌 생사 확인(주 1회)"),
            ("eye_trust", "눈 신뢰도 시험(월 1회)"),
            ("unity_health", "작업 프로젝트 점검"), ("briefing", "아침 브리핑")]
    jobs.append(("umbrella", "우산 알림(비 오는 날만)"))
    lines += ["", "[새벽 일과] — 마지막으로 한 날"]
    for key, ko in jobs:
        if key == "umbrella":                # 우산 알림 설정은 daily가 아니라 alerts에 삽니다
            conf = config.get("alerts", {}).get("umbrella", {})
        else:
            conf = config.get("daily", {}).get(key, {})
        default_on = key != "briefing"       # 브리핑만 기본 꺼짐
        if not conf.get("enabled", default_on):
            lines.append(f"  {ko}: 꺼짐")
        else:
            lines.append(f"  {ko}: {done.get(key) or '아직 안 함'}")

    alert = _count(lambda: _bench_alert(config), "")
    if alert:
        lines.append(alert)

    # 놓친 대화 — 다음 새벽에 거둘 것이 있나
    import session
    missed = _count(lambda: session.uncovered_days(), None)
    if missed:
        lines.append("  ⚠ 요약 안 된 지난 대화: " + ", ".join(missed) + " (다음 새벽에 거둡니다)")

    # 입과 눈
    import tts
    import vision
    mouth = _count(lambda: " → ".join(tts.ENGINE_KO[e] for e in tts.engines(config))
                   if tts.enabled(config) else "꺼짐")
    eyes = _count(lambda: ", ".join(m["label"] for m in vision.capable(config)) or "없음")
    lines += ["", f"[몸] 목소리: {mouth} · 눈: {eyes}",
              "  (서버가 살아 있는지는 '/점검'으로 확인합니다)"]
    return "\n".join(lines)
