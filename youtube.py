# -*- coding: utf-8 -*-
"""
유튜브 강의 요약 — 자막을 받아 요약해 지식 창고에 넣습니다.

    /유튜브 <주소>   또는   "이 영상 요약해줘 https://youtu.be/..."

GDC 강연·수업 영상처럼 긴 영상을 루시가 대신 보고(정확히는 '읽고') 노트로 남깁니다.
노트는 knowledge/youtube_*.md 로 들어가 search_knowledge로 검색됩니다.
(sync는 같은 이름만 덮어쓰므로 selfstudy_처럼 youtube_ 노트도 지워지지 않습니다)

자막을 받는 법 (pip 0 · 영상은 내려받지 않음):
  ⚠️시청 페이지 HTML의 captionTracks는 **주소는 주지만 열면 빈 응답**입니다(2026-07 실측
  — 유튜브가 웹 클라이언트에 원본 증명 토큰을 요구). 대신 innertube API(youtubei/v1/player)를
  **ANDROID 클라이언트로** 부르면 영상 정보와 살아 있는 자막 주소를 한 번에 줍니다.
  자막 응답은 json3을 요청해도 XML(timedtext)로 올 수 있어 둘 다 읽습니다.
  정식 자막이 없으면 자동 생성(asr)으로 물러섭니다 — 오타가 있어도 없는 것보다 낫고,
  노트에 '자동 생성'임을 밝힙니다.

긴 자막은 조각으로 나눠 요약(map)하고 마지막에 한 노트로 엮습니다(reduce) —
한 번에 다 실으면 작은 컨텍스트 두뇌(Cerebras 8192)가 통째로 거부합니다.
"""
import datetime
import json
import os
import re
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")

# 유튜브 주소 + '요약해달라'는 낱말이 함께 있을 때만 자연어로 알아듣습니다.
URL_RE = re.compile(r"(?:https?://)?(?:www\.|m\.)?"
                    r"(?:youtube\.com/(?:watch\?[^\s]*v=|shorts/|live/|embed/)|youtu\.be/)"
                    r"[\w\-?=&%.]+")
ASK_RE = re.compile(r"(요약|정리|학습|공부|반입|넣어|노트)")


def wants(text):
    """'이 영상 요약해줘 <주소>' 같은 말이면 주소를, 아니면 None을 돌려줍니다."""
    m = URL_RE.search(text or "")
    if m and ASK_RE.search(text):
        return m.group(0)
    return None


def video_id(url):
    url = (url or "").strip()
    m = re.search(r"(?:v=|youtu\.be/|shorts/|live/|embed/)([\w-]{11})", url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w-]{11}", url):
        return url
    raise RuntimeError(f"유튜브 주소를 알아보지 못했습니다: {url[:80]}")


