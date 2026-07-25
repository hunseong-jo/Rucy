# -*- coding: utf-8 -*-
"""
웹 화면 — 브라우저(폰 포함)에서 루시를 부릅니다. 표준 라이브러리만 씁니다.

    python web.py            → 주소가 뜹니다. 폰 브라우저에 그 주소를 칩니다(같은 와이파이).

**루시는 하나입니다.** 이 서버는 컴퓨터에서 도는 그 루시를 들여다보는 창일 뿐이라,
기억·지식창고·실수 노트·대화 기록이 터미널의 루시와 같은 것 하나입니다(사본이 없으므로
동기화할 것도 없습니다). 한 턴의 흐름도 agent.respond() 한 벌을 함께 씁니다.

터미널과 다른 점 세 가지:
1. **파일 쓰기·코드 실행은 거부합니다.** 터미널에서는 [y/N]로 사람이 막을 수 있지만,
   웹에서는 input()이 서버를 멈춰 세웁니다. 물어볼 수 없으면 실행하지 않습니다.
2. **폰 사진을 올릴 수 있습니다.** 루시는 PC 파일만 볼 수 있으므로, 폰 사진은 올려서
   PC에 저장한 뒤에야 볼 수 있습니다(uploads 폴더).
3. **첫 접속에 PIN을 묻습니다.** 같은 와이파이의 누구나 이 주소에 닿을 수 있는데,
   여기엔 대화·기억·기록이 다 있습니다. PIN은 keys/web_pin.txt(없으면 처음 켤 때 만들어
   화면에 보여줍니다). 한 번 통과한 기기는 쿠키로 기억해 다시 묻지 않습니다.
"""
import hmac
import html
import http.server
import io
import json
import mimetypes
import os
import re
import secrets
import socket
import socketserver
import threading
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE_DIR, "uploads")
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
PAGE = os.path.join(BASE_DIR, "web", "index.html")

import agent        # noqa: E402
import tools        # noqa: E402

PORT = 8765

# 그림은 대화에 바로 띄웁니다 — 답에 적힌 경로를 찾아냅니다 (윈도우/리눅스 경로 지원).
IMG_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/)[^\s\"'<>|]+?\.(?:png|jpg|jpeg|webp|gif)", re.I)

# 문서는 내려받기 링크로 답 밑에 답니다("그 기획서 폰으로 줘"). 한국어 파일명에는
# 공백이 흔해서(예: 2023 앱기획 강의자료.pdf) 그림과 달리 공백을 허용합니다 —
# 드라이브 글자나 /에서 시작해 확장자에서 끝나고, 실제로 존재하는 파일만 남기므로
# 문장이 딸려 들어올 걱정은 없습니다(존재 검사가 걸러냄).
DOC_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|/)[^\"'<>|*?\r\n]+?\.(?:pdf|docx?|xlsx?|pptx?|hwpx?|txt|md|csv|zip)\b", re.I)

# 브라우저가 아무 파일이나 빨아가지 못하게 여기 적힌 곳만 엽니다.
# main()이 config의 문서 검색 범위(filesearch.roots — 문서·다운로드)를 더합니다:
# search_files가 찾아준 파일을 폰으로 내려받는 길이라, 검색 범위와 같아야 말이 됩니다.
ALLOWED = [DESKTOP, UPLOADS, BASE_DIR]

# 허용 폴더 안이라도 절대 안 내주는 것 — BASE_DIR(my-agent 전체)이 열려 있어서,
# 이게 없으면 PIN 통과 기기가 /file로 API 키·구글 토큰·PIN 파일까지 받아갈 수 있습니다.
# (PIN 뒤라 당장 사고는 아니지만, 쿠키 하나 새면 키가 통째로 새는 구조는 안 됩니다)
DENIED = [os.path.join(BASE_DIR, "keys"),
          os.path.join(BASE_DIR, "memory", "web_tokens.json")]

_lock = threading.Lock()        # 한 대화를 여러 창이 동시에 건드리면 대화 기록이 엉킵니다
_config = None
_state = None

