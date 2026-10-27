#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_hwpx.py 결과물 검증.

 1) 패키지/열림 안전 검증기
 2) 문제 단위 쪽 나눔: 라이브러리의 쪽 배치 추정기(estimate_pages)로 문제(번호~구분선)가 두 쪽에 걸치는지 센다
 3) 서식 감사: 모든 문단·글자·표의 실제 서식 값이 지정 사양과 같은지
 4) .hwp 를 다시 열어 .hwpx 와 내용·서식이 같은지(문단·표·그림 수, 글자 서식 전부)
 5) 원본 데이터와 대조: 문항 수, 문제별 정답·해설 텍스트가 문서에 들어 있는지
"""
import collections
import glob
import json
import os
import re
import sys

from hwpx import HwpxDocument, validate_editor_open_safety, validate_package
from hwpx.layout.pages import estimate_pages, _Measure, _inline_table_height

HH = "{http://www.hancom.co.kr/hwpml/2011/head}"
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
ROOT = os.path.dirname(os.path.abspath(__file__))   # 이 스크립트가 있는 폴더(jcb_restored)
BODY_H = 70012
QHEAD = re.compile(r"^(\d{4})-(\d) 문제 (\d+) \(")


def props(doc):
    hdr = doc.oxml.headers[0].element
    chars = {c.get("id"): c for c in hdr.iter(HH + "charPr")}
    paras = {p.get("id"): p for p in hdr.iter(HH + "paraPr")}
    faces = {}
    for ff in hdr.iter(HH + "fontface"):
        faces[ff.get("lang")] = {f.get("id"): f.get("face") for f in ff.findall(HH + "font")}
    return hdr, chars, paras, faces


def char_desc(chars, faces, cid):
    c = chars[cid]
    fr = c.find(HH + "fontRef")
    return dict(
        size=int(c.get("height")) / 100,
        bold=c.find(HH + "bold") is not None,
        italic=c.find(HH + "italic") is not None,
        color=c.get("textColor"),
        hangul=faces["HANGUL"][fr.get("hangul")],
        latin=faces["LATIN"][fr.get("latin")],
        other=faces["OTHER"][fr.get("other")],
        symbol=faces["SYMBOL"][fr.get("symbol")],
    )


def para_desc(paras, pid):
    p = paras[pid]
    bs = p.find(HH + "breakSetting")
    ls = [x for x in p.iter(HH + "lineSpacing")]
    return dict(
        line=(ls[0].get("type"), ls[0].get("value")),
        keep_next=bs.get("keepWithNext") == "1",
        keep_lines=bs.get("keepLines") == "1",
        pbb=bs.get("pageBreakBefore") == "1",
    )


def in_hf(p):
    """머리말·꼬리말 안의 문단인가"""
    return any(a.tag in (HP + "header", HP + "footer") for a in p.iterancestors())


def all_paragraphs(root, with_hf=True):
    """문서 안의 모든 hp:p (표 칸 안 포함). with_hf=False 면 머리말·꼬리말 안 문단은 뺀다"""
    ps = list(root.iter(HP + "p"))
    return ps if with_hf else [p for p in ps if not in_hf(p)]


def audit(doc, label):
    hdr, chars, paras, faces = props(doc)
    root = doc.sections[0].element
    bad = collections.Counter()
    sizes = collections.Counter()
    fonts = collections.Counter()
    for p in all_paragraphs(root):
        pd = para_desc(paras, p.get("paraPrIDRef"))
        if pd["line"] != ("PERCENT", "130"):
            bad["줄간격이 130%가 아님"] += 1
        for r in p.findall(HP + "run"):
            t = "".join(r.itertext())
            if not t.strip() and r.find(HP + "tbl") is None and r.find(HP + "pic") is None:
                continue
            cd = char_desc(chars, faces, r.get("charPrIDRef"))
            sizes[cd["size"]] += 1
            fonts[(cd["hangul"], cd["latin"])] += 1
            if cd["color"] not in ("#000000",):
                bad[f"글자색 {cd['color']}"] += 1
            if cd["hangul"] != "함초롬돋움":
                bad["한글 글꼴이 함초롬돋움이 아님"] += 1
            if cd["latin"] not in ("함초롬돋움", "Courier New"):
                bad["영문 글꼴 이상"] += 1
    print(f"[{label}] 글자 크기 분포(pt→런 수):", dict(sorted(sizes.items())))
    print(f"[{label}] 글꼴 조합(한글,영문→런 수):", dict(fonts))
    print(f"[{label}] 서식 위반:", dict(bad) if bad else "없음")
    return not bad


def unit_of_top(p, chars, faces):
    """최상위 문단 하나가 '표에 담은 문제'면 (키, 바깥 표) 를, 아니면 None"""
    for r in p.findall(HP + "run"):
        for t in r.findall(HP + "tbl"):
            first = next(iter(t.iter(HP + "p")), None)
            if first is None:
                continue
            text = "".join(first.itertext()).strip()
            m = QHEAD.match(text)
            run = first.find(HP + "run")
            if m and run is not None and char_desc(chars, faces, run.get("charPrIDRef"))["size"] == 11.0:
                return f"{m.group(1)}-{m.group(2)}#{m.group(3)}", t
    return None


def question_units(doc):
    """최상위 문단을 문제 단위로 묶는다.
       - 'wrap': 문제 전체가 바깥 표 한 칸에 든 문단 하나
       - 'flat': 번호 줄(11pt) ~ 구분선(2pt 문단) 까지의 문단들"""
    hdr, chars, paras, faces = props(doc)
    root = doc.sections[0].element
    top = [p for p in root if p.tag == HP + "p"]
    units = []
    cur = None
    for i, p in enumerate(top):
        w = unit_of_top(p, chars, faces)
        first = p.find(HP + "run")
        text = "".join(p.itertext()).strip()
        m = QHEAD.match(text)
        cid = first.get("charPrIDRef") if first is not None else None
        if w is not None:
            units.append(dict(kind="wrap", key=w[0], start=i, end=i, table=w[1]))
            cur = None
        elif m and cid is not None and char_desc(chars, faces, cid)["size"] == 11.0:
            cur = dict(kind="flat", key=f"{m.group(1)}-{m.group(2)}#{m.group(3)}", start=i, end=i)
            units.append(cur)
        elif cur is not None:
            cur["end"] = i
            if cid is not None and char_desc(chars, faces, cid)["size"] == 2.0:
                cur = None            # 구분선에서 이 문제가 끝난다
    return top, units


def page_check(doc, label, limit=0.90, plan_path=None):
    """문제가 두 쪽에 걸치는지, 표에 담은 문제가 한 쪽을 넘는지 (라이브러리의 쪽 배치 추정기 기준)"""
    est = estimate_pages(doc)
    if est.pages is None:
        print(f"[{label}] 쪽 추정 불가:", est.unsupported)
        return False
    lines = est.lines
    top, units = question_units(doc)
    body_h = BODY_H
    meas = _Measure(getattr(doc, "_root"))
    split, tall, firsts, known = [], [], [], []
    kinds = collections.Counter(u["kind"] for u in units)
    over = set()                       # 한 쪽보다 커서 두 쪽에 걸칠 수밖에 없는 문제 (1단계 측정값 기준)
    if plan_path and os.path.exists(plan_path):
        over = {k for k, h in json.load(open(plan_path, encoding="utf-8")).items() if h > body_h}
    for u in units:
        pages = set()
        for i in range(u["start"], u["end"] + 1):
            for ln in lines[i]:
                pages.add(ln.page)
        if len(pages) > 1:
            if u["key"] in over:
                known.append((u["key"], (min(pages) + 1, max(pages) + 1)))
            else:
                split.append((u["key"], (min(pages) + 1, max(pages) + 1)))
        if u["kind"] == "wrap":
            h = _inline_table_height(meas, u["table"])
            if h > body_h * limit:
                tall.append((u["key"], round(h / body_h, 3)))
        else:
            # 새 쪽에서 시작하는 문제여야 한다: 번호 줄이 쪽의 맨 위에 있는가
            first_line = lines[u["start"]][0]
            firsts.append((u["key"], first_line.vertpos))
    flat_not_top = [(k, v) for k, v in firsts if v != 0]
    print(f"[{label}] 추정 쪽수 {est.pages}쪽 | 문제 {len(units)}개 (표에 담음 {kinds['wrap']}, 새 쪽 시작 {kinds['flat']})")
    print(f"[{label}] 쪽 경계에 걸친 문제 {len(split)}개, 표 높이가 본문의 {int(limit*100)}% 초과 {len(tall)}개, "
          f"새 쪽 시작이어야 하는데 쪽 맨 위가 아닌 문제 {len(flat_not_top)}개")
    for k, s in split[:40]:
        print("   걸침:", k, f"{s[0]}~{s[1]}쪽")
    for k, s in known:
        print("   (한 쪽보다 커서 불가피) 걸침:", k, f"{s[0]}~{s[1]}쪽")
    for k, h in tall[:40]:
        print("   표가 큼:", k, h)
    for k, v in flat_not_top[:40]:
        print("   쪽 맨 위 아님:", k, v)
    return not split and not tall and not flat_not_top


def para_left_margins(hdr):
    """paraPr id → 왼쪽 여백(HWPUNIT). 한/글 2014+ 가 읽는 hp:case 쪽 값."""
    HC = "{http://www.hancom.co.kr/hwpml/2011/core}"
    HPN = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
    out = {}
    for pp in hdr.iter(HH + "paraPr"):
        left = 0
        case = next((c for c in pp.iter(HPN + "case")), None)
        scope = case if case is not None else pp
        m = next((x for x in scope.iter(HH + "margin")), None)
        if m is not None:
            l = m.find(HC + "left")
            if l is not None:
                left = int(l.get("value"))
        out[pp.get("id")] = left
    return out


def code_text_width(line):
    return sum(600 if ord(ch) < 128 else 1000 for ch in line)


def fit_check(doc, label, text_w=48190, min_slack=800, pad=850):
    """표·그림·상자·코드 상자가 담긴 칸의 안쪽 폭 안에 들어오는지(여유 min_slack 이상), 코드 상자 폭이 내용에 맞는지"""
    hdr, chars, paras, faces = props(doc)
    left_of = para_left_margins(hdr)
    root = doc.sections[0].element
    bad = collections.Counter()
    ex = collections.defaultdict(list)

    def note(kind, what):
        bad[kind] += 1
        if len(ex[kind]) < 5:
            ex[kind].append(what)

    n_tbl = n_pic = n_code = 0
    min_seen = 10 ** 9
    for el in list(root.iter(HP + "tbl")) + list(root.iter(HP + "pic")):
        if in_hf(el):
            continue
        kind = etree_local(el)
        w = int(el.find(HP + "sz").get("width"))
        tc = next((a for a in el.iterancestors() if a.tag == HP + "tc"), None)
        anchor_p = next((a for a in el.iterancestors() if a.tag == HP + "p"), None)
        indent = left_of.get(anchor_p.get("paraPrIDRef"), 0) if anchor_p is not None else 0
        if tc is None:
            inner = text_w
        else:
            cw = int(tc.find(HP + "cellSz").get("width"))
            cm = tc.find(HP + "cellMargin")
            tbl = tc.getparent().getparent()
            im = tbl.find(HP + "inMargin")
            m1 = int(cm.get("left")) + int(cm.get("right"))
            m2 = int(im.get("left")) + int(im.get("right"))
            inner = cw - max(m1, m2) if tc.get("hasMargin") == "1" else cw - m2
        first = next(el.iter(HP + "p"), None)
        is_outer = kind == "tbl" and first is not None and QHEAD.match("".join(first.itertext()).strip())
        if is_outer:
            continue                                   # 문제 전체를 담는 바깥 표는 칸 폭 전체를 쓴다
        slack = inner - indent - w
        min_seen = min(min_seen, slack)
        if kind == "tbl":
            n_tbl += 1
        else:
            n_pic += 1
        if slack < min_slack:
            note("칸 폭에 여유가 부족(오른쪽이 잘릴 수 있음)", (kind, w, inner, indent, slack))
        # 코드 상자: 회색 칸(글꼴 Courier New)
        if kind == "tbl" and first is not None:
            run = first.find(HP + "run")
            if run is not None and char_desc(chars, faces, run.get("charPrIDRef"))["latin"] == "Courier New":
                n_code += 1
                cm = el.find(f"{HP}tr/{HP}tc/{HP}cellMargin")
                if [int(cm.get(k)) for k in ("left", "right", "top", "bottom")] != [pad] * 4:
                    note("코드 상자 안쪽 여백이 3mm가 아님", [cm.get(k) for k in ("left", "right", "top", "bottom")])
                lines = ["".join(p.itertext()) for p in el.iter(HP + "p")]
                need = max(code_text_width(x) for x in lines)
                room = w - 2 * pad
                capped = w >= text_w - 3000
                if room < need and not capped:
                    note("코드 상자가 가장 긴 줄보다 좁음", (w, need))
                if room - need > 1200 and not capped:
                    note("코드 상자가 내용보다 불필요하게 넓음", (w, need))
    print(f"[{label}] 폭 점검: 표 {n_tbl}·그림 {n_pic}개 (그중 코드 상자 {n_code}개), 가장 빠듯한 여유 {min_seen} HWPUNIT ({min_seen/283.46:.1f}mm) →",
          "모두 통과" if not bad else dict(bad))
    for k, v in ex.items():
        print("    ", k, v)
    return not bad


def etree_local(e):
    return e.tag.split("}")[1]


def is_blank(p):
    """글자도 표·그림도 없는 빈 문단인가"""
    if "".join(p.itertext()).strip():
        return False
    return next(p.iter(HP + "tbl"), None) is None and next(p.iter(HP + "pic"), None) is None


def spacing_check(doc, label):
    """요청한 빈 줄(줄바꿈 한 번)이 문제마다 정확히 한 줄씩 있는지:
       ① 문제 번호 ↔ 본문  ② 본문 ↔ 정답  ③ 구분선 위  ④ 구분선 아래(회차 마지막 문제 제외)  ⑤ 빈 줄이 연달아 두 줄 이상 없음"""
    top, units = question_units(doc)
    bad = collections.Counter()
    ex = collections.defaultdict(list)

    def note(kind, key):
        bad[kind] += 1
        if len(ex[kind]) < 5:
            ex[kind].append(key)

    def check_seq(key, seq, kind_end):
        # seq: 문제 안 최상위 문단 목록 (번호 줄부터 구분선 위 빈 줄까지)
        if len(seq) < 5:
            note("문단이 너무 적음", key); return
        if not is_blank(seq[1]):
            note("① 번호 뒤 빈 줄 없음", key)
        if len(seq) > 2 and is_blank(seq[2]):
            note("⑤ 번호 뒤 빈 줄이 둘 이상", key)
        ai = next((i for i, p in enumerate(seq) if "".join(p.itertext()).strip().startswith("정답:")), None)
        if ai is None:
            note("정답 문단 없음", key)
        else:
            if ai < 1 or not is_blank(seq[ai - 1]):
                note("② 정답 앞 빈 줄 없음", key)
            elif ai >= 2 and is_blank(seq[ai - 2]):
                note("⑤ 정답 앞 빈 줄이 둘 이상", key)
        if not is_blank(seq[-1]):
            note("③ 구분선 위 빈 줄 없음", key)
        elif is_blank(seq[-2]):
            note("⑤ 구분선 위 빈 줄이 둘 이상", key)
        # 문제 안에서 연달아 빈 문단
        for a, b in zip(seq, seq[1:]):
            if is_blank(a) and is_blank(b):
                note("⑤ 연속된 빈 문단", key); break

    for n, u in enumerate(units):
        if u["kind"] == "wrap":
            cell = u["table"].find(f"{HP}tr/{HP}tc/{HP}subList")
            seq = cell.findall(HP + "p")
            check_seq(u["key"], seq, "wrap")
            after = u["end"] + 1
        else:
            seq = top[u["start"]:u["end"]]            # 구분선 문단은 뺀다
            check_seq(u["key"], seq, "flat")
            after = u["end"] + 1
        # ④ 구분선 아래: 다음 문제가 표에 담긴 문제면 빈 줄 하나, 새 쪽에서 시작하는 문제나 회차 제목이면 빈 줄 없음
        #    (새 쪽 시작 앞에 빈 줄이 있으면, 쪽 끝에서 넘어가 빈 쪽이 생길 수 있다)
        nxt = top[after] if after < len(top) else None
        if nxt is None:
            continue
        txt = "".join(nxt.itertext()).strip()
        nu = units[n + 1] if n + 1 < len(units) else None
        if re.match(r"^\d{4}년 \d회 실기 복원문제$", txt):
            pass
        elif is_blank(nxt):
            if nu is None or nu["kind"] != "wrap" or nu["start"] != after + 1:
                note("④ 새 쪽 시작 앞에 빈 줄(빈 쪽 위험)", u["key"])
        else:
            if nu is None or nu["kind"] != "flat" or nu["start"] != after:
                note("④ 구분선 아래 빈 줄 없음", u["key"])
    print(f"[{label}] 빈 줄 점검: 문제 {len(units)}개 → ", "모두 통과" if not bad else dict(bad))
    for k, v in ex.items():
        print("    ", k, v)
    return not bad


def leaf_texts(root):
    """머리말·꼬리말을 뺀 모든 '잎' 문단(안에 다른 문단이 없는 것)의 텍스트, 문서 순서대로"""
    return ["".join(p.itertext()) for p in leaf_paragraphs(root)]


def structure(doc):
    root = doc.sections[0].element
    ps = all_paragraphs(root, with_hf=False)
    return dict(
        paragraphs=len(ps),
        tables=len(list(root.iter(HP + "tbl"))),
        pics=len(list(root.iter(HP + "pic"))),
        text="\n".join("".join(p.itertext()) for p in leaf_paragraphs(root)),
    )


def leaf_paragraphs(root):
    res = []
    for p in root.iter(HP + "p"):
        if in_hf(p):
            continue
        if any(x is not p for x in p.iter(HP + "p")):
            continue
        res.append(p)
    return res


def resolved_runs(doc):
    """(문단 서식, 글자 서식, 텍스트) 목록 — 서식 id 가 파일마다 달라도 값으로 비교하려고. 머리말·꼬리말 제외"""
    hdr, chars, paras, faces = props(doc)
    root = doc.sections[0].element
    out = []
    for p in all_paragraphs(root, with_hf=False):
        pd = para_desc(paras, p.get("paraPrIDRef"))
        for r in p.findall(HP + "run"):
            t = "".join(x for tt in r.findall(HP + "t") for x in tt.itertext())   # 런 바로 아래 글자만(안에 든 머리말 제외)
            cd = char_desc(chars, faces, r.get("charPrIDRef"))
            out.append((tuple(sorted(pd.items())), tuple(sorted(cd.items())), t))
    return out


def header_footer_check(doc, label):
    """머리글 문구, 꼬리말(쪽 번호) 가 있고 서식(9pt, 맞춤)이 맞는지"""
    hdr, chars, paras, faces = props(doc)
    root = doc.sections[0].element
    heads = {"".join(h.itertext()).strip() for h in root.iter(HP + "header")}
    foots = list(root.iter(HP + "footer"))
    pn = list(root.iter(HP + "pageNum"))
    auto = [a for a in root.iter(HP + "autoNum") if a.get("numType") == "PAGE"]
    ok = heads == {"정보처리기사 실기 복원문제 모음 (2020-2026)"} and foots and (pn or auto)
    sizes = set()
    for node in list(root.iter(HP + "header")) + foots:
        for r in node.iter(HP + "run"):
            sizes.add(char_desc(chars, faces, r.get("charPrIDRef"))["size"])
    ok = ok and sizes <= {9.0}
    print(f"[{label}] 머리글 {sorted(heads)}, 꼬리말 {len(foots)}개, 쪽번호 {len(pn)}개/{len(auto)}개, 크기 {sorted(sizes)} →", "OK" if ok else "확인 필요")
    return bool(ok)


def source_check(doc):
    """원본 JSON 과 대조: 문항 수·정답·해설이 문서 본문에 그대로 있는지"""
    full = structure(doc)["text"]
    flat = re.sub(r"\s+", "", full)
    E = json.load(open(f"{ROOT}/formatted_explanations.json", encoding="utf-8"))
    n_q = n_ans = n_expl = 0
    miss = []
    keys = []
    for f in sorted(glob.glob(f"{ROOT}/raw/*.json")):
        r = json.load(open(f, encoding="utf-8"))
        for q in r["questions"]:
            key = f"{r['year']}-{r['round']}#{q['number']}"
            if f"{r['year']}-{r['round']} 문제 {q['number']} (" not in full:
                continue          # (--only 로 일부만 만든 경우)
            n_q += 1
            ans = re.sub(r"\s+", "", (q.get("answer") or "").replace("\t", "    "))
            if ans in flat:
                n_ans += 1
            else:
                miss.append(("정답", key))
            ex = (q.get("explanation") or "").strip()
            if ex:
                parts = E.get(key) or [ex]
                ok = all(re.sub(r"\s+", "", x.replace("\t", "    ")) in flat for x in parts)
                if ok:
                    n_expl += 1
                else:
                    miss.append(("해설", key))
            keys.append(key)
    print(f"원본 대조: 문항 {n_q}개, 정답 일치 {n_ans}, 해설 일치 {n_expl}, 불일치 {len(miss)}")
    for m in miss[:20]:
        print("   불일치:", m)
    return n_q, miss


def docx_compare(doc):
    """같은 내용을 담은 .docx 와 문단 단위로 대조한다 (공백 무시)"""
    import difflib
    import zipfile
    z = zipfile.ZipFile(f"{ROOT}/정보처리기사_실기_복원문제_2020-2026.docx")
    x = z.read("word/document.xml").decode("utf-8")
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    from lxml import etree
    tree = etree.fromstring(x.encode("utf-8"))
    dpar = []
    for p in tree.iter(W + "p"):
        t = "".join(e.text or "" for e in p.iter() if e.tag in (W + "t",)) + \
            "".join("    " for e in p.iter() if e.tag == W + "tab")
        dpar.append(t)
    # 의도한 차이: ⚠→※, 탭→공백 4칸(공백은 무시), 목차의 '•' 머리표, 여러 줄 정답을 줄마다 문단으로 나눈 것(이어 붙여 비교)
    norm = lambda t: re.sub(r"\s+", "", t.replace("⚠", "※").replace("•", ""))
    a = "".join(norm(t) for t in dpar)
    b = "".join(norm(t) for t in leaf_texts(doc.sections[0].element))
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False) if a != b else None
    diffs = []
    if sm is not None:
        diffs = [(tag, a[i1:i2], b[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]
    print(f"docx↔hwpx 전체 본문 글자 대조(공백·목차 머리표 무시): docx {len(a)}자, hwpx {len(b)}자, 다른 구간 {len(diffs)}개")
    for tag, x1, y1 in diffs[:12]:
        print("   ", tag, "| docx:", x1[:60], "| hwpx:", y1[:60])
    npic = len(re.findall(r"<w:drawing>", x))
    return diffs, npic


PLAN = os.environ.get("HWP_PLAN")      # 1단계 측정 JSON 경로 (환경변수 HWP_PLAN)


def main():
    hwpx = sys.argv[1]
    hwp = sys.argv[2] if len(sys.argv) > 2 else None
    ok = True
    r = validate_editor_open_safety(open(hwpx, "rb").read())
    errs = [i for i in r.validate_package.issues if i.level == "error"] + list(r.blocking_package_errors)
    print("열림 안전 검증: reopen_ok =", r.reopen_ok, ", 오류", len(errs), ", 문서 검증 이슈", len(r.validate_document.issues))
    ok &= r.reopen_ok and not errs and not r.validate_document.issues
    d1 = HwpxDocument.open(hwpx)
    ok &= audit(d1, "hwpx")
    ok &= header_footer_check(d1, "hwpx")
    ok &= bool(page_check(d1, "hwpx", plan_path=PLAN))
    ok &= spacing_check(d1, "hwpx")
    ok &= fit_check(d1, "hwpx")
    n_q, miss = source_check(d1)
    ok &= not miss
    if len(sys.argv) > 3 and sys.argv[3] == "--docx":
        diffs, npic = docx_compare(d1)
        s1 = structure(d1)
        print(f"그림 수: docx {npic} ↔ hwpx {s1['pics']}")
        ok &= (not diffs) and npic == s1["pics"]
    if hwp:
        d2 = HwpxDocument.open(hwp)
        s1, s2 = structure(d1), structure(d2)
        for k in ("paragraphs", "tables", "pics"):
            print(f"hwpx↔hwp {k}: {s1[k]} ↔ {s2[k]}", "OK" if s1[k] == s2[k] else "다름")
            ok &= s1[k] == s2[k]
        same_text = re.sub(r"\s+", "", s1["text"]) == re.sub(r"\s+", "", s2["text"])
        print("hwpx↔hwp 텍스트(공백 무시) 동일:", same_text)
        ok &= same_text
        a1, a2 = resolved_runs(d1), resolved_runs(d2)
        norm = lambda L: [(p, c, re.sub(r"\s+", "", t)) for p, c, t in L if re.sub(r"\s+", "", t)]
        n1, n2 = norm(a1), norm(a2)
        diff = sum(1 for x, y in zip(n1, n2) if x != y) + abs(len(n1) - len(n2))
        print(f"hwpx↔hwp 런 서식 비교: {len(n1)}↔{len(n2)}, 다른 곳 {diff}")
        ok &= diff == 0
        ok &= audit(d2, "hwp(다시 읽음)")
        ok &= header_footer_check(d2, "hwp(다시 읽음)")
        ok &= bool(page_check(d2, "hwp(다시 읽음)", plan_path=PLAN))
        ok &= spacing_check(d2, "hwp(다시 읽음)")
        ok &= fit_check(d2, "hwp(다시 읽음)")
        n_q2, miss2 = source_check(d2)
        ok &= not miss2 and n_q2 == n_q
    print("종합:", "통과" if ok else "확인 필요")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
