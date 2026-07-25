# -*- coding: utf-8 -*-
"""
동영상 편집 — ffmpeg를 부립니다. 루시 본체는 여전히 "pip 없음"입니다.

멜로 목소리·SD WebUI와 같은 사상입니다: 무거운 일은 루시 밖의 물건(ffmpeg.exe 하나)이
하고, 루시는 안전한 명령을 만들어 넘길 뿐입니다. ffmpeg가 없는 PC에서는 도구가
설치 안내만 하고 물러납니다(winget install Gyan.FFmpeg 한 줄).

동작은 **정해진 목록**(trim·join·audio·convert·speed·gif·frame)만 됩니다.
모델이 ffmpeg 인자를 직접 짓게 하면 아무 명령이나 흘러들 수 있으므로(-i 뒤에 뭐가 올지
모름), 인자는 전부 이 파일의 코드가 조립하고 모델은 재료(시각·배속·폭)만 줍니다.

원본은 절대 건드리지 않습니다 — 결과는 항상 새 파일이고, 이름이 겹치면 _1을 붙입니다.
"""
import json
import os
import re
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

# 시각은 '90', '1:30', '01:02:03.5' 모양만 받습니다 — ffmpeg 인자로 그대로 가므로
# 이 검사가 곧 주입 방지막입니다(공백·하이픈이 든 것은 여기서 죽습니다).
_TIME = re.compile(r"^\d+(:\d{1,2}){0,2}(\.\d+)?$")


def _find(name, config=None):
    """ffmpeg/ffprobe를 찾습니다: config 지정 → PATH → winget 설치 자리."""
    conf = (config or {}).get("video", {})
    if conf.get(name) and os.path.isfile(conf[name]):
        return conf[name]
    hit = shutil.which(name)
    if hit:
        return hit
    winget = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                          "Microsoft", "WinGet", "Links", name + ".exe")
    if os.path.isfile(winget):
        return winget                    # 설치 직후에는 PATH가 아직 옛것입니다(셸 재시작 전)
    return None


def ready(config=None):
    return bool(_find("ffmpeg", config))

INSTALL_GUIDE = ("ffmpeg가 없어 동영상 편집을 못 합니다. 한 줄이면 설치됩니다:\n"
                 "  winget install -e --id Gyan.FFmpeg\n"
                 "설치 후 다시 시켜 주세요.")


def _run(args, timeout, cwd=None):
    proc = subprocess.run(args, capture_output=True, timeout=timeout,
                          cwd=cwd, creationflags=NO_WINDOW)
    if proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()
        raise RuntimeError("ffmpeg 실패: " + " / ".join(tail[-3:]))   # 마지막 몇 줄에 원인이 있습니다


def probe(path, config=None):
    """길이(초)·해상도·크기. 편집 전후 보고와 검증에 씁니다."""
    ffprobe = _find("ffprobe", config)
    if not ffprobe:
        return {}
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True, timeout=60, creationflags=NO_WINDOW)
    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except ValueError:
        return {}
    out = {"duration": float(data.get("format", {}).get("duration") or 0),
           "size": os.path.getsize(path) if os.path.exists(path) else 0}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            out["width"], out["height"] = s.get("width"), s.get("height")
            break
    return out


def _out_path(src, suffix, ext, output=None):
    """결과 파일 자리. 원본 옆에, 원본과 다른 이름으로, 겹치면 _1."""
    if output:
        path = str(output).strip().strip('"\'')
        if not os.path.dirname(path):
            path = os.path.join(os.path.dirname(os.path.abspath(src)), path)
    else:
        stem = os.path.splitext(os.path.basename(src))[0]
        path = os.path.join(os.path.dirname(os.path.abspath(src)), f"{stem}{suffix}{ext}")
    if os.path.abspath(path) == os.path.abspath(src):
        raise ValueError("결과 파일이 원본과 같은 경로입니다 — 원본은 덮어쓰지 않습니다.")
    base, dot = os.path.splitext(path)
    n = 1
    while os.path.exists(path):
        path = f"{base}_{n}{dot}"
        n += 1
    return path


def _t(value, name):
    v = str(value or "").strip()
    if not _TIME.match(v):
        raise ValueError(f"{name} 시각이 이상합니다: '{value}' ('90', '1:30', '01:02:03' 모양이어야 함)")
    return v


# ── 동작들 — 전부 (결과경로) 를 돌려줍니다 ──────────────────────────

def trim(ff, src, start, end, output, timeout):
    """구간 자르기. 스트림 복사(-c copy)는 키프레임에서만 잘려 몇 초씩 밀립니다 —
    '0:30부터'라고 말한 사람은 0:30을 기대하므로 다시 인코딩합니다(느리지만 정확)."""
    out = _out_path(src, "_잘라냄", os.path.splitext(src)[1] or ".mp4", output)
    _run([ff, "-y", "-ss", _t(start, "start"), "-to", _t(end, "end"), "-i", src,
          "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", out], timeout)
    return out


