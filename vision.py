# -*- coding: utf-8 -*-
"""
비전 — 루시에게 눈을 달아줍니다.

지금까지 루시는 그림을 그릴 줄만 알고 볼 줄은 몰랐습니다.
유니티 에러 화면, UI 스크린샷, 사진을 그대로 보여주고 물어볼 수 있게 합니다.

방식: OpenAI 호환 규격의 image_url에 data URI(base64)를 실어 보냅니다.
      파일을 어디에 올리지 않으므로 키 하나면 되고, 로컬 GPU도 쓰지 않습니다.

⚠️ 모델마다 눈이 있는 것과 없는 것이 있습니다. 없는 모델에 이미지를 보내면 400으로 거절당하거나
   (더 나쁘게는) 이미지를 조용히 무시하고 지어냅니다. 그래서 config의 "vision": true 인 모델에만 보냅니다.

⚠️ 이미지가 실린 요청에 도구 명세까지 함께 실으면 거절하는 모델이 있습니다.
   보는 것과 도구질을 한 번에 시키지 않고, 우선 보고 답하게 합니다.
   (그 답이 대화에 남으므로, 이어지는 질문에서는 평소대로 도구를 씁니다)
"""
import base64
import mimetypes
import os
import re

EXTS = ("png", "jpg", "jpeg", "webp", "gif", "bmp")

# 따옴표로 감싼 경로, C:\... 형태의 절대경로, 또는 그냥 파일명(현재 폴더·바탕화면에서 찾습니다).
_PATH = re.compile(
    r"""["']([^"'\n]+?\.(?:%s))["']"""            # "…\shot.png"
    r"""|([A-Za-z]:[\\/][^\s"'<>|?*\n]+?\.(?:%s))"""   # C:\Users\...\shot.png
    r"""|(\S+\.(?:%s))\b"""                        # shot.png
    % ("|".join(EXTS), "|".join(EXTS), "|".join(EXTS)),
    re.I,
)

# 파일명만 적었을 때 뒤져볼 곳들.
LOOKUP_DIRS = [
    os.path.join(os.path.expanduser("~"), "Desktop"),
    os.path.join(os.path.expanduser("~"), "Pictures"),
    os.path.expanduser("~"),
]

MAX_BYTES = 12 * 1024 * 1024      # base64로 부풀면 약 1.33배. 이보다 크면 대부분의 무료 모델이 거절합니다.


def _resolve(raw):
    """적어준 경로를 실제 파일로. 못 찾으면 None."""
    raw = raw.strip().strip("\"'")
    if os.path.isfile(raw):
        return os.path.abspath(raw)
    if not os.path.isabs(raw):
        for folder in LOOKUP_DIRS:
            candidate = os.path.join(folder, raw)
            if os.path.isfile(candidate):
                return candidate
    return None


def find_images(text):
    """
    문장에서 이미지 파일 경로를 찾아냅니다. (실제로 존재하는 파일만)
    돌려주는 값: (경로를 걷어낸 문장, [경로, ...])

    존재하지 않는 파일명은 그냥 대화의 일부일 수 있으므로(예: "food.onnx 어디 있지?") 무시합니다.
    """
    paths, spans = [], []
    for m in _PATH.finditer(text or ""):
        raw = next(g for g in m.groups() if g)
        found = _resolve(raw)
        if found and found not in paths:
            paths.append(found)
            spans.append(m.span())

    if not paths:
        return text, []

    cleaned = text
    for start, end in reversed(spans):
        cleaned = cleaned[:start] + cleaned[end:]
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, paths


import io


def encode(path):
    """이미지 파일 → data URI. 크거나 고해상도인 경우 리사이즈/JPEG 압축하여 비전 토큰 한도 초과(429) 방지."""
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        raise ValueError(
            f"이미지가 너무 큽니다({size / 1048576:.1f}MB). {MAX_BYTES // 1048576}MB 이하로 줄여주세요."
        )

    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
            max_dim = 1280
            im_format = (im.format or "").upper()
            if w > max_dim or h > max_dim or size > 400 * 1024 or im_format in ("PNG", "BMP", "TIFF"):
                if w > max_dim or h > max_dim:
                    im.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                im.save(buf, format="JPEG", quality=85, optimize=True)
                data_bytes = buf.getvalue()
                data = base64.b64encode(data_bytes).decode("ascii")
                return f"data:image/jpeg;base64,{data}"
    except Exception:
        pass

    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{data}"


def user_message(text, paths):
    """이미지가 실린 사용자 메시지(OpenAI 호환 멀티모달 형식)를 만듭니다."""
    content = [{"type": "text", "text": text or "이 이미지를 설명해줘."}]
    for path in paths:
        content.append({"type": "image_url", "image_url": {"url": encode(path)}})
    return {"role": "user", "content": content}


