#!/usr/bin/env python3
"""정보처리기사 복원문제 prompt 구조화 (지시문 / 본문 / 보기 → 줄바꿈 분리).

원칙
  1) 글자는 바꾸지 않는다. 바뀌는 것은 '공백(줄바꿈 포함)'뿐이다.
     예외: 항목 사이의 구분자 ' / ' 를 줄바꿈으로 대체할 때만 '/' 를 제거(sep 로 기록 → 검증 시 복원).
  2) 1차: 규칙 기반 분리  →  2차: OVERRIDES(문항별 수동 지정)  →  3차: verify() 로 원문 보존 검증.

출력 형식 (format_prompt 반환값)
  [ {"kind": "inst"|"body"|"opt", "lines": [ {"t": str, "sep": str|None}, ... ]}, ... ]
"""
import re, json, glob, os

JAMO = 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ'
CIRC_HAN = '㉠㉡㉢㉣㉤㉥㉦㉧㉨㉩㉪㉫㉬㉭'
CIRC_NUM = '①②③④⑤⑥⑦⑧⑨⑩'

# ---------------------------------------------------------------- 문장 분리
SENT_RE = re.compile(r"(?<=[가-힣\)\]])([.?])\s+(?=\S)")


def split_sentences(text):
    """문장 종결(한글/닫는괄호 뒤의 . ?) + 공백 에서 자른다. 종결부호는 앞 문장에 남긴다."""
    out, last = [], 0
    for m in SENT_RE.finditer(text):
        out.append(text[last:m.end(1)])
        last = m.end()
    out.append(text[last:])
    return [s for s in out if s]


IMPER_RE = re.compile(
    r"(시오\.?|십시오\.?|하라\.?|인가\?|은가\?|는가\?|가요\?|는지\?|까\?|것은\?|무엇인가\?|\?)\s*$")
INTRO_RE = re.compile(r"^(다음|아래|위)")
HINT_KEYS = ('작성', '글자', '약자', '문항', '영문', '한글', '영어', 'SQL', '순서', '모두', '기호', '쓰시오')
HINT_RE = re.compile(r"^\s*(\([^()]{1,30}\))")


def is_imperative(s):
    t = re.sub(r"\s*\([^()]*\)\s*$", "", s.strip())   # 끝의 '(8진법을 사용하시오)' 같은 괄호는 무시하고 판정
    return bool(IMPER_RE.search(t))


# ---------------------------------------------------------------- 항목(번호/ㄱㄴㄷ) 분리
def _chain(text, pat, idx_of, need=2):
    """pat 의 매치 중 라벨 번호가 '증가'하는 체인(첫 라벨은 1/ㄱ/① 또는 2/ㄴ/②, 건너뜀 허용 ≤3)의 시작 위치."""
    chain, prev = [], None
    for m in pat.finditer(text):
        idx = idx_of(m)
        if prev is None:
            if idx <= 1:
                chain.append(m.start()); prev = idx
        elif 0 < idx - prev <= 3:
            chain.append(m.start()); prev = idx
    return chain if len(chain) >= need else []


def _jamo_idx(m):
    return JAMO.index(m.group(1))


FAMILIES = [
    # (이름, 정규식, 라벨→번호)
    ('paren_num', re.compile(r"(?:(?<=\s)|^)\(\s*(\d{1,2})\s*\)\s*(?!은/는|은 |는 |을 |를 |이 |가 |과|와|에|의|로|도|개|\)|[/,.]|\s*(?:은|는)\b|$)"),
     lambda m: int(m.group(1)) - 1),
    ('num_dot', re.compile(r"(?:(?<=\s)|^)(\d{1,2})\.\s+(?=[^\d\s)])(?!\s*\))"), lambda m: int(m.group(1)) - 1),
    ('num_paren', re.compile(r"(?:(?<=\s)|^)(\d{1,2})\)\s+"), lambda m: int(m.group(1)) - 1),
    ('jamo', re.compile(r"(?:(?<=\s)|^|(?<=/))([ㄱ-ㅎ])[\.\)]\s*"), _jamo_idx),
    ('circ_han', re.compile(r"(?:(?<=\s)|^)([㉠-㉭])"), lambda m: CIRC_HAN.index(m.group(1))),
    ('circ_num', re.compile(r"(?:(?<=\s)|^)(?<!\()([①-⑩])(?!\s*\))"), lambda m: CIRC_NUM.index(m.group(1))),
    ('alpha_lo', re.compile(r"(?:(?<=\s)|^)([a-e])\.\s+"), lambda m: ord(m.group(1)) - 97),
    ('alpha_up', re.compile(r"(?:(?<=\s)|^)([A-E])\.\s+"), lambda m: ord(m.group(1)) - 65),
]
BULLET_RE = re.compile(r"(?:(?<=\s)|^)([-•·▪])\s+(?=\S)")