def join(ff, paths, output, timeout):
    """이어붙이기. 같은 형식(폰으로 찍은 연속 클립 등)은 재인코딩 없이 순식간입니다.
    형식이 다르면 ffmpeg가 거부합니다 — 그때는 convert로 형식을 맞춘 뒤 다시."""
    listing = os.path.join(BASE_DIR, "memory", "_concat.txt")
    os.makedirs(os.path.dirname(listing), exist_ok=True)
    with open(listing, "w", encoding="utf-8") as f:
        for p in paths:
            f.write("file '" + os.path.abspath(p).replace("'", "'\\''") + "'\n")
    out = _out_path(paths[0], "_이어붙임", os.path.splitext(paths[0])[1] or ".mp4", output)
    try:
        _run([ff, "-y", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", out], timeout)
    finally:
        try:
            os.remove(listing)
        except OSError:
            pass
    return out


def _vtt_time(sec):
    ms = int(round(float(sec) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def make_vtt(segments, path):
    """[(시작초, 끝초, 문장)] → WebVTT 파일."""
    lines = ["WEBVTT\n"]
    for i, (start, end, text) in enumerate(segments, 1):
        if end <= start:
            end = start + 1.5
        lines += [str(i), f"{_vtt_time(start)} --> {_vtt_time(end)}", text, ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def audio(ff, src, output=None, timeout=600, fmt="mp3"):
    """소리만 추출(mp3/wav/aac/m4a). 회의 영상을 받아쓰는 길: audio → transcribe_audio."""
    ext = f".{str(fmt or 'mp3').lstrip('.').lower()}"
    if ext not in (".mp3", ".wav", ".aac", ".m4a"):
        ext = ".mp3"
    codec_map = {
        ".mp3": ["-acodec", "libmp3lame", "-q:a", "4"],
        ".wav": ["-acodec", "pcm_s16le"],
        ".aac": ["-acodec", "aac", "-b:a", "192k"],
        ".m4a": ["-acodec", "aac", "-b:a", "192k"],
    }
    out = _out_path(src, "_소리", ext, output)
    cmd = [ff, "-y", "-i", src, "-vn"] + codec_map[ext] + [out]
    _run(cmd, timeout)
    return out


def convert(ff, src, output, width, timeout):
    """형식 변환·압축. width를 주면 그 폭으로 줄입니다(용량이 크게 줄어듦)."""
    ext = os.path.splitext(str(output or ""))[1].lower() or ".mp4"
    out = _out_path(src, "_변환", ext, output)
    args = [ff, "-y", "-i", src]
    if width:
        args += ["-vf", f"scale={int(width)}:-2"]      # -2: 높이는 비율대로(짝수 보정)
    args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-c:a", "aac", out]
    _run(args, timeout)
    return out


def speed(ff, src, rate, output, timeout):
    rate = float(rate)
    if not 0.25 <= rate <= 4.0:
        raise ValueError("배속은 0.25~4 사이만 됩니다.")
    # 소리(atempo)는 한 번에 0.5~2배만 됩니다 — 범위를 넘으면 두 번 겹쳐 걸어줍니다.
    tempos = []
    left = rate
    while left > 2.0:
        tempos.append("atempo=2.0")
        left /= 2.0
    while left < 0.5:
        tempos.append("atempo=0.5")
        left /= 0.5
    tempos.append(f"atempo={left:.4f}")
    out = _out_path(src, f"_{rate:g}배속", os.path.splitext(src)[1] or ".mp4", output)
    _run([ff, "-y", "-i", src,
          "-filter_complex", f"[0:v]setpts=PTS/{rate}[v];[0:a]{','.join(tempos)}[a]",
          "-map", "[v]", "-map", "[a]",
          "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", out], timeout)
    return out


def gif(ff, src, start, end, width, output, timeout):
    out = _out_path(src, "", ".gif", output)
    args = [ff, "-y"]
    if start:
        args += ["-ss", _t(start, "start")]
    if end:
        args += ["-to", _t(end, "end")]
    args += ["-i", src, "-vf", f"fps=12,scale={int(width or 480)}:-1:flags=lanczos", out]
    _run(args, timeout)
    return out


def frame(ff, src, at, output, timeout):
    """한 장면을 사진으로. 썸네일·'그 장면 보여줘'용."""
    out = _out_path(src, f"_{str(at).replace(':', '분')}", ".png", output)
    _run([ff, "-y", "-ss", _t(at or "0", "at"), "-i", src, "-frames:v", "1", out], timeout)
    return out


# ── 자막 ─────────────────────────────────────────────────────────

def _srt_time(sec):
    ms = int(round(float(sec) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_srt(segments, path):
    """[(시작초, 끝초, 문장)] → SRT 파일. utf-8-sig — 다른 재생기가 열어도 한글이 안 깨지게."""
    lines = []
    for i, (start, end, text) in enumerate(segments, 1):
        if end <= start:
            end = start + 1.5            # whisper가 가끔 길이 0 조각을 줍니다 — 최소한 읽을 시간을
        lines += [str(i), f"{_srt_time(start)} --> {_srt_time(end)}", text, ""]
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))
    return path


def _auto_srt(ff, src, srt_path, timeout, config):
    """영상의 말소리를 받아써서 SRT를 만듭니다(whisper의 문장별 시각 사용)."""
    import voice

    conf = (config or {}).get("voice", {})
    key_file = os.path.join(BASE_DIR, conf.get("key_file") or "keys/groq.txt")
    try:
        with open(key_file, "r", encoding="utf-8-sig") as f:
            key = f.read().strip()
    except OSError:
        key = ""
    if not key:
        raise RuntimeError("받아쓰기 키(keys/groq.txt)가 없어 자막을 만들 수 없습니다. "
                           "SRT 파일이 이미 있으면 srt 인자로 주세요.")

    # 받아쓰기용 소리 추출 — 말소리는 모노 16k면 충분하고, 48kbps면 1시간이 Groq 24MB 안에 듭니다.
    tmp = os.path.join(BASE_DIR, "memory", "_subtitle_audio.mp3")
    _run([ff, "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", tmp], timeout)
    try:
        if os.path.getsize(tmp) > 24 * 1024 * 1024:
            raise RuntimeError("영상이 너무 깁니다(추출한 소리가 Groq 상한 24MB 초과) — trim으로 잘라서 부분씩 해주세요.")
        segments = voice.transcribe_segments(tmp, key,
                                             model=conf.get("model", "whisper-large-v3"),
                                             language=conf.get("language", "ko"))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if not segments:
        raise RuntimeError("말소리를 찾지 못해 자막을 만들 수 없습니다(무음 영상?).")
    return make_srt(segments, srt_path)


def subtitle(ff, src, srt, output, timeout, config):
    """자막 입히기(화면에 굽기). srt를 안 주면 말소리를 받아써 자동 생성합니다.

    자동 생성한 SRT는 결과 영상 옆에 같은 이름으로 남깁니다 — 받아쓰기가 틀린 데를
    사람이 고쳐서 '이 SRT로 다시 입혀줘' 할 수 있게(굽고 버리면 고칠 길이 없습니다).
    """
    out = _out_path(src, "_자막", os.path.splitext(src)[1] or ".mp4", output)

    if srt:
        srt = str(srt).strip().strip('"\'')
        if not os.path.isfile(srt):
            raise ValueError(f"자막 파일이 없습니다: {srt}")
    else:
        srt = make_path = os.path.splitext(out)[0] + ".srt"
        _auto_srt(ff, src, make_path, timeout, config)

    # ffmpeg의 subtitles 필터는 경로 속 콜론·한글·공백 이스케이프가 지뢰밭입니다.
    # 아스키 이름으로 복사해 두고 **작업 폴더 기준 상대 이름**으로 부르면 이스케이프가 통째로 사라집니다.
    burn_dir = os.path.join(BASE_DIR, "memory")
    burn = os.path.join(burn_dir, "_burn.srt")
    shutil.copy2(srt, burn)
    try:
        _run([ff, "-y", "-i", src,
              "-vf", "subtitles=_burn.srt:force_style='FontName=Malgun Gothic,FontSize=20,Outline=1'",
              "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", out],
             timeout, cwd=burn_dir)
    finally:
        try:
            os.remove(burn)
        except OSError:
            pass
    return out


ACTIONS = ("trim", "join", "audio", "convert", "speed", "gif", "frame", "subtitle")


def edit(action, config=None, path=None, paths=None, output=None,
         start=None, end=None, rate=None, width=None, at=None, srt=None):
    """바깥(tools.edit_video)에서 부르는 문 하나. 결과 파일 경로를 돌려줍니다."""
    ff = _find("ffmpeg", config)
    if not ff:
        raise RuntimeError(INSTALL_GUIDE)
    timeout = int((config or {}).get("video", {}).get("timeout", 600))

    if action == "subtitle":
        return subtitle(ff, path, srt, output, timeout, config)
    if action == "trim":
        return trim(ff, path, start, end, output, timeout)
    if action == "join":
        return join(ff, paths, output, timeout)
    if action == "audio":
        return audio(ff, path, output, timeout)
    if action == "convert":
        return convert(ff, path, output, width, timeout)
    if action == "speed":
        return speed(ff, path, rate, output, timeout)
    if action == "gif":
        return gif(ff, path, start, end, width, output, timeout)
    if action == "frame":
        return frame(ff, path, at, output, timeout)
    raise ValueError(f"모르는 동작입니다: {action} (되는 것: {', '.join(ACTIONS)})")
