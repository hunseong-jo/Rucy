# -*- coding: utf-8 -*-
"""
문서 만들기 — 워드(.docx)·파워포인트(.pptx)·엑셀(.xlsx)을 **처음부터** 씁니다.

루시는 이미 오피스 문서를 읽을 줄 압니다(tools.read_document). 읽기가 zipfile+xml만으로 됐던 것처럼
쓰기도 똑같습니다: 오피스 파일은 그냥 **정해진 이름의 XML들을 담은 zip**입니다.
그래서 python-docx·python-pptx·openpyxl을 깔지 않습니다("pip 없음" 원칙 유지).
오피스가 깔려 있지 않은 PC에서도, 인터넷이 끊겨도 작동합니다.

모델에게는 마크다운을 쓰게 합니다. 언어모델이 가장 잘 쓰는 형식이고,
'문단'·'제목'·'글머리표'라는 개념이 세 형식에 공통으로 있기 때문입니다.

  # 제목        → 워드: 제목1 / PPT: 새 슬라이드의 제목
  ## 소제목     → 워드: 제목2 / PPT: 슬라이드 안의 굵은 줄
  - 글머리표    → 워드·PPT: 글머리표
  노트: ...     → PPT: 발표자 노트 (사용자가 기획서를 그렇게 씁니다)
  그냥 문장     → 문단

엑셀만 다릅니다: 표는 마크다운 표(| a | b |) 또는 CSV로 받습니다.
"""
import os
import re
import zipfile

# ── 아주 작은 XML 도우미 ──────────────────────────────────────────
def esc(text):
    """XML에 넣을 수 있게 다듬습니다. 이걸 빠뜨리면 '&'나 '<' 하나에 문서 전체가 안 열립니다."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def _zip(path, parts):
    """
    parts: {zip 안의 경로: 내용(str 또는 bytes)} → 파일 하나로 묶습니다.
    (그림은 bytes로 들어옵니다 — writestr이 둘 다 받습니다)

    ⚠️ [Content_Types].xml은 **반드시 zip의 첫 항목**이어야 합니다. 규격상 순서는 자유지만
       파워포인트는 이게 뒤에 있으면 "파일이 손상되었습니다"로 거부합니다(실제로 겪음 —
       워드·엑셀은 뒤에 있어도 잘 열려서, 파워포인트만 안 열리는 이유를 찾기 어려웠습니다).
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    first = "[Content_Types].xml"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(first, parts[first])
        for name, data in parts.items():
            if name != first:
                z.writestr(name, data)
    return path


# ── 마크다운 → 구조 ───────────────────────────────────────────────
def parse_blocks(text):
    """
    줄들을 (종류, 내용)으로 나눕니다. 종류: h1 · h2 · bullet · note · image · table · quote · text
    문서 형식들이 이 결과를 나눠 씁니다(같은 글을 워드로도 PPT로도 한글로도 뽑을 수 있게).
    """
    blocks = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        # 그림: 마크다운 ![설명](경로) 또는 '그림: 경로' — 둘 다 받습니다(세션65).
        m_img = (re.match(r"^!\[[^\]]*\]\(([^)]+)\)$", stripped)
                 or re.match(r"^(?:그림|이미지|사진|image)\s*[:：]\s*(.+)$", stripped, re.I))
        if m_img:
            blocks.append(("image", m_img.group(1).strip().strip("\"'")))
            continue
        if stripped.startswith("|") and stripped.count("|") >= 2:
            if set(stripped) <= set("|-: "):
                continue                             # 표의 구분선(|---|---|)은 자료가 아닙니다
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if blocks and blocks[-1][0] == "table":
                blocks[-1][1].append(cells)          # 붙은 표 줄은 한 표로 묶습니다
            else:
                blocks.append(("table", [cells]))
        elif stripped in ("---", "***", "___"):      # 슬라이드 구분선
            blocks.append(("break", ""))
        elif stripped.startswith("### "):
            blocks.append(("h2", stripped[4:].strip()))
        elif stripped.startswith("## "):
            blocks.append(("h2", stripped[3:].strip()))
        elif stripped.startswith("# "):
            blocks.append(("h1", stripped[2:].strip()))
        elif re.match(r"^[-*•]\s+", stripped):
            blocks.append(("bullet", re.sub(r"^[-*•]\s+", "", stripped)))
        elif re.match(r"^\d+[.)]\s+", stripped):
            blocks.append(("bullet", re.sub(r"^\d+[.)]\s+", "", stripped)))
        elif re.match(r"^(노트|발표자\s*노트|notes?)\s*[:：]", stripped, re.I):
            blocks.append(("note", re.split(r"[:：]", stripped, 1)[1].strip()))
        elif stripped.startswith(">"):
            blocks.append(("quote", stripped.lstrip("> ").strip()))
        else:
            blocks.append(("text", stripped))
    return blocks


def _plain(text):
    """마크다운 강조 기호는 글자로 남으면 지저분합니다(**굵게** → 굵게)."""
    return re.sub(r"(\*\*|__|\*|`)", "", text)


# ══ 워드 (.docx) ═════════════════════════════════════════════════
_DOCX_CT = DECL + """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

_ROOT_RELS = DECL + """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{target}"/>
</Relationships>"""

_DOC_RELS = DECL + """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

# 제목1·제목2·글머리표·콜아웃(인용) 스타일을 정의합니다.
_DOCX_STYLES = DECL + """<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="맑은 고딕" w:eastAsia="맑은 고딕" w:hAnsi="맑은 고딕"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>
  <w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="56"/><w:color w:val="1F4E78"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
  <w:pPr><w:outlineLvl w:val="0"/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/><w:color w:val="1F4E78"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>
  <w:pPr><w:outlineLvl w:val="1"/><w:spacing w:before="180" w:after="80"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="2F5597"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>
  <w:pPr><w:ind w:left="720"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/>
  <w:pPr><w:pBorders><w:left w:val="single" w:sz="24" w:space="12" w:color="2F5597"/></w:pBorders>
  <w:shd w:val="clear" w:color="auto" w:fill="F2F4F8"/><w:ind w:left="400"/><w:spacing w:before="120" w:after="120"/></w:pPr>
  <w:rPr><w:i/><w:color w:val="333333"/></w:rPr></w:style>
</w:styles>"""


def _p(text, style=None, bullet=False, bold=False):
    ppr = ""
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    if bullet:
        ppr += '<w:ind w:left="720" w:hanging="360"/>'
        text = "• " + text
    ppr = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>'