def find_cuts(text):
    best = (None, [])
    for name, pat, f in FAMILIES:
        ch = _chain(text, pat, f)
        if ch and (best[0] is None or ch[0] < best[1][0]
                   or (ch[0] == best[1][0] and len(ch) > len(best[1]))):
            best = (name, ch)
    ms = [m.start() for m in BULLET_RE.finditer(text)]
    if len(ms) >= 2 or (len(ms) == 1 and ms[0] == 0):
        if best[0] is None or ms[0] < best[1][0]:
            best = ('bullet', ms)
    return best


def mk_line(t):
    """끝의 ' /' 구분자는 sep 로 분리."""
    t = t.strip()
    m = re.search(r"\s+/$", t)
    if m:
        return {"t": t[:m.start()].rstrip(), "sep": "/"}
    return {"t": t, "sep": None}


def split_items(text):
    """text → 줄 리스트. 항목 체인이 있으면 항목별로, 없으면 한 줄."""
    text = text.strip()
    if not text:
        return []
    name, cuts = find_cuts(text)
    if not name:
        return [mk_line(text)]
    lines = []
    pts = [c for c in cuts]
    if pts[0] > 0:
        lead = text[:pts[0]].strip()
        if lead:
            lines.append(mk_line(lead))
    for i, p in enumerate(pts):
        e = pts[i + 1] if i + 1 < len(pts) else len(text)
        seg = text[p:e].strip()
        if seg:
            lines.append(mk_line(seg))
    return lines


# 라벨형 소제목: "조건:", "공격 절차:", "구하는 것:" 등 → 새 줄에서 시작
LABEL_RE = re.compile(r"(?:(?<=\.\s)|(?<=다\s)|(?<=오\s)|^)((?:테이블 )?조건|공격 절차|구하는 것|출력값|\[ ?출력값 ?\])\s*[:：]?")


def split_body(text):
    """본문 → 줄들. 라벨(조건: 등)이 있으면 라벨 앞에서 줄을 나누고, 각 구간은 항목 분리."""
    text = text.strip()
    if not text:
        return []
    # 라벨 위치 찾기 (문장 시작에서 '조건:' 처럼 콜론이 붙은 것만)
    pos = [m.start() for m in re.finditer(r"(?:(?<=\s)|^)(?:테이블 조건|조건|공격 절차|구하는 것|\[ ?출력값 ?\])\s*:", text)]
    # 앞 줄 + 라벨 구간
    cuts = [p for p in pos if p > 0]
    segs, last = [], 0
    for p in cuts:
        segs.append(text[last:p]); last = p
    segs.append(text[last:])
    lines = []
    for sgm in segs:
        lines += _split_labeled(sgm)
    out = []
    for l in lines:
        out += _split_slash(l)
    return out


def _split_slash(l):
    """' / ' 로 이어 붙인 서술(각 10자 이상)을 줄로 분리. 짧은 나열(읽기 / 쓰기 / 실행)은 그대로."""
    if l['sep'] or ' / ' not in l['t']:
        return [l]
    pieces = [p.strip() for p in re.split(r"\s+/\s+", l['t'])]
    core = [re.sub(r"^[^:：]{1,14}[:：]\s*", "", p) for p in pieces]
    if len(pieces) < 2 or not all(len(c) >= 10 for c in core):
        return [l]
    out = []
    m = re.match(r"^(조건\s*[:：])\s*(.+)$", pieces[0])
    if m:
        out.append({"t": m.group(1), "sep": None})
        pieces[0] = m.group(2)
    for i, p in enumerate(pieces):
        out.append({"t": p, "sep": "/" if i < len(pieces) - 1 else None})
    return out


