# -*- coding: utf-8 -*-
"""
지식 창고 — 클로드가 세션마다 정제해 적어둔 노트를 루시가 찾아 읽습니다.

왜 notes.md 와 나눠 두는가:
  notes.md = "사용자는 홍차를 좋아함" 같은 **개인에 관한 사실**. 매 질문마다 자동으로 딸려갑니다.
  knowledge/ = "premium9 아트는 3단계 토끼→기린으로 리디자인" 같은 **프로젝트 지식**.
               양이 많고 대부분의 질문과 무관하므로, 필요할 때 도구로 찾아 읽습니다.
  섞으면 둘 다 흐려집니다. 그래서 통을 따로 둡니다.

원본(.claude/projects/.../memory)은 클로드가 계속 갱신하므로, sync()로 복사해 옵니다.
복사본을 두는 이유: 이 폴더만 들고 다른 PC로 옮겨도 지식이 따라가야 하기 때문입니다.
"""
import hashlib
import json
import os
import re
import shutil

import memory_search

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
INDEX_FILE = os.path.join(KNOWLEDGE_DIR, "index.json")

# 클로드 코드의 메모리 폴더(MEMORY.md가 사는 곳). 폴더명은 홈 경로를 인코딩한 것이라
# 현재 홈에서 계산합니다 — 다른 PC/계정으로 옮겨도 맞게(없으면 sync가 조용히 건너뜀).
_HOME = os.path.expanduser("~")
DEFAULT_SOURCE = os.path.join(
    _HOME, ".claude", "projects",
    _HOME.replace(":", "-").replace("\\", "-").replace("/", "-"), "memory")


def sync(source=None):
    """클로드의 메모리 폴더에서 .md 파일을 복사해 옵니다. (복사한 개수, 폴더)"""
    source = source or DEFAULT_SOURCE
    if not os.path.isdir(source):
        return 0, f"원본 폴더가 없습니다: {source}"

    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    count = 0
    for name in os.listdir(source):
        if name.lower().endswith(".md"):
            shutil.copyfile(os.path.join(source, name), os.path.join(KNOWLEDGE_DIR, name))
            count += 1

    # 임베딩 캐시는 건드리지 않습니다.
    # _key() 가 조각의 텍스트 해시라, 안 바뀐 조각은 캐시가 그대로 맞고
    # 바뀐 조각만 다시 임베딩됩니다. 통째로 버리면 노트 하나 고쳤다고
    # 강의 자료 수백 조각을 다시 임베딩하게 됩니다. 죽은 항목은 search() 가 치웁니다.
    return count, KNOWLEDGE_DIR


# ── 조각내기 ──────────────────────────────────────────────────────
def _chunks_of(path, max_chars=700):
    """
    문서를 통째로 임베딩하면 한 벡터에 온갖 주제가 뭉개집니다.
    빈 줄 단위로 묶되 너무 길면 끊어서, 문단 하나가 검색 단위가 되게 합니다.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    title = os.path.splitext(os.path.basename(path))[0]
    # 프론트매터(--- ... ---)는 검색에 도움이 안 되니 걷어냅니다.
    text = re.sub(r"^---.*?---\s*", "", text, flags=re.S)

    out, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) > max_chars and buf:
            out.append((title, buf.strip()))
            buf = ""
        buf += para + "\n"
    if buf.strip():
        out.append((title, buf.strip()))
    return out


def load_chunks():
    if not os.path.isdir(KNOWLEDGE_DIR):
        return []
    chunks = []
    for name in sorted(os.listdir(KNOWLEDGE_DIR)):
        if name.lower().endswith(".md"):
            chunks += _chunks_of(os.path.join(KNOWLEDGE_DIR, name))
    return chunks


def _key(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


# ── 검색 ──────────────────────────────────────────────────────────
def search(query, config=None, top_k=5):
    """질문과 가까운 노트 조각을 돌려줍니다. (본문, 방식)"""
    chunks = load_chunks()
    if not chunks:
        return "", "지식 창고가 비어 있음 (sync 필요)"

    model = (config or {}).get("embed_model", "bge-m3")
    texts = [f"{t}: {b}" for t, b in chunks]

    try:
        index = {}
        if os.path.exists(INDEX_FILE):
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                index = json.load(f)

        missing = [t for t in texts if _key(t) not in index]
        if missing:
            # 한 번에 다 보내면 Ollama가 버거워하므로 나눠 보냅니다.
            for i in range(0, len(missing), 32):
                batch = missing[i:i + 32]
                for text, vec in zip(batch, memory_search._embed(batch, model)):
                    index[_key(text)] = vec

            # 사라진 조각의 벡터는 자리만 차지합니다. 쓰는 김에 치웁니다.
            live = {_key(t) for t in texts}
            index = {k: v for k, v in index.items() if k in live}

            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(index, f)

        qvec = memory_search._embed([query], model)[0]
        scored = [(memory_search._cosine(qvec, index[_key(t)]), i) for i, t in enumerate(texts)]
        method = f"임베딩({model})"
    except Exception as e:
        # Ollama가 없어도 검색은 되어야 합니다(품질만 떨어짐).
        # 다만 말없이 강등되면 엉뚱한 근거로 답하고도 아무도 눈치채지 못합니다.
        # 왜 떨어졌는지를 방식에 적어 둡니다 — 호출한 쪽이 화면에 그대로 보여 줍니다.
        scores = memory_search._keyword_scores(query, texts)
        scored = [(s, i) for i, s in enumerate(scores)]
        method = f"단어겹침(임베딩 실패: {type(e).__name__})"

    scored.sort(key=lambda x: -x[0])
    picked = [(s, chunks[i]) for s, i in scored[:top_k] if s > 0.30]
    if not picked:
        return "", method + " · 관련 노트 없음"

    body = "\n\n".join(f"[{title}] (유사도 {s:.2f})\n{text}" for s, (title, text) in picked)
    return body, f"{method} · {len(picked)}/{len(chunks)}조각"
