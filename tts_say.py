# -*- coding: utf-8 -*-
"""
말하는 일꾼 — 별도 프로세스로 떠서 소리를 내고 끝나면 죽습니다.

tts.py(부모)는 이 파일을 프로세스로 띄우기만 하고 곧장 프롬프트로 돌아갑니다.
멈출 때는 부모가 이 프로세스를 통째로 죽입니다(그래서 소리가 즉시 끊깁니다).

엔진은 두뇌 6단과 같은 사상으로 **차례로 시도**합니다.
    google : 온라인 신경망 목소리(부드러움). 키 불필요·pip 불필요.
    sapi   : 윈도우 내장 Heami(딱딱하지만 오프라인·전송 0).
앞엔진이 실패하면(인터넷 없음 등) 조용히 다음 엔진이 받습니다.
나중에 로컬 신경망 엔진이 생기면 여기에 함수 하나 + 목록 한 줄로 끼워 넣습니다.
"""
import array
import ctypes
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import wave

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPEAK_PS1 = os.path.join(BASE_DIR, "speak.ps1")


def scale_wav(data, volume):
    """WAV(16bit PCM)의 소리 크기를 volume/100배로 — 0=무음, 100=원음, 100초과=증폭(넘치면 클립).

    MCI는 이 PC의 waveaudio에서 볼륨 조절을 지원하지 않아(setaudio err 261), 주력 목소리
    (melo, WAV)는 샘플을 직접 키우고 줄입니다. 증폭도 되지만 원음이 너무 크면 클립될 수 있습니다.
    실패하면 원음 그대로 돌려줍니다(볼륨 하나 때문에 목소리를 잃지 않게).
    """
    if volume == 100:
        return data
    try:
        with wave.open(io.BytesIO(data), "rb") as rf:
            params = rf.getparams()
            if params.sampwidth != 2:                 # 16bit만 — 아니면 원음 그대로
                return data
            frames = rf.readframes(rf.getnframes())
        f = max(0, volume) / 100.0
        try:
            import audioop                             # C 구현(빠름) — 3.13에서 사라질 예정
            scaled = audioop.mul(frames, 2, f)         # 넘치면 알아서 클립
        except Exception:
            samples = array.array("h")
            samples.frombytes(frames)
            for i in range(len(samples)):             # 폴백: 순수 파이썬(클램프)
                v = int(samples[i] * f)
                samples[i] = -32768 if v < -32768 else 32767 if v > 32767 else v
            scaled = samples.tobytes()
        out = io.BytesIO()
        with wave.open(out, "wb") as wf:
            wf.setparams(params)
            wf.writeframes(scaled)
        return out.getvalue()
    except Exception:
        return data

GOOGLE_LIMIT = 180      # 구글 TTS는 한 번에 200자쯤이 한계 — 넘기면 잘려서 돌아옵니다


# ─────────────────────────────── 소리 재생 (mp3) ───────────────────────────────

def _mci(command):
    buf = ctypes.create_unicode_buffer(255)
    err = ctypes.windll.winmm.mciSendStringW(command, buf, 254, None)
    return err, buf.value


def play_audio(path, volume=100):
    """윈도우 내장 MCI로 재생합니다(ctypes만 — 재생기 설치 불필요).

    'wait'라서 다 들려줄 때까지 여기서 멈춰 있습니다. 부모가 이 프로세스를 죽이면
    소리도 그 자리에서 끊깁니다 — 그게 사용자가 엔터를 쳤을 때 기대하는 동작입니다.

    volume(0~100)은 **이 재생만의** 크기입니다(시스템 전체 볼륨은 안 건드림).
    MCI는 원음 대비 0~100%로 **줄이는** 것만 됩니다(원음보다 더 키우진 못함 —
    그건 윈도우/장치 볼륨을 올려야 합니다). setaudio가 안 먹는 장치면 조용히 무시합니다.
    """
    kind = "waveaudio" if path.lower().endswith(".wav") else "mpegvideo"
    alias = "lucytts%d" % os.getpid()
    _mci(f'close {alias}')
    err, _ = _mci(f'open "{path}" type {kind} alias {alias}')
    if err:
        raise RuntimeError(f"재생 실패(MCI {err})")
    try:
        lvl = max(0, min(int(volume), 100)) * 10        # MCI는 0~1000 (1000=원음 그대로)
        _mci(f'setaudio {alias} volume to {lvl}')        # best-effort — 실패해도 그냥 재생
        _mci(f'play {alias} wait')
    finally:
        _mci(f'close {alias}')


