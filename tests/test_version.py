# -*- coding: utf-8 -*-
"""헤더 버전 표시 테스트: 세 사이트 공통.
usage: test_version.py NAME NEW_URL OLD_URL EXPECTED_TEXT SHOTPREFIX
"""
import sys
from playwright.sync_api import sync_playwright

NAME, NEW, OLD, EXPECT, SHOT = sys.argv[1:6]
N = EXPECT.split('·')[0].strip().replace('Ver 1.', '')
PASS, FAIL = [], []

def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + str(extra)) if extra != '' else ''))

def rect(page, sel):
    s = sel
    return page.evaluate("""(s) => { const e = document.querySelector(s); if(!e) return null;
      const r = e.getBoundingClientRect(); return {l:r.left, r:r.right, t:r.top, b:r.bottom, w:r.width, h:r.height}; }""", s)

def textrect(page, sel):
    """블록 요소의 박스가 아니라 '실제 글자가 차지하는 범위'(Range)를 잰다."""
    return page.evaluate("""(s) => { const e = document.querySelector(s); const rg = document.createRange(); rg.selectNodeContents(e);
      const r = rg.getBoundingClientRect(); return {l:r.left, r:r.right, t:r.top, b:r.bottom, w:r.width, h:r.height}; }""", sel)

def overlap(a, b):
    return not (a['r'] <= b['l'] + 0.5 or b['r'] <= a['l'] + 0.5 or a['b'] <= b['t'] + 0.5 or b['b'] <= a['t'] + 0.5)

def vis(page, sel):
    return page.evaluate("""(s) => { const e = document.querySelector(s); if(!e) return false;
      const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
      return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0; }""", sel)

