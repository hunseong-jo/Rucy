# -*- coding: utf-8 -*-
"""
화면 지켜보기 — "이 작업 끝나면 알려줘"

유니티 빌드, 대용량 다운로드, 학습 진행바처럼 **화면으로만 알 수 있는 일**의 끝을
루시가 대신 기다립니다. 눈(vision)과 화면 캡처(screen.py)를 재활용합니다:

    interval초마다: 화면을 찍는다 → 눈 달린 두뇌가 '조건이 이루어졌나' 판정
    → 이루어지면 소리+창으로 알리고 끝. max_minutes가 지나면 못 봤다고 알리고 끝.

지켜보는 동안 루시 창은 자유롭습니다 — 감시는 떼어낸 별도 프로세스(pythonw)가 합니다.
한 번에 하나만 지켜봅니다(여럿이면 어느 알림이 어느 일인지 헷갈리고 한도도 겹으로 씁니다).

⚠️ 판정은 눈 달린 두뇌만 씁니다(computer.py와 같은 이유 — 눈 없는 모델은 화면을
   조용히 무시하고 지어냅니다). 오탐 방지로 done이 나오면 몇 초 뒤 한 번 더 보고
   **두 번 연속**일 때만 알립니다(한 번의 헛것에 빌드 알림이 오작동하지 않게).
"""
import argparse
import ctypes
import datetime
import json
import os
import re
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "memory", "watch.json")

# "빌드 끝나면 알려줘" 같은 자연스러운 말. 좁게 잡습니다 —
# 오발동하면 한 시간짜리 화면 감시가 시작되므로, 걸려도 시작 전에 y/N을 한 번 묻습니다.
TRIGGER = re.compile(r"(끝나면|끝났으면|다 ?되면|다 ?끝나면|완료되면|완료 ?하면)"
                     r".{0,15}?(알려|말해|깨워|알림)")


def wants(text):
    """'~ 끝나면 알려줘' 같은 말인가."""
    return bool(TRIGGER.search(text or ""))