def _split_labeled(seg):
    seg = seg.strip()
    if not seg:
        return []
    m = re.match(r"^((?:테이블 조건|조건|공격 절차|구하는 것)\s*:)\s*(.*)$", seg)
    if m:
        lab, rest = m.group(1), m.group(2)
        name, cuts = find_cuts(rest) if rest else (None, [])
        if rest and name:
            return [mk_line(lab)] + split_items(rest)
        # 라벨 뒤가 항목 체인이 아니면: 한 줄 유지
        if rest and ':' not in rest:
            sents = split_sentences(rest)
            if len(sents) >= 2 and lab.startswith(('조건', '테이블')):
                return [mk_line(lab)] + [mk_line(x) for x in sents]
        return [mk_line(seg)]
    return split_items(seg)


# ---------------------------------------------------------------- 보기(옵션) 꼬리
OPT_RE = re.compile(r"(?:[\(\[<＜]\s*)?보기\s*(?:[\]\)>＞]\s*[:：]?\s*|[:：]\s*)")
AFTER_BAD = re.compile(r"^(에서|에|를|을|중|의|와|과|로|이|가|\s*에서)")


def find_opt_tail(text):
    last = None
    for m in OPT_RE.finditer(text):
        after = text[m.end():]
        if AFTER_BAD.match(after) or len(after.strip()) < 2:
            continue
        # '<보기>에서 골라' 처럼 닫는 괄호 바로 뒤가 조사이면 제외 (위에서 처리)
        last = m
    return last


def build_opt_block(opt_text):
    m = OPT_RE.match(opt_text)
    head = opt_text[:m.end()].strip()
    rest = opt_text[m.end():].strip()
    name, cuts = find_cuts(rest)
    if name:
        return {"kind": "opt", "lines": [mk_line(head)] + split_items(rest)}
    if ' / ' in rest:
        parts = rest.split(' / ')
        lines = [mk_line(head)]
        for i, p in enumerate(parts):
            lines.append({"t": p.strip(), "sep": "/" if i < len(parts) - 1 else None})
        return {"kind": "opt", "lines": lines}
    return {"kind": "opt", "lines": [mk_line(opt_text)]}


# ---------------------------------------------------------------- head 분류: 지시문 / 본문
INTRO_END_RE = re.compile(r"(문제|설명|내용|것|코드)(이다|입니다)\.?$")


def is_intro(sent):
    t = sent.strip()
    if is_imperative(t):
        return False
    return bool(INTRO_RE.match(t)) or (len(t) <= 50 and bool(INTRO_END_RE.search(t)))


def classify_head(head):
    """head(문자열) → [block...] (inst/body 순서 유지)."""
    head = head.strip()
    if not head:
        return []
    sents = split_sentences(head)
    k = next((i for i, s in enumerate(sents) if is_imperative(s)), None)
    if k is None:
        # 지시문이 원문에 없는 경우: 맨 앞 '다음은 ~이다.' 류 도입 문장만 지시문으로
        if INTRO_RE.match(sents[0].strip()) and (len(sents) > 1 or True):
            rest = ' '.join(sents[1:])
            out = [{"kind": "inst", "lines": [mk_line(sents[0])]}]
            if rest:
                out.append({"kind": "body", "lines": split_body(rest)})
            return out
        return [{"kind": "body", "lines": split_body(head)}]
    j = k
    while j - 1 >= 0 and is_intro(sents[j - 1]):
        j -= 1
    pre = ' '.join(sents[:j])
    inst = ' '.join(sents[j:k + 1])
    post = ' '.join(sents[k + 1:])
    # 지시문 뒤 괄호 힌트 "(3글자로 작성)", "(SQL)", "(8진법 사용)"
    mh = HINT_RE.match(post)
    if mh:
        inner = mh.group(1)[1:-1]
        whole = (post[mh.end():].strip() == '')
        kw = any(x in mh.group(1) for x in HINT_KEYS)
        short_tag = whole and len(inner) <= 14 and '제시' not in inner and not inner.startswith('단')
        if kw or short_tag:
            inst = inst + ' ' + mh.group(1)
            post = post[mh.end():].strip()
    blocks = []
    if pre:
        blocks.append({"kind": "body", "lines": split_body(pre)})
    blocks.append({"kind": "inst", "lines": [mk_line(inst)]})
    tail_inst = None
    if post:
        ps = split_sentences(post)
        # 본문 맨 끝 문장이 다시 '~얼마인가?/~구하시오.' 이면 별도 지시문으로 분리
        if len(ps) >= 2 and is_imperative(ps[-1]) and not find_cuts(post)[0]:
            tail_inst = ps[-1]
            post = ' '.join(ps[:-1])
    if post:
        blocks.append({"kind": "body", "lines": split_body(post)})
    if tail_inst:
        blocks.append({"kind": "inst", "lines": [mk_line(tail_inst)]})
    return blocks


