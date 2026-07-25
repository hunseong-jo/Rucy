# -*- coding: utf-8 -*-
"""
두뇌 벤치 — 루시가 자기 두뇌들을 직접 시험해서 순위를 다시 매깁니다.

왜 필요한가:
  무료 모델판은 계속 바뀝니다. 어제 빠르던 게 오늘 한도에 걸리고, 새 모델이 생기고,
  잘 쓰던 서비스가 프로젝트를 막아버리기도 합니다(실제로 Gemini가 403으로 막혔습니다).
  그때마다 사람이 손으로 순서를 고치는 대신, 루시가 스스로 재보고 정하게 합니다.

무엇을 재는가:
  '똑똑함'을 추상적으로 재지 않고, 이 비서가 실제로 하는 일을 그대로 시킵니다.
    · 사실 질문에 검색 도구를 써서 정답을 내는가   (도구 호출 + 환각 방지)
    · 도구 두 개를 엮어 쓸 수 있는가              (다단계 실행)
    · 계산을 틀리지 않는가                        (추론)
  채점은 정답 여부(우선) → 속도(동점일 때) 순입니다.

실행:  루시 프롬프트에서 /벤치     (config.json을 백업하고 순위대로 다시 씁니다)
"""
import io
import contextlib
import json
import os
import random
import shutil
import subprocess
import tempfile
import time

import vision

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
EYE_PS1 = os.path.join(BASE_DIR, "eye_test.ps1")

# 답이 객관적으로 채점되는 질문만 씁니다("좋은 답"은 채점할 수 없으니까요).
TASKS = [
    ("사실+검색", "북한산 높이가 얼마야? 숫자로 정확히 답해줘.", ["836"]),
    ("도구 2개", "오늘 날짜를 확인하고, 이 폴더에 파일이 몇 개인지 세어줘: " + BASE_DIR.replace("\\", "/"),
     ["2026"]),
    ("추론", "농부가 닭과 소를 합쳐 20마리 기른다. 다리는 모두 56개다. 소는 몇 마리인가? 숫자만.", ["8"]),
]


# 한도 초과는 '틀린 답'이 아니라 '재보지 못한 것'입니다. 이 둘을 섞으면 순위가 엉망이 됩니다.
# (실제로 겪음: Groq가 분당 한도에 걸리자 남은 과제가 전부 0점 처리돼 꼴찌로 밀렸습니다)
RATE_LIMITED = ("한도", "429", "413", "혼잡")


# ── 눈(비전) 시험 ─────────────────────────────────────────────────
# 세 과제(검색·도구·추론)는 눈을 재지 않습니다. 그런데 어떤 두뇌에게 그림을 보낼지는
# config의 "vision": true 한 줄이 정하고, 그 줄은 **사람이 손으로 적은 것**입니다.
# 모델이 갈리거나 공급자가 눈을 붙이면 그 줄은 조용히 거짓말이 됩니다:
#   · 눈이 없는데 true → 400으로 거절당하거나, 더 나쁘게는 그림을 무시하고 **지어냅니다**
#   · 눈이 생겼는데 없음 → 멀쩡한 두뇌를 그림에서 빼놓습니다
# 그래서 벤치가 순위를 다시 쓸 때 이 줄도 **실측해서** 다시 씁니다(추측 금지).
EYE_QUESTION = "이 그림에 적힌 네 자리 숫자를 읽어라. 숫자 네 자리만 답하고 다른 말은 하지 마라."


def make_eye_image():
    """네 자리 숫자가 큼직하게 적힌 그림을 만듭니다. (경로, 정답)"""
    code = str(random.randint(1000, 9999))     # 매번 새로 뽑습니다 — 못 보면 찍어서 맞힐 수 없게(1/9000)
    path = os.path.join(tempfile.gettempdir(), f"lucy_eye_{code}.png")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", EYE_PS1, "-Out", path, "-Code", code],
        capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0 or not os.path.isfile(path):
        raise RuntimeError((proc.stderr or "시험용 그림을 만들지 못했습니다").strip()[:120])
    return path, code


