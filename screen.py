# -*- coding: utf-8 -*-
"""
화면 캡처 — 루시가 '지금 내 모니터에 떠 있는 것'을 봅니다.

루시에게는 이미 눈(vision.py)이 있지만, 지금까지는 **파일로 저장된 그림**만 볼 수 있었습니다.
그래서 유니티 에러를 물어보려면 사용자가 직접 스샷을 찍어 바탕화면에 저장하고 경로를 적어야 했습니다.
여기서 그 두 걸음을 없앱니다: "지금 화면 좀 봐줘" → 찍어서 → 눈에 그대로 넘김.

⚠️ 도구(TOOLS)로 만들지 않은 이유 — 도구는 **도구 턴**에서 실행되는데,
   그 턴에는 이미지를 실을 수 없습니다(이미지+도구명세를 함께 보내면 거절하는 모델이 있어
   vision을 쓰는 턴은 도구를 끕니다). 도구로 만들면 루시가 화면을 '찍고' 경로만 받은 채
   **정작 보지는 못하는** 반쪽이 됩니다. 그래서 respond()의 '보는 턴' 앞에 붙였습니다.
   (draw/generate_image가 두 갈래로 갈라져 버그가 났던 일과 같은 원칙 — 길은 하나만)

설치할 것 없음: 윈도우 내장 .NET(System.Drawing)을 파워셸로 부릅니다. TTS(speak.ps1)와 같은 방식.
"""
import os
import re
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHOT_DIR = os.path.join(BASE_DIR, "screenshots")
PS1 = os.path.join(BASE_DIR, "screen.ps1")

KEEP = 20          # 화면 캡처는 금방 쌓입니다. 최근 것만 남기고 지웁니다.


def _cfg(config):
    return (config or {}).get("screen", {})


def enabled(config):
    return _cfg(config).get("enabled", True)


# ── 언제 화면을 찍는가 ────────────────────────────────────────────
# '화면'이라는 말은 흔해서(웹 화면, 화면 정의서…) 낱말만 보고 찍으면 오작동합니다.
# 화면을 가리키는 말 + 보라는 말이 **함께** 있을 때만 찍습니다.
_WHAT = r"(?:내|이|지금|현재|여기|모니터의?|활성|앞에 ?있는)?\s*(?:화면|스크린샷|스크린 ?샷|스샷|모니터|창)"
_ACT = r"(?:캡처|캡쳐|찍어|찍고|찍은|봐줘|봐 줘|좀 봐|보고|보여|읽어|확인|무슨|뭐야|뭐가|어때|분석)"
# 사이에 낄 수 있는 말은 **아는 것만** 허용합니다. 아무 글자나 허용하면
# "기획서 화면 구성 어때?"까지 캡처로 오인합니다(화면…어때).
_FILLER = r"(?:좀|다|잘|한번|한 번|둘 다|두 개|전부|모두)?\s*"
_WANT = re.compile(_WHAT + r"[을를이가만]?\s*" + _FILLER + _ACT)

# '화면'이 들어가도 캡처와 무관한 말들.
_NOT = re.compile(r"(화면\s*정의서|화면정의|웹\s*화면|화면\s*캡처\s*기능|스크린샷\s*파일)")

# 맨 앞 창 하나만 / 모니터 전부.
_ACTIVE = re.compile(r"(활성\s*창|이 ?창|앞에 ?있는 ?창|창만|현재 ?창)")
_ALL = re.compile(r"(전체\s*화면|모니터\s*(둘|두|전부|다)|듀얼|양쪽|모든\s*모니터)")


def wants(text):
    """'지금 화면 좀 봐줘' 같은 말인가."""
    text = text or ""
    if _NOT.search(text):
        return False
    return bool(_WANT.search(text))


def mode_for(text):
    """
    무엇을 찍을 것인가.
      active = 맨 앞 창 하나 / all = 모니터 전부 / screen = 맨 앞 창이 있는 모니터 한 대(기본)

    기본이 '모니터 전부'가 아닌 이유: 듀얼이면 가로 3840px가 1920으로 줄면서 모니터당 960px가 되어
    터미널·오류창 글자가 뭉개집니다(실측). 보여주려는 창이 있는 모니터만 찍으면 원본 해상도가 유지됩니다.
    """
    text = text or ""
    if _ACTIVE.search(text):
        return "active"
    if _ALL.search(text):
        return "all"
    return "screen"


