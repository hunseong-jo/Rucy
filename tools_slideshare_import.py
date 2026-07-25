# -*- coding: utf-8 -*-
"""
슬라이드셰어 → 지식 창고(.md) 반입기.

공개된 강의 슬라이드를 루시가 찾아 읽을 수 있게 knowledge/ 에 .md 로 떨어뜨립니다.
개인 학습·개인 비서 참고용 사본이므로, 문서 머리에 **출처와 저자**를 반드시 적습니다.

왜 OCR이 필요 없는가:
  슬라이드셰어는 슬라이드 이미지 밑에 텍스트 전사(transcript)를 같이 싣습니다.
  그게 페이지 HTML의 <script id="__NEXT_DATA__"> JSON 안
  props.pageProps.slideshow.transcript 에 슬라이드 1장당 1개씩 들어 있습니다.
  이미지를 읽을 필요 없이 이 배열만 꺼내면 됩니다.

pypdf 조차 안 씁니다 — 표준 라이브러리(urllib+json+re)만으로 됩니다.

  미리보기:  python tools_slideshare_import.py --dry <URL>
  실제 반입:  python tools_slideshare_import.py <URL>
  이름 지정:  python tools_slideshare_import.py <URL> --name gamedesign_kay
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")

# 슬라이드셰어는 UA 없는 요청을 막습니다. (Groq와 같은 함정)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(html):
    """페이지에서 제목·저자·슬라이드 텍스트를 뽑습니다."""
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit("트랜스크립트를 못 찾았습니다. 슬라이드셰어 페이지 구조가 바뀌었을 수 있습니다.")

    show = json.loads(m.group(1))["props"]["pageProps"]["slideshow"]
    user = show.get("user") or {}
    return {
        "title": show.get("title", "제목 없음"),
        "author": user.get("name") or user.get("login") or "미상",
        "total": show.get("totalSlides") or len(show.get("transcript", [])),
        "slides": [str(t).strip() for t in show.get("transcript", [])],
    }


def _slug(title):
    """파일명으로 쓸 영문 슬러그. 한글 제목이면 못 만드므로 호출부에서 --name 을 씁니다."""
    s = re.sub(r"[^\w가-힣]+", "_", title).strip("_").lower()
    return s[:40] or "slideshare"


def build_doc(info, url):
    """
    빈 줄로 문단을 갈라 둡니다 — knowledge.py 의 _chunks_of() 가
    빈 줄 단위로 조각내 임베딩하기 때문입니다. 조각 하나만 검색에 걸려도
    몇 번째 슬라이드인지 알 수 있도록 머리에 슬라이드 번호를 박습니다.
    """
    head = (
        f"# {info['title']}\n\n"
        f"저자: {info['author']} · 슬라이드 {info['total']}장\n"
        f"출처: {url}\n"
        f"(공개 자료의 개인 학습용 사본. 인용할 때는 저자와 출처를 밝힐 것.)\n"
    )

    body, empty = [], 0
    for i, text in enumerate(info["slides"], 1):
        if len(text) < 10:          # 표지·간지처럼 글자가 없는 장
            empty += 1
            continue
        body.append(f"### p{i}\n{text}")

    return head + "\n" + "\n\n".join(body) + "\n", len(body), empty


def main():
    dry = "--dry" in sys.argv
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]

    name = None
    if "--name" in sys.argv:
        name = sys.argv[sys.argv.index("--name") + 1]
        argv = [a for a in argv if a != name]

    if not argv:
        print(__doc__)
        return
    url = argv[0]

    info = parse(fetch(url))
    doc, kept, empty = build_doc(info, url)

    stem = name or _slug(info["title"])
    out = os.path.join(KNOWLEDGE_DIR, stem + ".md")

    print(f"제목 : {info['title']}")
    print(f"저자 : {info['author']}")
    print(f"슬라이드: {info['total']}장 → 남김 {kept} · 버림(빈 장) {empty}")
    print(f"분량 : {len(doc):,}자")
    print(f"출력 : {out}")

    if dry:
        print("\n=== 미리보기 (파일을 쓰지 않습니다) ===")
        print(doc[:600] + "\n...")
        return

    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print("\n반입 완료. 임베딩을 미리 채우려면: python tools_reindex.py")


if __name__ == "__main__":
    main()
