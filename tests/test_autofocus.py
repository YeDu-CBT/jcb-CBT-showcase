# -*- coding: utf-8 -*-
"""답안 입력칸 자동 포커스 테스트. usage: test_autofocus.py URL TAG"""
import sys, re, json, time
from playwright.sync_api import sync_playwright
URL, TAG = sys.argv[1], sys.argv[2]
PASS, FAIL, errors = [], [], []
def check(n, c, e=''):
    (PASS if c else FAIL).append(n); print(('PASS ' if c else 'FAIL ') + n + ((' :: ' + str(e)) if e != '' else ''))

ACTIVE_JS = """() => { const e = document.activeElement; if(!e) return null;
  return {tag: e.tagName, cls: e.className, label: e.getAttribute('aria-label'), disabled: !!e.disabled,
          inMain: !!e.closest('#exam-main'), value: ('value' in e ? e.value : null)}; }"""
def active(pg): return pg.evaluate(ACTIVE_JS)
def is_answer_focus(pg):
    a = active(pg)
    return bool(a and a['tag'] in ('INPUT', 'TEXTAREA') and 'answer-input' in a['cls'] and a['inMain'] and not a['disabled'])
def home_ready(pg): pg.wait_for_selector('#screen-home:not([hidden]) .start-bar')
def prep_2023_1(pg, mode='실전 모드'):
    pg.locator('button.round-chip[aria-label="2023년 1회"]').click()
    pg.locator('#screen-home .seg button', has_text='연도·회차 순서').click()
    pg.locator('#screen-home .seg button', has_text=mode).click()
    pg.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = r.max; r.dispatchEvent(new Event('input')); }""")
def start(pg):
    pg.locator('#screen-home .start-bar .btn-primary').click(); pg.wait_for_selector('#screen-exam:not([hidden]) .q-card')
def goto_q(pg, n):
    pg.locator('#exam-qgrid button', has_text=re.compile(r'^%d$' % n)).click(); pg.wait_for_selector('.q-num:text-is("Q%d")' % n)
def progress(pg): return pg.locator('#exam-progress-text').inner_text()

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = b.new_context(viewport={'width': 1280, 'height': 520})
    pg = ctx.new_page()
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
    pg.goto(URL); home_ready(pg)
    check('홈에서는 입력칸에 포커스를 두지 않음', not is_answer_focus(pg))
    check('버전 칩 Ver 2.5 · 수정 21회', pg.locator('.app-header-ver').inner_text() == 'Ver 2.5 · 수정 21회')

    # 1) 시작하자마자 (클릭 없이) 타자
    prep_2023_1(pg); start(pg)
    check('시작 직후 첫 문항 입력칸에 포커스(textarea)', is_answer_focus(pg) and active(pg)['tag'] == 'TEXTAREA', active(pg))
    pg.keyboard.type('ab')
    pg.keyboard.press('Enter')
    pg.keyboard.type('cd')
    v = pg.locator('.answer-wrap textarea').input_value()
    check('클릭 없이 타자 → 입력됨 (줄바꿈 포함)', v == 'ab\ncd', repr(v))
    check('진행 문구에 답변 1건 반영', '답변 1/20' in progress(pg), progress(pg))
    # 2) 다음 → 다음 문항에도 포커스
    pg.get_by_role('button', name='다음 →', exact=True).click()
    check('다음 → 새 문항 입력칸에 포커스', is_answer_focus(pg))
    pg.keyboard.type('x')
    check('다음 문항에 클릭 없이 입력', pg.locator('.answer-wrap .answer-input').first.input_value() == 'x')
    pg.get_by_role('button', name='← 이전', exact=True).click()
    a = active(pg)
    check('이전으로 돌아오면 기존 글 맨 끝에 커서', is_answer_focus(pg) and pg.evaluate("() => { const e = document.activeElement; return e.selectionStart === e.value.length && e.selectionEnd === e.value.length; }"))
    pg.keyboard.type('!')
    check('이어쓰기: ab\\ncd! 로 이어짐', pg.locator('.answer-wrap textarea').input_value() == 'ab\ncd!')

    # 3) 번호별 답안란 (14번): 첫 빈 칸
    # 입력칸이 화면 아래(접힌 부분)에 있는지 확인 후, 스크롤이 튀지 않는지 검사
    pg.evaluate("() => window.scrollTo(0,0)")
    goto_q(pg, 14)
    top = pg.evaluate("() => document.querySelector('#exam-main .answer-wrap .answer-input').getBoundingClientRect().top")
    check('(전제) 14번 입력칸은 화면 아래쪽(접힌 부분)에 있음', top > 520, top)
    check('14번 이동 후 스크롤이 튀지 않음(scrollY=0)', pg.evaluate("() => window.scrollY") == 0, pg.evaluate("() => window.scrollY"))
    a = active(pg)
    check('14번: 첫 칸(① 답안)에 포커스', is_answer_focus(pg) and a['label'] == '① 답안', a)
    pg.keyboard.type('idx2'); pg.keyboard.press('Enter')
    a = active(pg)
    check('Enter → ② 칸으로 이동', a['label'] == '② 답안', a)
    pg.keyboard.type('nx')
    vals = pg.evaluate("() => [...document.querySelectorAll('#exam-main .answer-parts .answer-input')].map(e => e.value)")
    check('두 칸에 클릭 없이 입력', vals == ['idx2', 'nx'], vals)
    pg.keyboard.press('Control+A'); pg.keyboard.press('Delete')     # ② 칸 비우기
    goto_q(pg, 15); goto_q(pg, 14)
    a = active(pg)
    check('일부만 채운 문항으로 돌아오면 첫 빈 칸(②)에 포커스', a['label'] == '② 답안' and a['value'] == '', a)
    pg.keyboard.type('nx')
    goto_q(pg, 15); goto_q(pg, 14)
    check('모두 찬 문항은 첫 칸에 포커스', active(pg)['label'] == '① 답안', active(pg))

    # 4) 저장 버튼 후에도 계속 타자
    goto_q(pg, 3)
    pg.keyboard.type('s1')
    pg.locator('#btn-save').click(); pg.wait_for_selector('.toast.show')
    check('저장 버튼을 눌러도 입력칸에 포커스 유지', is_answer_focus(pg), active(pg))
    pg.keyboard.type('s2')
    check('저장 뒤 이어서 타자', pg.locator('.answer-wrap .answer-input').first.input_value() == 's1s2')

    # 5) 모달: 열려 있는 동안은 입력칸이 포커스를 받지 않고, 취소·배경 클릭 뒤에 복귀
    pg.locator('.exit-btn').click(); pg.wait_for_selector('#active-modal')
    check('모달이 열려 있는 동안 입력칸에 포커스 없음', not is_answer_focus(pg), active(pg))
    pg.locator('#active-modal').get_by_role('button', name='계속 풀기').click()
    check('계속 풀기 → 입력칸으로 포커스 복귀', is_answer_focus(pg), active(pg))
    pg.locator('.exit-btn').click(); pg.wait_for_selector('#active-modal')
    pg.mouse.click(5, 5)                                   # 배경 클릭으로 닫기
    time.sleep(0.15)
    check('배경 클릭으로 닫으면 포커스 복귀', pg.locator('#active-modal').count() == 0 and is_answer_focus(pg), active(pg))
    pg.locator('.exam-top-right .btn-sm', has_text='제출').click(); pg.wait_for_selector('#active-modal')
    pg.locator('#active-modal').get_by_role('button', name='계속 풀기').click()
    check('제출 확인창에서 계속 풀기 → 포커스 복귀', is_answer_focus(pg))

    # 6) 검토표시 버튼 뒤
    pg.locator('.flag-btn').click()
    check('검토표시를 눌러도 포커스가 입력칸으로', is_answer_focus(pg), active(pg))

    # 7) 저장하고 나가기 → 이어서 풀기: 포커스
    pg.locator('.exit-btn').click()
    pg.locator('#active-modal').get_by_role('button', name='저장하고 나가기').click(); home_ready(pg)
    check('나가면 홈(입력칸 포커스 없음)', not is_answer_focus(pg))
    pg.get_by_role('button', name='이어서 풀기').first.click(); pg.wait_for_selector('#screen-exam:not([hidden]) .q-card')
    check('이어서 풀기 직후 입력칸에 포커스', is_answer_focus(pg), active(pg))
    pg.keyboard.type('r')
    check('불러온 뒤 클릭 없이 이어쓰기', pg.locator('.answer-wrap .answer-input').first.input_value().endswith('r'))

    # 8) 제출 → 결과 → 오답만 다시 풀기 (결과 화면에서 시험 화면으로 전환될 때)
    pg.locator('.exam-top-right .btn-sm', has_text='제출').click()
    pg.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click(); pg.wait_for_selector('#screen-result:not([hidden])')
    check('결과 화면에서는 입력칸 포커스 없음', not is_answer_focus(pg))
    pg.get_by_role('button', name=re.compile('오답만 다시 풀기')).click(); pg.wait_for_selector('#screen-exam:not([hidden]) .q-card')
    check('오답만 다시 풀기 시작 직후 포커스', is_answer_focus(pg), active(pg))
    pg.locator('.exit-btn').click(); pg.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click(); home_ready(pg)

    # 9) 학습 모드: 정답 공개되면 잠긴 칸 → 포커스 시도하지 않음, 다음 문항에서 다시
    pg.locator('#screen-home .seg button', has_text='학습 모드').click(); start(pg)
    check('학습 모드 시작 직후 포커스', is_answer_focus(pg))
    pg.keyboard.type('zzz')
    pg.get_by_role('button', name=re.compile('정답 (확인|보기)')).first.click()
    dis = pg.evaluate("() => document.querySelector('#exam-main .answer-wrap .answer-input').disabled")
    check('정답 공개 → 입력칸 잠김 + 잠긴 칸에 포커스 없음', dis and not is_answer_focus(pg), active(pg))
    pg.get_by_role('button', name='다음 →', exact=True).click()
    check('다음 문항에서 다시 포커스', is_answer_focus(pg))

    # 콘솔 오류
    real = [e for e in errors if not re.search(r'ERR_|Failed to load resource|cdnjs|net::|blocked', e)]
    check('콘솔/페이지 오류 없음', not real, real[:3])

    # 10) 터치 기기: 화면 키보드가 지문을 가리지 않도록 자동 포커스 끔
    tctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    t = tctx.new_page(); t.goto(URL); home_ready(t)
    mm = t.evaluate("() => matchMedia('(hover: hover) and (pointer: fine)').matches")
    check('(전제) 터치 에뮬레이션은 (hover:hover) and (pointer:fine) 불일치', mm is False, mm)
    prep_2023_1(t); start(t)
    check('터치 기기에서는 자동 포커스 없음(키보드 안 올라옴)', not is_answer_focus(t), active(t))
    t.locator('.answer-wrap .answer-input').first.tap()
    check('터치: 직접 누르면 입력칸 활성화', is_answer_focus(t))
    b.close()
print('\n== %s: PASS %d / FAIL %d ==' % (TAG, len(PASS), len(FAIL)))
if FAIL: print('FAILED:', FAIL); sys.exit(1)
