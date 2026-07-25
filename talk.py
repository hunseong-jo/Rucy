# -*- coding: utf-8 -*-
"""
연속 음성 대화 — '/음성모드': 말하면 답하고, 답이 끝나면 다시 듣습니다.

지금까지 음성은 푸시투토크였습니다(`음성` 입력 → 말하기 → 엔터). 이 모드는 그 루프를
자동으로 돌립니다:  듣기(말이 끝나면 스스로 멈춤, voice.record_vad) → 받아쓰기 →
루시가 답 → 소리로 읽기 → **다 읽으면** 다시 듣기.

'다 읽으면'이 중요합니다 — 루시가 말하는 동안 마이크를 열면 스피커에서 나온 제 목소리를
제 귀로 듣고 자기 말에 자기가 답하는 루프가 됩니다. 그래서 tts.speaking()이 끝날 때까지
기다렸다가 듣습니다(그 대신 말이 겹치는 '끼어들기'는 안 됩니다 — 엔터로 끊으세요).

나가는 길: "그만"/"종료"라고 말하기 · 엔터 누르기 · 말없이 idle_rounds번 지나가기.
키 감지는 msvcrt(윈도우 콘솔 내장)라 스레드가 필요 없습니다 — input() 스레드를 쓰면
모드를 나간 뒤에도 스레드가 남아 다음 입력 한 줄을 삼킵니다.
"""
import os
import re
import time

import tts
import voice

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 대화를 끝내려는 짧은 말. 문장 속의 '그만'("그만두는 게 나을까?")까지 잡지 않게
# 발화 전체가 짧을 때만 끝냄말로 봅니다.
EXIT_RE = re.compile(r"(그만|종료|끝내|끝이야|대화 ?끝|이만|잘 ?자)")


def _enter_pressed():
    """콘솔에서 엔터(또는 ESC)를 눌렀는가. 누른 키는 삼킵니다."""
    try:
        import msvcrt
        hit = False
        while msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\r", "\n", "\x1b"):
                hit = True
        return hit
    except Exception:
        return False


def _groq_key(config):
    cfg = config.get("voice", {})
    path = os.path.join(BASE_DIR, cfg.get("key_file", "keys/groq.txt"))
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.readline().strip()


def meter(seconds=6, notify=print, config=None):
    """마이크 음량을 실시간으로 보여줍니다 — 문턱값(talk.min_threshold)을 맞출 때 씁니다.
    소리는 어디로도 전송되지 않습니다."""
    import ctypes
    device = voice.find_device((config or {}).get("voice", {}).get("device"))
    for i, name in voice.list_devices():
        mark = " ← 이걸로 듣는 중" if (i == device) else ""
        notify(f"  장치 {i}: {name}{mark}")
    if device == voice.WAVE_MAPPER:
        notify("  (기본 장치로 듣는 중 — 다른 마이크를 쓰려면 config voice.device에 이름 일부를)")
    winmm = ctypes.windll.winmm
    handle = ctypes.c_void_p()
    fmt = voice._WAVEFORMATEX(1, 1, voice._RATE, voice._RATE * 2, 2, 16, 0)
    if winmm.waveInOpen(ctypes.byref(handle), device, ctypes.byref(fmt), 0, 0, 0):
        notify("  마이크를 열지 못했습니다.")
        return
    buffers = [ctypes.create_string_buffer(voice._CHUNK_BYTES) for _ in range(4)]
    headers = [voice._WAVEHDR(ctypes.cast(b, ctypes.c_void_p), voice._CHUNK_BYTES) for b in buffers]

    notify(f"  {seconds}초 동안 음량을 잽니다 — 평소처럼 말해보세요. (전송 안 함)")
    peak = 0
    try:
        for i in range(len(headers)):
            winmm.waveInPrepareHeader(handle, ctypes.byref(headers[i]), ctypes.sizeof(voice._WAVEHDR))
            winmm.waveInAddBuffer(handle, ctypes.byref(headers[i]), ctypes.sizeof(voice._WAVEHDR))
        winmm.waveInStart(handle)
        started, i, bucket = time.time(), 0, []
        while time.time() - started < seconds:
            if not (headers[i].dwFlags & voice._WHDR_DONE):
                time.sleep(0.01)
                continue
            data = ctypes.string_at(headers[i].lpData, headers[i].dwBytesRecorded)
            winmm.waveInUnprepareHeader(handle, ctypes.byref(headers[i]), ctypes.sizeof(voice._WAVEHDR))
            winmm.waveInPrepareHeader(handle, ctypes.byref(headers[i]), ctypes.sizeof(voice._WAVEHDR))
            winmm.waveInAddBuffer(handle, ctypes.byref(headers[i]), ctypes.sizeof(voice._WAVEHDR))
            i = (i + 1) % len(headers)
            level = voice._rms(data)
            peak = max(peak, level)
            bucket.append(level)
            if len(bucket) >= 5:                     # 0.5초마다 한 줄
                avg = int(sum(bucket) / len(bucket))
                notify(f"    음량 {avg:5d}  {'#' * min(40, avg // 50)}")
                bucket = []
    finally:
        winmm.waveInStop(handle)
        winmm.waveInReset(handle)
        for h in headers:
            winmm.waveInUnprepareHeader(handle, ctypes.byref(h), ctypes.sizeof(voice._WAVEHDR))
        winmm.waveInClose(handle)
    notify(f"  최고 음량: {peak} — 말할 때 음량이 문턱(config talk.min_threshold, 기본 150)을"
           f" 넘어야 알아듣습니다. 안 넘으면 그 값을 낮추세요.")


