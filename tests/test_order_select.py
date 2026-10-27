# -*- coding: utf-8 -*-
"""연도·회차 순서 옵션과 전체/연도별 선택 버튼 테스트 (사이트 fetch 버전 + standalone file:// 버전)."""
import sys, re, json, subprocess, time, os
from playwright.sync_api import sync_playwright

TARGET = sys.argv[1]          # http://127.0.0.1:PORT/index.html  또는  file:///.../jcb_cbt.html
SHOT = sys.argv[2]            # 스크린샷 접두어
PASS, FAIL = [], []

def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + str(extra)) if extra != '' else ''))

def count_text(page):
    return page.inner_text('.filter-count')

def pressed(page, sel):
    return page.eval_on_selector_all(sel, "els => els.filter(e => e.getAttribute('aria-pressed')==='true').length")

with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = br.new_context(viewport={'width': 1100, 'height': 900})
    page = ctx.new_page()
    errors, failed = [], []
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
    page.on('requestfailed', lambda r: failed.append(r.url))
    page.goto(TARGET)
    page.wait_for_selector('#screen-home .round-chip')
    home = '#screen-home'

    # 1. 구조
    check('회차 칩 21개', page.locator(home + ' .round-grid .round-chip').count() == 21)
    check('연도 버튼 7개', page.locator(home + ' .year-chip').count() == 7)
    check('초기 전체 404문항', '404문항' in count_text(page), count_text(page))

    # 2. 전체 선택
    page.click('#btn-rounds-all')
    n_on = pressed(page, home + ' .round-grid .round-chip')
    check('전체 선택 -> 회차 칩 21개 모두 눌림', n_on == 21, n_on)
    check('전체 선택 -> 연도 버튼 7개 모두 눌림', pressed(page, home + ' .year-chip') == 7)
    t = count_text(page)
    check('전체 선택 -> "전체 회차" 404문항', '전체 회차' in t and '404문항' in t, t)

    # 3. 선택 해제
    page.click('#btn-rounds-none')
    check('선택 해제 -> 눌린 칩 0개', pressed(page, home + ' .round-grid .round-chip') == 0)
    check('선택 해제 -> 404문항(전체 범위)', '404문항' in count_text(page) and '전체 회차' in count_text(page), count_text(page))

    # 4. 연도 전체 (비어 있는 상태에서 누르면 그 해만)
    def year_btn(y): return page.locator(home + ' .year-chip', has_text=f'{y}년 전체')
    year_btn(2021).click()
    t = count_text(page)
    check('2021년 전체 -> 60문항, 라벨', '60문항' in t and '2021년 전체' in t, t)
    check('2021년 전체 -> 연도 버튼 1개, 칩 3개 눌림', pressed(page, home + ' .year-chip') == 1 and pressed(page, home + ' .round-grid .round-chip') == 3)

    # 5. 두 번째 연도 추가
    year_btn(2023).click()
    t = count_text(page)
    check('2021+2023 -> 120문항, 라벨', '120문항' in t and '2021·2023년 전체' in t, t)

    # 6. 다시 눌러 해제
    year_btn(2021).click()
    t = count_text(page)
    check('2021 해제 -> 60문항(2023만)', '60문항' in t and '2023년 전체' in t and '2021' not in t, t)

    # 7. 일부만 선택된 해 + 연도 버튼 -> 나머지 채워 전체 선택
    page.click('#btn-rounds-none')
    page.locator(home + ' .year-group').first.locator('.round-grid .round-chip').first.click()   # 2020년 1회
    t = count_text(page)
    check('2020년 1회만 -> 20문항', '20문항' in t and '2020년 1회' in t, t)
    check('일부 선택 -> 연도 버튼은 눌리지 않음', pressed(page, home + ' .year-chip') == 0)
    year_btn(2020).click()
    t = count_text(page)
    check('일부 선택 상태에서 2020년 전체 -> 80문항', '80문항' in t and '2020년 전체' in t, t)
    year_btn(2020).click()
    check('다시 누르면 해제 -> 404문항(전체 범위)', '404문항' in count_text(page), count_text(page))

    # 8. 연도·회차 순서 라벨/힌트 + 프리셋
    page.click('#btn-rounds-none')
    check('순서 버튼 라벨', page.locator(home + ' .seg button', has_text='연도·회차 순서').count() == 1)
    check('옛 라벨 "원본 순서" 없음', page.locator(home + ' .seg button', has_text='원본 순서').count() == 0)
    page.click('#btn-code-ordered')
    t = count_text(page)
    check('코드 문제 프리셋 -> 163문항', '163문항' in t, t)
    check('프리셋이 순서를 "연도·회차 순서"로 바꿈',
          page.locator(home + ' .seg button[aria-pressed="true"]', has_text='연도·회차 순서').count() == 1)
    hint = page.inner_text('#order-hint')
    check('힌트: 오래된 회차부터', hint.startswith('오래된 회차부터') and '→' in hint, hint)

    # 9. 163문항 전부로 시작해서 출제 순서 확인
    page.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = r.max; r.dispatchEvent(new Event('input')); }""")
    hint2 = page.inner_text('#order-hint')
    check('슬라이더를 움직이면 힌트가 갱신됨(163문항)', '163문항' in hint2, hint2)
    page.click('#screen-home .start-bar .btn-primary')
    page.wait_for_selector('#exam-main .q-card')
    seq = []
    for i in range(163):
        chip = page.locator('#exam-main .q-head-left .app-chip').first.inner_text()
        m = re.match(r'(\d+)년 (\d+)회 · #(\d+)', chip)
        lang = page.locator('#exam-main .q-head-left .chip:not(.app-chip)').first.inner_text()
        seq.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), lang))
        if i < 162:
            page.click('#exam-main >> text=다음 →')
    keys = [s[:3] for s in seq]
    check('출제 순서가 연도→회차→번호 오름차순', keys == sorted(keys), keys[:4])
    check('전부 코드 문제(기타 없음)', all(s[3] != '기타' for s in seq))
    check('중복 없음 163개', len(set(keys)) == 163)
    check('첫 문항 2020년 1회', seq[0][:2] == (2020, 1), seq[0])

    # 10. 무작위 모드는 순서가 정렬과 다를 수 있음 (같은 풀 크기)
    page.screenshot(path=SHOT + '_exam.png')
    page.click('.exit-btn')
    time.sleep(0.3)
    page.screenshot(path=SHOT + '_modal.png')
    br.close()

    # 11. 새 컨텍스트: 모바일 폭 + 가로 스크롤 + 스크린샷
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    m = br.new_context(viewport={'width': 390, 'height': 844})
    mp = m.new_page()
    mp.on('console', lambda mm: errors.append(mm.text) if mm.type == 'error' else None)
    mp.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
    mp.goto(TARGET)
    mp.wait_for_selector('#screen-home .round-chip')
    mp.click('#btn-rounds-all')
    sw = mp.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    check('모바일 390px 가로 스크롤 없음', sw[0] <= sw[1], sw)
    # 칩이 화면 밖으로 삐져나오지 않는지
    over = mp.evaluate("""() => Array.from(document.querySelectorAll('#screen-home .round-chip, #screen-home .year-chip, #screen-home .filter-tools .btn'))
        .filter(e => e.getBoundingClientRect().right > window.innerWidth + 0.5).length""")
    check('모바일 칩/버튼이 화면 밖으로 나가지 않음', over == 0, over)
    mp.locator('#screen-home .filter-block').first.screenshot(path=SHOT + '_mobile_rounds.png')
    mp.click('#btn-rounds-none')
    mp.click('#btn-code-ordered')
    mp.screenshot(path=SHOT + '_mobile_full.png', full_page=False)
    br.close()

    # 환경 요인 제외: 샌드박스가 막는 highlight.js CDN, 로컬 http.server에 없는 favicon
    real_err = [e for e in errors if 'ERR_TUNNEL_CONNECTION_FAILED' not in e and '404 (File not found)' not in e]
    real_fail = [u for u in failed if 'cdnjs.cloudflare.com' not in u]
    print('  (제외한 환경 요인: 콘솔 %d건, CDN 요청 %d건)' % (len(errors) - len(real_err), len(failed) - len(real_fail)))
    check('콘솔 에러 0 (환경 요인 제외)', len(real_err) == 0, real_err[:3])
    check('요청 실패 0 (CDN 제외)', len(real_fail) == 0, real_fail[:3])

print(f'\n== {len(PASS)} pass / {len(FAIL)} fail ==')
if FAIL:
    print('FAILED:', FAIL)
    sys.exit(1)
