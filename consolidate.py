# -*- coding: utf-8 -*-
"""
기억 정리 — 쌓인 기억을 정기적으로 병합하고, 지난 것을 지웁니다.

기억은 들어올 때만 걸러집니다. 세션 요약의 중복 필터(임베딩 0.90)는 '거의 같은 문장'만
잡기 때문에, 시간이 지나면 같은 주제의 기억이 여러 줄로 흩어지고("홍차를 좋아함" /
"홍차를 즐겨 마심"), 이미 지난 일정이 남고, 옛 기억과 새 기억이 모순된 채
검색에 같이 딸려옵니다. 그래서 일주일에 한 번 모델에게 목록을 보여주고
"합칠 것 / 지울 것"을 제안받아 정리합니다. (notes.md와 lessons.md 두 통 모두)

⚠️ 설계 원칙: 모델에게 기억 전체를 다시 쓰게 하지 않습니다.
   통째로 다시 쓰게 하면 멀쩡한 기억이 조용히 빠지거나 문장이 미묘하게 바뀌는데,
   그걸 코드가 검증할 방법이 없습니다. 대신 모델은 **작업 목록**(몇 번과 몇 번을
   합쳐라, 몇 번을 지워라)만 제안하고 적용은 코드가 합니다 — 지목되지 않은 기억은
   글자 하나 바뀌지 않고, 제안이 절반을 넘게 건드리면 통째로 의심하고 버립니다.
   적용 전 원본은 memory/backups/에 남으므로 잘못 정리해도 되돌릴 수 있습니다.
"""
import datetime
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
BACKUP_DIR = os.path.join(MEMORY_DIR, "backups")

# (보이는 이름, 파일, 프롬프트 종류)
STORES = [
    ("장기 기억", os.path.join(MEMORY_DIR, "notes.md"), "notes"),
    ("실수 노트", os.path.join(MEMORY_DIR, "lessons.md"), "lessons"),
]

NOTES_PROMPT = """너는 AI 비서의 장기 기억을 정리하는 사서다. 오늘은 {today}다.
아래는 사용자에 관한 기억 목록이다(끝의 괄호는 적은 날짜). 세 가지만 찾아라.

1. 병합 — 같은 주제의 기억 여러 개는 한 문장으로 합쳐라. 정보를 잃지 마라.
   서로 다른 주제(예: 취향과 프로젝트)를 한 줄로 뭉치지 마라.
2. 모순 — 같은 것을 두고 내용이 어긋나면 하나로 합치되, 날짜가 나중인 쪽을 사실로 삼아라.
3. 만료 — 날짜가 이미 지난 일정·마감·예약처럼 더는 쓸모없어진 기억은 지워라.
   (선호·습관·사는 곳·프로젝트 정보는 오래됐다는 이유만으로 지우면 안 된다)

규칙:
- 확실한 것만 제안하라. 애매하면 건드리지 마라. 고칠 것이 없으면 빈 배열 []이 정답이다.
- 합친 문장은 원래 기억들의 정보를 전부 담아라. 없던 정보를 지어내지 마라.
  날짜 괄호는 문장에 쓰지 마라(코드가 붙인다).
- targets의 번호는 아래 목록의 번호다. 하나의 번호를 두 작업에 넣지 마라.
- 반드시 JSON 배열 하나만 출력하라. 설명·코드블록·다른 말 금지.

출력 예:
[{{"action": "merge", "targets": [2, 5], "text": "사용자는 홍차를 좋아하고 매일 아침 마심"}},
 {{"action": "delete", "targets": [7], "why": "2026-07-02 발표는 이미 지남"}}]

[기억 목록]
{items}"""