# ---------------------------------------------------------------- 전체
def norm(s):
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- 원문 대조로 복원한 문항(restored_specs.json)
# 누락 문제 모음(2차 대조)을 본 문서에 반영하면서, 문항별로 (지시문/본문/보기/표/그림) 블록 구조를 미리 확정해 둔 파일.
# merge_missing.py 가 만든다. 여기서는 읽기만 한다.
RESTORED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'restored_specs.json')
RESTORED = {}
if os.path.exists(RESTORED_PATH):
    RESTORED = json.load(open(RESTORED_PATH, encoding='utf-8'))


def table_lines(rows, caption=None, header=True):
    """표 rows → 원문 줄 표기(캡션 줄 + '| a | b |' 줄들). 머리글이 있으면 구분행(| --- |)을 넣는다."""
    out = []
    if caption:
        out.append({'t': caption, 'sep': None})
    for ri, r in enumerate(rows):
        out.append({'t': '| ' + ' | '.join(r) + ' |', 'sep': None})
        if ri == 0 and header:
            out.append({'t': '| ' + ' | '.join('---' for _ in r) + ' |', 'sep': None})
    return out


def _restored_blocks(spec):
    out = []
    for b in spec:
        k = b['kind']
        if k in ('inst', 'body', 'opt'):
            out.append({'kind': k, 'lines': [dict(l) for l in b['lines']]})
        elif k == 'table':
            hd = b.get('header', True)
            out.append({'kind': 'table', 'caption': b.get('caption'), 'rows': b['rows'], 'header': hd,
                        'lines': table_lines(b['rows'], b.get('caption'), hd)})
        elif k == 'image':
            out.append({'kind': 'image', 'lines': [], 'file': b['file'], 'alt': b.get('alt', ''),
                        'caption': b.get('caption'), 'w': b.get('w'), 'h': b.get('h')})
        else:
            raise ValueError('unknown block kind: ' + k)
    return out


def _format_prompt_core(prompt, key=None):
    if key in RESTORED:
        return _restored_blocks(RESTORED[key])
    if key in OVERRIDES:
        return OVERRIDES[key](prompt)
    p = prompt.strip()
    if '\n' in p:
        return format_preserved(p)
    p = norm(p)
    m = find_opt_tail(p)
    blocks = []
    if m:
        head, tail = p[:m.start()], p[m.start():]
        blocks += classify_head(head)
        blocks.append(build_opt_block(tail))
    else:
        blocks += classify_head(p)
    return blocks


# ---------------------------------------------------------------- 박스(직사각형) 지정
BOX_TRIGGER = re.compile(r"다음|아래")
# 보기(opt) 블록이지만 실제로는 '설명 본문'이라서 박스에 넣을 문항
BOX_OPT_KEYS = {'2020-1#15', '2020-2#10'}


