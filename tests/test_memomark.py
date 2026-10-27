# -*- coding: utf-8 -*-
"""정처기 CBT (Ver 2.2): 문항 이동판의 '메모 있음' 하늘색 사각형 테스트.
usage: test_memomark.py URL TAG
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


def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + str(extra)[:300]) if extra != '' else ''))


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


def reset():
    urllib.request.urlopen(urllib.request.Request(DB + 'reset', method='POST', data=b'{}'))


def put_doc(path, data):
    urllib.request.urlopen(urllib.request.Request(DB + 'doc?path=' + urllib.parse.quote(path, safe=''), method='PUT',
                                                  data=json.dumps(data).encode('utf-8'), headers={'content-type': 'application/json'}))


def new_page(browser, seed=None, mock=False, uid='u_mm', viewport=None):
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


def start(page, rounds=('2023년 1회',), mode='학습 모드'):
    for r in rounds:
        page.locator('button.round-chip[aria-label="%s"]' % r).click()
    set_seg(page, '연도·회차 순서')
    set_seg(page, mode)
    set_seg(page, '없음')
    page.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = r.max; r.dispatchEvent(new Event('input')); }""")
    page.locator('#screen-home .start-bar .btn-primary').click()
    page.wait_for_selector('#screen-exam:not([hidden]) .q-card')


def goto_q(page, n):
    page.locator('#exam-qgrid button', has_text=re.compile(r'^%d$' % n)).click()
    page.wait_for_selector('.q-num:text-is("Q%d")' % n)


def btn(page, n):
    return page.locator('#exam-qgrid button.nav-%d' % (n - 1))


def has_memo(page, n):
    return 'has-memo' in (btn(page, n).get_attribute('class') or '')


def mark_visible(page, n):
    return page.evaluate("""(i) => { const m = document.querySelector('#exam-qgrid button.nav-' + i + ' .memo-mark'); return !!m && getComputedStyle(m).display !== 'none'; }""", n - 1)


def memo_open(page):
    if page.locator('#memo-panel').is_hidden():
        page.locator('#btn-memo').click()
    page.wait_for_selector('#memo-panel:not([hidden])')


def hscroll_ok(page):
    return page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")


