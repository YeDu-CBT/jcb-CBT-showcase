# jcb-CBT-showcase — 정보처리기사 실기 CBT 제작 파이프라인

정보처리기사 실기 기출 복원문제(2020~2026년 21개 회차, 출제 420건)를 웹에서 모아 **검수 → 구조화 → 문서(MD·DOCX·HWP) → CBT 모의고사 사이트**로 만든 작업의 코드와 설계 문서입니다. AI 에이전트(Claude)와 협업해 만들었고, 그 과정의 규칙과 실수를 지침서와 개발 일지로 남겼습니다.

> **문제 데이터는 이 저장소에 없습니다.** 문제 본문은 다른 저자의 블로그 글(CC BY / CC BY-NC-ND)이라, 공개 저장소에는 코드·시험·문서만 올렸습니다(맨 아래 "출처와 라이선스").

## 무엇을 만들었나

**데이터 검수**
- 원본(`raw/*.json`) 하나에서 문서와 사이트를 모두 다시 만드는 구조. 산출물은 손으로 고치지 않음
- 2차 대조로 표·그림·보기가 빠진 165문항 보완, 그림으로만 있던 13문항 복원(그림은 다시 그림)
- 코드 문제 정답을 실제 실행 출력과 대조해 7문항 수정, 코드 오탈자 15문항 수정
- 여러 회차에 다시 나온 같은 문제 17건을 합쳐 고유 문항 403개로 정리(원본은 그대로 두고 사이트용 데이터에서만 합침, 규칙 파일 `jcb_restored/dup_merges.json`)
- 한 줄로 붙어 있던 지문을 지시문·본문·보기·표·그림 블록으로 나누고, 다시 이어 붙였을 때 원문과 글자 하나까지 같은지 자동 검증

**CBT 사이트** (바닐라 JavaScript 단일 파일, 오프라인 단일 HTML 버전 포함)
- 실전/학습 모드, 자동 채점(완전 일치)과 자가 채점, 빈칸 번호별 답안란, 해설
- 풀이 중간 저장, 답안칸 자동 포커스, 코드 복사 버튼
- 같은 문제의 Java/C 판 탭, 비슷하지만 정답이 다른 문제 표시, 합친 문제의 출제 회차 표시
- 학습 모드 메모패드(서식 편집기 — 붙여 넣은 내용은 허용 목록 방식으로 정화), 메모가 있는 문항 표시
- 기기 간 동기화, 기록 파일 내보내기/가져오기, 폴더 연결(크롬·엣지)
- 화면 맨 위 버전 칩(`Ver 2.5 · 수정 21회` — 게시할 때마다 +1)

**검증**
- Playwright 회귀 시험을 웹 · 단일 파일(http) · 단일 파일(`file://`) 세 환경에서 실행(과거 결과: `tests/reg_summaries/`)
- 기기 간 동기화와 폴더 연결은 **모의 환경에서만** 검증했습니다(실제 서비스·실제 폴더 선택창은 확인 전)

## 폴더 구성

```
jcb-CBT-showcase/
├─ jcb_restored/
│   ├─ format_prompts.py        지문 구조화 + 재구성 검증
│   ├─ build_md.py              마크다운 문서
│   ├─ build_docx.js            DOCX (docx-js)
│   ├─ build_hwpx.py / verify_hwpx.py   한글 문서와 그 검사
│   ├─ dup_merges.json          같은 문제 합치기 규칙 (문항 번호·주제만 담김)
│   ├─ CBT_제작_에이전트_지침.md  작업 규칙·함정 95개 (v1.15)
│   ├─ 문서_서식_에이전트_지침.md  DOCX·한글 서식 규칙
│   └─ CBT_제작_개발일지.md       지침서 v1.0 → v1.15 개발 일지
├─ jcb_cbt/
│   ├─ build_data.py            원본 → 사이트 데이터 (채점 분류, 답안칸 분할, 합치기)
│   ├─ tools/answer_parts.py    정답을 번호별 칸으로 나누기
│   ├─ build_standalone.py      오프라인 단일 HTML 만들기
│   └─ site/index.html          사이트 본체 (데이터 없이는 문제 목록이 비어 있음)
└─ tests/                       Playwright 시험, 가짜 저장 서버, 실행 스크립트
```

모든 스크립트는 **자기 파일 위치를 기준으로 한 상대 경로**를 씁니다. `jcb_restored`와 `jcb_cbt`는 나란히 두어야 합니다.

## 원본 데이터 형식 (예시 값)

```json
{"year": 2025, "round": 1, "source_url": "…", "source_author": "…", "license": "CC BY",
 "questions": [{"number": 1, "language": "Java", "difficulty": "",
   "prompt": "지시문·본문·보기 (원문 줄바꿈 보존)",
   "code": "코드가 있는 문항만 (들여쓰기 보존)", "answer": "…", "explanation": ""}],
 "image_only_questions": []}
```

이 형식의 파일을 `jcb_restored/raw/`에 두면 아래 순서로 돌아갑니다.

```bash
python3 jcb_restored/format_prompts.py --dump jcb_restored/formatted_prompts.json \
        --dump-expl jcb_restored/formatted_explanations.json --dump-ctable jcb_restored/formatted_code_tables.json
python3 jcb_restored/build_md.py
python3 jcb_cbt/build_data.py
python3 jcb_cbt/build_standalone.py
bash tests/run_regression.sh web
```

`.gitignore`가 `raw/`, `data.json` 등 문제 본문이 든 파일을 막아 두었으므로, 데이터를 넣고 돌려도 실수로 커밋되지 않습니다. 시험 일부는 실제 문항 번호를 기대값으로 쓰기 때문에, 다른 데이터에서는 실패할 수 있습니다.

## 출처와 라이선스

- 문제 원문 주 출처: Life-Journey 블로그 https://chobopark.tistory.com (CC BY). `format_prompts.py`의 예외 지정과 일부 시험 코드에 원문 지시문·코드의 짧은 조각이 들어 있으며, 이 출처의 CC BY 조건(저작자·출처 표시)에 따라 여기 밝힙니다.
- 비교 출처: sssinga 블로그 (CC BY-NC-ND 4.0). 이 출처에서 온 내용(교체한 13문항, 다시 그린 그림, 비교 목록)은 **이 저장소에 넣지 않았습니다.**
- 이 저장소의 코드에 붙일 라이선스는 저장소 주인이 정합니다(아직 정하지 않음).
