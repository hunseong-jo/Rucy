# -*- coding: utf-8 -*-
"""
음성 입력 (말로 시키기)

녹음: 윈도우 기본 기능(winmm.dll)을 ctypes로 직접 호출합니다.
      → 마이크 라이브러리를 따로 설치할 필요가 없습니다(pip 불필요 원칙 유지).
받아쓰기: Groq의 whisper-large-v3 (무료). 네 GTX 1650의 VRAM을 전혀 쓰지 않습니다.

Groq 키가 없으면 음성 기능만 조용히 비활성화되고, 나머지 비서는 그대로 작동합니다.
"""
import ctypes
import json
import os
import threading
import time
import urllib.request
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def _mci(command):
    """윈도우 MCI 명령. 실패하면 오류 메시지를 돌려줍니다."""
    buf = ctypes.create_unicode_buffer(255)
    err = ctypes.windll.winmm.mciSendStringW(command, buf, 254, 0)
    if err:
        msg = ctypes.create_unicode_buffer(255)
        ctypes.windll.winmm.mciGetErrorStringW(err, msg, 254)
        raise RuntimeError(f"녹음 실패: {msg.value} (명령: {command})")
    return buf.value


def record(wav_path, stop_check=None, max_seconds=120):
    """
    마이크 녹음을 시작하고, stop_check()가 True를 돌려줄 때까지 계속합니다.
    stop_check가 없으면 max_seconds 동안 녹음합니다.
    """
    alias = "mic_" + uuid.uuid4().hex[:8]
    _mci(f"open new type waveaudio alias {alias}")
    try:
        # 16kHz 16bit 모노 — Whisper가 쓰는 형식이라 파일이 작고 변환이 필요 없습니다.
        # ⚠️ MCI는 형식을 **온전히** 줘야 합니다(bytespersec·alignment까지). 일부만 주면
        #    "현재 형식으로 녹음할 수 있는 웨이브 장치가 없습니다"로 거부합니다(실측).
        try:
            _mci(f"set {alias} bitspersample 16 channels 1 samplespersec 16000 "
                 f"bytespersec 32000 alignment 2")
            _mci(f"record {alias}")
        except RuntimeError:
            # 그래도 거부하는 장치가 있습니다(일부 오디오 인터페이스는 16kHz 모노 미지원).
            # 형식 지정을 포기하고 **장치 기본 형식**으로 녹음합니다 — 파일이 커질 뿐,
            # Whisper API는 어떤 샘플레이트든 알아서 읽습니다.
            _mci(f"close {alias}")
            alias = "mic_" + uuid.uuid4().hex[:8]
            _mci(f"open new type waveaudio alias {alias}")
            _mci(f"record {alias}")

        start = time.time()
        while time.time() - start < max_seconds:
            if stop_check and stop_check():
                break
            time.sleep(0.1)

        _mci(f"stop {alias}")
        if os.path.exists(wav_path):
            os.remove(wav_path)
        _mci(f'save {alias} "{wav_path}"')
    finally:
        _mci(f"close {alias}")
    return wav_path


# ── 말이 끝나면 스스로 멈추는 녹음 (연속 음성 대화용) ─────────────
# MCI는 녹음 중 음량을 보여주지 않아 '말이 끝났는지'를 알 수 없습니다(그래서 지금까지
# 엔터를 쳐야 했음). waveIn을 ctypes로 직접 열면 0.1초 조각마다 소리 데이터가 오므로,
# 음량(RMS)을 재서 "말을 시작했다 → 조용해졌다"를 스스로 알 수 있습니다. pip 0 유지.

class _WAVEFORMATEX(ctypes.Structure):
    _fields_ = [("wFormatTag", ctypes.c_ushort), ("nChannels", ctypes.c_ushort),
                ("nSamplesPerSec", ctypes.c_uint), ("nAvgBytesPerSec", ctypes.c_uint),
                ("nBlockAlign", ctypes.c_ushort), ("wBitsPerSample", ctypes.c_ushort),
                ("cbSize", ctypes.c_ushort)]