def assign_boxes(blocks, key=None):
    """지시문에 '다음'/'아래'가 있으면, 그 지시문 바로 뒤에 이어지는 본문(body) 블록들을 box=True 로 표시.
    table 블록을 만나면 멈춘다(표는 자체 테두리가 있으므로 박스에 넣지 않는다)."""
    for i, b in enumerate(blocks):
        if b['kind'] == 'inst' and BOX_TRIGGER.search(' '.join(l['t'] for l in b['lines'])):
            j = i + 1
            while j < len(blocks) and blocks[j]['kind'] in ('body', 'image'):
                blocks[j]['box'] = True
                j += 1
            if j < len(blocks) and key in BOX_OPT_KEYS and blocks[j]['kind'] == 'opt':
                blocks[j]['box'] = True
    for b in blocks:                      # 그림은 지시문에 '다음/아래'가 없어도 항상 네모칸 안에 둔다
        if b['kind'] == 'image':
            b['box'] = True
    return blocks


# ---------------------------------------------------------------- 파이프(|) 표 복원
# 원문에 "| a | b |" (마크다운식) 또는 "a | b" (맨 파이프) 로 적힌 표를 찾아 table 블록으로 만든다.
# table 블록의 lines 는 원문 줄을 그대로 보존한다(재구성 검증 유지). rows 는 그리기용 파생 데이터.
_SEP_CELL = re.compile(r"^:?-{2,}:?$")
_CAPTION_RE = re.compile(r"^\[[^\[\]|]{1,30}\]$")      # [학생 테이블], [결과] 같은 표 제목


def _split_row(t):
    s = t.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    return [c.strip() for c in s.split('|')]


def _row_cells(l):
    """줄이 표의 한 줄이면 셀 리스트, 아니면 None. 맨 파이프는 ' | ' (공백으로 둘러싸인 파이프)가 있어야 인정."""
    if l.get('sep'):
        return None
    t = l['t']
    if '|' not in t:
        return None
    if not (t.lstrip().startswith('|') or re.search(r"\s\|\s", t)):
        return None
    cells = _split_row(t)
    return cells if len(cells) >= 2 else None


def _is_sep_row(cells):
    return all(_SEP_CELL.match(c) for c in cells)


def _find_table_run(lines, i):
    """lines[i:] 에서 시작하는 표 구간을 찾는다. 반환: (끝 인덱스(제외), rows) 또는 None.
    조건: 구분행을 뺀 줄이 2개 이상이고 모든 줄의 열 수가 같다."""
    rows, k, ncol = [], i, None
    while k < len(lines):
        cells = _row_cells(lines[k])
        if cells is None:
            break
        if _is_sep_row(cells):
            if not rows:           # 구분행이 맨 앞이면 표가 아니다
                return None
            k += 1
            continue
        if ncol is None:
            ncol = len(cells)
        elif len(cells) != ncol:
            break
        rows.append(cells)
        k += 1
    if len(rows) >= 2 and ncol and ncol >= 2:
        return k, rows
    return None


def detect_tables(blocks):
    """body 블록 안의 파이프 표를 table 블록으로 분리. 앞뒤의 나머지 줄은 body 로 남긴다."""
    out = []
    for b in blocks:
        if b['kind'] != 'body':
            out.append(b)
            continue
        lines, cur, i = b['lines'], [], 0
        while i < len(lines):
            run = _find_table_run(lines, i) if _row_cells(lines[i]) else None
            if not run:
                cur.append(lines[i]); i += 1
                continue
            end, rows = run
            tlines = lines[i:end]
            caption = None
            if cur and _CAPTION_RE.match(cur[-1]['t']) and not cur[-1].get('sep'):
                cap = cur.pop()
                caption = cap['t']
                tlines = [cap] + tlines
            if cur:
                out.append({'kind': 'body', 'lines': cur})
                cur = []
            out.append({'kind': 'table', 'caption': caption, 'rows': rows, 'lines': tlines})
            i = end
        if cur:
            out.append({'kind': 'body', 'lines': cur})
    return out


def verify_table(b):
    """table 블록의 rows 가 lines 의 글자를 빠짐없이 담고 있는지(파이프·공백·구분행 제외하고 비교)."""
    body_lines = [l for l in b['lines'] if not (b.get('caption') and l['t'] == b['caption'])]
    want = ''
    for l in body_lines:
        cells = _row_cells(l)
        if cells is not None and _is_sep_row(cells):
            continue
        if re.fullmatch(r"\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*", l['t']):   # 열이 하나뿐인 표의 구분행
            continue
        want += re.sub(r"[\s|]+", "", l['t'])
    got = re.sub(r"[\s|]+", "", ''.join(c for r in b['rows'] for c in r))
    ncols = {len(r) for r in b['rows']}
    return want == got and len(ncols) == 1