def stream_speak(chunks, fetch, ext, tmpdir, conf):
    """덩이를 **받아오면서 동시에 재생**합니다 — 다 받고 나서 틀면 앞부분이 그만큼 늦습니다.

    첫 덩이는 여기서 직접 받습니다. 여기서 실패하면 아직 아무 소리도 안 났으므로
    깨끗하게 다음 엔진으로 넘길 수 있습니다(예외를 그대로 올립니다).
    """
    first = fetch(chunks[0])

    rest = [None] * len(chunks)
    ready = [threading.Event() for _ in chunks]
    failed_from = [len(chunks)]     # 중간에 끊기면 그 뒤는 윈도우 목소리가 이어받습니다

    def fetch_rest():
        for i in range(1, len(chunks)):
            try:
                rest[i] = fetch(chunks[i])
            except Exception:
                failed_from[0] = min(failed_from[0], i)
                ready[i].set()
                break
            ready[i].set()

    if len(chunks) > 1:
        threading.Thread(target=fetch_rest, daemon=True).start()

    for i, chunk in enumerate(chunks):
        if i == 0:
            data = first
        else:
            ready[i].wait(60)
            if i >= failed_from[0] or rest[i] is None:
                speak_sapi(" ".join(chunks[i:]), conf)   # 남은 말은 잃지 않습니다
                return
            data = rest[i]
        vol = int(conf.get("volume", 100))
        if ext == ".wav":
            data = scale_wav(data, vol)          # 주력(melo, WAV)은 샘플을 직접 키우고 줄임
        path = os.path.join(tmpdir, f"say{i}{ext}")
        with open(path, "wb") as f:
            f.write(data)
        play_audio(path, vol)                    # mp3(구글)는 여기서 MCI setaudio best-effort


# ─────────────────────────────── 엔진 1: 구글(온라인) ───────────────────────────────

def split_chunks(text, limit=GOOGLE_LIMIT):
    """긴 답을 문장 경계로 자릅니다. 문장 중간에서 자르면 어색하게 끊깁니다."""
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?…])\s+", text):
        while len(sent) > limit:                    # 한 문장이 통째로 길면 쉼표·띄어쓰기에서
            cut = sent.rfind(",", 0, limit)
            if cut < 40:
                cut = sent.rfind(" ", 0, limit)
            if cut < 40:
                cut = limit - 1
            parts.append(sent[:cut + 1].strip())
            sent = sent[cut + 1:].lstrip()
        if not sent:
            continue
        if len(cur) + len(sent) + 1 <= limit:
            cur = (cur + " " + sent).strip()
        else:
            if cur:
                parts.append(cur)
            cur = sent
    if cur:
        parts.append(cur)
    return parts


def google_mp3(text, lang, timeout):
    q = urllib.parse.urlencode(
        {"ie": "UTF-8", "q": text, "tl": lang, "client": "tw-ob"}
    )
    req = urllib.request.Request(
        "https://translate.google.com/translate_tts?" + q,
        headers={"User-Agent": "Mozilla/5.0"},      # 없으면 거절당합니다
    )
    data = urllib.request.urlopen(req, timeout=timeout).read()
    if len(data) < 500:
        raise RuntimeError("빈 음성이 돌아왔습니다")
    return data


def speak_google(text, conf, tmpdir):
    gconf = conf.get("google", {}) or {}
    lang = gconf.get("lang", "ko")
    timeout = int(gconf.get("timeout", 10))
    stream_speak(
        split_chunks(text),
        lambda t: google_mp3(t, lang, timeout),
        ".mp3", tmpdir, conf,
    )


# ─────────────────── 엔진 0: 로컬 신경망(MeloTTS) — 오프라인·전송 0 ───────────────────
#
# 목소리를 내는 무거운 일(torch)은 루시 밖의 별도 서비스가 합니다(tts_local_server.py).
# 여기서는 그 서버에 글을 보내고 소리를 받아올 뿐이라, 루시 본체는 "pip 없음"을 지킵니다.
# 서버가 꺼져 있으면 연결이 즉시 실패하고 → 구글 → 윈도우 순으로 조용히 내려갑니다.

def melo_wav(text, url, timeout):
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"},
    )
    data = urllib.request.urlopen(req, timeout=timeout).read()
    if len(data) < 500:
        raise RuntimeError("빈 음성이 돌아왔습니다")
    return data


