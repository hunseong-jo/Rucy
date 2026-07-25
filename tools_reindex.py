# -*- coding: utf-8 -*-
"""
지식 창고 임베딩 인덱스를 미리 만들어 둡니다.

없어도 루시는 돌아갑니다 — 다만 첫 질문 때 전부 임베딩하느라 한참 멈춥니다.
새 문서를 반입한 뒤 한 번 돌려 두면 그 지연이 사라집니다.

knowledge.search() 에 맡기지 않고 여기서 직접 배치를 돌리는 이유:
  search() 는 임베딩이 실패하면 조용히 단어겹침으로 강등됩니다(그게 옳습니다, 비서는
  멈추면 안 되니까). 하지만 인덱스를 만드는 도중에 그러면 아무 말 없이 아무것도
  안 만들어집니다. 여기서는 진행 상황이 보여야 하고, 실패하면 시끄러워야 합니다.

  python tools_reindex.py
"""
import io
import json
import os
import sys
import time

import knowledge
import memory_search

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

BATCH = 32


def main():
    config = {}
    cfg_path = os.path.join(knowledge.BASE_DIR, "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    model = config.get("embed_model", "bge-m3")

    chunks = knowledge.load_chunks()
    texts = [f"{t}: {b}" for t, b in chunks]
    print(f"조각 {len(texts)}개 · 모델 {model}")

    index = {}
    if os.path.exists(knowledge.INDEX_FILE):
        with open(knowledge.INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
        print(f"기존 캐시 {len(index)}개 재사용")

    missing = [t for t in texts if knowledge._key(t) not in index]
    if not missing:
        print("이미 전부 임베딩되어 있습니다.")
        return

    print(f"새로 임베딩할 조각 {len(missing)}개\n")
    t0 = time.time()
    for i in range(0, len(missing), BATCH):
        batch = missing[i:i + BATCH]
        vecs = memory_search._embed(batch, model)     # 실패하면 여기서 시끄럽게 죽습니다
        for text, vec in zip(batch, vecs):
            index[knowledge._key(text)] = vec

        done = min(i + BATCH, len(missing))
        rate = done / max(time.time() - t0, 0.01)
        eta = (len(missing) - done) / rate if rate else 0
        print(f"  {done:>4}/{len(missing)}  ({done * 100 // len(missing):>3}%)  "
              f"{rate:.1f}조각/초  남은시간 {eta:.0f}초")

    # 사라진 조각의 벡터는 자리만 차지합니다. 쓰는 김에 치웁니다.
    live = {knowledge._key(t) for t in texts}
    index = {k: v for k, v in index.items() if k in live}

    with open(knowledge.INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f)

    size = os.path.getsize(knowledge.INDEX_FILE) / 1024 / 1024
    print(f"\n완료 · {time.time() - t0:.0f}초 · 벡터 {len(index)}개 · index.json {size:.1f}MB")


if __name__ == "__main__":
    main()
