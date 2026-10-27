# -*- coding: utf-8 -*-
"""정처기 CBT: 기기 간 동기화(가짜 개인 저장소) + 학습 모드 메모패드 테스트.
usage: test_sync_memo.py URL TAG        (URL = http://localhost:9881/index.html | file:///.../jcb_cbt.html)
서버는 mockdb_server.py 가 9881 에서 떠 있어야 한다.
"""
import os
import sys, json, time, re, urllib.request
from playwright.sync_api import sync_playwright

URL, TAG = sys.argv[1], sys.argv[2]
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_out')   # 스크린샷 등 시험 산출물
os.makedirs(SP, exist_ok=True)
DB = 'http://localhost:9881/__db/'
PASS, FAIL = [], []
errors = []


def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + str(extra)) if extra != '' else ''))


def dump():
    return json.load(urllib.request.urlopen(DB + 'dump'))


def reset():
    urllib.request.urlopen(urllib.request.Request(DB + 'reset', method='POST', data=b'{}'))


def put_doc(path, data):
    urllib.request.urlopen(urllib.request.Request(DB + 'doc?path=' + urllib.parse.quote(path, safe=''), method='PUT',
                                                  data=json.dumps(data).encode('utf-8'), headers={'content-type': 'application/json'}))


import urllib.parse


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


def ls(page, key):
    return page.evaluate("(k) => localStorage.getItem(k)", key)


def ls_json(page, key, default=None):
    v = ls(page, key)
    return json.loads(v) if v else default


def new_device(browser, uid='u_test1', cfg=None, seed=None, viewport=None, mock=True):
    ctx = browser.new_context(viewport=viewport or {'width': 1280, 'height': 1000})
    if mock:
        c = {'uid': uid}
        c.update(cfg or {})
        ctx.add_init_script("window.__MOCK_CFG = %s;" % json.dumps(c))
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


def sync_state(page):
    return page.locator('#sync-bar').get_attribute('data-state')


def wait_on(page, timeout=6):
    return wait_until(lambda: sync_state(page) == 'on', timeout)


def set_seg(page, label):
    page.locator('#screen-home .seg button', has_text=label).click()


def start_study(page, rounds=('2023년 1회',), mode='학습 모드'):
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


def memo_open(page):
    if page.locator('#memo-panel').is_hidden():
        page.locator('#btn-memo').click()
    page.wait_for_selector('#memo-panel:not([hidden])')


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


def blur_memo(page):
    page.evaluate("() => document.getElementById('memo-editor').blur()")


def server_memos():
    return {p.split('/')[-1]: d for p, d in dump()['docs'].items() if '/memo_' in p}