def strip_request(text):
    """질문에서 '화면 캡처해서' 같은 지시 부분은 남겨둡니다 — 모델이 맥락으로 삼습니다."""
    return (text or "").strip() or "이 화면을 설명해줘."


# ── 실제로 찍기 ───────────────────────────────────────────────────
def _prune():
    try:
        shots = sorted(
            (os.path.join(SHOT_DIR, f) for f in os.listdir(SHOT_DIR) if f.endswith(".png")),
            key=os.path.getmtime,
        )
    except OSError:
        return
    for old in shots[:-KEEP]:
        try:
            os.remove(old)
        except OSError:
            pass


def capture(config, mode="screen", delay=None, notify=print):
    """화면을 찍어 PNG 경로를 돌려줍니다(보는 용도). 실패하면 RuntimeError."""
    path, _geom = capture_geom(config, mode=mode, delay=delay, notify=notify)
    return path


def capture_geom(config, mode="screen", delay=None, notify=print):
    """
    화면을 찍어 (PNG 경로, 기하정보)를 돌려줍니다. 실패하면 RuntimeError.

    기하정보 = {"left","top","width","height","img_w","img_h"}
      · left/top  : 찍은 영역의 실제 화면 좌표 (듀얼 모니터면 0이 아닐 수 있습니다)
      · width/height : 찍은 영역의 실제 크기
      · img_w/img_h  : 저장된 PNG 크기 (max_width로 줄었을 수 있습니다)

    **왜 필요한가:** 컴퓨터 조작(computer.py)은 모델이 그림을 보고 "여기를 눌러"라고 하면
    그 좌표로 진짜 마우스를 움직입니다. 그런데 모델이 보는 건 줄어든 PNG이고 마우스가 사는 곳은
    실제 화면입니다. 이 둘을 잇는 환산표가 없으면 4K에서 클릭이 절반쯤 어긋난 곳에 떨어집니다.

    delay: 찍기 전 기다리는 초. **기본값이 0이 아닌 이유** — 터미널에서 루시에게 말을 걸면
    맨 앞에 있는 창은 루시의 검은 콘솔입니다. 바로 찍으면 사용자가 보여주려던 유니티 대신
    루시 자신의 화면을 보게 됩니다. 몇 초 줘서 보여줄 창을 띄우게 합니다.
    (웹 화면에서 폰으로 물을 때는 PC를 건드리지 않으므로 config에서 0으로 낮춰도 됩니다)
    """
    cfg = _cfg(config)
    if delay is None:
        delay = cfg.get("delay", 3)
    os.makedirs(SHOT_DIR, exist_ok=True)

    if delay > 0:
        notify(f"[화면] {delay}초 뒤에 찍습니다 — 보여줄 창을 맨 앞으로 띄우세요")
        time.sleep(delay)

    path = os.path.join(SHOT_DIR, time.strftime("screen_%Y%m%d_%H%M%S.png"))
    cmd = [
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", PS1, "-Out", path,
        "-Mode", mode,
        "-MaxWidth", str(cfg.get("max_width", 1920)),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                              encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"화면을 찍지 못했습니다: {e}")

    if proc.returncode != 0 or not os.path.isfile(path):
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise RuntimeError("화면을 찍지 못했습니다: " + (detail[-1] if detail else "원인 불명"))

    _prune()
    lines = (proc.stdout or "").strip().splitlines()
    notify(f"[화면] 찍었습니다 ({lines[-1] if lines else '?'}, {os.path.getsize(path) // 1024}KB)")
    return path, _geom(lines)


def _geom(lines):
    """screen.ps1이 찍어준 'BOUNDS left top w h' 와 'w x h' 두 줄을 숫자로 옮깁니다."""
    geom = {"left": 0, "top": 0, "width": 0, "height": 0, "img_w": 0, "img_h": 0}
    for line in lines:
        line = line.strip()
        if line.startswith("BOUNDS "):
            try:
                l, t, w, h = (int(v) for v in line.split()[1:5])
                geom.update(left=l, top=t, width=w, height=h)
            except (ValueError, IndexError):
                pass
        elif " x " in line:
            try:
                iw, ih = (int(v.strip()) for v in line.split(" x ", 1))
                geom.update(img_w=iw, img_h=ih)
            except ValueError:
                pass
    return geom
