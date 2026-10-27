# -*- coding: utf-8 -*-
"""정답 문자열을 번호(빈칸)별 조각으로 쪼갠다.

지원하는 번호 표기: "1. x" "1.x" "1) x" "(1) x" "①" "①=15" "ㄱ. x"
규칙(깔끔하게 쪼개질 때만 인정):
  - 번호가 2개 이상, 숫자 번호는 순서대로 증가(1,2,3 또는 2,4,5처럼 건너뛰기 허용), 원문자(①②…)는 ①부터 연속,
    자모(ㄱㄴㄷ…)는 서로 다르기만 하면 됨(정답 키에 적힌 순서를 따른다)
  - 각 조각의 값은 비어 있지 않아야 한다
반환: [{"label": "1", "value": "..."}, ...]  또는 None
"""
import re

CIRC = "①②③④⑤⑥⑦⑧⑨⑩"
JAMO = "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"

# 숫자: 앞이 문자열 시작/공백/구분자일 때만 번호로 본다("128.5" 안의 "8." 같은 오인 방지)
RE_DIGIT = re.compile(r"(?:(?<=^)|(?<=[\s,/;]))(?:\((\d{1,2})\)|(\d{1,2})[.)])\s*")
RE_CIRC = re.compile(r"([" + CIRC + r"])\s*=?\s*")
RE_JAMO = re.compile(r"(?:(?<=^)|(?<=[\s,/;]))([" + JAMO + r"])[.)]\s*")


def _cut(answer, matches):
    parts = []
    for k, m in enumerate(matches):
        end = matches[k + 1].start() if k + 1 < len(matches) else len(answer)
        val = answer[m.end():end].strip()
        # 조각 사이의 구분자(" / ", ",")만 지운다. 코드 정답의 끝 ";" 나 연산자 "/" 는 값의 일부이므로 남긴다.
        val = re.sub(r"(?:\s+/|\s*,)\s*$", "", val).strip()
        lab = next(g for g in m.groups() if g)
        parts.append({"label": lab, "value": val})
    return parts


def split_answer(answer):
    a = (answer or "").strip()
    # 1) 원문자 ①②…
    ms = list(RE_CIRC.finditer(a))
    if len(ms) >= 2 and a[:ms[0].start()].strip() == "":
        labs = [m.group(1) for m in ms]
        if labs == list(CIRC[:len(labs)]):
            p = _cut(a, ms)
            if all(x["value"] for x in p):
                return p
    # 2) 자모 ㄱ. ㄴ.
    ms = list(RE_JAMO.finditer(a))
    if len(ms) >= 2 and a[:ms[0].start()].strip() == "":
        labs = [m.group(1) for m in ms]
        if len(set(labs)) == len(labs):
            p = _cut(a, ms)
            if all(x["value"] for x in p):
                return p
    # 3) 숫자: 순서대로 증가하는 번호만 골라낸다(값 안의 "2.5" 같은 오인은 증가 조건으로 일부 걸러짐 — 결과는 사람이 검토)
    ms = list(RE_DIGIT.finditer(a))
    if len(ms) >= 2 and a[:ms[0].start()].strip() == "":
        nums = [int(m.group(1) or m.group(2)) for m in ms]
        if all(nums[i] < nums[i + 1] for i in range(len(nums) - 1)) and nums[0] <= 2:
            p = _cut(a, ms)
            if all(x["value"] for x in p):
                return p
    return None