def _run_eye(agent, config, entry, path, code):
    """
    그림을 보여주고 숫자를 읽게 합니다. 돌려주는 값: True(봄) / False(못 봄) / None(측정 불가)

    ⚠️ 도구 명세는 싣지 않습니다(use_tools=False) — 이미지와 도구를 함께 보내면 거절하는
       모델이 있습니다. 실제 '보는 턴'과 같은 조건이어야 시험이 의미가 있습니다.
    """
    cfg = dict(config)
    cfg["models"] = [entry]
    msgs = [{"role": "system", "content": "너는 그림을 보고 답한다."},
            vision.user_message(EYE_QUESTION, [path])]

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            message, _used, _entry = agent.call_model(cfg, msgs, use_tools=False, order=[entry])
    except Exception:
        note = next((l.strip() for l in buf.getvalue().splitlines() if "->" in l), "실패")
        # 한도 때문에 못 잰 것을 '눈 없음'으로 적으면, 멀쩡한 눈을 config에서 지워버립니다.
        # 못 쟀으면 아무것도 바꾸지 않는 게 맞습니다.
        if any(k in note for k in RATE_LIMITED):
            return None
        return False
    return code in str(message.get("content") or "")


def _run_one(agent, config, entry, question):
    """에이전트 루프를 그대로 돌립니다(도구 포함). 실제 사용과 같은 조건이어야 의미가 있습니다."""
    msgs = [{"role": "system", "content": agent.build_system_prompt(config)},
            {"role": "user", "content": question}]
    buf = io.StringIO()
    t0 = time.time()
    try:
        with contextlib.redirect_stdout(buf):      # 도구 로그는 삼킵니다
            answer, _used = agent.run_turn(config, msgs, order=[entry])
        return answer, time.time() - t0, ""
    except Exception:
        note = next((l.strip() for l in buf.getvalue().splitlines() if "->" in l), "실패")
        return "", time.time() - t0, note.split(":", 1)[-1].strip()[:40]


