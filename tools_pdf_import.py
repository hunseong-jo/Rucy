# -*- coding: utf-8 -*-
"""
강의 PDF → 지식 창고(.md) 변환기.

루시 본체가 아니라 **1회성 반입 도구**입니다. 그래서 여기서만 pypdf를 씁니다
(pip install pypdf). 루시 런타임은 여전히 표준 라이브러리만 씁니다.

만들어진 .md는 knowledge/ 에 떨어지고, knowledge.py 의 load_chunks() 가
폴더 안의 모든 .md를 자동으로 읽으므로 코드 수정 없이 검색 대상이 됩니다.

운영성 슬라이드(과제·공지·토론질문·예고·Q&A)는 시험 공부에 쓸 지식이 아니라
검색을 방해하므로 걷어냅니다. 판단은 **페이지 제목**으로만 합니다 —
본문 단어로 거르면 "마케팅 퍼널 구조"가 '평가'라는 낱말 하나 때문에 날아갑니다.

  미리보기:  python tools_pdf_import.py --dry
  실제 반입:  python tools_pdf_import.py
"""
import io
import os
import re
import sys
from collections import Counter

from pypdf import PdfReader

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
DEFAULT_SRC = r"C:\Users\user\Downloads\마케팅교재"

# ── 버릴 페이지 ────────────────────────────────────────────────────
# 수업 운영에 관한 것들. 내용이 아니라 공지입니다.
DROP_ADMIN = [
    r"과제\s*(안내|제출|업데이트)", r"이번\s*주차?\s*과제", r"\d+\s*주차\s*과제",
    r"^Part\s*\d+\s*\|?\s*(이번주차\s*)?과제",
    r"토론\s*질문", r"모둠\s*토론", r"^토론\s*[—\-:]",
    r"다음\s*주\s*예고", r"^Q\s*&?\s*A\b",
    r"노션\s*활용", r"노션\s*포트폴리오", r"Notion\s*기반",
    r"중요\s*공지", r"(보충|추천)\s*영상", r"영상\s*자료",
    r"Table\s*of\s*Contents", r"T\s*a\s*b\s*l\s*e", r"^목\s*차",
    r"평가\s*기준", r"평가\s*가이드", r"수업\s*운영", r"강의\s*목표",
    r"(중간|기말)고사", r"발표\s*평가\s*안내", r"오늘\s*수업\s*흐름",
]
# 매주 되풀이되는 요약. (15주차 종합정리는 아래 화이트리스트로 살립니다)
DROP_SUMMARY = [
    r"핵심\s*정리", r"핵심\s*키워드\s*정리", r"지난\s*시간\s*복습",
    r"Key\s*Takeaways", r"\d+\s*주차\s*\|?\s*핵심",
]
# 수업 중 활동 지시. 계산법·템플릿 슬라이드는 남깁니다.
DROP_ACTIVITY = [r"모둠\s*활동", r"\(\s*\d+\s*분\s*\)"]

# 한 학기를 관통하는 지도 — 요약이지만 시험에 가장 값나갑니다.
KEEP_SUMMARY = [r"15\s*주", r"한\s*학기"]


def _match(title, patterns):
    return any(re.search(p, title, re.I) for p in patterns)


def _drop_reason(title):
    if _match(title, DROP_ADMIN):
        return "운영/공지"
    if _match(title, DROP_ACTIVITY):
        return "활동지시"
    if _match(title, DROP_SUMMARY) and not _match(title, KEEP_SUMMARY):
        return "주차요약"
    return None


def _week_of(filename):
    m = re.search(r"(\d+)\s*주차", filename)
    return int(m.group(1)) if m else None


def _subject_of(cover_text, label):
    """
    표지에서 그 주의 제목을 뽑습니다. 제목이 두 줄로 쪼개져 있는 경우가 많아
    ("디지털 마케팅의" / "장점과 성과 측정") 이어 붙입니다.
    과목명·대학명·부제 나열(· 로 이어진 줄)을 만나면 멈춥니다.
    """
    lines = [l.strip() for l in cover_text.splitlines() if l.strip()]
    parts = []
    for line in lines[1:]:                       # 첫 줄은 과목명("디지털 마케팅 트렌드")
        if re.search(r"University|Prof\.|학과", line):
            break
        if line.count("·") >= 2 or len(line) > 50:   # 부제 나열 줄
            break
        if re.fullmatch(r"\d+\s*주차", line):
            continue
        parts.append(re.sub(r"^\d+\s*주차\s*[:·\-]?\s*", "", line))
        if len(parts) == 3:
            break
    return " ".join(parts).strip() or label


