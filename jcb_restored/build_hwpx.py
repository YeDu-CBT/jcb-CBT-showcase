#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
정보처리기사 실기 복원문제 모음 -> 한글(HWPX / HWP) 문서.

원본 데이터는 build_docx.js 와 같다.
  raw/*.json                      회차별 문제(번호·언어·정답·해설·code)
  formatted_prompts.json          지시문/본문/보기/표/그림 블록
  formatted_explanations.json     해설 줄 나누기
  formatted_code_tables.json      code 칸에 들어 있던 파이프 표

서식(사용자 지정)
  글꼴    한글·영문 함초롬돋움, 코드의 영문은 Courier New (코드 안의 한글은 함초롬돋움)
  크기    본문 10pt, 문제 번호 11pt(검정, 굵게)
  줄간격  130%
  쪽 나눔 한 문제가 쪽 경계에서 갈리지 않는다. 한 쪽에 안 들어가면 문제 전체가 다음 쪽으로 간다.

쪽 나눔을 지키는 방법(2단계)
  1단계  모든 문제를 새 쪽에서 시작하게 한 임시 문서를 만들어, 라이브러리의 쪽 배치 추정기로 문제별 높이를 잰다.
  2단계  - 높이가 쪽 본문의 THRESHOLD 이하인 문제: 문제 전체를 '글자처럼 취급' 하는 투명한 1칸 표에 담는다.
           한글은 글자처럼 취급한 표를 쪽 경계에서 나누지 않고 통째로 다음 쪽으로 보낸다.
         - 그보다 큰 문제: 표에 담으면 쪽 밖으로 잘릴 수 있으므로 담지 않고, 새 쪽에서 시작하게 한다
           (문단 모양의 '다음 문단과 함께'·'문단 보호'도 건다).
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

from hwpx import HwpxDocument
from hwpx.layout.pages import estimate_pages

ROOT = os.path.dirname(os.path.abspath(__file__))   # 이 스크립트가 있는 폴더(jcb_restored)
HH = "{http://www.hancom.co.kr/hwpml/2011/head}"
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"


def mm(v):
    """mm -> HWPUNIT (1/7200 inch)"""
    return int(round(v * 7200 / 25.4))


PAGE_W, PAGE_H = 59528, 84186                        # A4
MARGIN_LR = mm(20)
TEXT_W = PAGE_W - 2 * MARGIN_LR                      # 본문 폭 = 쪽 폭 - 좌우 여백
M_TOP, M_BOTTOM, M_HEADER, M_FOOTER = mm(15), mm(15), mm(10), mm(10)
BODY_H = PAGE_H - M_TOP - M_BOTTOM - M_HEADER - M_FOOTER    # 쪽 본문 높이
THRESHOLD = 0.85                                     # 이 비율 이하인 문제만 표에 담는다
SAFE = mm(3)                                         # 문제 칸 안의 표·상자·코드 상자는 칸 폭보다 이만큼 좁게(오른쪽 끝이 잘리지 않게)
AVAIL = TEXT_W - SAFE                                # 문제 칸 안에서 표·상자가 쓸 수 있는 최대 폭
CODE_PAD = mm(3)                                     # 코드 상자 안쪽 여백(상하좌우) 3mm
CODE_INDENT = mm(5)                                  # 코드 상자 왼쪽 들여쓰기


# ---------------------------------------------------------------- 자료
def load_data(only=None):
    files = sorted(
        glob.glob(os.path.join(ROOT, "raw", "*.json")),
        key=lambda p: tuple(int(x) for x in os.path.basename(p)[:-5].split("_")),
    )
    rounds = [json.load(open(f, encoding="utf-8")) for f in files]
    if only:
        keep = set(only)
        for r in rounds:
            r["questions"] = [q for q in r["questions"] if f"{r['year']}-{r['round']}#{q['number']}" in keep]
        rounds = [r for r in rounds if r["questions"]]
    F = json.load(open(os.path.join(ROOT, "formatted_prompts.json"), encoding="utf-8"))
    E = json.load(open(os.path.join(ROOT, "formatted_explanations.json"), encoding="utf-8"))
    C = json.load(open(os.path.join(ROOT, "formatted_code_tables.json"), encoding="utf-8"))
    return rounds, F, E, C


def clean(s):
    """탭 -> 공백 4칸(한글의 탭 위치와 무관하게 들여쓰기가 같게 보이도록). 나머지는 그대로."""
    return (s or "").replace("\t", "    ")


def disp_units(t):
    """한글·전각은 2, 나머지는 1로 센 표시 폭"""
    u = 0
    for ch in t:
        o = ord(ch)
        u += 2 if (0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F or 0xAC00 <= o <= 0xD7AF
                   or 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF or 0x2460 <= o <= 0x24FF
                   or 0x3200 <= o <= 0x32FF or 0x4E00 <= o <= 0x9FFF) else 1
    return u


# ---------------------------------------------------------------- 서식 묶음
class Styles:
    """charPr / paraPr / borderFill 을 한 번만 만들어 두고 이름으로 꺼낸다."""

    def __init__(self, doc):
        self.doc = doc
        self.hdr = doc.oxml.headers[0]
        self._para = {}
        self._normalize_template()
        self.courier = self.hdr.ensure_font("Courier New", lang="LATIN")
        # --- 글자 모양 (모두 검정)
        self.c_body = self._run(size=10)
        self.c_bold = self._run(size=10, bold=True)
        self.c_italic = self._run(size=10, italic=True)
        self.c_qnum = self._run(size=11, bold=True)           # 문제 번호: 11pt, 검정, 굵게
        self.c_title = self._run(size=22, bold=True)
        self.c_sub = self._run(size=14)
        self.c_h1 = self._run(size=15, bold=True)
        self.c_small = self._run(size=9)
        self.c_sep = self._run(size=2)
        self.c_code = self._code_run(size=10)
        # --- 테두리/바탕
        self.bf_code = doc.styles.ensure_border_fill(border_color="#F2F2F2", border_width="0.12 mm", fill_color="#F2F2F2")
        self.bf_sep = doc.styles.ensure_border_fill(border_color="#BFBFBF", border_width="0.12 mm", active_borders=["bottom"])
        self.bf_table = doc.styles.ensure_border_fill(border_color="#555555", border_width="0.15 mm")
        self.bf_box = doc.styles.ensure_border_fill(border_color="#333333", border_width="0.25 mm")
        self.bf_head = self.hdr.ensure_shading_border_fill("#EDEFF2", base_border_fill_id=self.bf_table)
        self.bf_outer = self.bf_sep           # 문제 전체를 담는 표: 아래쪽 가는 회색 줄만 (문제 사이 구분선)

    # ---- 기본 틀(template)의 글꼴을 모두 함초롬돋움으로, 기본 줄간격을 130%로
    def _normalize_template(self):
        for cp in self.hdr.element.iter(HH + "charPr"):
            fr = cp.find(HH + "fontRef")
            for k in ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user"):
                fr.set(k, "0")
        for ls in self.hdr.element.iter(HH + "lineSpacing"):
            ls.set("type", "PERCENT")
            ls.set("value", "130")
            ls.set("unit", "HWPUNIT")

    def _run(self, size, bold=False, italic=False):
        return self.doc.styles.ensure_run(size=size, bold=bold or None, italic=italic or None, base_char_pr_id="1")

    def _code_run(self, size):
        """영문·숫자·기호(LATIN 칸)만 Courier New, 한글·한자·기타는 함초롬돋움"""
        cid = self.doc.styles.ensure_run(size=size, base_char_pr_id="1")
        base = [e for e in self.hdr.element.iter(HH + "charPr") if e.get("id") == cid][0]

        def modifier(cp):
            cp.set("height", base.get("height"))
            cp.find(HH + "fontRef").set("latin", self.courier)

        el = self.hdr.ensure_char_property(
            predicate=lambda e: (e.find(HH + "fontRef").get("latin") == self.courier
                                 and e.get("height") == base.get("height")),
            modifier=modifier, base_char_pr_id=cid)
        return el.get("id")

    # ---- 문단 모양
    def para(self, align="JUSTIFY", left=0, indent=0, prev=0, nxt=0, keep=True, keep_lines=True,
             page_break=False, border=None, code=False):
        key = (align, left, indent, prev, nxt, keep, keep_lines, page_break, border, code)
        if key in self._para:
            return self._para[key]
        brd = None
        if border == "code":
            brd = {"borderFillIDRef": self.bf_code, "offsetLeft": 200, "offsetRight": 200,
                   "offsetTop": 0, "offsetBottom": 0, "connect": "1", "ignoreMargin": "0"}
        elif border == "sep":
            brd = {"borderFillIDRef": self.bf_sep, "offsetLeft": 0, "offsetRight": 0,
                   "offsetTop": 0, "offsetBottom": 0, "connect": "0", "ignoreMargin": "0"}
        pid = self.hdr.ensure_paragraph_format(
            base_para_pr_id="0", alignment=align, line_spacing_percent=130,
            margins={"left": left, "intent": indent, "prev": prev, "next": nxt},
            break_setting={"keep_with_next": keep, "keep_lines": keep_lines,
                           "page_break_before": page_break, "widow_orphan": False},
            border=brd)
        if code:        # 코드 줄은 글자 단위로 줄바꿈(긴 식별자도 여백에서 꺾이게)
            pe = [e for e in self.hdr.element.iter(HH + "paraPr") if e.get("id") == pid][0]
            bs = pe.find(HH + "breakSetting")
            bs.set("breakLatinWord", "BREAK_WORD")
            bs.set("breakNonLatinWord", "BREAK_WORD")
        self._para[key] = pid
        return pid

    def with_gap(self, pid, prev=None, nxt=None):
        """같은 모양에서 문단 앞/뒤 간격만 바꾼 문단 모양 번호 (st.para 로 만든 모양만 가능)"""
        pid = str(pid)
        for key, v in list(self._para.items()):
            if str(v) == pid:
                align, left, indent, p0, n0, keep, keep_lines, page_break, border, code = key
                return self.para(align=align, left=left, indent=indent,
                                 prev=p0 if prev is None else prev, nxt=n0 if nxt is None else nxt,
                                 keep=keep, keep_lines=keep_lines, page_break=page_break, border=border, code=code)
        return None


# ---------------------------------------------------------------- 문단을 놓는 곳
class Sink:
    """문단과 표를 놓는 곳. 본문(BodySink)이거나 표 칸 안(CellSink)이다. keep 은 '다음 문단과 함께' 사용 여부."""

    def __init__(self, st, keep):
        self.st = st
        self.keep = keep

    def para(self, runs, pid):
        p = self.anchor(pid)
        for text, cid in runs:
            p.add_run(text, char_pr_id_ref=cid)
        if not runs:
            p.add_run("", char_pr_id_ref=self.st.c_body)
        return p

    def anchor(self, pid, with_run=False):      # 표·그림을 붙일 빈 문단
        raise NotImplementedError

    def last_p(self):
        """이 곳의 마지막 최상위 문단(lxml 요소)"""
        raise NotImplementedError

    def tighten_last(self, nxt=0):
        """마지막 문단 뒤 간격을 줄인다(그 뒤에 진짜 빈 줄을 따로 넣을 때, 간격이 겹쳐 두 줄 넘게 벌어지지 않게)"""
        p = self.last_p()
        new = self.st.with_gap(p.get("paraPrIDRef"), nxt=nxt)
        if new is not None:
            p.set("paraPrIDRef", str(new))

    def blank(self, keep=None):
        """빈 줄 하나(= 줄바꿈 한 번): 본문 글자 크기·줄 간격 130% 의 빈 문단"""
        k = self.keep if keep is None else keep
        return self.para([("", self.st.c_body)], self.st.para(align="LEFT", prev=0, nxt=0, keep=k, keep_lines=False))


class BodySink(Sink):
    def __init__(self, doc, st, keep):
        super().__init__(st, keep)
        self.doc = doc
        self.in_cell = False

    def anchor(self, pid, with_run=False):
        return self.doc.add_paragraph("", para_pr_id_ref=pid, char_pr_id_ref=self.st.c_body,
                                      include_run=False, inherit_style=False)

    def last_p(self):
        sec = self.doc.sections[-1].element
        return [c for c in sec if c.tag == HP + "p"][-1]


class CellSink(Sink):
    def __init__(self, st, sub, section, doc):
        super().__init__(st, False)
        self.sub, self.section, self.doc = sub, section, doc
        self.in_cell = True

    def anchor(self, pid, with_run=False):
        from hwpx.oxml.paragraph import HwpxOxmlParagraph
        from hwpx.oxml._document_primitives import _default_cell_paragraph_attributes
        attrs = _default_cell_paragraph_attributes()
        attrs["paraPrIDRef"] = str(pid)
        p = self.sub.makeelement(HP + "p", attrs)
        self.sub.append(p)
        return HwpxOxmlParagraph(p, self.section)

    def last_p(self):
        return self.sub.findall(HP + "p")[-1]


def clear_cell(cell):
    sub = cell.element.find(HP + "subList")
    for p in list(sub.findall(HP + "p")):
        sub.remove(p)
    return sub


def cell_margin(cell, left, right, top, bottom):
    cm = cell.element.find(HP + "cellMargin")
    for k, v in (("left", left), ("right", right), ("top", top), ("bottom", bottom)):
        cm.set(k, str(v))
    cell.element.set("hasMargin", "1")


def table_flags(tbl, repeat_header=False, page_break="CELL"):
    t = tbl.element
    t.set("pageBreak", page_break)
    t.set("repeatHeader", "1" if repeat_header else "0")


def table_inmargin(tbl, left, right, top, bottom):
    """표 전체의 기본 안여백. 칸마다 따로 정한 안여백(cellMargin)과 같은 값으로 맞춰 두어, 어느 쪽을 따르는 프로그램에서도 칸의 쓸 수 있는 폭이 같게 한다."""
    im = tbl.element.find(HP + "inMargin")
    for k, v in (("left", left), ("right", right), ("top", top), ("bottom", bottom)):
        im.set(k, str(v))


def code_text_width(line):
    """코드 한 줄의 폭(HWPUNIT, 10pt 기준). 영문·숫자·기호는 Courier New(글자 폭 0.6em), 그 밖은 1em 으로 넉넉히 센다."""
    return sum(600 if ord(ch) < 128 else 1000 for ch in line)


def v_align(cell, how="TOP"):
    cell.element.find(HP + "subList").set("vertAlign", how)


# ---------------------------------------------------------------- 본문 만들기
class Builder:
    def __init__(self, doc, st):
        self.doc = doc
        self.st = st
        self._images = {}
        self.flow_code = False      # 한 쪽보다 큰 문제: 코드 상자를 '글자처럼 취급'하지 않고 쪽 끝에서 나뉠 수 있게

    def text(self, sink, text, cid, pid):
        return sink.para([(text, cid)], pid)

    # ---- 표 (data table)
    def col_widths(self, rows, limit=AVAIL):
        ncol = len(rows[0])
        UNIT, PAD = 620, 1100             # 반각 한 칸 ≈ 6.2pt(10pt 글꼴 + 굵은 머리글 여유), 좌우 여백 합
        nat = [max(disp_units(r[c]) for r in rows) * UNIT + PAD for c in range(ncol)]
        if sum(nat) <= limit:
            return nat
        idx = sorted(range(ncol), key=lambda i: nat[i])
        res = [0] * ncol
        remain, left = limit, idx[:]
        while left:
            share = remain / len(left)
            c = left[0]
            if nat[c] <= share:
                res[c] = nat[c]
                remain -= nat[c]
                left.pop(0)
            else:
                tot = sum(nat[i] for i in left)
                for i in left:
                    res[i] = int(remain * nat[i] / tot)
                break
        return res

    def data_table(self, sink, rows, header=True, caption=None):
        st = self.st
        if caption:
            self.text(sink, clean(caption), st.c_body, st.para(keep=sink.keep, nxt=100))
        widths = self.col_widths(rows)
        nrow, ncol = len(rows), len(rows[0])
        anchor = sink.anchor(st.para(align="LEFT", nxt=500, keep=sink.keep))
        tbl = anchor.add_table(nrow, ncol, width=sum(widths), height=nrow * 1800,
                               border_fill_id_ref=st.bf_table, char_pr_id_ref=st.c_body)
        tbl.set_column_widths(widths)
        table_flags(tbl, repeat_header=header, page_break="CELL")
        table_inmargin(tbl, 510, 510, 200, 200)
        sec = anchor.section
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                cell = tbl.cell(r, c)
                head = header and r == 0
                csink = CellSink(st, clear_cell(cell), sec, self.doc)
                # code=True → 글자 단위 줄바꿈: 칸보다 긴 영문 낱말도 칸 안에서 꺾인다
                csink.para([(clean(text), st.c_bold if head else st.c_body)], st.para(align="LEFT", keep=False, code=True))
                cell_margin(cell, 510, 510, 200, 200)
                v_align(cell, "CENTER")
                if head:
                    tbl.set_cell_border_fill(r, c, st.bf_head)
        return tbl

    # ---- 박스 (테두리 상자 = 1칸짜리 표)
    def box(self, sink, group):
        st = self.st
        anchor = sink.anchor(st.para(align="LEFT", nxt=500, keep=sink.keep))
        tbl = anchor.add_table(1, 1, width=AVAIL, height=1800, border_fill_id_ref=st.bf_box,
                               char_pr_id_ref=st.c_body)
        table_flags(tbl, repeat_header=False, page_break="CELL")
        table_inmargin(tbl, 800, 800, 500, 500)
        cell = tbl.cell(0, 0)
        cell_margin(cell, 800, 800, 500, 500)
        v_align(cell, "TOP")
        csink = CellSink(st, clear_cell(cell), anchor.section, self.doc)
        n = len(group)
        for gi, g in enumerate(group):
            last_block = gi == n - 1
            if g["kind"] == "image":
                self.picture(csink, g, last_block)
                continue
            lines = g["lines"]
            for li, t in enumerate(lines):
                last_line = li == len(lines) - 1
                nxt = (0 if last_block else 500) if last_line else 100
                csink.para([(clean(t), st.c_body)], st.para(align="JUSTIFY", nxt=nxt, keep=False))
        return tbl

    def picture(self, csink, g, last_block):
        st = self.st
        data = open(os.path.join(ROOT, g["file"]), "rb").read()
        item = self._images.get(g["file"])
        if item is None:
            item = self._images[g["file"]] = self.doc.media.add_image(data, "png")
        pw, ph = g["w"], g["h"]
        # 원본 PNG 는 2배 해상도 -> 96dpi 화면 기준 폭 최대 560px·높이 최대 400px (build_docx.js 와 같은 비율)
        box_inner = AVAIL - 2 * 800                       # 그림이 놓이는 상자 칸의 안쪽 폭
        max_w_px = min(560, (box_inner - mm(2)) / 75)     # 칸 안쪽 폭보다 2mm 더 좁게
        sc = min(0.5, max_w_px / pw, 400 / ph)
        w_u, h_u = int(round(pw * sc * 75)), int(round(ph * sc * 75))     # 1px(96dpi) = 75 HWPUNIT
        pic_p = csink.anchor(st.para(align="CENTER", prev=100, nxt=100, keep=False))
        pic_p.add_picture(str(item), width=w_u, height=h_u, char_pr_id_ref=st.c_body)
        csink.para([(g.get("caption") or "", st.c_small)],
                   st.para(align="CENTER", nxt=0 if last_block else 500, keep=False))

    # ---- 문제 지문 블록
    def prompt_blocks(self, sink, blocks):
        st = self.st
        i = 0
        while i < len(blocks):
            b = blocks[i]
            if b["kind"] == "table":
                self.data_table(sink, b["rows"], header=b.get("header", True) is not False, caption=b.get("caption"))
                i += 1
                continue
            if b.get("box"):
                grp = []
                while i < len(blocks) and blocks[i].get("box") and blocks[i]["kind"] != "table":
                    grp.append(blocks[i])
                    i += 1
                self.box(sink, grp)
                continue
            lines = b["lines"]
            for li, t in enumerate(lines):
                last = li == len(lines) - 1
                left = mm(6.35) if b["kind"] == "opt" else 0
                self.text(sink, clean(t), st.c_body, st.para(align="JUSTIFY", left=left, nxt=500 if last else 100, keep=sink.keep))
            i += 1

    def code_block(self, sink, code):
        """코드: 글자 폭에 맞춘 회색 상자(1칸 표). 안쪽 여백은 상하좌우 3mm, 가로는 가장 긴 줄 + 약간."""
        st = self.st
        lines = clean(code).split("\n")
        want = max(code_text_width(ln) for ln in lines) + 2 * CODE_PAD + 400    # 가장 긴 줄 + 여백 3mm×2 + 약간(400 ≈ 1.4mm)
        indent = max(0, min(CODE_INDENT, AVAIL - want))            # 5mm 들여쓰기가 줄을 꺾이게 만들면 들여쓰기를 줄인다
        width = min(AVAIL - indent, want)
        anchor = sink.anchor(st.para(align="LEFT", left=indent, nxt=500, keep=sink.keep))
        tbl = anchor.add_table(1, 1, width=width, height=1800, border_fill_id_ref=st.bf_code,
                               char_pr_id_ref=st.c_code)
        table_flags(tbl, repeat_header=False, page_break="CELL")
        table_inmargin(tbl, CODE_PAD, CODE_PAD, CODE_PAD, CODE_PAD)
        cell = tbl.cell(0, 0)
        cell_margin(cell, CODE_PAD, CODE_PAD, CODE_PAD, CODE_PAD)
        v_align(cell, "TOP")
        if self.flow_code:
            tbl.set_treat_as_char(False)
        csink = CellSink(st, clear_cell(cell), anchor.section, self.doc)
        pid = st.para(align="LEFT", keep=False, code=True)        # 글자 단위 줄바꿈(상자보다 긴 줄은 상자 안에서 꺾인다)
        for line in lines:
            csink.para([(line, st.c_code)], pid)
        return tbl

    def label_line(self, sink, label, text):
        st = self.st
        sink.para([(label + " ", st.c_bold), (clean(text), st.c_body)], st.para(align="JUSTIFY", nxt=300, keep=sink.keep))

    def answer(self, sink, ans):
        st = self.st
        lines = clean(ans).split("\n")
        if len(lines) == 1:
            self.label_line(sink, "정답:", lines[0])
            return
        sink.para([("정답:", st.c_bold)], st.para(align="LEFT", nxt=100, keep=sink.keep))
        for k, t in enumerate(lines):
            last = k == len(lines) - 1
            self.text(sink, t, st.c_body, st.para(align="LEFT", left=mm(6.35), nxt=300 if last else 100, keep=sink.keep))

    def explanation(self, sink, el):
        st = self.st
        if len(el) <= 1:
            self.label_line(sink, "해설:", el[0] if el else "")
            return
        sink.para([("해설:", st.c_bold)], st.para(align="LEFT", nxt=100, keep=sink.keep))
        for k, t in enumerate(el):
            last = k == len(el) - 1
            self.text(sink, clean(t), st.c_body, st.para(align="JUSTIFY", left=mm(6.35), nxt=300 if last else 100, keep=sink.keep))

    # ---- 문제 하나
    def question(self, sink, r, q, F, E, C, new_page=False, top_gap=0):
        st = self.st
        key = f"{r['year']}-{r['round']}#{q['number']}"
        lang = "이론" if (not q.get("language") or q["language"] == "기타") else q["language"]
        diff = f" · 난이도 {q['difficulty']}" if q.get("difficulty") else ""
        # 문제 번호: 11pt, 검정, 굵게
        self.text(sink, f"{r['year']}-{r['round']} 문제 {q['number']} ({lang}{diff})", st.c_qnum,
                  st.para(align="LEFT", prev=top_gap, nxt=0, keep=sink.keep, page_break=new_page))
        sink.blank()                                   # 문제 번호 ↔ 문제 본문: 빈 줄 하나
        blocks = F.get(key)
        if blocks is None:
            raise RuntimeError("formatted prompt missing: " + key)
        self.prompt_blocks(sink, blocks)
        ct = C.get(key)
        code = (q.get("code") or "").rstrip("\n")
        if ct:
            self.data_table(sink, ct, header=True, caption=None)
        elif code.strip():
            self.code_block(sink, code)
        sink.tighten_last(0)
        sink.blank()                                   # 문제 본문 ↔ 정답: 빈 줄 하나
        self.answer(sink, q.get("answer") or "")
        expl = (q.get("explanation") or "").strip()
        if expl:
            self.explanation(sink, E.get(key) or [expl])
        sink.tighten_last(0)
        sink.blank()                                   # 구분선 바로 위: 빈 줄 하나

    def wrapped_question(self, bsink, r, q, F, E, C):
        """문제 전체를 '글자처럼 취급' 하는 투명한 1칸 표에 담는다. 아래쪽 가는 회색 줄이 문제 구분선이다."""
        st = self.st
        anchor = bsink.anchor(st.para(align="LEFT", nxt=0, keep=False))
        outer = anchor.add_table(1, 1, width=TEXT_W, height=1800, border_fill_id_ref=st.bf_outer,
                                 char_pr_id_ref=st.c_body)
        table_flags(outer, repeat_header=False, page_break="CELL")
        table_inmargin(outer, 0, 0, 100, 0)
        cell = outer.cell(0, 0)
        cell_margin(cell, 0, 0, 100, 0)
        v_align(cell, "TOP")
        csink = CellSink(st, clear_cell(cell), anchor.section, self.doc)
        self.question(csink, r, q, F, E, C, new_page=False, top_gap=200)

    def separator(self, sink):
        st = self.st
        sink.para([("", st.c_sep)], st.para(align="LEFT", prev=0, nxt=0, keep=False, border="sep"))


# ---------------------------------------------------------------- 문서
def build(rounds, F, E, C, plan=None, today=None):
    """plan: {문항 키: 'wrap' | 'flat'} — None 이면 전부 'flat' + 새 쪽에서 시작(1단계 측정용)"""
    measuring = plan is None
    doc = HwpxDocument.new()
    st = Styles(doc)
    b = Builder(doc, st)
    body = BodySink(doc, st, keep=False)
    flat = BodySink(doc, st, keep=True)

    doc.page.setup(paper_size="A4", orientation="PORTRAIT",
                   margin_left_mm=20, margin_right_mm=20, margin_top_mm=15, margin_bottom_mm=15,
                   header_margin_mm=10, footer_margin_mm=10, gutter_mm=0)

    total_q = sum(len(r["questions"]) for r in rounds)
    total_img = sum(len(r.get("image_only_questions", [])) for r in rounds)

    # ---- 표지/개요
    b.text(body, "정보처리기사 실기 복원문제 모음", st.c_title, st.para(align="LEFT", nxt=600, keep=False))
    b.text(body, "2020년 1회 ~ 2026년 2회", st.c_sub, st.para(align="LEFT", nxt=1200, keep=False))
    b.text(body, "출처 및 라이선스", st.c_h1, st.para(align="LEFT", nxt=500, keep=True))
    b.label_line(body, "원저작자:", "Life-Journey (블로그: chobopark.tistory.com)")
    b.label_line(body, "라이선스:", "CC BY (저작자표시) — 2020년 1회 글과 2026년 2회 글에서 직접 확인했으며, 같은 블로그의 나머지 글도 동일한 설정일 것으로 추정(개별 재확인은 하지 않음)")
    b.label_line(body, "수집 방법:", "각 회차 블로그 글을 AI 웹 열람 도구로 읽어 받아쓰기(transcribe)함. 원문 HTML을 직접 대조한 완전 검증은 아니며, 일부 코드 문제는 사용자가 보유한 별도의 독립적 자료(다른 저자의 기출풀이집)와 대조해 일치를 확인함.")
    b.label_line(body, "보완 이력:", "2026-10-08 원문 페이지와 2차 대조하여 165문항을 보완함 — 표·그림이 빠져 있던 57문항(A), 보기·본문이 빠져 있던 79문항(B), 이미지 전용이라 제외했던 13문항을 새로 추가(C), 원문과 표기가 달랐던 16문항(D, 표기 차이는 원문대로 반영. 다만 문제 풀이를 틀어지게 하는 코드 오타는 고침: 2020-1 문제 6·2022-3 문제 12의 'SELECT DERP'는 'SELECT DEPT'로 수정). 표는 진짜 표로 옮겼고, 그림은 원문을 보고 다시 그려 '▲ 원문 그림을 보고 다시 그린 도식'이라고 표시함(원문 그림과 세부 모양·배치가 다를 수 있으니 원문 링크로 확인). 원문 페이지 자체에 보기가 실려 있지 않은 문항은 '(실제 기출문제에서는 보기가 주어집니다)' 같은 원문 안내만 남아 있음.")
    scope = f"총 {len(rounds)}개 회차, {total_q}문제 수집" + (
        f" / {total_img}문제는 원문이 이미지(표·다이어그램)로만 되어 있어 제외" if total_img else
        " (원문이 표·그림으로만 되어 있던 문제도 표는 표로, 그림은 다시 그려 포함)")
    b.label_line(body, "수집 범위:", scope)
    body.para([("주의: 이 문서는 학습 참고용으로 정리한 것이며, 정답의 정확성을 100% 보장하지 않습니다. 실제 복원문제 특성상(응시자의 기억에 의존) 원 시험과 세부 표현이 다를 수 있습니다.", st.c_italic)],
              st.para(align="JUSTIFY", nxt=1000, keep=False))

    # ---- 목차
    b.text(body, "목차", st.c_h1, st.para(align="LEFT", nxt=500, keep=True))
    for r in rounds:
        n_img = len(r.get("image_only_questions", []))
        label = f"•  {r['year']}년 {r['round']}회 — {len(r['questions'])}문제" + (f", 이미지 문제 {n_img}개 제외" if n_img else "")
        b.text(body, label, st.c_body, st.para(align="LEFT", left=mm(3), nxt=100, keep=False))

    # ---- 회차별 본문
    for r in rounds:
        b.text(body, f"{r['year']}년 {r['round']}회 실기 복원문제", st.c_h1,
               st.para(align="LEFT", nxt=500, keep=True, page_break=True))
        body.para([("원문: ", st.c_bold), (r["source_url"], st.c_body)], st.para(align="LEFT", nxt=100, keep=True))
        body.para([("저작자/라이선스: ", st.c_bold), (f"{r['source_author']} · {r['license']}", st.c_body)],
                  st.para(align="LEFT", nxt=500, keep=True))
        img_list = r.get("image_only_questions", [])
        if img_list:
            nums = ", ".join(str(n) for n in img_list)
            b.text(body, f"※ {nums}번 문제는 원문이 표/다이어그램 이미지로만 제공되어 이 문서에서는 제외했습니다. 원문 링크에서 직접 확인하세요.",
                   st.c_body, st.para(align="JUSTIFY", nxt=800, keep=False))
        else:
            body.para([], st.para(align="LEFT", keep=False))

        for qi, q in enumerate(r["questions"]):
            key = f"{r['year']}-{r['round']}#{q['number']}"
            mode = "flat_new" if measuring else plan.get(key, "flat_new")
            if mode == "wrap":
                b.wrapped_question(body, r, q, F, E, C)
            elif mode == "flow":
                # 한 쪽에 다 들어가지 않는 문제(어쩔 수 없이 두 쪽에 걸침): 새 쪽에서 시작하고 코드는 쪽 끝에서 줄 사이로 나뉘게 한다
                b.flow_code = True
                b.question(body, r, q, F, E, C, new_page=True, top_gap=0)
                b.flow_code = False
                b.separator(body)
            else:
                # 새 쪽에서 시작하고, 문제 안의 문단은 서로 '다음 문단과 함께' 로 묶는다.
                b.question(flat, r, q, F, E, C, new_page=True, top_gap=0)
                b.separator(flat)
            # 구분선 바로 아래: 빈 줄 하나. 다음 문제가 '새 쪽에서 시작'(flat)이면 빈 줄을 넣지 않는다 —
            # 이전 문제가 쪽 끝까지 차 있으면 빈 줄이 다음 쪽으로 넘어가고, 거기에 쪽 나눔이 겹쳐 빈 쪽이 생기기 때문이다.
            if qi < len(r["questions"]) - 1:
                nq = r["questions"][qi + 1]
                nmode = "flat_new" if measuring else plan.get(f"{r['year']}-{r['round']}#{nq['number']}", "flat_new")
                if nmode == "wrap":
                    body.blank(keep=False)

    # ---- 머리글·쪽번호
    doc.page.set_header(text="정보처리기사 실기 복원문제 모음 (2020-2026)")
    doc.page.set_page_number(target="footer", align="CENTER", position="BOTTOM_CENTER")
    finish_header_footer(doc, st)

    # ---- 문서 정보
    now = (today or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc.parts.clear_document_metadata(keep=("title", "language"))
    doc.parts.set_document_metadata(
        title="정보처리기사 실기 복원문제 모음 (2020-2026)",
        creator="원저작자 Life-Journey (chobopark.tistory.com, CC BY)",
        subject="정보처리기사 실기 복원문제 2020년 1회 ~ 2026년 2회",
        created_date=now, modified_date=now)
    return doc


def finish_header_footer(doc, st):
    """머리말: 오른쪽 맞춤·9pt, 꼬리말(쪽 번호): 가운데·9pt, 글꼴은 함초롬돋움."""
    right = st.para(align="RIGHT", keep=False)
    center = st.para(align="CENTER", keep=False)
    sec = doc.sections[0]
    for tag, pid in (("header", right), ("footer", center)):
        for node in sec.element.iter(HP + tag):
            for p in node.iter(HP + "p"):
                p.set("paraPrIDRef", str(pid))
                for run in p.iter(HP + "run"):
                    run.set("charPrIDRef", str(st.c_small))
    sec.mark_dirty()


# ---------------------------------------------------------------- 1단계: 문제별 높이 측정
QHEAD_RE = None


def measure_heights(doc):
    """모든 문제가 새 쪽에서 시작하는 임시 문서에서 문제별 높이(HWPUNIT)를 잰다.
    문제가 한 쪽을 넘으면 (쪽 수 차이 × 본문 높이 + 마지막 줄 위치)로 계산한다."""
    from verify_hwpx import question_units
    est = estimate_pages(doc)
    if est.pages is None:
        raise RuntimeError("쪽 추정 불가: " + "; ".join(est.unsupported))
    top, groups = question_units(doc)
    heights = {}
    for g in groups:
        first = est.lines[g["start"]][0]
        last = est.lines[g["end"]][-1]
        assert first.vertpos == 0, (g["key"], first)       # 새 쪽에서 시작했는지(측정 전제)
        heights[g["key"]] = (last.page - first.page) * BODY_H + last.vertpos + 1100
    return heights


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "정보처리기사_실기_복원문제_2020-2026"))
    ap.add_argument("--only", nargs="*", help="특정 문항 키만 (예: 2020-1#6)")
    ap.add_argument("--formats", default="hwpx,hwp")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--plan", default=None, help="측정 결과를 저장/재사용할 JSON 경로")
    args = ap.parse_args()

    rounds, F, E, C = load_data(args.only)
    if args.plan and os.path.exists(args.plan):
        heights = json.load(open(args.plan, encoding="utf-8"))
        print("측정 결과 재사용:", args.plan)
    else:
        print("1단계: 문제별 높이 측정 …")
        heights = measure_heights(build(rounds, F, E, C, plan=None))
        if args.plan:
            json.dump(heights, open(args.plan, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    limit = args.threshold * BODY_H
    plan = {k: ("wrap" if h <= limit else ("flow" if h > BODY_H else "flat")) for k, h in heights.items()}
    n_wrap = sum(1 for v in plan.values() if v == "wrap")
    tall = [k for k, h in heights.items() if h > BODY_H]
    print(f"문제 {len(plan)}개: 표에 담음 {n_wrap}개, 새 쪽에서 시작 {len(plan) - n_wrap}개 "
          f"(그중 한 쪽 초과 {len(tall)}개 {tall[:12]})")
    if tall:
        print("  ※ 한 쪽을 넘는 문제는 두 쪽에 걸칠 수밖에 없다 →", tall)
    print(f"가장 큰 문제 높이 {max(heights.values()) / BODY_H:.2f}쪽 분량")

    print("2단계: 문서 만들기 …")
    doc = build(rounds, F, E, C, plan=plan)
    for fmt in args.formats.split(","):
        path = f"{args.out}.{fmt}"
        doc.save_to_path(path)
        print("saved", path, os.path.getsize(path), "bytes")


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    main()