def capable(config):
    """눈이 달린 두뇌만 추립니다. config에 "vision": true 로 표시된 것들.
    ⭐신뢰도 시험(eyecheck)을 본 적이 있으면 **믿는 눈부터** 오도록 정렬하되,
    서로 다른 키/제공자(Gemini, NVIDIA 등)가 교대로 교차하여 한쪽 한도(429) 시 다른 제공자로 즉시 폴백되도록 정렬."""
    eyes = [m for m in config["models"] if m.get("vision")]
    try:
        import eyecheck
        grade = eyecheck.load()
    except Exception:
        grade = {}

    order_grade = {"trusted": 0, "unknown": 1, "caution": 2, "demoted": 3}
    eyes_sorted = sorted(eyes, key=lambda m: order_grade.get(grade.get(m["label"], "unknown"), 1))

    # provider key 별 그룹화 후 인터리빙 (Gemini -> NVIDIA -> Gemini -> NVIDIA)
    grouped = {}
    for m in eyes_sorted:
        key = m.get("key_file", "default")
        grouped.setdefault(key, []).append(m)

    interleaved = []
    keys = list(grouped.keys())
    max_len = max(len(v) for v in grouped.values()) if grouped else 0
    for i in range(max_len):
        for k in keys:
            if i < len(grouped[k]):
                interleaved.append(grouped[k][i])
    return interleaved or eyes_sorted


# ── 기계 판정 — 눈에게 물어볼 필요가 없는 것들 ──────────────────
# ⭐왜 있나: 눈 두뇌는 확률로 답합니다. 온통 마젠타인 그림을 '정상'이라 답한 눈이 실제로
#   있었습니다(세션64 nemotron 실측). 그런데 '검은 화면'·'단색'·'마젠타 범벅'은 픽셀만 세면
#   **틀릴 수가 없습니다.** 그러니 이런 것은 눈에게 묻지 않고 여기서 끝냅니다 —
#   등급을 올리는 게 아니라 사고가 날 경로 자체를 없애는 쪽입니다.
# ⚠️여기서 판정하는 것은 '확실한 것'만입니다. 애매하면 반드시 (None, "")을 돌려주어
#   눈에게 넘깁니다 — 기계가 어설프게 단정하면 멀쩡한 결과물을 '문제'로 막습니다.

MAGENTA_EXACT = 0.05      # 정확히 (255,0,255)가 이만큼 = 셰이더/재질 실종. 디자인된 분홍은
                          # 이 값에 정확히 걸리는 일이 거의 없습니다(그래서 '느슨한 분홍'과 구분).
MAGENTA_LOOSE = 0.005     # 참고 메모용(판정 아님) — 분홍 소품일 수 있어 눈에게 넘깁니다.
FLAT_SOLID = 0.995        # 한 색이 이만큼 = 아무것도 안 그려짐.
DARK_MEAN = 6             # 평균 밝기가 이 아래 = 어두움. ⚠️이것만으로 판정하면 안 됩니다.
DARK_STD = 1.5            # ⭐'어둡다'와 '검은 화면'은 다릅니다. 의도적으로 어두운 게임 씬
                          #   (onlyuprat 배관 스테이지)이 mean=4.5로 DARK_MEAN에 걸렸지만
                          #   파이프·발판·아이템이 멀쩡히 렌더된 정상 화면이었습니다(실측 오탐).
                          #   진짜 렌더 실패는 **밋밋합니다**: 실측 std=0.00 vs 정상 어두운 씬
                          #   std=5.62 — 그래서 어둡고 **동시에** 밋밋할 때만 판정합니다.


def pixel_stats(png):
    """그림 한 장의 픽셀 통계. PIL이 없거나 실패하면 None — 판정을 지어내지 않습니다.
    돌려주기: {"magenta": 느슨한 분홍 비율, "exact": 정확한 마젠타 비율,
              "flat": 최빈색 비율, "mean": 평균 밝기, "std": 밝기 표준편차(=내용이 있나)}"""
    try:
        import statistics
        from PIL import Image
        from collections import Counter
        im = Image.open(png).convert("RGB")
        im = im.resize((180, 320)) if im.width < im.height else im.resize((320, 180))
        px = list(im.getdata())
        n = len(px)
        lum = [(r + g + b) / 3.0 for r, g, b in px]
        return {
            "magenta": sum(1 for r, g, b in px if r > 190 and b > 190 and g < 90) / n,
            "exact": sum(1 for p in px if p == (255, 0, 255)) / n,
            "flat": Counter(px).most_common(1)[0][1] / n,
            "mean": sum(lum) / n,
            "std": statistics.pstdev(lum),
        }
    except Exception:
        return None