def goto_home_from_exam(page):
    page.locator('.exam-top .exit-btn').click()
    page.locator('#active-modal').get_by_role('button', name='저장 없이 종료', exact=True).click()
    page.wait_for_selector('#screen-home:not([hidden]) .start-bar')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        reset()

        # =================================================================
        # 1. 연결 · 상태 줄
        # =================================================================
        ctxA, A = new_device(browser)
        ctxB, B = new_device(browser)
        check('A 동기화 켜짐', wait_on(A), A.locator('#sync-bar').inner_text())
        check('B 동기화 켜짐', wait_on(B), B.locator('#sync-bar').inner_text())
        check('상태 줄 문구', '켜짐' in A.locator('#sync-bar .sync-text').inner_text() and '다른 기기와 공유' in A.locator('#sync-bar .sync-text').inner_text())
        meta = ls_json(A, 'jcb_cbt_sync_v1', {})
        check('장부에 계정·병합 기록', meta.get('uid') == 'u_test1' and meta.get('merged') is True and meta.get('pending') == {}, meta)
        check('빈 기록 안내(동기화 켜짐)', '다른 기기와 공유됩니다' in A.locator('#screen-home .empty-note').inner_text())

        # =================================================================
        # 2. 메모패드 — 열기·배치
        # =================================================================
        start_study(A)
        check('학습 모드: 메모 버튼 있음', A.locator('#btn-memo').count() == 1)
        check('처음엔 메모패드가 닫혀 있음', A.locator('#memo-panel').is_hidden())
        memo_open(A)
        check('열면 nav-col 에 with-memo', 'with-memo' in (A.locator('.exam-nav-col').get_attribute('class') or ''))
        rm = A.locator('#exam-main').bounding_box()
        rp = A.locator('#memo-panel').bounding_box()
        rn = A.locator('.navpanel').bounding_box()
        check('메모패드는 문제 카드 오른쪽 옆', rp['x'] >= rm['x'] + rm['width'] - 1, (rm, rp))
        check('메모패드는 화면 안에 있음', rp['x'] + rp['width'] <= 1280 and rp['y'] + rp['height'] <= 1000, rp)
        check('문항 이동판 아래', rp['y'] >= rn['y'] + rn['height'] - 1, (rn, rp))
        check('가로 스크롤 없음(넓은 화면)', A.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth"))
        check('메모 버튼 눌림 표시', A.locator('#btn-memo').get_attribute('aria-pressed') == 'true')
        check('글자 수 한도 20000(표시)', A.locator('#memo-count').inner_text().endswith('/ 20000자'), A.locator('#memo-count').inner_text())
        check('안내문(placeholder)', '문항마다 따로' in (A.locator('#memo-ph').text_content() or ''))
        # 스크롤해도 따라온다
        A.evaluate("() => window.scrollTo(0, 400)")
        time.sleep(0.2)
        rp2 = A.locator('#memo-panel').bounding_box()
        check('스크롤해도 메모패드가 화면에 보임(sticky)', rp2['y'] >= 0 and rp2['y'] < 400, rp2)
        A.evaluate("() => window.scrollTo(0, 0)")

        # =================================================================
        # 3. 메모 입력 → 저장 → 다른 기기
        # =================================================================
        txt = 'FIFO 큐 정리\n- 먼저 들어온 것이 먼저 나간다\n두 번째 줄'
        A.locator('#memo-editor').fill(txt)
        check('입력 중 표시', '입력 중' in A.locator('#memo-state').inner_text())
        check('글자 수 표시', A.locator('#memo-count').inner_text().startswith(str(len(txt)) + ' /'), A.locator('#memo-count').inner_text())
        check('메모 버튼에 ● 표시', A.locator('#btn-memo').inner_text().strip().endswith('●'), A.locator('#btn-memo').inner_text())
        ok = wait_until(lambda: len(server_memos()) == 1, 4)
        sm = server_memos()
        qid = list(sm.keys())[0].replace('memo_', '') if sm else None
        check('서버에 memo 문서 1개', ok and qid is not None, sm)
        check('서버 문서 내용', sm and list(sm.values())[0].get('t') == txt and list(sm.values())[0].get('qid') == qid, sm)
        paths = [pp for pp in dump()['docs'] if '/memo_' in pp]
        check('경로가 data/users/<내 id>/ 아래', paths and paths[0].startswith('data/users/u_test1/'), paths)
        lm = ls_json(A, 'jcb_cbt_memos_v1', {})
        check('localStorage 에도 저장', lm.get(qid, {}).get('t') == txt, lm)
        check('저장됨 · 동기화됨 표시', wait_until(lambda: '동기화됨' in A.locator('#memo-state').inner_text(), 3), A.locator('#memo-state').inner_text())

        start_study(B)
        memo_open(B)
        check('B: 다른 기기의 메모가 보임', wait_until(lambda: memo_val(B) == txt, 4), memo_val(B))
        check('B: 메모 버튼 ●', B.locator('#btn-memo').inner_text().strip().endswith('●'))

        # B 에서 고치면 A 로
        B.locator('#memo-editor').fill(txt + '\nB 에서 덧붙임')
        blur_memo(B)
        A.evaluate("() => document.activeElement && document.activeElement.blur()")
        check('A: B 의 수정이 반영됨', wait_until(lambda: memo_val(A) == txt + '\nB 에서 덧붙임', 5), memo_val(A))
        lmA = ls_json(A, 'jcb_cbt_memos_v1', {})
        check('A localStorage 도 갱신', lmA.get(qid, {}).get('t', '').endswith('B 에서 덧붙임'))

        # 문항 옮겼다 돌아와도 유지, 다른 문항은 비어 있음
        goto_q(A, 2)
        check('Q2 메모는 비어 있음', memo_val(A) == '' and not A.locator('#btn-memo').inner_text().strip().endswith('●'))
        check('Q2 제목', 'Q2' in A.locator('#memo-title').inner_text(), A.locator('#memo-title').inner_text())
        A.locator('#memo-editor').fill('Q2 메모')
        goto_q(A, 1)       # 옮기는 순간 저장되어야 한다(0.6초 전이어도)
        check('Q1 로 돌아오면 Q1 메모', memo_val(A).startswith('FIFO'), memo_val(A))
        lm2 = ls_json(A, 'jcb_cbt_memos_v1', {})
        check('옮기는 순간 Q2 메모가 저장됨', any(v.get('t') == 'Q2 메모' for v in lm2.values()), lm2)
        check('서버에도 Q2 메모', wait_until(lambda: any(d.get('t') == 'Q2 메모' for d in server_memos().values()), 4))

        # 방향키는 문항 이동으로 새지 않는다
        A.locator('#memo-editor').click()
        A.keyboard.press('ArrowRight'); A.keyboard.press('ArrowLeft')
        check('메모 글상자에서 방향키는 문항을 옮기지 않음', A.locator('.q-num').inner_text() == 'Q1')

        # 지우기
        A.locator('#memo-clear').click()
        check('지우기 확인창', A.locator('#active-modal').count() == 1 and '메모를 지울까요' in A.locator('#active-modal h3').inner_text())
        check('확인창 안내(동기화)', '다른 기기의 같은 메모도' in A.locator('#active-modal p').inner_text())
        A.locator('#active-modal').get_by_role('button', name='지우기', exact=True).click()
        check('지운 뒤 글상자가 비어 있음', memo_val(A) == '')
        check('서버에서 Q1 메모 문서가 사라짐', wait_until(lambda: ('memo_' + qid) not in server_memos(), 4), list(server_memos().keys()))
        check('B: Q1 메모도 지워짐(localStorage)', wait_until(lambda: qid not in ls_json(B, 'jcb_cbt_memos_v1', {}), 5), ls_json(B, 'jcb_cbt_memos_v1', {}))
        check('B: 열려 있는 글상자도 비워짐', wait_until(lambda: memo_val(B) == '', 5), memo_val(B))

        # 닫기·다시 열기, 설정 기억
        A.locator('#memo-panel .memo-x').click()
        check('× 로 닫힘', A.locator('#memo-panel').is_hidden() and 'with-memo' not in (A.locator('.exam-nav-col').get_attribute('class') or ''))
        check('열림 상태 기억(localStorage)', ls(A, 'jcb_cbt_memoopen_v1') == '0')
        A.locator('#btn-memo').click()
        check('다시 열림', A.locator('#memo-panel').is_visible() and ls(A, 'jcb_cbt_memoopen_v1') == '1')
        # 닫으면 답안 칸에 커서가 돌아온다(자동 포커스 유지)
        A.locator('#btn-memo').click()
        check('닫으면 답안 칸에 포커스', A.evaluate("() => document.activeElement && document.activeElement.classList.contains('answer-input')"))

        # =================================================================
        # 4. 언어 판이 있는 문항: 같은 문항이면 같은 메모
        # =================================================================
        goto_q(A, 14)
        memo_open(A)
        check('Q14 는 언어 탭이 있음', A.locator('.ver-tab').count() >= 2)
        A.locator('#memo-editor').fill('버블 정렬 메모')
        blur_memo(A)
        tabs = A.locator('.ver-tab')
        n_tabs = tabs.count()
        for i in range(n_tabs):
            if 'on' not in (tabs.nth(i).get_attribute('class') or ''):
                tabs.nth(i).click()
                break
        check('다른 언어 탭으로 바꿔도 같은 메모', memo_val(A) == '버블 정렬 메모', memo_val(A))

        # =================================================================
        # 5. 실전 모드에는 메모패드가 없다
        # =================================================================
        goto_home_from_exam(A)
        start_study(A, rounds=(), mode='실전 모드')
        check('실전 모드: 메모 버튼·패널 없음', A.locator('#btn-memo').count() == 0 and A.locator('#memo-panel').count() == 0)
        check('실전 모드: 레이아웃 클래스 없음', 'memo-open' not in (A.evaluate("() => document.documentElement.className") or ''))
        goto_home_from_exam(A)

        # =================================================================
        # 6. 중간 저장 · 연습 기록 공유
        # =================================================================
        reset()
        time.sleep(0.6)
        ctxC, C = new_device(browser)
        ctxD, D = new_device(browser)
        wait_on(C); wait_on(D)
        start_study(C, mode='실전 모드')
        C.locator('#screen-exam .answer-input').first.fill('답안 하나')
        C.locator('#btn-save').click()
        check('C: 저장 토스트(동기화 문구)', wait_until(lambda: '다른 기기에도 올라갑니다' in C.locator('#toast-root').inner_text(), 3), C.locator('#toast-root').inner_text())
        check('서버에 save 문서', wait_until(lambda: any('/save_' in pp for pp in dump()['docs']), 4), list(dump()['docs'].keys()))
        check('D: 홈에 이어서 풀기 구역이 나타남(재그림)', wait_until(lambda: D.locator('#save-section .save-row').count() == 1, 5))
        check('D: 저장본 안내문(공유)', '다른 기기와 공유됩니다' in D.locator('#save-section .save-note').inner_text())
        D.locator('#save-section .save-row .btn-primary').click()
        D.wait_for_selector('#screen-exam:not([hidden]) .q-card')
        check('D: 이어 풀기 — 답안 복원', D.locator('#screen-exam .answer-input').first.input_value() == '답안 하나')
        # D 에서 제출
        D.locator('.exam-top-right .btn-sm', has_text='제출').click()
        D.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click()
        D.wait_for_selector('#screen-result:not([hidden])')
        check('서버: save 문서 삭제 + hist 문서 생성', wait_until(lambda: not any('/save_' in pp for pp in dump()['docs']) and any('/hist_' in pp for pp in dump()['docs']), 5), list(dump()['docs'].keys()))
        # C 는 아직 시험 화면 — 홈으로 나가서 확인
        goto_home_from_exam(C)
        check('C: 저장본이 지워져 있음', wait_until(lambda: C.locator('#save-section').count() == 0, 5) and not ls_json(C, 'jcb_cbt_saves_v1', []), ls_json(C, 'jcb_cbt_saves_v1', []))
        check('C: D 의 제출 기록이 보임', wait_until(lambda: C.locator('.history-row').count() == 1, 5))
        check('C: 기록 행 내용', '2023년' in C.locator('.history-row').first.inner_text() or '학습' in C.locator('.history-row').first.inner_text() or '실전' in C.locator('.history-row').first.inner_text(), C.locator('.history-row').first.inner_text())
        C.locator('.history-row').first.click()
        check('C: 다른 기기 기록을 열어 볼 수 있음', C.locator('#screen-result:not([hidden])').count() == 1)
        C.locator('.app-header').click()
        C.wait_for_selector('#screen-home:not([hidden]) .start-bar')

        # =================================================================
        # 7. 처음 합칠 때: 이 기기에만 있던 것은 올리고, 서버 것이 더 새로우면 받는다 (덜 온 목록으로는 덮지 않는다)
        # =================================================================
        reset()
        put_doc('data/users/u_test1/memo_2023-1-1', {'qid': '2023-1-1', 't': 'SERVER NEW', 'ts': int(time.time() * 1000) - 3600000})
        put_doc('data/users/u_test1/hist_1700000000001', {'ts': 1700000000001, 'sourceLabel': '서버 기록', 'total': 5, 'examCount': 5, 'examCorrect': 5, 'scorePct': 100, 'selfCount': 0, 'mode': 'exam', 'elapsedSec': 10, 'results': []})
        seed = {
            'jcb_cbt_memos_v1': {'2023-1-1': {'t': 'LOCAL OLD', 'ts': 1000}, '2023-1-3': {'t': '로컬에만 있는 메모', 'ts': 5000}},
            'jcb_cbt_history_v1': [{'ts': 1700000000000, 'sourceLabel': '로컬 기록', 'total': 3, 'examCount': 3, 'examCorrect': 1, 'scorePct': 33, 'selfCount': 0, 'mode': 'exam', 'elapsedSec': 5, 'results': []}],
            'jcb_cbt_saves_v1': [{'id': 'sLOCAL1', 'ts': 1700000000500, 'sourceLabel': '로컬 저장', 'mode': 'exam', 'ids': ['2023-1-1', '2023-1-2'], 'idx': 0, 'answers': {}, 'selfMarks': {}, 'revealed': {}, 'flagged': {}, 'timeLimitSec': 0, 'remainingSec': 0, 'elapsedSec': 3, 'answered': 0}],
        }
        ctxE, E = new_device(browser, seed=seed)
        check('E: 켜짐', wait_on(E))
        time.sleep(0.8)
        sm = {p: d for p, d in dump()['docs'].items()}
        check('서버 메모가 더 새로워 로컬 것으로 덮이지 않음', sm.get('data/users/u_test1/memo_2023-1-1', {}).get('t') == 'SERVER NEW', sm.get('data/users/u_test1/memo_2023-1-1'))
        check('E: 로컬 메모가 서버 것으로 갱신', ls_json(E, 'jcb_cbt_memos_v1', {}).get('2023-1-1', {}).get('t') == 'SERVER NEW')
        check('로컬에만 있던 메모는 서버로 올라감', sm.get('data/users/u_test1/memo_2023-1-3', {}).get('t') == '로컬에만 있는 메모')
        check('로컬에만 있던 기록은 서버로 올라감', 'data/users/u_test1/hist_1700000000000' in sm)
        check('로컬에만 있던 저장본은 서버로 올라감', 'data/users/u_test1/save_sLOCAL1' in sm)
        hh = ls_json(E, 'jcb_cbt_history_v1', [])
        check('E: 기록은 서버 것 + 로컬 것(최신순)', [h['ts'] for h in hh] == [1700000000001, 1700000000000], [h['ts'] for h in hh])
        check('E: 홈에 합쳐진 기록 2행', wait_until(lambda: E.locator('.history-row').count() == 2, 4), E.locator('.history-row').count())
        check('E: 홈에 저장본 1행', E.locator('#save-section .save-row').count() == 1)
        meta = ls_json(E, 'jcb_cbt_sync_v1', {})
        check('E: 합친 뒤 장부 비어 있음', meta.get('merged') is True and wait_until(lambda: ls_json(E, 'jcb_cbt_sync_v1', {}).get('pending') == {}, 4), meta)

        # 합친 뒤에는 다른 기기의 삭제가 전파된다
        ctxF, F = new_device(browser)
        wait_on(F)
        check('F: 합쳐진 저장본이 보임', wait_until(lambda: F.locator('#save-section .save-row').count() == 1, 4))
        F.locator('#save-section .save-row .btn', has_text='삭제').click()
        F.locator('#active-modal').get_by_role('button', name='삭제', exact=True).click()
        check('서버: 저장본 삭제됨', wait_until(lambda: 'data/users/u_test1/save_sLOCAL1' not in dump()['docs'], 4))
        check('E: 삭제가 전파됨(로컬 저장본 0)', wait_until(lambda: not ls_json(E, 'jcb_cbt_saves_v1', []), 5))
        check('E: 홈에서 저장 구역이 사라짐', wait_until(lambda: E.locator('#save-section').count() == 0, 4))

        # =================================================================
        # 8. 끊김 → 대기열 → 다시 올림
        # =================================================================
        E.evaluate("() => { window.__MOCK_CFG.offline = true; }")
        start_study(E, rounds=('2023년 1회',), mode='학습 모드')
        memo_open(E)
        E.locator('#memo-editor').fill('오프라인에서 쓴 메모')
        blur_memo(E)
        time.sleep(1.0)
        mt = ls_json(E, 'jcb_cbt_memos_v1', {})
        check('오프라인: 로컬에는 저장됨', any(v.get('t') == '오프라인에서 쓴 메모' for v in mt.values()))
        pend = ls_json(E, 'jcb_cbt_sync_v1', {}).get('pending', {})
        check('오프라인: 장부에 올릴 일이 남음', any(k.startswith('memo_') for k in pend), pend)
        check('오프라인: 서버엔 아직 없음', not any(d.get('t') == '오프라인에서 쓴 메모' for d in server_memos().values()))
        check('오프라인: 메모 상태 문구', '연결되면' in E.locator('#memo-state').inner_text() or '올리는 중' in E.locator('#memo-state').inner_text(), E.locator('#memo-state').inner_text())
        E.evaluate("() => { window.__MOCK_CFG.offline = false; window.dispatchEvent(new Event('online')); }")
        check('복구 후 서버에 올라감', wait_until(lambda: any(d.get('t') == '오프라인에서 쓴 메모' for d in server_memos().values()), 8), list(server_memos().values()))
        check('장부가 비워짐', wait_until(lambda: not any(k.startswith('memo_') for k in ls_json(E, 'jcb_cbt_sync_v1', {}).get('pending', {})), 5))

        # =================================================================
        # 9. 같은 문서에 쓰기가 겹치지 않는다 / 마지막 글이 남는다
        # =================================================================
        reset(); time.sleep(0.5)
        ctxG, G = new_device(browser)
        wait_on(G)
        start_study(G); memo_open(G)
        for i in range(6):
            G.locator('#memo-editor').fill('빠른 입력 %d' % i)
            blur_memo(G)
            G.locator('#memo-editor').focus()
        G.locator('#memo-editor').fill('마지막 글')
        blur_memo(G)
        ok = wait_until(lambda: any(d.get('t') == '마지막 글' for d in server_memos().values()), 6)
        time.sleep(0.6)
        check('겹친 쓰기 0건', dump()['violations'] == [], dump()['violations'])
        check('서버에는 마지막 글만 남음', ok and [d.get('t') for d in server_memos().values()] == ['마지막 글'], [d.get('t') for d in server_memos().values()])
        check('모든 쓰기가 내 경로', all(pp.startswith('data/users/u_test1/') for op, pp in dump()['log']), dump()['log'][:5])

        # =================================================================
        # 10. 읽기 전용 · 로그인 안 됨 · 기능 없음
        # =================================================================
        reset()
        ctxH, H = new_device(browser, cfg={'readonly': True})
        check('읽기 전용: 상태', wait_until(lambda: sync_state(H) in ('on', 'readonly'), 5))
        start_study(H); memo_open(H)
        H.locator('#memo-editor').fill('읽기 전용 기기의 메모'); blur_memo(H)
        check('읽기 전용: 쓰기 거절 뒤 readonly 표시', wait_until(lambda: sync_state(H) == 'readonly', 5), sync_state(H))
        check('읽기 전용: 그래도 로컬 저장은 됨', any(v.get('t') == '읽기 전용 기기의 메모' for v in ls_json(H, 'jcb_cbt_memos_v1', {}).values()))
        goto_home_from_exam(H)
        check('읽기 전용: 안내 문구', '쓸 권한' in H.locator('#sync-bar .sync-text').inner_text(), H.locator('#sync-bar .sync-text').inner_text())

        ctxI, I = new_device(browser, cfg={'noUser': True})
        check('로그인 안 됨: 꺼짐', wait_until(lambda: sync_state(I) == 'off', 4) and '로그인' in I.locator('#sync-bar .sync-text').inner_text(), I.locator('#sync-bar .sync-text').inner_text())
        check('로그인 안 됨: 안내문은 예전 문구', '이 브라우저에만 저장되며' in I.locator('.empty-note').inner_text())
        ctxJ, J = new_device(browser, cfg={'noDb': True})
        check('db 없음: 꺼짐', wait_until(lambda: sync_state(J) == 'off', 4))

        ctxK, K = new_device(browser, mock=False)
        check('claude 없음(저장 파일 등): 꺼짐 + 이유', sync_state(K) == 'off' and '이 화면에서는 쓸 수 없어' in K.locator('#sync-bar .sync-text').inner_text(), K.locator('#sync-bar .sync-text').inner_text())
        start_study(K); memo_open(K)
        K.locator('#memo-editor').fill('로컬 전용 메모'); blur_memo(K)
        K.reload(); K.wait_for_selector('#screen-home:not([hidden]) .start-bar')
        check('claude 없음: 장부에 아무것도 쌓지 않음', (ls_json(K, 'jcb_cbt_sync_v1', {}) or {}).get('pending', {}) == {})
        start_study(K); memo_open(K)
        check('claude 없음: 새로고침 뒤에도 메모 유지', memo_val(K) == '로컬 전용 메모', memo_val(K))
        check('claude 없음: 상태 문구', '이 브라우저에만' in K.locator('#memo-state').inner_text(), K.locator('#memo-state').inner_text())

        # =================================================================
        # 11. 좁은 화면(폰): 아래에서 올라오는 창
        # =================================================================
        reset()
        ctxL, L = new_device(browser, viewport={'width': 390, 'height': 844})
        start_study(L)
        L.locator('#btn-memo').click()
        L.wait_for_selector('#memo-panel:not([hidden])')
        r = L.locator('#memo-panel').bounding_box()
        check('폰: 메모창이 화면 아래쪽에 붙음', abs((r['y'] + r['height']) - 844) <= 1 and r['x'] <= 1 and abs(r['width'] - 390) <= 2, r)
        check('폰: 높이는 화면의 64%(최대 560px) 이하 — 서식 도구줄이 생겨 예전 46% 에서 키움', r['height'] <= min(844 * 0.64, 560) + 2, r['height'])
        check('폰: 가로 스크롤 없음', L.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth"))
        check('폰: position fixed', L.evaluate("() => getComputedStyle(document.getElementById('memo-panel')).position") == 'fixed')
        check('폰: html.memo-open', 'memo-open' in L.evaluate("() => document.documentElement.className"))
        tb = L.locator('.exam-top').bounding_box()
        check('폰: 상단 도구줄은 가려지지 않음', tb['y'] < 200 and tb['y'] + tb['height'] < r['y'], (tb, r))
        L.locator('#memo-editor').fill('폰에서 쓴 메모')
        blur_memo(L)
        L.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")      # 끝까지 내리면 아래 여백(창 높이만큼) 덕에 다음 버튼이 창 위로 올라온다
        L.wait_for_timeout(250)
        fb = L.locator('.q-footer .btn-primary').bounding_box()
        check('폰: 다음 버튼이 메모창 위로 스크롤돼 눌림', fb['y'] + fb['height'] <= r['y'] + 1, (fb, r))
        btns = [L.locator(s).bounding_box() for s in ('#btn-memo', '#btn-save')]
        check('폰: 메모·저장 버튼이 겹치지 않음', btns[0]['x'] + btns[0]['width'] <= btns[1]['x'] + 1 or btns[1]['x'] + btns[1]['width'] <= btns[0]['x'] + 1, btns)
        L.screenshot(path=SP + '/memo_%s_phone.png' % TAG)
        L.locator('#memo-panel .memo-x').click()
        check('폰: 닫으면 아래 여백 클래스도 사라짐', 'memo-open' not in L.evaluate("() => document.documentElement.className"))
        goto_home_from_exam(L)
        check('홈으로 나오면 memo-open 없음', 'memo-open' not in L.evaluate("() => document.documentElement.className"))

        # 넓은 화면 스크린샷
        reset()
        ctxM, M = new_device(browser)
        start_study(M); memo_open(M)
        M.locator('#memo-editor').fill('스택: LIFO\n큐: FIFO\n- 둘 다 선형 자료구조')
        wait_until(lambda: len(server_memos()) == 1, 4)
        M.screenshot(path=SP + '/memo_%s_wide.png' % TAG)

        # =================================================================
        # 12. 처음 합칠 때 수십 건을 올려도 동시에 쓰는 수는 제한된다 / 같은 브라우저의 다른 탭이 올릴 일을 지우지 않는다
        # =================================================================
        reset(); time.sleep(0.5)
        big_memos = {'2023-1-%d' % i: {'t': '메모 %d' % i, 'ts': 1000 + i} for i in range(1, 41)}
        big_hist = [{'ts': 1700000000000 + i, 'sourceLabel': '기록 %d' % i, 'total': 1, 'examCount': 1, 'examCorrect': 0, 'scorePct': 0, 'selfCount': 0, 'mode': 'exam', 'elapsedSec': 1, 'results': []} for i in range(25, 0, -1)]
        ctxP, P = new_device(browser, seed={'jcb_cbt_memos_v1': big_memos, 'jcb_cbt_history_v1': big_hist})
        check('대량: 켜짐', wait_on(P))
        ok = wait_until(lambda: len([pp for pp in dump()['docs'] if '/memo_' in pp]) == 40 and len([pp for pp in dump()['docs'] if '/hist_' in pp]) == 25, 12)
        check('대량: 메모 40 + 기록 25 가 전부 올라감', ok, len(dump()['docs']))
        check('대량: 동시에 쓴 문서 수 ≤ 4', dump()['maxpar'] <= 4, dump()['maxpar'])
        check('대량: 겹친 쓰기 0건', dump()['violations'] == [], dump()['violations'])
        check('대량: 장부가 비워짐', wait_until(lambda: ls_json(P, 'jcb_cbt_sync_v1', {}).get('pending') == {}, 6))

        reset(); time.sleep(0.5)
        ctxT = browser.new_context(viewport={'width': 1280, 'height': 1000})
        ctxT.add_init_script("window.__MOCK_CFG = %s;" % json.dumps({'uid': 'u_test1'}))
        ctxT.add_init_script(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_claude.js'))
        T1 = ctxT.new_page(); T2 = ctxT.new_page()
        for pg in (T1, T2):
            pg.on('pageerror', lambda e: errors.append('PAGEERROR: ' + str(e)))
            pg.goto(URL); pg.wait_for_selector('#screen-home:not([hidden]) .start-bar')
        wait_on(T1); wait_on(T2)
        T1.evaluate("() => { window.__MOCK_CFG.offline = true; }")
        start_study(T1); memo_open(T1)
        T1.locator('#memo-editor').fill('탭1 오프라인 메모'); blur_memo(T1)
        time.sleep(0.8)
        check('탭1: 올릴 일이 장부에 남음', any(k.startswith('memo_') for k in ls_json(T1, 'jcb_cbt_sync_v1', {}).get('pending', {})))
        start_study(T2); memo_open(T2)
        goto_q(T2, 2)
        T2.locator('#memo-editor').fill('탭2 메모'); blur_memo(T2)
        ok = wait_until(lambda: {d.get('t') for d in server_memos().values()} == {'탭1 오프라인 메모', '탭2 메모'}, 8)
        check('다른 탭의 대기 중인 메모가 지워지지 않고 함께 올라감', ok, [d.get('t') for d in server_memos().values()])
        lm = ls_json(T2, 'jcb_cbt_memos_v1', {})
        check('두 메모 모두 로컬에 남아 있음', {v['t'] for v in lm.values()} == {'탭1 오프라인 메모', '탭2 메모'}, lm)

        # 같은 계정의 서로 다른 uid 는 섞이지 않는다
        for c in (ctxA, ctxB, ctxC, ctxD, ctxE, ctxF, ctxG, ctxH, ctxI, ctxJ, ctxK, ctxL, ctxM, ctxP, ctxT):
            c.close()
        time.sleep(1.5)                      # 닫는 순간 날아가던 쓰기가 서버에 닿을 시간을 준 뒤 비운다
        reset()
        ctxN, N = new_device(browser, uid='u_other')
        wait_on(N)
        start_study(N); memo_open(N)
        N.locator('#memo-editor').fill('다른 사람 메모'); blur_memo(N)
        wait_until(lambda: len(server_memos()) == 1, 4)
        ctxO, O = new_device(browser, uid='u_test1')
        wait_on(O); start_study(O); memo_open(O)
        time.sleep(1.0)
        check('다른 계정의 메모는 보이지 않음', memo_val(O) == '', memo_val(O))
        check('다른 계정 문서는 그 계정 경로에만', all(pp.startswith('data/users/u_other/') for pp in dump()['docs']), list(dump()['docs']))

        real_errors = [e for e in errors if 'Failed to load resource' not in e and 'net::ERR' not in e]
        check('콘솔/페이지 오류 없음', len(real_errors) == 0, real_errors[:5])
        browser.close()

    print('\n== %s: PASS %d / FAIL %d ==' % (TAG, len(PASS), len(FAIL)))
    if FAIL:
        print('FAILED:', FAIL)
        sys.exit(1)


main()