_TBL_BORDERS = ("<w:tblBorders>"
                + "".join(f'<w:{side} w:val="single" w:sz="4" w:color="D3D3D3"/>'
                          for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
                + "</w:tblBorders>")


def _tbl(rows):
    """마크다운 표 → 워드 진짜 표. 첫 줄은 머리글이라 배경색(#2F5597)과 흰 글씨로 강조합니다."""
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/>{_TBL_BORDERS}</w:tblPr>']
    for r, cells in enumerate(rows):
        out.append("<w:tr>")
        for cell in cells:
            if r == 0:
                tcPr = '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="2F5597"/><w:tcW w:w="0" w:type="auto"/></w:tcPr>'
                cell_p = f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr><w:t xml:space="preserve">{esc(_plain(cell))}</w:t></w:r></w:p>'
            else:
                bg = ' w:fill="F9FAFC"' if r % 2 == 1 else ''
                tcPr = f'<w:tcPr><w:tcW w:w="0" w:type="auto"/>{"<w:shd w:val=\"clear\" w:color=\"auto\"" + bg + "/>" if bg else ""}</w:tcPr>'
                cell_p = _p(_plain(cell))
            out.append(f'<w:tc>{tcPr}{cell_p}</w:tc>')
        out.append("</w:tr>")
    out.append("</w:tbl><w:p/>")      # 표 뒤 빈 문단 — 표가 문서 끝이면 워드가 이걸 요구합니다
    return "".join(out)


def _docx_body(blocks):
    """블록들을 워드 본문 XML 조각으로. write_docx(새 문서)와 edit(덧붙이기)가 같이 씁니다."""
    body = []
    for kind, text in blocks:
        if kind == "table":
            body.append(_tbl(text))
            continue
        text = _plain(text)
        if kind == "break":
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        elif kind == "h1":
            body.append(_p(text, style="Heading1"))
        elif kind == "h2":
            body.append(_p(text, style="Heading2"))
        elif kind == "bullet":
            body.append(_p(text, style="ListParagraph", bullet=True))
        elif kind == "quote":
            body.append(_p(text, style="Quote"))
        elif kind == "note":
            body.append(_p("[노트] " + text))
        else:
            body.append(_p(text))
    return body


def write_docx(path, blocks, title=None):
    body = []
    if title:
        body.append(_p(title, style="Title"))
    body += _docx_body(blocks)

    document = (DECL +
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>" + "".join(body) +
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1418"/></w:sectPr>'
                "</w:body></w:document>")

    return _zip(path, {
        "[Content_Types].xml": _DOCX_CT,
        "_rels/.rels": _ROOT_RELS.format(target="word/document.xml"),
        "word/_rels/document.xml.rels": _DOC_RELS,
        "word/styles.xml": _DOCX_STYLES,
        "word/document.xml": document,
    })


# ══ 엑셀 (.xlsx) ═════════════════════════════════════════════════
_XLSX_CT = DECL + """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""

_XLSX_WB = DECL + """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="{name}" sheetId="1" r:id="rId1"/></sheets></workbook>"""

_XLSX_WB_RELS = DECL + """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""


def _colname(i):
    """0 → A, 26 → AA"""
    name = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        name = chr(65 + rem) + name
    return name


def parse_table(text):
    """마크다운 표(| a | b |)든 CSV든 줄 단위로 받아 2차원 목록으로."""
    rows = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if set(line) <= set("|-: "):          # 마크다운 표의 구분선(|---|---|)은 자료가 아닙니다
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
        elif "\t" in line:
            cells = [c.strip() for c in line.split("\t")]
        else:
            cells = [c.strip() for c in line.split(",")]
        rows.append([_plain(c) for c in cells])
    return rows


_NUM = re.compile(r"^-?\d+(\.\d+)?$")


def _col2idx(col_str):
    """'A' -> 0, 'Z' -> 25, 'AA' -> 26"""
    idx = 0
    for ch in col_str.upper():
        idx = idx * 26 + (ord(ch) - ord('A') + 1)
    return idx - 1


def _parse_num_val(text):
    """글자에서 숫자 값을 뽑아냅니다 (통화, 퍼센트, 천단위 콤마 포함)."""
    t = str(text).strip()
    if not t:
        return None
    if re.match(r"^-?\d+(\.\d+)?%$", t):
        return float(t[:-1]) / 100.0
    if re.match(r"^[\$₩]?\s*-?[\d,]+(\.\d+)?\s*(원|dollars?)?$", t, re.I) and any(ch in t for ch in ("$", "₩", "원")):
        clean_str = re.sub(r"[^\d.-]", "", t)
        try:
            return float(clean_str)
        except ValueError:
            return None
    clean_str = t.replace(",", "")
    if re.match(r"^-?\d+(\.\d+)?$", clean_str):
        try:
            return float(clean_str) if "." in clean_str else int(clean_str)
        except ValueError:
            return None
    return None


def eval_formula(text, rows):
    """=SUM(A2:A10) 수식을 읽어 rows 자료 범위에서 계산 결과를 만듭니다."""
    m = re.match(r"^=(SUM|AVERAGE|AVG|COUNT|MIN|MAX)\(\s*([A-Z]+)(\d+)\s*:\s*([A-Z]+)(\d+)\s*\)$", text.strip(), re.I)
    if not m:
        return None
    func = m.group(1).upper()
    c1, r1 = _col2idx(m.group(2)), int(m.group(3)) - 1
    c2, r2 = _col2idx(m.group(4)), int(m.group(5)) - 1

    vals = []
    for r in range(min(r1, r2), max(r1, r2) + 1):
        if r < len(rows):
            for c in range(min(c1, c2), max(c1, c2) + 1):
                if c < len(rows[r]):
                    v = _parse_num_val(rows[r][c])
                    if v is not None:
                        vals.append(v)
    if not vals:
        return 0
    if func == "SUM":
        res = sum(vals)
    elif func in ("AVERAGE", "AVG"):
        res = sum(vals) / len(vals)
    elif func == "COUNT":
        res = len(vals)
    elif func == "MIN":
        res = min(vals)
    elif func == "MAX":
        res = max(vals)
    else:
        return None
    return round(res, 4) if isinstance(res, float) else res


# 서식 사전(styles.xml). 번호로 셀에서 가리킵니다.
_XLSX_STYLES = DECL + """<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="4">
<numFmt numFmtId="164" formatCode="#,##0"/>
<numFmt numFmtId="165" formatCode="&#x20A9;#,##0;(&#x20A9;#,##0);&quot;-&quot;"/>
<numFmt numFmtId="166" formatCode="0.0%"/>
<numFmt numFmtId="167" formatCode="#,##0.00"/>
</numFmts>
<fonts count="2"><font><sz val="11"/><name val="맑은 고딕"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF2F5597"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFB0B8C4"/></left><right style="thin"><color rgb="FFB0B8C4"/></right>
<top style="thin"><color rgb="FFB0B8C4"/></top><bottom style="thin"><color rgb="FFB0B8C4"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="7">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
<xf numFmtId="166" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
<xf numFmtId="167" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
</cellXfs></styleSheet>"""

_S_NORMAL, _S_HEAD, _S_NUM, _S_CELL, _S_CURR, _S_PERCENT, _S_DECIMAL = 0, 1, 2, 3, 4, 5, 6


def _sheet_xml(rows, header=True):
    """표 하나를 워크시트 XML로. 머리행 자동 서식, 통화·퍼센트·천단위 자동 감지, 수식(=SUM, =AVERAGE) 평가."""
    ncol = max((len(r) for r in rows), default=1)
    out = []
    for r, cells in enumerate(rows, 1):
        cs = []
        for c, value in enumerate(cells):
            ref = f"{_colname(c)}{r}"
            text = str(value).strip()
            if header and r == 1:
                cs.append(f'<c r="{ref}" s="{_S_HEAD}" t="inlineStr">'
                          f'<is><t xml:space="preserve">{esc(text)}</t></is></c>')
            elif text.startswith("="):
                ev = eval_formula(text, rows)
                f_tag = f'<f>{esc(text[1:])}</f>'
                if ev is not None:
                    cs.append(f'<c r="{ref}" s="{_S_NUM if isinstance(ev, (int, float)) else _S_CELL}">{f_tag}<v>{esc(str(ev))}</v></c>')
                else:
                    cs.append(f'<c r="{ref}" s="{_S_CELL}">{f_tag}</c>')
            elif re.match(r"^-?\d+(\.\d+)?%$", text):
                p_val = float(text[:-1]) / 100.0
                cs.append(f'<c r="{ref}" s="{_S_PERCENT}"><v>{p_val}</v></c>')
            elif (re.match(r"^[\$₩]?\s*-?[\d,]+(\.\d+)?\s*(원|dollars?)?$", text, re.I)
                  and any(ch in text for ch in ("$", "₩", "원"))):
                c_val = re.sub(r"[^\d.-]", "", text)
                cs.append(f'<c r="{ref}" s="{_S_CURR}"><v>{esc(c_val)}</v></c>')
            elif re.match(r"^-?\d[\d,]*\.\d+$", text):
                d_val = text.replace(",", "")
                cs.append(f'<c r="{ref}" s="{_S_DECIMAL}"><v>{esc(d_val)}</v></c>')
            elif re.match(r"^-?\d[\d,]*$", text) and text.replace(",", "").lstrip("-").isdigit():
                i_val = text.replace(",", "")
                cs.append(f'<c r="{ref}" s="{_S_NUM}"><v>{esc(i_val)}</v></c>')
            else:
                cs.append(f'<c r="{ref}" s="{_S_CELL}" t="inlineStr">'
                          f'<is><t xml:space="preserve">{esc(text)}</t></is></c>')
        out.append(f'<row r="{r}">' + "".join(cs) + "</row>")

    # 열 너비 — 그 열에서 가장 긴 글자수에 맞춥니다(한글은 폭이 넓어 1.6배로 셉니다).
    cols = []
    for c in range(ncol):
        longest = 4
        for row in rows:
            if c < len(row):
                t = str(row[c])
                longest = max(longest, sum(1.6 if ord(ch) > 0x2000 else 1 for ch in t))
        cols.append(f'<col min="{c + 1}" max="{c + 1}" width="{min(round(longest + 3, 1), 60)}"'
                    ' customWidth="1"/>')

    freeze = ('<sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft"'
              ' state="frozen"/></sheetView>') if header and len(rows) > 1 else \
             '<sheetView workbookViewId="0"/>'

    return (DECL + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetViews>{freeze}</sheetViews>"
            f'<cols>{"".join(cols)}</cols>'
            "<sheetData>" + "".join(out) + "</sheetData></worksheet>")


def write_xlsx(path, sheets, sheet="Sheet1"):
    """sheets: 표 하나([[셀…]…]) 또는 [(시트이름, 표)…] 여러 장.
    ⭐세션65부터 머리행 강조·천 단위 숫자·열 너비 자동·틀 고정·수식(=SUM(A2:A9))·여러 시트."""
    # [(이름, 표)…]인가, 표 한 장([[셀…]…])인가.
    # ⚠️여기를 'sheets[0][0]이 리스트인가'로 판별했다가 틀렸습니다 — [(이름, 표)]의
    #   sheets[0][0]은 **이름(문자열)**입니다. 그래서 여러 시트가 통째로 한 표로 뭉개졌습니다.
    #   짝(이름, 표)의 **두 번째**가 리스트인지를 봐야 맞습니다.
    is_pages = (sheets and isinstance(sheets[0], tuple) and len(sheets[0]) == 2
                and isinstance(sheets[0][1], list))
    pages = list(sheets) if is_pages else [(sheet, sheets)]

    used, clean = set(), []
    for i, (name, rows) in enumerate(pages, 1):
        nm = (str(name or f"Sheet{i}")[:31]) or f"Sheet{i}"
        for bad in "[]:*?/\\":                     # 엑셀이 금지하는 시트 이름 글자
            nm = nm.replace(bad, " ")
        base, n = nm, 2
        while nm in used:                          # 이름이 겹치면 엑셀이 파일을 거부합니다
            nm = f"{base[:28]}_{n}"
            n += 1
        used.add(nm)
        clean.append((nm, rows or [[""]]))

    parts = {
        "_rels/.rels": _ROOT_RELS.format(target="xl/workbook.xml"),
        "xl/styles.xml": _XLSX_STYLES,
    }
    sheet_tags, rel_tags, overrides = [], [], []
    for i, (nm, rows) in enumerate(clean, 1):
        parts[f"xl/worksheets/sheet{i}.xml"] = _sheet_xml(rows)
        sheet_tags.append(f'<sheet name="{esc(nm)}" sheetId="{i}" r:id="rId{i}"/>')
        rel_tags.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/'
                        f'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
        overrides.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType='
                         '"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')

    parts["xl/workbook.xml"] = DECL + (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>" + "".join(sheet_tags) + "</sheets></workbook>")
    parts["xl/_rels/workbook.xml.rels"] = DECL + (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rel_tags)
        + '<Relationship Id="rIdS" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
          'relationships/styles" Target="styles.xml"/></Relationships>')
    parts["[Content_Types].xml"] = DECL + (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.spreadsheetml.styles+xml"/>'
        + "".join(overrides) + "</Types>")
    return _zip(path, parts)


