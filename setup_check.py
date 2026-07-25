# -*- coding: utf-8 -*-
"""
새 PC 점검 — 이 폴더를 다른 컴퓨터로 옮겼을 때 뭐가 빠졌는지 알려줍니다.

이 비서는 폴더 하나가 전부(코드·설정·키·기억)지만, PC에 미리 있어야 하는 게 둘 있습니다:
  · 파이썬        — 없으면 아예 안 켜짐
  · Ollama(선택)  — 없으면 최후의 보루(로컬 모델)와 기억 검색(임베딩)이 빠짐

실행:  setup_check.bat 더블클릭  (또는 python setup_check.py)
       python setup_check.py --offline   → 네트워크 확인 없이 파일만 점검
"""
import json
import os
import sys
import urllib.error
import urllib.request

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OLLAMA_TAGS = "http://localhost:11434/api/tags"

# User-Agent가 없으면 Groq 등의 Cloudflare가 403으로 막습니다(파이썬 기본 UA는 봇 취급).
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

OK, WARN, BAD = "[정상]", "[주의]", "[없음]"
problems = []   # (심각도, 무엇이, 어떻게 고치는지)


def say(mark, text, detail=""):
    print(f"  {mark} {text}" + (f"\n         {detail}" if detail else ""))


def head(title):
    print(f"\n── {title} " + "─" * max(0, 46 - len(title)))


def read_key(rel_path):
    """키 파일을 읽습니다. (키, 문제) — BOM은 utf-8-sig로 걷어냅니다."""
    path = os.path.join(BASE_DIR, rel_path)
    if not os.path.exists(path):
        return None, "파일 없음"
    raw = open(path, "rb").read()
    if not raw.strip():
        return None, "파일이 비어 있음"
    # BOM이 남은 채 헤더에 들어가면 UnicodeEncodeError로 터집니다. 여기서 미리 경고합니다.
    bom = raw.startswith(b"\xef\xbb\xbf")
    with open(path, "r", encoding="utf-8-sig") as f:
        key = f.readline().strip()
    if not key:
        return None, "내용이 비어 있음"
    return key, ("BOM이 붙어 있음 (코드가 걷어내지만 BOM 없이 다시 저장하는 게 안전)" if bom else "")


def mask(key):
    return key[:6] + "…" + key[-4:] if len(key) > 12 else "…"


# ── 1. 파이썬 ────────────────────────────────────────────────────
def check_python():
    head("파이썬")
    v = sys.version_info
    if v < (3, 8):
        say(BAD, f"파이썬 {v.major}.{v.minor} — 너무 낮습니다 (3.8 이상 필요)")
        problems.append((BAD, "파이썬 3.8+", "https://www.python.org/downloads/ 에서 설치 "
                                             "(설치 화면의 'Add python.exe to PATH' 반드시 체크)"))
    else:
        say(OK, f"파이썬 {v.major}.{v.minor}.{v.micro}")
    say(OK, "추가 설치 패키지 없음 (표준 라이브러리만 사용 — pip install 불필요)")


# ── 2. 폴더 안의 파일 ────────────────────────────────────────────
def check_files():
    head("파일")
    need = ["agent.py", "tools.py", "memory_search.py", "session.py", "voice.py", "config.json"]
    missing = [f for f in need if not os.path.exists(os.path.join(BASE_DIR, f))]
    if missing:
        say(BAD, f"빠진 파일: {', '.join(missing)}")
        problems.append((BAD, "코드 파일 누락", "원래 PC의 my-agent 폴더를 통째로 다시 복사하세요"))
    else:
        say(OK, f"코드·설정 {len(need)}개 모두 있음")

    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        say(BAD, f"config.json을 읽을 수 없음 ({type(e).__name__})")
        problems.append((BAD, "config.json 손상", "원래 PC에서 다시 복사하세요"))
        return None
    say(OK, f"config.json 정상 (이름: {config.get('name', '비서')}, 모델 {len(config.get('models', []))}단)")
    return config


# ── 3. 기억 ─────────────────────────────────────────────────────
def check_memory():
    head("기억")
    notes = os.path.join(BASE_DIR, "memory", "notes.md")
    if os.path.exists(notes):
        with open(notes, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip().startswith("-")]
        say(OK, f"장기 기억 {len(lines)}건 (memory/notes.md)")
    else:
        say(WARN, "장기 기억이 없음 — 새 비서로 시작합니다 (문제는 아님)")

    hist = os.path.join(BASE_DIR, "memory", "history")
    days = len([f for f in os.listdir(hist) if f.endswith(".md")]) if os.path.isdir(hist) else 0
    say(OK, f"대화 기록 {days}일치 (memory/history)")

    # index.json은 지워도 자동 재생성되므로 없어도 정상입니다.
    if not os.path.exists(os.path.join(BASE_DIR, "memory", "index.json")):
        say(OK, "임베딩 캐시 없음 — 첫 질문 때 자동으로 다시 만들어집니다")