class _WAVEHDR(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", ctypes.c_uint),
                ("dwBytesRecorded", ctypes.c_uint), ("dwUser", ctypes.c_void_p),
                ("dwFlags", ctypes.c_uint), ("dwLoops", ctypes.c_uint),
                ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_void_p)]


_CHUNK_SEC = 0.1
_RATE = 16000                     # Whisper가 쓰는 형식 — 파일이 작고 변환이 필요 없습니다
_CHUNK_BYTES = int(_RATE * 2 * _CHUNK_SEC)
_WHDR_DONE = 0x01


class _WAVEINCAPS(ctypes.Structure):
    _fields_ = [("wMid", ctypes.c_ushort), ("wPid", ctypes.c_ushort),
                ("vDriverVersion", ctypes.c_uint), ("szPname", ctypes.c_wchar * 32),
                ("dwFormats", ctypes.c_uint), ("wChannels", ctypes.c_ushort),
                ("wReserved1", ctypes.c_ushort)]

WAVE_MAPPER = 0xFFFFFFFF


def list_devices():
    """녹음 장치 목록 [(번호, 이름)]. 어느 마이크로 들을지 고를 때 씁니다."""
    winmm = ctypes.windll.winmm
    out = []
    for i in range(winmm.waveInGetNumDevs()):
        caps = _WAVEINCAPS()
        if winmm.waveInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
            out.append((i, caps.szPname))
    return out


def find_device(want):
    """config voice.device(이름 일부 또는 번호)를 장치 번호로. 못 찾으면 기본 장치.

    윈도우 '기본 장치'가 실제 마이크가 아닌 경우가 실재합니다(이 PC: 기본=Focusrite인데
    목소리는 Galaxy Buds로 들어옴 — 전 장치 동시 측정으로 실측). 이름 일부로 적어두면
    그 장치가 꽂혀 있을 때 그리로 듣고, 없으면(버즈를 끈 날) 기본 장치로 물러섭니다.
    """
    if want in (None, ""):
        return WAVE_MAPPER
    devices = list_devices()
    try:
        num = int(want)
        if any(i == num for i, _ in devices):
            return num
    except (TypeError, ValueError):
        pass
    want_low = str(want).lower()
    for i, name in devices:
        if want_low in name.lower():
            return i
    return WAVE_MAPPER


def save_device(name):
    """찾아낸 마이크를 config.json(voice.device)에 되돌려 씁니다 — 다음 실행에도 그 귀로.

    ⚠️config를 통째로 덮어쓰면 안 됩니다(save_tts와 같은 이유 — '--local' 모드의 메모리
    config를 저장하면 두뇌 목록이 파일에서 지워짐). 파일을 다시 읽어 이 한 칸만 갈아 끼웁니다.
    """
    path = os.path.join(BASE_DIR, "config.json")
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        raw.setdefault("voice", {})["device"] = name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
    except (OSError, ValueError):
        pass                                 # 저장 실패 = 이번 실행에만 적용(대화는 계속)


