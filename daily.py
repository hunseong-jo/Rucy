# -*- coding: utf-8 -*-
"""
매일 하는 일 — 아침 브리핑 + 지식 창고 자동 동기화.

새 부품을 만들지 않았습니다. 작업 스케줄러가 이미 1분마다 notify.py를 부르고 있으므로,
notify가 예약을 확인하는 김에 "오늘 할 일 중 아직 안 한 게 있나"를 함께 봅니다.
루시 창이 꺼져 있어도, 컴퓨터를 늦게 켜도 돌아갑니다.

두 가지를 합니다.
  ① 아침 브리핑 — 정한 시각에 루시가 **생각해서** 말합니다:
     오늘 날짜·요일 / 오늘 예약된 일 / 어제 나눈 이야기 / (원하면) 관심사 뉴스.
     ⚠️ 사실은 파이썬이 모아서 넘기고, 모델은 **말로 엮기만** 합니다.
        배경 프로세스에서 도구 루프를 돌리면 실패 지점이 늘고(한도·타임아웃) 조용히 죽습니다.
        아침 브리핑은 '안 오면 모르는' 기능이라 가장 단순한 길로 갑니다.
  ② 지식 창고 동기화 — 클로드가 노트를 갱신해도 루시는 '/지식갱신'을 누르기 전까지 옛 정보를
     말합니다. 하루 한 번 조용히 복사해 오고, 바뀐 조각만 미리 임베딩해 둡니다(첫 질문이 안 느리게).
  ③ 기억 정리 — 일주일에 한 번, 쌓인 기억에서 같은 주제를 합치고 지난 일정을 지웁니다.
     (자세한 원칙은 consolidate.py — 모델은 제안만, 검증·백업·적용은 코드가)
  ④ 자가 점검 — 하루 한 번 제 몸을 살핍니다(doctor.py). 재부팅 뒤 목소리 서버·Ollama가
     꺼진 채 방치되면 알림 목소리·검색이 종일 강등된 채 돌기 때문입니다.
  ⑤ 스스로 배우기 — 어제 대화를 복습해 지적받지 않은 실수에서도 교훈을 뽑고,
     얕게 답했던 주제 하나를 스스로 조사해 지식 노트로 남깁니다(study.py).
  ⑥ 놓친 대화 거두기 — 종료 요약은 exit만 잡습니다. 터미널을 X로 닫았거나 정전이 났거나
     웹으로만 대화한 날의 '기억할 사실'을 새벽에 받아냅니다(session.catch_up).

'오늘 이미 했는가'는 memory/daily.json에 날짜로 기록합니다 — 스케줄러가 1분마다 불러도 하루 한 번만 합니다.
"""
import datetime
import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "memory", "daily.json")
BRIEF_DIR = os.path.join(BASE_DIR, "memory", "briefings")
HISTORY_DIR = os.path.join(BASE_DIR, "memory", "history")
TASK_DIR = os.path.join(BASE_DIR, "memory", "tasks")


# ── '오늘 했는지' 기록 ────────────────────────────────────────────
def _state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _mark(job, day):
    data = _state()
    data[job] = day
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)          # 쓰다 죽어도 원본이 남게(원자적 저장)


def days_since(job, now=None):
    """이 일을 마지막으로 한 지 며칠 지났는가. 한 번도 안 했으면 아주 큰 수(=바로 할 때가 됨)."""
    try:
        done = datetime.date.fromisoformat(str(_state().get(job)))
    except (TypeError, ValueError):
        return 10 ** 6
    return ((now or datetime.date.today()) - done).days


def is_due(job, at, catch_up_hours=6, now=None):
    """
    오늘 이 일을 할 때가 됐는가.

    '늦게라도 한 번'은 예약(reminders)과 같은 원칙입니다 — 8시에 컴퓨터가 꺼져 있었고
    10시에 켰다면 그때 브리핑합니다. 다만 **한없이 늦게는 안 합니다**:
    밤 11시에 켰는데 "좋은 아침입니다"라고 하면 그건 알림이 아니라 사고입니다.
    """
    now = now or datetime.datetime.now()
    try:
        hour, minute = [int(x) for x in str(at).split(":")]
    except ValueError:
        return False

    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now < scheduled:
        return False
    if catch_up_hours and now - scheduled > datetime.timedelta(hours=catch_up_hours):
        return False                     # 너무 늦었습니다. 오늘은 건너뜁니다.
    return _state().get(job) != now.strftime("%Y-%m-%d")