def code_table(code):
    """code 필드 전체가 파이프 표이면 rows, 아니면 None. (표가 코드 칸에 들어 있는 이론 문항용)"""
    lines = [mk_line(x) for x in (code or '').strip().split('\n') if x.strip()]
    if not lines or not _row_cells(lines[0]):
        return None
    run = _find_table_run(lines, 0)
    if run and run[0] == len(lines):
        return run[1]
    return None


def format_prompt(prompt, key=None):
    return assign_boxes(detect_tables(_format_prompt_core(prompt, key)), key)



def format_preserved(p):
    """원문에 이미 줄바꿈이 있는 14개 문항: 줄바꿈을 존중하면서 종류만 부여."""
    paras = re.split(r"\n\s*\n", p)
    blocks = []
    for bi, para in enumerate(paras):
        lines = [l.strip() for l in para.split('\n') if l.strip()]
        if not lines:
            continue
        first = lines[0]
        if re.match(r"^[\[\(<]\s*보기", first):
            mm = OPT_RE.match(first)
            hd = first[:mm.end()].strip() if mm else first
            rest = first[mm.end():].strip() if mm else ''
            ls = [mk_line(hd)]
            if rest:
                ls.append(mk_line(rest))
            ls += [mk_line(x) for x in lines[1:]]
            blocks.append({"kind": "opt", "lines": ls})
            continue
        if bi == 0:
            blocks += classify_head(first)
            if len(lines) > 1:
                blocks.append({"kind": "body", "lines": [mk_line(x) for x in lines[1:]]})
        else:
            blocks.append({"kind": "body", "lines": [mk_line(x) for x in lines]})
    return blocks


OVERRIDES = {}   # key -> callable(prompt) -> blocks  (아래에서 채움)


def _spec(spec):
    """spec = [(kind, [line, ...]), ...]; 줄 끝이 ' /' 이면 sep='/' 로 기록."""
    blocks = []
    for kind, lines in spec:
        ls = []
        for t in lines:
            ls.append(mk_line(t))
        blocks.append({"kind": kind, "lines": ls})
    return blocks


def _ov(key, spec):
    OVERRIDES[key] = lambda prompt, _s=spec: _spec(_s)


# ---- 문항별 수동 지정 (규칙으로 처리되지 않는 예외) ----
_ov('2026-2#16', [
    ('inst', ['다음은 IP 주소 서브네팅(Subnetting)에 대한 설명이다. 물음에 답하시오.']),
    ('body', ['10.0.0.0/27 네트워크를 동일한 크기의 2개 서브넷으로 분할하였다.',
              '- 첫 번째 서브넷: 10.0.0.0 ~ 10.0.0.15',
              '- 두 번째 서브넷: 10.0.0.16 ~ 10.0.0.31.']),
    ('inst', ['이때 10.0.0.1이 속한 서브넷의 프리픽스 길이(비트 수)를 구하시오.']),
])


# ---------------------------------------------------------------- 해설: ' / ' 구분 → 줄바꿈
# 원칙은 지문과 같다: 글자는 그대로, 항목 사이 ' / ' 의 '/' 만 줄바꿈으로 대체(sep 기록).
EXPL_KEEP_INLINE = {'2020-4#15'}      # '유효 값 / 무효 값' 처럼 문장 안의 병기 → 그대로 둔다
# 키 -> {'markers': [조각 맨 앞에서 떼어낼 머리말...], 'cut_before': [그 앞에서 줄을 나눌 문구...]}
EXPL_HINTS = {
    '2020-3#10': {'markers': ['순수관계연산자는']},
    '2020-3#11': {'markers': ['식별자 표기법 :']},
    '2020-3#18': {'markers': ['EAI의 유형(데이터 전송 모델):']},
    '2020-4#2':  {'markers': ['디자인 패턴 목적:', '행위,', '범위:']},
    '2020-4#17': {'markers': ['유닉스 계열 운영체제의 특징:']},
    '2020-4#20': {'markers': ['SW개발 보안의 3개 요소:'], 'cut_before': ['기밀성 - ', '무결성 - ']},
}