def find_live_device(seconds=6, min_peak=40, notify=print):
    """모든 녹음 장치를 **동시에** 열고 잠깐 들어, 목소리가 실제로 들어오는 장치를 찾습니다.
    (번호, 이름, 최고음량) 또는 None.

    왜 동시인가: 장치를 하나씩 재면 사용자가 장치 수만큼 같은 말을 반복해야 합니다.
    '스테레오 믹스' 같은 되울림 장치는 뺍니다 — 스피커에서 나오는 소리(루시 목소리·음악)를
    마이크로 오인해 그리로 갈아타면 자기 말에 자기가 답하는 루프가 됩니다.
    """
    winmm = ctypes.windll.winmm
    candidates = []
    for i, name in list_devices():
        low = name.lower()
        if "믹스" in name or "mix" in low or "loop" in low:
            continue
        candidates.append((i, name))
    if not candidates:
        return None

    peaks = {}

    def probe(dev):
        handle = ctypes.c_void_p()
        fmt = _WAVEFORMATEX(1, 1, _RATE, _RATE * 2, 2, 16, 0)
        if winmm.waveInOpen(ctypes.byref(handle), dev, ctypes.byref(fmt), 0, 0, 0):
            return                           # 못 여는 장치(다른 앱이 독점 등)는 후보에서 빠짐
        buffers = [ctypes.create_string_buffer(_CHUNK_BYTES) for _ in range(4)]
        headers = [_WAVEHDR(ctypes.cast(b, ctypes.c_void_p), _CHUNK_BYTES) for b in buffers]
        peak = 0
        try:
            for h in headers:
                winmm.waveInPrepareHeader(handle, ctypes.byref(h), ctypes.sizeof(_WAVEHDR))
                winmm.waveInAddBuffer(handle, ctypes.byref(h), ctypes.sizeof(_WAVEHDR))
            winmm.waveInStart(handle)
            started, i = time.time(), 0
            while time.time() - started < seconds:
                if not (headers[i].dwFlags & _WHDR_DONE):
                    time.sleep(0.01)
                    continue
                data = ctypes.string_at(headers[i].lpData, headers[i].dwBytesRecorded)
                winmm.waveInUnprepareHeader(handle, ctypes.byref(headers[i]), ctypes.sizeof(_WAVEHDR))
                winmm.waveInPrepareHeader(handle, ctypes.byref(headers[i]), ctypes.sizeof(_WAVEHDR))
                winmm.waveInAddBuffer(handle, ctypes.byref(headers[i]), ctypes.sizeof(_WAVEHDR))
                i = (i + 1) % len(headers)
                peak = max(peak, _rms(data))
        finally:
            winmm.waveInStop(handle)
            winmm.waveInReset(handle)
            for h in headers:
                winmm.waveInUnprepareHeader(handle, ctypes.byref(h), ctypes.sizeof(_WAVEHDR))
            winmm.waveInClose(handle)
        peaks[dev] = peak

    threads = [threading.Thread(target=probe, args=(d,), daemon=True) for d, _ in candidates]
    for t in threads:
        t.start()
    for t in threads:
        t.join(seconds + 5)
    if not peaks:
        return None
    best = max(peaks, key=peaks.get)
    if peaks[best] < min_peak:
        return None                          # 아무 데서도 목소리가 안 들림(안 말했거나 다 무음)
    name = dict(list_devices()).get(best, str(best))
    return best, name, peaks[best]


