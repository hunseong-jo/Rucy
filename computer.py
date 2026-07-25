# -*- coding: utf-8 -*-
"""
컴퓨터 조작 — 루시에게 손을 달아줍니다.

루시에게는 이미 눈이 있습니다(screen.py로 찍고 vision.py로 봅니다). 그런데 지금까지는
보고 **말만** 할 수 있었습니다. "저 빨간 버튼 눌러줘"는 못 합니다. 여기서 손을 붙입니다.

    [화면을 찍는다] → [모델이 보고 '다음 한 동작'을 정한다] → [실제로 마우스·키보드가 움직인다]
                              ↑                                              │
                              └──────────── 바뀐 화면을 다시 찍어 ←───────────┘

일꾼 모드(worker.py)와 닮았지만 다릅니다. 일꾼은 **도구**로 일하고, 이쪽은 **화면**으로 일합니다.
도구가 없는 프로그램(유니티 에디터, 웹사이트, 그림판)에도 손이 닿는다는 게 차이입니다.

⚠️ 설계에서 중요한 세 가지 — 다른 기능과 달리 이건 **되돌릴 수 없는 일**을 합니다.

1. 좌표 환산. 모델이 보는 건 1920px로 줄어든 PNG이고, 마우스가 사는 곳은 진짜 화면입니다.
   듀얼 모니터면 원점도 (0,0)이 아닙니다. screen.capture_geom()이 주는 환산표로 되돌립니다.
   (이걸 빼면 4K에서 클릭이 절반쯤 어긋난 곳에 떨어집니다)

2. 한 번에 한 동작. "클릭하고 타이핑하고 저장해"를 한 번에 시키면 모델은 화면을 안 보고
   상상으로 계획을 세웁니다. 매 동작 뒤에 다시 찍어서 보게 하면, 창이 안 떴다는 걸 스스로 압니다.

3. 확인 게이트. 시작할 때 무엇을 할지 말하고 사람의 허락을 받습니다. 그리고 **웹 화면에서는
   아예 막습니다**(tools.CONFIRM을 거부로 갈아끼운 것과 같은 이유 — 폰에서 원격으로 내 PC의
   마우스를 휘두르게 두지 않습니다. 화면 앞에 사람이 없으면 잘못 눌러도 못 멈춥니다).
"""
import os
import re
import subprocess
import time

import screen
import vision
from worker import json_from   # 모델 답변에서 JSON만 안전하게 뽑기 (괄호 짝 세기)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PS1 = os.path.join(BASE_DIR, "input.ps1")

# 사용자가 이 기능을 부르는 말. 넓게 잡으면 평범한 질문이 마우스질로 끌려가므로 좁게 둡니다.
# '/컴퓨터'가 확실한 방법이고, 자연스러운 말은 '대신 눌러/조작해' 정도만 받습니다.
TRIGGER = re.compile(
    r"^\s*/(컴퓨터|조작|pc)\b"
    r"|대신\s*(눌러|클릭|조작|해줘\s*컴퓨터)"
    r"|(마우스|키보드)로\s*(조작|눌러)"
    r"|화면을?\s*(조작|눌러)",
    re.I,
)

# 모델이 고를 수 있는 동작들. 여기 없는 건 실행하지 않습니다(모델이 지어낸 동작명 차단).
ACTIONS = {
    "click": "마우스 왼쪽 클릭 (x, y 필요)",
    "doubleclick": "더블클릭 (x, y 필요)",
    "rightclick": "오른쪽 클릭 (x, y 필요)",
    "move": "마우스만 옮기기 (x, y 필요)",
    "type": "글자 입력 — 지금 커서가 있는 칸에 넣습니다 (text 필요)",
    "keys": "특수키·단축키. {ENTER} {TAB} {ESC} {F5} ^c(Ctrl+C) ^s(Ctrl+S) %{F4}(Alt+F4) (text 필요)",
    "drag": "끌어다 놓기 — (x,y)를 누른 채 (x2,y2)까지 끌고 가서 놓습니다 (x, y, x2, y2 필요)",
    "scroll": "스크롤. amount 양수=위, 음수=아래 (예: -3)",
    "open": "프로그램이나 웹주소 열기 (text: notepad, https://... )",
    "wait": "잠깐 기다렸다 화면을 다시 봅니다 (프로그램이 뜨는 중일 때)",
    "done": "목표를 달성했습니다. 무엇을 했는지 say에 적으세요",
    "give_up": "더는 진행할 수 없습니다. 이유를 say에 적으세요",
}

