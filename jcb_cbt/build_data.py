#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
../jcb_restored/raw/*.json (chobopark.tistory.com 복원문제 수집 데이터)를
정보처리기사 실기 CBT 사이트용 site/data.json으로 변환한다.

채점 방식 분류(grading) 규칙 — 사용자 결정 사항:
  1) 숫자/전문용어/코드실행결과/SQL문 등 "짧고 정확한 값"은 완전일치(exact) 자동채점
     (공백 한 칸이라도 다르면 오답)
  2) 40자를 넘는 설명/정의형 서술 답안은 자가채점(self) — 정답 공개 후 본인이 맞음/틀림 체크
  규칙은 휴리스틱이라 100% 정확하지 않을 수 있다. 애매할 때는 일부러 self 쪽으로 치우치게 했다
  (짧은 값을 self로 보내는 건 안전하지만, 서술형을 exact로 보내면 맞는 답도 전부 오답 처리되므로).
"""
import json
import glob
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
from answer_parts import split_answer   # 정답 문자열 → 번호별 조각

HERE = os.path.dirname(os.path.abspath(__file__))   # 이 스크립트가 있는 폴더(jcb_cbt)
SRC = os.path.join(os.path.dirname(HERE), "jcb_restored")   # 옆 폴더 jcb_restored
RAW_DIR = SRC + "/raw"
OUT_PATH = os.path.join(HERE, "site", "data.json")
IMG_OUT = os.path.join(HERE, "site", "img")
OLD_PATH = os.path.join(HERE, "backup_before_dups_memomark", "data.json")   # 병합 전 데이터(비교 보고용)

# 2026-10-08 교체·보강: 문서 단계(format_prompts.py)에서 확정한 구조를 그대로 가져온다.
#   formatted_prompts.json      → prompt_blocks (지시문/본문/보기/표/그림 + 박스 표시)
#   formatted_explanations.json → explanation_lines (해설의 " / " 항목을 줄로 나눈 것; 원문 explanation 은 그대로)
#   formatted_code_tables.json  → code_table (code 칸 전체가 표인 문항)
#   images/*.png                → site/img/*.png (다시 그린 그림)
FORMATTED = json.load(open(SRC + "/formatted_prompts.json", encoding="utf-8"))
EXPL_LINES = json.load(open(SRC + "/formatted_explanations.json", encoding="utf-8"))
CTABLES = json.load(open(SRC + "/formatted_code_tables.json", encoding="utf-8"))
# 2026-10-12: 같은 문제의 다른 언어 판(Java/C) — 기본 문항은 그대로 두고 옆에 '탭'으로 붙인다.
#   variants.json : {source:{...참고 사이트 정보...}, questions:{"2023-2-2":{base_blog, base_blog_url, variants:[...]}}}
#   기본 판(base)은 raw/*.json 그대로이고, 아래 변형은 문항에 variants 로 붙는다. blog=True 인 판에 클라이언트가 빨간 점을 단다.
VARIANTS = json.load(open(SRC + "/variants.json", encoding="utf-8"))
VARIANT_FIELDS = ("key", "language", "lang_hint", "blog", "source_url", "prompt", "prompt_blocks", "code", "grading", "answer", "explanation")

# 2026-10-12: 여러 회차에 다시 나온 같은 문제는 1개만 남기고 출제 연도·회차를 appearances 로 붙인다.
#   dup_merges.json : 묶음별 keep(남길 판) / merge(합칠 판) / 언어·채점 보정 / 해설 가져올 곳. 되돌리려면 묶음을 지우고 다시 돌린다.
MERGES = json.load(open(SRC + "/dup_merges.json", encoding="utf-8"))
MERGE_REPORT_PATH = os.path.join(HERE, "merge_report.json")

SQL_KW = re.compile(r"(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\s", re.I)
DESC_VERB = re.compile(r"(서술하시오|설명하시오|약술하시오|기술하시오|서술하세요|설명하세요|서술할|설명할)")
SPLIT_RE = re.compile(r"[\n/,]|(?:^|\s)(?:[①-⑳]|\([0-9]+\)|[0-9]+\.|[ㄱ-ㅎ]\.)", re.UNICODE)

LANG_HINT = {
    "Python": "python", "Java": "java", "C": "c", "SQL": "sql", "Shell": "bash",
}


# 2026-10-08: 새로 들어온 문항 중 정답이 "여러 표기 중 하나(or)", 표 모양, "(왼쪽부터)" 같은 설명이 섞인 것은
# 완전일치로 채점하면 맞게 풀어도 오답이 되므로 자가채점으로 보낸다(규칙: 애매하면 self 쪽으로).
GRADING_OVERRIDE = {
    "2025-1-7": "self",    # 정답이 표 모양(name | incentives → 이순신 | 1000)
    "2025-2-11": "self",   # 정답이 'A or B' 두 표기
    "2025-3-14": "self",   # 정답이 'A 열 / a1 (1행)' 설명 섞임
    "2025-3-19": "self",   # '(왼쪽부터) ㄱ ㄹ ㅁ' 설명 섞임
    "2026-2-10": "self",   # 번호별 IP 여러 개를 한 줄에 적은 형식
}


# 2026-10-08: 번호별 답안란(answer_parts).
#   정답 키가 "1. x / 2. y", "(1) x (2) y", "① x ② y", "ㄱ. x ㄴ. y" 처럼 번호로 나뉘어 있고 깔끔하게 쪼개지면
#   tools/answer_parts.py 가 자동으로 조각낸다. 아래는 자동으로 안 되거나 사람이 값을 다듬어야 하는 문항이다.
#   label = 입력칸 옆에 보일 이름, value = 그 칸의 정답(완전일치). 원문 answer 는 그대로 둔다.
PARTS_OVERRIDE = {
    "2022-3-18": [("①", "ㄴ"), ("②", "ㄷ"), ("③", "ㄱ"), ("④", "ㄹ"), ("⑤", "ㅁ")],   # 블로그 판: 정답 'ㄴ, ㄷ, ㄱ, ㄹ, ㅁ' (기호 ㄱ~ㅁ)
    "2022-2-18": [("①", "ㄹ"), ("②", "ㅇ"), ("③", "ㄷ")],           # 블로그 판: 정답 'ㄹ, ㅇ, ㄷ' (= Full, Partial, Transitive)
    "2021-2-15": [("①", "ㅁ"), ("②", "ㅅ"), ("③", "ㄷ")],           # 블로그 판: 정답 'ㅁ, ㅅ, ㄷ' (= Function, Dynamic, Information)
    "2024-2-4":  [("①", "5"), ("②", "4")],                          # 정답 키: 'Cardinality: 5, Degree: 4'
    "2023-1-14": [("①", "idx2"), ("②", "nx")],                      # 정답 키: 'idx2, nx' (2026-10-11 코드를 시험 원본 사진의 C 코드로 교체 — 빈칸 표기 ① ②)
    "2024-1-9":  [("LRU", "6"), ("LFU", "6")],                      # 정답 키: '(1) LRU: 6 / (2) LFU: 6' → 칸 이름을 알고리즘명으로
    "2022-2-19": [("1", "HTTP"), ("2", "Hypertext"), ("3", "HTML")],  # 정답 키의 ㅇ ㄹ ㅂ 는 보기 기호 → 칸 번호는 문제 번호
    "2025-1-15": [("①", "int a = 0"), ("②", "a < m || b[a] < x"), ("③", "b[a] < 0"), ("④", "b[a] = -b[a];"),
                  ("⑤", "a++;"), ("⑥", "return 1;"), ("⑦", "③ → ④ → ⑤ → ② → ⑥")],   # ⑦ = 문장 커버리지 순서

    # 2026-10-12: 지문에 번호 없는 빈칸 '( )' 여러 개 / 괄호 (a)(b) 가 있는 문항 — 답안란을 괄호(빈칸)마다 나눈다.
    #   번호가 없는 빈칸은 지문에 나온 순서(표는 위→아래·왼→오른쪽)대로 (1)(2)… 이름을 붙인다. 정답 값은 원문 answer 의 순서와 같다.
    "2022-2-10": [("1", "베타"), ("2", "알파")],                                   # 1번 설명=베타, 2번 설명=알파
    "2022-3-2":  [("합집합", "U"), ("차집합", "-"), ("카티션 프로덕트", "X"), ("프로젝트", "π"), ("조인", "⋈")],   # 표의 항목 이름을 칸 이름으로
    "2022-3-16": [("1", "SJF"), ("2", "RR"), ("3", "SRT")],                         # 표의 위→아래 순서
    "2023-1-5":  [("1", "가상회선"), ("2", "데이터그램")],                           # 표의 위→아래 순서
    "2023-1-9":  [("(a)", "%"), ("(b)", "10")],                                     # 본 정답 %,10 / 같은 뜻 %,5 · %,2 · &,1 은 raw 의 answer_alts(통째 비교)로 인정
    "2023-2-2":  [("a", "m/1000"), ("b", "(m%1000)/500", ["m%1000/500"]), ("c", "(m%500)/100", ["m%500/100"]), ("d", "(m%100)/10", ["m%100/10"])],
                 # 코드의 a = ( ); … 괄호 안에 들어갈 식. 괄호를 뺀 꼴은 계산 순서가 같아 같은 식이므로 인정(C 판 탭도 같은 처리)
    "2023-2-15": [("대칭키", "DES, AES, ARIA, SEED"), ("비대칭키", "RSA, ECC")],    # 한 칸에 보기 여러 개를 쉼표로 적는다(순서는 정답 표기대로)
    "2024-1-10": [("1", "6"), ("2", "3"), ("3", "1"), ("4", "7"), ("5", "2")],     # '5 → ( ) → ( ) → ( ) → ( ) → ( )' 다섯 빈칸
    "2025-3-19": [("1", "ㄱ"), ("2", "ㄹ"), ("3", "ㅁ")],                           # 표 머리글의 ( ) 세 칸, 왼쪽부터 (채점은 기존대로 자가채점)
}
PARTS_EXCLUDE = set()   # 번호 형식이지만 칸을 나누면 오히려 어색한 문항(현재 없음)


def make_parts(qid, answer):
    if qid in PARTS_EXCLUDE:
        return None
    if qid in PARTS_OVERRIDE:
        parts = []
        for t in PARTS_OVERRIDE[qid]:             # (label, value) 또는 (label, value, [같은 식의 다른 표기, …])
            p = {"label": t[0], "value": t[1]}
            if len(t) > 2:
                assert isinstance(t[2], list) and t[2] and all(isinstance(a, str) and a.strip() and a.strip() != t[1].strip() for a in t[2]), (qid, "칸 alts 형식")
                p["alts"] = list(t[2])
            parts.append(p)
    else:
        parts = split_answer(answer)
    if not parts:
        return None
    assert len(parts) >= 2, qid
    pos = 0
    for p in parts:                       # 값들이 원문 정답 안에 순서대로 들어 있는지 확인
        assert p["value"].strip(), (qid, "빈 조각")
        k = answer.find(p["value"], pos)
        assert k >= 0, (qid, "조각이 원문 정답에 없음", p)
        pos = k + len(p["value"])
    return parts


def classify_grading(prompt, answer):
    a = (answer or "").strip()
    p = prompt or ""
    if not a:
        return "exact"
    if DESC_VERB.search(p):
        return "self"
    if SQL_KW.search(a):
        return "exact"
    segs = [s.strip() for s in SPLIT_RE.split(a) if s and s.strip()]
    if len(segs) >= 2 and max(len(s) for s in segs) <= 20:
        return "exact"
    if len(a) <= 40:
        return "exact"
    return "self"


def make_variant(qid, v):
    """variants.json 의 변형 1개를 검증해 data.json 용으로 다듬는다."""
    for f in VARIANT_FIELDS:
        assert f in v, (qid, "변형에 필드 없음", f)
    assert v["grading"] in ("exact", "self"), (qid, v["key"])
    assert v["answer"].strip() and v["prompt_blocks"], (qid, v["key"])
    out = {f: v[f] for f in VARIANT_FIELDS}
    out["code"] = out["code"].strip("\n")
    out["answer"] = out["answer"].strip()
    out["blog"] = bool(out["blog"])
    if v.get("blog_url"):
        out["blog_url"] = v["blog_url"]
    parts = v.get("answer_parts")
    if parts:
        assert len(parts) >= 2, (qid, v["key"])
        pos = 0
        for p in parts:                       # 값이 원문 정답 안에 순서대로 들어 있는지(기본 판과 같은 검사)
            assert p["value"].strip(), (qid, "빈 조각")
            k = out["answer"].find(p["value"], pos)
            assert k >= 0, (qid, "조각이 변형 정답에 없음", p)
            pos = k + len(p["value"])
        out["answer_parts"] = [dict(label=p["label"], value=p["value"], **({"alts": p["alts"]} if p.get("alts") else {})) for p in parts]
    return out


def apply_merges(all_questions, rounds_meta):
    """dup_merges.json 의 묶음대로 같은 문제를 합친다. 반환: (남은 문항 목록, 보고용 dict)."""
    by_id = {q["id"]: q for q in all_questions}
    seen, dropped, report = set(), set(), []
    for g in MERGES["groups"]:
        ids = [g["keep"]] + list(g["merge"])
        assert len(set(ids)) == len(ids), (g["key"], "묶음 안 id 중복")
        for i in ids:
            assert i in by_id, (g["key"], "문항을 찾을 수 없음", i)
            assert i not in seen, (g["key"], "여러 묶음에 들어 있음", i)
            seen.add(i)
        keep = by_id[g["keep"]]
        mem = [by_id[i] for i in g["merge"]]
        rk = [(m["year"], m["round"]) for m in [keep] + mem]
        assert len(set(rk)) == len(rk), (g["key"], "같은 회차에 두 번 나온 문제는 합치지 않는다")
        for m in [keep] + mem:
            assert "variants" not in m, (g["key"], m["id"], "언어 판(탭)이 있는 문항은 합치지 않는다")

        # 번호별 답안란 구조가 같아야 칸마다 대체 표기를 합칠 수 있다
        kp = keep.get("answer_parts")
        for m in mem:
            mp = m.get("answer_parts")
            assert bool(kp) == bool(mp), (g["key"], m["id"], "번호별 답안란 유무가 다름")
            if kp:
                assert [p["label"] for p in kp] == [p["label"] for p in mp], (g["key"], m["id"], "칸 이름이 다름")

        # 같은 뜻의 다른 정답 표기(통째 비교) — 합치는 판의 정답을 모두 인정
        alts = list(keep.get("answer_alts", []))
        for m in mem:
            for a in [m["answer"]] + list(m.get("answer_alts", [])):
                a = a.strip()
                if a and a != keep["answer"].strip() and a not in alts:
                    alts.append(a)
        if alts:
            keep["answer_alts"] = alts
        # 번호별 칸의 대체 표기
        if kp:
            for i, p in enumerate(kp):
                pa = list(p.get("alts", []))
                for m in mem:
                    mp = m["answer_parts"][i]
                    for v in [mp["value"]] + list(mp.get("alts", [])):
                        v = v.strip()
                        if v and v != p["value"].strip() and v not in pa:
                            pa.append(v)
                if pa:
                    p["alts"] = pa

        src = g.get("explanation_from")
        if src:
            assert src in g["merge"], (g["key"], "해설을 가져올 문항은 합치는 판이어야 함")
            assert not keep["explanation"], (g["key"], "남길 판에 이미 해설이 있음")
            s_q = by_id[src]
            assert s_q["explanation"], (g["key"], "가져올 해설이 비어 있음")
            keep["explanation"] = s_q["explanation"]
            if "explanation_lines" in s_q:
                keep["explanation_lines"] = s_q["explanation_lines"]
        if g.get("grading"):
            assert g["grading"] in ("exact", "self")
            keep["grading"] = g["grading"]
        if g.get("language"):
            keep["language"] = g["language"]
            keep["lang_hint"] = LANG_HINT.get(g["language"], "")

        apps = [{"id": m["id"], "year": m["year"], "round": m["round"], "number": m["display_number"]} for m in [keep] + mem]
        apps.sort(key=lambda a: (a["year"], a["round"], int(a["number"])))
        keep["appearances"] = apps
        keep["aliases"] = [m["id"] for m in mem]
        dropped |= set(keep["aliases"])
        report.append({
            "key": g["key"], "topic": g["topic"], "keep": g["keep"], "merged": g["merge"],
            "appearances": [a["id"] for a in apps], "why": g["why"],
            "answer_alts": keep.get("answer_alts", []),
            "part_alts": [[p["label"], p["alts"]] for p in (kp or []) if p.get("alts")],
            "explanation_from": src, "grading": keep["grading"], "language": keep["language"],
        })

    final = [q for q in all_questions if q["id"] not in dropped]
    # 회차마다 '원래 문항 수'와 같은 수의 문항이 그 회차에 출제 기록을 갖는지 확인(합쳐도 회차별 문항 수는 그대로)
    for r in rounds_meta:
        n = 0
        for q in final:
            ap = q.get("appearances") or [{"year": q["year"], "round": q["round"]}]
            if any(a["year"] == r["year"] and a["round"] == r["round"] for a in ap):
                n += 1
        assert n == r["count"], (r["label"], "합친 뒤 회차별 문항 수가 달라짐", n, r["count"])
    return final, {"groups": report, "dropped": sorted(dropped), "kept": [g["keep"] for g in MERGES["groups"]]}


def assert_no_enter_only_duplicates(questions):
    """(2026-10-12 사용자 지시, 앞으로도 같음) 줄바꿈·공백(엔터)만 다른 문제는 '유사'가 아니라 '같은 문제'다 → 합쳐야 한다.
    합친 뒤에도 지문(prompt)+코드(code)가 모든 공백을 지운 글자열로 같은 문항 쌍이 남아 있으면 빌드를 멈춘다.
    (코드의 숫자·글자가 한 글자라도 다르면 실행 결과가 달라질 수 있어 이 검사에 걸리지 않고, 그런 쌍은 similar 로 다룬다.)"""
    import re as _re
    seen = {}
    for q in questions:
        key = _re.sub(r"\s+", "", q.get("prompt") or "") + "||" + _re.sub(r"\s+", "", q.get("code") or "")
        assert key not in seen, ("줄바꿈·공백만 다른 같은 문제가 합쳐지지 않았다 → dup_merges.json 의 groups 에 넣을 것", seen[key], q["id"])
        seen[key] = q["id"]


def apply_similar(all_questions):
    """dup_merges.json 의 not_merged.similar_but_different_answer — 비슷하지만 정답이 달라 '합치지 않은' 쌍.
    (2026-10-12 사용자 요청) 합치지는 않고, 각 문항에 similar:[{id,year,round,number,note}] 를 붙여
    문제 번호 옆에 '비슷한 문제가 출제된 연도·회차'를 보여 준다. 같은 개념·다른 문장(same_concept_different_wording)은 아무것도 하지 않는다."""
    pairs = MERGES["not_merged"].get("similar_but_different_answer", [])
    by_id = {q["id"]: q for q in all_questions}
    for q in all_questions:
        for a in q.get("aliases", []):
            by_id[a] = q                                   # 합쳐져 없어진 옛 id 도 남은 문항으로 찾는다

    def parse(i):
        y, r, n = i.split("-")
        return int(y), int(r), n

    sim = {}
    for p in pairs:
        a, b, note = p[0], p[1], p[2]
        assert a in by_id and b in by_id, ("비슷한 문항 id 를 찾을 수 없음", a, b)
        qa, qb = by_id[a], by_id[b]
        assert qa["id"] != qb["id"], ("같은 문항으로 합쳐진 쌍은 '정답이 다른 유사 문항'이 아님", a, b)
        assert qa["answer"].strip() != qb["answer"].strip(), ("정답이 같은 쌍은 합칠 후보이지 '정답이 다른 유사 문항'이 아님", a, b)
        for me, other_id, other_note in ((qa, b, note), (qb, a, note)):
            y, r, n = parse(other_id)
            lst = sim.setdefault(me["id"], [])
            assert all(s["id"] != other_id for s in lst), ("유사 문항 중복", me["id"], other_id)
            lst.append({"id": other_id, "year": y, "round": r, "number": n, "note": other_note})
    for q in all_questions:
        if q["id"] in sim:
            q["similar"] = sorted(sim[q["id"]], key=lambda s: (s["year"], s["round"], int(s["number"])))
    return len(pairs), sorted(sim)


def make_blocks(key):
    """formatted_prompts.json 의 블록 → 사이트용 prompt_blocks (표는 rows, 그림은 img/ 상대경로)."""
    out = []
    for b in FORMATTED[key]:
        k = b["kind"]
        if k == "table":
            out.append({"kind": "table", "caption": b.get("caption"), "rows": b["rows"], "header": b.get("header", True)})
        elif k == "image":
            out.append({"kind": "image", "box": True, "file": "img/" + os.path.basename(b["file"]),
                        "alt": b.get("alt") or "그림", "caption": b.get("caption") or "", "w": b["w"], "h": b["h"]})
        else:
            out.append({"kind": k, "box": bool(b.get("box")), "lines": b["lines"]})
    return out


def main():
    files = sorted(
        glob.glob(os.path.join(RAW_DIR, "*.json")),
        key=lambda p: tuple(int(x) for x in os.path.basename(p).replace(".json", "").split("_")),
    )

    rounds_meta = []
    all_questions = []
    lang_counter = {}
    grading_counter = {"exact": 0, "self": 0}
    total_img = 0
    used_variants = set()

    for fp in files:
        with open(fp, encoding="utf-8") as f:
            r = json.load(f)
        year, rnd = r["year"], r["round"]
        img_list = r.get("image_only_questions", [])
        total_img += len(img_list)

        rounds_meta.append({
            "year": year, "round": rnd,
            "label": f"{year}년 {rnd}회",
            "source_url": r["source_url"],
            "count": len(r["questions"]),
            "image_excluded": img_list,
        })

        for q in r["questions"]:
            lang = q.get("language") or "기타"
            grading = GRADING_OVERRIDE.get(f"{year}-{rnd}-{q['number']}") or classify_grading(q.get("prompt"), q.get("answer"))

            fkey = f"{year}-{rnd}#{q['number']}"
            item = {
                "id": f"{year}-{rnd}-{q['number']}",
                "year": year,
                "round": rnd,
                "display_number": str(q["number"]),
                "language": lang,
                "lang_hint": LANG_HINT.get(lang, ""),
                "difficulty": q.get("difficulty"),
                "prompt": q.get("prompt") or "",
                "prompt_blocks": make_blocks(fkey),
                "code": (q.get("code") or "").strip("\n"),
                "grading": grading,
                "answer": (q.get("answer") or "").strip(),
                "explanation": (q.get("explanation") or "").strip(),
                "source_url": r["source_url"],
            }
            parts = make_parts(item["id"], item["answer"])
            if parts:
                item["answer_parts"] = parts          # 번호별 답안란(채점: 칸마다 완전일치)
            alts = q.get("answer_alts")               # 같은 뜻의 다른 표기(통째로 비교). 예: 문장 끝 세미콜론 생략
            if alts:
                assert isinstance(alts, list) and all(isinstance(a, str) and a.strip() for a in alts), (item["id"], "answer_alts 형식")
                assert all(a.strip() != item["answer"] for a in alts), (item["id"], "answer_alts 가 정답과 같음")
                assert len(set(a.strip() for a in alts)) == len(alts), (item["id"], "answer_alts 중복")
                item["answer_alts"] = [a.strip() for a in alts]
            el = EXPL_LINES.get(fkey)
            if el and len(el) > 1:
                item["explanation_lines"] = el
            if fkey in CTABLES:                      # code 칸 전체가 표 → 코드 상자 대신 표로
                item["code_table"] = CTABLES[fkey]
                item["code"] = ""
            if q.get("restored"):
                item["restored"] = q["restored"]     # A 표·그림 / B 보기·본문 / C 신규(이미지 전용이던 문항) / D 경미한 차이
            vq = VARIANTS["questions"].get(item["id"])
            if vq:                                   # 같은 문제의 다른 언어 판을 탭으로 붙인다
                vs = [make_variant(item["id"], v) for v in vq["variants"]]
                keys = ["base"] + [v["key"] for v in vs]
                assert len(set(keys)) == len(keys), (item["id"], "판 key 중복")
                assert all(v["language"] != item["language"] for v in vs), (item["id"], "기본 판과 같은 언어의 변형은 탭의 의미가 없음")
                item["variants"] = vs
                if vq.get("base_blog"):
                    item["blog_version"] = "base"
                    item["blog_url"] = vq["base_blog_url"]
                else:
                    blogs = [v["key"] for v in vs if v["blog"]]
                    assert len(blogs) == 1, (item["id"], "블로그 판은 정확히 1개여야 함", blogs)
                    item["blog_version"] = blogs[0]
                used_variants.add(item["id"])
            all_questions.append(item)

    n_before_merge = len(all_questions)
    all_questions, merge_report = apply_merges(all_questions, rounds_meta)     # 같은 문제는 1개만 남기고 출제 회차를 appearances 에 모은다
    assert_no_enter_only_duplicates(all_questions)                             # 엔터·공백만 다른 문제가 따로 남아 있으면 중단
    n_sim_pairs, sim_ids = apply_similar(all_questions)                        # 비슷하지만 정답이 다른 문항: 합치지 않고 서로의 연도·회차를 similar 에 적는다
    for q in all_questions:                                                    # 합친 뒤의 문항으로 언어·채점 집계
        lang_counter[q["language"]] = lang_counter.get(q["language"], 0) + 1
        grading_counter[q["grading"]] += 1

    languages_meta = [
        {"id": lang, "label": lang, "count": cnt}
        for lang, cnt in sorted(lang_counter.items(), key=lambda kv: -kv[1])
    ]

    out = {
        "meta": {
            "title": "정보처리기사 실기 복원문제 CBT",
            "source_author": "Life-Journey (chobopark.tistory.com)",
            "license": "CC BY",
            "total_questions": len(all_questions),
            "total_appearances": n_before_merge,                  # 회차별 출제 기록 수(합치기 전 문항 수)
            "merged_duplicates": n_before_merge - len(all_questions),
            "similar_pairs": n_sim_pairs,                         # 비슷하지만 정답이 달라 합치지 않은 쌍(번호 옆에 서로의 연도·회차 표시)
            "total_image_only_excluded": total_img,
            "revised": "2026-10-12",
            "total_rounds": len(rounds_meta),
            "grading_breakdown": grading_counter,
            "ref_source": VARIANTS["source"],        # 홈 화면의 '참고한 웹사이트' 출처 블록
        },
        "rounds_meta": rounds_meta,
        "languages_meta": languages_meta,
        "questions": all_questions,
    }

    # ---- 일관성 검증 ------------------------------------------------------
    raw_total = 0
    for fp in files:
        raw_total += len(json.load(open(fp, encoding="utf-8"))["questions"])
    assert len(all_questions) + len(merge_report["dropped"]) == raw_total, "문항 수가 raw 합계와 다름"
    assert sum(r["count"] for r in rounds_meta) == raw_total
    assert sum(len(q.get("appearances") or [1]) for q in all_questions) == raw_total, "출제 기록 수 합계가 raw 와 다름"
    all_ids = {q["id"] for q in all_questions}
    assert not (all_ids & set(merge_report["dropped"])), "합쳐서 없앤 id 가 문항으로 남아 있음"
    for q in all_questions:
        for a in q.get("aliases", []):
            assert a not in all_ids
        if q.get("appearances"):
            assert q["id"] in [a["id"] for a in q["appearances"]] and len(q["appearances"]) >= 2
    assert sum(lang_counter.values()) == len(all_questions)
    assert sum(grading_counter.values()) == len(all_questions)
    assert len({q["id"] for q in all_questions}) == len(all_questions), "id 중복"
    assert sum(len(r["image_excluded"]) for r in rounds_meta) == total_img
    assert all(q["answer"] for q in all_questions), "정답이 빈 문항: " + str([q["id"] for q in all_questions if not q["answer"]])
    assert all(q["prompt_blocks"] for q in all_questions), "prompt_blocks 가 빈 문항"
    assert used_variants == set(VARIANTS["questions"]), ("variants.json 에 있는데 문항을 못 찾은 id", set(VARIANTS["questions"]) - used_variants)
    assert not (used_variants & set(merge_report["dropped"])), "언어 판이 있는 문항이 합쳐져 사라짐"

    # ---- 그림 복사 + 참조 파일 존재 확인 --------------------------------
    os.makedirs(IMG_OUT, exist_ok=True)
    used = set()
    for q in all_questions:
        for b in q["prompt_blocks"]:
            if b["kind"] == "image":
                used.add(os.path.basename(b["file"]))
    for name in sorted(used):
        shutil.copy(os.path.join(SRC, "images", name), os.path.join(IMG_OUT, name))
    for name in os.listdir(IMG_OUT):
        assert name in used, "사용하지 않는 그림이 site/img 에 있음: " + name

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("OK:", OUT_PATH)
    print("문항수:", len(all_questions), "(합치기 전 출제 기록", n_before_merge, "- 중복", n_before_merge - len(all_questions), ") / 회차수:", len(rounds_meta), "/ 이미지전용 제외:", total_img)
    print("채점 분류:", grading_counter)
    print("언어 분포:", lang_counter)
    n_parts = sum(1 for q in all_questions if q.get("answer_parts"))
    print("번호별 답안란 문항:", n_parts, "/ 칸 수 분포:", sorted({len(q["answer_parts"]) for q in all_questions if q.get("answer_parts")}))
    print("비슷하지만 정답이 다른 쌍:", n_sim_pairs, "쌍 / 연도·회차를 표시하는 문항:", sim_ids)
    print("언어 판(탭) 문항:", sorted(used_variants))
    print("그림 파일:", len(used), "/ 그림 블록:", sum(1 for q in all_questions for b in q["prompt_blocks"] if b["kind"] == "image"))

    # ---- 교체 전 데이터와 비교(보고용) -------------------------------------
    if os.path.exists(OLD_PATH):
        old = {q["id"]: q for q in json.load(open(OLD_PATH, encoding="utf-8"))["questions"]}
        new_ids = [q["id"] for q in all_questions if q["id"] not in old]
        gone = [i for i in old if i not in {q["id"] for q in all_questions}]
        chg = {"prompt": [], "code": [], "answer": [], "explanation": [], "grading": [], "language": []}
        for q in all_questions:
            o = old.get(q["id"])
            if not o:
                continue
            for k in chg:
                if o.get(k) != q.get(k):
                    chg[k].append(q["id"])
        print("신규 문항:", len(new_ids), new_ids)
        print("사라진 문항:", gone)
        for k, v in chg.items():
            print("변경 -", k, len(v), (v if k in ("answer", "grading", "language", "explanation", "code") else ""))
        json.dump({"new": new_ids, "gone": gone, "changed": chg, "merge": merge_report}, open(MERGE_REPORT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