def _read():
    try:
        with open(STATE_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def _alive(pid):
    """그 프로세스가 아직 살아 있는가(윈도우). PID가 재사용됐을 수도 있지만 감시용으로는 충분합니다."""
    if not pid:
        return False
    SYNCHRONIZE = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
    if not handle:
        return False
    ended = ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0   # WAIT_OBJECT_0
    ctypes.windll.kernel32.CloseHandle(handle)
    return not ended


# ── 루시 창에서 부르는 것들 ───────────────────────────────────────
def start(config, what):
    """감시 프로세스를 떼어서 띄웁니다. 사람에게 보여줄 안내문을 돌려줍니다."""
    cfg = config.get("watch", {})
    if not cfg.get("enabled", True):
        return "화면 지켜보기가 설정에서 꺼져 있습니다(watch.enabled)."
    import vision
    if not vision.capable(config):
        # 눈 없는 두뇌로 지켜보면 화면을 무시하고 지어냅니다 — 시작조차 하지 않습니다.
        return "눈 달린 두뇌가 없어 화면을 볼 수 없습니다. '/벤치'로 눈 명단을 갱신해 보세요."

    state = _read()
    if _alive(state.get("pid")):
        return f"이미 지켜보는 중입니다: \"{state.get('what')}\" — 멈추려면 /감시 중지"

    exe = sys.executable
    quiet = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(quiet):
        exe = quiet                      # 창 없는 파이썬 — 감시가 검은 창을 띄우면 그게 화면에 찍힙니다
    DETACHED, NO_WINDOW = 0x00000008, 0x08000000
    proc = subprocess.Popen([exe, os.path.join(BASE_DIR, "watch.py"), "--what", what],
                            creationflags=DETACHED | NO_WINDOW, cwd=BASE_DIR)

    # 자식이 자기 상태를 적기 전에 '/감시'나 두 번째 start가 들어와도 헛보지 않게 먼저 적어둡니다.
    _write({"pid": proc.pid, "what": what,
            "started": datetime.datetime.now().strftime("%H:%M")})

    interval = cfg.get("interval_sec", 60)
    max_min = cfg.get("max_minutes", 60)
    return (f"지켜보기 시작 — \"{what}\"\n"
            f"  {interval}초마다 화면을 보고, 이루어지면 소리와 창으로 알립니다"
            f" (최대 {max_min}분 · 멈추려면 /감시 중지)")


def stop():
    state = _read()
    pid = state.get("pid")
    if not _alive(pid):
        return "지금 지켜보는 것이 없습니다."
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    state["result"] = "사용자가 중지"
    state["ended"] = datetime.datetime.now().strftime("%H:%M")
    _write(state)
    return f"멈췄습니다 — \"{state.get('what')}\""


def status_text():
    state = _read()
    if not state:
        return "지켜본 기록이 없습니다. 시작하려면: /감시 <무엇이 되면>"
    alive = _alive(state.get("pid"))
    lines = [("지켜보는 중" if alive else "끝남")
             + f" — \"{state.get('what')}\" (시작 {state.get('started', '?')})"]
    last = state.get("last")
    if last:
        lines.append(f"  마지막 확인 {last.get('at')}: "
                     + ("이루어짐" if last.get("done") else "아직")
                     + (f" — {last.get('seen')}" if last.get("seen") else ""))
    if not alive and state.get("result"):
        lines.append(f"  결과: {state['result']}")
    if alive:
        lines.append("  멈추려면: /감시 중지")
    return "\n".join(lines)


# ── 감시 프로세스 본체 ────────────────────────────────────────────
JUDGE_PROMPT = """지금 컴퓨터 화면을 찍은 것이다. 다음 조건이 이루어졌는지 판단하라.

[조건] {what}

- 화면에서 실제로 본 것으로만 판단하라. 추측 금지.
- 진행 중이거나, 불확실하거나, 관련 화면이 안 보이면 done은 false다.
- 확실히 이루어진 것이 **보일 때만** true다.

JSON 하나만 출력하라: {{"done": true/false, "seen": "화면에서 본 것 한 줄"}}"""


def check_once(config, what):
    """화면을 한 번 보고 (이루어졌나, 본 것). 찍기나 판정이 실패하면 None."""
    import agent
    import screen
    import vision
    from worker import json_from
    try:
        shot = screen.capture(config, mode=config.get("watch", {}).get("mode", "screen"),
                              delay=0, notify=lambda m: None)
        msg = vision.user_message(JUDGE_PROMPT.format(what=what), [shot])
        message, _used, _entry = agent.call_model(config, [msg], use_tools=False,
                                                  order=vision.capable(config))
        data = json_from(message.get("content") or "")
        if not isinstance(data, dict) or "done" not in data:
            return None
        return bool(data.get("done")), str(data.get("seen") or "")[:200]
    except Exception:
        return None


def _announce(config, title, body, say, silent=False):
    if silent:
        print(f"[{title}] {say}")
        return
    import notify
    notify.speak_and_show(config, title, body, say)


def run(config, what, interval, max_minutes, silent=False):
    """감시 루프. 끝나는 길은 셋뿐입니다 — 이루어짐 / 시간 초과 / 확인 실패 누적."""
    name = config.get("name") or "루시"
    started = datetime.datetime.now()
    deadline = started + datetime.timedelta(minutes=max_minutes)
    state = {"pid": os.getpid(), "what": what, "started": started.strftime("%H:%M")}
    _write(state)

    fails = 0
    while datetime.datetime.now() < deadline:
        got = check_once(config, what)
        now = datetime.datetime.now().strftime("%H:%M")

        if got is None:
            fails += 1
            if fails >= 5:
                # 두뇌 한도 소진 등으로 계속 실패하면 조용히 헛돌지 말고 알리고 끝냅니다 —
                # 사용자는 '지켜보고 있다'고 믿고 자리를 비웠을 수 있습니다.
                # 마지막 관찰이 '이루어짐'이었다면 그것도 전합니다(더블체크 직전에 한도가
                # 마르면 다 봐놓고 입을 다무는 꼴이 됩니다 — 실제로 겪음).
                hint, hint_say = "", ""
                if state.get("last", {}).get("done"):
                    hint = f"\n마지막 확인 때는 이루어진 것처럼 보였습니다: {state['last'].get('seen', '')}"
                    hint_say = " 다만 마지막으로 봤을 때는 끝난 것처럼 보였으니 화면을 확인해 보세요."
                state.update(result="확인 실패가 잦아 중단(두뇌 한도일 수 있음)" + hint, ended=now)
                _write(state)
                _announce(config, f"{name} — 지켜보기 중단",
                          f"\"{what}\"\n\n화면 확인이 계속 실패해 지켜보기를 중단했습니다.{hint}\n"
                          "('/상태'로 두뇌 한도를 확인해 보세요)",
                          "죄송해요, 지켜보던 일을 확인할 수 없어 멈췄어요." + hint_say, silent)
                return "fail"
        else:
            fails = 0
            done, seen = got
            state["last"] = {"at": now, "done": done, "seen": seen}
            _write(state)
            if done:
                # 오탐 방지 — 잠깐 뒤 한 번 더 보고 두 번 연속일 때만 알립니다.
                time.sleep(config.get("watch", {}).get("recheck_sec", 5))
                again = check_once(config, what)
                if again and again[0]:
                    state.update(result="이루어짐: " + (again[1] or seen), ended=now)
                    _write(state)
                    _announce(config, f"{name} — 기다리던 일",
                              f"{what}\n\n화면에서 확인했습니다: {again[1] or seen}",
                              f"기다리시던 일이 끝난 것 같아요. {again[1] or seen}", silent)
                    return "done"
                # 두 번째 확인에서 뒤집혔으면 헛것 — 계속 지켜봅니다.
        time.sleep(interval)

    state.update(result=f"{max_minutes}분 안에 이루어지지 않음",
                 ended=datetime.datetime.now().strftime("%H:%M"))
    _write(state)
    _announce(config, f"{name} — 지켜보기 종료",
              f"\"{what}\"\n\n{max_minutes}분 동안 지켜봤지만 이루어지는 것을 보지 못했습니다.",
              f"{int(max_minutes)}분 동안 지켜봤는데 아직인 것 같아요. 필요하면 다시 시켜주세요.",
              silent)
    return "timeout"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--what", required=True)
    parser.add_argument("--interval", type=float, default=None)
    parser.add_argument("--max-minutes", type=float, default=None)
    parser.add_argument("--silent", action="store_true")   # 시험용 — 창·소리 대신 print
    args = parser.parse_args()

    import agent
    config = agent.load_config()
    cfg = config.get("watch", {})
    run(config, args.what,
        interval=args.interval or cfg.get("interval_sec", 60),
        max_minutes=args.max_minutes or cfg.get("max_minutes", 60),
        silent=args.silent)


if __name__ == "__main__":
    main()
