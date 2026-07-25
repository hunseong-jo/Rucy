"""
일꾼 모드 — 여러 단계짜리 일을 스스로 끝까지 해냅니다.

평소의 루시(respond→run_turn)는 **한 번의 문답**입니다. 도구를 몇 번 쓰고 답이 나오면 끝입니다.
그래서 "자료 찾아서 정리하고 문서로 만들어 줘"처럼 단계가 여럿인 일을 시키면,
중간에서 만족하고 멈추거나(문서를 안 만듦), 도구 한도(max_steps)에 걸려 잘립니다.

일꾼 모드는 그 위에 얹는 **바깥 루프**입니다.

    계획 세우기  →  [ 한 단계 실행 → 스스로 검증 → 아니면 다시 ]×N  →  최종 보고

핵심은 '검증'입니다. 모델은 "다 했습니다"라고 말하는 데 아무 저항이 없어서, 시키지 않으면
파일을 안 만들어 놓고도 만들었다고 합니다. 그래서 매 단계마다 **다른 턴**에서
"이 단계의 완료 조건이 실제로 충족됐는가"를 도구 결과(근거)와 대조해 판정하고,
아니라고 나오면 그 이유를 알려주며 다시 시킵니다.

각 단계는 **자기만의 짧은 대화**에서 돕니다. 한 대화에 전부 쌓으면 도구 결과가 눈덩이처럼
불어나 컨텍스트 한도(무료 Cerebras는 8192)를 먼저 넘겨 죽습니다. 본 대화에는 목표와
최종 보고만 남기므로, 일이 끝난 뒤에도 "아까 그거 어디 저장했지?"가 이어집니다.
"""
import json
import re
import time

import lessons

# 사용자가 일꾼 모드를 부르는 말. '/일'이 확실한 방법이고, 자연스러운 말도 몇 개 받습니다.
# 너무 넓게 잡으면 평범한 부탁까지 일꾼 모드로 끌려가 느려지므로 좁게 둡니다.
TRIGGER = re.compile(
    r"^\s*/(일|일꾼|work)\b"
    r"|알아서\s*(다|전부|끝까지)"
    r"|끝까지\s*(해|처리|맡)"
    r"|혼자(서)?\s*(다|전부)\s*(해|처리)",
    re.I,
)

PLAN_PROMPT = """너는 개인 비서다. 사용자가 아래 '목표'를 시켰다.
이걸 끝내려면 무엇을 어떤 순서로 해야 하는지 **실행 계획**을 세워라.

규칙:
- 단계는 최대 {max_steps}개. 적을수록 좋다. 한 번의 문답으로 끝날 일이면 1단계로 써라.
- 각 단계는 네가 가진 도구로 **실제로 실행할 수 있는 일**이어야 한다.
  (쓸 수 있는 도구: 웹 검색·웹페이지 읽기·파일 읽기/쓰기·문서 만들기(워드/PPT/엑셀)·
   파이썬 실행·계산·그림 그리기·지식창고 검색·기억·클립보드·파워셸)
- "사용자에게 물어본다" 같은 단계는 넣지 마라. 너 혼자 끝내야 한다.
- done_when(완료 조건)은 **눈으로 확인 가능한 결과**로 적어라.
  나쁨: "조사를 잘한다"   좋음: "출처 3개 이상을 링크와 함께 확보했다"
  나쁨: "문서를 정리한다" 좋음: "C:/Users/user/Desktop/보고서.docx 파일이 실제로 만들어졌다"

JSON 배열만 출력하라. 설명·인사·코드펜스 금지.
[{{"step": "할 일", "done_when": "완료 조건"}}, ...]

[목표]
{goal}"""

VERIFY_PROMPT = """단계 하나가 끝났다고 한다. **실제로 끝났는지** 판정하라.

너는 깐깐한 검사관이다. 일꾼은 아무것도 안 해 놓고 "완료했습니다"라고 말하는 버릇이 있다.
말이 아니라 **도구가 돌려준 근거**를 봐라. 근거가 없으면 안 끝난 것이다.
단, 완료 조건을 충족했다면 더 잘할 수 있었다는 이유로 트집 잡지는 마라.

[전체 목표] {goal}
[이번 단계] {step}
[완료 조건] {done_when}

[도구가 돌려준 것(근거)]
{evidence}

[일꾼의 보고]
{report}

JSON만 출력하라. 설명·코드펜스 금지.
{{"done": true 또는 false, "why": "안 됐다면 무엇이 부족한지 한 문장. 됐으면 빈 문자열"}}"""

