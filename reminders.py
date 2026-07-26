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
import re

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

WEEKDAYS = {
    "월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3, "금요일": 4, "토요일": 5, "일요일": 6,
    "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6
}


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
    """
    날짜/시각 문자열을 datetime 객체로 안정하게 파싱합니다.
    날짜 파싱 및 이번 주 요일 연산에서 오차가 발생하지 않도록 예외 처리 및 계산 안정화를 수행합니다.
    """
    if isinstance(at, datetime.datetime):
        return at

    s = str(at).strip()
    now = datetime.datetime.now()

    # 1. 표준 날짜/시간 포맷 시도
    formats = (
        FMT,
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%Y.%m.%d %H:%M",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    )
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            if fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
                dt = dt.replace(hour=9, minute=0, second=0)
            return dt
        except ValueError:
            pass

    # 2. 상대 날짜 및 요일 파싱 (예: "이번주 수요일 15:00", "내일 09:00" 등)
    time_match = re.search(r"(\d{1,2}):(\d{2})", s)
    hour = int(time_match.group(1)) if time_match else 9
    minute = int(time_match.group(2)) if time_match else 0

    target_date = None

    if "오늘" in s:
        target_date = now.date()
    elif "내일" in s:
        target_date = (now + datetime.timedelta(days=1)).date()
    elif "모레" in s:
        target_date = (now + datetime.timedelta(days=2)).date()

    if target_date is None:
        for w_name, w_idx in WEEKDAYS.items():
            if w_name in s:
                # 이번 주 월요일 기준 정확한 연산 (0:월 ~ 6:일)
                this_monday = now.date() - datetime.timedelta(days=now.weekday())
                target_date = this_monday + datetime.timedelta(days=w_idx)
                if "다음 주" in s or "다음주" in s:
                    target_date += datetime.timedelta(weeks=1)
                elif "이번 주" in s or "this week" in s.lower() or "이번주" in s:
                    pass
                else:
                    # 요일만 입력되었고 과거 일자이면 다음 주 동일 요일로 조정
                    if target_date < now.date():
                        target_date += datetime.timedelta(weeks=1)
                break

    if target_date:
        return datetime.datetime.combine(target_date, datetime.time(hour, minute))

    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        pass

    raise ValueError(f"시각 파싱 실패: '{at}'. 'YYYY-MM-DD HH:MM' 또는 '이번주 수요일 15:00' 형식이어야 합니다")


def _days_in(year, month):
    year = year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    nxt = datetime.date(year + (month // 12), month % 12 + 1, 1)
    return (nxt - datetime.timedelta(days=1)).day


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
            year = dt.year + (dt.month // 12)
            month = dt.month % 12 + 1
            day = min(dt.day, _days_in(year, month))
            dt = dt.replace(year=year, month=month, day=day)
        else:
            return None
    return dt


# ─────────────────────────────── 루시가 쓰는 것 ───────────────────────────────

def add(what, at, repeat="once", kind="notify"):
    """예약을 추가합니다. at은 'YYYY-MM-DD HH:MM' 또는 요일/상대 날짜 표현. kind는 notify(알림) 또는 task(지시)."""
    repeat = repeat if repeat in REPEATS else "once"
    kind = kind if kind in KINDS else "notify"
    try:
        when = _parse(at)
    except ValueError as e:
        raise ValueError(str(e))
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