def _rms(data):
    """소리 조각의 음량. 데이터는 16bit 모노."""
    import array
    import math
    if len(data) < 2:
        return 0
    samples = array.array("h", data[: len(data) // 2 * 2])
    return int(math.sqrt(sum(x * x for x in samples) / len(samples)))


def record_vad(wav_path, max_seconds=30, silence_sec=1.2, listen_timeout=12,
               abort_check=None, on_speech=None, min_threshold=150, device=WAVE_MAPPER,
               noise_mult=3.0):
    """
    말을 시작하면 담고, 말이 끝나면(침묵 silence_sec) 스스로 멈춥니다.

    돌려주기: 'ok'(녹음됨) / 'silent'(listen_timeout 동안 말이 없음) / 'abort'(abort_check가 True)

    방식: 주변 소음을 첫 0.5초로 재서 문턱을 정하고(조용한 방과 시끄러운 방이 다르므로
    고정값은 안 됩니다), 문턱을 넘는 조각이 이어지면 '말 시작', 말한 뒤 문턱 아래로
    silence_sec 동안 조용하면 '말 끝'. 말 시작 직전 조각도 몇 개 담아 첫음절이 잘리지 않게 합니다.
    """
    winmm = ctypes.windll.winmm
    handle = ctypes.c_void_p()
    fmt = _WAVEFORMATEX(1, 1, _RATE, _RATE * 2, 2, 16, 0)

    rc = winmm.waveInOpen(ctypes.byref(handle), device, ctypes.byref(fmt), 0, 0, 0)
    if rc:
        raise RuntimeError(f"마이크를 열지 못했습니다 (waveInOpen 오류 {rc}, 장치 {device})")

    buffers = [ctypes.create_string_buffer(_CHUNK_BYTES) for _ in range(8)]
    headers = [_WAVEHDR(ctypes.cast(b, ctypes.c_void_p), _CHUNK_BYTES) for b in buffers]

    def _feed(i):
        winmm.waveInPrepareHeader(handle, ctypes.byref(headers[i]), ctypes.sizeof(_WAVEHDR))
        winmm.waveInAddBuffer(handle, ctypes.byref(headers[i]), ctypes.sizeof(_WAVEHDR))

    try:
        for i in range(len(headers)):
            _feed(i)
        winmm.waveInStart(handle)

        collected, pre_roll = [], []     # 담은 소리 / 말 시작 직전의 몇 조각
        noise_samples = []
        threshold = None
        speaking = False
        quiet_run = 0
        speech_chunks = 0
        started = time.time()
        need_quiet = max(1, int(silence_sec / _CHUNK_SEC))
        result = "silent"
        i = 0

        while True:
            if abort_check and abort_check():
                result = "abort"
                break
            if time.time() - started > (listen_timeout if not speaking else max_seconds):
                result = "ok" if speaking else "silent"
                break

            if not (headers[i].dwFlags & _WHDR_DONE):
                time.sleep(0.01)
                continue

            data = ctypes.string_at(headers[i].lpData, headers[i].dwBytesRecorded)
            winmm.waveInUnprepareHeader(handle, ctypes.byref(headers[i]), ctypes.sizeof(_WAVEHDR))
            _feed(i)
            i = (i + 1) % len(headers)

            level = _rms(data)
            if threshold is None:
                noise_samples.append(level)
                if len(noise_samples) >= 5:      # 첫 0.5초 = 방의 기본 소음
                    # 평균이 아니라 **최솟값**을 씁니다 — 측정 중에 사용자가 말을 시작하면
                    # 평균은 말소리에 끌려 올라가 문턱이 부풀고(말을 소음으로 오인),
                    # 그 뒤로는 아무리 말해도 못 알아듣습니다(버즈에서 실제로 겪음).
                    # 최솟값은 다섯 조각 중 가장 조용한 순간 = 진짜 바닥에 가깝습니다.
                    ambient = min(noise_samples)
                    # 문턱 = 바닥×배수(talk.noise_mult). 조용한 마이크(버즈: 바닥 30~55,
                    # 말소리 117~251)는 배수 3.0이 과해서 말을 놓칩니다 — 그럴 땐 config에서
                    # 배수를 낮추세요. min_threshold는 그 아래로는 안 내려가는 안전 바닥.
                    threshold = max(ambient * noise_mult, min_threshold)
                continue

            if not speaking:
                pre_roll.append(data)
                pre_roll = pre_roll[-3:]         # 첫음절 보호용 0.3초
                if level > threshold:
                    speaking = True
                    if on_speech:
                        on_speech()
                    collected.extend(pre_roll)
                    speech_chunks = 1
            else:
                collected.append(data)
                if level > threshold:
                    speech_chunks += 1
                    quiet_run = 0
                elif level < threshold * 0.7:
                    quiet_run += 1
                    if quiet_run >= need_quiet:
                        result = "ok"
                        break
    finally:
        winmm.waveInStop(handle)
        winmm.waveInReset(handle)
        for h in headers:
            winmm.waveInUnprepareHeader(handle, ctypes.byref(h), ctypes.sizeof(_WAVEHDR))
        winmm.waveInClose(handle)

    if result != "ok" or speech_chunks < 3:      # 0.3초 미만의 '말'은 문 닫는 소리 같은 잡음
        return result if result != "ok" else "silent"

    import wave
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_RATE)
        w.writeframes(b"".join(collected))
    return "ok"


def listen_vad(key, model="whisper-large-v3", language="ko", abort_check=None,
               notify=print, max_seconds=30, silence_sec=1.2, listen_timeout=12,
               min_threshold=150, device=WAVE_MAPPER, noise_mult=3.0):
    """말이 끝나면 알아서 받아씁니다. None=사용자가 끊음 / ''=말이 없었음 / 글자=받아쓴 것."""
    wav = os.path.join(BASE_DIR, "memory", "_last_voice.wav")
    os.makedirs(os.path.dirname(wav), exist_ok=True)

    got = record_vad(wav, max_seconds=max_seconds, silence_sec=silence_sec,
                     listen_timeout=listen_timeout, abort_check=abort_check,
                     on_speech=lambda: notify("  (듣고 있어요...)"),
                     min_threshold=min_threshold, device=device, noise_mult=noise_mult)
    if got == "abort":
        return None
    if got != "ok":
        return ""
    notify("  받아쓰는 중…")
    return transcribe(wav, key, model=model, language=language)


def _multipart(fields, file_field, filename, file_bytes, content_type="audio/wav"):
    """urllib으로 파일 업로드를 하려면 multipart 본문을 직접 만들어야 합니다."""
    boundary = "----agent" + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
        f"filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


def _groq_transcribe(wav_path, key, model, language, response_format):
    """Groq 받아쓰기 공용 요청. wav만이 아니라 폰 녹음(m4a)·mp3도 됩니다 —
    Groq가 형식을 **파일명 확장자로** 알아보므로 실제 이름을 그대로 넘깁니다."""
    import mimetypes
    with open(wav_path, "rb") as f:
        audio = f.read()

    stem, ext = os.path.splitext(os.path.basename(wav_path))
    # 형식은 확장자로 전하되, 한글 이름은 multipart 헤더에서 깨질 수 있어 ASCII로 바꿉니다.
    name = (stem if stem.isascii() else "audio") + (ext if ext else ".wav")
    body, boundary = _multipart(
        {"model": model, "language": language, "response_format": response_format},
        "file", name, audio,
        content_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
    )
    req = urllib.request.Request(
        GROQ_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": UA,   # 없으면 Cloudflare가 403으로 막습니다
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        import json
        return json.loads(resp.read().decode("utf-8"))


def transcribe(wav_path, key, model="whisper-large-v3", language="ko"):
    """녹음 파일을 글자로 바꿉니다(글자만 — 시각이 필요하면 transcribe_segments)."""
    return _groq_transcribe(wav_path, key, model, language, "json").get("text", "").strip()


def transcribe_segments(wav_path, key, model="whisper-large-v3", language="ko"):
    """받아쓰기 + 문장별 시각 — 자막(SRT) 만들기용. [(시작초, 끝초, 문장)] 목록.
    verbose_json의 segments가 whisper가 끊은 문장 단위라 자막 줄로 바로 씁니다."""
    data = _groq_transcribe(wav_path, key, model, language, "verbose_json")
    out = []
    for s in data.get("segments") or []:
        text = str(s.get("text") or "").strip()
        if text:
            out.append((float(s.get("start") or 0), float(s.get("end") or 0), text))
    return out


def listen(key, model="whisper-large-v3", language="ko"):
    """엔터를 누를 때까지 녹음하고, 받아쓴 글자를 돌려줍니다."""
    wav = os.path.join(BASE_DIR, "memory", "_last_voice.wav")
    os.makedirs(os.path.dirname(wav), exist_ok=True)

    print("  🎤 말하세요… (다 말했으면 엔터)")
    done = {"v": False}

    import threading
    def wait_enter():
        input()
        done["v"] = True

    t = threading.Thread(target=wait_enter, daemon=True)
    t.start()
    record(wav, stop_check=lambda: done["v"])

    size = os.path.getsize(wav) if os.path.exists(wav) else 0
    if size < 2000:                      # 사실상 아무 소리도 안 들어옴
        return ""

    print("  받아쓰는 중…")
    return transcribe(wav, key, model=model, language=language)