# 실행 자체를 거부하는 말들. 모델이 아무리 그럴듯하게 굴어도 코드가 막습니다.
# (프롬프트로 '하지 마라'라고 부탁하는 것은 방어가 아닙니다 — 모델은 부탁을 잊습니다)
FORBIDDEN = re.compile(
    r"(format\s+[a-z]:|rm\s+-rf|del\s+/[sf]|shutdown|Remove-Item.*-Recurse|"
    r"diskpart|reg\s+delete|vssadmin)",
    re.I,
)

STEP_PROMPT = """너는 사용자의 컴퓨터를 직접 조작하는 비서다. 지금 **화면 그림**을 보고 있다.

[사용자가 시킨 일]
{goal}

[지금 맨 앞에 있는 창 — type·keys로 넣는 글자는 **여기로** 들어간다]
{front}

[지금까지 한 동작]
{history}

⚠️ 글자를 넣기 전에 위의 '맨 앞 창'을 확인하라. 글을 넣어야 할 프로그램이 아니라면
   **절대 type/keys를 쓰지 마라** — 엉뚱한 창(채팅창 등)에 글이 들어간다.
   그 창을 먼저 열거나(open) 클릭해서 맨 앞으로 가져온 뒤에 넣어라.

이 화면을 보고 **다음 한 동작**만 정하라. 여러 동작을 한 번에 계획하지 마라 —
한 번 움직일 때마다 화면을 다시 찍어 보여줄 테니, 그때 다음을 정하면 된다.

쓸 수 있는 동작:
{actions}

좌표(x, y)는 **네가 보고 있는 이 그림의 픽셀 좌표**로 적어라(왼쪽 위가 0,0).
누를 것의 **한가운데**를 찍어라. 그림에 안 보이는 것은 좌표를 지어내지 마라 —
안 보이면 스크롤하거나(scroll), 그 창을 먼저 열어라(open).

이미 목표가 달성돼 보이면 done을 골라라. 화면이 예상과 다르면 지어내지 말고
give_up으로 무엇이 막혔는지 알려라.

'지금까지 한 동작'에 **⚠ 실패**가 적혀 있으면 같은 동작을 그대로 반복하지 마라 —
실패 이유를 읽고 원인부터 풀어라(예: "창이 바뀌었습니다" 실패면 글을 넣을 창을
먼저 클릭해 맨 앞으로 가져온 뒤 다시 넣어라).

JSON 하나만 출력하라. 설명·코드펜스 금지.
{{"action": "동작", "x": 숫자, "y": 숫자, "x2": 숫자, "y2": 숫자(drag만), "text": "글", "amount": 숫자, "why": "왜 이걸 누르는지 한 줄", "say": "done/give_up일 때만"}}"""


def enabled(config):
    return config.get("computer", {}).get("enabled", True)


def wants(text):
    return bool(TRIGGER.search(text or ""))


def strip_request(text):
    return re.sub(r"^\s*/(컴퓨터|조작|pc)\b[:\s]*", "", text or "", flags=re.I).strip()


# ── 좌표 환산: 그림 픽셀 → 진짜 화면 ─────────────────────────────
def to_screen(x, y, geom):
    """
    모델이 그림에서 찍은 (x, y)를 실제 마우스 좌표로 옮깁니다.

    그림은 max_width로 줄어들어 있고(4K면 절반), 듀얼 모니터면 원점도 0이 아닙니다.
    둘 다 되돌리지 않으면 클릭이 엉뚱한 곳에 떨어집니다.
    """
    img_w = geom.get("img_w") or geom.get("width") or 1
    scale = (geom.get("width") or img_w) / img_w        # 줄어든 배율을 되돌립니다
    real_x = geom.get("left", 0) + int(round(x * scale))
    real_y = geom.get("top", 0) + int(round(y * scale))

    # 찍은 영역 밖으로 나가는 좌표는 잘라냅니다. 모델이 그림 밖 좌표를 뱉으면
    # (예: 스크롤해야 보이는 것을 상상해서 y=2000) 엉뚱한 모니터를 클릭하게 됩니다.
    left, top = geom.get("left", 0), geom.get("top", 0)
    right = left + (geom.get("width") or 0) - 1
    bottom = top + (geom.get("height") or 0) - 1
    if right > left:
        real_x = max(left, min(right, real_x))
    if bottom > top:
        real_y = max(top, min(bottom, real_y))
    return real_x, real_y