LESSONS_PROMPT = """너는 AI 비서의 '실수 노트'를 정리하는 감독자다. 오늘은 {today}다.
실수 노트는 비서가 틀렸던 일에서 뽑은 행동 지침이다. 아래 목록에서 두 가지만 찾아라.

1. 병합 — **같은 실수**를 가리키는 교훈의 변형들만 하나로 합쳐라. 더 구체적인 쪽의 표현을 살려라.
2. 중복 — 다른 교훈에 내용이 완전히 포함되는 교훈은 지워라.

규칙:
- 주제가 다른 교훈을 한 줄로 뭉치지 마라. 교훈에 든 구체 사실(올바른 값·수치)을 잃지 마라.
- 교훈은 지난 일정과 달리 시간이 지나도 유효하다. 오래됐다는 이유로 지우지 마라.
- 확실한 것만 제안하라. 고칠 것이 없으면 빈 배열 []이 정답이다.
- 합친 문장에 없던 내용을 지어내지 마라. 날짜 괄호는 쓰지 마라(코드가 붙인다).
- targets의 번호는 아래 목록의 번호다. 하나의 번호를 두 작업에 넣지 마라.
- 반드시 JSON 배열 하나만 출력하라. 설명·코드블록·다른 말 금지.

출력 예:
[{{"action": "merge", "targets": [1, 4], "text": "프로젝트 수치는 기억에 의존하지 말고 search_knowledge로 확인할 것"}}]

[실수 노트]
{items}"""


# ── 파일 읽기 ─────────────────────────────────────────────────────
def _read(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def _note_lines(lines):
    """기억이 적힌 줄의 위치들. 머리글·빈 줄은 건드리지 않고 그대로 보존하기 위해 위치로 다룹니다."""
    return [i for i, l in enumerate(lines) if l.strip().startswith("- ")]


def _items(lines):
    return [lines[i].strip()[2:].strip() for i in _note_lines(lines)]


# ── 제안 받기 ─────────────────────────────────────────────────────
def _parse_ops(text, count):
    """
    모델의 제안을 뜯어보고 **믿을 수 있는 것만** 남깁니다.
    범위 밖 번호, 형식이 틀린 항목, 이미 다른 작업이 잡은 번호는 조용히 버립니다 —
    제안 하나가 이상하다고 전체를 버리면 멀쩡한 정리까지 놓치기 때문입니다.
    """
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    ops, used = [], set()
    for raw in data:
        if not isinstance(raw, dict):
            continue
        action = raw.get("action")
        targets = raw.get("targets")
        if action not in ("merge", "delete") or not isinstance(targets, list):
            continue
        try:
            targets = sorted({int(t) for t in targets})
        except (TypeError, ValueError):
            continue
        if not targets or targets[0] < 1 or targets[-1] > count:
            continue
        if any(t in used for t in targets):
            continue
        new_text = str(raw.get("text") or "").strip()
        if action == "merge" and (len(targets) < 2 or not new_text or len(new_text) > 400):
            continue
        ops.append({"action": action, "targets": targets,
                    "text": new_text, "why": str(raw.get("why") or "").strip()})
        used.update(targets)
    return ops


def propose(lines, kind, config, call_model, guard=True):
    """
    모델에게 정리안을 제안받습니다. (검증을 통과한 작업 목록, 비었을 때의 이유)

    guard=True(배경 실행)면 제안이 기억의 절반을 넘게 건드릴 때 통째로 버립니다.
    '/기억정리'는 사람이 보고 거절할 수 있으므로 이 장치를 끕니다(guard=False) —
    안 그러면 기억이 몇 개 안 될 때 멀쩡한 병합안까지 사람이 보기도 전에 막힙니다.
    """
    items = _items(lines)
    if len(items) < 2:
        return [], f"기억이 {len(items)}개뿐이라 정리할 게 없음"

    prompt = (NOTES_PROMPT if kind == "notes" else LESSONS_PROMPT).format(
        today=datetime.date.today().isoformat(),
        items="\n".join(f"{n}. {t}" for n, t in enumerate(items, 1)),
    )
    message, _used, _entry = call_model(config, [{"role": "user", "content": prompt}],
                                        use_tools=False)
    ops = _parse_ops(message.get("content"), len(items))
    if not ops:
        return [], "고칠 것 없음"

    # 제안이 기억의 절반을 넘게 건드리면 모델의 판단 전체를 의심합니다.
    # (첫 정리라도 진짜 절반이 쓰레기인 경우는 드뭅니다 — 사람이 /기억정리로 보고 정하면 됩니다)
    if guard:
        touched = {t for op in ops for t in op["targets"]}
        ratio = config.get("daily", {}).get("consolidate", {}).get("max_touch_ratio", 0.5)
        if len(touched) > max(4, int(len(items) * ratio)):
            return [], (f"제안이 기억의 절반 이상을 건드려 의심스러움({len(touched)}/{len(items)}개)"
                        " — 적용 안 함 (직접 보려면 /기억정리)")
    return ops, ""


def describe(ops, lines):
    """제안을 사람이 읽을 줄들로. (배경 실행의 기록과 /기억정리의 미리보기가 같은 것을 봅니다)"""
    items = _items(lines)
    out = []
    for op in ops:
        if op["action"] == "merge":
            out.append("[병합]")
            out.extend(f"  - {items[t - 1]}" for t in op["targets"])
            out.append(f"  → {op['text']}")
        else:
            for t in op["targets"]:
                out.append(f"[삭제] {items[t - 1]}" + (f" — {op['why']}" if op["why"] else ""))
    return out


# ── 적용 ──────────────────────────────────────────────────────────
def apply(path, lines, ops):
    """
    작업 목록을 파일에 적용합니다. (병합 건수, 삭제 줄수, 백업 경로)

    병합된 문장은 첫 대상의 자리에 오늘 날짜로 들어가고, 나머지 대상 줄은 빠집니다.
    지목되지 않은 줄(머리글 포함)은 원문 그대로입니다.
    """
    pos = _note_lines(lines)
    today = datetime.date.today().isoformat()

    replace, drop = {}, set()
    for op in ops:
        where = [pos[t - 1] for t in op["targets"]]
        if op["action"] == "merge":
            replace[where[0]] = f"- {op['text']}  ({today})\n"
            drop.update(where[1:])
        else:
            drop.update(where)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(path))[0]
    backup = os.path.join(BACKUP_DIR, f"{base}_{stamp}.md")
    with open(backup, "w", encoding="utf-8") as f:
        f.writelines(lines)

    out = [replace.get(i, line) for i, line in enumerate(lines) if i not in drop]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(out)
    os.replace(tmp, path)                # 쓰다 죽어도 원본이 남게(원자적 저장)
    # 임베딩 캐시는 문장 해시 기준이라 따로 지울 게 없습니다 —
    # 새 문장은 다음 검색 때 계산되고, 사라진 문장의 벡터는 memory_search가 걷어냅니다.

    merged = sum(1 for op in ops if op["action"] == "merge")
    deleted = sum(len(op["targets"]) for op in ops if op["action"] == "delete")
    return merged, deleted, backup