# ── 4. Ollama (로컬 두뇌 + 기억 검색) ────────────────────────────
def check_ollama(config, offline):
    head("Ollama (로컬 두뇌 · 기억 검색)")
    local = next((m for m in config.get("models", []) if m.get("key_file") is None), None)
    want = [m for m in (local and local["model"], config.get("embed_model")) if m]

    if offline:
        say(WARN, "건너뜀 (--offline)")
        return

    try:
        req = urllib.request.Request(OLLAMA_TAGS, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=5) as resp:
            have = [m["name"] for m in json.loads(resp.read().decode("utf-8")).get("models", [])]
    except Exception:
        say(BAD, "Ollama가 실행돼 있지 않음 (localhost:11434 응답 없음)")
        print("         → 없어도 비서는 켜집니다. 다만 이 둘이 빠집니다:")
        print("           · 최후의 보루: Gemini·Groq가 둘 다 막히면 답을 못 받습니다")
        print("           · 기억 검색: 임베딩 대신 단어 겹침으로 강등됩니다(멈추진 않음)")
        problems.append((WARN, "Ollama 없음", "https://ollama.com 설치 후 → "
                                              + "  ".join(f"ollama pull {m}" for m in want)))
        return

    say(OK, f"Ollama 실행 중 (설치된 모델 {len(have)}개)")
    for want_model in want:
        # 태그(:latest)가 생략된 채 저장되는 경우가 있어 앞부분만 비교합니다.
        base = want_model.split(":")[0]
        if any(h == want_model or h.split(":")[0] == base for h in have):
            say(OK, f"{want_model} 있음")
        else:
            say(BAD, f"{want_model} 없음")
            problems.append((WARN, f"{want_model} 모델 없음", f"ollama pull {want_model}"))


# ── 5. API 키 (진짜로 불러봅니다) ────────────────────────────────
def ping_model(entry, key):
    """가장 싼 요청을 한 번 던져서 키가 진짜 살아있는지 확인합니다."""
    body = json.dumps({
        "model": entry["model"],
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
    }, ensure_ascii=False).encode("utf-8")
    url = entry["base_url"].rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": UA,
                 "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25):
            return OK, "키 정상 (실제 호출 성공)"
    except urllib.error.HTTPError as e:
        if e.code == 429:
            # 한도 초과는 키가 살아있다는 뜻입니다. 시간이 지나면 풀립니다.
            return WARN, "무료 한도 초과 — 키는 유효합니다 (다음 모델이 대신 답합니다)"
        if e.code in (401, 403):
            return BAD, f"키가 거부됨 ({e.code}) — 키를 다시 발급받으세요"
        return WARN, f"HTTP {e.code} — 일시적 오류일 수 있습니다"
    except Exception as e:
        return BAD, f"연결 실패 ({type(e).__name__}) — 인터넷 확인"


def check_models(config, offline):
    head("API 키 · 모델")
    alive = 0
    for entry in config.get("models", []):
        label, key_file = entry["label"], entry.get("key_file")

        if not key_file:                       # 로컬 모델은 위에서 이미 확인했습니다
            say(OK, f"{label} — 키 불필요")
            alive += 1
            continue

        key, issue = read_key(key_file)
        if not key:
            say(BAD, f"{label} — {issue} ({key_file})")
            problems.append((WARN, f"{label} 키 없음",
                             f"{key_file} 에 키를 넣으세요 (BOM 없이 저장)"))
            continue
        if issue:
            say(WARN, f"{label} — {issue}")

        if offline:
            say(OK, f"{label} — 키 있음 {mask(key)} (호출 확인은 건너뜀)")
            alive += 1
            continue

        mark, detail = ping_model(entry, key)
        say(mark, f"{label} — {detail}")
        if mark != BAD:
            alive += 1
        else:
            problems.append((WARN, f"{label} 사용 불가", detail))

    if alive == 0:
        problems.append((BAD, "쓸 수 있는 두뇌가 하나도 없음",
                         "키를 넣거나 Ollama를 설치하세요 — 지금은 비서가 답할 수 없습니다"))
    return alive