def run(agent, config, pause=4, include_local=False, eyes=True):
    """
    두뇌들을 시험합니다. [{label, score, tried, secs, note, eye, entry}, ...]

    pause: 과제 사이에 쉬는 시간(초). 쉬지 않고 연타하면 우리가 직접 분당 한도를 터뜨려서,
           멀쩡한 모델이 '한도 초과'로 찍힙니다. 벤치가 자기 발등을 찍는 셈입니다.
    include_local: 로컬 모델은 과제당 5분 넘게 걸리는데(4GB VRAM), 어차피 순위와 무관하게
           항상 맨 아래(최후의 보루)라서 기본으로는 건너뜁니다.
    eyes: 그림을 볼 수 있는지도 함께 잽니다(순위에는 넣지 않고, config의 "vision" 줄만 고칩니다).
    """
    eye_path = eye_code = None
    if eyes:
        try:
            eye_path, eye_code = make_eye_image()
        except Exception as e:
            print(f"  (눈 시험용 그림을 만들지 못해 건너뜁니다: {e})")

    results = []
    for entry in config["models"]:
        label = entry["label"]
        is_local = entry.get("key_file") is None

        if entry.get("key_file") and not agent.load_key(entry):
            print(f"  {label:32} 건너뜀 (키 없음)")
            continue
        if is_local and not include_local:
            print(f"  {label:32} 건너뜀 (최후의 보루 — 순위와 무관, 항상 맨 아래)")
            results.append({"label": label, "score": 0, "tried": 0, "secs": 0.0,
                            "note": "시험 생략", "entry": entry, "local": True, "eye": None})
            continue

        cfg = dict(config)
        cfg["models"] = [entry]
        score, tried, total_secs, notes = 0, 0, 0.0, []

        for name, question, expect in TASKS:
            # 벤치는 쿨다운을 무시합니다. 시험하려고 부른 모델을 '쉬는 중'이라고 건너뛰면 안 됩니다.
            agent._cooldown.pop(label, None)
            answer, secs, err = _run_one(agent, cfg, entry, question)

            if err and any(k in err for k in RATE_LIMITED):
                print(f"  {label:32} {name:9} —  한도에 걸림, {pause * 3}초 쉬고 한 번 더")
                time.sleep(pause * 3)
                agent._cooldown.pop(label, None)
                answer, secs, err = _run_one(agent, cfg, entry, question)

            if err and any(k in err for k in RATE_LIMITED):
                notes.append("한도 초과로 측정 불가")
                print(f"  {label:32} {name:9} ?  측정 불가 (한도 초과 — 오답이 아님)")
            else:
                tried += 1
                ok = any(e in str(answer) for e in expect)
                score += 1 if ok else 0
                total_secs += secs
                if err:
                    notes.append(err)
                print(f"  {label:32} {name:9} {'O' if ok else 'X'}  {secs:5.1f}초"
                      + (f"  ({err})" if err else ""))
            time.sleep(pause)

        # 눈 시험은 점수에 넣지 않습니다 — 눈이 없어도 좋은 주력일 수 있습니다(글 질문이 대부분이니까요).
        # 그림 질문은 어차피 눈 달린 두뇌에게만 갑니다. 여기서 재는 건 '그 명단'이 맞는지입니다.
        eye = None
        if eye_path:
            agent._cooldown.pop(label, None)
            eye = _run_eye(agent, cfg, entry, eye_path, eye_code)
            mark = {True: "O 봄", False: "X 못 봄", None: "? 측정 불가"}[eye]
            was = entry.get("vision", False)
            changed = "" if eye is None or eye == was else "   ← config를 고칩니다"
            print(f"  {label:32} {'눈':9} {mark}{changed}")
            time.sleep(pause)

        results.append({
            "label": label, "score": score, "tried": tried,
            "secs": (total_secs / tried) if tried else 999.0,
            "note": notes[0] if notes else "", "entry": entry, "local": is_local,
            "eye": eye,
        })

    if eye_path:
        try:
            os.remove(eye_path)
        except OSError:
            pass
    agent._cooldown.clear()      # 벤치 때문에 걸린 쿨다운을 대화에 물려주지 않습니다
    return results


def accuracy(r):
    """맞힌 수 ÷ 실제로 잰 수. 한도 때문에 못 잰 과제는 분모에서 빠집니다."""
    return (r["score"] / r["tried"]) if r["tried"] else -1.0


def _key(r):
    """
    맞힌 개수(우선) → 정답률 → 속도.

    정답률만 쓰면 한 문제만 겨우 풀고 한도에 걸린 모델(1/1 = 100%)이
    세 문제를 다 맞힌 모델(3/3)을 이깁니다. 표본이 적은 쪽을 신뢰할 이유가 없습니다.
    맞힌 개수를 먼저 보면, 한도에 자주 걸려 재보지도 못한 모델은 자연히 뒤로 갑니다 —
    그게 맞습니다. 매번 한도에 걸리는 모델을 주력에 두면 질문마다 429를 맞고 시작하니까요.
    """
    return (-r["score"], -accuracy(r), r["secs"])


def rank(results):
    """
    순위 규칙:
      · 로컬 모델은 항상 맨 아래 — 인터넷이 끊겼을 때를 위한 최후의 보루라, 빠르다고 앞에 두면 안 됩니다.
      · 나머지는 맞힌 개수 → 정답률 → 속도.
      · 한 문제도 재보지 못한 모델은 뒤로 밀되 지우지 않습니다. 오늘 한도가 찼을 뿐
        내일은 멀쩡할 수 있으니까요.
    """
    online = sorted([r for r in results if not r["local"]], key=_key)
    local = [r for r in results if r["local"]]
    return online + local