STEP_SYSTEM = """{persona}

너는 지금 **일꾼 모드**다. 큰 목표를 단계로 쪼개 하나씩 처리하는 중이다.

[전체 목표] {goal}

[지금까지 한 일]
{done_so_far}

[이번에 할 일] {step}
[완료 조건] {done_when}

이번 단계**만** 처리하라. 다음 단계를 미리 하지 마라.
말로 때우지 말고 **도구를 실제로 불러서** 하라. 파일을 만들라고 하면 진짜로 만들어야 한다.

⚠️ 지어내지 마라. URL·수치·날짜·인용은 **도구가 실제로 돌려준 것만** 써라.
   검색 결과에 기사 링크가 없으면 기억나는 주소를 적지 말고, 링크를 못 찾았다고 보고하라.
   (예전에 'wsj.com/tech/ai' 같은 카테고리 주소를 기사 출처인 양 적어 냈다가 반려됐다.)

끝나면 무엇을 했고 결과가 어디에 있는지(경로·수치·출처) 짧게 보고하라."""

FINAL_PROMPT = """일이 끝났다. 사용자에게 **결과만** 보고하라.

[사용자가 시킨 일] {goal}

[단계별 결과 — '실패'로 적힌 것은 검사관이 근거를 확인하고 내린 판정이다]
{results}

규칙:
- 무엇이 나왔는지, 어디에 있는지(파일 경로·핵심 수치·출처)를 먼저 말하라.
- 과정 나열·자화자찬 금지. 사용자는 결과만 궁금하다.
- ⚠️ **실패로 적힌 단계를 성공한 것처럼 쓰지 마라.** 파일이 안 만들어졌으면
  "만들었습니다"라고 쓰면 안 된다. 무엇이 왜 안 됐는지 그대로 밝혀라.
- 확인되지 않은 수치·시각·경로를 지어내지 마라. 근거에 있는 것만 써라.
- 한국어 존댓말, 간결하게."""


def enabled(config):
    return config.get("worker", {}).get("enabled", True)


def wants(text):
    """이 부탁이 일꾼 모드로 갈 일인가."""
    return bool(TRIGGER.search(text or ""))


def strip_request(text):
    """'/일 보고서 만들어줘' → '보고서 만들어줘'"""
    return re.sub(r"^\s*/(일꾼|일|work)\b[:\s]*", "", text or "", flags=re.I).strip()


def json_from(text, want_list=False):
    """
    모델은 JSON만 내놓으라고 해도 코드펜스나 인사말을 붙입니다. 거기서 알맹이만 뽑습니다.

    find("{")·rfind("}")로 바깥을 자르면 답변 속 예시 중괄호까지 물려서 통째로 깨집니다
    (예: "설명 {요약} 하고… {진짜JSON}"). 그래서 괄호 짝을 직접 세며 걷습니다 —
    문자열 안의 괄호는 세지 않고, 첫 후보가 깨진 JSON이면 다음 여는 괄호부터 다시 봅니다.
    """
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence and fence.group(1).strip():
        text = fence.group(1).strip()

    open_ch, close_ch = ("[", "]") if want_list else ("{", "}")
    start = text.find(open_ch)
    while start >= 0:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find(open_ch, start + 1)
    return None


def _plan(config, call_model, goal, notify):
    """목표를 단계로 쪼갭니다. 실패하면 '통째로 한 단계'로 물러섭니다(멈추는 것보단 낫습니다)."""
    max_steps = config.get("worker", {}).get("max_steps", 6)
    prompt = PLAN_PROMPT.format(goal=goal, max_steps=max_steps)

    try:
        message, _used, _entry = call_model(
            config, [{"role": "user", "content": prompt}], use_tools=False
        )
    except Exception as e:                      # AllModelsFailed 등 — 계획을 못 세워도 일은 해봅니다
        notify(f"[일꾼] 계획을 세우지 못했습니다({type(e).__name__}) — 통째로 한 번에 시도합니다")
        return [{"step": goal, "done_when": "사용자가 시킨 일이 실제로 끝났다"}]

    parsed = json_from(message.get("content"), want_list=True)
    steps = []
    for item in (parsed or []):
        if isinstance(item, dict) and item.get("step"):
            steps.append({
                "step": str(item["step"])[:200],
                "done_when": str(item.get("done_when") or "이 단계의 결과물이 실제로 존재한다")[:200],
            })
    if not steps:
        notify("[일꾼] 계획이 비어 있어 통째로 한 번에 시도합니다")
        return [{"step": goal, "done_when": "사용자가 시킨 일이 실제로 끝났다"}]
    return steps[:max_steps]