# ── 6. 검색 · 음성 ──────────────────────────────────────────────
def check_extras(config):
    head("검색 · 음성")
    for backend in config.get("search_backends", []):
        kind = backend.get("type")
        if kind == "wikipedia":
            say(OK, "위키백과 — 키 불필요 (항상 작동하는 바닥)")
            continue
        key_file = backend.get("key_file")
        key, issue = read_key(key_file) if key_file else (None, "설정 없음")
        if key:
            say(OK, f"{kind} — 키 있음 {mask(key)}" + (f"  ({issue})" if issue else ""))
        else:
            say(WARN, f"{kind} — {issue} → 위키백과로만 검색합니다 (최신·시사 정보에 약함)")

    voice_cfg = config.get("voice", {})
    if not voice_cfg.get("enabled", True):
        say(WARN, "음성 입력 — 설정에서 꺼져 있음")
    elif sys.platform != "win32":
        # 녹음을 윈도우 기본 기능(winmm)으로 직접 호출하므로 다른 OS에선 이 기능만 빠집니다.
        say(WARN, f"음성 입력 — 윈도우 전용입니다 (지금 OS: {sys.platform}). 나머지는 정상 작동")
    else:
        key, _ = read_key(voice_cfg.get("key_file", "keys/groq.txt"))
        if key:
            say(OK, "음성 입력 — 준비됨 (프롬프트에 '음성' 또는 '/v')")
        else:
            say(WARN, "음성 입력 — Groq 키가 없어 받아쓰기 불가")


def check_dev_tools(config):
    """블렌더·유니티·C#·영상 도구 — 없어도 비서는 돌지만 그 기능만 빠집니다.
    경로는 portable이 알아서 찾으므로, 다른 PC로 옮겨도 설치만 돼 있으면 잡힙니다."""
    head("작업 도구 (선택 · 해당 기능에만 필요)")
    import shutil
    try:
        import portable
    except Exception:
        portable = None

    blender = None
    if portable:
        try:
            import blender3d
            blender = blender3d.find_exe(config)
        except Exception:
            blender = portable.find_blender()
    if blender:
        say(OK, f"블렌더 — {blender}")
    else:
        say(WARN, "블렌더 없음 → 3D(blender_3d·blender_batch)만 빠짐",
            "winget install -e --id BlenderFoundation.Blender")

    unity = portable.find_unity() if portable else None
    if unity:
        say(OK, f"유니티 에디터 — {unity}")
    else:
        say(WARN, "유니티 없음 → 유니티 C#(unity_run·build 등)만 빠짐",
            "Unity Hub로 설치, 또는 config unity.exe에 경로")

    if shutil.which("dotnet"):
        say(OK, "dotnet SDK — C# 실행/유니티 검증 가능")
    else:
        say(WARN, "dotnet 없음 → code_run의 C#(.cs)만 빠짐",
            "https://dotnet.microsoft.com/download")

    if shutil.which("ffmpeg"):
        say(OK, "ffmpeg — 동영상 편집 가능")
    else:
        say(WARN, "ffmpeg 없음 → edit_video만 빠짐", "winget install ffmpeg")


# ── 결과 ────────────────────────────────────────────────────────
def main():
    offline = "--offline" in sys.argv

    print("=" * 60)
    print("  나만의 AI 비서 — 새 PC 점검")
    print(f"  폴더: {BASE_DIR}")
    if offline:
        print("  (--offline: 네트워크 확인 없이 파일만 점검합니다)")
    print("=" * 60)

    check_python()
    config = check_files()
    if not config:
        print("\n설정을 읽지 못해 여기서 멈춥니다.")
        return 1

    check_memory()
    check_ollama(config, offline)
    alive = check_models(config, offline)
    check_extras(config)
    check_dev_tools(config)

    head("결과")
    blockers = [p for p in problems if p[0] == BAD]
    if not problems:
        print("  전부 정상입니다. start.bat 으로 바로 시작하세요.")
    elif not blockers:
        print(f"  지금 상태로도 비서는 작동합니다 (쓸 수 있는 두뇌 {alive}개).")
        print("  아래를 채우면 더 좋아집니다:\n")
        for _, what, how in problems:
            print(f"    · {what}\n      → {how}")
    else:
        print("  먼저 해결해야 켜집니다:\n")
        for mark, what, how in problems:
            print(f"    {mark} {what}\n      → {how}")

    print()
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