# ── 자막 받기 ─────────────────────────────────────────────────────
_ANDROID_UA = "com.google.android.youtube/20.10.38 (Linux; U; Android 11) gzip"


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": _ANDROID_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _player_response(vid):
    """innertube(유튜브 내부 API)에 ANDROID 클라이언트로 영상 정보를 묻습니다.

    ⚠️웹(시청 페이지)의 자막 주소는 열면 빈 응답이 옵니다 — ANDROID 클라이언트로
    받은 주소만 살아 있습니다(실측). 클라이언트 버전은 낡으면 거부될 수 있으니
    이 함수가 갑자기 실패하면 버전 숫자부터 올려볼 것."""
    body = json.dumps({
        "context": {"client": {"clientName": "ANDROID",
                               "clientVersion": "20.10.38",
                               "androidSdkVersion": 30}},
        "videoId": vid,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://www.youtube.com/youtubei/v1/player", data=body,
        headers={"Content-Type": "application/json", "User-Agent": _ANDROID_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))

    status = data.get("playabilityStatus", {})
    if status.get("status") not in (None, "OK"):
        why = status.get("reason") or status.get("status")
        raise RuntimeError(f"영상을 열 수 없습니다: {why}")
    return data


def _pick_track(tracks, prefer=("ko", "en")):
    """정식 한국어 > 자동 한국어 > 정식 영어 > 자동 영어 > 아무거나."""
    def rank(t):
        lang = (t.get("languageCode") or "")[:2]
        manual = t.get("kind") != "asr"
        try:
            li = prefer.index(lang)
        except ValueError:
            li = len(prefer)
        return (li, 0 if manual else 1)
    return sorted(tracks, key=rank)[0]


def _lines_from(raw):
    """자막 응답을 [(초, 문장)]으로. json3을 요청해도 XML(timedtext)로 오기도 해 둘 다 읽습니다."""
    raw = (raw or "").strip()
    if not raw:
        raise RuntimeError("자막 응답이 비어 있습니다(유튜브가 이 클라이언트를 거부했을 수 있음)")

    lines = []
    if raw.startswith("<"):
        import xml.etree.ElementTree as ET
        for p in ET.fromstring(raw).iter("p"):
            text = "".join(p.itertext()).replace("\n", " ").strip()
            if text:
                lines.append((int(p.get("t", 0)) / 1000, text))
    else:
        for ev in json.loads(raw).get("events", []):
            segs = ev.get("segs") or []
            text = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
            if text:
                lines.append((ev.get("tStartMs", 0) / 1000, text))
    return lines


def _caption_text(base_url):
    """자막 트랙을 받아 '[mm:ss] 문장들' 덩어리로 엮습니다(약 40초 단위)."""
    lines = _lines_from(_get(base_url + "&fmt=json3"))
    blocks, buf, block_start = [], "", None

    def flush():
        if buf.strip() and block_start is not None:
            stamp = f"[{int(block_start // 60):02d}:{int(block_start % 60):02d}]"
            blocks.append(f"{stamp} {buf.strip()}")

    for t, text in lines:
        if block_start is None:
            block_start = t
        buf += text + " "
        if t - block_start >= 40:
            flush()
            buf, block_start = "", None
    flush()
    return "\n".join(blocks)


def transcript(url_or_id):
    """자막과 영상 정보. {'title','author','minutes','lang','auto','text'}"""
    vid = video_id(url_or_id)
    pr = _player_response(vid)

    details = pr.get("videoDetails", {})
    tracks = (pr.get("captions", {})
                .get("playerCaptionsTracklistRenderer", {})
                .get("captionTracks") or [])
    if not tracks:
        raise RuntimeError("이 영상에는 자막이 없습니다(자동 생성 자막도 없음) — 요약할 원문이 없습니다")

    track = _pick_track(tracks)
    text = _caption_text(track["baseUrl"])
    if len(text.strip()) < 80:
        raise RuntimeError("자막이 사실상 비어 있습니다 — 요약할 내용이 없습니다")

    return {
        "title": details.get("title") or "(제목 없음)",
        "author": details.get("author") or "?",
        "minutes": int(details.get("lengthSeconds") or 0) // 60,
        "lang": track.get("languageCode", "?"),
        "auto": track.get("kind") == "asr",
        "text": text,
    }


# ── 요약 ──────────────────────────────────────────────────────────
CHUNK_PROMPT = """유튜브 영상 "{title}"의 자막 일부다 ({i}/{n} 조각).

이 조각의 내용을 요점으로 정리하라.
- 구체적인 수치·사례·용어·주장을 잃지 마라. 그게 이 노트의 가치다.
- 각 요점 앞의 [mm:ss] 시각 표시를 살려라(나중에 그 대목을 찾아볼 수 있게).
- 광고·인사말·잡담은 버려라.
- 한국어로 써라(전문용어는 원어를 괄호로 병기).

[자막 {i}/{n}]
{part}"""

NOTE_PROMPT = """유튜브 영상 "{title}"의 자막(또는 부분 요약들)이다. 지식 창고에 남길 **학습 노트**로 정리하라.

형식:
## 핵심 요약
(3~5문장 — 이 영상이 무엇을 말하는가)

## 주요 내용
(소제목 몇 개로 나눠 요점 정리. 구체 수치·사례·용어를 보존하고, 가능하면 [mm:ss] 시각을 남겨라)

## 기억할 것
(가장 중요한 주장·수치·조언 3~5개)

규칙: 자막에 있는 것만 쓰고 지어내지 마라. 한국어로 쓰되 전문용어는 원어 병기. 다른 말 없이 노트만 출력하라.

[내용]
{content}"""


def _split(text, size):
    """줄 경계로 나눕니다 — 문장이 조각 사이에서 찢기지 않게."""
    parts, buf = [], ""
    for line in text.splitlines():
        if len(buf) + len(line) > size and buf:
            parts.append(buf)
            buf = ""
        buf += line + "\n"
    if buf.strip():
        parts.append(buf)
    return parts


def summarize(config, call_model, url, notify=print):
    """자막을 받아 요약 노트를 만들어 지식 창고에 넣습니다. (파일 경로, 노트 본문)"""
    cfg = config.get("youtube", {})
    if not cfg.get("enabled", True):
        raise RuntimeError("유튜브 요약이 설정에서 꺼져 있습니다(youtube.enabled)")

    notify("자막을 받는 중...")
    info = transcript(url)
    label = info["lang"] + (" 자동생성" if info["auto"] else "")
    notify(f"자막 {len(info['text']):,}자 ({label}) · {info['minutes']}분 영상 — 요약을 시작합니다")

    def ask(prompt):
        message, _used, _entry = call_model(
            config, [{"role": "user", "content": prompt}], use_tools=False)
        out = (message.get("content") or "").strip()
        if not out:
            raise RuntimeError("요약 모델이 빈 답을 돌려줬습니다")
        return out

    parts = _split(info["text"], cfg.get("chunk_chars", 6000))
    if len(parts) == 1:
        final = ask(NOTE_PROMPT.format(title=info["title"], content=parts[0]))
    else:
        partials = []
        for i, part in enumerate(parts, 1):
            notify(f"  조각 {i}/{len(parts)} 요약 중...")
            partials.append(ask(CHUNK_PROMPT.format(
                title=info["title"], i=i, n=len(parts), part=part)))
        notify("  조각들을 한 노트로 엮는 중...")
        final = ask(NOTE_PROMPT.format(title=info["title"],
                                       content="\n\n".join(partials)[:12000]))

    today = datetime.date.today()
    slug = "".join(c for c in info["title"][:24]
                   if c.isalnum() or c in " _-").strip().replace(" ", "_") or "video"
    path = os.path.join(KNOWLEDGE_DIR,
                        f"youtube_{slug}_{today.strftime('%Y%m%d')}.md")

    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    vid = video_id(url)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# [유튜브 요약] {info['title']}\n\n"
                f"- 원본: https://www.youtube.com/watch?v={vid}\n"
                f"- 채널: {info['author']} · 길이: {info['minutes']}분 · 자막: {label}\n"
                f"- 반입: {today.isoformat()} — 자막 기반 자동 요약(사람이 검증하지 않음)\n\n"
                f"{final}\n")
    notify(f"지식 창고에 넣었습니다: {os.path.basename(path)}")
    return path, final