# ── 재료 모으기 ───────────────────────────────────────────────────
def _todays_reminders():
    import reminders
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    items = [i for i in reminders.all_items() if str(i.get("at", "")).startswith(today)]
    if not items:
        return "오늘 예약된 일정은 없습니다."
    return "\n".join(f"- {i['at'].split()[1]} {i['what']}" for i in items)


def _yesterday_talk(limit=1500):
    """어제 나눈 대화. 없으면 가장 최근 기록을 씁니다(주말 뒤 월요일이면 금요일 이야기)."""
    if not os.path.isdir(HISTORY_DIR):
        return ""
    today = datetime.date.today()
    logs = sorted(f for f in os.listdir(HISTORY_DIR) if f.endswith(".md"))
    if not logs:
        return ""

    want = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d") + ".md"
    pick = want if want in logs else logs[-1]
    if pick == today.strftime("%Y-%m-%d") + ".md":
        return ""                        # 오늘 기록뿐이면 '어제'는 없습니다
    with open(os.path.join(HISTORY_DIR, pick), "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return f"({pick[:-3]}의 대화)\n" + text[-limit:]


def _news(config, notify=print):
    """관심사 뉴스. 검색 실패는 브리핑 전체를 죽이지 않습니다(뉴스만 빠집니다)."""
    conf = config.get("daily", {}).get("briefing", {})
    topics = conf.get("topics") or []
    if not conf.get("news", True) or not topics:
        return ""

    import tools
    out = []
    for topic in topics[:3]:
        try:
            found = tools.web_search({"query": f"{topic} 최신 소식"})
            out.append(f"[{topic}]\n{found[:800]}")
        except Exception as e:
            notify(f"  (뉴스 '{topic}' 검색 실패: {type(e).__name__})")
    return "\n\n".join(out)


BRIEF_PROMPT = """너는 사용자의 비서 '{name}'다. 아침 브리핑을 **소리로 들려줄 글**로 써라.

규칙:
- 인사 한 줄 + 오늘 날짜·요일. 그다음 날씨, 집 앞 버스, 일정, 할 일, 메일, 어제 이야기, 소식 순서.
- 날씨는 한두 문장으로 요약하고, 우산이 필요한 날이면 반드시 챙기라고 말하라.
- 집 앞 버스는 지금 몇 분 뒤에 오는지만 한 문장으로. 없으면 통째로 건너뛰어라(도착 정보가 없다는 말도 하지 마라).
- 귀로 듣는 글이다. 마크다운·표·목록 기호·URL·이모지를 쓰지 마라. 문장으로 말하라.
- 6~10문장. 사실만 말하고, 없는 것은 지어내지 마라(일정이 없으면 없다고 하라).
- 어제 이야기는 "어제는 ~ 하셨죠" 하고 **한두 문장으로 요약**하고, 오늘 이어서 할 만한 것이 있으면 짚어라.
- 메일은 한 통씩 다 읽지 마라. 몇 통 왔는지 말하고 **눈에 띄는 것만** 한두 개 짚어라.
- 작업 프로젝트 상태는 **문제가 있을 때만** 한 문장으로 말하라("샐러드팜에 컴파일 에러가 하나 있습니다" 식).
  문제 없음·기록 없음·확인 못 함이면 이 부분은 통째로 건너뛰어라(잘 되고 있다는 말도 하지 마라).
- '챙길 것 후보'는 기계가 낱말로 거른 것이라 광고가 섞여 있을 수 있다. 오늘 실제로 챙길 일
  (택배 도착, 예약, 결제 마감)만 골라 한 문장씩 말하고, 없으면 이 부분은 통째로 건너뛰어라.

[오늘]
{today}

[오늘 날씨]
{weather}

[집 앞 버스 — 지금 도착 상황]
{bus}

[오늘의 일정]
{schedule}

[할 일 목록 (미완료)]
{todos}

[작업 중인 유니티 프로젝트 상태 — 새벽 점검 결과]
{unity}

[구글 캘린더]
{calendar}

[안 읽은 메일]
{mail}

[메일에서 거른 챙길 것 후보 — 택배·예약·결제]
{actions}

[어제 나눈 이야기]
{yesterday}

[관심사 소식]
{news}
"""


def _weather_brief(config):
    """오늘 날씨 — 실패해도 브리핑 전체를 죽이지 않습니다."""
    try:
        import weather
        return weather.brief_line(config)
    except Exception as e:
        return f"(날씨 없음: {type(e).__name__})"


def _bus_brief(config):
    """집 앞 버스 지금 도착 상황 — 아침에 나갈 사람에게 제일 급한 정보라 브리핑에 얹습니다.
    단골 정류장(transit.home)이 없거나 조회가 실패하면 조용히 빠집니다(브리핑은 계속)."""
    if not config.get("transit", {}).get("home"):
        return "(설정 안 함)"
    try:
        import transit
        return transit.home(config)
    except Exception as e:
        return f"(버스 정보 없음: {type(e).__name__})"


def _unity_health():
    """새벽에 적어둔 작업 프로젝트 컴파일 상태 한 줄 — 브리핑은 유니티를 켜지 않습니다."""
    try:
        import unity
        return unity.health_line() or "(점검 기록 없음)"
    except Exception as e:
        return f"(확인 못 함: {type(e).__name__})"


def _open_todos(limit=6):
    """미완료 할 일 — tools를 통째로 얹지 않고 파일만 읽습니다(배경 프로세스는 가볍게)."""
    path = os.path.join(BASE_DIR, "memory", "todo.md")
    if not os.path.exists(path):
        return "(없음)"
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = [l.strip()[6:] for l in f if l.strip().startswith("- [ ]")]
    except OSError:
        return "(없음)"
    if not items:
        return "(없음 — 전부 완료)"
    out = items[:limit]
    if len(items) > limit:
        out.append(f"…외 {len(items) - limit}개")
    return "\n".join("- " + t for t in out)


# 브리핑은 배경에서(사람이 없을 때) 돕니다. 구글이 삐끗해도 브리핑 전체가 죽으면 안 되므로
# 여기서는 무엇이 실패하든 조용히 빈손으로 돌아옵니다.
def _calendar_today(config):
    if not config.get("google", {}).get("enabled", True):
        return "(연동 안 함)"
    try:
        import gmail_calendar as gc
        if not gc.ready():
            return "(구글 연동 전)"
        found = gc.events(days=1)
        if not found:
            return "오늘 캘린더에 등록된 일정이 없습니다."
        return "\n".join(
            f"- {e['title']}"
            + ("" if e["allday"] else f" ({e['when'][11:16]})")
            + (f" @{e['where']}" if e["where"] else "")
            for e in found
        )
    except Exception as e:
        return f"(캘린더를 읽지 못했습니다: {type(e).__name__})"


# 메일에서 '챙길 것'(택배·예약·결제) 후보를 낱말로 거릅니다. 여기서는 거르기만 하고
# 판단은 브리핑 모델이 합니다 — 배경 프로세스에서 모델을 한 번 더 부르지 않기 위해서입니다
# (브리핑이 어차피 모델을 한 번 부르므로, 후보를 재료로 끼워 넣으면 공짜입니다).
_ACTION_WORDS = ("택배", "배송", "운송장", "발송", "도착", "예약", "확정", "체크인",
                 "결제", "청구", "납부", "마감", "연체", "환불", "입금")


def _mail_actions(config, limit=15):
    if not config.get("google", {}).get("enabled", True):
        return "(연동 안 함)"
    try:
        import gmail_calendar as gc
        if not gc.ready():
            return "(구글 연동 전)"
        # 읽음 여부와 무관하게 최근 이틀 — 택배 문자류는 자동으로 읽음 처리돼 있기도 합니다.
        found = gc.mail("newer_than:2d", limit=limit)
    except Exception as e:
        return f"(메일을 읽지 못했습니다: {type(e).__name__})"
    hits = []
    for m in found:
        blob = m.get("subject", "") + " " + m.get("snippet", "")
        if any(w in blob for w in _ACTION_WORDS):
            hits.append(f"- {m['subject']} / {m['from'][:40]} / {m.get('snippet', '')[:80]}")
    return "\n".join(hits[:6]) or "(없음)"


def _unread_mail(config, limit=5):
    if not config.get("google", {}).get("enabled", True):
        return "(연동 안 함)"
    try:
        import gmail_calendar as gc
        if not gc.ready():
            return "(구글 연동 전)"
        found = gc.mail("is:unread newer_than:2d", limit=limit)
        if not found:
            return "안 읽은 메일이 없습니다."
        return "\n".join(f"- {m['subject']} / 보낸이 {m['from'][:40]}" for m in found)
    except Exception as e:
        return f"(메일을 읽지 못했습니다: {type(e).__name__})"


# ── 아침 브리핑 ───────────────────────────────────────────────────
def briefing(config, notify=print, speak=True):
    """브리핑 글을 만들어 돌려줍니다(말하기·창 띄우기는 부른 쪽이 합니다)."""
    import agent

    now = datetime.datetime.now()
    weekday = "월화수목금토일"[now.weekday()]
    conf = config.get("daily", {}).get("briefing", {})

    prompt = BRIEF_PROMPT.format(
        name=config.get("name", "루시"),
        today=now.strftime(f"%Y년 %m월 %d일 {weekday}요일 %H시 %M분"),
        weather=_weather_brief(config),
        bus=_bus_brief(config),
        todos=_open_todos(),
        unity=_unity_health(),
        schedule=_todays_reminders(),
        calendar=_calendar_today(config),
        mail=_unread_mail(config, conf.get("mail_limit", 5)),
        actions=_mail_actions(config),
        yesterday=_yesterday_talk() or "(어제 나눈 대화 기록이 없습니다)",
        news=_news(config, notify) or "(소식 없음)",
    )

    # 도구도 감수도 없이 한 번만 부릅니다 — 배경에서 도는 일은 단순할수록 오래 삽니다.
    message, used, _entry = agent.call_model(config, [{"role": "user", "content": prompt}],
                                             use_tools=False)
    text = agent._clean(message.get("content") or "")
    if not text:
        raise RuntimeError("브리핑 글이 비어 있습니다")

    os.makedirs(BRIEF_DIR, exist_ok=True)
    path = os.path.join(BRIEF_DIR, now.strftime("%Y-%m-%d") + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {now.strftime('%Y-%m-%d')} 아침 브리핑 ({used})\n\n{text}\n")
    notify(f"  브리핑을 적었습니다: {path}")
    return text


# ── 지식 창고 동기화 ──────────────────────────────────────────────
def sync_knowledge(config, notify=print):
    import knowledge
    count, where = knowledge.sync()
    if not count:
        notify(f"  지식 동기화 실패: {where}")
        return 0

    # 복사만 하면 '바뀐 조각'은 다음 질문 때 임베딩됩니다 — 그 질문이 느려집니다.
    # 어차피 배경이니 지금 미리 데워 둡니다. 실패해도 검색은 되므로 조용히 넘어갑니다.
    try:
        knowledge.search("워밍업", config, top_k=1)
    except Exception as e:
        notify(f"  (인덱스 예열 실패: {type(e).__name__} — 검색은 됩니다)")
    notify(f"  지식 창고 동기화: 노트 {count}개")
    return count


# ── 월 1회 두뇌 벤치 — 보고만 ─────────────────────────────────────
BENCH_DIR = os.path.join(BASE_DIR, "memory", "bench_reports")


def bench_check(config, notify=print):
    """
    무료 모델판은 계속 바뀝니다 — 어제 1위가 오늘 한도에 걸리고, 라우터가 깨진 답을
    내기 시작합니다(OpenRouter '올ypedia'). 한 달에 한 번 순위를 실측해 보고서만 남깁니다.

    ⚠️ **적용은 하지 않습니다.** 밤에 말없이 config(두뇌 순서)를 갈아엎는 비서는
    위험합니다 — 아침에 루시 성격이 바뀌어 있는데 아무도 이유를 모릅니다.
    적용은 사람이 '/벤치'에서 y/N로 합니다. 순위가 달라졌으면 '/상태'가 알려줍니다.

    벤치는 두뇌마다 과제를 실제로 시키므로 무료 한도를 씁니다 — 그래서 새벽 일과 중
    가장 뒤 시각(05:50)에 둡니다(낮의 대화 한도를 아침부터 갉지 않게).
    """
    import contextlib
    import io

    import agent
    import bench

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):      # 벤치의 진행 로그는 보고서 파일로만
        results = bench.run(agent, config)
        ranked = bench.rank(results)
        bench.report(ranked)

    # 비교는 '실제로 잰' 온라인 두뇌끼리만 — 한도 때문에 못 잰 모델을 순위에서
    # 밀렸다고 보고하면 매달 거짓 경보가 옵니다(벤치의 '측정 불가' 원칙과 같음).
    measured = [r["label"] for r in ranked if not r["local"] and r["tried"]]
    current = [m["label"] for m in config.get("models", []) if m["label"] in set(measured)]
    changed = measured != current

    day = datetime.date.today().isoformat()
    lines = [f"# {day} 두뇌 벤치 (자동 · 보고만)", "",
             "지금 순서: " + " > ".join(current),
             "측정 순위: " + " > ".join(measured), ""]
    if changed:
        lines.append("⚠ 순위가 달라졌습니다 — 적용하려면 루시에서 '/벤치' "
                     "(자동으로는 config를 바꾸지 않습니다)")
    else:
        lines.append("순위 그대로입니다 — 바꿀 것 없음.")
    lines += ["", "## 상세", "```", buf.getvalue().rstrip(), "```", ""]

    os.makedirs(BENCH_DIR, exist_ok=True)
    path = os.path.join(BENCH_DIR, day + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    notify(f"  벤치 보고서: {path}" + (" (⚠ 순위 변동)" if changed else " (변동 없음)"))
    return changed


# ── 예약한 '지시'를 실제로 수행 ───────────────────────────────────
TASK_PROMPT = """사용자가 미리 예약해 둔 지시다. 지금 이 일을 해라.

[지시]
{what}

지금은 {now}이고, 사용자는 화면 앞에 없다. 되물을 수 없으니 스스로 판단해서 끝까지 해라.
- 조사가 필요하면 research나 web_search를 써라. 추측으로 채우지 마라.
- 문서를 만들라고 했으면 write_document로 실제 파일을 만들어라(경로를 답에 적어라).
- 마지막 줄에 사용자에게 알릴 한 문장을 써라. 소리로 들려줄 것이므로 짧게.
"""


def run_task(config, item, notify=print):
    """
    예약한 지시를 배경에서 수행합니다. (사람에게 알릴 한 줄, 결과를 적어둔 파일 경로)

    ⚠️ 사람이 화면 앞에 없으므로 tools.UNATTENDED를 켭니다 — 파일·문서 쓰기는 허용하고
       코드·명령 실행은 거부합니다. 지시문에 숨어든 코드가 아무도 모르게 도는 일은 없어야 합니다.
    """
    import agent
    import tools

    what = item.get("what", "").strip()
    now = datetime.datetime.now()

    tools.init(config)
    tools.UNATTENDED = True
    try:
        state = agent.new_state(config)
        answer, used = agent.respond(
            config, state,
            TASK_PROMPT.format(what=what, now=now.strftime("%Y년 %m월 %d일 %H:%M")),
            notify=notify,
        )
    finally:
        tools.UNATTENDED = False          # 켜둔 채로 두면 다음에 사람이 쓸 때도 무인 규칙이 적용됩니다

    os.makedirs(TASK_DIR, exist_ok=True)
    slug = "".join(c for c in what[:20] if c.isalnum() or c in " _-").strip().replace(" ", "_")
    path = os.path.join(TASK_DIR, now.strftime("%Y-%m-%d_%H%M_") + (slug or "task") + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 예약한 지시 ({used})\n\n**지시**: {what}\n**시각**: {now.strftime('%Y-%m-%d %H:%M')}\n\n---\n\n{answer}\n")

    # 답 전체를 소리로 읽으면 몇 분이 걸립니다. 마지막 한 줄(알릴 말)만 들려줍니다.
    lines = [l.strip() for l in answer.splitlines() if l.strip()]
    headline = lines[-1] if lines else "일을 마쳤습니다."
    notify(f"  지시를 수행했습니다 → {path}")
    return headline, path


def _prune_old(folder, days):
    """폴더 안에서 days일 넘게 안 건드린 파일을 지웁니다. 지운 수를 돌려줍니다."""
    if not os.path.isdir(folder):
        return 0
    cutoff = time.time() - days * 86400
    gone = 0
    for name in os.listdir(folder):
        p = os.path.join(folder, name)
        try:
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
                gone += 1
        except OSError:
            continue
    return gone


# ── 스케줄러가 부르는 문 ──────────────────────────────────────────
def tick(config, notify=print, announce=None):
    """
    notify.py가 1분마다 부릅니다. 때가 된 것만 하고, 아니면 즉시 조용히 끝납니다.
    announce(text): 브리핑을 사람에게 전달하는 방법(소리·창). 없으면 글만 남깁니다.
    """
    daily = config.get("daily", {})
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    did = []

    know = daily.get("knowledge_sync", {})
    if know.get("enabled", True) and is_due("knowledge_sync", know.get("at", "05:00"),
                                            know.get("catch_up_hours", 18)):
        # 먼저 오늘 한 것으로 표시합니다 — 동기화가 오래 걸려 스케줄러가 다시 들어와도
        # 두 번 돌지 않게(예약 알림이 '먼저 넘기고 터뜨리는' 것과 같은 이유).
        _mark("knowledge_sync", today)
        try:
            sync_knowledge(config, notify)
            did.append("지식 동기화")
        except Exception as e:
            notify(f"  지식 동기화 오류: {type(e).__name__}: {e}")

    files = daily.get("filesindex", {})
    if files.get("enabled", True) and is_due("filesindex", files.get("at", "05:05"),
                                             files.get("catch_up_hours", 18)):
        _mark("filesindex", today)
        try:
            # PC 문서 색인을 매일 새벽에 증분 갱신합니다. 안 하면 색인이 24시간 안
            # 넘었다는 이유로 어제 받은 파일을 못 찾습니다("방금 받은 계약서 어딨지?"
            # 에 빈손). 증분이라 바뀐 파일이 없으면 1초 안에 끝납니다.
            import docsearch
            if docsearch.enabled(config):
                added, total, failed = docsearch.build(config, notify)
                if added:
                    did.append(f"문서 색인({added}개 갱신)")
        except Exception as e:
            notify(f"  문서 색인 오류: {type(e).__name__}: {e}")
        try:
            # 대화 색인(의미 검색용)도 같은 새벽에 — 낮에 첫 질문이 임베딩을 기다리지 않게.
            import histsearch
            refreshed, chunks = histsearch.build(config, notify)
            if refreshed:
                did.append(f"대화 색인({refreshed}일치)")
        except Exception as e:
            notify(f"  대화 색인 오류: {type(e).__name__}: {e}")

    sweep = daily.get("cleanup", {})
    if sweep.get("enabled", True) and is_due("cleanup", sweep.get("at", "05:08"),
                                             sweep.get("catch_up_hours", 18)):
        _mark("cleanup", today)
        try:
            # ⚠️루시가 스스로 만든 찌꺼기만 지웁니다(화면캡처·문서수정 자동백업).
            # uploads(사용자가 올린 파일)는 절대 안 지웁니다 — 크기는 /상태가 보여줍니다.
            shots = _prune_old(os.path.join(BASE_DIR, "screenshots"),
                               sweep.get("screenshots_days", 30))
            baks = _prune_old(os.path.join(BASE_DIR, "memory", "doc_backups"),
                              sweep.get("doc_backups_days", 60))
            if shots or baks:
                did.append(f"찌꺼기 청소(캡처 {shots}·문서백업 {baks})")
        except Exception as e:
            notify(f"  찌꺼기 청소 오류: {type(e).__name__}: {e}")

    care = daily.get("selfcheck", {})
    if care.get("enabled", True) and is_due("selfcheck", care.get("at", "05:10"),
                                            care.get("catch_up_hours", 18)):
        _mark("selfcheck", today)
        try:
            import doctor
            if doctor.run(config, notify):
                did.append("자가 점검(문제 발견)")
        except Exception as e:
            notify(f"  자가 점검 오류: {type(e).__name__}: {e}")

    rescue = daily.get("recover", {})
    if rescue.get("enabled", True) and is_due("recover", rescue.get("at", "05:15"),
                                              rescue.get("catch_up_hours", 18)):
        _mark("recover", today)
        try:
            # 어제(및 그제) 대화 중 요약 안 된 것을 거둡니다 — 터미널을 X로 닫았거나
            # 정전이 났거나, 웹으로만 대화한 날의 사실이 여기서 살아납니다.
            import agent
            import session
            got = session.catch_up(config, agent.call_model, notify,
                                   days=rescue.get("days", 3))
            if got:
                did.append(f"놓친 대화 거두기({len(got)}개 기억)")
        except Exception as e:
            notify(f"  놓친 대화 거두기 오류: {type(e).__name__}: {e}")

    tidy = daily.get("consolidate", {})
    if (tidy.get("enabled", True)
            and days_since("consolidate") >= tidy.get("every_days", 7)
            and is_due("consolidate", tidy.get("at", "05:20"), tidy.get("catch_up_hours", 18))):
        _mark("consolidate", today)      # 지식 동기화와 같은 이유 — 먼저 넘기고 시작합니다
        try:
            import consolidate
            if consolidate.run(config, notify):
                did.append("기억 정리")
        except Exception as e:
            notify(f"  기억 정리 오류: {type(e).__name__}: {e}")

    learn = daily.get("study", {})
    if learn.get("enabled", True) and is_due("study", learn.get("at", "05:30"),
                                             learn.get("catch_up_hours", 18)):
        _mark("study", today)
        try:
            import study
            did += study.nightly(config, notify)
        except Exception as e:
            notify(f"  스스로 배우기 오류: {type(e).__name__}: {e}")

    save = daily.get("backup", {})
    if (save.get("enabled", True)
            and days_since("backup") >= save.get("every_days", 7)
            and is_due("backup", save.get("at", "05:40"), save.get("catch_up_hours", 18))):
        _mark("backup", today)               # 기억 정리와 같은 이유 — 먼저 넘기고 시작합니다
        try:
            import backup
            if backup.run(config, notify):
                did.append("기억 백업")
        except Exception as e:
            notify(f"  기억 백업 오류: {type(e).__name__}: {e}")

    test = daily.get("bench", {})
    if (test.get("enabled", True)
            and days_since("bench") >= test.get("every_days", 30)
            and is_due("bench", test.get("at", "05:50"), test.get("catch_up_hours", 18))):
        _mark("bench", today)                # 벤치는 10분 넘게 걸립니다 — 먼저 넘기고 시작
        try:
            if bench_check(config, notify):
                did.append("두뇌 벤치(⚠ 순위 변동 — '/벤치'로 적용 검토)")
            else:
                did.append("두뇌 벤치(변동 없음)")
        except Exception as e:
            notify(f"  두뇌 벤치 오류: {type(e).__name__}: {e}")

    # 눈 신뢰도 시험 — 월 1회(두뇌 벤치와 같은 주기). 눈 하나당 그림 6장이라 자주 돌리면
    # 무료 한도를 먹습니다. 결과는 자가검수 때 '믿는 눈부터' 묻는 순서로 쓰입니다.
    eye = daily.get("eye_trust", {})
    if (eye.get("enabled", True)
            and days_since("eye_trust") >= eye.get("every_days", 30)
            and is_due("eye_trust", eye.get("at", "05:55"), eye.get("catch_up_hours", 18))):
        _mark("eye_trust", today)             # 몇 분 걸립니다 — 먼저 넘기고 시작
        try:
            import agent
            import eyecheck
            # ⭐새벽 배경 작업이라 쿨다운을 기다릴 수 있습니다 — 무료 눈(Groq)은 이미지 2장이면
            #   30분 쉬러 가서, 안 기다리면 여섯 문제 중 둘만 채점되고 '측정 불가'로 남습니다.
            _text, res = eyecheck.run(agent, config, notify=notify,
                                      max_wait=eye.get("max_wait_sec", 2700))
            bad = [l for l, r in res.items() if r.get("grade") == "demoted"]
            did.append("눈 신뢰도 시험" + (f"(⚠ {len(bad)}개 강등)" if bad else "(이상 없음)"))
        except Exception as e:
            notify(f"  눈 신뢰도 시험 오류: {type(e).__name__}: {e}")

    # 놀고 있는 두뇌 생사 확인 — 주 1회. 폴백 사슬 아래쪽 두뇌는 위가 건강하면 안 불려서
    # 계측이 못 봅니다(조용한 고장 경보의 사각지대). 안 불린 것만 골라 짧게 찔러 보고,
    # 결과는 doctor가 읽습니다. 실제 호출이라 무료 한도를 조금 쓰므로 벤치 근처에 둡니다.
    alive = daily.get("brain_probe", {})
    if (alive.get("enabled", True)
            and days_since("brain_probe") >= alive.get("every_days", 7)
            and is_due("brain_probe", alive.get("at", "05:45"),
                       alive.get("catch_up_hours", 18))):
        _mark("brain_probe", today)           # 몇 분 걸립니다 — 먼저 넘기고 시작
        try:
            import brainprobe
            res = brainprobe.run(config, notify)
            dead = [l for l, r in res.items() if r.get("state") in brainprobe.ALARM_STATES]
            did.append("두뇌 생사 확인" + (f"(⚠ {len(dead)}개 죽음)" if dead else "(이상 없음)"))
        except Exception as e:
            notify(f"  두뇌 생사 확인 오류: {type(e).__name__}: {e}")

    # 작업 대상 유니티 프로젝트 컴파일 점검 — 브리핑 전에 끝나야 브리핑에 실립니다.
    # 배치모드로 프로젝트를 열고 닫으므로 사람이 없는 새벽에 돌립니다(에디터가 열려 있으면
    # 정적 점검으로 자동 대체되니 잠금 걱정은 없습니다).
    uni = daily.get("unity_health", {})
    if uni.get("enabled", True) and is_due("unity_health", uni.get("at", "06:00"),
                                           uni.get("catch_up_hours", 2)):
        _mark("unity_health", today)          # 몇 분 걸립니다 — 먼저 넘기고 시작
        try:
            import unity
            _text, res = unity.health(config, timeout=uni.get("timeout", 900), notify=notify)
            bad = [r for r in res if r["state"] in ("error", "stale")]
            did.append("작업 프로젝트 점검" + (f"(⚠ {len(bad)}건 문제)" if bad else "(이상 없음)"))
        except Exception as e:
            notify(f"  작업 프로젝트 점검 오류: {type(e).__name__}: {e}")

    brief = daily.get("briefing", {})
    if brief.get("enabled", False) and is_due("briefing", brief.get("at", "08:00"),
                                              brief.get("catch_up_hours", 6)):
        _mark("briefing", today)
        try:
            text = briefing(config, notify)
            if announce:
                announce(text)
            did.append("아침 브리핑")
        except Exception as e:
            notify(f"  브리핑 오류: {type(e).__name__}: {e}")

    return did
