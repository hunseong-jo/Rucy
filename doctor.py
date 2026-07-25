# -*- coding: utf-8 -*-
"""
자가 진단·수리 — 루시가 제 몸의 문제를 알아채고, 말하고, 고칠 수 있으면 고칩니다.

루시는 "절대 멈추지 않기" 위해 문제를 조용히 삼킵니다: 로컬 목소리 서버가 꺼지면
말없이 구글 목소리로, Ollama가 꺼지면 말없이 단어겹침 검색으로 내려갑니다.
계속 돌아가는 건 좋은데, **사용자는 루시가 아프다는 걸 모릅니다** — 목소리가 왜
딱딱한지, 기억 검색이 왜 엉뚱한지 겉으로는 폴백인지 고장인지 구분이 안 되니까요.

그래서 여기서 점검하고, 고칠 수 있는 것은 그 자리에서 고칩니다. 세 곳에서 불립니다:
  1. 시작할 때(agent.main) — 문제가 있을 때만 한 줄씩 말합니다(정상이면 조용).
  2. '/점검' — 전부 보여줍니다(정상인 것 포함).
  3. self_check 도구 — 사용자가 "목소리가 왜 이래?"라고 **루시에게 물으면**
     루시가 스스로 이걸 돌려 진단하고, 고치고, 무슨 일이었는지 답합니다.
  4. daily.tick — 하루 한 번, 알림 일꾼도 제 몸을 살핍니다(재부팅 뒤 서버들이 꺼진 채
     방치되지 않게).

고치는 방법은 전부 '켜는 것'뿐입니다 — 지우거나 바꾸는 수리는 하지 않습니다.
(무엇을 지워야 할지 스스로 판단해 지우는 비서는 위험합니다. 그건 사람과 상의할 일.)
"""
import json
import os
import shutil
import socket
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MELO_PORT = 8767
MELO_PY = r"D:\lucy-tts\venv\Scripts\python.exe"
OLLAMA_PORT = 11434
WEB_PORT = 8765
TASK_NAME = "Lucy 알림"
TAILSCALE_EXE = r"C:\Program Files\Tailscale\tailscale.exe"

# 같은 프로세스에서 같은 수리를 반복하지 않습니다 — 켜도 안 살아나는 서버를
# 1분마다 다시 켜면 프로세스만 쌓입니다. 한 번 시도했으면 다음 실행 때 다시.
_tried = set()


def _port_open(port, timeout=0.4):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _launch(cmd):
    """루시가 죽어도 살아남게 완전히 떼어서 켭니다(창 없음).

    CREATE_BREAKAWAY_FROM_JOB: 이 점검이 작업 스케줄러(notify.py) 안에서 돌 때,
    스케줄러의 잡 오브젝트가 notify 종료와 함께 **자식(방금 켠 서버)까지 거둬 갑니다**
    (voice_autostart에서 실측). 잡을 탈출시켜야 서버가 살아남고, 탈출이 금지된
    환경이면 일반 분리로 물러섭니다.
    """
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200))
    breakaway = 0x01000000                      # CREATE_BREAKAWAY_FROM_JOB
    for f in (flags | breakaway, flags):
        try:
            subprocess.Popen(cmd, cwd=BASE_DIR,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=f, close_fds=True)
            return
        except OSError:
            continue


# ── 개별 점검 ─────────────────────────────────────────────────────
# 각 점검은 (정상?, 사람에게 할 말)을 돌려줍니다. fix=True면 고치기까지 한 뒤의 말입니다.

def _check_melo(config, fix):
    import tts
    if not tts.enabled(config) or "melo" not in tts.engines(config):
        return True, ""                      # 안 쓰는 기능은 점검하지 않습니다
    if _port_open(MELO_PORT):
        return True, "로컬 목소리 서버(멜로): 켜져 있음"
    if not os.path.exists(MELO_PY):
        return False, ("로컬 목소리 서버가 꺼져 있고 D:\\lucy-tts도 없어 켤 수 없습니다"
                       " — 그동안은 구글 목소리로 말합니다")
    if not fix or "melo" in _tried:
        return False, "로컬 목소리 서버가 꺼져 있습니다 — 그동안은 구글 목소리로 말합니다"
    _tried.add("melo")
    _launch([MELO_PY, os.path.join(BASE_DIR, "tts_local_server.py")])
    return False, ("로컬 목소리 서버가 꺼져 있어 다시 켰습니다"
                   " — 모델을 올리는 몇십 초 동안은 구글 목소리로 말합니다")


