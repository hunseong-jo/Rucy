# -*- coding: utf-8 -*-
"""
기억 검색 (RAG)

기억이 쌓이면 전부 프롬프트에 밀어넣을 수 없습니다.
질문과 '의미가 가까운' 기억만 골라내기 위해 임베딩 모델을 씁니다.

임베딩 = 문장을 숫자 벡터로 바꾼 것. 뜻이 비슷하면 벡터 방향도 비슷해집니다.
그래서 '샐러드팜 뭐로 만들지?' 와 '유니티로 게임 제작 중' 이 단어가 하나도 안 겹쳐도 연결됩니다.

Ollama가 꺼져 있으면 단어 겹침 방식으로 자동 강등됩니다. (비서는 절대 멈추지 않습니다)
"""
import hashlib
import json
import math
import os
import re
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
NOTES_FILE = os.path.join(MEMORY_DIR, "notes.md")
INDEX_FILE = os.path.join(MEMORY_DIR, "index.json")  # 임베딩 캐시 (같은 문장을 다시 계산하지 않음)

EMBED_URL = "http://localhost:11434/api/embed"


def _config(cfg, key, default):
    return cfg.get(key, default) if cfg else default


# ── 기억 읽기 ─────────────────────────────────────────────────────
def load_notes():
    """notes.md 의 '- 내용  (날짜)' 줄들을 리스트로."""
    if not os.path.exists(NOTES_FILE):
        return []
    notes = []
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("- "):
                notes.append(line[2:].strip())
    return notes


# ── 임베딩 ────────────────────────────────────────────────────────
def _embed(texts, model, retries=2):
    # keep_alive: Ollama는 기본 5분만 지나면 모델을 메모리에서 내립니다.
    # bge-m3는 다시 올리는 데 20초 넘게 걸려서(실측), 오랜만에 던진 질문 하나가
    # 그대로 20초를 잡아먹습니다. 붙잡아 두면 0.3초대로 떨어집니다.
    body = json.dumps({"model": model, "input": texts, "keep_alive": "1h"}).encode("utf-8")

    # 모델을 올리는 중이면 Ollama가 요청을 흘립니다. 여기서 포기하면 호출한 쪽은
    # 단어겹침으로 강등되어 엉뚱한 근거를 물어옵니다 — 잠깐 쉬었다 다시 묻는 편이 낫습니다.
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                EMBED_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))["embeddings"]
        except Exception as e:
            last = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise last


def _key(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _load_index():
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


def _save_index(index):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f)


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


# ── 단어 겹침 폴백 (임베딩 모델이 없을 때) ──────────────────────────
def _keyword_scores(query, notes):
    words = set(re.findall(r"[가-힣A-Za-z0-9]+", query.lower()))
    scores = []
    for note in notes:
        nw = set(re.findall(r"[가-힣A-Za-z0-9]+", note.lower()))
        overlap = len(words & nw)
        scores.append(overlap / len(words) if words else 0.0)
    return scores


# ── 검색 ──────────────────────────────────────────────────────────
def search(query, config=None):
    """질문과 관련된 기억만 돌려줍니다. (본문, 사용한_방식)"""
    picked, method, _best = search_scored(query, config)
    return "\n".join("- " + n for n in picked), method


def search_scored(query, config=None):
    """
    search()와 같지만 고른 기억을 리스트로, 그리고 1등 유사도까지 함께 돌려줍니다.
    호출한 쪽에서 "이 검색을 믿어도 되는가"를 판단할 수 있어야 하기 때문입니다.
    돌려주는 값: ([기억, ...], 사용한_방식, 1등_유사도)
    """
    notes = load_notes()
    if not notes:
        return [], "기억 없음", 0.0

    top_k = _config(config, "memory_top_k", 4)
    always_all = _config(config, "memory_always_all_under", 8)
    model = _config(config, "embed_model", "bge-m3")

    # 기억이 얼마 없으면 굳이 검색하지 않고 전부 넣는 게 더 정확합니다.
    if len(notes) <= always_all:
        return notes, f"전체({len(notes)}개)", 1.0

    try:
        index = _load_index()
        missing = [n for n in notes if _key(n) not in index]
        if missing:
            for note, vec in zip(missing, _embed(missing, model)):
                index[_key(note)] = vec
        # forget으로 지운 문장의 벡터는 아무도 안 걷어가서 캐시에 계속 쌓입니다 —
        # 지금 노트에 없는 키는 여기서 털어냅니다(지우고 쓰기를 반복해도 캐시가 안 붇게).
        keep = {_key(n) for n in notes}
        stale = [k for k in index if k not in keep]
        for k in stale:
            del index[k]
        if missing or stale:
            _save_index(index)

        qvec = _embed([query], model)[0]
        scored = [(_cosine(qvec, index[_key(n)]), n) for n in notes]
        method = f"임베딩({model})"
    except Exception:
        # Ollama가 꺼져 있어도 비서는 계속 돌아가야 합니다.
        scored = list(zip(_keyword_scores(query, notes), notes))
        method = "단어겹침(임베딩 모델 없음)"

    scored.sort(key=lambda x: x[0], reverse=True)

    # 관련 있는 기억은 0.52~0.57, 무관한 기억도 0.40쯤 나옵니다(bge-m3 실측).
    # 그래서 절대 기준선 하나로는 잘 안 잘립니다. 1등 점수 대비 상대 기준을 같이 씁니다.
    floor = _config(config, "memory_min_score", 0.45)
    ratio = _config(config, "memory_relative_ratio", 0.85)
    if method.startswith("단어겹침"):
        floor, ratio = 0.15, 0.5   # 폴백 방식은 점수 분포가 다릅니다

    best = scored[0][0]
    cutoff = max(floor, best * ratio)
    picked = [n for score, n in scored[:top_k] if score >= cutoff]

    if not picked:
        return [], method + " · 관련 기억 없음", best
    return picked, f"{method} · {len(picked)}/{len(notes)}개 (최고 {best:.2f})", best


def invalidate():
    """새 기억이 추가되면 다음 검색 때 다시 임베딩하도록 합니다."""
    # 인덱스는 문장 해시 기준이라 새 문장은 자동으로 계산됩니다. 지울 필요 없음.
    pass