def format_explanation(expl, key=None):
    """해설 문자열 → 줄 리스트 [{'t','sep'}]. ' / ' 가 없으면 한 줄."""
    e = (expl or '').strip()
    if not e:
        return []
    if '\n' in e:
        return [mk_line(x) for x in e.split('\n') if x.strip()]
    if ' / ' not in e or key in EXPL_KEEP_INLINE:
        return [mk_line(e)]
    hint = EXPL_HINTS.get(key, {})
    pieces = [x.strip() for x in e.split(' / ')]
    lines = []
    for pi, piece in enumerate(pieces):
        last = pi == len(pieces) - 1
        parts = []
        # cut_before: 해당 문구 앞에서 줄 나누기 (공백만 바뀜)
        for cb in hint.get('cut_before', []):
            idx = piece.find(cb)
            if idx > 0:
                parts.append(piece[:idx].strip()); piece = piece[idx:].strip()
        # markers: 조각 맨 앞의 머리말을 별도 줄로
        changed = True
        while changed:
            changed = False
            for m in hint.get('markers', []):
                if piece.startswith(m) and len(piece) > len(m):
                    parts.append(m); piece = piece[len(m):].strip(); changed = True
        parts.append(piece)
        for qi, part in enumerate(parts):
            is_end = qi == len(parts) - 1
            lines.append({'t': part, 'sep': '/' if (is_end and not last) else None})
    return lines


def verify_explanation(expl, lines):
    return norm(' '.join(l['t'] + ((' ' + l['sep']) if l['sep'] else '') for l in lines)) == norm(expl or '')


# 화면 표기용 분류 이름: 원본 데이터의 '기타'(이론 문제)는 문서에서 '이론'으로 표기
def display_language(lang):
    return '이론' if (not lang or lang == '기타') else lang


# ---------------------------------------------------------------- 검증
def reconstruct(blocks):
    parts = []
    for b in blocks:
        for l in b['lines']:
            parts.append(l['t'] + ((' ' + l['sep']) if l['sep'] else ''))
    return norm(' '.join(parts))


def verify(prompt, blocks):
    return reconstruct(blocks) == norm(prompt)