# ── 긴 턴은 배경으로 ─────────────────────────────────────────────
# respond()가 몇 분짜리 도구(영상 인코딩 등)를 돌리면, 예전엔 그 fetch가 몇 분을 매달렸고
# 다른 창의 질문도 _lock에 줄을 서서 **웹 루시 전체가 침묵**했습니다. 이제 한 턴은 배경
# 스레드에서 돌고, 제때 안 끝나면 작업표(id)를 돌려줍니다 — 폰은 /poll로 결과를 찾아가고,
# 그동안 화면은 살아 있습니다(다음 질문은 배경에서 _lock 차례를 기다립니다).
_jobs = {}                      # id → {"done", "payload", "extra", "at"}


def _run_job(job, fn):
    """배경 턴 하나. 오류도 답의 한 형태로 담습니다 — 폰이 /poll에서 그대로 받아 보여줍니다."""
    try:
        job["payload"] = fn()
    except agent.ImageUnreadable as e:
        job["payload"] = {"error": f"이미지를 읽지 못했습니다: {e}"}
    except agent.AllModelsFailed as e:
        job["payload"] = {"error": f"모든 두뇌가 실패했습니다.\n{e}"}
    except Exception as e:
        job["payload"] = {"error": f"실패했습니다: {type(e).__name__}: {e}"}
    job["done"] = True

# ── 문 잠금(PIN) ──────────────────────────────────────────────────
# 같은 와이파이의 누구나 8765에 닿을 수 있고, 여기엔 대화·기억·기록이 다 있습니다.
# (파일 쓰기·실행은 원래 막혀 있지만 '읽기'만으로도 다 새어 나갑니다)
# 통과한 기기에는 무작위 토큰을 쿠키로 줘서 다시 묻지 않고, 토큰은 파일에 남겨
# 서버를 껐다 켜도 폰이 PIN을 다시 넣을 필요가 없게 합니다.
PIN_FILE = os.path.join(BASE_DIR, "keys", "web_pin.txt")
TOKEN_FILE = os.path.join(BASE_DIR, "memory", "web_tokens.json")

PIN = None                      # main()이 채웁니다
_tokens = []                    # 통과한 기기들의 토큰(최근 10개만)
_fails = 0                      # 연속으로 틀린 횟수 — 5번이면 잠급니다
_locked_until = 0.0