def start_exam(page):
    page.wait_for_selector('#screen-home .seg')
    page.locator('#screen-home .seg button', has_text='학습 모드').click()
    page.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = 8; r.dispatchEvent(new Event('input')); }""")
    page.locator('#screen-home .start-bar .btn-primary').click()
    page.wait_for_selector('#exam-main .q-card')

def header_h(page):
    return page.evaluate("() => document.getElementById('app-header').getBoundingClientRect().height")

def css_var_h(page):
    return page.evaluate("() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--app-header-h'))")

with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    errors = []

    # ---------- 이전 버전(기준선): 헤더 높이 기록
    base = {}
    for label, vp in (('desk', (1100, 900)), ('mob', (390, 844))):
        ctx = br.new_context(viewport={'width': vp[0], 'height': vp[1]})
        pg = ctx.new_page(); pg.goto(OLD); pg.wait_for_selector('#screen-home .seg')
        base[label + '_home'] = header_h(pg)
        start_exam(pg)
        base[label + '_exam'] = header_h(pg)
        ctx.close()
    print('  기준선(수정 전) 헤더 높이:', base)

    for label, vp in (('desk', (1100, 900)), ('mob', (390, 844))):
        ctx = br.new_context(viewport={'width': vp[0], 'height': vp[1]})
        pg = ctx.new_page()
        pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
        pg.goto(NEW); pg.wait_for_selector('#screen-home .seg')
        tag = '[%s/%s] ' % (NAME, label)

        # ----- 홈
        ver = pg.locator('#app-header .app-header-ver')
        check(tag + '홈: 버전 칩 1개, 문구 일치', ver.count() == 1 and ver.inner_text() == EXPECT, ver.inner_text())
        ttl = ver.get_attribute('title')
        check(tag + '툴팁에 수정 횟수 설명', ('수정 %s회' % N) in ttl, ttl)
        e, v, t = rect(pg, '.app-header-eyebrow'), rect(pg, '.app-header-ver'), rect(pg, '.app-header-title')
        check(tag + '홈: 칩이 헤더 맨 위(작은 글씨와 같은 줄 또는 바로 옆)에 있고 제목 위쪽', v['b'] <= t['t'] + 1, (v, t))
        if label == 'desk':
            check(tag + '홈(데스크톱): 작은 글씨 오른쪽 옆, 같은 줄', v['l'] >= e['r'] - 0.5 and abs((v['t'] + v['b']) / 2 - (e['t'] + e['b']) / 2) < 8 and not overlap(e, v), (e, v))
        check(tag + '홈: 칩과 작은 글씨 겹침 없음', not overlap(e, v))
        hh = header_h(pg)
        pg.wait_for_timeout(150)
        check(tag + '홈: --app-header-h == 실제 헤더 높이(±1px)', abs(css_var_h(pg) - hh) <= 1, (css_var_h(pg), hh))
        print('  %s홈 헤더 높이 수정 전 %.1f → 후 %.1f' % (tag, base[label + '_home'], hh))
        sw = pg.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
        check(tag + '홈: 가로 스크롤 없음', sw[0] <= sw[1], sw)
        check(tag + '홈: 칩이 화면 안', v['l'] >= 0 and v['r'] <= vp[0], v)
        pg.locator('#app-header').screenshot(path='%s_%s_home.png' % (SHOT, label))

        # ----- 시험 화면
        start_exam(pg)
        check(tag + '시험: 칩 표시', vis(pg, '#app-header .app-header-ver'))
        hx = header_h(pg)
        v, t = rect(pg, '.app-header-ver'), textrect(pg, '.app-header-title')
        check(tag + '시험: 칩이 제목 글자와 겹치지 않음', not overlap(v, t), (v, t))
        check(tag + '시험: 칩이 헤더 안쪽·화면 안', v['t'] >= 0 and v['b'] <= hx + 0.5 and v['r'] <= vp[0] + 0.5, (v, hx))
        print('  %s시험 헤더 높이 수정 전 %.1f → 후 %.1f' % (tag, base[label + '_exam'], hx))
        pg.wait_for_timeout(150)
        check(tag + '시험: --app-header-h 정합', abs(css_var_h(pg) - hx) <= 1, (css_var_h(pg), hx))
        # sticky 아래 요소가 헤더에 가려지지 않는지 (스크롤 후)
        pg.evaluate("() => window.scrollTo(0, 500)"); pg.wait_for_timeout(150)
        et = rect(pg, '.exam-top'); hb = rect(pg, '#app-header')
        check(tag + '시험: 스크롤해도 exam-top이 헤더 바로 아래(겹침 없음)', et and et['t'] >= hb['b'] - 1.5, (et, hb['b']))
        pg.evaluate("() => window.scrollTo(0, 0)")
        pg.locator('#app-header').screenshot(path='%s_%s_exam.png' % (SHOT, label))
        sw = pg.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
        check(tag + '시험: 가로 스크롤 없음', sw[0] <= sw[1], sw)

        # 헤더(칩 포함) 클릭 → 종료 확인 → 홈
        pg.locator('#app-header .app-header-ver').click()
        pg.wait_for_selector('#modal-root >> text=종료하기')
        pg.click('#modal-root >> text=종료하기')
        pg.wait_for_selector('#screen-home:not([hidden]) .seg')
        check(tag + '시험 중 칩/헤더 클릭 → 종료 확인창 → 처음 화면', True)

        # ----- 결과 화면
        start_exam(pg)
        for _ in range(2):
            pg.locator('#exam-main .check-row .btn').first.click()
            pg.click('#exam-main >> text=다음 →')
        pg.click('.exam-top .btn-sm')
        pg.locator('#modal-root .btn-primary').click()
        pg.wait_for_selector('#screen-result:not([hidden])', timeout=8000)
        check(tag + '결과: 칩 표시', vis(pg, '#app-header .app-header-ver'))
        v, t = rect(pg, '.app-header-ver'), textrect(pg, '.app-header-title')
        check(tag + '결과: 칩이 제목 글자와 겹치지 않음', not overlap(v, t), (v, t))
        sw = pg.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
        check(tag + '결과: 가로 스크롤 없음', sw[0] <= sw[1], sw)
        pg.locator('#app-header').screenshot(path='%s_%s_result.png' % (SHOT, label))
        pg.locator('#app-header').click()
        pg.wait_for_selector('#screen-home:not([hidden]) .seg')
        check(tag + '결과 화면에서 헤더 클릭 → 처음 화면', True)
        ctx.close()
    br.close()

    real = [e for e in errors if 'ERR_TUNNEL_CONNECTION_FAILED' not in e and '404 (File not found)' not in e]
    print('  (제외한 환경 요인 콘솔 %d건)' % (len(errors) - len(real)))
    check('콘솔 에러 0 (환경 요인 제외)', len(real) == 0, real[:3])

print('\n== %s: %d pass / %d fail ==' % (NAME, len(PASS), len(FAIL)))
if FAIL:
    print('FAILED:', FAIL); sys.exit(1)
