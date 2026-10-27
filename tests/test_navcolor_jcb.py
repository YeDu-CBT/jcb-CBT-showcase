# -*- coding: utf-8 -*-
"""정보처리기사 CBT: 학습 모드에서 정답 확인 후 문제 이동 버튼 색(초록/빨강/주황) 테스트."""
import os
import sys, json, time
from playwright.sync_api import sync_playwright

TARGET = sys.argv[1]
SHOT = sys.argv[2]
DATA = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jcb_cbt', 'site', 'data.json'), encoding='utf-8'))['questions']
BYKEY = {}
for q in DATA:
    for a in (q.get('appearances') or [{'year': q['year'], 'round': q['round'], 'number': q['display_number']}]):
        BYKEY[(str(a['year']), str(a['round']), str(a['number']))] = q
PASS, FAIL = [], []

def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + str(extra)) if extra != '' else ''))

GREEN, RED, ORANGE = 'rgb(30, 142, 62)', 'rgb(211, 47, 47)', 'rgb(240, 169, 46)'

def classes(page):
    return page.eval_on_selector_all('#exam-qgrid button', "els => els.map(e => e.className)")

def kind(cls):
    if 'result-correct' in cls: return 'C'
    if 'result-wrong' in cls: return 'W'
    if 'result-pending' in cls: return 'P'
    if 'answered' in cls: return 'a'
    return '-'

def cur_q(page):
    chip = page.locator('#exam-main .q-head-left .chip').first.inner_text()
    import re
    m = re.match(r'(\d+)년 (\d+)회 · #(\d+)', chip)
    return BYKEY[(m.group(1), m.group(2), m.group(3))]

def fields(page):
    return page.locator('#exam-main .answer-wrap .answer-input')

def fill_all(page, values):
    f = fields(page)
    for i, v in enumerate(values):
        f.nth(i).fill(v)

def correct_values(q):
    if q.get('answer_parts'):
        return [p['value'] for p in q['answer_parts']]
    return [q['answer']]

