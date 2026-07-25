"""
눈(비전) 신뢰도 시험 — 정답을 아는 그림으로 눈 달린 두뇌들을 주기적으로 검증합니다.

왜 필요한가:
  세션63에 llama-3.2-11b-vision이 배경색·배치를 **틀리게** 답하는 것을 실측했습니다(그래서
  등록 금지). 이미 등록된 눈들도 언제든 그럴 수 있는데, 기존 벤치의 눈시험은 "네 자리 숫자를
  읽나"만 봅니다 — 그건 **눈이 달렸나**를 보는 시험이지 **판단이 맞나**를 보는 시험이 아닙니다.
  루시의 눈은 지금 👁 자가검수(수술 미리보기·유니티 샷)에서 '정상/문제'를 판정하는 데 쓰입니다.

⭐위험한 방향은 한쪽뿐입니다:
  · **문제인데 '정상'이라고 답하는 것(놓침)** = 치명적. 아무도 모르게 불량이 통과합니다.
  · 정상인데 '문제'라고 답하는 것(오탐) = 가볍습니다. 사람이 미리보기를 보고 바로 알아챕니다.
  그래서 채점은 대칭이 아닙니다 — 놓침에 2배 벌점을 줍니다.

결과는 memory/eye_trust.json에 남고, vision.capable()이 그 순서를 반영합니다(믿는 눈부터).
⚠️강등해도 명단에서 **빼지는 않습니다** — 눈이 하나뿐일 수 있고, 틀리는 눈이라도 없는 것보단
  낫습니다(자가검수는 보조 신호이고 최종 판단은 사람이 그림을 봅니다).
"""
import datetime
import io
import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRUST_FILE = os.path.join(BASE_DIR, "memory", "eye_trust.json")

# 실제 👁 자가검수와 **같은 어법**으로 묻습니다 — 시험만 잘 보는 눈을 뽑지 않기 위해서입니다.
# ⭐'화면이 비었나·온통 한 색인가'는 **더 이상 눈에게 묻지 않습니다** — vision.machine_verdict가
#   픽셀로 확답합니다(1순위). 시험도 실제로 눈에게 맡기는 것만 물어야 공정합니다.
CHECKPOINT = ("물체가 바닥에 제대로 놓였는지(공중에 뜨거나 바닥을 뚫고 잠기지 않았는지), "
              "분홍(마젠타) 덩어리처럼 재질이 빠진 곳이 없는지.")
INTRO = "3D 작업 결과를 렌더한 점검용 그림이다."
MIN_GRADED = 4          # 이만큼은 실제로 채점돼야 '믿음'을 줍니다(못 잰 건 잘 본 게 아님)

# (이름, 그리는 함수 이름, 기대 판정) — 기대 판정이 정답입니다.
# 정상 그림도 섞습니다. 문제 그림만 내면 "무조건 문제"라고 답하는 눈이 만점을 받습니다.
FIXTURES = [
    ("바닥에 놓인 상자", "ground_box", "정상"),
    ("나란히 놓인 두 상자", "two_boxes", "정상"),
    # ⭐어둡지만 정상인 화면 — 실측에서 나온 문항입니다. onlyuprat 배관 스테이지가 평균밝기
    #   4.5로 '검은 화면'처럼 보였지만 멀쩡히 렌더된 정상 화면이었습니다. 눈이 '어둡다'를
    #   '고장'이라 외치면 사람이 헛걸음하므로, 오탐 쪽도 재야 합니다.
    ("어둡지만 물체가 보이는 화면", "dark_scene", "정상"),
    ("공중에 뜬 상자", "floating_box", "문제"),
    # ⛔'바닥을 뚫고 잠긴 상자'(sunken_box)는 **시험에서 뺐습니다** — 함수는 아래 남겨둡니다.
    #   내력: ①'서로 겹친 두 상자'를 뺐던 이유와 같은 함정에 두 번 걸렸습니다. 반투명 바닥에
    #   비친 아래쪽이 **광택 바닥의 반사**로 읽혀(3D에서 반사는 정상) 눈들이 '정상'이라 답했고,
    #   놓침 2배 벌점 탓에 Gemini가 '주의'·nemotron이 '강등'으로 부당하게 깎였습니다.
    #   ②세션65에 바닥 격자선을 상자 위로 지나가게 다시 그려 봤지만(반사에는 격자가 안 덮이므로
    #   뜻이 하나뿐이 되도록) **소용없었습니다**: Groq 2회 연속 '정상', nemotron도 '정상' —
    #   Groq은 "물체는 바닥 그리드에 정확히 위치해 있으며"라고 격자를 보면서도 그렇게 읽었습니다.
    #   ⭐결론: 바닥 관통은 **눈의 일이 아니라 기계의 일**입니다. 모든 눈이 틀리는 문항은
    #   아무것도 재지 못하면서 벌점만 물립니다. 실제로 애니메이션 바닥 관통은 이미 눈이 아니라
    #   프레임별 최저 z 측정으로 잡고 있습니다 — 그쪽이 옳은 방향입니다.
    #   ⚠️새 문항을 넣고 싶으면 **넣기 전에 멀쩡한 눈으로 답을 받아 공정한지 확인할 것.**
    #   이 문항은 그 확인 없이 들어와서 등급표를 두 세대에 걸쳐 망가뜨렸습니다.
    # ⭐기계가 확답 못 하는 구간(마젠타가 화면 일부뿐) — 눈이 실제로 필요한 자리입니다.
    #   온통 마젠타/검정은 machine_verdict가 가로채므로 시험에서 뺐습니다.
    ("일부 재질이 빠진(분홍) 화면", "partial_magenta", "문제"),
]