# ── 장기 대화록 자동 요약 및 압축 (30일+) ──────────────────────────────
def archive_old_history(config, call_model=None, notify=print, days_threshold=30):
    """
    30일 이상 지난 대화록(memory/history/YYYY-MM-DD.md)을 정기적으로 요약하여
    memory/summarized.json 및 notes.md에 통합 정리하고 토큰 사용을 최적화(압축)합니다.
    """
    import memory_search
    import session

    history_dir = os.path.join(MEMORY_DIR, "history")
    if not os.path.exists(history_dir):
        return 0

    today = datetime.date.today()
    cutoff_date = today - datetime.timedelta(days=days_threshold)

    files = [f for f in os.listdir(history_dir) if f.endswith(".md") and re.match(r"^\d{4}-\d{2}-\d{2}\.md$", f)]
    archived_count = 0

    covered_data = session._covered()

    if call_model is None:
        try:
            import agent
            call_model = agent.call_model
        except Exception:
            pass

    for fname in sorted(files):
        day_str = fname[:-3]
        try:
            file_date = datetime.date.fromisoformat(day_str)
        except ValueError:
            continue

        if file_date > cutoff_date:
            continue

        fpath = os.path.join(history_dir, fname)
        file_size = os.path.getsize(fpath)

        covered_info = covered_data.get(day_str)
        if isinstance(covered_info, dict) and covered_info.get("archived"):
            continue

        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if len(content.strip()) < 150:
            covered_data[day_str] = {"size": file_size, "archived": True, "archived_at": today.isoformat()}
            archived_count += 1
            continue

        notify(f"  30일 이상 지난 대화록({day_str}) 장기 메모리 요약 및 압축 진행...")

        saved_facts = []
        if call_model:
            existing_notes = memory_search.load_notes()
            prompt = session.SUMMARY_PROMPT.format(
                existing="\n".join("- " + e for e in existing_notes) or "(없음)",
                transcript=content[-8000:]
            )
            try:
                msg, _used, _entry = call_model(config, [{"role": "user", "content": prompt}], use_tools=False)
                facts = session._extract_json_array(msg.get("content"))
                saved_facts = [x for x in facts if not session._is_duplicate(x, existing_notes + saved_facts, config)]
            except Exception as e:
                notify(f"  ({day_str} 대화록 요약 실패: {type(e).__name__} — 다음 주기에 재시도)")
                continue

        if saved_facts:
            notes_file = os.path.join(MEMORY_DIR, "notes.md")
            with open(notes_file, "a", encoding="utf-8") as f:
                for fact in saved_facts:
                    f.write(f"- {fact}  ({day_str})\n")
            notify(f"  {day_str} 대화록에서 {len(saved_facts)}개 주요 사실을 notes.md 에 통합했습니다.")

        compressed_text = f"# {day_str} 대화록 (30일 경과 요약 압축본)\n\n- 요약 일자: {today.isoformat()}\n- 추출된 핵심 정보: {len(saved_facts)}건 통합 완료\n"
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(compressed_text)

        covered_data[day_str] = {
            "size": len(compressed_text.encode("utf-8")),
            "archived": True,
            "archived_at": today.isoformat(),
            "facts_count": len(saved_facts)
        }
        archived_count += 1

    if archived_count > 0:
        tmp = session.COVERED_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(covered_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, session.COVERED_FILE)
        session.auto_git_sync("push")

    return archived_count