def _check_ollama(config, fix):
    if _port_open(OLLAMA_PORT):
        return True, "Ollama(기억·지식 검색 임베딩): 켜져 있음"
    exe = shutil.which("ollama") or os.path.expandvars(
        r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    if not os.path.exists(exe):
        return False, ("Ollama가 꺼져 있고 설치도 안 보입니다 — 기억·지식 검색이"
                       " 단어겹침으로 강등됩니다(멈추진 않음)")
    if not fix or "ollama" in _tried:
        return False, "Ollama가 꺼져 있습니다 — 기억·지식 검색이 단어겹침으로 강등됩니다"
    _tried.add("ollama")
    _launch([exe, "serve"])
    return False, ("Ollama(기억 검색)가 꺼져 있어 다시 켰습니다"
                   " — 다음 검색부터 임베딩으로 돌아갑니다")


def _check_notifier(config, fix):
    # 이 작업이 없으면 예약 알림·아침 브리핑·지식 동기화·기억 정리가 전부 죽습니다.
    # 만드는 건 사람 몫으로 둡니다(스케줄러 등록을 말없이 하는 비서는 과합니다).
    try:
        gone = subprocess.run(
            ["schtasks", "/query", "/tn", TASK_NAME],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).returncode != 0
    except (OSError, subprocess.SubprocessError):
        return True, ""                      # 스케줄러 자체를 못 물어보면 판단 보류
    if gone:
        return False, (f"작업 스케줄러에 '{TASK_NAME}'이 없습니다 — 예약 알림·아침 브리핑·"
                       "새벽 동기화가 전부 멈춰 있습니다 (README의 예약·알림 절 참조)")
    return True, f"알림 일꾼(작업 스케줄러 '{TASK_NAME}'): 등록됨"


def _check_google(config, fix):
    if not config.get("google", {}).get("enabled", True):
        return True, ""
    try:
        import gmail_calendar
        if gmail_calendar.ready():
            # 자격증명이 있어도 **토큰의 권한이 낡았을** 수 있습니다 — 코드의 스코프가
            # 늘었는데 옛 토큰이 남아 있으면 다음 호출이 재승인(브라우저)을 요구하고,
            # 배경(아침 브리핑)은 브라우저를 못 열어 메일·일정이 조용히 빠집니다.
            # ⚠️creds.scopes가 아니라 토큰 **파일**의 scopes를 읽어야 합니다(세션54 실측
            # — 라이브러리가 그 속성을 '요청한' 스코프로 덮어써 검사가 항상 통과함).
            if os.path.exists(gmail_calendar.TOKEN_PATH):
                try:
                    with open(gmail_calendar.TOKEN_PATH, "r", encoding="utf-8-sig") as f:
                        granted = set(json.load(f).get("scopes") or [])
                except (OSError, ValueError):
                    granted = set()
                if not set(gmail_calendar.SCOPES) <= granted:
                    return False, ("구글 토큰의 권한이 낡았습니다 — 터미널 루시에서 '메일"
                                   " 확인해줘'라고 한 번 시켜 재승인 창에서 '허용'을 눌러"
                                   " 주세요. 그 전까지 아침 브리핑의 메일·일정이 빠질 수"
                                   " 있습니다")
            return True, "구글 연동(메일·캘린더): 정상"
    except Exception:
        pass
    return False, ("구글 연동이 끊겨 있습니다 — 메일·캘린더를 못 봅니다"
                   " (바탕화면의 루시_구글연동_가이드.md 참조)")


def _check_web(config, fix):
    # 웹 화면(8765)은 폰(Tailscale)에서 들어오는 유일한 문입니다. 이게 죽으면
    # 밖에서는 루시가 통째로 사라진 것과 같은데, PC 앞에 아무도 없어 알 길이 없습니다.
    if not config.get("web", {}).get("enabled", True):
        return True, ""
    if _port_open(WEB_PORT):
        return True, f"웹 화면(포트 {WEB_PORT}): 켜져 있음"
    if not fix or "web" in _tried:
        return False, "웹 화면 서버가 꺼져 있습니다 — 폰에서 접속할 수 없습니다"
    _tried.add("web")
    # pythonw로 켭니다(창 없음). web.py의 print는 pythonw에서 조용히 무시될 뿐 죽지
    # 않으므로(멜로 서버와 달리) 발사대 없이 직접 켜도 됩니다 — 부팅 작업 "Lucy 웹"과 동일.
    py = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(py):
        py = sys.executable
    _launch([py, os.path.join(BASE_DIR, "web.py")])
    return False, "웹 화면 서버가 꺼져 있어 다시 켰습니다 — 몇 초 뒤부터 폰에서 접속됩니다"


def _check_disk(config, fix):
    # C:가 차면 루시만이 아니라 윈도우가 같이 병듭니다(업데이트 실패·임시파일 오류).
    # 고치는 건 사람 몫이라(무엇을 지울지는 상의할 일) 여기서는 알리기만 합니다.
    min_free = float(config.get("disk", {}).get("min_free_gb", 15))
    try:
        free_gb = shutil.disk_usage("C:\\").free / (1024 ** 3)
    except OSError:
        return True, ""                      # 못 재면 판단 보류
    if free_gb >= min_free:
        return True, f"C: 드라이브 여유 공간: {free_gb:.1f}GB"
    hints = []
    hf = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    if os.path.isdir(hf):
        hints.append("AI 모델 캐시(~\\.cache\\huggingface — 전에도 여기가 주범)")
    hints.append("휴지통·임시파일(디스크 정리)")
    hints.append("큰 파일은 D:로 옮기기")
    return False, (f"C: 드라이브 여유가 {free_gb:.1f}GB뿐입니다({min_free:.0f}GB 미만)"
                   " — 우선 볼 곳: " + ", ".join(hints))


def _check_groq_key(config, fix):
    # 받아쓰기 키 하나가 네 기능을 받칩니다: 마이크('음성')·연속 음성(/음성모드)·
    # 웹 음성 대화(🎤)·녹음/영상 받아쓰기(자막 포함). 키가 사라지면 각자 제자리에서
    # 조용히 안내만 하고 넘어가므로, 여기서 한 번에 알립니다. 고치는 건 사람 몫.
    if not config.get("voice", {}).get("enabled", True):
        return True, ""
    path = os.path.join(BASE_DIR, config.get("voice", {}).get("key_file", "keys/groq.txt"))
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            key = f.read().strip()
    except OSError:
        key = ""
    if key:
        return True, "받아쓰기 키(Groq): 있음"
    return False, ("받아쓰기 키(keys/groq.txt)가 없거나 비었습니다 — 음성 입력·웹 🎤·"
                   "녹음/영상 받아쓰기가 전부 멈춥니다 (console.groq.com에서 무료 발급)")


def _check_ffmpeg(config, fix):
    # 동영상 편집(edit_video)의 유일한 다리입니다. 지워지거나 다른 PC로 이사하면
    # 도구가 그때그때 안내만 하므로, 여기서 미리 알립니다. 설치는 사람 몫(winget 한 줄).
    if not config.get("video", {}).get("enabled", True):
        return True, ""
    try:
        import video
        if video.ready(config):
            return True, "ffmpeg(동영상 편집): 있음"
    except Exception:
        return True, ""                      # 모듈 자체가 못 뜨면 판단 보류
    return False, ("ffmpeg가 없습니다 — 동영상 편집(자르기·자막·받아쓰기 연계)을 못 합니다."
                   " 설치: winget install -e --id Gyan.FFmpeg")


def _ts_ip(exe):
    """Tailscale에 물어본 내 주소(연결돼 있으면 100.x). 못 물어보면 None(판단 보류)."""
    try:
        out = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    ip = (out.stdout or "").strip().splitlines()[0].strip() if (out.stdout or "").strip() else ""
    return ip if out.returncode == 0 and ip.startswith("100.") else ""


def _check_tailscale(config, fix):
    # 집 밖(LTE)에서 폰이 루시(웹 8765)에 닿는 유일한 길입니다. 꺼져 있어도 집
    # 와이파이에서는 멀쩡해서 알아채기 어렵고, 밖에 나가서야 "안 돼요"가 됩니다.
    exe = shutil.which("tailscale") or TAILSCALE_EXE
    if not os.path.exists(exe):
        return True, ""                      # 안 쓰는 PC에서는 잔소리하지 않습니다
    ip = _ts_ip(exe)
    if ip is None:
        return True, ""                      # 못 물어보면 판단 보류
    if ip:
        return True, f"Tailscale(밖에서 접속): 연결됨 ({ip})"
    if not fix or "tailscale" in _tried:
        return False, "Tailscale이 꺼져 있습니다 — 집 밖에서 폰으로 접속할 수 없습니다"
    _tried.add("tailscale")
    # 'up'은 켜는 것뿐이라 수리 원칙에 맞습니다. 로그아웃 상태면 브라우저 승인이
    # 필요해 여기서는 못 살립니다 — timeout으로 매달리지 않고 정직하게 알립니다.
    try:
        subprocess.run([exe, "up", "--timeout=8s"], capture_output=True, timeout=15,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        pass
    if _ts_ip(exe):
        return False, "Tailscale이 꺼져 있어 다시 켰습니다 — 밖에서 접속이 다시 됩니다"
    return False, ("Tailscale이 꺼져 있고 켜도 안 살아납니다 — 로그인이 풀렸을 수"
                   " 있습니다(트레이의 Tailscale 아이콘에서 로그인)")


def _check_brains(config, fix):
    """조용한 고장 — 특정 두뇌만 계속 죽는데 폴백이 매번 받아내 사람은 모르는 상태.
    다른 점검과 달리 '지금 고장'이 아니라 '며칠치 계측의 추세'를 봅니다. 고치는 건 사람 몫
    (키 재발급·유료 전환·모델 교체는 상의할 일)이라 여기서는 알리기만 합니다."""
    try:
        import status
        faults = status.silent_faults(config)
    except Exception:
        return True, ""                      # 계측을 못 읽으면 판단 보류(조용히)
    if not faults:
        return True, "두뇌 계측: 만성 고장 없음"
    return False, ("두뇌가 조용히 고장 나 있습니다(폴백이 가려주는 중) — "
                   + " / ".join(faults))


def _check_dead_brains(config, fix):
    """폴백 사슬 아래쪽에서 공급자가 내려버린 두뇌 — 조용한 고장 경보의 사각지대입니다.

    _check_brains(계측)는 '불려본 두뇌'만 봅니다. 안 불린 두뇌는 실패조차 못 쌓아
    문턱에 영영 안 닿습니다(2026-07-23 실측: 404로 죽은 Groq qwen3-32b가 순위 5위에
    그대로 있었는데 경보는 '만성 고장 없음'이었음).

    ⚠️여기서는 네트워크를 두드리지 않습니다 — 실제 확인은 새벽 일과(daily의
    brain_probe)가 주 1회 하고, 여기는 적어둔 결과만 읽습니다. 루시를 켤 때마다
    두뇌 열 개에 인사를 보내면 시작이 그만큼 느려집니다."""
    try:
        import brainprobe
        bad = brainprobe.alarm_lines(config)
    except Exception:
        return True, ""                      # 기록을 못 읽으면 판단 보류(조용히)
    if not bad:
        try:
            return True, brainprobe.status_line(config)
        except Exception:
            return True, ""
    return False, ("두뇌가 죽어 있습니다(폴백 사슬 아래라 티가 안 납니다) — "
                   + " / ".join(bad) + " · 모델 교체는 config.json에서 사람이 정합니다")


CHECKS = [_check_melo, _check_ollama, _check_notifier, _check_google, _check_web,
          _check_disk, _check_groq_key, _check_ffmpeg, _check_tailscale, _check_brains,
          _check_dead_brains]


# ── 세 문 ─────────────────────────────────────────────────────────
def run(config, notify=print, fix=True, verbose=False):
    """
    점검하고, 문제는 알리고, 고칠 수 있으면 고칩니다. (문제 개수)
    verbose=False면 문제만 말합니다 — 시작할 때마다 '정상' 네 줄을 읽게 하지 않습니다.
    """
    problems = 0
    for check in CHECKS:
        try:
            ok, note = check(config, fix)
        except Exception as e:
            ok, note = True, ""
            notify(f"({check.__name__} 점검 실패: {type(e).__name__} — 건너뜀)")
        if not ok:
            problems += 1
            notify("⚠ " + note)
        elif verbose and note:
            notify("✓ " + note)
    if verbose and not problems:
        notify("몸에 문제 없음.")
    return problems


def report(config):
    """self_check 도구용 — 점검·수리 결과를 한 덩어리 글로. 모델이 이걸 읽고 사용자에게 설명합니다."""
    lines = []
    run(config, notify=lines.append, fix=True, verbose=True)
    return "\n".join(lines)