# ── 실제로 움직이기 ───────────────────────────────────────────────
def act(action, x=None, y=None, x2=None, y2=None, text="", amount=0, timeout=30, expect=""):
    """input.ps1을 불러 마우스·키보드를 움직입니다. 실패하면 RuntimeError.

    expect: 타이핑(type/keys)이 들어가야 할 창 제목. input.ps1이 **주입 직전에** 전경 창과
    대조해, 다르면 안 넣고 실패로 던집니다. 모델이 판단한 시점과 손이 움직이는 시점 사이
    (모델 호출 수 초 + 실행 틈)에 알림 팝업이나 사용자 클릭으로 포커스가 바뀌면,
    글자가 엉뚱한 창(채팅창이면 재앙)으로 들어가는 것을 여기서 막습니다.
    """
    cmd = [
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", PS1, "-Action", action,
    ]
    if x is not None and y is not None:
        cmd += ["-X", str(int(x)), "-Y", str(int(y))]
    if x2 is not None and y2 is not None:
        cmd += ["-X2", str(int(x2)), "-Y2", str(int(y2))]
    if text:
        cmd += ["-Text", str(text)]
    if amount:
        cmd += ["-Amount", str(int(amount))]
    if expect:
        cmd += ["-Expect", str(expect)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"{action} 실패: {e}")
    if proc.returncode != 0:
        raise RuntimeError(f"{action} 실패: {_reason(proc)}")
    return (proc.stdout or "").strip()


def _reason(proc):
    """
    파워셸 오류에서 **사람이 읽을 첫 줄**만 뽑습니다.

    마지막 줄을 쓰면 "FullyQualifiedErrorId : InvalidOperationException,Microsoft.PowerShell..."
    같은 내부 딱지가 나옵니다. 진짜 이유("필요한 파일을 찾을 수 없습니다")는 맨 앞에 있고,
    이 문장은 모델에게 그대로 넘어가 다음 동작을 정하는 근거가 되므로 중요합니다.
    """
    text = (proc.stderr or proc.stdout or "").strip()
    for line in text.splitlines():
        line = line.strip()
        # '+ CategoryInfo', '+ FullyQualifiedErrorId', '+ $proc = ...' 같은 부속 줄은 건너뜁니다.
        if line and not line.startswith("+") and "위치 줄:" not in line:
            return line[:200]
    return "원인 불명"


# ── 모델이 고른 동작을 안전하게 다듬기 ────────────────────────────
def front_window():
    """
    지금 키보드 입력이 들어갈 창의 제목. 못 알아내면 "".

    **왜 필요한가:** type/keys는 '지금 포커스가 있는 창'에 글을 넣습니다. 열려던 프로그램이
    아직 안 떴으면 글이 **직전 창**으로 들어갑니다(실제로 겪음). 그게 채팅창이면 큰일이므로,
    매 턴 모델에게 "지금 글자는 여기로 간다"를 보여주고 스스로 멈추게 합니다.
    """
    try:
        out = act("title")
    except RuntimeError:
        return ""
    for line in out.splitlines():
        if line.startswith("TITLE "):
            return line[6:].strip()
    return ""


def _decide(config, call_model, goal, shot, history, notify, front=""):
    """화면을 보여주고 다음 한 동작을 받아옵니다. (동작 dict 또는 None)

    front: 호출한 쪽이 이번 턴에 확인한 전경 창 제목. 모델에게 보여주는 제목과
    실행 직전에 대조할 제목이 **같은 값**이어야 하므로 여기서 다시 재지 않습니다.
    """
    prompt = STEP_PROMPT.format(
        goal=goal,
        front=front or "(알 수 없음)",
        history="\n".join(f"{i}. {h}" for i, h in enumerate(history, 1)) or "(아직 없음)",
        actions="\n".join(f"  - {k}: {v}" for k, v in ACTIONS.items()),
    )
    msgs = [vision.user_message(prompt, [shot])]

    # 눈이 달린 두뇌만. 눈 없는 모델은 그림을 조용히 무시하고 좌표를 **지어냅니다** —
    # 그 좌표로 진짜 마우스가 움직이므로, 여기서만은 절대 폴백하면 안 됩니다.
    eyes = vision.capable(config)
    if not eyes:
        notify("[컴퓨터] 눈이 달린 두뇌가 없습니다 (config의 vision: true 확인)")
        return None

    try:
        # 이미지가 실린 요청에 도구 명세를 함께 실으면 거절하는 모델이 있습니다(비전 턴 규칙).
        message, used, _entry = call_model(config, msgs, use_tools=False, order=eyes)
    except Exception as e:
        notify(f"[컴퓨터] 화면을 판단하지 못했습니다 ({type(e).__name__})")
        return None

    step = json_from(message.get("content"))
    if not isinstance(step, dict):
        notify("[컴퓨터] 두뇌가 동작을 JSON으로 주지 않았습니다")
        return None

    step["_used"] = used
    return step


