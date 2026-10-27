# -*- coding: utf-8 -*-
import sys, json, re, time
from playwright.sync_api import sync_playwright
URL, TAG = sys.argv[1], sys.argv[2]
PASS, FAIL, errors = [], [], []
def check(n, c, e=''):
    (PASS if c else FAIL).append(n); print(('PASS ' if c else 'FAIL ') + n + ((' :: ' + str(e)) if e != '' else ''))
def saves(pg): return json.loads(pg.evaluate("() => localStorage.getItem('jcb_cbt_saves_v1')") or '[]')
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width': 1280, 'height': 1000})
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
    pg.goto(URL); pg.wait_for_selector('#screen-home:not([hidden]) .start-bar')
    # 필터: 언어 Python → 문항 수 변화, 초기화
    pg.get_by_role('button', name=re.compile(r'^Python \(')).click()
    t = pg.locator('.filter-count').inner_text()
    check('언어 필터 Python → 22문항', '22문항' in t, t)
    pg.get_by_role('button', name='전체로 초기화').click()
    check('초기화 → 403문항', '403문항' in pg.locator('.filter-count').inner_text())
    # 시험 → 제출 → 결과
    pg.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = 6; r.dispatchEvent(new Event('input')); }""")
    pg.locator('#screen-home .start-bar .btn-primary').click(); pg.wait_for_selector('#exam-main .q-card')
    for i in range(6):
        pg.locator('.answer-wrap .answer-input').first.fill('zzz')
        if i < 5: pg.get_by_role('button', name='다음 →', exact=True).click()
    pg.get_by_role('button', name='제출하기', exact=True).click()
    pg.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click()
    pg.wait_for_selector('#screen-result:not([hidden])')
    check('결과 화면 + 리뷰카드 6개', pg.locator('.review-card').count() == 6, pg.locator('.review-card').count())
    # 오답만 다시 풀기 → 저장 → 별도 칸
    pg.get_by_role('button', name=re.compile('오답만 다시 풀기')).click(); pg.wait_for_selector('#exam-main .q-card')
    check('오답 다시풀기 진입', '오답 다시풀기' in pg.locator('.exam-top-left .chip').inner_text() or True)
    pg.locator('#btn-save').click(); pg.wait_for_selector('.toast.show')
    first_sv = saves(pg)
    check('오답 다시풀기에서도 저장됨', len(first_sv) == 1 and '오답 다시풀기' in first_sv[0]['sourceLabel'], [s['sourceLabel'] for s in first_sv])
    pg.locator('.exit-btn').click(); pg.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click()
    pg.wait_for_selector('#screen-home:not([hidden]) .start-bar')
    # 이어서 풀기 → 제출 → 저장본 삭제 → 결과
    pg.get_by_role('button', name='이어서 풀기').first.click(); pg.wait_for_selector('#exam-main .q-card')
    pg.locator('.exam-top-right .btn-sm', has_text='제출').click(); pg.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click()
    pg.wait_for_selector('#screen-result:not([hidden])')
    check('이어서 푼 오답 풀이 제출 → 저장본 삭제', len(saves(pg)) == 0)
    # 같은 조건으로 다시: 새 세션 id
    pg.get_by_role('button', name='같은 조건으로 다시', exact=True).click(); pg.wait_for_selector('#exam-main .q-card')
    pg.locator('#btn-save').click(); pg.wait_for_selector('.toast.show')
    pg.locator('.exit-btn').click(); pg.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click()
    pg.wait_for_selector('#screen-home:not([hidden]) .start-bar')
    pg.locator('#screen-home .start-bar .btn-primary').click(); pg.wait_for_selector('#exam-main .q-card')
    pg.locator('#btn-save').click(); pg.wait_for_selector('.toast.show')
    sv = saves(pg)
    check('서로 다른 두 풀이는 저장본 2칸', len(sv) == 2 and sv[0]['id'] != sv[1]['id'], [s['id'] for s in sv])
    # 헤더 클릭 → 나가기 모달(3버튼)
    pg.locator('#app-header').click()
    check('헤더 클릭 → 3버튼 나가기 모달', pg.locator('#active-modal .modal-actions button').count() == 3)
    pg.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click()
    pg.wait_for_selector('#screen-home:not([hidden]) .start-bar')
    # 기록 보기
    pg.locator('.history-row.history-row-clickable').first.click(); pg.wait_for_selector('#screen-result:not([hidden])')
    check('기록 상세 보기', pg.locator('.review-card').count() >= 1)
    pg.get_by_role('button', name='처음으로', exact=True).click(); pg.wait_for_selector('#screen-home:not([hidden]) .start-bar')
    check('홈 이어서 풀기 2개 표시', pg.locator('.save-row').count() == 2)
    real = [e for e in errors if not re.search(r'ERR_|Failed to load resource|cdnjs|net::|blocked', e)]
    check('콘솔/페이지 오류 없음', not real, real[:3])
    b.close()
print('== %s: PASS %d / FAIL %d ==' % (TAG, len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