def _img_size(blob):
    """그림의 (가로, 세로)를 EMU로. 비율을 지켜 넣기 위해 필요합니다.
    PIL이 있으면 쓰고, 없으면 PNG·JPEG 머리글을 직접 읽습니다 — 'pip 없음' 원칙이라
    PIL을 **전제하지 않습니다**(다른 기능에선 쓰지만 문서 만들기는 혼자 서야 합니다).
    끝내 모르면 4:3으로 가정합니다(찌그러뜨리느니 어림잡는 편이 낫습니다)."""
    px = None
    try:
        import io as _io
        from PIL import Image
        with Image.open(_io.BytesIO(blob)) as im:
            px = im.size
    except Exception:
        try:
            if blob[:8] == b"\x89PNG\r\n\x1a\n":          # PNG: IHDR에 가로·세로
                px = (int.from_bytes(blob[16:20], "big"), int.from_bytes(blob[20:24], "big"))
            elif blob[:2] == b"\xff\xd8":                 # JPEG: SOF 마커를 훑습니다
                i = 2
                while i < len(blob) - 9:
                    if blob[i] != 0xFF:
                        i += 1
                        continue
                    marker, seg = blob[i + 1], int.from_bytes(blob[i + 2:i + 4], "big")
                    if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                        px = (int.from_bytes(blob[i + 7:i + 9], "big"),
                              int.from_bytes(blob[i + 5:i + 7], "big"))
                        break
                    i += 2 + seg
        except Exception:
            px = None
    if not px or not px[0] or not px[1]:
        px = (800, 600)
    return (px[0] * 9525, px[1] * 9525)                   # 1px(96dpi) = 9525 EMU


# ══ 파워포인트 (.pptx) ═══════════════════════════════════════════
# PPT는 부품이 가장 많습니다: 발표 자체(presentation) + 마스터 + 레이아웃 + 테마 + 슬라이드들.
# 마스터·레이아웃은 '빈 판' 하나만 두고, 글상자는 슬라이드마다 직접 그립니다.
# (레이아웃의 자리표시자를 쓰면 부품 사이 참조가 복잡해지고, 하나만 어긋나도 파일이 안 열립니다)
EMU = 12700                                    # 1pt = 12700 EMU
W, H = 12192000, 6858000                       # 16:9 (33.87cm x 19.05cm)

_THEME = DECL + """<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Lucy">
<a:themeElements>
<a:clrScheme name="Lucy"><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="44546A"/></a:dk2><a:lt2><a:srgbClr val="E7E6E6"/></a:lt2><a:accent1><a:srgbClr val="4472C4"/></a:accent1>
<a:accent2><a:srgbClr val="ED7D31"/></a:accent2><a:accent3><a:srgbClr val="A5A5A5"/></a:accent3><a:accent4><a:srgbClr val="FFC000"/></a:accent4>
<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5><a:accent6><a:srgbClr val="70AD47"/></a:accent6>
<a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>
<a:fontScheme name="Lucy"><a:majorFont><a:latin typeface="맑은 고딕"/><a:ea typeface="맑은 고딕"/><a:cs typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="맑은 고딕"/><a:ea typeface="맑은 고딕"/><a:cs typeface=""/></a:minorFont></a:fontScheme>
<a:fmtScheme name="Lucy">
<a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
<a:lnStyleLst><a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>
<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
</a:fmtScheme></a:themeElements></a:theme>"""

_EMPTY_TREE = ('<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
               '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
               '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree>')

_PML = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')

_MASTER = DECL + f"""<p:sldMaster {_PML}>
<p:cSld>{_EMPTY_TREE}</p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3"
 accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>"""

_LAYOUT = DECL + f"""<p:sldLayout {_PML} type="blank" preserve="1">
<p:cSld name="빈 화면">{_EMPTY_TREE}</p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""

_MASTER_RELS = DECL + """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""

