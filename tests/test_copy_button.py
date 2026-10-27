# -*- coding: utf-8 -*-
"""코드 문제 복사 버튼 테스트. usage: test_copy_button.py URL TAG"""
import os
import sys, re, json, time
from playwright.sync_api import sync_playwright
URL, TAG = sys.argv[1], sys.argv[2]
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_out')   # 스크린샷 등 시험 산출물
os.makedirs(SP, exist_ok=True)
D = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jcb_cbt', 'site', 'data.json'), encoding='utf-8'))
QS = {q['id']: q for q in D['questions']}
PASS, FAIL, errors = [], [], []
def check(n, c, e=''):
    (PASS if c else FAIL).append(n); print(('PASS ' if c else 'FAIL ') + n + ((' :: ' + str(e)[:300]) if e != '' else ''))
def has_code(q): return bool((q.get('code') or '').strip())
def home_ready(pg): pg.wait_for_selector('#screen-home:not([hidden]) .start-bar')
def prep_round(pg, year, rnd, mode='실전 모드'):
    pg.locator('button.round-chip[aria-label="%d년 %d회"]' % (year, rnd)).click()
    pg.locator('#screen-home .seg button', has_text='연도·회차 순서').click()
    pg.locator('#screen-home .seg button', has_text=mode).click()
    pg.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = r.max; r.dispatchEvent(new Event('input')); }""")
def start(pg):
    pg.locator('#screen-home .start-bar .btn-primary').click(); pg.wait_for_selector('#screen-exam:not([hidden]) .q-card')
def apps_of(q): return q.get('appearances') or [{'id': q['id'], 'year': q['year'], 'round': q['round'], 'number': q['display_number']}]
def round_members(year, rnd):
    out = []
    for x in D['questions']:
        for a in apps_of(x):
            if a['year'] == year and a['round'] == rnd: out.append((int(a['number']), x))
    return [x for _, x in sorted(out, key=lambda t: t[0])]
def order_index(qid):
    q = QS[qid]
    a0 = apps_of(q)[0]
    return [x['id'] for x in round_members(a0['year'], a0['round'])].index(qid) + 1
def goto_id(pg, qid):
    n = order_index(qid)
    pg.locator('#exam-qgrid button', has_text=re.compile(r'^%d$' % n)).click()
    pg.wait_for_selector('.q-num:text-is("Q%d")' % n)
    chip = pg.locator('.q-head-left .chip').first.inner_text()
    assert '#%s' % apps_of(QS[qid])[0]['number'] in chip, (chip, qid)
def clip(pg): return pg.evaluate("() => navigator.clipboard.readText()")
def btn(pg, name): return pg.locator('#exam-main .code-tools .copy-btn', has_text=name)
def active(pg): return pg.evaluate("() => { const e = document.activeElement; return e ? {tag:e.tagName, cls:e.className} : null; }")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = b.new_context(viewport={'width': 1280, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
    pg = ctx.new_page()
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
    pg.goto(URL); home_ready(pg)
    check('버전 칩 Ver 2.5 · 수정 21회', pg.locator('.app-header-ver').inner_text() == 'Ver 2.5 · 수정 21회')

    # ---- 코드 문항 / 비코드 문항에서의 도구줄 유무 (2023-1회) ----
    prep_round(pg, 2023, 1); start(pg)
    r = round_members(2023, 1)
    no_code = [q for q in r if not has_code(q)][0]
    goto_id(pg, no_code['id'])
    check('코드 없는 문항(#%s)에는 복사 도구줄 없음' % no_code['display_number'], pg.locator('#exam-main .code-tools').count() == 0)
    q14 = QS['2023-1-14']
    goto_id(pg, '2023-1-14')
    check('코드 문항(#14)에는 도구줄(버튼 2개)', pg.locator('#exam-main .code-tools .copy-btn').count() == 2,
          [x.inner_text() for x in pg.locator('#exam-main .code-tools .copy-btn').all()])

    # ---- 14번: 답 입력 후 '문제 전체 복사' (실전 모드: 정답 비포함) ----
    pg.keyboard.type('idx2'); pg.keyboard.press('Enter'); pg.keyboard.type('nx')
    btn(pg, '문제 전체 복사').click()
    pg.wait_for_selector('.toast.show')
    t = clip(pg)
    check('전체 복사: 머리줄', t.startswith('[정보처리기사 실기 복원문제 · 2023년 1회 #14 · C]'), t[:60])
    check('전체 복사: ■ 문제 + 지문', '■ 문제\n다음은 버블 정렬을 이용하여 배열에 저장된 수를 오름차순으로 정렬하는 프로그램이다.' in t)
    check('전체 복사: ■ 코드 + ```c 펜스', '■ 코드\n```c\n#include <stdio.h>' in t and t.count('```') == 2)
    check('전체 복사: 코드 본문 일치', q14['code'].rstrip() in t)
    check('전체 복사: ■ 내 답안 ① idx2 / ② nx', '■ 내 답안\n① idx2\n② nx' in t, t[t.find('■ 내 답안'):][:60])
    check('실전 모드 풀이 중에는 정답·해설 미포함', '■ 정답' not in t and '■ 해설' not in t and '모범답안' not in t)
    check('전체 복사: 출처 줄', '(출처: ' in t and q14['source_url'] in t)
    lab = btn(pg, '복사됨').count()
    check('버튼이 잠시 "✓ 복사됨"으로 바뀜', lab == 1)
    toast = pg.locator('.toast').inner_text()
    check('복사 토스트', '복사했습니다' in toast and '문제 전체' in toast, toast)
    a = active(pg)
    check('복사 후에도 입력칸에 포커스 유지(타자 계속 가능)', a['tag'] == 'INPUT' and 'answer-input' in a['cls'], a)
    pg.keyboard.press('Control+A'); pg.keyboard.type('NX')
    check('복사 후에도 쓰던 ② 칸에 커서 유지', pg.evaluate("() => document.activeElement.getAttribute('aria-label')") == '② 답안')
    check('복사 직후 이어서 타자 → ② 칸에 반영', pg.evaluate("() => [...document.querySelectorAll('#exam-main .answer-parts .answer-input')].map(e => e.value)") == ['idx2', 'NX'])
    time.sleep(1.8)
    check('버튼 문구가 원래대로 돌아옴', btn(pg, '문제 전체 복사').count() == 1 and btn(pg, '복사됨').count() == 0)

    lab2 = lambda: pg.evaluate("() => document.activeElement.getAttribute('aria-label')")
    pg.locator('#btn-save').click(); pg.wait_for_selector('.toast.show')
    check('저장 버튼 뒤에도 쓰던 ② 칸에 커서 유지', lab2() == '② 답안', lab2())
    pg.locator('.exit-btn').click(); pg.wait_for_selector('#active-modal')
    pg.locator('#active-modal').get_by_role('button', name='계속 풀기').click()
    check('확인창 "계속 풀기" 뒤에도 ② 칸에 커서 유지', lab2() == '② 답안', lab2())

    # ---- 코드만 복사 ----
    btn(pg, '코드만 복사').click(); time.sleep(0.3)
    t2 = clip(pg)
    check('코드만 복사: 코드 원문과 정확히 일치(앞뒤 설명·펜스 없음)', t2 == q14['code'].rstrip(), repr(t2[:50]))

    # ---- 답을 안 썼을 때: 내 답안 구역 없음 ----
    for i in range(2):
        pg.locator('#exam-main .answer-parts .answer-input').nth(i).fill('')
    btn(pg, '문제 전체 복사').click(); time.sleep(0.3)
    t3 = clip(pg)
    check('미작성이면 ■ 내 답안 구역 생략', '■ 내 답안' not in t3 and '■ 코드' in t3)

    # ---- 자바/파이썬/SQL/펜스 언어 ----
    for qid, fence in [('2023-1-1', '```java'), ('2023-1-9', None)]:
        goto_id(pg, qid)
        btn(pg, '문제 전체 복사').click(); time.sleep(0.25)
        tt = clip(pg)
        want = '```' + QS[qid].get('lang_hint', '') + '\n'
        check('%s 코드 펜스 언어(%s)' % (qid, QS[qid].get('lang_hint', '') or '없음'), want in tt, tt[tt.find('■ 코드'):][:30])

    # ---- 학습 모드: 정답 공개 전/후 ----
    pg.locator('.exit-btn').click(); pg.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click(); home_ready(pg)
    pg.locator('#screen-home .seg button', has_text='학습 모드').click(); start(pg)
    goto_id(pg, '2023-1-14')
    pg.keyboard.type('idx2'); pg.keyboard.press('Enter'); pg.keyboard.type('nx')
    btn(pg, '문제 전체 복사').click(); time.sleep(0.3)
    check('학습 모드·공개 전: 정답 미포함', '■ 정답' not in clip(pg))
    pg.get_by_role('button', name=re.compile('정답 (확인|보기)')).first.click()
    btn(pg, '문제 전체 복사').click(); time.sleep(0.3)
    t4 = clip(pg)
    check('학습 모드·공개 후: 채점 결과 + 정답 포함', '■ 내 답안 (채점: 정답)' in t4 and '■ 정답\n① idx2\n② nx' in t4, t4[t4.find('■ 내 답안'):][:80])

    # ---- 표·그림·보기 문항 ----
    pg.locator('.exit-btn').click(); pg.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click(); home_ready(pg)
    pg.locator('button.round-chip[aria-label="2023년 1회"]').click()             # 선택 해제
    prep_round(pg, 2022, 1, '실전 모드'); start(pg)
    tab_id = '2022-1-4'
    q = QS[tab_id]
    tb = [x for x in q['prompt_blocks'] if x['kind'] == 'table'][0]
    goto_id(pg, tab_id)
    btn(pg, '문제 전체 복사').click(); time.sleep(0.3)
    tt = clip(pg)
    first_row = '| ' + ' | '.join(str(c).replace('|', '\\|') for c in tb['rows'][0]) + ' |'
    check('표 문항: 마크다운 표 머리 행', first_row in tt, first_row)
    check('표 문항: 구분선 행(| --- |)', re.search(r'\n\| --- (\| --- )*\|\n', tt) is not None)
    check('표 문항: 모든 행이 들어 있음', all(('| ' + ' | '.join(str(c).replace('|', '\\|') for c in row) + ' |') in tt for row in tb['rows']))
    img_q = QS['2025-1-15']
    pg.locator('.exit-btn').click(); pg.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click(); home_ready(pg)
    pg.locator('button.round-chip[aria-label="2022년 1회"]').click()
    prep_round(pg, 2025, 1); start(pg)
    goto_id(pg, '2025-1-15')
    btn(pg, '문제 전체 복사').click(); time.sleep(0.3)
    tt = clip(pg)
    check('그림 문항: [그림: …] 자리 표시와 안내', '[그림: ' in tt and '글로 복사되지 않습니다' in tt, tt[tt.find('[그림'):][:80])

    # ---- 결과 화면 복습 카드 ----
    pg.locator('.exit-btn').click(); pg.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click(); home_ready(pg)
    pg.locator('button.round-chip[aria-label="2025년 1회"]').click()
    prep_round(pg, 2023, 1); start(pg)
    goto_id(pg, '2023-1-14')
    pg.keyboard.type('wrong'); pg.keyboard.press('Enter'); pg.keyboard.type('nx')
    pg.locator('.exam-top-right .btn-sm', has_text='제출').click()
    pg.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click(); pg.wait_for_selector('#screen-result:not([hidden])')
    cards = pg.locator('.review-card')
    n_code = sum(1 for q in r if has_code(q))
    check('복습 카드의 도구줄 수 = 코드 문항 수(%d)' % n_code, pg.locator('.review-card .code-tools').count() == n_code, pg.locator('.review-card .code-tools').count())
    card14 = pg.locator('.review-card', has=pg.locator('.chip', has_text='#14'))
    card14.locator('.copy-btn', has_text='문제 전체 복사').click(); time.sleep(0.3)
    t5 = clip(pg)
    check('결과 화면 복사: 채점 결과(오답) + 내 답안 + 정답 포함',
          '■ 내 답안 (채점: 오답)\n① wrong\n② nx' in t5 and '■ 정답\n① idx2\n② nx' in t5, t5[t5.find('■ 내 답안'):][:120])
    cardx = pg.locator('.review-card', has=pg.locator('.chip', has_text=re.compile(r'#1$')))
    cardx.locator('.copy-btn', has_text='문제 전체 복사').click(); time.sleep(0.3)
    t6 = clip(pg)
    check('미답변 문항 복사: 내 답안 (미답변) + 정답', '■ 내 답안: (미답변)' in t6 and '■ 정답' in t6, t6[t6.find('■ 내 답안'):][:60])
    pg.screenshot(path=f'{SP}/copy_{TAG}_result.png')

    # ---- 클립보드가 막힌 환경 ----
    pg.get_by_role('button', name='처음으로', exact=True).click(); home_ready(pg)
    pg.locator('#screen-home .start-bar .btn-primary').click(); pg.wait_for_selector('#screen-exam:not([hidden]) .q-card')
    goto_id(pg, '2023-1-14')
    pg.evaluate("""() => {
        Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new Error('denied')) }, configurable: true });
        document.execCommand = () => false;
    }""")
    pg.keyboard.type('a')
    btn(pg, '문제 전체 복사').click()
    pg.wait_for_selector('#active-modal .copy-textarea')
    sel = pg.evaluate("() => { const t = document.querySelector('#active-modal .copy-textarea'); return {v: t.value, s: t.selectionStart, e: t.selectionEnd, focused: document.activeElement === t}; }")
    check('복사 불가 환경: 안내 창에 글이 들어 있음', sel['v'].startswith('[정보처리기사 실기 복원문제') and '■ 코드' in sel['v'])
    check('복사 불가 환경: 글 전체가 선택되고 포커스됨(Ctrl+C 한 번)', sel['s'] == 0 and sel['e'] == len(sel['v']) and sel['focused'], (sel['s'], sel['e'], len(sel['v']), sel['focused']))
    pg.screenshot(path=f'{SP}/copy_{TAG}_fallback.png')
    pg.locator('#active-modal').get_by_role('button', name='닫기').click()
    a = active(pg)
    check('안내 창을 닫으면 모달 제거', pg.locator('#active-modal').count() == 0)

    real = [e for e in errors if not re.search(r'ERR_|Failed to load resource|cdnjs|net::|blocked|denied', e)]
    check('콘솔/페이지 오류 없음', not real, real[:3])

    # ---- 데스크톱 스크린샷 ----
    ctx2 = b.new_context(viewport={'width': 1280, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
    p2 = ctx2.new_page(); p2.goto(URL); home_ready(p2)
    prep_round(p2, 2023, 1); start(p2); goto_id(p2, '2023-1-14')
    p2.screenshot(path=f'{SP}/copy_{TAG}_desktop_q14.png')

    # ---- 모바일 390px ----
    mctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, permissions=['clipboard-read', 'clipboard-write'])
    m = mctx.new_page(); m.goto(URL); home_ready(m)
    prep_round(m, 2023, 1); start(m); goto_id(m, '2023-1-14')
    sw = m.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    check('모바일: 가로 스크롤 없음', sw[0] <= sw[1], sw)
    bb = m.evaluate("() => [...document.querySelectorAll('#exam-main .code-tools .copy-btn')].map(e => { const r = e.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })")
    check('모바일: 복사 버튼 2개가 화면 안', len(bb) == 2 and all(x[0] >= 0 and x[1] <= 390 for x in bb), bb)
    m.screenshot(path=f'{SP}/copy_{TAG}_mobile_q14.png', full_page=False)
    b.close()
print('\n== %s: PASS %d / FAIL %d ==' % (TAG, len(PASS), len(FAIL)))
if FAIL: print('FAILED:', FAIL); sys.exit(1)