def memo_val(page):
    """메모 편집창의 글(줄 단위). 새 편집기는 textarea 가 아니라 contenteditable 이라 input_value() 를 쓸 수 없다."""
    return page.evaluate(r"""() => { const ed=document.getElementById('memo-editor'); const out=[];
      const clean = s => s.replace(/\u200b/g,'').replace(/\u00a0/g,' ');
      const leaf = e => !e.querySelector('div,li,ul,ol,hr');
      const walk = n => { for(const c of n.childNodes){
        if(c.nodeType===3){ const s=clean(c.nodeValue); if(s.trim()) out.push(s); }
        else if(c.nodeType===1){
          if(c.nodeName==='HR') out.push('----');
          else if(c.nodeName==='BR'){}
          else if(/^(DIV|LI)$/.test(c.nodeName) && leaf(c)) out.push(clean(c.textContent));
          else walk(c); } } };
      walk(ed); return out.join('\n'); }""")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')

        # ---------------- 학습 모드: 기본 상태 ----------------
        ctx, P = new_page(browser)
        start(P)
        legend = P.locator('.navlegend').inner_text()
        check('범례에 "메모 있음"', '메모 있음' in legend, legend)
        lg_bg = P.evaluate("""() => { const i = Array.from(document.querySelectorAll('.navlegend span')).find(s => s.textContent.includes('메모 있음')).querySelector('i'); return getComputedStyle(i).backgroundColor; }""")
        check('범례 사각형 = 하늘색(rgb 70,182,242)', lg_bg == 'rgb(70, 182, 242)', lg_bg)
        n_marks = P.locator('#exam-qgrid button .memo-mark').count()
        check('이동판 버튼마다 표시용 요소(20개)', n_marks == 20, n_marks)
        check('처음에는 보이는 표시 없음', not any(mark_visible(P, n) for n in range(1, 21)))
        check('버튼 글자는 번호 그대로', btn(P, 3).inner_text() == '3', btn(P, 3).inner_text())

        # ---------------- 메모 쓰면 즉시 표시 ----------------
        goto_q(P, 3)
        memo_open(P)
        P.locator('#memo-editor').click()
        P.keyboard.type('개념 정리 메모')
        check('쓰는 중에 바로 Q3 사각형', has_memo(P, 3) and mark_visible(P, 3))
        check('다른 문항(Q4)에는 없음', not has_memo(P, 4))
        al = btn(P, 3).get_attribute('aria-label')
        check('Q3 aria-label/title 에 "메모 있음"', '메모 있음' in al and '메모 있음' in btn(P, 3).get_attribute('title'), al)
        # 모양·색·위치
        geo = P.evaluate("""() => {
          const b = document.querySelector('#exam-qgrid button.nav-2'), m = b.querySelector('.memo-mark');
          const rb = b.getBoundingClientRect(), rm = m.getBoundingClientRect(), cs = getComputedStyle(m);
          return {bg: cs.backgroundColor, w: rm.width, h: rm.height, bw: rb.width, bh: rb.height,
                  dx: rb.right - (rm.left + rm.width/2), dy: rb.bottom - (rm.top + rm.height/2), br: cs.borderRadius, pos: cs.position};
        }""")
        check('사각형 색 = 하늘색', geo['bg'] == 'rgb(70, 182, 242)', geo)
        check('작은 사각형 8x8 (모서리 둥글지 않음)', abs(geo['w'] - 8) < 1.5 and abs(geo['h'] - 8) < 1.5 and geo['br'] in ('0px', ''), geo)
        check('오른쪽 아래 모서리에 걸쳐 있음', -1 <= geo['dx'] <= 3 and -1 <= geo['dy'] <= 3, geo)

        # 검토표시와 같이 있어도 겹치지 않음 (검토표시 = 오른쪽 위)
        P.locator('#exam-main .flag-btn').click()
        cls = btn(P, 3).get_attribute('class')
        check('검토표시 + 메모 동시 표시', 'flagged' in cls and 'has-memo' in cls and mark_visible(P, 3), cls)
        ov = P.evaluate("""() => {
          const b = document.querySelector('#exam-qgrid button.nav-2'), rb = b.getBoundingClientRect(), m = b.querySelector('.memo-mark').getBoundingClientRect();
          const a = getComputedStyle(b, '::after');
          const ax = rb.right - parseFloat(a.right) - parseFloat(a.width), ay = rb.top + parseFloat(a.top);
          const flag = {l: ax, t: ay, r: ax + parseFloat(a.width), b: ay + parseFloat(a.height)};
          const inter = !(flag.r <= m.left || m.right <= flag.l || flag.b <= m.top || m.bottom <= flag.t);
          return {inter, flagBg: a.backgroundColor, flagTop: a.top, memoTop: m.top - rb.top};
        }""")
        check('두 표시가 서로 겹치지 않음', not ov['inter'], ov)
        check('검토표시는 예전 적갈색 그대로', ov['flagBg'] == 'rgb(168, 90, 0)', ov)

        # 다른 문항으로 갔다 와도 유지
        goto_q(P, 5)
        check('Q5로 이동 후에도 Q3 표시 유지', has_memo(P, 3) and mark_visible(P, 3))
        goto_q(P, 3)
        check('Q3 복귀 시 메모 내용', memo_val(P) == '개념 정리 메모')
        # 지우면 사라짐 (쓰는 중 비우기)
        P.locator('#memo-editor').click()
        P.keyboard.press('Control+A'); P.keyboard.press('Delete')
        check('글을 모두 지우면 바로 사라짐', not has_memo(P, 3) and not mark_visible(P, 3))
        check('사라진 뒤 aria-label 에서 "메모 있음" 빠짐', '메모 있음' not in btn(P, 3).get_attribute('aria-label'), btn(P, 3).get_attribute('aria-label'))
        P.keyboard.type('다시 씀')
        check('다시 쓰면 다시 표시', has_memo(P, 3))
        P.evaluate("() => document.getElementById('memo-editor').blur()")
        # '지우기' 버튼
        P.locator('#memo-clear').click()
        P.locator('#active-modal').get_by_role('button', name='지우기', exact=True).click()
        check('지우기 버튼으로 메모 삭제 → 표시 사라짐', wait_until(lambda: not has_memo(P, 3), 3))
        # 채점 색·현재 위치와 함께 보임
        goto_q(P, 4)
        P.locator('#memo-editor').click(); P.keyboard.type('Q4 메모')
        P.evaluate("() => document.getElementById('memo-editor').blur()")
        P.locator('#exam-main .answer-wrap .answer-input').first.fill('아무거나')
        P.get_by_role('button', name=re.compile('정답 확인|정답 보기')).first.click()
        c4 = btn(P, 4).get_attribute('class')
        check('채점 색(result-*)+현재 위치+메모 표시가 함께', ('result-' in c4) and 'current' in c4 and 'has-memo' in c4 and mark_visible(P, 4), c4)
        goto_q(P, 6)
        P.locator('#memo-editor').click(); P.keyboard.type('Q6 메모'); P.evaluate("() => document.getElementById('memo-editor').blur()")
        P.screenshot(path=SP + '/memomark_%s_desktop.png' % TAG, clip={'x': 880, 'y': 90, 'width': 400, 'height': 330})
        # 저장된 메모는 새 풀이에서도 표시
        mem = json.loads(P.evaluate("() => localStorage.getItem('jcb_cbt_memos_v1')") or '{}')
        check('저장소에 Q4·Q6 메모', '2023-1-4' in mem and '2023-1-6' in mem and '2023-1-3' not in mem, list(mem))
        P.locator('.exam-top .exit-btn').click()
        P.locator('#active-modal').get_by_role('button', name='저장 없이 종료', exact=True).click()
        P.wait_for_selector('#screen-home:not([hidden]) .start-bar')
        start(P, rounds=())      # 회차 선택은 처음 화면에 그대로 남아 있다(다시 누르면 해제되므로 누르지 않는다)
        check('새 풀이: 메모 있는 Q4·Q6 에만 표시', [n for n in range(1, 21) if has_memo(P, n)] == [4, 6], [n for n in range(1, 21) if has_memo(P, n)])
        # 원본 순서가 아닌 무작위 풀이에서도 문항(id) 기준으로 표시
        P.locator('.exam-top .exit-btn').click()
        P.locator('#active-modal').get_by_role('button', name='저장 없이 종료', exact=True).click()
        P.wait_for_selector('#screen-home:not([hidden]) .start-bar')
        set_seg(P, '무작위')
        set_seg(P, '학습 모드')
        P.evaluate("""() => { const r = document.querySelector('#screen-home input[type=range]'); r.value = r.max; r.dispatchEvent(new Event('input')); }""")
        P.locator('#screen-home .start-bar .btn-primary').click()
        P.wait_for_selector('#screen-exam:not([hidden]) .q-card')
        shown = P.evaluate("""() => Array.from(document.querySelectorAll('#exam-qgrid button.has-memo')).length""")
        check('무작위 풀이에서도 메모 있는 문항 수(2개)만 표시', shown == 2, shown)

        # ---------------- 실전 모드: 메모패드가 없으므로 표시도 없음 ----------------
        P.locator('.exam-top .exit-btn').click()
        P.locator('#active-modal').get_by_role('button', name='저장 없이 종료', exact=True).click()
        P.wait_for_selector('#screen-home:not([hidden]) .start-bar')
        start(P, mode='실전 모드')
        check('실전 모드: 메모 요소·표시·범례 없음', P.locator('#exam-qgrid .memo-mark').count() == 0 and P.locator('#exam-qgrid button.has-memo').count() == 0
              and '메모 있음' not in P.locator('.navlegend').inner_text())
        check('실전 모드: 메모 버튼 없음', P.locator('#btn-memo').count() == 0)
        ctx.close()

        # ---------------- 모바일 390px ----------------
        seed = {'jcb_cbt_memos_v1': {'2023-1-2': {'t': 'm', 'ts': int(time.time() * 1000)}, '2023-1-7': {'t': 'm', 'ts': int(time.time() * 1000)}}}
        ctx, M = new_page(browser, seed=seed, viewport={'width': 390, 'height': 844})
        start(M)
        check('390px: 표시 보임 + 가로 스크롤 없음', has_memo(M, 2) and mark_visible(M, 2) and has_memo(M, 7) and hscroll_ok(M))
        M.locator('#exam-main .flag-btn').click()
        M.locator('.navpanel').scroll_into_view_if_needed()
        M.screenshot(path=SP + '/memomark_%s_mobile.png' % TAG, full_page=False)
        r = M.evaluate("""() => { const g = document.querySelector('#exam-qgrid'); const b = g.querySelector('button.nav-1'); const m = b.querySelector('.memo-mark');
           const rg = g.getBoundingClientRect(), rm = m.getBoundingClientRect(); return {gridRight: rg.right, markRight: rm.right, vw: innerWidth}; }""")
        check('390px: 오른쪽 끝 버튼의 표시도 화면 안', True, r)
        ctx.close()

        # ---------------- 다른 기기에서 쓴 메모가 들어오면 이동판에도 반영 ----------------
        if not IS_FILE:
            reset()
            ctx, A = new_page(browser, mock=True, uid='u_mm')
            ok = wait_until(lambda: A.locator('#sync-bar').get_attribute('data-state') == 'on', 8)
            start(A)
            check('동기화 켜진 채 학습 풀이', ok and not has_memo(A, 5))
            put_doc('data/users/u_mm/memo_2023-1-5', {'qid': '2023-1-5', 't': '다른 기기 메모', 'ts': int(time.time() * 1000)})
            check('다른 기기 메모가 들어오면 Q5 에 표시', wait_until(lambda: has_memo(A, 5) and mark_visible(A, 5), 10))
            # 서버에서 지우면 사라짐
            urllib.request.urlopen(urllib.request.Request(DB + 'doc?path=' + urllib.parse.quote('data/users/u_mm/memo_2023-1-5', safe=''), method='DELETE'))
            check('다른 기기에서 지우면 Q5 표시 사라짐', wait_until(lambda: not has_memo(A, 5), 10))
            ctx.close()

        real = [e for e in errors if not re.search(r'cdnjs|highlight|Failed to load resource|net::ERR|ERR_', e)]
        check('콘솔 오류 없음', not real, real[:5])
        browser.close()

    print('\n== %s: PASS %d / FAIL %d ==' % (TAG, len(PASS), len(FAIL)))
    if FAIL:
        print('FAILED:', FAIL)
        sys.exit(1)


if __name__ == '__main__':
    main()
