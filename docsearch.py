"""
내 PC 문서 전체 검색 — "작년에 쓴 그 계약서 어디 있지?"

지식 창고(knowledge.py)와는 다른 물건입니다.
  · 지식 창고 = 내가 **골라서 넣은** 자료(강의 PDF·프로젝트 노트). 의미 검색(임베딩).
  · 문서 검색 = 내 PC에 **이미 널려 있는** 파일들. 넣은 적 없어도 찾아냅니다.

임베딩을 쓰지 않는 이유: 바탕화면·문서·다운로드에는 파일이 수백 개입니다. 전부 임베딩하면
색인에 몇십 분이 걸리고, 질문할 때마다 Ollama를 깨워야 합니다(지식 창고에서 이미 겪었습니다 —
병목은 문서 파싱이 아니라 질문 임베딩이었습니다). 파일을 찾는 일은 대개 "계약서", "정산",
"2025 예산" 같은 **낱말로 충분히** 찾힙니다. 그래서 낱말 점수로 빠르게 찾고, 파일을 찾은 뒤
내용을 자세히 보는 건 read_document에 맡깁니다.

색인은 증분입니다. 파일의 수정시각이 그대로면 다시 읽지 않으므로, 두 번째부터는 몇 초입니다.
"""
import json
import os
import re
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "memory", "files_index.json")

# 읽을 수 있는 것만. 구버전 .doc/.xls/.ppt/.hwp(바이너리)는 형식이 달라 파서가 없습니다.
# 한글은 HWPX(2014+ 기본 저장, zip+xml)만 읽습니다.
TEXT_EXT = {".txt", ".md", ".csv", ".log", ".json", ".py", ".js", ".cs", ".html", ".bat", ".ps1"}
DOC_EXT = {".pdf", ".docx", ".xlsx", ".pptx", ".hwpx"}

# 들어가면 안 되는 곳 — 프로그램 찌꺼기가 수만 개씩 있어 색인이 며칠 걸립니다.
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv", "env",
    "Library", "Temp", "AppData", "obj", "bin", "build", "dist",
    ".idea", ".vs", ".vscode", "site-packages", "Logs", "cache", ".cache",
}

# 파일 한 개에서 색인할 글자 수. 전문을 다 담으면 색인 파일이 수백 MB가 됩니다.
# 앞부분 몇천 자면 "이 파일이 그 파일인가"를 가리기에 충분하고, 자세히 볼 땐 read_document를 씁니다.
MAX_CHARS = 6000


def _conf(config):
    return (config or {}).get("filesearch", {})


def enabled(config):
    return _conf(config).get("enabled", True)


def _roots(config):
    import portable
    roots = _conf(config).get("roots") or ["~/Desktop", "~/Documents", "~/Downloads"]
    return [d for d in (portable.expand(r) for r in roots) if os.path.isdir(d)]


def _extract(path, ext):
    """파일에서 글자를 뽑습니다. 파서는 tools.py 것을 그대로 씁니다(같은 코드를 두 벌 두지 않습니다).

    tools를 함수 안에서 늦게 부르는 이유: tools.py가 이 모듈을 가져다 쓰므로,
    위에서 import하면 순환 임포트가 됩니다.
    """
    if ext in TEXT_EXT:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(MAX_CHARS * 2)

    import tools
    import zipfile
    if ext == ".pdf":
        return tools._read_pdf(path)
    with zipfile.ZipFile(path) as zf:
        if ext == ".docx":
            return tools._read_docx(zf)
        if ext == ".pptx":
            return tools._read_pptx(zf)
        if ext == ".hwpx":
            return tools._read_hwpx(zf)
        return tools._read_xlsx(zf)


def _load():
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"built_at": 0, "files": {}}


def _save(index):
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)


def build(config, notify=print, force=False):
    """바뀐 파일만 다시 읽어 색인을 갱신합니다. (새로 읽은 수, 전체 수, 실패 수)"""
    conf = _conf(config)
    max_bytes = conf.get("max_mb", 30) * 1024 * 1024
    index = {"built_at": 0, "files": {}} if force else _load()
    old = index["files"]
    fresh, added, failed = {}, 0, 0

    for root in _roots(config):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in TEXT_EXT and ext not in DOC_EXT:
                    continue
                path = os.path.join(dirpath, fname)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                if stat.st_size > max_bytes:
                    continue

                key = path.replace("\\", "/")
                prev = old.get(key)
                # 수정시각·크기가 그대로면 다시 읽지 않습니다 — 이게 증분 색인의 전부입니다.
                if prev and prev.get("mtime") == stat.st_mtime and prev.get("size") == stat.st_size:
                    fresh[key] = prev
                    continue

                try:
                    text = _extract(path, ext) or ""
                except Exception:
                    failed += 1                  # 손상·암호걸림·희한한 인코딩 — 조용히 건너뜁니다
                    continue

                fresh[key] = {
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "name": fname,
                    "text": re.sub(r"\s+", " ", text)[:MAX_CHARS],
                }
                added += 1
                if added % 25 == 0:
                    notify(f"    [문서색인] {added}개 읽는 중...")

    index = {"built_at": time.time(), "files": fresh}
    _save(index)
    return added, len(fresh), failed


def _tokens(text):
    """검색어를 낱말로 쪼갭니다. 한글/한자 단일 문자 및 2글자 이상 단어를 포함합니다."""
    raw = [t.lower() for t in re.findall(r"[가-힣\u4e00-\u9fffA-Za-z0-9]+", text or "")]
    tokens = [t for t in raw if len(t) >= 2 or re.match(r"[가-힣\u4e00-\u9fff]", t)]
    return tokens or raw


def _snippet(text, tokens, width=110):
    """찾은 낱말 주변을 잘라 보여줍니다 — 이게 그 파일인지 사용자가 눈으로 가립니다."""
    low = text.lower()
    for t in tokens:
        at = low.find(t)
        if at >= 0:
            start = max(0, at - width // 2)
            return ("..." if start else "") + text[start:start + width].strip() + "..."
    return text[:width].strip() + "..."


def search(config, query, top_k=5):
    """낱말 점수로 파일을 찾습니다. 파일 이름에 든 낱말은 본문보다 훨씬 크게 칩니다."""
    tokens = _tokens(query)
    if not tokens:
        return []

    index = _load()
    hits = []
    for path, item in index.get("files", {}).items():
        name = item.get("name", "").lower()
        text = item.get("text", "")
        low = text.lower()

        score = 0
        matched = 0
        for t in tokens:
            in_name = t in name
            count = low.count(t)
            if in_name:
                score += 8          # 파일명에 있으면 거의 그 파일입니다
            if count:
                score += min(count, 4)      # 본문에 많이 나올수록 좋지만 상한을 둡니다
            if in_name or count:
                matched += 1

        if not matched:
            continue
        # 검색어의 낱말을 골고루 담은 파일을 앞으로. ('계약서 2025' 둘 다 든 파일 > 하나만 든 파일)
        score *= (1 + matched / len(tokens))
        hits.append((score, path, item, _snippet(text, tokens)))

    hits.sort(key=lambda h: -h[0])
    out = []
    for score, path, item, snip in hits[:top_k]:
        out.append({
            "path": path,
            "name": item.get("name", ""),
            "when": time.strftime("%Y-%m-%d", time.localtime(item.get("mtime", 0))),
            "score": round(score, 1),
            "snippet": snip,
        })
    return out


def stale(config, hours=24):
    """색인이 없거나 오래됐는가."""
    index = _load()
    if not index.get("files"):
        return True
    return (time.time() - index.get("built_at", 0)) > hours * 3600