PIN_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PIN</title>
<style>
  body{font-family:sans-serif;background:#1b1e24;color:#eee;display:flex;
       align-items:center;justify-content:center;min-height:100vh;margin:0}
  .card{background:#262a33;padding:32px 28px;border-radius:16px;text-align:center;width:260px}
  input{font-size:28px;letter-spacing:8px;text-align:center;width:100%;box-sizing:border-box;
        padding:10px 0;margin:16px 0;border-radius:8px;border:1px solid #444;
        background:#1b1e24;color:#eee}
  button{font-size:16px;padding:10px 0;width:100%;border-radius:8px;border:0;
         background:#5b8def;color:#fff}
  #msg{color:#f88;min-height:1.2em;font-size:13px;margin-top:10px}
</style></head><body><div class="card">
  <div>PIN을 입력하세요</div>
  <input id="pin" inputmode="numeric" autocomplete="one-time-code" maxlength="12" autofocus>
  <button onclick="go()">열기</button><div id="msg"></div>
<script>
async function go(){
  const r = await fetch('/pin', {method:'POST',
    body: JSON.stringify({pin: document.getElementById('pin').value})});
  const d = await r.json().catch(()=>({}));
  if (r.ok) location.reload();
  else document.getElementById('msg').textContent = d.error || '실패했습니다';
}
document.getElementById('pin').addEventListener('keydown', e=>{if(e.key==='Enter')go()});
</script></div></body></html>"""


def load_pin():
    """PIN을 읽고, 없으면 만들어 저장합니다. 바꾸려면 keys/web_pin.txt를 고치면 됩니다."""
    try:
        with open(PIN_FILE, "r", encoding="utf-8-sig") as f:
            pin = f.read().strip()
        if pin:
            return pin
    except OSError:
        pass
    pin = "".join(secrets.choice("0123456789") for _ in range(6))
    os.makedirs(os.path.dirname(PIN_FILE), exist_ok=True)
    with open(PIN_FILE, "w", encoding="utf-8") as f:
        f.write(pin + "\n")
    return pin


def _load_tokens():
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return [str(t) for t in data] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save_tokens():
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(_tokens, f)


def deny_confirm(question):
    """웹에서는 위험한 동작을 실행하지 않습니다(사람에게 물어볼 방법이 없으므로)."""
    return False


def allowed(path):
    real = os.path.realpath(path)
    if any(real.startswith(os.path.realpath(d)) for d in DENIED):
        return False
    return any(real.startswith(os.path.realpath(root)) for root in ALLOWED)


def find_images(answer):
    out = []
    for m in IMG_PATH.finditer(answer):
        p = m.group(0)
        if os.path.exists(p) and allowed(p) and p not in out:
            out.append(p)
    return out


def find_docs(answer):
    """답에 적힌 문서 경로 — 실제로 있고 허용 폴더 안에 있는 것만 내려받기 링크가 됩니다."""
    out = []
    for m in DOC_PATH.finditer(answer):
        p = m.group(0)
        if os.path.isfile(p) and allowed(p) and p not in out:
            out.append(p)
    return out


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))          # 실제로 보내지는 않습니다 — 내 주소만 알아냅니다
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass                                # 요청마다 콘솔을 어지럽히지 않습니다

    # ── 보내기 도우미 ──
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    # ── 문 잠금 ──
    def _authed(self):
        """이 요청의 기기가 PIN을 통과했는가(쿠키의 토큰으로 판단)."""
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "lucy_auth" and value in _tokens:
                return True
        return False

    def _handle_pin(self, raw):
        global _fails, _locked_until
        now = time.time()
        if now < _locked_until:
            wait = int(_locked_until - now) + 1
            return self._json({"error": f"틀린 PIN이 잦아 잠갔습니다. {wait}초 뒤에 다시 하세요."}, 429)
        try:
            pin = str(json.loads(raw or b"{}").get("pin") or "").strip()
        except ValueError:
            pin = ""
        # compare_digest: 비교 시간이 내용에 따라 달라지지 않게(한 자리씩 재보는 공격 방지)
        if not (pin and hmac.compare_digest(pin, PIN or "")):
            _fails += 1
            time.sleep(1.0)                 # 기계가 마구 넣어보는 속도를 늦춥니다
            if _fails >= 5:
                _fails = 0
                _locked_until = time.time() + 300
                return self._json({"error": "5번 틀려서 5분간 잠급니다."}, 429)
            return self._json({"error": "PIN이 틀렸습니다."}, 403)
        _fails = 0
        token = secrets.token_hex(16)
        _tokens.append(token)
        del _tokens[:-10]                   # 기기 10대면 충분 — 오래된 것부터 밀어냅니다
        _save_tokens()
        # HttpOnly: 페이지에 끼어든 스크립트가 토큰을 못 읽게. 90일 뒤 다시 묻습니다.
        return self._send(200, '{"ok": true}', extra={
            "Set-Cookie": f"lucy_auth={token}; Max-Age=7776000; Path=/; HttpOnly; SameSite=Lax"})

    # ── GET ──
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)

        if not self._authed():
            # 첫 화면만 PIN 입력창으로 바꿔치기하고, 나머지(/file·/say)는 전부 닫습니다 —
            # 대화 내용이 담긴 mp3나 그림 파일이 PIN 없이 새어 나가면 잠근 의미가 없습니다.
            if url.path in ("/", "/index.html"):
                return self._send(200, PIN_PAGE, "text/html; charset=utf-8")
            return self._send(401, b"pin required", "text/plain")

        if url.path in ("/", "/index.html"):
            with open(PAGE, "r", encoding="utf-8") as f:
                page = f.read()
            page = page.replace("{{NAME}}", html.escape(agent.agent_name(_config)))
            return self._send(200, page, "text/html; charset=utf-8")

        if url.path == "/file":                     # 그림 보여주기 + 문서 내려받기(dl=1)
            p = (query.get("p") or [""])[0]
            if not p or not os.path.exists(p) or not allowed(p):
                return self._send(404, b"not found", "text/plain")
            ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
            extra = None
            if (query.get("dl") or [""])[0]:
                # attachment = 브라우저가 열지 않고 저장합니다. 한글 파일명은 filename*
                # (RFC 5987)로 넘겨야 폰에서 안 깨집니다.
                quoted = urllib.parse.quote(os.path.basename(p))
                extra = {"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"}
            with open(p, "rb") as f:
                return self._send(200, f.read(), ctype, extra=extra)

        if url.path == "/history":
            # 지난 대화 보기 — PC에서 나눈 이야기를 폰에서 이어봅니다(읽기만).
            # 대화 전체가 담긴 파일이라 반드시 PIN(401) 뒤에 있어야 합니다(위에서 걸러짐).
            day = (query.get("d") or [""])[0]
            folder = os.path.join(BASE_DIR, "memory", "history")
            if not day:
                days = []
                if os.path.isdir(folder):
                    days = sorted((f[:-3] for f in os.listdir(folder)
                                   if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", f)), reverse=True)
                return self._json({"days": days[:60]})
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):     # 경로 조작 차단 — 날짜 모양만
                return self._json({"error": "잘못된 날짜"}, 400)
            path = os.path.join(folder, day + ".md")
            if not os.path.exists(path):
                return self._json({"messages": []})
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            # 기록 형식은 session.log_turn이 씁니다: **역할** (HH:MM)\n본문\n\n
            messages, current = [], None
            for line in raw.splitlines():
                m = re.fullmatch(r"\*\*(.+?)\*\* \((\d{2}:\d{2})\)", line.strip())
                if m:
                    if current:
                        current["text"] = current["text"].strip()
                        messages.append(current)
                    current = {"who": "me" if m.group(1) == "나" else "lucy",
                               "time": m.group(2), "text": ""}
                elif current is not None:
                    current["text"] += line + "\n"
            if current:
                current["text"] = current["text"].strip()
                messages.append(current)
            return self._json({"messages": messages})

        if url.path == "/poll":                     # 배경으로 넘어간 긴 턴의 결과 찾아가기
            jid = (query.get("id") or [""])[0]
            job = _jobs.get(jid)
            if not job:
                return self._json({"error": "그런 작업이 없습니다 — 서버가 재시작됐을 수"
                                            " 있습니다. 결과는 지난 대화(📜)에 남아 있습니다."}, 404)
            if not job["done"]:
                return self._json({"pending": jid})
            _jobs.pop(jid, None)                    # 한 번 찾아가면 끝 — 쌓아두지 않습니다
            payload = dict(job["payload"])
            payload.update(job["extra"])
            return self._json(payload)

        if url.path == "/say":                      # 폰 스피커로 읽어주기(구글 음성 mp3를 중계)
            text = (query.get("text") or [""])[0]
            if not text:
                return self._send(400, b"no text", "text/plain")
            try:
                import tts_say
                data = b"".join(
                    tts_say.google_mp3(chunk, "ko", 10)
                    for chunk in tts_say.split_chunks(text)[:6]
                )
            except Exception as e:
                return self._send(502, str(e).encode(), "text/plain")
            return self._send(200, data, "audio/mpeg")

        return self._send(404, b"not found", "text/plain")

    def _answer(self, question):
        """한 턴을 돌리고 웹 응답 조각을 만듭니다 — /chat(글)과 /talk(말)이 같이 씁니다."""
        notes = []
        with _lock:                     # 한 번에 한 사람만 — 대화 기록이 엉키지 않게
            # confirm=deny_confirm — 웹에서는 컴퓨터 조작(마우스·키보드)도 거부합니다.
            # 이걸 빼면 respond의 기본값이 input()이라 서버가 통째로 멈추고,
            # 더 나쁘게는 폰에서 원격으로 내 PC의 마우스를 휘두를 수 있게 됩니다
            # (화면 앞에 사람이 없으면 잘못 눌러도 멈출 사람이 없습니다).
            answer, used = agent.respond(_config, _state, question, notify=notes.append,
                                         confirm=deny_confirm)
        return {
            "answer": answer,
            "used": used,
            "notes": notes,
            "images": ["/file?p=" + urllib.parse.quote(p) for p in find_images(answer)],
            # 답에 적힌 문서는 내려받기 링크로 — "그 기획서 폰으로 줘"가 이 한 줄로 됩니다.
            "files": [{"name": os.path.basename(p),
                       "url": "/file?p=" + urllib.parse.quote(p) + "&dl=1"}
                      for p in find_docs(answer)],
        }

    def _answer_or_pending(self, question, extra=None):
        """한 턴을 배경에서 돌리고 잠깐 기다립니다. 제때 끝나면 평소처럼 답을,
        오래 걸리면(영상 인코딩 등) 작업표(pending id)를 줍니다 — 폰이 /poll로 찾아갑니다."""
        wait = float(_config.get("web", {}).get("slow_after_seconds", 20))
        now = time.time()
        for jid in [j for j, job in list(_jobs.items()) if now - job["at"] > 3600]:
            _jobs.pop(jid, None)         # 아무도 안 찾아간 지 1시간 — 버립니다
        job = {"done": False, "payload": None, "extra": extra or {}, "at": now}
        threading.Thread(target=_run_job, args=(job, lambda: self._answer(question)),
                         daemon=True).start()
        deadline = time.time() + wait
        while not job["done"] and time.time() < deadline:
            time.sleep(0.2)
        if job["done"]:
            payload = dict(job["payload"])
            payload.update(job["extra"])
            return payload
        jid = secrets.token_hex(8)
        _jobs[jid] = job
        resp = {"pending": jid,
                "answer": "시간이 걸리는 일이라 계속하고 있어요 — 끝나면 여기에 답을 달게요."}
        resp.update(job["extra"])
        return resp

    def _save_body(self, path, length, chunk=256 * 1024):
        """본문을 조각 단위로 디스크에 바로 씁니다 — 폰 영상(수백 MB~GB)을 통째로
        램에 올리면 그 크기만큼 메모리를 먹습니다(실제 구멍이었음). 쓴 바이트 수를 돌려줍니다."""
        written = 0
        with open(path, "wb") as f:
            while written < length:
                data = self.rfile.read(min(chunk, length - written))
                if not data:
                    break
                f.write(data)
                written += len(data)
        return written

    # 경로별 본문 상한 — 글 대화가 1MB일 리 없고, 녹음은 Groq 상한(24MB)보다 조금 크게,
    # 영상 업로드는 편집용이라 넉넉하되 무한은 아니게.
    _BODY_LIMITS = {"/upload": 2 * 1024 ** 3, "/talk": 40 * 1024 ** 2}

    # ── POST ──
    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._json({"error": "잘못된 요청"}, 400)
        limit = self._BODY_LIMITS.get(url.path, 1024 ** 2)
        if length > limit:
            return self._json({"error": f"파일이 너무 큽니다(상한 {limit // 1024 ** 2}MB)."}, 413)

        # 큰 본문(/upload·/talk)은 램에 안 올리고 각 처리부에서 디스크로 흘려 받습니다.
        raw = b"" if url.path in self._BODY_LIMITS else self.rfile.read(length)

        if url.path == "/pin":              # 이 문만 PIN 없이 두드릴 수 있습니다
            return self._handle_pin(raw)
        if not self._authed():
            return self._json({"error": "PIN이 필요합니다. 화면을 새로고침하세요."}, 401)

        if url.path == "/chat":
            try:
                text = (json.loads(raw or b"{}").get("text") or "").strip()
            except ValueError:
                return self._json({"error": "잘못된 요청"}, 400)
            if not text:
                return self._json({"error": "빈 질문"}, 400)
            # 오류(이미지 못 읽음·전 두뇌 실패)도 _run_job이 답의 형태로 담아 옵니다.
            return self._json(self._answer_or_pending(text))

        if url.path == "/talk":
            # 폰 마이크 → 받아쓰기 → 같은 respond() 한 벌 — '밖에서 루시랑 통화'의 서버 절반.
            # (마이크 자체는 브라우저가 https/localhost에서만 열어줍니다 — index.html의 안내 참고)
            if length < 1000:
                return self._json({"error": "녹음이 너무 짧습니다. 다시 말해 주세요."}, 400)
            name = urllib.parse.unquote(self.headers.get("X-Filename", "talk.webm"))
            ext = os.path.splitext(name)[1].lower() or ".webm"

            conf = _config.get("voice", {})
            try:
                with open(os.path.join(BASE_DIR, conf.get("key_file") or "keys/groq.txt"),
                          "r", encoding="utf-8-sig") as f:
                    key = f.read().strip()
            except OSError:
                key = ""
            if not key:
                return self._json({"error": "받아쓰기 키(keys/groq.txt)가 없어 음성 대화를 못 합니다."}, 500)

            os.makedirs(UPLOADS, exist_ok=True)
            clip = os.path.join(UPLOADS, f"talk_{int(time.time() * 1000)}{ext}")
            self._save_body(clip, length)
            try:
                import voice
                heard = voice.transcribe(clip, key,
                                         model=conf.get("model", "whisper-large-v3"),
                                         language=conf.get("language", "ko")).strip()
            except Exception as e:
                return self._json({"error": f"받아쓰기 실패: {type(e).__name__}: {e}"}, 502)
            finally:
                try:
                    os.remove(clip)     # 말소리 조각은 안 쌓아둡니다(대화는 history에 남습니다)
                except OSError:
                    pass
            if not heard:
                return self._json({"error": "말소리를 알아듣지 못했습니다. 다시 말해 주세요."}, 400)

            # heard는 extra로 실어 pending 응답에도 담습니다 — 폰이 기다리는 동안에도
            # '내가 이렇게 말한 걸로 들렸구나'를 바로 보여줄 수 있게.
            return self._json(self._answer_or_pending(heard, extra={"heard": heard}))

        if url.path == "/upload":
            # 폰 사진 → PC에 저장해야 루시가 볼 수 있습니다(루시는 PC 파일만 봅니다).
            ctype = self.headers.get("Content-Type", "")
            name = urllib.parse.unquote(self.headers.get("X-Filename", "photo.jpg"))
            name = re.sub(r"[^\w.\-가-힣]", "_", os.path.basename(name)) or "photo.jpg"
            os.makedirs(UPLOADS, exist_ok=True)
            path = os.path.join(UPLOADS, name)
            stem, ext = os.path.splitext(path)
            n = 1
            while os.path.exists(path):     # 같은 이름을 덮어쓰지 않습니다
                path = f"{stem}_{n}{ext}"
                n += 1
            self._save_body(path, length)   # 조각 단위 — 큰 영상도 램을 안 먹습니다
            return self._json({"path": path, "url": "/file?p=" + urllib.parse.quote(path)})

        return self._json({"error": "없는 주소"}, 404)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    global _config, _state, PIN
    os.makedirs(DESKTOP, exist_ok=True)
    os.makedirs(UPLOADS, exist_ok=True)
    PIN = load_pin()
    _tokens[:] = _load_tokens()     # 껐다 켜도 이미 통과한 폰은 다시 묻지 않습니다
    _config = agent.load_config()
    # 웹에서는 소리가 PC 스피커에서 나면 폰 사용자는 못 듣습니다.
    # 읽어주기는 브라우저가 /say로 직접 가져가 재생합니다.
    _config.setdefault("tts", {})["enabled"] = False
    _state = agent.new_state(_config)

    # 도구에 설정을 넘깁니다. 이걸 빠뜨리면 도구들이 기본값으로 돌아 — 그림을 바탕화면이 아닌
    # 엉뚱한 폴더에 저장하려 하고, 허용 폴더·검색 백엔드도 비어버립니다(실제로 겪음).
    tools.init(_config)
    tools.CONFIRM = deny_confirm        # 웹에서는 파일 쓰기·코드 실행을 실행하지 않습니다

    # 문서 검색(search_files) 범위를 내려받기 허용 목록에 더합니다 — 루시가 찾아준
    # 파일을 폰으로 받는 길입니다. 여기 없는 폴더는 여전히 404입니다.
    for root in _config.get("filesearch", {}).get("roots", []):
        if os.path.isdir(root) and root not in ALLOWED:
            ALLOWED.append(root)

    name = agent.agent_name(_config)
    ip = lan_ip()
    print("=" * 56)
    print(f"  {name} 웹 화면이 열렸습니다.")
    print(f"    이 컴퓨터 : http://localhost:{PORT}")
    print(f"    폰·태블릿 : http://{ip}:{PORT}     (같은 와이파이)")
    print()
    print(f"  ※ 첫 접속에는 PIN이 필요합니다 →  {PIN}")
    print("     (바꾸려면 keys/web_pin.txt를 고치고 서버를 다시 켜세요)")
    print("  ※ PIN이 있어도 카페·공용 와이파이에서는 켜지 마세요.")
    print("  ※ 파일 쓰기·코드 실행·컴퓨터 조작은 웹에서 거부됩니다(터미널에서만).")
    print("  끄려면 Ctrl+C")
    print("=" * 56)

    Server(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