_W, _H = 640, 480
_BG = (232, 232, 235)
_FLOOR_Y = 360


def _canvas(draw_floor=True):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (_W, _H), _BG)
    d = ImageDraw.Draw(img)
    if draw_floor:
        d.rectangle([0, _FLOOR_Y, _W, _H], fill=(200, 200, 204))
        d.line([0, _FLOOR_Y, _W, _FLOOR_Y], fill=(120, 120, 126), width=3)
    return img, d


def _box(d, cx, top, w, h, color=(90, 130, 200)):
    """앞면 + 윗면 살짝(입체로 보이게) — 평평한 사각형보다 '3D 렌더'처럼 읽힙니다."""
    d.rectangle([cx - w // 2, top, cx + w // 2, top + h], fill=color,
                outline=(40, 60, 100), width=3)
    d.polygon([(cx - w // 2, top), (cx - w // 2 + 26, top - 26),
               (cx + w // 2 + 26, top - 26), (cx + w // 2, top)],
              fill=tuple(min(255, c + 40) for c in color), outline=(40, 60, 100))


def ground_box(path):
    img, d = _canvas()
    _box(d, _W // 2, _FLOOR_Y - 150, 150, 150)          # 바닥선에 정확히 닿게
    img.save(path)


def two_boxes(path):
    img, d = _canvas()
    _box(d, 200, _FLOOR_Y - 130, 130, 130)
    _box(d, 440, _FLOOR_Y - 130, 130, 130, color=(200, 120, 90))
    img.save(path)


def floating_box(path):
    img, d = _canvas()
    _box(d, _W // 2, 60, 150, 150)                      # 바닥에서 한참 위 — 공중부양
    img.save(path)


def _floor_grid(d, over=True):
    """바닥면을 원근 격자로 그립니다. 격자선이 물체 **위로** 지나가면 그 물체는 바닥면
    아래에 있다는 뜻이 됩니다 — 반사(reflection)에는 바닥 격자가 덮이지 않으므로,
    이 한 가지 단서로 '잠김'과 '광택 바닥의 반사'가 갈립니다(세션65 오답 수리)."""
    line = (150, 150, 158)
    for i in range(1, 9):                              # 가로선 — 멀어질수록 촘촘하게
        y = _FLOOR_Y + int((_H - _FLOOR_Y) * (i / 8.0) ** 1.6)
        d.line([0, y, _W, y], fill=line, width=2)
    for i in range(-6, 7):                             # 세로선 — 소실점으로 모이게
        d.line([_W // 2 + i * 46, _FLOOR_Y, _W // 2 + i * 150, _H], fill=line, width=2)


def sunken_box(path):
    """바닥면을 뚫고 절반이 잠긴 상자(원점 어긋남).
    ⭐순서가 핵심입니다: 상자를 그린 뒤 **바닥 격자선을 상자 위에 덮어** 그립니다.
      바닥이 물체를 가린다 = 물체가 바닥면 아래다. 반사로는 설명되지 않는 배치입니다."""
    from PIL import Image, ImageDraw
    img, d = _canvas(draw_floor=False)
    d.rectangle([0, _FLOOR_Y, _W, _H], fill=(200, 200, 204))
    _box(d, _W // 2, _FLOOR_Y - 80, 150, 150)          # 절반이 바닥선 아래로 내려감
    # 잠긴 부분을 바닥색으로 흐리게 덮고(가라앉은 느낌) 그 위에 격자선을 지나가게 합니다.
    sunk = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sunk).rectangle([0, _FLOOR_Y, _W, _H], fill=(200, 200, 204, 150))
    img = Image.alpha_composite(img.convert("RGBA"), sunk).convert("RGB")
    d2 = ImageDraw.Draw(img)
    _floor_grid(d2)                                    # ⭐상자 위로 지나가는 바닥 격자
    d2.line([0, _FLOOR_Y, _W, _FLOOR_Y], fill=(110, 110, 118), width=3)
    img.save(path)


def dark_scene(path):
    """어둡지만 물체가 멀쩡히 보이는 정상 화면 — '어둡다'를 '고장'이라 외치는지 봅니다.
    (실측: onlyuprat 배관 스테이지 평균밝기 4.5, 표준편차 5.6 — 정상 렌더였음)"""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (_W, _H), (7, 8, 11))
    d = ImageDraw.Draw(img)
    d.rectangle([0, _FLOOR_Y, _W, _H], fill=(13, 14, 18))
    for cx, w, h in ((150, 90, 120), (330, 130, 170), (500, 100, 140)):
        d.rectangle([cx - w // 2, _FLOOR_Y - h, cx + w // 2, _FLOOR_Y],
                    fill=(20, 22, 30), outline=(34, 37, 48), width=2)
    d.ellipse([470, 250, 510, 290], fill=(120, 96, 30))      # 작은 발광체 — 내용이 있다는 표시
    img.save(path)


def partial_magenta(path):
    """정상 장면인데 물체 하나만 분홍(재질 실종) — 화면 일부라 기계는 확답하지 않고,
    눈이 실제로 필요한 자리입니다. ⚠️vision.MAGENTA_EXACT(5%)보다 작게 유지할 것."""
    img, d = _canvas()
    _box(d, 200, _FLOOR_Y - 130, 130, 130)
    _box(d, 440, _FLOOR_Y - 110, 110, 110, color=(255, 0, 255))   # ≈3% — 기계 임계값 아래
    img.save(path)


def black(path):
    from PIL import Image
    Image.new("RGB", (_W, _H), (0, 0, 0)).save(path)


def magenta(path):
    from PIL import Image
    Image.new("RGB", (_W, _H), (255, 0, 255)).save(path)


def make_images(folder=None):
    """시험용 그림을 만듭니다(FIXTURES 개수만큼). [(이름, 경로, 기대판정), …]"""
    import tempfile
    folder = folder or os.path.join(tempfile.gettempdir(), "lucy_eye_trust")
    os.makedirs(folder, exist_ok=True)
    out = []
    for name, fn, expect in FIXTURES:
        path = os.path.join(folder, fn + ".png")
        globals()[fn](path)
        out.append((name, path, expect))
    return out


def _verdict(text):
    """모델 답에서 판정만 뽑습니다 — 형식이 제멋대로라 낱말로 봅니다(_eye_look_many와 같은 방침).
    돌려주기: '정상' · '문제' · None(못 읽음)."""
    t = (text or "").strip().replace("\n", " ")
    if not t:
        return None
    head = t[:40]
    if "문제" in head or "이상" in head:
        return "문제"
    if "정상" in head:
        return "정상"
    # 앞머리에 없으면 전체에서 한 번 더(앞에 군더더기를 붙이는 두뇌가 있음)
    if "문제" in t:
        return "문제"
    if "정상" in t:
        return "정상"
    return None


def _ask(agent, config, entry, question, path):
    """한 눈에게 그림 하나를 묻습니다. 돌려주기: (판정, 사유).
    실패·한도는 판정 None — 못 잰 것을 '틀렸다'로 적으면 멀쩡한 눈을 강등시킵니다
    (벤치가 같은 실수를 했던 자리).
    ⭐사유를 함께 남깁니다: 예전엔 모든 실패를 통째로 삼켜 '못 읽음'이 한도인지·거절인지·
      빈 답인지 구분할 수 없었고, 그 바람에 Groq이 왜 5/6을 못 읽었는지 알아내려고
      재현 실험을 따로 해야 했습니다(세션65). 사유를 알아야 다음에 손을 쓸 수 있습니다."""
    import contextlib
    import vision
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            msg = vision.user_message(question, [path])
            answer, _label, _e = agent.call_model(config, [msg], use_tools=False, order=[entry])
    except Exception as e:
        text = f"{e}"
        if "한도" in text or "429" in text or "쉬는 중" in text:
            return None, "한도"
        return None, type(e).__name__
    body = (answer.get("content") or "").strip()
    if not body:
        return None, "빈답"
    got = _verdict(body)
    return got, ("" if got else "형식")


def _wait_for_cooldown(agent, labels, notify, budget):
    """한도로 쉬는 눈들이 풀릴 때까지 기다립니다. (실제로 기다린 초). 못 기다리면 0.
    ⭐왜 기다리나: Groq 무료 눈은 이미지 2장이면 한도에 걸리고 **30분 쿨다운**에 들어가
      남은 문항이 통째로 날아갑니다(세션65 재현). 그래서 여섯 문제 중 둘만 채점되고
      '측정 불가'로 남아, 2개 눈 합의제의 한 자리가 계속 비어 있었습니다.
      정기 시험은 새벽 배경 작업이라 **기다릴 시간은 얼마든지 있습니다.**"""
    import time as _t
    until = max((agent.resting_until(l) for l in labels), default=0)
    if not until:
        return 0
    wait = min(until - _t.time() + 5, budget)
    if wait <= 0:
        return 0
    how_long = f"{wait / 60:.0f}분" if wait >= 60 else f"{wait:.0f}초"
    notify(f"  ⏳ 한도로 쉬는 눈({', '.join(labels)})이 풀리기를 {how_long} 기다립니다"
           " — 못 잰 문항을 남기지 않기 위해서입니다")
    _t.sleep(wait)
    return wait


def run(agent, config, notify=print, pause=2.0, save=True, max_wait=0):
    """눈 달린 두뇌들을 정답 아는 그림으로 시험합니다. (요약문, 결과 dict)

    max_wait: 한도로 못 잰 문항을 위해 쿨다운을 기다려줄 총 예산(초).
              0이면 안 기다립니다 — 대화 중에 부르는 도구가 30분씩 멈추면 안 되니까요.
              새벽 정기 시험(daily)만 넉넉히 줍니다."""
    import vision
    eyes = vision.capable(config)
    if not eyes:
        return "눈 달린 두뇌가 없습니다(config의 vision: true 확인).", {}
    try:
        images = make_images()
    except Exception as e:
        return f"시험용 그림을 만들지 못했습니다: {type(e).__name__}: {e}", {}

    question = (INTRO + " 다음만 판정하세요: " + CHECKPOINT
                + " 첫 단어를 '정상' 또는 '문제:'로 시작해 한두 문장으로만 답하세요.")
    # ⭐한 두뇌에게 여러 장을 연달아 물으면 무료 티어 분당 한도에 걸리고, 429를 맞은 두뇌는
    #   30분 쿨다운에 들어가 **남은 문항이 통째로 날아갑니다**(세션64 Groq 실측 — 그 바람에
    #   쉬운 2문제만 채점되고 '믿음'을 받을 뻔했음). 그래서 문항을 바깥, 두뇌를 안쪽으로 돌려
    #   같은 두뇌를 연타하지 않습니다.
    tally = {e["label"]: {"miss": 0, "false": 0, "graded": 0, "detail": []} for e in eyes}

    def _record(label, name, got, why, expect):
        t = tally[label]
        if got is None:
            t["detail"].append(f"{name}: 못 읽음({why})")
            return
        t["graded"] += 1
        if got == expect:
            t["detail"].append(f"{name}: ✅{got}")
        elif expect == "문제":
            t["miss"] += 1                    # ⭐치명 — 불량을 정상이라고 통과시킴
            t["detail"].append(f"{name}: ❌놓침(문제인데 '정상')")
        else:
            t["false"] += 1                   # 가벼움 — 사람이 보면 바로 앎
            t["detail"].append(f"{name}: ⚠오탐(정상인데 '문제')")

    todo = [(entry, name, path, expect) for name, path, expect in images for entry in eyes]
    budget = max_wait
    while todo:
        deferred = []                          # 한도로 못 물어본 것 — 쿨다운 뒤 다시
        for entry, name, path, expect in todo:
            got, why = _ask(agent, config, entry, question, path)
            time.sleep(pause)
            if got is None and why == "한도" and budget > 0:
                deferred.append((entry, name, path, expect))
                continue
            _record(entry["label"], name, got, why, expect)
        if not deferred:
            break
        slept = _wait_for_cooldown(agent, sorted({e["label"] for e, *_ in deferred}),
                                   notify, budget)
        if slept <= 0:                         # 더는 못 기다림 — 남은 건 정직하게 '못 읽음'
            for entry, name, _p, _x in deferred:
                _record(entry["label"], name, None, "한도", None)
            break
        budget -= slept
        todo = deferred

    result = {}
    for entry in eyes:
        label = entry["label"]
        t = tally[label]
        miss, wrong_alarm, graded, detail = t["miss"], t["false"], t["graded"], t["detail"]
        if not graded:
            result[label] = {"grade": "unknown", "miss": 0, "false": 0, "n": 0,
                             "detail": detail}
            notify(f"  {label}: 측정 불가(한도·거절) — 판정 보류")
            continue
        # 놓침 2배 벌점. 치명 2건 이상이면 강등, 1건이거나 오탐이 많으면 주의.
        # ⚠️표본이 모자라면 '믿음'은 못 줍니다 — 한도로 4문제가 날아가고 쉬운 2문제만 맞힌
        #   두뇌가 만점처럼 보였던 실측(세션64 Groq). 못 잰 것은 잘 본 것이 아닙니다.
        penalty = miss * 2 + wrong_alarm
        if graded < MIN_GRADED:
            grade = "unknown" if miss == 0 else "caution"
        else:
            grade = "trusted" if penalty <= 1 else ("caution" if miss <= 1 and penalty <= 3
                                                    else "demoted")
        result[label] = {"grade": grade, "miss": miss, "false": wrong_alarm,
                         "n": graded, "detail": detail}
        ko = {"trusted": "믿음", "caution": "주의", "demoted": "강등",
              "unknown": "판정 보류(표본 부족)"}[grade]
        notify(f"  {label}: {ko} — {graded}문제 중 놓침 {miss}·오탐 {wrong_alarm}")

    if save:
        try:
            os.makedirs(os.path.dirname(TRUST_FILE), exist_ok=True)
            tmp = TRUST_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"at": datetime.datetime.now().isoformat(timespec="seconds"),
                           "eyes": result}, f, ensure_ascii=False, indent=1)
            os.replace(tmp, TRUST_FILE)
        except OSError:
            pass
    return summary(result), result


def summary(result):
    ko = {"trusted": "믿음", "caution": "주의", "demoted": "강등", "unknown": "측정 불가"}
    lines = [f"[눈 신뢰도 시험] — 정답을 아는 그림 {len(FIXTURES)}장"
             f"(정상 {sum(1 for f in FIXTURES if f[2] == '정상')}·"
             f"문제 {sum(1 for f in FIXTURES if f[2] == '문제')})"]
    for label, r in result.items():
        if r["grade"] == "unknown":
            lines.append(f"  ? {label} — 판정 보류: {r['n']}문제만 채점됨"
                         f"(나머지는 한도·거절 — {MIN_GRADED}문제는 돼야 믿음을 줍니다)")
            for d in r["detail"]:
                lines.append("      " + d)
            continue
        mark = {"trusted": "✅", "caution": "⚠", "demoted": "✗"}[r["grade"]]
        lines.append(f"  {mark} {label} — {ko[r['grade']]}: {r['n']}문제 중 "
                     f"놓침 {r['miss']}(치명)·오탐 {r['false']}")
        for d in r["detail"]:
            lines.append("      " + d)
    bad = [l for l, r in result.items() if r["grade"] == "demoted"]
    if bad:
        lines.append("  ⚠강등된 눈도 명단에서 빼지는 않습니다(눈이 없는 것보단 나음) — "
                     "믿는 눈에게 먼저 묻고, 이 눈의 판정은 참고만 하세요.")
    return "\n".join(lines)


def load():
    """저장된 신뢰도. {label: grade} — 없으면 빈 dict."""
    try:
        with open(TRUST_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return {k: v.get("grade", "unknown") for k, v in (data.get("eyes") or {}).items()}
    except (OSError, ValueError, AttributeError):
        return {}


def status_lines():
    """'/상태'용 한 줄 요약(시험을 본 적 없으면 아무것도 안 보탬)."""
    try:
        with open(TRUST_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    eyes = data.get("eyes") or {}
    if not eyes:
        return []
    ko = {"trusted": "믿음", "caution": "주의", "demoted": "강등", "unknown": "측정불가"}
    when = str(data.get("at", ""))[:10]
    parts = [f"{l}={ko.get(r.get('grade'), '?')}" for l, r in eyes.items()]
    lines = ["", f"[눈 신뢰도] — 마지막 시험 {when}", "  " + " · ".join(parts)]
    risky = [l for l, r in eyes.items() if r.get("miss")]
    if risky:
        lines.append("  ⚠ 문제를 '정상'이라 답한 적 있는 눈: " + ", ".join(risky)
                     + " (자가검수 통과를 그대로 믿지 마세요)")
    return lines
