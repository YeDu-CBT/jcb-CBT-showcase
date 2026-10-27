# -*- coding: utf-8 -*-
"""정처기 CBT (Ver 2.1): 같은 문제 합치기(404문항 + 출제 회차 표시) + 문항 이동판 메모 표시 테스트.
usage: test_dups.py URL TAG
  URL = http://localhost:9881/index.html | http://localhost:9881/standalone.html | file:///.../jcb_cbt.html
서버(mockdb_server.py)는 9881 에서 떠 있어야 한다(동기화 시험은 http 에서만).
"""
import os
import sys, json, time, re, urllib.request, urllib.parse
from playwright.sync_api import sync_playwright

URL, TAG = sys.argv[1], sys.argv[2]
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_out')   # 스크린샷 등 시험 산출물
os.makedirs(SP, exist_ok=True)
IS_FILE = URL.startswith('file:')
DB = 'http://localhost:9881/__db/'
PASS, FAIL = [], []
errors = []
D = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jcb_cbt', 'site', 'data.json'), encoding='utf-8'))
QS = {q['id']: q for q in D['questions']}
MERGED = [q for q in D['questions'] if q.get('appearances')]


def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + str(extra)[:400]) if extra != '' else ''))


def wait_until(fn, timeout=6.0, step=0.15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = fn()
            if v:
                return v
        except Exception:
            pass
        time.sleep(step)
    return False


def dump():
    return json.load(urllib.request.urlopen(DB + 'dump'))


def reset():
    urllib.request.urlopen(urllib.request.Request(DB + 'reset', method='POST', data=b'{}'))


def put_doc(path, data):
    urllib.request.urlopen(urllib.request.Request(DB + 'doc?path=' + urllib.parse.quote(path, safe=''), method='PUT',
                                                  data=json.dumps(data).encode('utf-8'), headers={'content-type': 'application/json'}))


def ls(page, key):
    return page.evaluate("(k) => localStorage.getItem(k)", key)


def ls_json(page, key, default=None):
    v = ls(page, key)
    return json.loads(v) if v else default


def new_page(browser, seed=None, mock=False, uid='u_dups', viewport=None):
    ctx = browser.new_context(viewport=viewport or {'width': 1280, 'height': 1000})
    if mock:
        ctx.add_init_script("window.__MOCK_CFG = %s;" % json.dumps({'uid': uid}))
        ctx.add_init_script(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_claude.js'))
    if seed:
        js = "try{ if(!localStorage.getItem('__seeded')){ " + ';'.join(
            "localStorage.setItem(%s, %s)" % (json.dumps(k), json.dumps(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))
            for k, v in seed.items()) + "; localStorage.setItem('__seeded','1'); } }catch(e){}"
        ctx.add_init_script(js)
    page = ctx.new_page()
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append('PAGEERROR: ' + str(e)))
    page.goto(URL)
    page.wait_for_selector('#screen-home:not([hidden]) .start-bar')
    return ctx, page


def set_seg(page, label):
    page.locator('#screen-home .seg button', has_text=label).click()


def pick_rounds(page, rounds):
    for r in rounds:
        page.locator('button.round-chip[aria-label="%s"]' % r).click()


def start(page, rounds=(), mode='학습 모드', ordered=True, limit='없음'):
    pick_rounds(page, rounds)
    if ordered:
        set_seg(page, '연도·회차 순서')
    set_seg(page, mode)
    set_seg(page, limit)
    page.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = r.max; r.dispatchEvent(new Event('input')); }""")
    page.locator('#screen-home .start-bar .btn-primary').click()
    page.wait_for_selector('#screen-exam:not([hidden]) .q-card')


def goto_q(page, n):
    page.locator('#exam-qgrid button', has_text=re.compile(r'^%d$' % n)).click()
    page.wait_for_selector('.q-num:text-is("Q%d")' % n)


def exit_exam(page):
    page.locator('.exam-top .exit-btn').click()
    page.locator('#active-modal').get_by_role('button', name='저장 없이 종료', exact=True).click()
    page.wait_for_selector('#screen-home:not([hidden]) .start-bar')


def chips(page):
    return [c.inner_text() for c in page.locator('#exam-main .q-head-left .app-chip').all()]


def filter_count(page):
    return page.locator('.filter-count b').inner_text()


def status_of(page, n):
    cls = page.locator('#exam-qgrid button.nav-%d' % (n - 1)).get_attribute('class')
    return 'correct' if 'result-correct' in cls else ('wrong' if 'result-wrong' in cls else ('pending' if 'result-pending' in cls else 'none'))


def solve_one(browser, rounds, qn, answers, expect):
    """한 라운드를 학습 모드로 열어 qn 번 문항에 답을 넣고 '정답 확인' → 채점 결과가 expect 인지."""
    ctx, p = new_page(browser)
    start(p, rounds=rounds)
    goto_q(p, qn)
    fields = p.locator('#exam-main .answer-wrap .answer-input')
    if len(answers) == 1 and fields.count() == 1:
        fields.first.fill(answers[0])
    else:
        assert fields.count() == len(answers), (fields.count(), answers)
        for i, a in enumerate(answers):
            fields.nth(i).fill(a)
    p.get_by_role('button', name=re.compile('정답 확인|정답 보기')).first.click()
    st = status_of(p, qn)
    ctx.close()
    return st


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')

        # =================================================================
        # 0. 데이터(파이썬에서 직접)
        # =================================================================
        check('data.json: 403문항 / 15개 합친 문항', len(D['questions']) == 403 and len(MERGED) == 15, (len(D['questions']), len(MERGED)))
        al = [a for q in MERGED for a in q['aliases']]
        check('옛 id 17개, 문항으로 남지 않음', len(al) == 17 and not any(a in QS for a in al))
        check('meta: 출제 기록 420 / 합친 17', D['meta']['total_appearances'] == 420 and D['meta']['merged_duplicates'] == 17 and D['meta']['total_questions'] == 403)
        allapp = [a['id'] for q in D['questions'] for a in (q.get('appearances') or [{'id': q['id']}])]
        check('출제 기록 420개가 겹침 없이 원래 id 와 같음', len(allapp) == 420 and len(set(allapp)) == 420)

        # =================================================================
        # 1. 처음 화면
        # =================================================================
        ctx, P = new_page(browser)
        hp = P.locator('.home-header p').inner_text()
        check('처음 화면 설명: 403문항 + 17개 합침', '403문항' in hp and '420문항 중 같은 문제 17개를 합쳐' in hp, hp)
        check('흐르는 글: 403문항', '403문항 전체 수록' in P.locator('.marquee-text').inner_text())
        check('범위 미선택: 403문항', filter_count(P) == '403문항', filter_count(P))
        pick_rounds(P, ['2023년 1회'])
        check('2023년 1회만: 20문항(합친 문항 포함)', filter_count(P) == '20문항', filter_count(P))
        P.locator('#btn-rounds-none').click()
        pick_rounds(P, ['2025년 2회'])
        check('2025년 2회만: 20문항', filter_count(P) == '20문항', filter_count(P))
        pick_rounds(P, ['2020년 3회'])
        check('2020년 3회+2025년 2회: 39문항(공통 1개)', filter_count(P) == '39문항', filter_count(P))
        P.locator('#btn-rounds-all').click()
        check('전체 선택: 403문항', filter_count(P) == '403문항', filter_count(P))
        # 모든 회차가 20문항씩인지(합쳐도 회차별 문항 수 그대로)
        for r in D['rounds_meta']:
            P.locator('#btn-rounds-none').click()
            pick_rounds(P, [r['label']])
            if filter_count(P) != '20문항':
                check('회차별 20문항: ' + r['label'], False, filter_count(P))
        check('21개 회차 모두 20문항', not [f for f in FAIL if f.startswith('회차별 20문항')])
        ctx.close()

        # =================================================================
        # 2. 풀이 화면: 출제 회차 칩 · 순서
        # =================================================================
        ctx, P = new_page(browser)
        start(P, rounds=['2023년 1회'])
        check('Q1 칩 1개', chips(P) == ['2023년 1회 · #1'], chips(P))
        goto_q(P, 15)
        check('Q15 = 2020-2-2 + 2023-1-15 (오래된 순)', chips(P) == ['2020년 2회 · #2', '2023년 1회 · #15'], chips(P))
        goto_q(P, 19)
        c19 = chips(P)
        check('Q19 = 3회 출제 (2020-3-7 · 2023-1-19 · 2025-2-11)', c19 == ['2020년 3회 · #7', '2023년 1회 · #19', '2025년 2회 · #11'], c19)
        t = P.locator('#exam-main .app-chip').first.get_attribute('title')
        check('칩 title: 3개 회차 안내', t and '3개 회차' in t, t)
        t1 = P.locator('#exam-qgrid button').count()
        check('2023년 1회 풀: 문항 20개', t1 == 20, t1)
        # 번호 순서: 각 Q 에 '2023년 1회 · #n' 칩이 n 번째로
        ok = True
        for n in range(1, 21):
            goto_q(P, n)
            if '2023년 1회 · #%d' % n not in chips(P):
                ok = False
                print('   순서 어긋남 Q', n, chips(P))
        check('고른 회차 안의 번호 순서대로 20문항', ok)
        ctx.close()

        # 전체 회차: 404문항을 훑어 출제 기록 420개가 정확히 한 번씩 나오는지
        ctx, P = new_page(browser)
        start(P, rounds=[])
        check('전체 풀이: 진행 표시 1 / 403', P.locator('#exam-progress-text').inner_text().startswith('1 / 403'), P.locator('#exam-progress-text').inner_text())
        res = P.evaluate("""() => {
          const out = [];
          const n = document.querySelectorAll('#exam-qgrid button').length;
          const btns = () => Array.from(document.querySelectorAll('#exam-main .app-chip')).map(c => c.textContent);
          for(let i = 0; i < n; i++){
            document.querySelectorAll('#exam-qgrid button')[i].click();
            out.push(btns());
          }
          return out;
        }""")
        flat = [c for r in res for c in r]
        check('403문항 모두 읽음', len(res) == 403, len(res))
        check('출제 기록 420개(회차·번호) 정확히 한 번씩', len(flat) == 420 and len(set(flat)) == 420, (len(flat), len(set(flat))))

        def key(s):
            m = re.match(r'(\d+)년 (\d+)회 · #(\d+)', s)
            return tuple(int(x) for x in m.groups())
        leads = [key(r[0]) for r in res]
        check('앞 칩(가장 이른 출제)이 오래된 순으로 정렬됨', leads == sorted(leads))
        check('각 문항 안의 칩도 오래된 순', all([key(c) for c in r] == sorted(key(c) for c in r) for r in res))
        i6 = res.index(['2020년 1회 · #6', '2022년 3회 · #12', '2026년 1회 · #9'])
        check('SQL 튜플 수 문항: 2020-1 #6 자리에 3회 출제로 한 번', i6 == 5, i6)
        ctx.close()

        # =================================================================
        # 3. 채점: 합친 판의 정답도 인정
        # =================================================================
        # G2 파이썬 set (2020-2-2 / 2023-1-15)
        s = solve_one(browser, ['2020년 2회'], 2, ["{'중국','한국','베트남','홍콩','태국'}"], 'correct')
        check('G2: 2020 판 표기 정답', s == 'correct', s)
        s = solve_one(browser, ['2020년 2회'], 2, ["{'한국', '중국', '베트남', '홍콩', '태국'}"], 'correct')
        check('G2: 2023 판 표기도 정답', s == 'correct', s)
        s = solve_one(browser, ['2020년 2회'], 2, ["{'한국'}"], 'wrong')
        check('G2: 틀린 값은 오답', s == 'wrong', s)
        # G3 NAT
        s = solve_one(browser, ['2020년 4회'], 8, ['NAT(Network Address Transformation)'], 'correct')
        check('G3: NAT(…) 정답', s == 'correct', s)
        s = solve_one(browser, ['2020년 4회'], 8, ['NAT (Network Address Transformation)'], 'correct')
        check('G3: NAT (…) 띄어쓰기 판도 정답', s == 'correct', s)
        # G7 결합도 (번호별 칸): 2025-1-12
        s = solve_one(browser, ['2025년 1회'], 12, ['ㅁ. 내용 결합도', 'ㄴ. 스탬프 결합도', 'ㄹ. 공통 결합도'], 'correct')
        check('G7: 2025 판 표기 정답', s == 'correct', s)
        s = solve_one(browser, ['2025년 1회'], 12, ['내용결합도', '스탬프결합도', '공통결합도'], 'correct')
        check('G7: 2021 판 표기(용어)도 정답', s == 'correct', s)
        s = solve_one(browser, ['2025년 1회'], 12, ['내용결합도', 'ㄴ. 스탬프 결합도', '공통결합도'], 'correct')
        check('G7: 칸마다 섞어 써도 정답', s == 'correct', s)
        s = solve_one(browser, ['2025년 1회'], 12, ['내용결합도', '자료결합도', '공통결합도'], 'wrong')
        check('G7: 한 칸 틀리면 오답', s == 'wrong', s)
        # G8 SQL 행 수
        s = solve_one(browser, ['2026년 1회'], 9, ['200', '3', '1'], 'correct')
        check('G8: 200 / 3 / 1 정답', s == 'correct', s)
        # G9 DELETE (2023-1-13 / 2020-3-9)
        s = solve_one(browser, ['2023년 1회'], 13, ["DELETE FROM 학생 WHERE 이름 = '민수';"], 'correct')
        check('G9: 2020 판 표기(대문자)도 정답', s == 'correct', s)
        s = solve_one(browser, ['2023년 1회'], 13, ["delete from 학생 where 이름 = '민수';"], 'correct')
        check('G9: 2023 판 표기(소문자) 정답', s == 'correct', s)
        # G13 HAVING (2023-1-16 / 2020-3-8: 줄바꿈 위치만 다름)
        s = solve_one(browser, ['2023년 1회'], 16, ['SELECT 과목이름, MIN(점수) AS 최소점수, MAX(점수) AS 최대점수 FROM 성적\nGROUP BY 과목이름 HAVING AVG(점수) >= 90;'], 'correct')
        check('G13: 2020 판 표기(줄바꿈)도 정답', s == 'correct', s)

        # G1 자가채점 + 칩
        ctx, P = new_page(browser)
        start(P, rounds=['2020년 3회'])
        goto_q(P, 7)
        gc = P.locator('#exam-main .grading-chip').inner_text()
        check('G1: 합친 문항은 자가채점', '자가채점' in gc, gc)
        check('G1: 칩 3개', chips(P) == ['2020년 3회 · #7', '2023년 1회 · #19', '2025년 2회 · #11'], chips(P))
        # 복사 머리글
        P.context.grant_permissions(['clipboard-read', 'clipboard-write']) if not IS_FILE else None
        ctx.close()

        # =================================================================
        # 4. 옛 기록 호환: 메모 · 중간 저장 · 연습 기록
        # =================================================================
        T = int(time.time() * 1000)
        seed = {
            'jcb_cbt_memos_v1': {
                '2023-1-19': {'t': '옛 메모 A', 'ts': T - 5000, 'c': T - 90000},
                '2020-3-7': {'t': '남은 메모 B', 'ts': T - 4000, 'c': T - 4000},
                '2025-3-10': {'t': '옛 메모 C', 'ts': T - 3000, 'c': T - 30000},
                '2020-2-15': {'t': 'chmod 메모', 'ts': T - 2000},
                '2023-3-3': {'t': '앞 chmod 메모 뒤', 'ts': T - 1000},
            },
            'jcb_cbt_saves_v1': [{
                'id': 'sdups1', 'ts': T - 7000, 'sourceLabel': '테스트 저장', 'mode': 'study',
                'ids': ['2020-3-7', '2023-1-19', '2023-1-1'], 'idx': 1,
                'answers': {'2023-1-19': '옛답', '2023-1-1': '다른답'}, 'selfMarks': {}, 'revealed': {}, 'flagged': {'2023-1-19': True},
                'vers': {}, 'ansByVer': {}, 'timeLimitSec': 0, 'remainingSec': 0, 'elapsedSec': 10, 'answered': 2}],
            'jcb_cbt_history_v1': [{
                'ts': T - 9000, 'sourceLabel': '테스트 기록', 'total': 2, 'examCount': 2, 'examCorrect': 0, 'scorePct': 0, 'selfCount': 0, 'mode': 'exam', 'elapsedSec': 30,
                'results': [{'qid': '2025-2-11', 'inputValue': 'x', 'selfMark': None, 'status': 'wrong', 'flagged': False},
                            {'qid': '2023-1-1', 'inputValue': '', 'selfMark': None, 'status': 'unanswered', 'flagged': False}]}],
        }
        ctx, P = new_page(browser, seed=seed)
        memos = ls_json(P, 'jcb_cbt_memos_v1', {})
        check('메모: 옛 id 키가 모두 사라짐', not [k for k in memos if k in ('2023-1-19', '2025-3-10', '2020-2-15')], list(memos))
        mb = memos.get('2020-3-7', {})
        check('메모: 둘 다 있으면 이어 붙임(남은 메모 + 헤더 + 옛 메모)',
              mb.get('t', '').startswith('남은 메모 B') and '── 2023년 1회 #19 때 쓴 메모 ──' in mb.get('t', '') and mb.get('t', '').endswith('옛 메모 A'), mb)
        check('메모: 이어 붙인 뒤 시각 = 새로, 처음 작성 시각 = 더 이른 쪽', mb.get('ts', 0) >= T and mb.get('c') == T - 90000, mb)
        mc = memos.get('2021-3-13', {})
        check('메모: 남은 문항에 메모가 없으면 글·시각 그대로 옮김', mc == {'t': '옛 메모 C', 'ts': T - 3000, 'c': T - 30000}, mc)
        md = memos.get('2023-3-3', {})
        check('메모: 이미 글이 들어 있으면 다시 붙이지 않음', md.get('t') == '앞 chmod 메모 뒤' and md.get('ts') == T - 1000, md)
        toast = P.locator('.toast').first.inner_text() if P.locator('.toast').count() else ''
        check('옮김 안내 토스트(3개)', '메모 3개' in toast, toast)

        # 중간 저장 불러오기
        P.get_by_role('button', name='이어서 풀기').first.click()
        P.wait_for_selector('#screen-exam:not([hidden]) .q-card')
        prog = P.locator('#exam-progress-text').inner_text()
        check('저장본: 목록이 겹치지 않게 줄어듦(2문항), 현재 문항 = 합친 문항', prog.startswith('1 / 2'), prog)
        check('저장본: 옛 id 로 적은 답안이 남은 문항 칸에', P.locator('#exam-main .answer-wrap .answer-input').first.input_value() == '옛답',
              P.locator('#exam-main .answer-wrap .answer-input').first.input_value())
        check('저장본: 검토표시도 남은 문항으로', 'flagged' in P.locator('#exam-qgrid button.nav-0').get_attribute('class'))
        check('저장본: 다른 문항 답안 유지', (lambda: (goto_q(P, 2), P.locator('#exam-main .answer-wrap .answer-input').first.input_value())[1])() == '다른답')
        # 메모 표시: 학습 모드 저장본이므로 이동판에 하늘색 사각형 (2020-3-7 메모 있음)
        check('이동판: 합쳐진 문항(1번)에 메모 표시', 'has-memo' in P.locator('#exam-qgrid button.nav-0').get_attribute('class'))
        exit_exam(P)

        # 연습 기록 보기
        P.locator('.history-row.history-row-clickable').first.click()
        P.wait_for_selector('#screen-result:not([hidden]) .review-card')
        cards = P.locator('.review-card')
        check('기록 보기: 옛 id(2025-2-11) 문항이 합쳐진 문항으로 열림', cards.count() == 2)
        c0 = [c.inner_text() for c in cards.first.locator('.app-chip').all()]
        check('기록 보기: 칩 3개', c0 == ['2020년 3회 · #7', '2023년 1회 · #19', '2025년 2회 · #11'], c0)
        links = cards.first.locator('a.src-link')
        lt = [l.inner_text() for l in links.all()]
        check('기록 보기: 회차마다 원문 링크 3개', lt == ['원문 보기(2020년 3회) ↗', '원문 보기(2023년 1회) ↗', '원문 보기(2025년 2회) ↗'], lt)
        hrefs = [l.get_attribute('href') for l in links.all()]
        rm = {r['label']: r['source_url'] for r in D['rounds_meta']}
        check('기록 보기: 링크 주소 = 각 회차 원문', hrefs == [rm['2020년 3회'], rm['2023년 1회'], rm['2025년 2회']], hrefs)
        one = [l.inner_text() for l in cards.nth(1).locator('a.src-link').all()]
        check('기록 보기: 한 번만 나온 문항은 예전처럼 "원문 보기 ↗"', one == ['원문 보기 ↗'], one)
        ctx.close()

        # =================================================================
        # 5. 결과 화면 오답 분포(처음 출제 회차 기준)
        # =================================================================
        ctx, P = new_page(browser)
        start(P, rounds=['2025년 2회'], mode='실전 모드')
        goto_q(P, 20)
        P.get_by_role('button', name='제출하기', exact=True).click()
        P.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click()
        P.wait_for_selector('#screen-result:not([hidden])')
        rows = [r.inner_text().replace('\t', '|').replace('\n', '|') for r in P.locator('.chapter-summary .cs-table').first.locator('tr').all()]
        txt = ' '.join(rows)
        check('오답 분포: 합친 문항은 처음 출제된 회차(2020년 3회·2022년 2회)에 한 번씩', '2020년 3회' in txt and '2022년 2회' in txt and '2025년 2회' in txt, rows)
        total = sum(int(r.split('|')[1]) for r in rows[1:] if r.split('|')[0].endswith('회'))
        check('오답 분포 합계 = 20 (겹쳐 세지 않음)', total == 20, (total, rows))
        hint = P.locator('.chapter-summary .cs-hint').inner_text()
        check('오답 분포 안내: 처음 출제된 회차에 한 번만 셉니다', '처음 출제된 회차에 한 번만' in hint, hint)
        ctx.close()

        # =================================================================
        # 6. 동기화: 합쳐지기 전 id 로 올라간 서버 메모
        # =================================================================
        if not IS_FILE:
            reset()
            put_doc('data/users/u_dups/memo_2023-1-15', {'qid': '2023-1-15', 't': '서버 옛 메모', 'ts': T - 1000, 'c': T - 1000})
            ctx, P = new_page(browser, mock=True, uid='u_dups')
            ok = wait_until(lambda: P.locator('#sync-bar').get_attribute('data-state') == 'on', 8)
            check('동기화 켜짐', ok)
            m2 = wait_until(lambda: (ls_json(P, 'jcb_cbt_memos_v1', {}).get('2020-2-2') or None), 6)
            check('서버의 옛 id 메모가 남은 문항(2020-2-2) 메모로 들어옴', bool(m2) and m2.get('t') == '서버 옛 메모', m2)
            ok = wait_until(lambda: not [p for p in dump()['docs'] if p.endswith('memo_2023-1-15')] and [p for p in dump()['docs'] if p.endswith('memo_2020-2-2')], 8)
            check('서버: 옛 id 문서는 지워지고 남은 id 문서가 생김', bool(ok), [p.split('/')[-1] for p in dump()['docs']])
            check('로컬 메모에 옛 id 키 없음', '2023-1-15' not in ls_json(P, 'jcb_cbt_memos_v1', {}))
            ctx.close()

        # =================================================================
        # 7. 오류 콘솔
        # =================================================================
        real = [e for e in errors if not re.search(r'cdnjs|highlight|Failed to load resource|net::ERR|ERR_', e)]
        check('콘솔 오류 없음', not real, real[:5])
        browser.close()

    print('\n== %s: PASS %d / FAIL %d ==' % (TAG, len(PASS), len(FAIL)))
    if FAIL:
        print('FAILED:', FAIL)
        sys.exit(1)


if __name__ == '__main__':
    main()