def _boilerplate(pages, min_repeat=0.5):
    """쪽마다 되풀이되는 줄(대학명·교수명)은 내용이 아니라 장식입니다."""
    counter = Counter()
    for text in pages:
        for line in set(l.strip() for l in text.splitlines() if l.strip()):
            counter[line] += 1
    threshold = max(2, int(len(pages) * min_repeat))
    return {line for line, n in counter.items() if n >= threshold}


def _clean(text, junk):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line in junk:
            continue
        if re.fullmatch(r"[\d\s/\-.]+", line):      # 외톨이 쪽번호
            continue
        out.append(line)
    return "\n".join(out)


def convert(pdf_path, dry=False):
    name = os.path.basename(pdf_path)
    week = _week_of(name)
    label = f"{week}주차" if week else os.path.splitext(name)[0]
    reader = PdfReader(pdf_path)

    raw = [(p.extract_text() or "") for p in reader.pages]
    junk = _boilerplate(raw)

    subject = _subject_of(raw[0] if raw else "", label)

    body, dropped = [], []
    for i, text in enumerate(raw):
        cleaned = _clean(text, junk)
        title = cleaned.splitlines()[0].strip() if cleaned else ""

        if len(cleaned) < 40:                       # 내용 없는 Part 표지
            dropped.append((i + 1, title or "(빈 쪽)", "표지/빈쪽"))
            continue
        reason = _drop_reason(title)
        if reason:
            dropped.append((i + 1, title, reason))
            continue

        # 빈 줄로 갈라 두면 knowledge.py 가 문단 단위로 조각냅니다.
        # 머리에 주차를 박아 두어야 조각만 떼어 봐도 몇 주차인지 압니다.
        body.append(f"### [{label}] p{i + 1}\n{cleaned}")

    doc = (f"# 디지털마케팅 트렌드 — {subject}\n\n"
           f"수업: 디지털마케팅 트렌드 ({label}) · 유한대 IT융합비즈니스\n\n"
           + "\n\n".join(body) + "\n")

    stem = f"lecture_마케팅_{week:02d}주차" if week else f"lecture_마케팅_{os.path.splitext(name)[0]}"
    out_path = os.path.join(KNOWLEDGE_DIR, stem + ".md")
    if not dry:
        os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(doc)

    return {"out": out_path, "label": label, "pages": len(raw),
            "kept": len(body), "dropped": dropped, "chars": len(doc)}


def main():
    dry = "--dry" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = args[0] if args else DEFAULT_SRC

    pdfs = [os.path.join(src, n) for n in os.listdir(src) if n.lower().endswith(".pdf")]
    if not pdfs:
        print(f"PDF가 없습니다: {src}")
        return
    pdfs.sort(key=lambda p: (_week_of(os.path.basename(p)) or 99))

    if dry:
        print("=== 미리보기 (파일을 쓰지 않습니다) ===\n")

    kept = drop = chars = 0
    for pdf in pdfs:
        r = convert(pdf, dry=dry)
        kept += r["kept"]
        drop += len(r["dropped"])
        chars += r["chars"]
        print(f"[{r['label']}] {r['pages']}쪽 → 남김 {r['kept']} · 버림 {len(r['dropped'])}")
        for pno, title, reason in r["dropped"]:
            print(f"      ✗ p{pno:<3} {title[:46]:<48} ({reason})")

    print(f"\n총 {len(pdfs)}개 파일 · 남긴 쪽 {kept} · 버린 쪽 {drop} · {chars:,}자")

    if not dry:
        # 임베딩 캐시는 그대로 둡니다. 새로 들어온 조각만 다음 검색 때 채워집니다.
        # 미리 채우려면: python tools_reindex.py
        print(f"반입 완료 → {KNOWLEDGE_DIR}")


if __name__ == "__main__":
    main()