def front_load(chunks, first_limit):
    """첫 덩이만 짧게 끊습니다.

    로컬 합성은 글자수에 비례해 시간이 듭니다(대략 0.15초/자). 첫 덩이가 길면 말이 시작되기
    전에 그만큼 기다려야 합니다. 반면 뒷 덩이는 앞 덩이가 재생되는 동안 만들어지므로
    (합성이 재생보다 1.3배 빠름) 길어도 끊기지 않습니다. → 앞은 짧게, 뒤는 길게.
    """
    if not chunks or len(chunks[0]) <= first_limit:
        return chunks
    head = chunks[0]
    cut = max(head.rfind(",", 0, first_limit), head.rfind(" ", 0, first_limit))
    if cut < 10:
        cut = first_limit - 1
    return [head[:cut + 1].strip(), head[cut + 1:].strip()] + chunks[1:]


def speak_melo(text, conf, tmpdir):
    """
    ⭐첫 덩이만 짧게 기다립니다(first_timeout) — 나머지는 넉넉히(timeout).

    왜: 서버는 켜질 때 예열을 마치고 _ready를 켭니다. 그런데 몇 시간 아무도 말을 안
    시키면 **윈도우가 그 프로세스의 작업집합을 통째로 디스크로 내보냅니다**(2026-07-23
    실측: 커밋 3.28GB인데 상주 35MB). 이때 첫 요청은 3GB를 도로 읽어들이느라 **79.7초**가
    걸렸고, timeout이 120이라 구글로 내려가지도 못한 채 그 시간을 통째로 기다렸습니다.
    예열을 한 번 더 붙여도 소용없습니다 — 예열이 없어서가 아니라 예열해 둔 것이 쫓겨나서니까요.

    그래서 첫 덩이만 일찍 포기하고 구글이 말하게 합니다. 이때 **서버 쪽 합성은 계속 돌아가
    페이지가 도로 올라오므로**, 바로 다음 마디부터는 다시 로컬 목소리로 돌아옵니다.
    (뒷 덩이는 앞이 재생되는 동안 만들어지므로 짧게 잡을 이유가 없습니다 — 넉넉히 둡니다.)
    """
    mconf = conf.get("melo", {}) or {}
    url = mconf.get("url", "http://127.0.0.1:8767/tts")
    timeout = int(mconf.get("timeout", 120))
    first_timeout = int(mconf.get("first_timeout", 20)) or timeout   # 0이면 옛 동작(끄기)
    chunks = split_chunks(text, int(mconf.get("chunk", 150)))
    chunks = front_load(chunks, int(mconf.get("first_chunk", 30)))

    # stream_speak은 첫 덩이를 **동기로 먼저** 받고 그 뒤에야 나머지를 스레드로 받습니다
    # (그 순서 덕분에 이 셈이 어긋나지 않습니다).
    seen = [0]

    def fetch(t):
        seen[0] += 1
        return melo_wav(t, url, first_timeout if seen[0] == 1 else timeout)

    stream_speak(chunks, fetch, ".wav", tmpdir, conf)


# ─────────────────────────────── 엔진 2: 윈도우 내장(오프라인) ───────────────────────────────

def speak_sapi(text, conf):
    # 한글을 명령줄로 넘기면 깨집니다 — UTF-8 파일에 써서 경로만 넘깁니다.
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="lucy_say_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", SPEAK_PS1,
             "-TextFile", path,
             "-Voice", str(conf.get("voice", "")),
             "-Rate", str(int(conf.get("rate", 0))),
             "-Volume", str(int(conf.get("volume", 100)))],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


ENGINES = {
    "melo":   speak_melo,                                       # 로컬 신경망 (오프라인·전송 0)
    "google": speak_google,                                     # 온라인 신경망
    "sapi":   lambda text, conf, tmpdir: speak_sapi(text, conf),  # 윈도우 내장 (최후의 보루)
}


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        job = json.load(f)
    text, conf = job["text"], job["tts"]
    engines = job["engines"]

    tmpdir = tempfile.mkdtemp(prefix="lucy_tts_")
    try:
        for name in engines:
            engine = ENGINES.get(name)
            if not engine:
                continue
            try:
                engine(text, conf, tmpdir)
                return
            except Exception:
                continue        # 조용히 다음 엔진 — 읽어주기 하나 때문에 대화를 어지럽히지 않습니다
    finally:
        for f_ in os.listdir(tmpdir):
            try:
                os.remove(os.path.join(tmpdir, f_))
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass


if __name__ == "__main__":
    main()
