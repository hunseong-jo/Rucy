"""
읽어주기(TTS) — 루시의 답을 소리로 읽습니다. pip 없이 표준 라이브러리만 씁니다.

설계에서 중요한 세 가지:

1. **목소리도 두뇌처럼 갈아끼운다.** 엔진을 차례로 시도합니다(google → sapi).
   구글 신경망 목소리가 부드러워 기본이고, 인터넷이 없거나 실패하면 윈도우 내장
   Heami가 조용히 이어받습니다. `--local`(프라이버시 모드)에서는 읽을 문장이 밖으로
   나가면 안 되므로 온라인 엔진을 아예 뺍니다. 실제로 소리를 내는 일은 tts_say.py.
   ※ 윈도우 내장 목소리만으로는 한계가 분명합니다(Heami는 낡은 엔진). 반대로 로컬
     신경망 한국어 TTS는 실행파일 하나로 끝나는 물건이 없습니다 — Piper의 유일한
     한국어 모델은 발음기호가 달라 중국어처럼 들렸습니다(세션44에 실측하고 폐기).

2. **말은 별도 프로세스에서 한다.** 파이썬이 말이 끝날 때까지 기다리면, 긴 답을
   다 들을 때까지 다음 질문을 못 합니다. 프로세스를 띄워두고 바로 프롬프트로 돌아옵니다.
   멈출 때는 그 프로세스를 죽입니다(엔터 한 번이면 조용해집니다).

3. **화면용 글과 귀로 듣는 글은 다르다.** 코드 블록·URL·표·마크다운 기호를 그대로 읽으면
   "백틱 백틱 파이썬 def 괄호..."가 됩니다. 소리로 의미가 없는 것은 걷어내고 읽습니다.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(BASE_DIR, "speak.ps1")
WORKER = os.path.join(BASE_DIR, "tts_say.py")       # 실제로 소리를 내는 별도 프로세스

_proc = None      # 지금 말하고 있는 프로세스
_tmp = None       # 그 프로세스가 읽고 있는 임시 파일


def _conf(config):
    return config.get("tts", {}) or {}


def enabled(config):
    return bool(_conf(config).get("enabled"))


# ─────────────────────────────── 읽을 수 있는 글로 다듬기 ───────────────────────────────

_URL = re.compile(r"https?://\S+|www\.\S+")
_FENCE = re.compile(r"```.*?```", re.S)
_INDENT_CODE = re.compile(r"^(?: {4}|\t).*$", re.M)
_PATH = re.compile(r"[A-Za-z]:[\\/][^\s,)]+|(?:\.{1,2}[\\/])[^\s,)]+")
_TABLE = re.compile(r"^\s*\|.*\|\s*$", re.M)
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿─-╿]"
)
_MD = re.compile(r"[*_~`#>]|^\s*[-•]\s+", re.M)
_SENT_END = re.compile(r"(?<=[.!?。…])\s|(?<=[다요])\.\s")


def clean(text, config=None):
    """화면용 마크다운을 귀로 들을 수 있는 문장으로 바꿉니다."""
    conf = _conf(config or {})
    t = text or ""

    if conf.get("skip_code", True):
        # 코드를 소리로 읽어봐야 알아들을 수 없습니다. 있었다는 사실만 알립니다.
        if _FENCE.search(t):
            t = _FENCE.sub(" 코드는 화면을 보세요. ", t)
        t = _INDENT_CODE.sub("", t)

    t = _TABLE.sub(" 표는 화면을 보세요. ", t)
    t = _URL.sub(" 링크 ", t)
    t = _PATH.sub(" 경로 ", t)          # 'C:\\Users\\...'를 한 글자씩 읽으면 30초가 사라집니다
    t = _EMOJI.sub(" ", t)
    t = _MD.sub("", t)
    t = re.sub(r"\[(.+?)\]\(.*?\)", r"\1", t)   # [글자](링크) → 글자
    t = re.sub(r"\n{2,}", ". ", t)
    t = re.sub(r"\s+", " ", t).strip()

    # 같은 문구가 반복되면 한 번만 (코드 블록이 여러 개일 때)
    t = re.sub(r"(코드는 화면을 보세요\.\s*)+", "코드는 화면을 보세요. ", t)
    t = re.sub(r"(표는 화면을 보세요\.\s*)+", "표는 화면을 보세요. ", t)

    # 걷어낸 자리에 마침표가 겹치면 SAPI가 그만큼 뜸을 들입니다
    t = re.sub(r"[.\s]*\.[.\s]*\.[.\s]*", ". ", t)
    t = re.sub(r"\s+([.,!?])", r"\1", t).strip(" .")
    if not t:
        return ""       # 코드·표뿐이던 답 — 읽을 것이 없습니다
    t += "."

    limit = int(conf.get("max_chars", 600))
    if len(t) > limit:
        # 문장 중간에 자르면 어색하게 뚝 끊깁니다. 가까운 문장 끝에서 자릅니다.
        head = t[:limit]
        parts = _SENT_END.split(head)
        if len(parts) > 1:
            head = " ".join(parts[:-1])
        t = head.rstrip() + " ... 나머지는 화면을 보세요."
    return t


# ─────────────────────────────── 엔진 고르기 ───────────────────────────────
#
# 두뇌 6단과 같은 사상입니다. 앞엔진이 안 되면 뒤엔진이 받습니다.
#   google : 온라인 신경망 목소리(부드러움) — 읽을 문장이 구글로 전송됩니다.
#   sapi   : 윈도우 내장 Heami — 딱딱하지만 오프라인·전송 0.
# 로컬 신경망 엔진이 생기면 tts_say.ENGINES에 함수 하나 + 이 목록에 이름 하나.

ALL_ENGINES = ("melo", "google", "sapi")
ONLINE = ("google",)            # 읽을 문장이 밖으로 나가는 엔진
ENGINE_KO = {
    "melo": "로컬 신경망(오프라인·부드러움)",
    "google": "구글(온라인·부드러움)",
    "sapi": "윈도우 Heami(오프라인)",
}

_privacy = False        # --local 모드: 무엇도 밖으로 내보내지 않습니다


def privacy_mode(on=True):
    """--local에서 켭니다. 켜지면 config가 뭐라고 하든 온라인 엔진을 쓰지 않습니다."""
    global _privacy
    _privacy = bool(on)


def engines(config):
    """이번 실행에서 실제로 쓸 엔진 순서."""
    want = _conf(config).get("engines") or ["melo", "google", "sapi"]
    want = [e for e in want if e in ALL_ENGINES]
    if _privacy:
        # 프라이버시 모드에서 온라인 엔진을 쓰면 '외부로 전송 안 함'이 거짓말이 됩니다.
        # 로컬 신경망(melo)은 이 PC 안에서만 도므로 여기서도 그대로 씁니다 —
        # 프라이버시 모드라고 목소리까지 딱딱해질 이유는 없습니다.
        want = [e for e in want if e not in ONLINE]
    return want or ["sapi"]


# ─────────────────────────────── 말하기 · 멈추기 ───────────────────────────────

def stop():
    """말하는 중이면 즉시 멈춥니다."""
    global _proc, _tmp
    if _proc and _proc.poll() is None:
        try:
            # 일꾼이 파워셸(윈도우 목소리)을 또 띄웠을 수 있습니다. 자식까지 함께 죽여야
            # 조용해집니다(/T). 그냥 kill()하면 손자가 계속 떠듭니다.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(_proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            pass
        try:
            _proc.kill()
        except OSError:
            pass
    _proc = None
    if _tmp and os.path.exists(_tmp):
        try:
            os.remove(_tmp)
        except OSError:
            pass          # 프로세스가 아직 붙들고 있을 수 있습니다 — 다음 실행 때 어차피 새로 만듭니다
    _tmp = None


def speaking():
    return bool(_proc and _proc.poll() is None)


def speak(text, config):
    """답을 소리로 읽습니다. 기다리지 않고 바로 돌아옵니다."""
    global _proc, _tmp
    if not enabled(config):
        return False

    said = clean(text, config)
    if not said:
        return False

    stop()      # 앞말이 남아 있으면 덮어씁니다(두 목소리가 겹쳐 나오면 알아들을 수 없습니다)

    # 일꾼에게 넘길 지시서. 한글을 명령줄로 넘기면 깨지므로 파일로 넘깁니다.
    fd, path = tempfile.mkstemp(suffix=".json", prefix="lucy_say_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:     # BOM 없이
        json.dump(
            {"text": said, "tts": _conf(config), "engines": engines(config)},
            f, ensure_ascii=False,
        )
    _tmp = path

    try:
        _proc = subprocess.Popen(
            [sys.executable, WORKER, path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),  # 검은 창이 깜빡이지 않게
        )
    except OSError:
        _proc = None
        return False
    return True


def voices():
    """이 PC에 깔린 음성 목록."""
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices()"
        " | ForEach-Object { $_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        if "|" in line:
            name, _, culture = line.partition("|")
            found.append((name.strip(), culture.strip()))
    return found


def pick_voice(needle):
    """이름 일부로 음성을 고릅니다. ('헤미'가 아니라 'Heami'처럼 실제 이름의 일부)"""
    for name, culture in voices():
        if needle.lower() in name.lower():
            return name, culture
    return None, None
