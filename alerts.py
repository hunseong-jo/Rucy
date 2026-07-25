# -*- coding: utf-8 -*-
"""
상황 알림 — 루시가 먼저 말을 겁니다.

지금까지 알림은 사용자가 직접 건 예약(reminders)뿐이었습니다. 이건 반대 방향입니다:
  ① 캘린더 선(先)알림 — 구글 캘린더 일정이 다가오면(기본 30분 전) 예약을 안 걸었어도
     소리와 창으로 알립니다. 예약은 '걸어둔 것', 이건 '알아서 봐주는 것'.
  ② 우산 알림 — 아침 정한 시각에 오늘 비 소식이 있으면 나가기 전에 한 번 말합니다.
     비가 안 오는 날은 조용합니다. (아침 브리핑에도 날씨가 있지만 브리핑은 기본 꺼짐이고,
     우산은 놓치면 젖습니다)

notify.py(작업 스케줄러, 1분 주기)가 부릅니다. 배경 원칙은 daily.py와 같습니다 —
모델을 부르지 않고(문장은 코드가 만듦), 무엇이 실패하든 예약 알림을 죽이지 않습니다.
"""
import datetime
import json
import os

import daily

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "memory", "events_cache.json")
ALERTED_FILE = os.path.join(BASE_DIR, "memory", "alerted.json")


def _read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, type(fallback)) else fallback
    except (OSError, ValueError):
        return fallback


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ── 캘린더 선알림 ─────────────────────────────────────────────────
def _fresh_events(conf):
    """
    앞으로 하루치 일정. 구글에는 refresh_min마다 한 번만 묻고 그사이엔 캐시를 씁니다.
    1분마다 새 프로세스로 뜨므로 캐시는 메모리가 아니라 파일이어야 합니다.
    """
    cal = conf.get("alerts", {}).get("calendar", {})
    cache = _read_json(CACHE_FILE, {})
    now = datetime.datetime.now()
    try:
        fetched = datetime.datetime.fromisoformat(cache.get("fetched_at", ""))
        if (now - fetched).total_seconds() < cal.get("refresh_min", 10) * 60:
            return cache.get("events", [])
    except ValueError:
        pass

    import gmail_calendar as gc
    # 자격증명만 있고 토큰이 없으면 _service가 브라우저 로그인 창을 띄웁니다 —
    # 배경 프로세스가 그러면 안 되므로 토큰이 이미 있는 경우에만 묻습니다.
    if not (gc.ready() and os.path.exists(gc.TOKEN_PATH)):
        return []
    try:
        events = gc.events(days=1)
    except Exception:
        return cache.get("events", [])   # 구글이 삐끗하면 옛 캐시라도 — 일정은 잘 안 움직입니다
    _write_json(CACHE_FILE, {"fetched_at": now.isoformat(), "events": events})
    return events


def _due_events(conf):
    """지금 알릴 일정 목록. [(일정, 시작시각, 남은 분)] — 알리기 전에 먼저 표시합니다."""
    cal = conf.get("alerts", {}).get("calendar", {})
    if not cal.get("enabled", True):
        return []
    ahead = cal.get("minutes_before", 30)
    now = datetime.datetime.now().astimezone()
    alerted = _read_json(ALERTED_FILE, {})
    today = now.date().isoformat()

    due = []
    for e in _fresh_events(conf):
        if e.get("allday"):
            continue                     # 시각이 없는 일정에는 '몇 분 전'이 없습니다
        try:
            start = datetime.datetime.fromisoformat(e["when"])
        except (KeyError, TypeError, ValueError):
            continue
        if start.tzinfo is None:
            start = start.astimezone()
        minutes = (start - now).total_seconds() / 60
        key = e.get("id") or f"{e.get('when')}|{e.get('title')}"
        # 지난 일정은 알리지 않습니다 — 컴퓨터가 꺼져 있었어도 "10분 전에 시작했어요"는
        # 알림이 아니라 사고입니다. 단 1분은 봐줍니다: 1분 주기 폴링이 시작 직후에
        # 걸리면 '정각 시작' 일정이 통째로 새기 때문입니다(그때는 "지금"이라고 말합니다).
        if -1 <= minutes <= ahead and key not in alerted:
            due.append((e, start, max(0, int(minutes))))
            alerted[key] = today

    if due:
        # 터뜨리기 전에 먼저 적습니다 — 알림 창이 사용자를 기다리는 동안 스케줄러가
        # 또 돌아도 중복되지 않게(예약 알림의 '먼저 넘기고 터뜨리기'와 같은 원칙).
        keep_from = (now.date() - datetime.timedelta(days=2)).isoformat()
        _write_json(ALERTED_FILE, {k: d for k, d in alerted.items() if d >= keep_from})
    return due


# ── 우산 알림 ─────────────────────────────────────────────────────
def _umbrella_alert(conf):
    """오늘 비 소식이 있으면 (제목, 본문, 말할 것) — 없으면 None. 하루 한 번만 봅니다."""
    um = conf.get("alerts", {}).get("umbrella", {})
    if not um.get("enabled", True):
        return None
    if not daily.is_due("umbrella", um.get("at", "07:30"), um.get("catch_up_hours", 3)):
        return None
    daily._mark("umbrella", datetime.date.today().isoformat())   # 먼저 넘기고 시작합니다

    import weather
    try:
        prob, rain, sky, label = weather.rain_today(conf)
    except Exception:
        return None            # 날씨가 안 나온 날은 조용히 — 내일 다시 봅니다

    if prob < um.get("min_prob", 40) and rain < um.get("min_mm", 3):
        return None            # 비 소식이 없으면 아무 말 안 하는 게 이 알림의 미덕입니다

    say = (f"오늘 {label}에 비 소식이 있어요. 강수확률 {prob}퍼센트, {sky}. "
           "나가실 때 우산 챙기세요.")
    body = (f"{label} — {sky}\n강수확률 {prob}%"
            + (f" · 예상 강수 {rain}mm" if rain else "")
            + "\n\n나가실 때 우산을 챙기세요.")
    return ("우산 챙기세요", body, say)


# ── 스케줄러가 부르는 문 ──────────────────────────────────────────
def tick(conf, announce, notify=print):
    """
    notify.py가 1분마다 부릅니다. announce(title, body, say)가 사람에게 전하는 방법입니다.
    한쪽이 죽어도 다른 쪽 알림은 계속되도록 각자 감쌉니다.
    """
    if not conf.get("alerts", {}).get("enabled", True):
        return []
    did = []
    name = conf.get("name") or "루시"

    try:
        for e, start, minutes in _due_events(conf):
            title = e.get("title", "(제목 없음)")
            lead = f"{minutes}분 뒤" if minutes >= 1 else "지금"
            say = f"일정 알림이에요. {lead}, {start.strftime('%H시 %M분')}에 {title}"
            if e.get("where"):
                say += f". 장소는 {e['where']}"
            say += "입니다."
            body = (f"{start.strftime('%H:%M')}  {title}"
                    + (f"\n장소: {e['where']}" if e.get("where") else "")
                    + f"\n\n(캘린더 일정 {lead})")
            announce(f"{name} — 곧 일정", body, say)
            did.append(f"일정 선알림({title})")
    except Exception as e:
        notify(f"  캘린더 선알림 오류: {type(e).__name__}: {e}")

    try:
        found = _umbrella_alert(conf)
        if found:
            title, body, say = found
            announce(f"{name} — {title}", body, say)
            did.append("우산 알림")
    except Exception as e:
        notify(f"  우산 알림 오류: {type(e).__name__}: {e}")

    return did