# ── 두 가지 문 ────────────────────────────────────────────────────
def run(config, notify=print):
    """
    정기 실행(daily.tick이 부릅니다). 사람이 없으므로 제안을 그대로 적용하되,
    무엇을 어떻게 바꿨는지 전부 notify로 남기고 백업을 남깁니다. (정리한 통 개수)
    """
    import agent

    cfg = config.get("daily", {}).get("consolidate", {})
    min_items = cfg.get("min_items", 10)
    done = 0

    # 30일 이상 지난 대화록 장기 메모리 요약 및 압축 수행
    try:
        archived = archive_old_history(config, agent.call_model, notify, days_threshold=30)
        if archived > 0:
            notify(f"  장기 대화록 압축 요약: {archived}개 파일 처리")
    except Exception as e:
        notify(f"  장기 대화록 압축 요약 중 오류: {type(e).__name__}: {e}")

    for label, path, kind in STORES:
        lines = _read(path)
        count = len(_note_lines(lines))
        if count < min_items:
            continue                     # 아직 정리할 만큼 안 쌓임 — 조용히 넘어갑니다
        try:
            ops, why = propose(lines, kind, config, agent.call_model)
        except Exception as e:
            notify(f"  {label}: 제안을 받지 못함 ({type(e).__name__}) — 다음 주기에 다시 시도")
            continue
        if not ops:
            notify(f"  {label}: {why}")
            continue
        for line in describe(ops, lines):
            notify(f"    {line}")
        merged, deleted, backup = apply(path, lines, ops)
        notify(f"  {label}: 병합 {merged}건 · 삭제 {deleted}줄 (원본: {backup})")
        done += 1
    return done


def run_interactive(config, call_model):
    """
    '/기억정리' — 지금 훑어서 제안을 보여주고, 사람이 y라고 해야 적용합니다.
    (수동 실행은 개수 제한 없이 훑습니다 — 사람이 보자고 부른 것이므로)
    """
    for label, path, kind in STORES:
        lines = _read(path)
        count = len(_note_lines(lines))
        if count < 2:
            print(f"  {label}: 기억이 {count}개뿐이라 정리할 게 없습니다.")
            continue
        print(f"  {label} {count}개를 훑는 중...")
        try:
            ops, why = propose(lines, kind, config, call_model, guard=False)
        except Exception as e:
            print(f"  {label}: 제안을 받지 못했습니다 ({type(e).__name__}: {e})")
            continue
        if not ops:
            print(f"  {label}: {why}")
            continue
        for line in describe(ops, lines):
            print(f"    {line}")
        if input(f"  {label}에 적용할까요? [y/N] ").strip().lower() != "y":
            print("  그대로 두었습니다.")
            continue
        merged, deleted, backup = apply(path, lines, ops)
        print(f"  적용했습니다 — 병합 {merged}건 · 삭제 {deleted}줄. 원본은 {backup}")
