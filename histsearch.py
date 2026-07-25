# -*- coding: utf-8 -*-
"""루시 자신의 대화 기록(memory/history/날짜.md) 의미 검색.

"지난번에 내가 뭐라 했지?"는 낱말이 그대로 겹치는 일이 드뭅니다 — 사용자는 '버즈 마이크
문제'라고 묻는데 기록에는 '음량 문턱'이라고 적혀 있는 식입니다. 기억(notes.md)·지식
창고는 임베딩 검색인데 자기 대화만 낱말 일치였던 구멍을 메웁니다.

통 분리 원칙 유지: notes.md=걸러 담은 사실 / 여기는 **흘러간 대화 원문**. 색인도
따로(memory/history_index.json) — 대화는 매일 자라므로 파일 단위 증분(mtime+size)이고,
오늘 파일 하나만 다시 임베딩하면 됩니다. 임베딩은 memory_search._embed 재사용(Ollama).
Ollama가 꺼져 있으면 tools.search_my_history가 원래의 낱말 검색으로 강등됩니다.
"""
import datetime
import json
import os
import re

import memory_search

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HIST_DIR = os.path.join(BASE_DIR, "memory", "history")
INDEX_FILE = os.path.join(BASE_DIR, "memory", "history_index.json")

MAX_DAYS = 120          # 이보다 오래된 날은 색인에서 내림 — 색인 파일이 한없이 크지 않게
CHUNK_CHARS = 400       # 턴 덩어리를 이 크기로 뭉침(너무 잘게 쪼개면 벡터 수만 늘어남)


def _load():
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"files": {}}


def _save(index):
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    tmp = INDEX_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    os.replace(tmp, INDEX_FILE)          # 쓰다 죽어도 원본이 남게

def _chunks(text):
    """'**나** (14:03)\\n내용' 턴 덩어리들을 ~CHUNK_CHARS로 뭉칩니다. 덩어리째라야 맥락이 삽니다."""
    out, buf = [], ""
    for turn in text.split("\n\n"):
        t = " ".join(turn.split())
        if len(t) < 8:
            continue
        if buf and len(buf) + len(t) > CHUNK_CHARS:
            out.append(buf)
            buf = t
        else:
            buf = (buf + " ▸ " + t) if buf else t
    if buf:
        out.append(buf)
    return out


def build(config, notify=print):
    """바뀐 날짜 파일만 다시 임베딩합니다. (다시 읽은 파일 수, 전체 덩어리 수)"""
    model = (config or {}).get("embed_model", "bge-m3")
    old = _load().get("files", {})
    files = {}
    refreshed = 0
    today = datetime.date.today()

    if not os.path.isdir(HIST_DIR):
        return 0, 0
    for name in sorted(os.listdir(HIST_DIR)):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.md", name)
        if not m:
            continue
        try:
            if (today - datetime.date.fromisoformat(m.group(1))).days > MAX_DAYS:
                continue
        except ValueError:
            continue
        path = os.path.join(HIST_DIR, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        prev = old.get(name)
        if prev and prev.get("mtime") == st.st_mtime and prev.get("size") == st.st_size:
            files[name] = prev
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            chunks = _chunks(f.read())
        if not chunks:
            continue
        vecs = memory_search._embed(chunks, model)   # Ollama 꺼짐 → 예외 → 호출자가 강등
        files[name] = {"mtime": st.st_mtime, "size": st.st_size,
                       "chunks": [{"t": c, "v": [round(x, 5) for x in v]}
                                  for c, v in zip(chunks, vecs)]}
        refreshed += 1
        if refreshed % 5 == 0:
            notify(f"    [대화색인] {refreshed}일치 임베딩...")

    _save({"files": files})
    return refreshed, sum(len(f["chunks"]) for f in files.values())


def search(config, query, top_k=6, min_score=0.45):
    """질문과 의미가 가까운 대화 덩어리. [(점수, 'YYYY-MM-DD', 덩어리)] — 높은 점수부터.

    색인이 낡았으면(오늘 파일이 자랐으면) 그 파일만 몇 초 증분하고 찾습니다.
    Ollama가 꺼져 있으면 예외를 그대로 올립니다 — 호출자(tools)가 낱말 검색으로 강등.
    """
    build(config, notify=lambda *a: None)
    model = (config or {}).get("embed_model", "bge-m3")
    qv = memory_search._embed([query], model)[0]

    scored = []
    for name, entry in _load().get("files", {}).items():
        day = name[:-3]
        for ch in entry.get("chunks", []):
            s = memory_search._cosine(qv, ch["v"])
            if s >= min_score:
                scored.append((s, day, ch["t"]))
    scored.sort(key=lambda x: -x[0])
    return scored[:top_k]