def apply(ranked, config):
    """
    벤치 결과대로 config.json의 모델 **순서만** 다시 씁니다. 원본은 .bak로 백업합니다.

    주력(맨 앞)  = 만점 중 가장 빠른 모델 → 평소 질문을 즉답

    ⛔**deep은 벤치가 건드리지 않습니다(세션65, 사용자 결정 "수동 고정").**
      예전 규칙은 '만점 중 가장 느린 모델'에게 deep을 줬습니다 — "느리지만 정확한 쪽"이라는
      전제였는데, **'느림'은 깊이 생각한다는 증거가 아니었습니다.** 실측(4일치): 그 규칙으로
      deep을 받은 Gemini 3 Flash는 평균 9.0초·최대 26.8초에 한도 실패 9건이었고, 느렸던 이유는
      숙고가 아니라 **인프라 지연과 한도 스로틀링**이었습니다. 그런데 pick_order가 어려운 질문마다
      이 모델을 맨 앞으로 당기는 바람에, 느림과 한도 소진이 동시에 터졌습니다(호출 1위 49회).
      ⭐더 근본적으로는 **벤치의 3과제(검색·도구2개·추론)가 '어려운 질문 능력'을 재지 않습니다** —
      재지도 않은 것을 결과로 추론하면 안 됩니다. 그래서 deep은 사람이 config에 직접 적고,
      벤치는 그 줄을 그대로 둡니다.
    """
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # 지금 config에 적힌 deep을 그대로 보존합니다(벤치는 순서만 손댐).
    deep_label = next((m["label"] for m in raw["models"] if m.get("deep")), None)

    order = [r["label"] for r in ranked]
    eye_of = {r["label"]: r.get("eye") for r in ranked}
    by_label = {m["label"]: m for m in raw["models"]}
    new_models = []
    eye_changes = []
    for label in order:
        model = by_label.get(label)
        if not model:
            continue
        model.pop("deep", None)
        if label == deep_label:
            model["deep"] = True

        # 눈은 실측한 것만 고칩니다. 못 잰 모델(한도 초과·건너뜀)은 있던 줄을 그대로 둡니다 —
        # 오늘 한도가 찼다는 이유로 멀쩡한 눈을 지워버리면, 다음부터 그림 질문이 그 두뇌를 건너뜁니다.
        eye = eye_of.get(label)
        if eye is not None and eye != model.get("vision", False):
            eye_changes.append((label, eye))
            if eye:
                model["vision"] = True
            else:
                model.pop("vision", None)
        new_models.append(model)
    # 키가 없어서 시험하지 못한 모델은 지우지 않고 뒤에 남겨둡니다(키만 넣으면 다시 살아납니다).
    new_models += [m for m in raw["models"] if m["label"] not in order]

    shutil.copyfile(CONFIG_FILE, CONFIG_FILE + ".bak")
    raw["models"] = new_models
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    return order, deep_label, eye_changes


def _eye_mark(r):
    return {True: "  눈O", False: "  눈X", None: "  눈?"}[r.get("eye")]


def report(ranked):
    print("\n  ── 순위 (정답률 → 속도) ──")
    for i, r in enumerate(ranked, 1):
        if r["local"]:
            print(f"   {i}. {'—':>7}  {'—':>7}{_eye_mark(r)}  {r['label']}  (최후의 보루 · 인터넷 끊겨도 작동)")
            continue
        if not r["tried"]:
            print(f"   {i}. {'측정불가':>7}  {'—':>7}{_eye_mark(r)}  {r['label']}  ← {r['note'] or '한도 초과'}")
            continue
        print(f"   {i}. {r['score']}/{r['tried']}점  {r['secs']:5.1f}초{_eye_mark(r)}  {r['label']}"
              + (f"  ({r['note']})" if r["note"] else ""))
    print("   (눈O=그림을 봄 · 눈X=못 봄 · 눈?=못 잼 → 못 잰 것은 config를 건드리지 않습니다)")