_LAYOUT_RELS = DECL + """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""

# ⚠️ 노트마스터(notesMaster)는 **일부러 만들지 않습니다.**
# 발표자 노트를 넣으려고 미니멀 노트마스터를 하나 끼웠더니 파워포인트가 파일 전체를
# "손상되었습니다"로 거부했습니다(notesStyle을 넣어도 마찬가지). 오래 헤맨 함정입니다 —
# 워드·엑셀은 멀쩡히 열려서 원인이 PPT 안쪽에 있다는 걸 알아채기 어려웠습니다.
# 노트마스터 없이 notesSlide만 두고 그 슬라이드로 되돌아가는 관계 하나만 걸면
# 파워포인트가 잘 열고 노트도 제대로 보여줍니다(실측 확인). 없는 부품이 잘못될 일은 없습니다.


def _para(text, size, bold=False, bullet=False):
    """글 한 줄. size는 pt."""
    props = f'<a:pPr marL="{285750 if bullet else 0}" indent="{-285750 if bullet else 0}">'
    props += "<a:buChar char='•'/>" if bullet else "<a:buNone/>"
    props += "</a:pPr>"
    run = (f'<a:r><a:rPr lang="ko-KR" sz="{int(size * 100)}"{" b=\"1\"" if bold else ""} dirty="0"/>'
           f"<a:t>{esc(text)}</a:t></a:r>")
    return f"<a:p>{props}{run}</a:p>"


def _textbox(idx, name, x, y, cx, cy, paragraphs):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{idx}" name="{esc(name)}"/>'
            '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            '<p:txBody><a:bodyPr wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720">'
            '<a:normAutofit/></a:bodyPr><a:lstStyle/>'
            + "".join(paragraphs) + "</p:txBody></p:sp>")


def _pic_xml(idx, rid, x, y, cx, cy):
    """그림 하나(p:pic). rid는 이 슬라이드의 rels에 등록된 관계 번호."""
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{idx}" name="그림{idx}"/>'
            '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')


_ROW_H = 370000            # 한 줄 높이(EMU ≈ 1cm). 글이 길면 파워포인트가 알아서 늘립니다.


def _tbl_xml(idx, rows, x, y, cx):
    """진짜 표(graphicFrame + a:tbl). 머리행은 테마 배경색(#2F5597)과 흰 글씨로 강조합니다."""
    ncol = max(len(r) for r in rows)
    colw = cx // ncol
    rowh = _ROW_H
    cy = rowh * len(rows)
    grid = "".join(f'<a:gridCol w="{colw}"/>' for _ in range(ncol))
    trs = []
    for r, row in enumerate(rows):
        cells = []
        for c in range(ncol):
            text = row[c] if c < len(row) else ""
            if r == 0:
                fill = '<a:solidFill><a:srgbClr val="2F5597"/></a:solidFill>'
                text_run = f'<a:r><a:rPr lang="ko-KR" sz="1400" b="1" dirty="0"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:rPr><a:t>{esc(text)}</a:t></a:r>'
            else:
                bg_color = "F9FAFC" if r % 2 == 1 else "FFFFFF"
                fill = f'<a:solidFill><a:srgbClr val="{bg_color}"/></a:solidFill>'
                text_run = f'<a:r><a:rPr lang="ko-KR" sz="1400" b="0" dirty="0"/><a:t>{esc(text)}</a:t></a:r>'
            borders = '<a:ln w="12700"><a:solidFill><a:srgbClr val="D3D3D3"/></a:solidFill></a:ln>'
            tcPr = f'<a:tcPr>{borders}{borders}{borders}{borders}{fill}</a:tcPr>'
            cells.append(
                "<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>"
                f'<a:p><a:pPr algn="{"ctr" if r == 0 else "l"}"/>'
                f'{text_run}</a:p>'
                f"</a:txBody>{tcPr}</a:tc>")
        trs.append(f'<a:tr h="{rowh}">' + "".join(cells) + "</a:tr>")
    return (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{idx}" name="표{idx}"/>'
            "<p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>"
            f'<p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></p:xfrm>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
            '<a:tbl><a:tblPr firstRow="1" bandRow="1"/>'
            f"<a:tblGrid>{grid}</a:tblGrid>" + "".join(trs) + "</a:tbl>"
            "</a:graphicData></a:graphic></p:graphicFrame>")


def _slide_xml(title, lines, w=W, h=H, pics=(), tables=(), is_title=False, slide_num=None, total_slides=None):
    """lines: [(kind, text)] — h2(굵은 줄) / bullet / text
    pics: [(rid, 가로, 세로)] — 그림. tables: [[[셀,…],…]] — 표.
    is_title: 표지 슬라이드 여부 (표지와 본문 슬라이드 디자인 차별화).
    slide_num: 슬라이드 번호."""
    shapes = []
    
    if is_title:
        # 표지 슬라이드 디자인: 상단 테마 색상 바 + 중앙 대형 제목
        shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="10" name="표지배경"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{w}" cy="{int(h * 0.12)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="2F5597"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr></p:sp>'
        )
        title_y = int(h * 0.32)
        title_paras = [_para(title or "", 44, bold=True)]
        for kind, text in lines:
            title_paras.append(_para(text, 20))
        shapes.append(_textbox(2, "표지제목", 685800, title_y, w - 1371600, 2500000, title_paras))
    else:
        # 본문 슬라이드 디자인: 제목 + 하단 강조선 + 본문/그림/표 + 슬라이드 번호
        shapes.append(_textbox(2, "제목", 685800, 457200, w - 1371600, 900000,
                               [_para(title or "", 30, bold=True)]))
        # 테마 강조선
        shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="11" name="구분선"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="685800" y="1250000"/><a:ext cx="{w - 1371600}" cy="35000"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="4472C4"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr></p:sp>'
        )
        
        paras = []
        for kind, text in lines:
            if kind == "h2":
                paras.append(_para(text, 20, bold=True))
            elif kind == "bullet":
                paras.append(_para(text, 18, bullet=True))
            else:
                paras.append(_para(text, 18))

        top, body_h = 1500000, h - 2200000
        text_w = (w - 1371600) // 2 if pics else (w - 1371600)
        if paras:
            shapes.append(_textbox(3, "본문", 685800, top, text_w, body_h, paras))

        idx = 4
        if pics:
            area_x = 685800 + text_w + 200000 if paras else 685800
            area_w = (w - 685800 - area_x) if paras else (w - 1371600)
            each_h = body_h // len(pics)
            for i, (rid, iw, ih) in enumerate(pics):
                scale = min(area_w / iw, (each_h - 100000) / ih) if iw and ih else 1
                cx, cy = int(iw * scale), int(ih * scale)
                shapes.append(_pic_xml(idx, rid, area_x + (area_w - cx) // 2,
                                       top + i * each_h, cx, cy))
                idx += 1
        if tables:
            t_y = top + (len(paras) * 300000 + 200000 if paras else 0)
            for rows in tables:
                shapes.append(_tbl_xml(idx, rows, 685800, t_y, w - 1371600))
                t_y += _ROW_H * len(rows) + 200000
                idx += 1

        # 슬라이드 번호
        if slide_num is not None:
            num_str = f"{slide_num} / {total_slides}" if total_slides else str(slide_num)
            num_para = f'<a:p><a:pPr algn="r"/><a:r><a:rPr lang="ko-KR" sz="1200" dirty="0"><a:solidFill><a:srgbClr val="7F7F7F"/></a:solidFill></a:rPr><a:t>{esc(num_str)}</a:t></a:r></a:p>'
            shapes.append(_textbox(99, "슬라이드번호", w - 2000000, h - 500000, 1400000, 350000, [num_para]))

    return (DECL + f"<p:sld {_PML}><p:cSld><p:spTree>"
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            + "".join(shapes) +
            "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>")


def _notes_xml(note):
    body = _textbox(2, "발표자 노트", 0, 0, 6858000, 4114800,
                    [_para(line, 12) for line in note.splitlines() if line.strip()])
    return (DECL + f"<p:notes {_PML}><p:cSld><p:spTree>"
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            + body + "</p:spTree></p:cSld></p:notes>")


def _new_slide(title=""):
    """빈 슬라이드 하나. 그림·표 칸을 여기서 한 번에 만들어 둡니다 — 예전엔 dict를 세 군데서
    따로 만들어서, 칸을 하나 늘릴 때 한 곳을 빠뜨리면 KeyError가 났습니다."""
    return {"title": title, "lines": [], "note": "", "images": [], "tables": []}


def to_slides(blocks, title=None):
    """블록들을 슬라이드로 자릅니다. '# 제목'이 새 슬라이드의 시작입니다."""
    slides = []
    current = None
    for kind, text in blocks:
        if kind != "table":
            text = _plain(text)
        if kind == "h1" or (kind == "break" and current):
            if current:
                slides.append(current)
            current = _new_slide(text if kind == "h1" else "")
            continue
        if current is None:
            # '# 제목' 없이 글부터 시작하면 표지 슬라이드를 하나 만듭니다.
            current = _new_slide(title or "")
        if kind == "table":
            current["tables"].append([[_plain(c) for c in row] for row in text])
            continue
        if kind == "image":
            current["images"].append(text)
            continue
        if kind == "note":
            current["note"] += (("\n" if current["note"] else "") + text)
        else:
            current["lines"].append((kind, text))
    if current:
        slides.append(current)

    if title and slides and slides[0]["title"] != title:
        slides.insert(0, _new_slide(title))
    if slides:
        slides[0]["is_title"] = True
    return slides


