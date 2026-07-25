# -*- coding: utf-8 -*-
"""
로컬 신경망 목소리 서버 (MeloTTS) — 루시와 **떨어져 있는 별도 서비스**입니다.

    D:\\lucy-tts\\venv\\Scripts\\python.exe  이 파일  →  http://127.0.0.1:8767

왜 떨어뜨렸나: MeloTTS는 torch를 씁니다(수백 MB~GB). 루시 본체는 "pip 없이 표준
라이브러리만"이라는 원칙 위에 서 있어서, 그걸 본체에 섞으면 다른 PC로 폴더만 복사해
쓰던 이식성이 무너집니다. SD WebUI(그림)와 똑같이 **밖에 세우고 API로 부릅니다.**
꺼져 있으면 루시는 조용히 구글 → 윈도우 목소리로 내려갑니다.

이 파일만 이 venv에서 돕니다. 루시(파이썬 3.12)는 이 파일을 import하지 않습니다.
"""
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8767
LANG = "KR"

_ready = False      # 모델+예열이 끝나면 True — 그 전의 /tts는 503으로 즉시 거절합니다


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/health"):
            body = b'{"ok":true}' if _ready else b'{"ok":true,"loading":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        if not self.path.startswith("/tts"):
            return self.send_error(404)
        if not _ready:
            # 아직 모델을 올리는 중 — 기다리게 하면 루시의 첫 마디가 몇십 초 멈춥니다.
            # 바로 거절해야 루시가 지체 없이 다음 목소리(구글)로 폴백합니다.
            return self.send_error(503, "model loading")
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            text = (req.get("text") or "").strip()
            speed = float(req.get("speed") or 1.0)
        except (ValueError, TypeError):
            return self.send_error(400)
        if not text:
            return self.send_error(400)

        try:
            data = synth(text, speed)
        except Exception as e:                            # 합성 실패는 루시가 폴백할 수 있게 알립니다
            msg = f"{type(e).__name__}: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return

        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


# ─────────────── 포트는 모델보다 **먼저** 잡습니다 ───────────────
#
# 예전엔 모델 로딩(수십 초~수 분)이 끝난 뒤에야 포트를 잡았습니다. 그 사이엔 포트가
# 비어 보여서, start.bat 동반기동과 자동시작 발사대가 겹치면 **둘 다** 살아남아 모델을
# 두 번 올렸습니다 — CPU를 나눠 먹어 로딩이 배로 늘어지고, 그만큼 구글 목소리로 말하는
# 시간이 길어졌습니다(세션55 실측). 뜨자마자 포트부터 잡으면 중복 기동은 이 줄에서 즉시
# 죽고(start.bat의 "중복은 스스로 꺼진다" 가정이 참이 됨), 로딩 중 온 요청은 503으로
# 바로 거절되어 루시가 기다리지 않고 폴백합니다. 로딩이 실패하면 메인 흐름이 죽고
# 서버 스레드는 데몬이라 함께 내려갑니다 — 503만 반복하는 좀비로 남지 않습니다.
_server = HTTPServer(("127.0.0.1", PORT), Handler)
_serving = threading.Thread(target=_server.serve_forever, daemon=True)
_serving.start()
print(f"로컬 목소리 서버: http://127.0.0.1:{PORT} (모델이 올라올 때까지는 503으로 거절합니다)")


# ─────────────── 한국어 발음 변환기의 형태소 분석기를 갈아끼웁니다 ───────────────
#
# MeloTTS는 한국어를 g2pkk로 발음기호화하고, g2pkk는 윈도우에서 `eunjeon`을 부릅니다.
# 그런데 eunjeon은 파이썬 3.10용 휠이 없어 빌드가 실패합니다(MeloTTS의 고질적인 윈도우 벽).
#
# 다행히 형태소 분석기는 g2pkk의 annotate() 한 곳에서 `.pos()`로만 쓰이고,
# 필요한 것은 (표면형, 품사) 쌍뿐입니다. 그래서 윈도우 휠이 멀쩡한 kiwipiepy로 대신합니다.
#
# ⚠️핵심: Kiwi는 '갔'을 가/VV + 었/EP로 쪼개서 돌려주므로 그대로 쓰면 원문과 이어붙지 않고,
#   그러면 annotate()가 다듬기를 통째로 건너뜁니다. **원문 위치(start·len)가 같은 토큰을 묶어**
#   '갔 → VV+EP'로 되돌리면 mecab-ko가 내놓던 모양과 같아집니다(annotate는 tag.split("+")[-1]).
from kiwipiepy import Kiwi                                # noqa: E402
import g2pkk.g2pkk as _g2pkk                              # noqa: E402


class KiwiAsMecab:
    def __init__(self):
        self.kiwi = Kiwi()

    def pos(self, text):
        merged = []
        for t in self.kiwi.tokenize(text):
            span = (t.start, t.len)
            surface = text[t.start:t.start + t.len]
            if merged and merged[-1][2] == span:          # 같은 글자에서 나온 형태소끼리 묶습니다
                merged[-1][1] += "+" + t.tag
            else:
                merged.append([surface, t.tag, span])
        return [(surface, tag) for surface, tag, _ in merged]


_g2pkk.G2p.check_mecab = lambda self: None
_g2pkk.G2p.get_mecab = lambda self: KiwiAsMecab()

import os                                                 # noqa: E402
import torch                                              # noqa: E402

# torch는 기본으로 코어 절반만 씁니다. 전부 주면 합성이 4배 빨라집니다(8.3초 → 2.0초, 실측).
torch.set_num_threads(os.cpu_count() or 4)

print("모델을 올리는 중입니다... (처음 한 번은 내려받느라 오래 걸립니다)")
from melo.api import TTS                                  # noqa: E402

_model = TTS(language=LANG, device="cpu")                 # GTX 1650은 4GB뿐 — CPU가 안전합니다
_speaker = list(_model.hps.data.spk2id.values())[0]
print(f"준비됐습니다. 화자 id={_speaker}")


def synth(text, speed=1.0):
    buf = io.BytesIO()
    _model.tts_to_file(text, _speaker, buf, speed=speed, format="wav", quiet=True)
    return buf.getvalue()


# 예열 — 첫 합성은 내부 준비(사전 로드·그래프 첫 실행) 때문에 18.9초가 걸립니다(실측).
# 그 18.9초를 사용자의 첫 마디가 아니라 서버 기동 때 미리 치릅니다. 실패해도 서버는 켭니다
# (예열은 빠르게 하려는 것이지, 못 하면 안 켜지는 조건이 아닙니다).
# ⚠️여기 print에 em-dash(—) 같은 cp949 밖 글자를 쓰면 콘솔 인코딩 오류로 서버가
#   기동 중에 죽습니다(실제로 겪음). 순한글·아스키만 쓸 것.
try:
    import time as _time
    _t0 = _time.time()
    synth("안녕하세요")
    print(f"예열 완료 ({_time.time() - _t0:.1f}초). 첫 마디부터 빠르게 말합니다.")
except Exception as _e:
    print(f"예열 실패({type(_e).__name__}). 첫 합성만 느릴 뿐 기능은 정상입니다.")

_ready = True       # 이제부터 /tts가 진짜 목소리를 냅니다
print("모델 준비 끝. 지금부터 로컬 목소리로 말합니다. (끄려면 프로세스 종료)")
_serving.join()     # 서버는 위에서 이미 돌고 있습니다 — 메인은 여기 머물며 프로세스를 지킵니다
