# -*- coding: utf-8 -*-
"""정처기 CBT: 1번 해답 줄바꿈 / 14번 코드 교체 / 중간 저장·불러오기 테스트.
usage: test_save_feature.py URL TAG
"""
import os
import sys, json, time, re
from playwright.sync_api import sync_playwright

URL, TAG = sys.argv[1], sys.argv[2]
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_out')   # 스크린샷 등 시험 산출물
os.makedirs(SP, exist_ok=True)
PASS, FAIL = [], []
errors = []

def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + str(extra)) if extra != '' else ''))

def saves(page):
    return json.loads(page.evaluate("() => localStorage.getItem('jcb_cbt_saves_v1')") or '[]')

def home_ready(page):
    page.wait_for_selector('#screen-home:not([hidden]) .start-bar')

def select_round_2023_1(page, ordered=True, count_max=True):
    page.locator('button.round-chip[aria-label="2023년 1회"]').click()
    if ordered:
        page.locator('#screen-home .seg button', has_text='연도·회차 순서').click()
    if count_max:
        page.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = r.max; r.dispatchEvent(new Event('input')); }""")

def set_mode(page, label):
    page.locator('#screen-home .seg button', has_text=label).click()

def set_limit(page, label):
    page.locator('#screen-home .seg button', has_text=label).click()

def start(page):
    page.locator('#screen-home .start-bar .btn-primary').click()
    page.wait_for_selector('#screen-exam:not([hidden]) .q-card')

def goto_q(page, n):
    page.locator('#exam-qgrid button', has_text=re.compile(r'^%d$' % n)).click()
    page.wait_for_selector('.q-num:text-is("Q%d")' % n)

def progress_text(page):
    return page.locator('#exam-progress-text').inner_text()

def modal_buttons(page):
    return [b.inner_text() for b in page.locator('#active-modal .modal-actions button').all()]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        page = ctx.new_page()
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append('PAGEERROR: ' + str(e)))
        page.goto(URL)
        home_ready(page)

        # ---------- 버전 칩 ----------
        chip = page.locator('.app-header-ver').inner_text()
        check('버전 칩 Ver 2.5 · 수정 21회', chip == 'Ver 2.5 · 수정 21회', chip)
        title = page.locator('.app-header-ver').get_attribute('title')
        check('버전 칩 title', '수정 21회' in title and 'Ver 2.5' in title, title)

        # ---------- 1번: 줄바꿈 해답 ----------
        select_round_2023_1(page)
        set_mode(page, '학습 모드')
        start(page)
        chipq = page.locator('.q-head-left .chip').first.inner_text()
        check('첫 문항 = 2023년 1회 #1', '2023년 1회' in chipq and '#1' in chipq, chipq)
        ta = page.locator('.answer-wrap textarea.answer-input')
        check('1번 입력칸이 여러 줄 textarea', ta.count() == 1)
        # "/" 로 구분해 쓰면 오답
        ta.fill('10 / 11 / 10 / 20')
        page.get_by_role('button', name='정답 확인', exact=True).click()
        ttl = page.locator('.exp-title').inner_text()
        check('"10 / 11 / 10 / 20" 입력은 오답', '오답' in ttl, ttl)
        mav = page.locator('.ma-value').first.inner_text()
        check('정답 표시가 줄바꿈 4줄(슬래시 없음)', mav.split('\n') == ['10', '11', '10', '20'] and '/' not in mav, repr(mav))
        # 새로 시작해 4줄로 입력하면 정답
        page.locator('.exit-btn').click()
        page.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click()
        home_ready(page)
        page.locator('#screen-home .seg button', has_text='연도·회차 순서').click()
        start(page)
        ta = page.locator('.answer-wrap textarea.answer-input')
        ta.fill('10\n11\n10\n20')
        page.get_by_role('button', name='정답 확인', exact=True).click()
        ttl = page.locator('.exp-title').inner_text()
        check('4줄 입력은 정답', '정답입니다' in ttl, ttl)

        # ---------- 14번: C 코드 + ①② 칸 ----------
        goto_q(page, 14)
        chips = [c.inner_text() for c in page.locator('.q-head-left .chip').all()]
        check('14번 언어 칩 = C', 'C' in chips, chips)
        code = page.locator('.q-code').inner_text() if page.locator('.q-code').count() else page.locator('pre').first.inner_text()
        check('14번 코드: swap(int* a, int idx1, int idx2)', 'void swap(int* a, int idx1, int idx2)' in code)
        check('14번 코드: 빈칸 ① ②', 'a[( ① )] = t;' in code and 'Usort(a, ( ② ));' in code)
        check('14번 코드: Java 흔적 없음', 'public' not in code and 'System.out' not in code)
        labels = [l.inner_text() for l in page.locator('.ap-label').all()]
        check('14번 답안칸 라벨 ①② (2칸)', labels == ['①', '②'], labels)
        inputs = page.locator('.answer-parts .answer-input')
        inputs.nth(0).fill('idx2'); inputs.nth(1).fill('nx')
        page.get_by_role('button', name='정답 확인', exact=True).click()
        ttl = page.locator('.exp-title').inner_text()
        check('14번 idx2 / nx 정답', '정답입니다' in ttl, ttl)
        page.screenshot(path=f'{SP}/save_{TAG}_q14.png', full_page=False)
        # 틀린 값
        page.locator('.exit-btn').click()
        page.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click()
        home_ready(page)

        # ---------- 저장 · 불러오기 (실전 모드, 45분) ----------
        check('저장본 없을 때 이어서 풀기 구역 없음', page.locator('#save-section').count() == 0)
        set_mode(page, '실전 모드'); set_limit(page, '45분')
        page.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = 10; r.dispatchEvent(new Event('input')); }""")
        start(page)
        check('시험 화면에 저장 버튼', page.locator('#btn-save').count() == 1 and page.locator('#btn-save').inner_text() == '저장')
        page.locator('.answer-wrap .answer-input').first.fill('내답1')
        page.locator('.flag-btn').click()                       # Q1 검토표시
        goto_q(page, 3)
        page.locator('.answer-wrap .answer-input').first.fill('내답3')
        goto_q(page, 4)
        time.sleep(1.2)
        timer_before = page.locator('#exam-timer').inner_text()
        page.locator('#btn-save').click()
        page.wait_for_selector('.toast.show')
        toast = page.locator('.toast').inner_text()
        check('저장 토스트 (1/10)', '저장했습니다 (1/10)' in toast, toast)
        sv = saves(page)
        check('localStorage 에 저장본 1개', len(sv) == 1)
        rec = sv[0]
        check('저장 내용: idx=3, answered=2, 10문항, 실전, 45분',
              rec['idx'] == 3 and rec['answered'] == 2 and len(rec['ids']) == 10 and rec['mode'] == 'exam' and rec['timeLimitSec'] == 2700,
              {k: rec[k] for k in ('idx', 'answered', 'mode', 'timeLimitSec', 'remainingSec')})
        check('저장 내용: flagged 1개', len([k for k, v in rec['flagged'].items() if v]) == 1)
        first_id = rec['ids'][0]
        page.locator('#btn-save').click()                          # 같은 풀이를 다시 저장 → 덮어쓰기
        time.sleep(0.2)
        check('같은 풀이 재저장은 덮어쓰기(개수 그대로 1)', len(saves(page)) == 1)

        # 나가기 모달: 버튼 3개
        page.locator('.exit-btn').click()
        btns = modal_buttons(page)
        check('나가기 모달 버튼 3개', btns == ['계속 풀기', '저장 없이 종료', '저장하고 나가기'], btns)
        # 계속 풀기 → 시험 화면 유지
        page.locator('#active-modal').get_by_role('button', name='계속 풀기').click()
        check('계속 풀기 → 시험 화면 유지', page.locator('#screen-exam').is_visible())
        # 저장하고 나가기
        goto_q(page, 5)
        page.locator('.answer-wrap .answer-input').first.fill('내답5')
        page.locator('.exit-btn').click()
        page.locator('#active-modal').get_by_role('button', name='저장하고 나가기').click()
        home_ready(page)
        sv = saves(page)
        check('저장하고 나가기 → 홈 + 저장본 1개(덮어쓰기), answered=3, idx=4', len(sv) == 1 and sv[0]['answered'] == 3 and sv[0]['idx'] == 4,
              (len(sv), sv[0]['answered'], sv[0]['idx']))
        check('홈에 이어서 풀기 구역', page.locator('#save-section .save-row').count() == 1)
        sub = page.locator('.sv-sub').inner_text()
        check('저장행 요약 문구', '답변 3/10' in sub and '현재 5번' in sub and '실전 모드' in sub and '남은 시간' in sub, sub)
        page.screenshot(path=f'{SP}/save_{TAG}_home_with_save.png', full_page=False)
        time.sleep(2.2)           # 홈에 머무는 동안 타이머가 흘러가면 안 된다
        page.get_by_role('button', name='이어서 풀기').first.click()
        page.wait_for_selector('#screen-exam:not([hidden]) .q-card')
        check('이어서 풀기 → 5번 문항', progress_text(page).startswith('5 / 10'), progress_text(page))
        check('답변 개수 복원 (3/10)', '답변 3/10' in progress_text(page), progress_text(page))
        check('5번 답안 복원', page.locator('.answer-wrap .answer-input').first.input_value() == '내답5')
        goto_q(page, 1)
        check('1번 답안 복원', page.locator('.answer-wrap .answer-input').first.input_value() == '내답1')
        check('1번 검토표시 복원', page.locator('.flag-btn').get_attribute('aria-pressed') == 'true')
        goto_q(page, 3)
        check('3번 답안 복원', page.locator('.answer-wrap .answer-input').first.input_value() == '내답3')
        t_after = page.locator('#exam-timer').inner_text()
        def sec(t): m, s = t.split(':'); return int(m) * 60 + int(s)
        saved_rem = saves(page)[0]['remainingSec']
        check('타이머 복원: 홈에 머문 시간만큼 줄지 않음', abs(sec(t_after) - saved_rem) <= 2, (t_after, saved_rem))
        time.sleep(2.1)
        check('타이머 다시 흘러감', sec(page.locator('#exam-timer').inner_text()) < sec(t_after) + 1 and sec(page.locator('#exam-timer').inner_text()) <= sec(t_after))
        toast = page.locator('.toast').inner_text() if page.locator('.toast').count() else ''
        # 이어서 푼 뒤 제출 → 저장본 삭제 + 기록 생성
        page.locator('.exam-top-right .btn-sm', has_text='제출').click()
        page.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click()
        page.wait_for_selector('#screen-result:not([hidden])')
        check('제출하면 저장본이 지워짐', len(saves(page)) == 0, saves(page))
        hist = json.loads(page.evaluate("() => localStorage.getItem('jcb_cbt_history_v1')") or '[]')
        check('제출한 풀이는 기록에 남음', len(hist) >= 1 and hist[0]['total'] == 10)
        page.get_by_role('button', name='처음으로', exact=True).click()
        home_ready(page)
        check('홈에서 이어서 풀기 구역 사라짐', page.locator('#save-section').count() == 0)

        # ---------- 학습 모드 저장: revealed/selfMarks + 설정 모드 복귀 ----------
        set_mode(page, '학습 모드'); set_limit(page, '없음')
        start(page)
        page.locator('.answer-wrap .answer-input').first.fill('아무거나')
        page.get_by_role('button', name=re.compile('정답 (확인|보기)')).first.click()
        check('학습: 정답 공개됨', page.locator('.explain-box').count() >= 1)
        goto_q(page, 2)
        page.locator('#btn-save').click()
        page.wait_for_selector('.toast.show')
        page.locator('.exit-btn').click()
        page.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click()
        home_ready(page)
        sv = saves(page)
        check('학습 저장본 revealed 1개', len([k for k, v in sv[0]['revealed'].items() if v]) == 1 and sv[0]['mode'] == 'study')
        set_mode(page, '실전 모드')                                 # 홈 설정을 실전으로 바꿔 둔다
        page.get_by_role('button', name='이어서 풀기').first.click()
        page.wait_for_selector('#screen-exam:not([hidden]) .q-card')
        check('저장본 모드(학습) 복원: 정답 확인 버튼 보임/탐색판 범례', page.locator('.navlegend').inner_text().count('정답') >= 1)
        goto_q(page, 1)
        check('학습: 공개 상태 복원(해설 박스)', page.locator('.explain-box').count() >= 1)
        page.locator('.exit-btn').click()
        page.locator('#active-modal').get_by_role('button', name='저장 없이 종료').click()
        home_ready(page)
        pressed = page.locator('#screen-home .seg button', has_text='실전 모드').get_attribute('aria-pressed')
        check('홈으로 돌아오면 풀이 모드 설정이 원래대로(실전)', pressed == 'true', pressed)

        # ---------- 삭제 ----------
        page.locator('.save-row').get_by_role('button', name='삭제').first.click()
        check('삭제 확인 모달', page.locator('#active-modal h3').inner_text() == '저장본을 삭제할까요?')
        page.locator('#active-modal').get_by_role('button', name='취소').click()
        check('삭제 취소 → 그대로', len(saves(page)) == 1)
        page.locator('.save-row').get_by_role('button', name='삭제').first.click()
        page.locator('#active-modal').get_by_role('button', name='삭제', exact=True).click()
        time.sleep(0.2)
        check('삭제 → 저장본 0개, 구역 사라짐', len(saves(page)) == 0 and page.locator('#save-section').count() == 0)

        # ---------- 가득 참 (10개) ----------
        ids = [q for q in json.loads(page.evaluate("() => localStorage.getItem('jcb_cbt_history_v1')") or '[]')]
        fake = []
        for i in range(10):
            fake.append({'id': 'fake%d' % i, 'ts': 1000000 + i, 'sourceLabel': '가짜 %d' % i, 'mode': 'exam', 'ids': [first_id],
                         'idx': 0, 'answers': {}, 'selfMarks': {}, 'revealed': {}, 'flagged': {}, 'timeLimitSec': 0, 'remainingSec': 0,
                         'elapsedSec': 0, 'answered': 0})
        fake.sort(key=lambda x: -x['ts'])
        page.evaluate("(v) => localStorage.setItem('jcb_cbt_saves_v1', v)", json.dumps(fake))
        page.reload(); home_ready(page)
        check('홈에 저장본 10개 표시', page.locator('.save-row').count() == 10)
        page.locator('#screen-home .seg button', has_text='실전 모드').click()
        page.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = 5; r.dispatchEvent(new Event('input')); }""")
        start(page)
        page.locator('#btn-save').click()
        page.wait_for_selector('#active-modal')
        check('10개 가득 → 안내 모달', page.locator('#active-modal h3').inner_text() == '저장 공간이 가득 찼습니다', page.locator('#active-modal p').inner_text())
        check('모달이 가장 오래된 저장본을 지목', '가짜 0' in page.locator('#active-modal p').inner_text())
        page.locator('#active-modal').get_by_role('button', name='취소').click()
        check('취소하면 10개 그대로, 가짜0 유지', len(saves(page)) == 10 and any(x['id'] == 'fake0' for x in saves(page)))
        page.locator('#btn-save').click()
        page.locator('#active-modal').get_by_role('button', name='지우고 저장').click()
        page.wait_for_selector('.toast.show')
        sv = saves(page)
        check('지우고 저장 → 10개 유지, fake0 삭제, 새 저장본 맨 앞',
              len(sv) == 10 and not any(x['id'] == 'fake0' for x in sv) and not sv[0]['id'].startswith('fake'), [x['id'] for x in sv][:3])

        # ---------- 저장 실패(브라우저가 저장을 막음) ----------
        page.evaluate("() => { Storage.prototype.setItem = function(){ throw new Error('blocked'); }; }")
        page.locator('#btn-save').click()
        page.wait_for_selector('.toast.bad')
        check('저장 실패 → 빨간 토스트', '저장하지 못했습니다' in page.locator('.toast.bad').inner_text())
        page.locator('.exit-btn').click()
        page.locator('#active-modal').get_by_role('button', name='저장하고 나가기').click()
        time.sleep(0.4)
        check('저장 실패 시 "저장하고 나가기"는 시험 화면에 남음', page.locator('#screen-exam').is_visible() and not page.locator('#screen-home').is_visible())

        # ---------- 데이터가 바뀐 저장본(없는 문항 id) ----------
        page2 = ctx.new_page()
        page2.goto(URL); home_ready(page2)
        page2.evaluate("""(v) => localStorage.setItem('jcb_cbt_saves_v1', v)""", json.dumps([
            {'id': 'ghost', 'ts': 5, 'sourceLabel': '유령', 'mode': 'exam', 'ids': ['no-such-id'], 'idx': 0, 'answers': {}, 'selfMarks': {}, 'revealed': {}, 'flagged': {}, 'timeLimitSec': 0, 'remainingSec': 0, 'elapsedSec': 0, 'answered': 0},
            {'id': 'mixed', 'ts': 6, 'sourceLabel': '일부만', 'mode': 'exam', 'ids': ['no-such-id', first_id], 'idx': 1, 'answers': {first_id: 'zz', 'no-such-id': 'x'}, 'selfMarks': {}, 'revealed': {}, 'flagged': {}, 'timeLimitSec': 0, 'remainingSec': 0, 'elapsedSec': 5, 'answered': 2}]))
        page2.reload(); home_ready(page2)
        rows = page2.locator('.save-row')
        check('저장본 2개 표시', rows.count() == 2)
        rows.nth(0).get_by_role('button', name='이어서 풀기').click()   # 첫 번째 = 유령
        page2.wait_for_selector('.toast.bad')
        check('없는 문항뿐인 저장본: 오류 토스트 + 홈 유지', '찾을 수 없어' in page2.locator('.toast.bad').inner_text() and page2.locator('#screen-home').is_visible())
        rows.nth(1).get_by_role('button', name='이어서 풀기').click()
        page2.wait_for_selector('#screen-exam:not([hidden]) .q-card')
        check('일부만 남은 저장본: 1문항으로 복원 + 답안 유지', progress_text(page2).startswith('1 / 1') and page2.locator('.answer-wrap .answer-input').first.input_value() == 'zz', progress_text(page2))
        page2.close()

        # 콘솔 오류 (외부 CDN 차단에 따른 것은 제외)
        real = [e for e in errors if not re.search(r'ERR_|Failed to load resource|cdnjs|net::|blocked', e)]
        check('콘솔/페이지 오류 없음', len(real) == 0, real[:3])

        # ---------- 모바일 390px ----------
        mctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2)
        m = mctx.new_page()
        m.on('pageerror', lambda e: errors.append('PAGEERROR(m): ' + str(e)))
        m.goto(URL); home_ready(m)
        m.evaluate("(v) => localStorage.setItem('jcb_cbt_saves_v1', v)", json.dumps([
            {'id': 'a', 'ts': 1760000000000, 'sourceLabel': '2023년 1회, 2023년 2회, 2023년 3회 · 전체 언어', 'mode': 'exam', 'ids': [first_id] * 3, 'idx': 1,
             'answers': {}, 'selfMarks': {}, 'revealed': {}, 'flagged': {}, 'timeLimitSec': 2700, 'remainingSec': 2500, 'elapsedSec': 200, 'answered': 1}]))
        m.reload(); home_ready(m)
        sw = m.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
        check('모바일 홈: 가로 스크롤 없음', sw[0] <= sw[1], sw)
        m.locator('.save-row').scroll_into_view_if_needed()
        m.screenshot(path=f'{SP}/save_{TAG}_mobile_home.png')
        rowbox = m.evaluate("() => { const r = document.querySelector('.save-row').getBoundingClientRect(); return [r.left, r.right]; }")
        check('모바일: 저장행이 화면 안에 들어옴', rowbox[0] >= 0 and rowbox[1] <= 390, rowbox)
        m.locator('button.round-chip[aria-label="2023년 1회"]').click()
        m.locator('#screen-home .seg button', has_text='45분').click()
        start(m)
        m.wait_for_selector('#exam-timer')
        boxes = m.evaluate("""() => ['#exam-timer', '#btn-save', '.exam-top-right .btn-sm:nth-of-type(2)', '.exit-btn'].map(s => { const e = document.querySelector(s); if(!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })""")
        right_edge = max(b[1] for b in boxes if b)
        check('모바일 시험 상단: 모든 버튼이 화면 안(≤390)', right_edge <= 390 and all(b for b in boxes), boxes)
        ordered = sorted([b for b in boxes if b], key=lambda b: b[0])
        no_overlap = all(ordered[i][1] <= ordered[i + 1][0] + 0.5 for i in range(len(ordered) - 1))
        check('모바일 시험 상단: 버튼끼리 겹치지 않음', no_overlap, ordered)
        ch = m.evaluate("() => document.querySelector('.exam-top-left .chip').getBoundingClientRect().height")
        check('모바일 시험 상단: 회차 칩이 한 줄(높이<30)', ch < 30, ch)
        pt = m.evaluate("() => { const e = document.querySelector('#exam-progress-text'); const r = e.getBoundingClientRect(); return [r.right, e.scrollWidth, e.clientWidth]; }")
        check('모바일 시험 상단: 진행 문구가 잘리지 않음', pt[0] <= 390 and pt[1] <= pt[2] + 1, pt)
        sw = m.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
        check('모바일 시험 화면: 가로 스크롤 없음', sw[0] <= sw[1], sw)
        m.screenshot(path=f'{SP}/save_{TAG}_mobile_exam.png')
        m.locator('.exit-btn').click()
        m.wait_for_selector('#active-modal')
        mb = m.evaluate("() => [...document.querySelectorAll('#active-modal .modal-actions button')].map(b => { const r = b.getBoundingClientRect(); return [r.left, r.right]; })")
        check('모바일 나가기 모달: 버튼 3개가 모두 화면 안', len(mb) == 3 and all(x[0] >= 0 and x[1] <= 390 for x in mb), mb)
        m.screenshot(path=f'{SP}/save_{TAG}_mobile_exit_modal.png')
        browser.close()

    print('\n== %s: PASS %d / FAIL %d ==' % (TAG, len(PASS), len(FAIL)))
    if FAIL:
        print('FAILED:', FAIL)
        sys.exit(1)

main()