def _evidence(messages, limit=2500):
    """이 단계에서 도구가 실제로 돌려준 것들 — 검사관이 보고와 대조할 근거입니다."""
    bits = [str(m.get("content", "")) for m in messages if m.get("role") == "tool"]
    return ("\n---\n".join(bits))[-limit:] if bits else "(도구를 하나도 쓰지 않음)"


def _verify(config, call_model, goal, step, report, evidence):
    """정말 끝났는지 판정합니다. (True, '') 또는 (False, 부족한 이유)."""
    prompt = VERIFY_PROMPT.format(
        goal=goal, step=step["step"], done_when=step["done_when"],
        evidence=evidence, report=report,
    )
    try:
        message, _used, _entry = call_model(
            config, [{"role": "user", "content": prompt}], use_tools=False
        )
    except Exception:
        return True, ""       # 검사관을 못 부르면 통과시킵니다. 못 넘어가고 무한 재시도하는 것보단 낫습니다.

    verdict = json_from(message.get("content")) or {}
    done = verdict.get("done")
    if done is None:
        return True, ""
    return bool(done), str(verdict.get("why") or "")[:200]


def run(config, state, goal, call_model, run_turn, notify=print, preface=None, log=None):
    """
    목표 하나를 끝까지 해냅니다. respond()와 같은 (답, 사용한 두뇌)를 돌려줍니다.

    call_model·run_turn을 인자로 받는 이유: agent가 worker를 부르는데 worker가 agent를 부르면
    순환 임포트가 됩니다. lessons.learn()이 쓰는 방식과 같습니다.
    """
    conf = config.get("worker", {})
    retries = max(1, conf.get("retries", 2))
    budget_min = conf.get("max_minutes", 12)
    do_verify = conf.get("verify", True)
    persona = state["messages"][0].get("content", "")
    deadline = time.time() + budget_min * 60

    if not goal:
        return ("무슨 일을 시킬지 함께 적어주세요. 예: /일 이번 주 AI 뉴스 정리해서 "
                "바탕화면에 워드로 만들어줘", "일꾼")

    if log:
        log("나", goal)

    notify("[일꾼] 계획을 세웁니다...")
    steps = _plan(config, call_model, goal, notify)
    notify(f"[일꾼] {len(steps)}단계 계획:")
    for i, s in enumerate(steps, 1):
        notify(f"    {i}. {s['step']}  (끝난 기준: {s['done_when']})")

    results, used_last = [], "일꾼"

    for i, step in enumerate(steps, 1):
        if time.time() > deadline:
            results.append({"step": step["step"], "ok": False,
                            "report": f"시간(최대 {budget_min}분)이 다 되어 시작하지 못했습니다."})
            notify(f"[일꾼] 시간이 다 되어 {i}단계부터는 건너뜁니다")
            break

        done_so_far = "\n".join(
            f"- {r['step']} → {'완료' if r['ok'] else '실패'}: {r['report'][:150]}"
            for r in results
        ) or "(아직 없음)"

        feedback = None       # 검사관이 퇴짜 놓은 이유 — 다시 시킬 때 함께 넘깁니다
        ok, report, why = False, "", ""

        for attempt in range(1, retries + 1):
            tag = f"{i}/{len(steps)}" + (f" (재시도 {attempt - 1})" if attempt > 1 else "")
            # 시간 검사를 단계 시작 때만 하면, 오래 걸린 시도 뒤의 재시도가 예산을 넘겨 이어집니다.
            # 재시도 사이에도 잽니다 (도구 하나하나는 각자 타임아웃이 있어 무한정 매달리진 않습니다).
            if attempt > 1 and time.time() > deadline:
                why = f"시간(최대 {budget_min}분)이 다 되어 재시도를 포기했습니다"
                notify(f"[일꾼 {tag}] {why}")
                break
            notify(f"[일꾼 {tag}] {step['step']}")

            sub = [{"role": "system", "content": STEP_SYSTEM.format(
                persona=persona, goal=goal, done_so_far=done_so_far,
                step=step["step"], done_when=step["done_when"],
            )}]
            sub += list(preface or [])       # 관련 기억·실수 노트를 단계마다 함께 읽힙니다
            ask = step["step"]
            if feedback:
                ask += (f"\n\n(앞선 시도는 이렇게 부족하다는 판정을 받았다: {feedback}\n"
                        f"이번엔 그 부분을 반드시 채워라.)")
            sub.append({"role": "user", "content": ask})

            try:
                report, used_last = run_turn(config, sub, use_tools=True)
            except Exception as e:           # 두뇌가 전부 죽어도 남은 단계는 시도해 봅니다
                report, ok = f"실행하지 못했습니다: {type(e).__name__}: {e}", False
                why = report
                notify(f"[일꾼 {tag}] 실패 — {type(e).__name__}")
                break

            if not do_verify:
                ok = True
                break

            ok, why = _verify(config, call_model, goal, step, report, _evidence(sub))
            if ok:
                notify(f"[일꾼 {tag}] 확인 완료")
                break
            feedback = why
            notify(f"[일꾼 {tag}] 아직 안 끝났습니다 — {why}")

        if not ok:
            notify(f"[일꾼] {i}단계를 {retries}번 시도하고도 끝내지 못해, 다음 단계로 넘어갑니다")
        results.append({"step": step["step"], "ok": ok, "report": report, "why": why})

        # 퇴짜를 맞았다가 고쳐서 통과했다면, 그 차이가 곧 교훈입니다.
        # 사용자의 지적 없이도 스스로 배우는 유일한 지점 — 검사관의 퇴짜 사유(무엇이 부족했나)와
        # 통과한 보고(어떻게 채웠나)가 한 쌍으로 남아 있어서 가능합니다.
        if ok and feedback:
            lesson = lessons.learn_from_work(config, call_model, goal, step["step"], feedback, report)
            if lesson:
                notify(f"[실수 노트] 일하면서 배웠습니다 — {lesson}")

    # 일꾼의 '보고'는 못 믿습니다(파일을 안 만들어 놓고 만들었다고 합니다). 실패한 단계는
    # 일꾼의 말 대신 **검사관의 판정**을 요약 모델에게 넘깁니다.
    summary = "\n\n".join(
        f"[{i}단계] {r['step']}\n"
        + (f"결과: 완료\n{r['report']}" if r["ok"]
           else f"결과: ⚠️ 실패 — 검사관 판정: {r['why'] or '완료 근거 없음'}\n"
                f"(일꾼은 이렇게 주장했지만 믿지 마라: {r['report'][:200]})")
        for i, r in enumerate(results, 1)
    )

    notify("[일꾼] 결과를 정리합니다...")
    try:
        message, used_last, _entry = call_model(
            config,
            [{"role": "user", "content": FINAL_PROMPT.format(goal=goal, results=summary)}],
            use_tools=False,
        )
        answer = (message.get("content") or "").strip()
    except Exception:
        answer = ""
    if not answer:
        answer = summary or "아무것도 하지 못했습니다."

    # 요약 모델이 실패를 성공으로 둔갑시키는 일이 실제로 있었습니다(안 만든 파일을 만들었다고 보고).
    # 그래서 실패 사실만은 모델의 말과 무관하게 **코드가** 덧붙입니다. 이건 못 지어냅니다.
    failed = [r for r in results if not r["ok"]]
    if failed:
        answer += f"\n\n⚠️ 끝내지 못한 단계 {len(failed)}개 (위 보고가 이걸 성공이라 했다면 그건 틀린 말입니다):"
        for r in failed:
            answer += f"\n  · {r['step']} — {r['why'] or '완료를 확인하지 못했습니다'}"

    # 본 대화에는 목표와 최종 보고만 남깁니다. 단계별 도구 결과까지 쌓으면 컨텍스트가 터집니다.
    state["messages"].append({"role": "user", "content": goal})
    state["messages"].append({"role": "assistant", "content": answer})
    state["last_q"], state["last_a"], state["last_images"] = goal, answer, []
    if log:
        log(config.get("name", "루시"), answer)

    return answer, used_last
