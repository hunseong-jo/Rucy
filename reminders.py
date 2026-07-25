# -*- coding: utf-8 -*-
"""
예약·알림 — 루시가 약속을 기억했다가 때가 되면 알려줍니다.

설계에서 중요한 세 가지:

1. **알리는 주체는 하나다.** 예약을 실제로 터뜨리는 것은 오직 notify.py(윈도우 작업
   스케줄러가 1분마다 부름)입니다. 루시 창은 예약을 만들고 보여주기만 합니다.
   양쪽이 다 터뜨리면 같은 알림이 두 번 뜹니다.

2. **컴퓨터가 꺼져 있었어도 잃지 않는다.** 지난 예약은 늦게라도 한 번 알리고,
   반복 예약이면 다음 차례로 넘깁니다(밀린 걸 수십 번 연달아 터뜨리지 않습니다).

3. **터뜨리기 전에 먼저 시각을 넘긴다.** 알림 창이 사용자를 기다리는 동안 스케줄러가
   또 돌아도, 이미 다음 차례로 넘어가 있으므로 중복되지 않습니다.
"""
import datetime
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(BASE_DIR, "memory", "reminders.json")

FMT = "%Y-%m-%d %H:%M"
REPEATS = ("once", "daily", "weekly", "monthly")
REPEAT_KO = {"once": "한 번", "daily": "매일", "weekly": "매주", "monthly": "매달"}

# 예약에는 두 종류가 있습니다.
#   notify = 정해둔 문구를 때가 되면 읽어주고 창을 띄웁니다. ("3시에 약 먹으라고 알려줘")
#   task   = 루시가 그 시각에 **실제로 그 일을 합니다**. ("매주 월요일 AI 소식 조사해서 문서로 만들어놔")
# 알리는 주체가 하나인 것은 그대로입니다 — 지시를 수행하는 것도 notify.py입니다.
KINDS = ("notify", "task")
KIND_KO = {"notify": "알림", "task": "지시"}


def _load():
    try:
        with open(FILE, "r", encoding="utf-8-sig") as f:      # BOM 방어
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _save(items):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:               # 원자적 저장 —
        json.dump(items, f, ensure_ascii=False, indent=2)     # 쓰다 죽어도 원본이 남습니다
    os.replace(tmp, FILE)


def _parse(at):
    return datetime.datetime.strptime(at, FMT)


def _advance(dt, repeat):
    """다음 차례로 넘깁니다. 이미 지난 예약이면 미래가 될 때까지 넘깁니다."""
    now = datetime.datetime.now()
    if repeat == "once":
        return None
    while dt <= now:
        if repeat == "daily":
            dt += datetime.timedelta(days=1)
        elif repeat == "weekly":
            dt += datetime.timedelta(days=7)
        elif repeat == "monthly":
            # 31일 같은 날짜는 짧은 달에 없습니다 — 그 달의 마지막 날로 당깁니다.
            year, month = dt.year + (dt.month // 12), dt.month % 12 + 1
            day = min(dt.day, _days_in(year, month))
            dt = dt.replace(year=year, month=month, day=day)
        else:
            return None
    return dt


def _days_in(year, month):
    nxt = datetime.date(year + (month // 12), month % 12 + 1, 1)
    return (nxt - datetime.timedelta(days=1)).day


# ─────────────────────────────── 루시가 쓰는 것 ───────────────────────────────

def add(what, at, repeat="once", kind="notify"):
    """예약을 추가합니다. at은 'YYYY-MM-DD HH:MM'. kind는 notify(알림) 또는 task(지시)."""
    repeat = repeat if repeat in REPEATS else "once"
    kind = kind if kind in KINDS else "notify"
    try:
        when = _parse(at)
    except ValueError:
        raise ValueError("시각은 'YYYY-MM-DD HH:MM' 형식이어야 합니다")
    if repeat == "once" and when <= datetime.datetime.now():
        raise ValueError("이미 지난 시각입니다")

    items = _load()
    new_id = max([i.get("id", 0) for i in items], default=0) + 1
    items.append({
        "id": new_id,
        "what": what.strip(),
        "at": when.strftime(FMT),
        "repeat": repeat,
        "kind": kind,
        "created": datetime.datetime.now().strftime(FMT),
    })
    _save(items)
    return items[-1]


def all_items():
    return sorted(_load(), key=lambda i: i.get("at", ""))


def cancel(needle):
    """번호(1) 또는 내용의 일부('치과')로 지웁니다."""
    items = _load()
    needle = str(needle).strip()
    if needle.isdigit():
        keep = [i for i in items if i.get("id") != int(needle)]
        gone = [i for i in items if i.get("id") == int(needle)]
    else:
        keep = [i for i in items if needle not in i.get("what", "")]
        gone = [i for i in items if needle in i.get("what", "")]
    if gone:
        _save(keep)
    return gone


def due(now=None):
    """지금 터뜨려야 할 예약을 돌려주고, **먼저** 다음 차례로 넘겨 저장합니다.

    넘기는 것을 알림보다 먼저 하는 이유: 알림 창이 떠 있는 동안 스케줄러가 다시 돌아도
    같은 예약을 또 집지 않게 하기 위해서입니다.
    """
    now = now or datetime.datetime.now()
    items = _load()
    fired, keep = [], []
    for item in items:
        try:
            when = _parse(item["at"])
        except (KeyError, ValueError):
            continue                    # 망가진 줄은 조용히 버립니다
        if when <= now:
            fired.append(dict(item))
            nxt = _advance(when, item.get("repeat", "once"))
            if nxt:
                item["at"] = nxt.strftime(FMT)
                keep.append(item)       # 반복이면 다음 차례로 살아남습니다
        else:
            keep.append(item)
    if fired:
        _save(keep)
    return fired


def describe(item):
    kind = KIND_KO.get(item.get("kind", "notify"), "알림")
    return (f"[{item['id']}] {item['at']} ({REPEAT_KO.get(item.get('repeat','once'),'한 번')}·{kind}) "
            f"{item['what']}")