def _valid(step, notify):
    """모델이 준 동작이 실행해도 되는 것인지. (동작명, 사유) 또는 (None, 사유)"""
    action = str(step.get("action") or "").strip().lower()
    if action not in ACTIONS:
        notify(f"[컴퓨터] 모르는 동작 '{action}' — 멈춥니다")
        return None, f"모르는 동작 '{action}'"

    text = str(step.get("text") or "")
    if text and FORBIDDEN.search(text):
        notify(f"[컴퓨터] 위험한 명령이라 거부했습니다: {text[:60]}")
        return None, "위험한 명령"

    if action in ("click", "doubleclick", "rightclick", "move", "drag"):
        if step.get("x") is None or step.get("y") is None:
            notify(f"[컴퓨터] {action}인데 좌표가 없습니다 — 멈춥니다")
            return None, "좌표 없음"
    if action == "drag" and (step.get("x2") is None or step.get("y2") is None):
        notify("[컴퓨터] drag인데 도착점(x2, y2)이 없습니다 — 멈춥니다")
        return None, "도착점 없음"
    if action in ("type", "keys", "open") and not text:
        notify(f"[컴퓨터] {action}인데 넣을 글이 없습니다 — 멈춥니다")
        return None, "내용 없음"
    return action, ""


def _describe(action, step, sx=None, sy=None, sx2=None, sy2=None):
    """사람이 읽을 한 줄. 화면에도 찍고 다음 턴의 '지금까지 한 동작'에도 들어갑니다."""
    why = str(step.get("why") or "").strip()
    if action == "drag":
        what = f"drag ({sx},{sy}) → ({sx2},{sy2})"
    elif action in ("click", "doubleclick", "rightclick", "move"):
        what = f"{action} ({sx},{sy})"
    elif action in ("type", "keys", "open"):
        what = f"{action} \"{str(step.get('text'))[:40]}\""
    elif action == "scroll":
        what = f"scroll {step.get('amount') or -3}"
    else:
        what = action
    return what + (f" — {why}" if why else "")