with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = br.new_context(viewport={'width': 1200, 'height': 900})
    page = ctx.new_page()
    errors, failed = [], []
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
    page.on('requestfailed', lambda r: failed.append(r.url))
    page.goto(TARGET)
    page.wait_for_selector('#screen-home .round-chip')

    # ---- 학습 모드 세션: 연도·회차 순서, 12문항
    page.locator('#screen-home .seg button', has_text='학습 모드').click()
    page.locator('#screen-home .seg button', has_text='연도·회차 순서').click()
    page.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = 12; r.dispatchEvent(new Event('input')); }""")
    page.click('#screen-home .start-bar .btn-primary')
    page.wait_for_selector('#exam-main .q-card')
    k0 = [kind(c) for c in classes(page)]
    check('시작 직후 채점 색 없음', set(k0) == {'-'}, k0)
    legend = page.inner_text('.navlegend')
    check('학습 모드 범례에 정답/오답·미답/채점 대기 포함', all(t in legend for t in ['정답', '오답·미답', '채점 대기']), legend)

    expected = {}
    def nxt():
        page.click('#exam-main >> text=다음 →')

    # 0: 서술형 — 입력 후 정답 보기 → 주황 → ✓ → 초록
    q = cur_q(page); check('0번은 서술형(self)', q['grading'] == 'self', q['grading'])
    fill_all(page, ['내 생각 나름'])
    page.click('#exam-main >> text=정답 보기')
    c = classes(page)[0]
    check('서술형: 정답 보기 직후 주황(result-pending)+current 동시', 'result-pending' in c and 'current' in c, c)
    bg = page.eval_on_selector('#exam-qgrid button:nth-child(1)', "e => getComputedStyle(e).backgroundColor")
    page.click('#exam-main .sg-correct')
    c = classes(page)[0]
    check('서술형: ✓ 맞았음 → 초록', 'result-correct' in c and 'result-pending' not in c, c)
    page.click('#exam-main .sg-wrong')
    c = classes(page)[0]
    check('서술형: ✗ 틀렸음으로 바꾸면 빨강', 'result-wrong' in c and 'result-correct' not in c, c)
    page.click('#exam-main .sg-correct')   # 최종 초록으로
    expected[0] = 'C'
    nxt()

    # 1: 서술형 — 빈칸으로 정답 보기 → 빨강(미답)
    q = cur_q(page); check('1번은 서술형(self)', q['grading'] == 'self')
    page.click('#exam-main >> text=정답 보기')
    c = classes(page)[1]
    check('서술형 미입력+채점 전: 빨강(미답)', 'result-wrong' in c and 'current' in c, c)
    expected[1] = 'W'
    nxt()

    # 2: exact 단일 — 정답 입력 → 초록
    q = cur_q(page); check('2번은 exact', q['grading'] == 'exact')
    fill_all(page, correct_values(q))
    c = classes(page)[2]
    check('입력만 하고 확인 전엔 answered(파랑)+current, 색 없음', 'answered' not in c and 'result' not in c and 'current' in c, c)
    page.click('#exam-main >> text=정답 확인')
    c = classes(page)[2]
    check('exact 정답 → result-correct+current 동시', 'result-correct' in c and 'current' in c, c)
    expected[2] = 'C'
    nxt()

    # 3: exact — 오답 → 빨강
    q = cur_q(page); fill_all(page, ['zzz오답'])
    page.click('#exam-main >> text=정답 확인')
    check('exact 오답 → 빨강', 'result-wrong' in classes(page)[3], classes(page)[3])
    expected[3] = 'W'
    nxt()

    # 4: exact — 미응답 → 빨강
    q = cur_q(page)
    page.click('#exam-main >> text=정답 확인')
    check('exact 미응답 → 빨강', 'result-wrong' in classes(page)[4], classes(page)[4])
    expected[4] = 'W'
    nxt()

    # 5: 번호별 칸(answer_parts) — 모두 정답 → 초록
    q = cur_q(page)
    check('5번(idx)은 answer_parts 문항', bool(q.get('answer_parts')) and q['grading'] == 'exact')
    fill_all(page, correct_values(q)); page.click('#exam-main >> text=정답 확인')
    check('answer_parts 전부 정답 → 초록', 'result-correct' in classes(page)[5], classes(page)[5])
    expected[5] = 'C'
    nxt()

    # 6: 입력만 하고 확인 안 함 → answered
    q = cur_q(page); fill_all(page, ['아무거나'])
    expected[6] = 'a'
    nxt()

    # 7: 방문만 하고 아무것도 안 함 → 기본
    expected[7] = '-'
    nxt()

    # 8: 정답을 입력했지만 확인 안 눌렀음 → answered
    q = cur_q(page); fill_all(page, correct_values(q))
    expected[8] = 'a'
    nxt()

    # 9: 오답 확인 → 빨강 (마지막으로 다음 문항으로 이동)
    q = cur_q(page); fill_all(page, ['틀림'])
    page.click('#exam-main >> text=%s' % ('정답 확인' if q['grading'] == 'exact' else '정답 보기'))
    expected[9] = 'W' if q['grading'] == 'exact' else 'W'   # self 이고 채점 전이면 입력이 있으므로 pending
    if q['grading'] == 'self': expected[9] = 'P'
    nxt()

    # 이동 후 최종 상태 비교 (현재 문항 10번은 아직 안 건드림)
    ks = [kind(c) for c in classes(page)]
    for i, e in expected.items():
        check('문항 %d 최종 색: 기대 %s' % (i + 1, e), ks[i] == e, ks[i])
    check('현재(10번) 버튼은 current 클래스', 'current' in classes(page)[10])
    check('현재 문항이 아닌 버튼에는 current 없음', sum('current' in c for c in classes(page)) == 1)

    # 계산된 색
    def bgcolor(i): return page.eval_on_selector('#exam-qgrid button:nth-child(%d)' % (i + 1), "e => getComputedStyle(e).backgroundImage + ' | ' + getComputedStyle(e).backgroundColor + ' | ' + getComputedStyle(e).color")
    print('  바탕/글자색 샘플 0(초록):', bgcolor(0)); print('  1(빨강):', bgcolor(1)); print('  9:', bgcolor(9))

    # 버튼 눌러 이동 -> 이동한 곳이 채점된 문항이면 색 유지 + current 추가
    page.click('#exam-qgrid button:nth-child(3)')  # 3번(index 2, 정답)
    c = classes(page)[2]
    check('채점된 문항으로 돌아오면 초록 유지 + current', 'result-correct' in c and 'current' in c, c)
    ring = page.eval_on_selector('#exam-qgrid button:nth-child(3)', "e => getComputedStyle(e).boxShadow")
    check('현재+채점 버튼에 겹 테두리(box-shadow) 표시', 'rgb(10, 59, 147)' in ring, ring)
    # 학습 모드 결과 상태에서 문항 화면 정답 표시도 유지
    check('해당 문항은 정답 확인 화면(잠금)', page.locator('#exam-main .explain-box').count() == 1)
    page.screenshot(path=SHOT + '_study_desktop.png')
    page.locator('.navpanel').screenshot(path=SHOT + '_study_navpanel.png')

    # 접근성 이름
    lab = page.eval_on_selector('#exam-qgrid button:nth-child(3)', "e => e.getAttribute('aria-label')")
    check('aria-label에 채점 결과 포함', '정답' in lab, lab)

    # 플래그와 겹쳐도 유지
    page.click('#exam-main .flag-btn')
    c = classes(page)[2]
    check('검토표시 + 채점 색 + current 동시 유지', 'flagged' in c and 'result-correct' in c and 'current' in c, c)
    page.screenshot(path=SHOT + '_flag.png')
    page.locator('.navpanel').screenshot(path=SHOT + '_flag_navpanel.png')

    # ---- 실전 모드: 색 변화 없음, 정답 확인 버튼 없음
    page.click('.exit-btn'); page.click('#modal-root >> text=저장 없이 종료')
    page.wait_for_selector('#screen-home .round-chip')
    page.locator('#screen-home .seg button', has_text='실전 모드').click()
    page.locator('#screen-home .seg button', has_text='연도·회차 순서').click()
    page.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = 5; r.dispatchEvent(new Event('input')); }""")
    page.click('#screen-home .start-bar .btn-primary')
    page.wait_for_selector('#exam-main .q-card')
    check('실전 모드: 정답 확인/정답 보기 버튼 없음', page.locator('#exam-main .check-row .btn').count() == 0)
    q = cur_q(page); fill_all(page, correct_values(q))
    nxt(); q = cur_q(page); fill_all(page, ['틀림'])
    ks = [kind(c) for c in classes(page)]
    check('실전 모드: 답을 입력해도 초록/빨강/주황 없음(지난 문항은 answered, 현재 문항은 current)', ks[0] == 'a' and not any(k in 'CWP' for k in ks), ks)
    check('실전 모드 범례에는 정답/오답 항목 없음', '오답·미답' not in page.inner_text('.navlegend'), page.inner_text('.navlegend'))
    br.close()

    # ---- 모바일 390px
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    m = br.new_context(viewport={'width': 390, 'height': 844})
    mp = m.new_page()
    mp.on('console', lambda mm: errors.append(mm.text) if mm.type == 'error' else None)
    mp.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
    mp.goto(TARGET)
    mp.wait_for_selector('#screen-home .round-chip')
    mp.locator('#screen-home .seg button', has_text='학습 모드').click()
    mp.locator('#screen-home .seg button', has_text='연도·회차 순서').click()
    mp.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = 12; r.dispatchEvent(new Event('input')); }""")
    mp.click('#screen-home .start-bar .btn-primary')
    mp.wait_for_selector('#exam-main .q-card')
    # 3번(exact) 정답, 4번 오답
    mp.click('#exam-main >> text=정답 보기')
    mp.click('#exam-main >> text=다음 →'); mp.click('#exam-main >> text=정답 보기')
    mp.click('#exam-main >> text=다음 →')
    q = cur_q(mp); mp.locator('#exam-main .answer-wrap .answer-input').nth(0).fill(correct_values(q)[0]); mp.click('#exam-main >> text=정답 확인')
    mp.click('#exam-main >> text=다음 →'); mp.click('#exam-main >> text=정답 확인')
    sw = mp.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    check('모바일 390px 가로 스크롤 없음', sw[0] <= sw[1], sw)
    mp.locator('.navpanel').scroll_into_view_if_needed()
    mp.locator('.navpanel').screenshot(path=SHOT + '_mobile_navpanel.png')
    mp.screenshot(path=SHOT + '_mobile_full.png')
    br.close()

    real_err = [e for e in errors if 'ERR_TUNNEL_CONNECTION_FAILED' not in e and '404 (File not found)' not in e]
    real_fail = [u for u in failed if 'cdnjs.cloudflare.com' not in u]
    print('  (제외한 환경 요인: 콘솔 %d건, CDN 요청 %d건)' % (len(errors) - len(real_err), len(failed) - len(real_fail)))
    check('콘솔 에러 0 (환경 요인 제외)', len(real_err) == 0, real_err[:3])
    check('요청 실패 0 (CDN 제외)', len(real_fail) == 0, real_fail[:3])

print('\n== %d pass / %d fail ==' % (len(PASS), len(FAIL)))
if FAIL:
    print('FAILED:', FAIL); sys.exit(1)