def run(config, state, respond, notify=print):
    """연속 음성 대화 루프. 마칠 때 안내문을 돌려줍니다."""
    cfg = config.get("talk", {})
    if not cfg.get("enabled", True):
        return "연속 음성 대화가 설정에서 꺼져 있습니다(talk.enabled)."
    key = _groq_key(config)
    if not key:
        return "받아쓰기용 Groq 키가 없습니다(keys/groq.txt). '음성' 기능과 같은 키입니다."

    vcfg = config.get("voice", {})
    name = config.get("name") or "루시"

    # 음성 대화니까 답은 소리로 — 읽어주기가 꺼져 있어도 이 모드 안에서만 켭니다.
    tts_conf = config.setdefault("tts", {})
    tts_was = tts_conf.get("enabled", False)
    tts_conf["enabled"] = True

    notify("  🎙 연속 음성 대화 — 그냥 말씀하세요. 말이 끝나면 알아서 답합니다.")
    notify("     끝내려면 \"그만\"이라고 말하거나 엔터를 누르세요. (읽는 중 엔터 = 말 끊기)")
    # 어느 귀로 듣는지 먼저 보여줍니다 — 엉뚱한 장치(오디오 인터페이스 등)로 듣고 있으면
    # 사용자가 이 줄에서 바로 알아챕니다(장치가 조용히 틀려 있던 것이 세션56의 실제 사고).
    dev_name = dict(voice.list_devices()).get(
        voice.find_device(vcfg.get("device")), "윈도우 기본 장치")
    notify(f"     듣는 장치: {dev_name}")
    tts.speak("네, 말씀하세요.", config)

    idle = 0
    reason = "연속 음성 대화를 마쳤습니다."
    try:
        while True:
            # 루시가 말을 마칠 때까지 — 스피커 소리를 제 귀로 듣지 않게.
            while tts.speaking():
                if _enter_pressed():
                    tts.stop()
                time.sleep(0.1)
            if _enter_pressed():
                break

            heard = voice.listen_vad(
                key, model=vcfg.get("model", "whisper-large-v3"),
                language=vcfg.get("language", "ko"),
                abort_check=_enter_pressed, notify=notify,
                max_seconds=cfg.get("max_seconds", 30),
                silence_sec=cfg.get("silence_sec", 1.2),
                listen_timeout=cfg.get("listen_timeout", 12),
                min_threshold=cfg.get("min_threshold", 150),
                device=voice.find_device(vcfg.get("device")),
                noise_mult=cfg.get("noise_mult", 3.0),
            )
            if heard is None:                    # 엔터로 끊음
                break
            if not heard:
                idle += 1
                if idle >= cfg.get("idle_rounds", 3):
                    reason = "말씀이 없어 연속 음성 대화를 마쳤습니다."
                    tts.speak("말씀이 없으셔서 이만 물러갈게요. 필요하면 다시 불러주세요.", config)
                    break
                # 첫 침묵이면 '안 말한 것'이 아니라 '엉뚱한 귀로 듣는 것'일 수 있습니다
                # (헤드셋·이어폰을 새로 꽂으면 설정된 장치가 무음이 됨 — 세션56 실사고).
                # 모든 마이크를 동시에 열고 한 번 더 들어, 목소리가 들리는 귀로 갈아탑니다.
                if idle == 1 and cfg.get("auto_device", True):
                    notify("  (안 들리네요 — 어느 마이크로 들리는지 찾아볼게요)")
                    tts.speak("잘 안 들려요. 마이크를 찾아볼게요. 한 문장 말씀해 주세요.", config)
                    while tts.speaking():
                        time.sleep(0.1)
                    found = voice.find_live_device(
                        seconds=6, min_peak=max(cfg.get("min_threshold", 150) * 2, 40),
                        notify=notify)
                    if found and found[1] != dict(voice.list_devices()).get(
                            voice.find_device(vcfg.get("device"))):
                        vcfg["device"] = found[1]        # 이름으로 기억 — 번호는 수시로 바뀜
                        voice.save_device(found[1])      # 다음 실행에도 이 귀로
                        notify(f"  ✓ 마이크를 갈아탑니다: {found[1]} (음량 {found[2]})")
                        tts.speak("찾았어요. 이 마이크로 들을게요. 이제 말씀하세요.", config)
                        idle = 0
                        continue
                    if found:
                        notify("  (지금 마이크가 맞아요 — 소리가 작았을 뿐. 조금 크게 말씀해 주세요.)")
                        continue
                notify("  (말씀이 없네요 — 계속 듣고 있어요. 끝내려면 엔터)")
                continue
            idle = 0

            notify(f"\n나 (음성) > {heard}")
            if len(heard) <= 12 and EXIT_RE.search(heard):
                tts.speak("네, 대화 모드를 마칠게요.", config)
                break

            try:
                answer, used = respond(config, state, heard,
                                       notify=lambda m: notify(f"    {m}"))
            except Exception as e:
                notify(f"  답하지 못했습니다: {type(e).__name__}: {e}")
                tts.speak("죄송해요, 답을 만들다 오류가 났어요.", config)
                continue
            notify(f"{name} ({used}) > {answer}")
            tts.speak(answer, config)
    except KeyboardInterrupt:
        reason = "연속 음성 대화를 마쳤습니다(Ctrl+C)."
    finally:
        tts_conf["enabled"] = tts_was            # 원래 켬/끔 상태로 — 모드 밖까지 끌고 가지 않게

    # 마지막 인사가 끊기지 않게 잠깐 기다립니다(엔터로 언제든 끊을 수 있음).
    for _ in range(40):
        if not tts.speaking():
            break
        if _enter_pressed():
            tts.stop()
            break
        time.sleep(0.25)
    return reason