def write_pptx(path, slides):
    if not slides:
        slides = [_new_slide("(빈 문서)")]

    parts = {
        "_rels/.rels": _ROOT_RELS.format(target="ppt/presentation.xml"),
        "ppt/theme/theme1.xml": _THEME,
        "ppt/slideMasters/slideMaster1.xml": _MASTER,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _MASTER_RELS,
        "ppt/slideLayouts/slideLayout1.xml": _LAYOUT,
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _LAYOUT_RELS,
    }
    overrides, sld_ids, pres_rels = [], [], []
    pres_rels.append('<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>')

    media_exts = set()
    for i, s in enumerate(slides, 1):
        rid = f"rId{9 + i}"
        rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>']

        pics = []
        for j, img in enumerate(s.get("images", []), 1):
            try:
                with open(img, "rb") as fh:
                    blob = fh.read()
            except OSError:
                continue
            ext = (os.path.splitext(img)[1].lower().lstrip(".") or "png")
            if ext == "jpg":
                ext = "jpeg"
            name = f"image{i}_{j}.{ext}"
            parts[f"ppt/media/{name}"] = blob
            media_exts.add(ext)
            prid = f"rId{100 + j}"
            rels.append(f'<Relationship Id="{prid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{name}"/>')
            pics.append((prid,) + _img_size(blob))

        parts[f"ppt/slides/slide{i}.xml"] = _slide_xml(
            s.get("title", ""), s.get("lines", []), pics=pics, tables=s.get("tables", []),
            is_title=s.get("is_title", i == 1), slide_num=i, total_slides=len(slides))
        if s.get("note"):
            parts[f"ppt/notesSlides/notesSlide{i}.xml"] = _notes_xml(s["note"])
            parts[f"ppt/notesSlides/_rels/notesSlide{i}.xml.rels"] = DECL + (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="../slides/slide{i}.xml"/>'
                "</Relationships>")
            rels.append(f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide{i}.xml"/>')
            overrides.append(f'<Override PartName="/ppt/notesSlides/notesSlide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>')
        parts[f"ppt/slides/_rels/slide{i}.xml.rels"] = DECL + (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels) + "</Relationships>")
        overrides.append(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
        sld_ids.append(f'<p:sldId id="{255 + i}" r:id="{rid}"/>')
        pres_rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')

    parts["ppt/presentation.xml"] = DECL + (
        f"<p:presentation {_PML} saveSubsetFonts=\"1\">"
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        "<p:sldIdLst>" + "".join(sld_ids) + "</p:sldIdLst>"
        f'<p:sldSz cx="{W}" cy="{H}"/><p:notesSz cx="6858000" cy="9144000"/>'
        "</p:presentation>")
    parts["ppt/_rels/presentation.xml.rels"] = DECL + (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(pres_rels) + "</Relationships>")

    parts["[Content_Types].xml"] = DECL + (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        # 그림 확장자를 여기 안 적으면 파워포인트가 "복구할 수 없는 내용"이라며 거부합니다.
        + "".join(f'<Default Extension="{e}" ContentType="image/{e}"/>' for e in sorted(media_exts))
        + '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        + "".join(overrides) + "</Types>")

    return _zip(path, parts)


# ══ 한글 (.hwpx) ═════════════════════════════════════════════════
# HWPX = zip 속 OWPML(XML). docx·pptx와 같은 사상이라 여기서도 라이브러리를 안 씁니다.
# 루시는 이미 hwpx를 **읽을** 줄 알았는데(tools._read_hwpx) 쓸 줄은 몰랐습니다 — 그 구멍을 메웁니다.
#
# ⚠️오피스와 결정적으로 다른 점: 본문(section0.xml)은 글자모양·문단모양을 **번호로만** 가리키고,
#   그 번호의 실체는 header.xml에 있습니다. 번호 하나가 어긋나면 한글이 파일을 통째로 거부합니다.
#   그래서 아래 ID들은 header와 본문이 **같이** 움직여야 합니다:
#     charPr 0=본문 10pt · 1=제목 16pt 굵게 · 2=소제목 12pt 굵게
#     paraPr 0=보통 · 1=글머리표(왼쪽 들여쓰기)
# ⚠️borderFill·charPr가 서로를 참조합니다(charPr의 borderFillIDRef=2) — 지우지 말 것.
# ⚠️mimetype은 zip의 **첫 항목**이고 **압축하지 않아야** 합니다(OCF 규약, ODF·EPUB와 동일).
_HWPX_NS = (
    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
    'xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" '
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
    'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
    'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" '
    'xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" '
    'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:opf="http://www.idpf.org/2007/opf/" '
    'xmlns:epub="http://www.idpf.org/2007/ops" '
    'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"'
)

_HWPX_FONT = "함초롬바탕"                       # 한글 기본 글꼴 — 어느 PC에나 한글과 함께 깔립니다
_HWPX_LANGS = ("HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER")


def _hwpx_charpr(idx, height, bold=False):
    """글자모양 하나. height는 1/100 pt 단위(1000 = 10pt)."""
    return (f'<hh:charPr id="{idx}" height="{height}" textColor="#000000" shadeColor="#FFFFFFFF"'
            ' useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="2">'
            '<hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
            '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
            '<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
            '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
            '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
            + ("<hh:bold/>" if bold else "")
            + "</hh:charPr>")


def _hwpx_parapr(idx, left_margin=0):
    """문단모양 하나. left_margin은 HWPUNIT(1mm ≈ 283)."""
    return (f'<hh:paraPr id="{idx}" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="1"'
            ' suppressLineNumbers="0" checked="0">'
            '<hh:align horizontal="JUSTIFY" vertical="BASELINE"/>'
            '<hh:heading type="NONE" idRef="0" level="0"/>'
            '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="0"'
            ' keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
            '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
            '<hh:margin><hc:intent value="0" unit="HWPUNIT"/>'
            f'<hc:left value="{left_margin}" unit="HWPUNIT"/>'
            '<hc:right value="0" unit="HWPUNIT"/><hc:prev value="0" unit="HWPUNIT"/>'
            '<hc:next value="0" unit="HWPUNIT"/></hh:margin>'
            '<hh:lineSpacing type="PERCENT" value="160" unit="HWPUNIT"/>'
            '<hh:border borderFillIDRef="2" offsetLeft="0" offsetRight="0" offsetTop="0"'
            ' offsetBottom="0" connect="0" ignoreMargin="0"/></hh:paraPr>')


def _hwpx_header():
    """header.xml — 글꼴·테두리·글자모양·문단모양·스타일의 '사전'."""
    fonts = "".join(
        f'<hh:fontface lang="{lang}" fontCnt="1">'
        f'<hh:font id="0" face="{_HWPX_FONT}" type="TTF" isEmbedded="0">'
        '<hh:typeInfo familyType="FCAT_GOTHIC" weight="8" proportion="4" contrast="0"'
        ' strokeVariation="1" armStyle="1" letterform="1" midline="1" xHeight="1"/>'
        "</hh:font></hh:fontface>" for lang in _HWPX_LANGS)

    borders = "".join(
        f'<hh:borderFill id="{i}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
        "</hh:borderFill>" for i in (1, 2))

    chars = (_hwpx_charpr(0, 1000) + _hwpx_charpr(1, 1600, bold=True)
             + _hwpx_charpr(2, 1200, bold=True))
    paras = _hwpx_parapr(0) + _hwpx_parapr(1, left_margin=1400)

    return (DECL + f'<hh:head {_HWPX_NS} version="1.2" secCnt="1">'
            '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>'
            "<hh:refList>"
            f'<hh:fontfaces itemCnt="{len(_HWPX_LANGS)}">{fonts}</hh:fontfaces>'
            f'<hh:borderFills itemCnt="2">{borders}</hh:borderFills>'
            f'<hh:charProperties itemCnt="3">{chars}</hh:charProperties>'
            '<hh:tabProperties itemCnt="1"><hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/>'
            "</hh:tabProperties>"
            f'<hh:paraProperties itemCnt="2">{paras}</hh:paraProperties>'
            '<hh:styles itemCnt="1"><hh:style id="0" type="PARA" name="바탕글" engName="Normal"'
            ' paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0" langID="1042" lockForm="0"/>'
            "</hh:styles>"
            "</hh:refList></hh:head>")


# 첫 문단에만 들어가는 쪽 설정(A4 세로·기본 여백). 값은 HWPUNIT.
_HWPX_SECPR = (
    '<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000"'
    ' outlineShapeIDRef="1" memoShapeIDRef="0" textVerticalWidthHead="0" masterPageCnt="0">'
    '<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>'
    '<hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>'
    '<hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0"'
    ' border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>'
    '<hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>'
    '<hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">'
    '<hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504"'
    ' top="5668" bottom="4252"/></hp:pagePr>'
    "</hp:secPr>"
)


def _hwpx_p(text, char_id=0, para_id=0, first=False):
    """문단 하나. first=True면 쪽 설정(secPr)을 함께 싣습니다(첫 문단의 의무)."""
    head = ""
    if first:
        head = (f'<hp:run charPrIDRef="{char_id}">' + _HWPX_SECPR
                + '<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1"'
                ' sameSz="1" sameGap="0"/></hp:ctrl></hp:run>')
    body = f'<hp:run charPrIDRef="{char_id}"><hp:t>{esc(text)}</hp:t></hp:run>'
    return (f'<hp:p id="0" paraPrIDRef="{para_id}" styleIDRef="0" pageBreak="0"'
            f' columnBreak="0" merged="0">{head}{body}</hp:p>')


def write_hwpx(path, blocks, title=None):
    """마크다운 블록들을 한글 문서로. blocks는 parse_blocks가 만든 [(종류, 글)]."""
    rows = []
    if title:
        rows.append((title, 1, 0))                 # (글, charPr, paraPr)
    for kind, text in blocks:
        if kind == "h1":
            rows.append((text, 1, 0))
        elif kind == "h2":
            rows.append((text, 2, 0))
        elif kind == "bullet":
            rows.append(("· " + text, 0, 1))       # 들여쓴 문단 + 가운뎃점(한글 글머리표 관례)
        elif kind == "table":
            # ⚠️표 블록은 문자열이 아니라 **행들의 목록**입니다([[셀,…],…]) — 여기를 문자열로
            #   착각해 splitlines()를 부르다 회귀 시험에서 터졌습니다. 한글 표(hp:tbl)는 아직
            #   안 만들고 글줄로 폅니다(표가 중요하면 워드·엑셀로 만드는 게 맞습니다).
            for row in text:
                rows.append((" | ".join(str(c) for c in row), 0, 0))
        else:
            rows.append((text, 0, 0))
    if not rows:
        rows = [("", 0, 0)]

    paras = "".join(_hwpx_p(t, c, p, first=(i == 0)) for i, (t, c, p) in enumerate(rows))
    section = DECL + f"<hs:sec {_HWPX_NS}>{paras}</hs:sec>"

    preview = "\n".join(t for t, _c, _p in rows)[:1000]
    content_hpf = (DECL + f'<opf:package {_HWPX_NS} version="" unique-identifier="" id="">'
                   f"<opf:metadata><opf:title>{esc(title or '')}</opf:title>"
                   "<opf:language>ko</opf:language></opf:metadata>"
                   "<opf:manifest>"
                   '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
                   '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
                   "</opf:manifest>"
                   '<opf:spine><opf:itemref idref="header" linear="yes"/>'
                   '<opf:itemref idref="section0" linear="yes"/></opf:spine></opf:package>')

    parts = {
        "version.xml": DECL + '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version"'
                              ' tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="0"'
                              ' buildNumber="0" os="1" xmlVersion="1.2" application="Lucy"'
                              ' appVersion="1.0"/>',
        "META-INF/container.xml": DECL + '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:'
                                         'xmlns:container"><ocf:rootfiles><ocf:rootfile '
                                         'full-path="Contents/content.hpf" '
                                         'media-type="application/hwpml-package+xml"/>'
                                         "</ocf:rootfiles></ocf:container>",
        "META-INF/manifest.xml": DECL + '<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:'
                                        'xmlns:manifest:1.0"/>',
        "Contents/content.hpf": content_hpf,
        "Contents/header.xml": _hwpx_header(),
        "Contents/section0.xml": section,
        "Preview/PrvText.txt": preview,
    }
    return _zip_hwpx(path, parts)


def _zip_hwpx(path, parts):
    """한글용 zip. ⚠️mimetype이 **첫 항목**이고 **무압축**이어야 합니다(OCF 규약)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, "application/hwp+zip")
        for name, data in parts.items():
            z.writestr(name, data)
    return path


# ── 바깥에서 부르는 문 하나 ───────────────────────────────────────
def write(path, content, title=None, sheet=None):
    """확장자를 보고 알맞은 형식으로 만듭니다. 만든 경로를 돌려줍니다."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        # '# 시트이름'이 있으면 시트를 나눕니다(PPT에서 '# 제목'이 슬라이드를 나누는 것과 같은 규칙).
        pages, cur_name, cur = [], None, []
        for raw in (content or "").splitlines():
            m = re.match(r"^#{1,2}\s+(.+)$", raw.strip())
            if m:
                if cur:
                    pages.append((cur_name, "\n".join(cur)))
                cur_name, cur = m.group(1).strip(), []
            else:
                cur.append(raw)
        if cur:
            pages.append((cur_name, "\n".join(cur)))

        if len(pages) > 1 or (pages and pages[0][0]):
            tables = [(nm or f"Sheet{i}", parse_table(body))
                      for i, (nm, body) in enumerate(pages, 1)]
            tables = [(nm, rows) for nm, rows in tables if rows]
            if not tables:
                raise ValueError("표로 읽을 내용이 없습니다. 마크다운 표(| a | b |)나 CSV로 주세요.")
            return write_xlsx(path, tables)

        rows = parse_table(content)
        if not rows:
            raise ValueError("표로 읽을 내용이 없습니다. 마크다운 표(| a | b |)나 CSV로 주세요.")
        return write_xlsx(path, rows, sheet or title or "Sheet1")

    blocks = parse_blocks(content)
    if ext == ".docx":
        return write_docx(path, blocks, title)
    if ext == ".pptx":
        return write_pptx(path, to_slides(blocks, title))
    if ext == ".hwpx":
        return write_hwpx(path, blocks, title)
    raise ValueError(f"만들 수 없는 형식입니다: {ext} (.docx · .pptx · .xlsx · .hwpx 만 됩니다)")


# ══ 문서 수정 (.docx · .pptx) ════════════════════════════════════
# 새로 만드는 게 아니라 **이미 있는** 문서의 글자를 바꾸거나 끝에 덧붙입니다.
# 원리는 만들기와 같습니다: 오피스 파일 = XML을 담은 zip. 바꿀 XML만 고쳐 다시 쌉니다.
#
# ⚠️워드가 만든 문서는 한 문장이 여러 run(<w:r>)으로 쪼개져 있기 일쑤입니다(맞춤법 검사
#   흔적·서식 경계). 그래서 두 단계로 찾습니다:
#     ① 한 글자 덩어리(w:t/a:t) 안에서 바로 치환 — 구조를 전혀 안 건드리는 안전한 길
#     ② 안 걸리면 문단의 글자를 다 이어붙여 보고, 있으면 문단을 첫 run의 서식
#        하나로 합쳐 치환 — 그림·링크·필드가 든 문단은 합치면 그것들이 사라지므로
#        건너뛰고 정직하게 보고합니다.

_W_T = re.compile(r"(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)", re.S)
_A_T = re.compile(r"(<a:t>)(.*?)(</a:t>)", re.S)
_W_P = re.compile(r"<w:p(?:\s[^>]*)?>.*?</w:p>", re.S)
_A_P = re.compile(r"<a:p>.*?</a:p>", re.S)


def _unesc(s):
    """XML 텍스트 노드 → 원래 글자. &amp;를 맨 뒤에 풀어야 '&amp;lt;'가 '<'로 안 둔갑합니다."""
    return (s.replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&"))


def _replace_in_xml(xml, old, new, flavor):
    """한 XML 부품 안에서 old→new. (바뀐 xml, 바꾼 횟수, 서식 보호로 건너뛴 문단 수)

    문단마다 전략을 **한 번만** 고릅니다. 덩어리 치환을 먼저 다 하고 나서 문단 검사를
    또 돌리면, 바꾼 결과가 원래 문구를 품고 있을 때('A'→'B+A') 같은 자리를 두 번
    치환합니다('B+B+A' — 실제 시험이 잡은 버그).
    """
    t_re = _W_T if flavor == "w" else _A_T
    p_re = _W_P if flavor == "w" else _A_P
    unsafe = (("<w:drawing", "<w:pict", "<w:hyperlink", "<w:fldChar", "<m:oMath")
              if flavor == "w" else ("<a:fld",))
    count = 0
    skipped = 0

    def sub_nodes(para):
        """구조를 전혀 안 건드리는 길 — 덩어리(w:t/a:t) 안에서만 바꿉니다."""
        def sub_t(tm):
            plain = _unesc(tm.group(2))
            if old not in plain:
                return tm.group(0)
            opening = tm.group(1)
            if flavor == "w" and "xml:space" not in opening:
                # 치환으로 양끝에 공백이 생기면 워드가 조용히 지워버립니다 — 지키라고 못박습니다
                opening = opening[:-1] + ' xml:space="preserve">'
            return opening + esc(plain.replace(old, new)) + tm.group(3)
        return t_re.sub(sub_t, para)

    def fix_para(m):
        nonlocal count, skipped
        para = m.group(0)
        nodes = [_unesc(t.group(2)) for t in t_re.finditer(para)]
        joined = "".join(nodes)
        total = joined.count(old)
        if not total:
            return para

        in_nodes = sum(n.count(old) for n in nodes)     # 덩어리 안에 온전히 든 발생 수
        risky = any(mark in para for mark in unsafe)
        if in_nodes == total or (in_nodes and risky):
            # 전부 덩어리 안이면 그 길로. 그림·링크가 있어도 덩어리 안 것은 안전하게 바꿉니다.
            count += in_nodes
            if in_nodes < total:
                skipped += 1            # 걸쳐 있는 나머지는 합쳐야 하는데 합치면 그림이 사라집니다
            return sub_nodes(para)
        if risky:
            skipped += 1                # 발생이 전부 run 경계에 걸림 + 그림·링크 — 손대지 않습니다
            return para

        # 발생이 run 경계에 걸림 — 문단을 첫 run의 서식 하나로 합쳐 치환합니다.
        count += total
        replaced = joined.replace(old, new)
        if flavor == "w":
            head = re.match(r"<w:p(?:\s[^>]*)?>(?:<w:pPr>.*?</w:pPr>)?", para, re.S).group(0)
            # 첫 run의 서식을 가져옵니다. head 뒤에서 찾아야 문단표식 서식(pPr 안 rPr)과 안 섞입니다.
            rpr = re.search(r"<w:rPr>.*?</w:rPr>", para[len(head):], re.S)
            return (head + f"<w:r>{rpr.group(0) if rpr else ''}"
                    f'<w:t xml:space="preserve">{esc(replaced)}</w:t></w:r></w:p>')
        head = re.match(r"<a:p>(?:<a:pPr[^>]*(?:/>|>.*?</a:pPr>))?", para, re.S).group(0)
        rpr = re.search(r"<a:rPr[^>]*(?:/>|>.*?</a:rPr>)", para[len(head):], re.S)
        return (head + f"<a:r>{rpr.group(0) if rpr else ''}"
                f"<a:t>{esc(replaced)}</a:t></a:r></a:p>")

    xml = p_re.sub(fix_para, xml)
    return xml, count, skipped


_XL_T = re.compile(r"(<t(?:\s[^>]*)?>)(.*?)(</t>)", re.S)
_XL_CELL = re.compile(r"<c\b[^>]*>.*?</c>", re.S)
_NUMERIC = re.compile(r"-?\d+(\.\d+)?([eE][+-]?\d+)?")


def _replace_in_xlsx(data, names, old, new):
    """엑셀 치환. (바꾼 횟수, 건너뛴 셀 수, 고친 부품 이름들)

    셀의 종류마다 규칙이 다릅니다 — 섞으면 파일이 거짓말을 하거나 깨집니다:
      · 글자 셀(sharedStrings·인라인 문자열) = 부분 치환(워드와 같은 감각).
        ⚠️공유 문자열은 여러 셀이 한 항목을 같이 씀 — 한 번 바꾸면 그 글자를 쓰는
        모든 셀이 같이 바뀝니다(find→replace의 의미와 일치하므로 그대로 둡니다).
      · 숫자 셀 = 값 **전체가 정확히 일치할 때만**('150'→'90'이 '1500'을 '900'으로
        만들면 재앙). 바꿀 값이 숫자 꼴이 아니면 건너뛰고 정직하게 셉니다.
      · 수식 셀 = 손대지 않음(캐시 값만 바꾸면 열자마자 재계산으로 되돌아감).
      · t="s" 셀의 <v>는 값이 아니라 공유 문자열 **번호** — 절대 만지면 안 됩니다.
    """
    count = skipped = 0
    changed = []

    def sub_t(m):
        nonlocal count
        plain = _unesc(m.group(2))
        if old not in plain:
            return m.group(0)
        count += plain.count(old)
        return m.group(1) + esc(plain.replace(old, new)) + m.group(3)

    ss = "xl/sharedStrings.xml"
    if ss in data:
        xml = data[ss].decode("utf-8")
        fixed = _XL_T.sub(sub_t, xml)
        if fixed != xml:
            data[ss] = fixed.encode("utf-8")
            changed.append(ss)

    new_is_number = bool(_NUMERIC.fullmatch(new.strip()))
    for name in names:
        if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
            continue
        xml = data[name].decode("utf-8")

        def fix_cell(m):
            nonlocal count, skipped
            cell = m.group(0)
            head = cell[:cell.find(">")]
            t_attr = re.search(r'\bt="([^"]+)"', head)
            kind = t_attr.group(1) if t_attr else ""
            if kind == "s":
                return cell                  # 공유 문자열 번호 — sharedStrings 쪽에서 처리됨
            if kind in ("inlineStr", "str"):
                return _XL_T.sub(sub_t, cell)
            vm = re.search(r"<v>(.*?)</v>", cell, re.S)
            if not vm or vm.group(1).strip() != old.strip():
                return cell
            if "<f" in cell:
                skipped += 1                 # 수식의 캐시 값 — 바꿔봐야 재계산으로 되돌아감
                return cell
            if not new_is_number:
                skipped += 1                 # 숫자 셀에 글자를 넣으면 엑셀이 '복구'를 띄움
                return cell
            count += 1
            return cell.replace(vm.group(0), f"<v>{new.strip()}</v>", 1)

        fixed = _XL_CELL.sub(fix_cell, xml)
        if fixed != xml:
            data[name] = fixed.encode("utf-8")
            changed.append(name)
    return count, skipped, changed


_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_RELS = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'


def _append_slides_pptx(data, names, append):
    """이미 있는 pptx 끝에 새 슬라이드를 답니다. data·names를 제자리에서 고치고
    (붙인 슬라이드 수, 새로 만들거나 고친 부품 이름들)을 돌려줍니다.

    새로 만들 때(write_pptx)와 달리 **남의 덱을 존중**해야 합니다:
      · 번호(슬라이드 파일·rId·sldId)는 전부 '지금 최댓값+1'부터 — 빈 번호를 메우려
        들면 어긋난 덱에서 기존 부품과 충돌합니다.
      · 새 슬라이드의 레이아웃은 마지막 슬라이드가 쓰는 것을 물려받습니다(덱의
        생김새를 따라감). 슬라이드가 없으면 덱에 실존하는 첫 레이아웃.
      · 노트마스터는 여기서도 만들지 않습니다(만들면 파워포인트가 '손상' 거부 — 위 함정).
    고쳐야 하는 장부 셋을 전부 고칩니다: presentation.xml(슬라이드 목록)·그 rels·
    [Content_Types].xml. 하나라도 빠지면 파워포인트가 파일을 거부합니다.
    """
    slides = to_slides(parse_blocks(append))
    if not slides:
        raise ValueError("덧붙일 내용이 비어 있습니다.")

    pres_name, rels_name, ct_name = ("ppt/presentation.xml",
                                     "ppt/_rels/presentation.xml.rels", "[Content_Types].xml")
    if pres_name not in data or rels_name not in data or ct_name not in data:
        raise ValueError("presentation.xml이 없는 이상한 pptx입니다 — 손대지 않습니다.")
    pres = data[pres_name].decode("utf-8")
    rels = data[rels_name].decode("utf-8")
    ct = data[ct_name].decode("utf-8")

    m = re.search(r'<p:sldSz[^>]*\bcx="(\d+)"[^>]*\bcy="(\d+)"', pres)
    w, h = (int(m.group(1)), int(m.group(2))) if m else (W, H)

    slide_nums = [int(g) for n in names for g in re.findall(r"^ppt/slides/slide(\d+)\.xml$", n)]
    notes_nums = [int(g) for n in names
                  for g in re.findall(r"^ppt/notesSlides/notesSlide(\d+)\.xml$", n)]
    next_slide = max(slide_nums, default=0) + 1
    next_note = max(notes_nums, default=0) + 1
    next_rid = max([int(g) for g in re.findall(r'Id="rId(\d+)"', rels)], default=0) + 1
    next_sid = max([int(g) for g in re.findall(r'<p:sldId id="(\d+)"', pres)] + [255]) + 1

    layout_rel = None
    if slide_nums:
        last = data.get(f"ppt/slides/_rels/slide{max(slide_nums)}.xml.rels")
        if last:
            for tag in re.findall(r"<Relationship\b[^>]*/?>", last.decode("utf-8")):
                if "/slideLayout" in tag:
                    tm = re.search(r'Target="([^"]+)"', tag)
                    layout_rel = tm.group(1) if tm else None
                    break
    if not layout_rel:
        layouts = sorted(n for n in names
                         if re.fullmatch(r"ppt/slideLayouts/slideLayout\d+\.xml", n))
        if not layouts:
            raise ValueError("이 pptx에는 슬라이드 레이아웃이 없습니다 — 손대지 않습니다.")
        layout_rel = "../slideLayouts/" + os.path.basename(layouts[0])

    new_sldids, new_rels, new_overrides, touched = [], [], [], []
    for k, s in enumerate(slides):
        num = next_slide + k
        rid = f"rId{next_rid + k}"
        part = f"ppt/slides/slide{num}.xml"
        data[part] = _slide_xml(s.get("title", ""), s.get("lines", []), w, h,
                                is_title=s.get("is_title", False),
                                slide_num=num, total_slides=None).encode("utf-8")
        names.append(part)
        touched.append(part)
        srels = [f'<Relationship Id="rId1" Type="{_REL_NS}/slideLayout" Target="{layout_rel}"/>']
        if s.get("note"):
            npart = f"ppt/notesSlides/notesSlide{next_note}.xml"
            nrels = f"ppt/notesSlides/_rels/notesSlide{next_note}.xml.rels"
            data[npart] = _notes_xml(s["note"]).encode("utf-8")
            data[nrels] = (DECL + _PKG_RELS
                           + f'<Relationship Id="rId1" Type="{_REL_NS}/slide" Target="../slides/slide{num}.xml"/>'
                           "</Relationships>").encode("utf-8")
            names += [npart, nrels]
            touched += [npart, nrels]
            srels.append(f'<Relationship Id="rId2" Type="{_REL_NS}/notesSlide" '
                         f'Target="../notesSlides/notesSlide{next_note}.xml"/>')
            new_overrides.append(f'<Override PartName="/{npart}" ContentType="application/'
                                 'vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>')
            next_note += 1
        part_rels = f"ppt/slides/_rels/slide{num}.xml.rels"
        data[part_rels] = (DECL + _PKG_RELS + "".join(srels) + "</Relationships>").encode("utf-8")
        names.append(part_rels)
        touched.append(part_rels)
        new_overrides.append(f'<Override PartName="/{part}" ContentType="application/'
                             'vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
        new_sldids.append(f'<p:sldId id="{next_sid + k}" r:id="{rid}"/>')
        new_rels.append(f'<Relationship Id="{rid}" Type="{_REL_NS}/slide" Target="slides/slide{num}.xml"/>')

    if "</p:sldIdLst>" in pres:
        pres = pres.replace("</p:sldIdLst>", "".join(new_sldids) + "</p:sldIdLst>", 1)
    elif "<p:sldIdLst/>" in pres:
        pres = pres.replace("<p:sldIdLst/>",
                            "<p:sldIdLst>" + "".join(new_sldids) + "</p:sldIdLst>", 1)
    else:
        # 슬라이드가 한 장도 없던 덱 — 스키마 순서상 sldIdLst는 sldSz 앞입니다.
        lst = "<p:sldIdLst>" + "".join(new_sldids) + "</p:sldIdLst>"
        at = pres.find("<p:sldSz")
        pres = (pres[:at] + lst + pres[at:] if at >= 0
                else pres.replace("</p:presentation>", lst + "</p:presentation>", 1))
    data[pres_name] = pres.encode("utf-8")
    data[rels_name] = rels.replace("</Relationships>",
                                   "".join(new_rels) + "</Relationships>", 1).encode("utf-8")
    data[ct_name] = ct.replace("</Types>", "".join(new_overrides) + "</Types>", 1).encode("utf-8")
    touched += [pres_name, rels_name, ct_name]
    return len(slides), touched


def _edit_targets(names, ext):
    """이 문서에서 글자가 사는 XML 부품들. (머리글·바닥글은 안 건드립니다 — 쪽번호 등이 살아야 함)"""
    if ext == ".docx":
        return [n for n in names if n == "word/document.xml"]
    return sorted(n for n in names
                  if re.fullmatch(r"ppt/(slides|notesSlides)/[^/]+\.xml", n))


def edit(path, find=None, replace="", append=None, dry=False):
    """
    이미 있는 문서를 고칩니다. find→replace 치환(.docx·.pptx)과 끝에 덧붙이기
    (.docx=문단, .pptx=새 슬라이드 — '# 제목'마다 한 장).

    dry=True면 몇 군데가 바뀔지만 세고 파일은 안 건드립니다(사용자 확인 문구용).
    실제로 고칠 때는: 고친 XML이 멀쩡한지 검사 → 원본을 memory/doc_backups에 복사 →
    임시 파일에 다 쓴 뒤 원자적으로 교체. 어느 단계에서 죽어도 원본은 남습니다.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".docx", ".pptx", ".xlsx"):
        raise ValueError(f"{ext}는 고칠 수 없습니다 (.docx·.pptx·.xlsx만 됩니다)")
    if ext == ".xlsx" and append:
        raise ValueError("엑셀에는 덧붙이기(append)가 없습니다 — 셀 값 바꾸기(find→replace)만 됩니다. "
                         "표를 크게 고치려면 write_document로 새로 만드세요.")
    flavor = "w" if ext == ".docx" else "a"

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        data = {n: zf.read(n) for n in names}

    replaced = skipped = 0
    changed = set()
    if find and ext == ".xlsx":
        replaced, skipped, touched = _replace_in_xlsx(data, names, find, replace)
        changed.update(touched)
    elif find:
        for n in _edit_targets(names, ext):
            xml = data[n].decode("utf-8")
            xml, c, s = _replace_in_xml(xml, find, replace, flavor)
            replaced += c
            skipped += s
            if c:
                data[n] = xml.encode("utf-8")
                changed.add(n)

    slides_added = 0
    if append and ext == ".docx":
        xml = data["word/document.xml"].decode("utf-8")
        add = "".join(_docx_body(parse_blocks(append)))
        at = xml.rfind("<w:sectPr")          # 본문 끝의 구역 설정 앞에. rfind — 중간 구역 나눔에 속지 않게
        if at >= 0:
            xml = xml[:at] + add + xml[at:]
        else:
            xml = xml.replace("</w:body>", add + "</w:body>")
        data["word/document.xml"] = xml.encode("utf-8")
        changed.add("word/document.xml")

    if append and ext == ".pptx":
        # PPT의 덧붙이기 = 새 슬라이드. '# 제목'마다 한 장입니다(write_document와 같은 규칙).
        slides_added, touched = _append_slides_pptx(data, names, append)
        changed.update(touched)

    result = {"replaced": replaced, "skipped": skipped, "appended": bool(append),
              "slides_added": slides_added, "backup": ""}
    if dry or not changed:
        return result

    # 고친 XML이 깨졌으면 여기서 멈춥니다 — 잘못 싼 zip은 문서를 통째로 잃게 합니다.
    import xml.etree.ElementTree as ET
    for n in changed:
        ET.fromstring(data[n])

    backups = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", "doc_backups")
    os.makedirs(backups, exist_ok=True)
    import shutil
    import time as _time
    stem, dot_ext = os.path.splitext(os.path.basename(path))
    bak = os.path.join(backups, f"{stem}_{_time.strftime('%Y%m%d_%H%M%S')}{dot_ext}")
    shutil.copy2(path, bak)
    result["backup"] = bak

    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:                      # 원본의 항목 순서 그대로 — [Content_Types].xml 첫 자리 유지
            z.writestr(n, data[n])
    os.replace(tmp, path)
    return result