def load_all(raw_dir=None):
    raw_dir = raw_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw')
    out = []
    for f in sorted(glob.glob(os.path.join(raw_dir, '*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        for q in d['questions']:
            out.append((f"{d['year']}-{d['round']}#{q['number']}", q))
    return out


def _md_cell(t):
    return t.replace('|', '\\|')


def md_table_lines(rows, caption=None, header=True):
    """rows(첫 줄=머리글) → GFM 표 줄. 표 제목이 있으면 그 앞에 한 줄로 쓰고 빈 줄을 둔다.
    header=False(머리글 없는 값 표)이면 GFM 문법상 필요한 머리글 줄을 빈 칸으로 채운다."""
    out = []
    if caption:
        out += [caption, '']
    ncol = len(rows[0])
    if header:
        out.append('| ' + ' | '.join(_md_cell(c) for c in rows[0]) + ' |')
        body = rows[1:]
    else:
        out.append('|' + '   |' * ncol)
        body = rows
    out.append('|' + '---|' * ncol)
    for r in body:
        out.append('| ' + ' | '.join(_md_cell(c) for c in r) + ' |')
    out.append('')
    return out


def to_markdown_lines(blocks):
    """블록 → 마크다운 줄 리스트.
    - 일반 블록: 블록 사이는 빈 줄, 블록 안의 줄은 하드 브레이크(끝 공백 2칸)
    - box=True 블록: 연속된 것들을 한 칸짜리 표(직사각형 테두리)로 묶는다. 줄바꿈은 <br>.
    - table 블록: 진짜 표(GFM). 머리글 행 + 구분행 + 데이터 행."""
    out = []
    i = 0
    n = len(blocks)
    while i < n:
        b = blocks[i]
        if b['kind'] == 'table':
            out += md_table_lines(b['rows'], b.get('caption'), b.get('header', True))
            i += 1
            continue
        ts = [l['t'] for l in b['lines']]
        if b.get('box'):
            grp = []
            while i < n and blocks[i].get('box') and blocks[i]['kind'] != 'table':
                grp.append(blocks[i]); i += 1

            def _cell_part(g):
                if g['kind'] == 'image':      # 그림: 이미지 + (있으면) 작은 설명
                    alt = (g.get('alt') or '').replace('[', '(').replace(']', ')')
                    part = f"![{alt}]({g['file']})"
                    if g.get('caption'):
                        part += f"<br><sub>{g['caption']}</sub>"
                    return part
                return '<br>'.join(_md_cell(l['t']) for l in g['lines'])
            cell = '<br><br>'.join(_cell_part(g) for g in grp)
            out += ['|   |', '|---|', f'| {cell} |', '']
            continue
        out += [t + '  ' for t in ts[:-1]] + [ts[-1]]
        out.append('')
        i += 1
    return out


def dump_json(path, expl_path=None, ctable_path=None):
    """Node(docx) 빌더용: key -> [{kind, box, lines:[str], (table 이면) caption, rows}],
    (선택) key -> 해설 줄 리스트, (선택) key -> code 칸에 든 표 rows"""
    data, edata, cdata = {}, {}, {}
    for key, q in load_all():
        bl = format_prompt(q['prompt'], key)
        ent = []
        for b in bl:
            e = {"kind": b['kind'], "box": bool(b.get('box')), "lines": [l['t'] for l in b['lines']]}
            if b['kind'] == 'table':
                assert verify_table(b), f"표 불일치: {key}"
                e["caption"] = b.get('caption')
                e["rows"] = b['rows']
                e["header"] = b.get('header', True)
            elif b['kind'] == 'image':
                e["file"] = b['file']
                e["alt"] = b.get('alt', '')
                e["caption"] = b.get('caption')
                e["w"] = b.get('w')
                e["h"] = b.get('h')
            ent.append(e)
        data[key] = ent
        ct = code_table(q.get('code'))
        if ct:
            cdata[key] = ct
        el = format_explanation(q.get('explanation'), key)
        assert verify_explanation(q.get('explanation'), el), f"해설 불일치: {key}"
        edata[key] = [l['t'] for l in el]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    if expl_path:
        with open(expl_path, 'w', encoding='utf-8') as f:
            json.dump(edata, f, ensure_ascii=False, indent=1)
    if ctable_path:
        with open(ctable_path, 'w', encoding='utf-8') as f:
            json.dump(cdata, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    import sys
    bad = 0
    n = 0
    for key, q in load_all():
        n += 1
        bl = format_prompt(q['prompt'], key)
        if not verify(q['prompt'], bl):
            bad += 1
            print('MISMATCH', key)
    print(f'checked {n} prompts, mismatch: {bad}')
    ebad = 0
    for key, q in load_all():
        if not verify_explanation(q.get('explanation'), format_explanation(q.get('explanation'), key)):
            ebad += 1
            print('EXPL MISMATCH', key)
    print(f'checked {n} explanations, mismatch: {ebad}')
    tbl_keys, tbad = [], 0
    for key, q in load_all():
        for b in format_prompt(q['prompt'], key):
            if b['kind'] == 'table':
                tbl_keys.append(key)
                if not verify_table(b):
                    tbad += 1
                    print('TABLE MISMATCH', key)
    ctbl_keys = [key for key, q in load_all() if code_table(q.get('code'))]
    print(f'tables in prompt: {len(tbl_keys)} blocks in {len(set(tbl_keys))} questions {sorted(set(tbl_keys))}, mismatch: {tbad}')
    print(f'tables in code field: {ctbl_keys}')
    if '--dump' in sys.argv:
        out = sys.argv[sys.argv.index('--dump') + 1]
        eout = sys.argv[sys.argv.index('--dump-expl') + 1] if '--dump-expl' in sys.argv else None
        cout = sys.argv[sys.argv.index('--dump-ctable') + 1] if '--dump-ctable' in sys.argv else None
        dump_json(out, eout, cout)
        print('dumped ->', out, eout or '', cout or '')