def machine_verdict(png, context="blender"):
    """눈 없이 확답할 수 있는가. (판정, 설명) — 확답 못 하면 (None, "").

    context="blender": 조형 결과 렌더. 단색·검정이면 렌더가 실패한 것이라 '문제'입니다.
    context="unity"  : 게임 씬 샷. 단색은 **정상일 수 있습니다**(UI를 런타임에 만드는 씬) —
                       기존 동작대로 '문제'가 아니라 '알림'으로만 두고 눈도 건너뜁니다.
    """
    s = pixel_stats(png)
    if not s:
        return None, ""
    if s["exact"] >= MAGENTA_EXACT:
        return "문제", (f"분홍(마젠타) 픽셀 {s['exact'] * 100:.0f}% — 재질/셰이더 실종입니다"
                       " (기계 판정 · 눈에게 묻지 않음)")
    if s["mean"] < DARK_MEAN and s["std"] < DARK_STD:
        return "문제", "화면이 검고 아무것도 담기지 않았습니다 — 카메라·조명·렌더 실패 (기계 판정)"
    if s["flat"] >= FLAT_SOLID:
        if context == "unity":
            return None, ""          # 판정은 부르는 쪽에서(런타임 UI 씬이면 정상)
        return "문제", "화면이 한 가지 색뿐입니다 — 렌더에 아무것도 담기지 않았습니다 (기계 판정)"
    return None, ""


def strip_history_images(messages):
    """
    지난 턴의 이미지를 자리표시자로 바꿉니다. (바꾼 개수)

    이걸 안 하면 대화에 한 번 실린 base64 수 MB가 그 뒤 **모든** 요청에 계속 따라붙습니다.
    무료 티어는 분당 토큰 제한이 있어서(Groq는 413으로 거절) 서너 턴 만에 대화가 마비됩니다.
    모델이 그림을 보고 한 설명은 대화에 남으므로, 이어지는 질문은 그 설명을 근거로 답할 수 있습니다.
    """
    changed = 0
    for m in messages:
        content = m.get("content")
        if not isinstance(content, list):
            continue
        if not any(isinstance(p, dict) and p.get("type") == "image_url" for p in content):
            continue
        texts = [p.get("text", "") for p in content
                 if isinstance(p, dict) and p.get("type") == "text"]
        m["content"] = " ".join(t for t in texts if t) + " [보여줬던 이미지 — 위 설명 참고]"
        changed += 1
    return changed


def describe(paths):
    """대화 기록·화면에 남길 사람이 읽을 형태(base64 덩어리를 기록에 남길 수는 없으니)."""
    return " ".join(f"[이미지: {os.path.basename(p)}]" for p in paths)


# 경로를 다시 적지 않고 방금 그 그림을 가리키는 말들 — "거기 왼쪽 위 버튼은 뭐야?"
AGAIN = re.compile(r"(이 ?(그림|사진|이미지|화면|스샷|스크린샷)|저 ?(그림|사진|이미지)|거기|여기|아까 그)")


def refers_back(text):
    """새 경로 없이 직전 이미지를 가리키는 질문인가."""
    return bool(AGAIN.search(text or ""))


# 그림을 '보는' 것이 아니라 '고치는' 요청 — 이때는 보는 턴으로 만들면 안 됩니다.
# 보는 턴은 도구를 끄기 때문에(agent.py: use_tools=not images), 그러면 루시가 그림을
# 감상만 하고 restyle을 못 부릅니다(실제로 겪음).
# ⭐여기 넣는 것은 '도구가 이미지 파일을 직접 재료로 먹는' 편집(restyle 등)뿐입니다 —
#   그런 도구는 경로만 있으면 되고 눈으로 볼 필요가 없어 도구를 켜는 게 맞습니다.
#   ⚠️'사진 보고 3D로 만들어줘'는 여기 넣지 마세요: build는 사진을 인자로 못 먹으므로
#   루시가 **눈으로 형태를 읽어** 치수로 옮겨야 합니다(→ 보는 턴 + wants_make 힌트, 세션68).
EDIT = re.compile(r"(화풍|스타일|덧칠|바꿔|바꾸|변환|restyle|다시 그려|그려줘)")


def wants_edit(text):
    """이미지 경로가 있어도 '보기'가 아니라 '편집'(도구가 그림 파일을 직접 먹는)을 원하는가."""
    return bool(EDIT.search(text or ""))


# 그림을 '보고' 3D 모델·조형을 만들어 달라는 요청 — 이건 wants_edit과 반대로 **눈이 필요**합니다.
# build·sculpt_displace는 사진을 인자로 받지 못하므로, 루시가 참조 그림을 직접 보고 형태·비율을
# 읽어 치수로 옮겨야 합니다. 그래서 '보는 턴'(도구 꺼짐)으로 두되, 그 턴에 "기능 없다"고 하지 않고
# 본 것을 설명하며 만들기를 제안하도록 agent.py가 힌트를 심습니다.
MAKE = re.compile(r"(만들어|만들라|만들게|만들어줘|제작|모델링|모델\s*링|조립|블렌더|blender|3\s*d로|3\s*d\s*모델|입체로)",
                  re.IGNORECASE)


def wants_make(text):
    """그림을 보고 3D 모델·조형을 만들어 달라는(눈이 필요한) 요청인가."""
    return bool(MAKE.search(text or ""))
