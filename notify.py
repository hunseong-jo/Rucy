# -*- coding: utf-8 -*-
"""
알림 일꾼 — 윈도우 작업 스케줄러가 1분마다 부릅니다. 루시 창이 꺼져 있어도 돕니다.

할 일은 하나입니다: 때가 된 예약을 찾아 (1) 소리로 읽어주고 (2) 화면에 창을 띄웁니다.
때가 된 게 없으면 아무것도 하지 않고 조용히 끝납니다(1분마다 깜빡이면 안 되므로 창 없이 실행).

수동 확인: python notify.py --test
"""
import ctypes
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import daily                                            # noqa: E402
import reminders                                        # noqa: E402
import tts                                              # noqa: E402

MB_OK = 0x0
MB_ICONINFO = 0x40
MB_TOPMOST = 0x40000        # 다른 창 뒤에 숨으면 알림이 아닙니다
MB_SETFOREGROUND = 0x10000


def config():
    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def announce(items, conf):
    name = (conf.get("name") or "루시")
    lines = [f"{i['at'].split()[1]}  {i['what']}" for i in items]
    body = "\n".join(lines)

    # 소리부터. 읽어주기가 꺼져 있어도 알림만큼은 말하게 합니다 — 화면을 안 보고 있을 수 있습니다.
    spoken = conf.setdefault("tts", {})
    spoken["enabled"] = True
    say = "알림이에요. " + ". ".join(i["what"] for i in items)
    tts.speak(say, conf)

    # 창은 사용자가 확인을 누를 때까지 기다립니다(놓치지 않게).
    ctypes.windll.user32.MessageBoxW(
        None, body, f"{name} 알림",
        MB_OK | MB_ICONINFO | MB_TOPMOST | MB_SETFOREGROUND,
    )

    # 말이 아직 끝나지 않았으면 마저 하도록 잠깐 기다립니다(프로세스가 죽으면 소리도 끊깁니다).
    import time
    for _ in range(60):
        if not tts.speaking():
            break
        time.sleep(0.5)


def speak_and_show(conf, title, body, say=None):
    """소리로 읽고 창으로 보여줍니다. (알림도 브리핑도 전달 방법은 같습니다)"""
    import time

    spoken = conf.setdefault("tts", {})
    spoken["enabled"] = True             # 읽어주기가 꺼져 있어도 알림·브리핑은 말합니다
    tts.speak(say or body, conf)

    ctypes.windll.user32.MessageBoxW(
        None, body, title,
        MB_OK | MB_ICONINFO | MB_TOPMOST | MB_SETFOREGROUND,
    )
    # 말이 아직 안 끝났으면 마저 하도록 기다립니다(프로세스가 죽으면 소리도 끊깁니다).
    for _ in range(180):
        if not tts.speaking():
            break
        time.sleep(0.5)


def main():
    conf = config()
    name = conf.get("name") or "루시"

    if "--test" in sys.argv:
        # 진짜 예약을 건드리지 않고 알림 경로만 시험합니다.
        announce([{"at": "2026-01-01 09:00", "what": "시험 알림입니다. 잘 들리고 잘 보이면 성공이에요."}], conf)
        return

    if "--task" in sys.argv:
        # 예약을 기다리지 않고 지시 하나를 지금 시켜봅니다: python notify.py --task "오늘 날짜 알려줘"
        what = sys.argv[sys.argv.index("--task") + 1]
        headline, path = daily.run_task(conf, {"what": what})
        speak_and_show(conf, f"{name} — 예약한 일", f"{what}\n\n{headline}\n\n결과: {path}", say=headline)
        return

    due = reminders.due()
    # 예약은 두 종류입니다. 알림은 문구를 읽어주고, 지시는 루시가 **실제로 그 일을 합니다**.
    alerts = [i for i in due if i.get("kind", "notify") != "task"]
    tasks = [i for i in due if i.get("kind") == "task"]

    if alerts:
        announce(alerts, conf)

    for item in tasks:
        try:
            headline, path = daily.run_task(conf, item)
            body = f"{item['what']}\n\n{headline}\n\n결과를 적어뒀습니다:\n{path}"
        except Exception as e:
            headline = f"예약한 일을 하다가 실패했습니다. {type(e).__name__}"
            body = f"{item['what']}\n\n{headline}\n{e}"
        speak_and_show(conf, f"{name} — 예약한 일", body, say=headline)

    # 상황 알림 — 캘린더 일정이 다가오면(기본 30분 전), 아침에 비 소식이 있으면 먼저 말합니다.
    # 이게 죽어도 예약 알림·새벽 일과는 계속되어야 하므로 따로 감쌉니다.
    try:
        import alerts
        alerts.tick(conf, announce=lambda title, body, say=None:
                    speak_and_show(conf, title, body, say))
    except Exception:
        pass

    # 예약을 보는 김에 '오늘 아직 안 한 일'(아침 브리핑·지식 동기화)도 확인합니다.
    # 때가 아니면 즉시 조용히 끝나므로 1분마다 불려도 부담이 없습니다.
    daily.tick(conf, announce=lambda text: speak_and_show(conf, f"{name} 아침 브리핑", text))


if __name__ == "__main__":
    main()
