#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jcb_restored/raw/*.json (chobopark.tistory.com 복원문제 수집 데이터)를
사람이 읽기 좋은 하나의 마크다운 문서로 합친다.
"""
import json
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import format_prompts as fmt   # 지시문/본문/보기 줄바꿈 분리

HERE = os.path.dirname(os.path.abspath(__file__))   # 이 스크립트가 있는 폴더(jcb_restored)
RAW_DIR = os.path.join(HERE, "raw")
OUT_PATH = os.path.join(HERE, "정보처리기사_실기_복원문제_2020-2026.md")

files = sorted(
    glob.glob(os.path.join(RAW_DIR, "*.json")),
    key=lambda p: (
        int(os.path.basename(p).split("_")[0]),
        int(os.path.basename(p).split("_")[1].split(".")[0]),
    ),
)

rounds = []
for fp in files:
    with open(fp, encoding="utf-8") as f:
        rounds.append(json.load(f))

total_q = sum(len(r["questions"]) for r in rounds)
total_img = sum(len(r.get("image_only_questions", [])) for r in rounds)

lines = []
lines.append("# 정보처리기사 실기 복원문제 모음 (2020년 1회 ~ 2026년 2회)")
lines.append("")
lines.append("## 출처 및 라이선스")
lines.append("")
lines.append("- **원저작자**: Life-Journey (블로그: chobopark.tistory.com)")
lines.append("- **라이선스**: CC BY (저작자표시) — 2020년 1회 글과 2026년 2회 글에서 직접 확인했으며, 같은 블로그의 나머지 글도 동일한 설정일 것으로 추정(개별 재확인은 하지 않음)")
lines.append("- **수집 방법**: 각 회차 블로그 글을 AI 웹 열람 도구로 읽어 받아쓰기(transcribe)함. 원문 HTML을 직접 대조한 완전 검증은 아니며, 일부 코드 문제는 사용자가 보유한 별도의 독립적 자료(다른 저자의 기출풀이집)와 대조해 일치를 확인함.")
HIST = ("2026-10-08 원문 페이지와 2차 대조하여 165문항을 보완함 — 표·그림이 빠져 있던 57문항(A), 보기·본문이 빠져 있던 79문항(B), "
        "이미지 전용이라 제외했던 13문항을 새로 추가(C), 원문과 표기가 달랐던 16문항(D, 표기 차이는 원문대로 반영. 다만 문제 풀이를 틀어지게 하는 코드 오타는 고침: 2020-1 문제 6·2022-3 문제 12의 'SELECT DERP'는 'SELECT DEPT'로 수정). "
        "표는 진짜 표로 옮겼고, 그림은 원문을 보고 다시 그려 '▲ 원문 그림을 보고 다시 그린 도식'이라고 표시함(원문 그림과 세부 모양·배치가 다를 수 있으니 원문 링크로 확인). "
        "원문 페이지 자체에 보기가 실려 있지 않은 문항은 '(실제 기출문제에서는 보기가 주어집니다)' 같은 원문 안내만 남아 있음.")
RANGE = (f"총 {len(rounds)}개 회차, {total_q}문제 수집" +
         (f" / {total_img}문제는 원문이 이미지(표·다이어그램)로만 되어 있어 제외" if total_img else " (원문이 표·그림으로만 되어 있던 문제도 표는 표로, 그림은 다시 그려 포함)"))
lines.append(f"- **보완 이력**: {HIST}")
lines.append(f"- **수집 범위**: {RANGE}")
lines.append("- **주의**: 이 문서는 학습 참고용으로 정리한 것이며, 정답의 정확성을 100% 보장하지 않습니다. 실제 복원문제 특성상(응시자의 기억에 의존) 원 시험과 세부 표현이 다를 수 있습니다.")
lines.append("")
lines.append("---")
lines.append("")
lines.append("## 목차")
lines.append("")
for r in rounds:
    y, rd = r["year"], r["round"]
    n_q = len(r["questions"])
    n_img = len(r.get("image_only_questions", []))
    anchor = f"{y}년-{rd}회"
    lines.append(f"- [{y}년 {rd}회](#{y}년-{rd}회-실기-복원문제) ({n_q}문제{f', 이미지 문제 {n_img}개 제외' if n_img else ''})")
lines.append("")
lines.append("---")
lines.append("")

for r in rounds:
    y, rd = r["year"], r["round"]
    lines.append(f"## {y}년 {rd}회 실기 복원문제")
    lines.append("")
    lines.append(f"- 원문: [{r['source_url']}]({r['source_url']})")
    lines.append(f"- 저작자: {r['source_author']} · 라이선스: {r['license']}")
    img_list = r.get("image_only_questions", [])
    if img_list:
        nums = ", ".join(str(n) for n in img_list)
        lines.append(f"- ⚠️ {nums}번 문제는 원문이 표/다이어그램 이미지로만 제공되어 이 문서에서는 제외했습니다. 원문 링크에서 직접 확인해주세요.")
    lines.append("")

    for q in r["questions"]:
        num = q["number"]
        lang = fmt.display_language(q.get("language"))   # 원본의 '기타' → 문서에서는 '이론' 
        diff = q.get("difficulty")
        diff_str = f" · 난이도 {diff}" if diff else ""
        lines.append(f"### {y}-{rd} 문제 {num} ({lang}{diff_str})")
        lines.append("")
        blocks = fmt.format_prompt(q["prompt"], f"{y}-{rd}#{num}")
        assert fmt.verify(q["prompt"], blocks), f"원문 불일치: {y}-{rd}#{num}"
        lines.extend(fmt.to_markdown_lines(blocks))
        code = (q.get("code") or "").strip("\n")
        ctable = fmt.code_table(code)
        if ctable:                      # code 칸에 들어 있던 파이프 표 → 진짜 표로
            lines.extend(fmt.md_table_lines(ctable))
        elif code.strip():
            lang_tag = {"Python": "python", "Java": "java", "C": "c"}.get(lang, "")
            lines.append(f"```{lang_tag}")
            lines.append(code)
            lines.append("```")
            lines.append("")
        lines.append(f"**정답**: {q['answer']}")
        lines.append("")
        expl = (q.get("explanation") or "").strip()
        if expl:
            el = fmt.format_explanation(expl, f"{y}-{rd}#{num}")
            assert fmt.verify_explanation(expl, el), f"해설 불일치: {y}-{rd}#{num}"
            if len(el) == 1:
                lines.append(f"**해설**: {el[0]['t']}")
            else:                       # 항목별로 줄을 나눈 해설: 라벨 줄 + 항목 줄들(하드 브레이크)
                lines.append("**해설**:  ")
                lines += [l["t"] + "  " for l in el[:-1]] + [el[-1]["t"]]
            lines.append("")
    lines.append("---")
    lines.append("")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("OK:", OUT_PATH, "-", len("\n".join(lines)), "chars,", total_q, "questions,", len(rounds), "rounds")