# ── 바깥 루프 ─────────────────────────────────────────────────────
def run(config, state, goal, call_model, notify=print, confirm=None, log=None):
    """
    목표 하나를 화면을 보며 손으로 해냅니다. respond()와 같은 (답, 사용한 두뇌)를 돌려줍니다.

    confirm: 시작 허락을 받는 함수. 터미널은 input()으로 묻고, 웹은 무조건 거부합니다.
             None이면 안전한 쪽(거부)으로 갑니다 — 허락 없이 마우스를 움직이지 않습니다.
    """
    conf = config.get("computer", {})
    max_actions = conf.get("max_actions", 12)
    pause = conf.get("pause_sec", 1.0)
    used = "컴퓨터"

    if not goal:
        return ("무엇을 시킬지 함께 적어주세요. 예: /컴퓨터 메모장 열어서 '안녕'이라고 쓰고 "
                "바탕화면에 test.txt로 저장해줘", used)

    if not vision.capable(config):
        return ("눈이 달린 두뇌가 없어서 화면을 볼 수 없습니다. 화면을 못 보면 클릭 좌표를 "
                "지어내게 되므로 시작하지 않았습니다. (config에서 vision: true 확인)", used)

    # 시작 전 허락. 이건 되돌릴 수 없는 일이라, 무엇을 하려는지 먼저 말합니다.
    ask = (f"루시가 마우스·키보드를 직접 움직입니다 (최대 {max_actions}동작):\n"
           f"    \"{goal}\"\n"
           f"  · 글자 입력에는 클립보드를 씁니다(지금 복사해 둔 내용이 바뀝니다)\n"
           f"  · 진행 중에 Ctrl+C를 누르면 즉시 멈춥니다\n"
           f"  시작할까요?")
    if confirm is None or not confirm(ask):
        return "사용자가 거부했습니다. 아무것도 조작하지 않았습니다.", used

    if log:
        log("나", goal)

    history, done_say, gave_up = [], "", ""
    flops = 0                      # 연속 실행 실패 횟수 — 2번이면 접습니다

    for n in range(1, max_actions + 1):
        # 눈: 지금 화면. delay=0 — 사용자가 이미 허락했고, 창을 띄울 시간을 줄 이유가 없습니다
        # (오히려 루시가 스스로 연 창을 찍어야 하므로 기다리면 안 됩니다).
        try:
            shot, geom = screen.capture_geom(config, mode="screen", delay=0,
                                             notify=lambda m: None)
        except RuntimeError as e:
            notify(f"[컴퓨터] {e}")
            gave_up = str(e)
            break

        # 이번 턴의 전경 창 — 모델에게 보여주고, 타이핑 직전 재검증에도 같은 값을 씁니다.
        front = front_window()

        step = _decide(config, call_model, goal, shot, history, notify, front)
        if not step:
            gave_up = "화면을 보고 다음 동작을 정하지 못했습니다"
            break
        used = step.get("_used", used)

        action, why_not = _valid(step, notify)
        if not action:
            gave_up = why_not
            break

        if action == "done":
            done_say = str(step.get("say") or "").strip() or "끝냈습니다."
            notify(f"[컴퓨터 {n}/{max_actions}] 완료 — {done_say}")
            break
        if action == "give_up":
            gave_up = str(step.get("say") or "").strip() or "더 진행할 수 없습니다."
            notify(f"[컴퓨터 {n}/{max_actions}] 중단 — {gave_up}")
            break

        if action == "wait":
            notify(f"[컴퓨터 {n}/{max_actions}] 기다립니다 — {step.get('why') or ''}")
            history.append("wait (화면이 바뀌기를 기다림)")
            time.sleep(max(pause, 1.5))
            continue

        # 손: 실제로 움직입니다.
        sx = sy = sx2 = sy2 = None
        if step.get("x") is not None and step.get("y") is not None:
            sx, sy = to_screen(step["x"], step["y"], geom)
        if action == "drag":
            sx2, sy2 = to_screen(step["x2"], step["y2"], geom)

        line = _describe(action, step, sx, sy, sx2, sy2)
        notify(f"[컴퓨터 {n}/{max_actions}] {line}")

        try:
            act(action, x=sx, y=sy, x2=sx2, y2=sy2,
                text=str(step.get("text") or ""),
                amount=int(step.get("amount") or 0),
                # 타이핑만 검사합니다 — 클릭은 포커스를 바꾸는 게 목적이라 대조가 무의미합니다.
                expect=front if action in ("type", "keys") else "")
        except (RuntimeError, ValueError) as e:
            # 한 동작이 실패해도 통째로 포기하지 않습니다 — 실패를 기록에 남기고 다음 턴의
            # 화면과 함께 모델에게 보여주면, 원인을 풀 수를 스스로 찾습니다(예: 포커스가
            # 바뀌어 타이핑이 거부됐으면 그 창을 클릭한 뒤 다시). 연속 2번 실패면 멈춥니다.
            notify(f"[컴퓨터] {e}")
            history.append(f"{line} → ⚠ 실패: {e}")
            flops += 1
            if flops >= 2:
                gave_up = f"동작이 연속으로 실패했습니다. 마지막 오류: {e}"
                break
            time.sleep(pause)
            continue
        except KeyboardInterrupt:
            gave_up = "사용자가 중간에 멈췄습니다."
            notify("[컴퓨터] 멈췄습니다")
            break

        flops = 0
        history.append(line)
        time.sleep(pause)          # 화면이 반응할 틈. 이게 없으면 바뀌기 전 화면을 찍습니다
    else:
        gave_up = f"{max_actions}동작을 다 쓰고도 끝내지 못했습니다."
        notify(f"[컴퓨터] {gave_up}")

    # 보고. 일꾼 모드와 같은 원칙 — **실패는 코드가 적습니다**. 모델의 말을 믿지 않습니다
    # (안 만든 파일을 만들었다고 보고한 전례가 있습니다).
    if done_say:
        answer = f"{done_say}\n\n한 일 {len(history)}가지:\n" + "\n".join("  · " + h for h in history)
    else:
        answer = f"⚠️ 끝내지 못했습니다 — {gave_up}\n"
        answer += (f"\n여기까지 했습니다 ({len(history)}동작):\n" + "\n".join("  · " + h for h in history)
                   if history else "\n아무 동작도 하지 않았습니다.")

    state["messages"].append({"role": "user", "content": goal})
    state["messages"].append({"role": "assistant", "content": answer})
    state["last_q"], state["last_a"], state["last_images"] = goal, answer, []
    if log:
        log(config.get("name", "루시"), answer)
    return answer, used
