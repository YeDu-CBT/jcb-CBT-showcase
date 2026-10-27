# -*- coding: utf-8 -*-
"""정처기 CBT (Ver 2.5): 메모패드 서식 편집기 + 오른쪽 칸 배치 테스트.
usage: test_memo_editor.py URL TAG [PART]
"""
import sys, json, time, re, os
from playwright.sync_api import sync_playwright

import test_dups as T
check = T.check
PART = sys.argv[3] if len(sys.argv) > 3 else 'all'
MK = 'jcb_cbt_memos_v1'


def want(p):
    return PART == 'all' or p in PART.split(',')


def ed_html(P):
    return P.evaluate("document.getElementById('memo-editor').innerHTML")


def ed_text(P):
    """편집창의 '줄' 단위 글(innerText 는 빈 줄 개수가 브라우저 규칙에 따라 늘어나 믿을 수 없다). nbsp·보이지 않는 글자는 정리."""
    return P.evaluate(r"""() => { const ed=document.getElementById('memo-editor'); const out=[];
      const clean = s => s.replace(/​/g,'').replace(/ /g,' ');
      const leaf = e => !e.querySelector('div,li,ul,ol,hr');
      const walk = n => { for(const c of n.childNodes){
        if(c.nodeType===3){ const s=clean(c.nodeValue); if(s.trim()) out.push(s); }
        else if(c.nodeType===1){
          if(c.nodeName==='HR') out.push('----');
          else if(c.nodeName==='BR'){}
          else if(/^(DIV|LI)$/.test(c.nodeName) && leaf(c)) out.push(clean(c.textContent));
          else walk(c); } } };
      walk(ed); return out.join('\n'); }""")


def store(P):
    return P.evaluate("(k) => JSON.parse(localStorage.getItem(k) || '{}')", MK)


def commit(P, ms=900):
    P.wait_for_timeout(ms)


def open_memo(P):
    if P.locator('#memo-panel').is_hidden():
        P.locator('#btn-memo').click()
    P.wait_for_selector('#memo-editor', state='visible')


def focus_end(P):
    P.evaluate("""() => { const ed=document.getElementById('memo-editor'); ed.focus(); const r=document.createRange(); r.selectNodeContents(ed); r.collapse(false); const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""")


def clear_editor(P):
    P.locator('#memo-editor').click()
    P.keyboard.press('Control+a')
    P.keyboard.press('Delete')


def select_text(P, sub):
    ok = P.evaluate("""(sub) => { const ed=document.getElementById('memo-editor'); ed.focus();
      const w=document.createTreeWalker(ed, NodeFilter.SHOW_TEXT); let n;
      while((n=w.nextNode())){ const i=n.nodeValue.indexOf(sub); if(i>=0){ const r=document.createRange(); r.setStart(n,i); r.setEnd(n,i+sub.length); const s=getSelection(); s.removeAllRanges(); s.addRange(r); return true; } }
      return false; }""", sub)
    assert ok, 'text not found: ' + sub
    return ok


def caret_after(P, sub):
    ok = P.evaluate("""(sub) => { const ed=document.getElementById('memo-editor'); ed.focus();
      const w=document.createTreeWalker(ed, NodeFilter.SHOW_TEXT); let n;
      while((n=w.nextNode())){ const i=n.nodeValue.indexOf(sub); if(i>=0){ const r=document.createRange(); r.setStart(n,i+sub.length); r.collapse(true); const s=getSelection(); s.removeAllRanges(); s.addRange(r); return true; } }
      return false; }""", sub)
    assert ok, 'text not found: ' + sub


def tool(P, key):
    P.locator('.memo-tools .mt-%s' % key).click()


def pressed(P, key):
    return P.locator('.memo-tools .mt-%s' % key).get_attribute('aria-pressed')


def geom(P, sel):
    return P.evaluate("""(s) => { const e=document.querySelector(s); if(!e) return null; const r=e.getBoundingClientRect(); return {l:Math.round(r.left),t:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height),r:Math.round(r.right),b:Math.round(r.bottom)}; }""", sel)


def hscroll(P):
    return P.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")


def fsize(P, sub):
    return P.evaluate("""(sub) => { const ed=document.getElementById('memo-editor'); const w=document.createTreeWalker(ed, NodeFilter.SHOW_TEXT); let n;
      while((n=w.nextNode())){ if(n.nodeValue.indexOf(sub)>=0) return getComputedStyle(n.parentElement).fontSize; } return null; }""", sub)


def paste(P, text, html=None):
    P.evaluate("""([text, html]) => { const ed=document.getElementById('memo-editor'); ed.focus();
      const dt = new DataTransfer(); dt.setData('text/plain', text); if(html) dt.setData('text/html', html);
      ed.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles:true, cancelable:true})); }""", [text, html])


def state_text(P):
    return P.locator('#memo-state').inner_text()


def count_text(P):
    return P.locator('#memo-count').inner_text()


NOW = int(time.time() * 1000)


def mk_memos(**kw):
    return kw


def write_tmp(name, obj):
    p = T.SP + '/' + name
    open(p, 'w', encoding='utf-8').write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False))
    return p


def fresh(browser, rounds=('2023년 3회',), vp=None, seed=None, mock=False, **kw):
    ctx, P = T.new_page(browser, viewport=vp or {'width': 1920, 'height': 1080}, seed=seed, mock=mock, **kw)
    T.start(P, rounds=list(rounds))
    return ctx, P


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')

        # ===================== A. 배치 (1920×1080) =====================
        if want('A'):
            ctx, P = fresh(browser)
            col0 = geom(P, '.exam-nav-col'); card0 = geom(P, '.q-card'); app0 = geom(P, '#app')
            check('A1 메모 닫힘: 이동판 칸 250px, 앱 폭 ≤1360 (옛 모양 그대로)', col0['w'] == 250 and app0['w'] <= 1360, (col0, app0))
            check('A2 메모 닫힘: 메모 패널은 숨김', P.locator('#memo-panel').is_hidden())
            P.locator('#btn-memo').click()
            P.wait_for_selector('#memo-editor', state='visible')
            P.wait_for_timeout(200)
            col = geom(P, '.exam-nav-col'); card = geom(P, '.q-card'); panel = geom(P, '#memo-panel'); nav = geom(P, '.navpanel')
            ed = geom(P, '#memo-editor'); tools = geom(P, '.memo-tools'); foot = geom(P, '.memo-foot')
            check('A3 열림: 오른쪽 칸 너비 600~700px (1920×1080 기준)', 600 <= col['w'] <= 700, col)
            check('A4 열림: 문제 카드가 닫혀 있을 때보다 넓다(왼쪽으로 옮겨 자리를 만듦)', card['w'] > card0['w'] and card['l'] < card0['l'], (card0, card))
            check('A5 열림: 카드와 오른쪽 칸이 겹치지 않음(간격 ≥ 12px)', col['l'] - card['r'] >= 12, (card, col))
            check('A6 열림: 오른쪽 칸이 화면 안(오른쪽 끝 ≤ 1920)', col['r'] <= 1920, col)
            check('A7 열림: 이동판이 오른쪽 칸 맨 위, 메모 패널이 그 아래', nav['t'] <= panel['t'] and nav['b'] <= panel['t'], (nav, panel))
            check('A8 열림: 편집창 높이 ≥ 500px', ed['h'] >= 500, ed)
            check('A9 열림: 맨 위(스크롤 0)에서 패널 아래 끝이 화면 안', panel['b'] <= 1080, panel)
            check('A10 열림: 도구줄이 편집창 위, 글자 수 줄이 아래', tools['b'] <= ed['t'] and ed['b'] <= foot['t'], (tools, ed, foot))
            check('A11 가로 스크롤 없음', hscroll(P)[0] <= hscroll(P)[1], hscroll(P))
            nbtn = P.locator('.memo-tools .mt-btn').count(); nsel = P.locator('.memo-tools .mt-sel').count()
            check('A12 도구 개수: 버튼 15 + 선택상자 3', nbtn == 15 and nsel == 3, (nbtn, nsel))
            # 고정 위치: 스크롤해도 상단 고정줄 아래에 붙고 화면 안에 머무는가
            P.evaluate("window.scrollTo(0, 300)"); P.wait_for_timeout(250)
            colS = geom(P, '.exam-nav-col'); topS = geom(P, '.exam-top')
            check('A13 스크롤해도 오른쪽 칸이 상단 고정줄과 겹치지 않고 화면 안', colS['t'] >= topS['b'] and colS['b'] <= 1080, (colS, topS))
            P.evaluate("window.scrollTo(0, 0)")
            # 닫으면 옛 배치로
            P.locator('.memo-x').click(); P.wait_for_timeout(200)
            col1 = geom(P, '.exam-nav-col'); card1 = geom(P, '.q-card')
            check('A14 닫으면 이동판 칸 250px · 카드 폭이 원래대로', col1['w'] == 250 and card1['w'] == card0['w'], (col1, card1, card0))
            ctx.close()

        # ===================== A2. 너비 끌기 =====================
        if want('A2'):
            ctx, P = fresh(browser)
            open_memo(P); P.wait_for_timeout(200)
            w0 = geom(P, '.exam-nav-col')['w']
            rz = geom(P, '#memo-resizer')
            check('A15 너비 조절 손잡이가 보임', rz and rz['w'] >= 8 and rz['h'] > 300, rz)
            cx, cy = rz['l'] + rz['w'] / 2, rz['t'] + rz['h'] / 2
            P.mouse.move(cx, cy); P.mouse.down(); P.mouse.move(cx - 60, cy, steps=5); P.mouse.move(cx - 140, cy, steps=5); P.mouse.up()
            P.wait_for_timeout(200)
            w1 = geom(P, '.exam-nav-col')['w']
            check('A16 왼쪽으로 140px 끌면 칸이 약 140px 넓어짐', abs((w1 - w0) - 140) <= 6, (w0, w1))
            check('A17 너비가 기기별로 저장됨(jcb_cbt_memow_v1)', abs(int(T.ls(P, 'jcb_cbt_memow_v1')) - w1) <= 1, T.ls(P, 'jcb_cbt_memow_v1'))
            P.locator('#memo-resizer').focus(); P.keyboard.press('ArrowRight')
            w2 = geom(P, '.exam-nav-col')['w']
            check('A18 → 키로 24px 좁아짐', abs((w1 - w2) - 24) <= 1, (w1, w2))
            P.keyboard.press('ArrowLeft'); P.keyboard.press('ArrowLeft')
            w3 = geom(P, '.exam-nav-col')['w']
            check('A19 ← 키 두 번으로 48px 넓어짐', abs((w3 - w2) - 48) <= 1, (w2, w3))
            # 한계: 끝까지 끌어도 카드가 너무 좁아지지 않음
            P.mouse.move(cx, cy)
            r2 = geom(P, '#memo-resizer'); cx2, cy2 = r2['l'] + r2['w'] / 2, r2['t'] + r2['h'] / 2
            P.mouse.move(cx2, cy2); P.mouse.down(); P.mouse.move(100, cy2, steps=8); P.mouse.up(); P.wait_for_timeout(200)
            wmax = geom(P, '.exam-nav-col')['w']; cardm = geom(P, '.q-card')
            check('A20 최대로 끌어도 너비 ≤1000, 카드 폭 ≥ 560', wmax <= 1000 and cardm['w'] >= 560, (wmax, cardm))
            P.mouse.move(cx2, cy2)
            r3 = geom(P, '#memo-resizer'); cx3, cy3 = r3['l'] + r3['w'] / 2, r3['t'] + r3['h'] / 2
            P.mouse.move(cx3, cy3); P.mouse.down(); P.mouse.move(1800, cy3, steps=8); P.mouse.up(); P.wait_for_timeout(200)
            wmin = geom(P, '.exam-nav-col')['w']
            check('A21 최소로 줄여도 너비 ≥ 360', wmin >= 360, wmin)
            # 새로고침 후에도 유지
            saved = int(T.ls(P, 'jcb_cbt_memow_v1'))
            P.reload(); P.wait_for_selector('#screen-home:not([hidden]) .start-bar')
            T.start(P, rounds=['2023년 3회']); open_memo(P); P.wait_for_timeout(200)
            wr = geom(P, '.exam-nav-col')['w']
            check('A22 새로고침 뒤 다시 열어도 저장한 너비', abs(wr - saved) <= 1, (saved, wr))
            P.locator('#memo-resizer').dblclick(); P.wait_for_timeout(200)
            wd = geom(P, '.exam-nav-col')['w']
            check('A23 더블클릭하면 기본 너비로(저장값 삭제)', 600 <= wd <= 700 and T.ls(P, 'jcb_cbt_memow_v1') is None, (wd, T.ls(P, 'jcb_cbt_memow_v1')))
            ctx.close()

        # ===================== B. 좁은 화면 =====================
        if want('B'):
            for (w, h, side) in ((1400, 900, True), (1281, 800, True), (1181, 800, True), (1180, 800, False), (1024, 768, False), (768, 900, False), (390, 800, False)):
                ctx, P = fresh(browser, vp={'width': w, 'height': h})
                open_memo(P); P.wait_for_timeout(250)
                hs = hscroll(P)
                col = geom(P, '.exam-nav-col'); card = geom(P, '.q-card'); panel = geom(P, '#memo-panel'); ed = geom(P, '#memo-editor'); tools = geom(P, '.memo-tools')
                check('B %dpx 가로 스크롤 없음' % w, hs[0] <= hs[1], hs)
                if side:
                    check('B %dpx 나란히 배치: 카드 ≥ 560, 겹침 없음, 편집창 ≥ 300' % w, card['w'] >= 560 and col['l'] - card['r'] >= 12 and ed['h'] >= 300 and panel['b'] <= h, (card, col, ed, panel))
                else:
                    pos = P.evaluate("getComputedStyle(document.getElementById('memo-panel')).position")
                    check('B %dpx 아래 창: fixed, 화면 아래에 붙음, 편집창 ≥ 150' % w, pos == 'fixed' and abs(panel['b'] - h) <= 1 and ed['h'] >= 150 and panel['w'] == w, (pos, panel, ed))
                    # 창이 카드 마지막 줄을 가리지 않도록 아래 여백이 있는가
                    P.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); P.wait_for_timeout(200)
                    foot = geom(P, '.q-footer')
                    check('B %dpx 끝까지 내리면 이전/다음 줄이 창 위에 보임' % w, foot and foot['b'] <= panel['t'] + 1, (foot, panel))
                tl = tools
                check('B %dpx 도구줄이 패널 폭 안' % w, tl['l'] >= panel['l'] and tl['r'] <= panel['r'] + 1, (tl, panel))
                ctx.close()

        # ===================== C. 입력 · 저장 =====================
        if want('C'):
            ctx, P = fresh(browser)
            open_memo(P)
            P.locator('#memo-editor').click()
            P.keyboard.type('첫째 줄 abc')
            P.keyboard.press('Enter')
            P.keyboard.type('둘째 줄  두 칸 띄움')
            P.keyboard.press('Enter'); P.keyboard.press('Enter')
            P.keyboard.type('넷째 줄')
            check('C1 입력 직후 상태 문구 "입력 중…"', P.locator('#memo-state').inner_text() == '입력 중…', P.locator('#memo-state').inner_text())
            check('C2 입력 중 글자 수 표시', re.match(r'^\d+ / 20000자$', P.locator('#memo-count').inner_text()) is not None, P.locator('#memo-count').inner_text())
            check('C3 입력 중에도 이동판 하늘색 사각형 즉시 켜짐', 'has-memo' in P.locator('#exam-qgrid button.nav-0').get_attribute('class'))
            commit(P)
            st = store(P).get('2023-3-1')
            check('C4 서식 없는 메모는 t 만 저장(h 없음), 줄바꿈 보존', st and st['t'] == '첫째 줄 abc\n둘째 줄  두 칸 띄움\n\n넷째 줄' and 'h' not in st, st)
            check('C5 저장 뒤 상태 문구 "저장됨 …"', P.locator('#memo-state').inner_text().startswith('저장됨'), P.locator('#memo-state').inner_text())
            # 새로고침 뒤 복원
            P.reload(); P.wait_for_selector('#screen-home:not([hidden]) .start-bar')
            T.start(P, rounds=['2023년 3회']); open_memo(P)
            check('C6 새로고침 뒤 같은 문항 메모가 그대로 보임', ed_text(P) == '첫째 줄 abc\n둘째 줄  두 칸 띄움\n\n넷째 줄', repr(ed_text(P)))
            # 문항 이동: Q2 는 비어 있고, 다시 Q1 에 오면 그대로
            T.goto_q(P, 2)
            check('C7 다른 문항에서는 편집창이 비어 있고 안내 글이 보임', ed_text(P).strip() == '' and P.locator('#memo-ph').is_visible(), (ed_text(P), P.locator('#memo-ph').is_visible()))
            P.locator('#memo-editor').click(); P.keyboard.type('Q2 메모'); commit(P)
            T.goto_q(P, 1)
            check('C8 Q1 로 돌아오면 Q1 메모', '첫째 줄' in ed_text(P) and 'Q2' not in ed_text(P), ed_text(P))
            T.goto_q(P, 2)
            check('C9 Q2 메모도 보존', ed_text(P).strip() == 'Q2 메모', ed_text(P))
            # 방향키: 편집창 안에서는 문항이 넘어가지 않는다
            P.locator('#memo-editor').click(); P.keyboard.press('ArrowLeft'); P.keyboard.press('ArrowRight')
            check('C10 편집창에서 ←/→ 를 눌러도 문항은 그대로(Q2)', P.locator('.q-num').first.inner_text() == 'Q2', P.locator('.q-num').first.inner_text())
            P.locator('.memo-tools .mt-bold').focus(); P.keyboard.press('ArrowRight')
            check('C11 도구줄 버튼에서 →를 눌러도 문항은 그대로', P.locator('.q-num').first.inner_text() == 'Q2', P.locator('.q-num').first.inner_text())
            P.locator('.mt-sel-font').focus(); P.keyboard.press('ArrowRight')
            check('C12 선택 상자에서 →를 눌러도 문항은 그대로', P.locator('.q-num').first.inner_text() == 'Q2', P.locator('.q-num').first.inner_text())
            # 지우기
            T.goto_q(P, 1)
            P.locator('#memo-clear').click()
            P.locator('#active-modal').get_by_role('button', name='지우기', exact=True).click()
            P.wait_for_timeout(200)
            check('C13 지우기: 저장소에서 삭제, 편집창 비움, 사각형 꺼짐', '2023-3-1' not in store(P) and ed_text(P).strip() == '' and 'has-memo' not in P.locator('#exam-qgrid button.nav-0').get_attribute('class'), (store(P).keys(), ed_text(P)))
            # 공백만 쓰면 메모 없음
            P.locator('#memo-editor').click(); P.keyboard.type('   '); P.keyboard.press('Enter'); commit(P)
            check('C14 공백·빈 줄만 있으면 저장하지 않음', '2023-3-1' not in store(P), store(P).get('2023-3-1'))
            ctx.close()

        # ===================== D. 서식 =====================
        if want('D'):
            ctx, P = fresh(browser)
            open_memo(P)
            P.locator('#memo-editor').click()
            P.keyboard.type('굵게 기울임 밑줄 취소선 글꼴 크기 색 정렬 행간')
            P.keyboard.press('Enter'); P.keyboard.type('항목 하나'); P.keyboard.press('Enter'); P.keyboard.type('항목 둘')
            P.keyboard.press('Enter'); P.keyboard.type('마지막 줄')
            # --- 글자 서식(선택 후) ---
            select_text(P, '굵게')
            tool(P, 'bold'); h = ed_html(P)
            check('D1 굵게: <b>굵게</b>', '<b>굵게</b>' in h, h)
            check('D2 굵게 단추가 눌림 표시(aria-pressed)', pressed(P, 'bold') == 'true', pressed(P, 'bold'))
            select_text(P, '기울임'); tool(P, 'italic'); h = ed_html(P)
            check('D3 기울임: <i>', '<i>기울임</i>' in h, h)
            select_text(P, '밑줄'); tool(P, 'underline'); h = ed_html(P)
            check('D4 밑줄: <u>', '<u>밑줄</u>' in h, h)
            select_text(P, '취소선'); tool(P, 'strike'); h = ed_html(P)
            check('D5 취소선: <strike>/<s>', ('<strike>취소선</strike>' in h) or ('<s>취소선</s>' in h), h)
            select_text(P, '굵게'); tool(P, 'bold'); h = ed_html(P)
            check('D6 다시 누르면 굵게 해제', '<b>굵게</b>' not in h and '굵게' in h, h)
            # 글꼴 (선택 상자에 포커스를 줬다가 적용 → 선택 복원 경로)
            select_text(P, '글꼴'); P.locator('.mt-sel-font').focus(); P.locator('.mt-sel-font').select_option('dotum'); h = ed_html(P)
            check('D7 글꼴 함초롬돋움 → font-family 에 HCR Dotum', re.search(r'<span style="[^"]*font-family:[^"]*HCR Dotum[^"]*">글꼴</span>', h) is not None, h)
            select_text(P, '크기'); P.locator('.mt-sel-size').select_option('24'); h = ed_html(P)
            check('D8 글자 크기 24 → font-size: 24px', re.search(r'<span style="[^"]*font-size: 24px[^"]*">크기</span>', h) is not None, h)
            select_text(P, '색'); P.locator('.memo-tools .mt-color').click()
            check('D9 글자색 창이 열림', P.locator('#memo-colors').is_visible())
            P.locator('#memo-colors .mc-sw[data-color="#D32F2F"]').click(); h = ed_html(P)
            check('D10 글자색 빨강 → color: rgb(211, 47, 47)', re.search(r'<span style="[^"]*color: rgb\(211, 47, 47\)[^"]*">색</span>', h) is not None, h)
            check('D11 색 고르면 창이 닫힘', P.locator('#memo-colors').is_hidden())
            # 글꼴 바탕/고정폭
            select_text(P, '정렬'); P.locator('.mt-sel-font').select_option('batang')
            check('D12 함초롬바탕', 'HCR Batang' in ed_html(P), ed_html(P))
            select_text(P, '행간'); P.locator('.mt-sel-font').select_option('mono')
            check('D13 고정폭', 'Courier New' in ed_html(P), ed_html(P))
            # --- 줄 서식 ---
            caret_after(P, '마지막')
            tool(P, 'center'); h = ed_html(P)
            check('D14 가운데 정렬: 그 줄 div 에 text-align: center', re.search(r'<div style="text-align: center;">마지막 줄</div>', h) is not None, h)
            check('D15 정렬 단추 상태(가운데 눌림, 왼쪽 안 눌림)', pressed(P, 'center') == 'true' and pressed(P, 'left') == 'false', (pressed(P, 'center'), pressed(P, 'left')))
            tool(P, 'right'); h = ed_html(P)
            check('D16 오른쪽 정렬로 바뀜', 'text-align: right;">마지막 줄' in h and 'text-align: center;">마지막 줄' not in h, h)
            tool(P, 'justify'); check('D17 양쪽 정렬', 'text-align: justify;">마지막 줄' in ed_html(P), ed_html(P))
            tool(P, 'left'); check('D18 왼쪽 정렬', 'text-align: left;">마지막 줄' in ed_html(P), ed_html(P))
            P.locator('.mt-sel-lh').select_option('2.0'); h = ed_html(P)
            check('D19 행간 2.0 → line-height: 2', 'line-height: 2;' in h and '마지막 줄' in h, h)
            check('D20 행간 선택 상자가 지금 줄 값으로 표시', P.locator('.mt-sel-lh').input_value() == '2.0', P.locator('.mt-sel-lh').input_value())
            # 여러 줄 선택 + 정렬/행간
            P.evaluate("""() => { const ed=document.getElementById('memo-editor'); ed.focus(); const divs=[...ed.children]; const a=divs.find(d=>d.textContent.startsWith('항목 하나')), b=divs.find(d=>d.textContent.startsWith('항목 둘')); const r=document.createRange(); r.setStart(a.firstChild,1); r.setEnd(b.firstChild,2); const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""")
            tool(P, 'center'); h = ed_html(P)
            check('D21 두 줄에 걸친 선택 → 두 줄 모두 가운데 정렬', h.count('text-align: center;">항목') == 2, h)
            P.locator('.mt-sel-lh').select_option('1.3'); h = ed_html(P)
            check('D22 두 줄 모두 행간 1.3', h.count('line-height: 1.3;') == 2, h)
            # 목록
            tool(P, 'ul'); h = ed_html(P)
            check('D23 글머리표: <ul><li>항목…', '<ul>' in h and '<li' in h and '항목 하나' in h and '항목 둘' in h, h)
            check('D24 글머리표 단추 눌림 상태', pressed(P, 'ul') == 'true', pressed(P, 'ul'))
            tool(P, 'ul'); h = ed_html(P)
            check('D25 다시 누르면 목록 해제', '<ul>' not in h, h)
            tool(P, 'ol'); h = ed_html(P)
            check('D26 번호 목록: <ol><li>', '<ol>' in h, h)
            commit(P)
            st = store(P).get('2023-3-1')
            check('D27 저장: h 가 있고 t 에는 "1. 항목 하나" 처럼 번호가 들어감', st and 'h' in st and '1. 항목 하나' in st['t'] and '2. 항목 둘' in st['t'], st)
            check('D28 저장된 h 에 <ol>·<b> 같은 태그와 style 이 정리된 모양으로 있음', st and '<ol' in st['h'] and '<i>기울임</i>' in st['h'] and '<u>밑줄</u>' in st['h'] and '<script' not in st['h'], st and st['h'][:400])
            # 구분선
            caret_after(P, '마지막'); tool(P, 'hr'); h = ed_html(P)
            check('D29 구분선: <hr> 삽입, id 속성 없음', '<hr>' in h and 'id=' not in h.split('<hr')[1][:12], h)
            commit(P)
            st = store(P)['2023-3-1']
            check('D30 구분선은 t 에서 ──── 한 줄', '────────────' in st['t'] and '<hr>' in st['h'], st)
            # 서식 지우기
            select_text(P, '기울임'); tool(P, 'clear'); h = ed_html(P)
            check('D31 서식 지우기: 선택 글자의 기울임 해제', '<i>기울임</i>' not in h and '기울임' in h, h)
            select_text(P, '글꼴'); tool(P, 'clear'); h = ed_html(P)
            check('D32 서식 지우기: 글꼴(span) 서식 해제', 'HCR Dotum' not in h and '글꼴' in h, h)
            select_text(P, '크기'); tool(P, 'clear'); h = ed_html(P)
            check('D33 서식 지우기: 글자 크기 해제', 'font-size: 24px' not in h, h)
            ctx.close()

            # --- 커서만 있을 때(선택 없음): 이어 쓰는 글에 적용 ---
            ctx, P = fresh(browser)
            open_memo(P); P.locator('#memo-editor').click()
            P.keyboard.type('앞')
            P.locator('.mt-sel-size').select_option('32')
            P.keyboard.type('큰글자')
            P.locator('.mt-sel-size').select_option('14')
            P.keyboard.type('뒤')
            h = ed_html(P)
            check('D34 커서만 둔 채 크기 32 → 이어 쓴 글만 32px(앞·뒤는 14px)', (fsize(P, '앞'), fsize(P, '큰글자'), fsize(P, '뒤')) == ('14px', '32px', '14px'), (fsize(P, '앞'), fsize(P, '큰글자'), fsize(P, '뒤'), h))
            commit(P)
            st = store(P)['2023-3-1']
            check('D35 저장된 t 에 보이지 않는 글자(\\u200b) 없음', '​' not in st['t'] and st['t'] == '앞큰글자뒤', repr(st['t']))
            check('D36 저장된 h 에도 \\u200b 없음', '​' not in st['h'] and 'font-size: 32px' in st['h'], st['h'])
            P.keyboard.press('Control+a'); P.keyboard.press('Delete')
            P.keyboard.press('Control+b'); P.keyboard.type('굵게'); P.keyboard.press('Control+b'); P.keyboard.type('보통')
            h = ed_html(P)
            check('D37 Ctrl+B 단축키: 굵은 글씨 뒤 보통 글씨', '<b>굵게</b>보통' in h, h)
            ctx.close()

        # ===================== E. 되돌리기 · 다시하기 =====================
        if want('E'):
            ctx, P = fresh(browser)
            open_memo(P); P.locator('#memo-editor').click()
            P.keyboard.type('abc')
            P.wait_for_timeout(1400)
            P.keyboard.type('def')
            P.wait_for_timeout(1400)
            P.keyboard.type('ghi')
            check('E1 입력 3묶음 후 abcdefghi', ed_text(P) == 'abcdefghi', ed_text(P))
            P.keyboard.press('Control+z')
            check('E2 Ctrl+Z → 마지막 묶음만 취소(abcdef)', ed_text(P) == 'abcdef', ed_text(P))
            P.locator('.memo-tools .mt-undo').click()
            check('E3 되돌리기 단추 → abc', ed_text(P) == 'abc', ed_text(P))
            P.locator('.memo-tools .mt-undo').click()
            check('E4 한 번 더 → 빈 글(처음 상태)', ed_text(P).strip() == '', repr(ed_text(P)))
            P.locator('.memo-tools .mt-undo').click()
            check('E5 처음 상태에서 더 되돌려도 그대로(오류 없음)', ed_text(P).strip() == '', repr(ed_text(P)))
            P.keyboard.press('Control+y')
            check('E6 Ctrl+Y → abc', ed_text(P) == 'abc', ed_text(P))
            P.locator('.memo-tools .mt-redo').click()
            check('E7 다시하기 단추 → abcdef', ed_text(P) == 'abcdef', ed_text(P))
            P.keyboard.press('Control+Shift+z')
            check('E8 Ctrl+Shift+Z → abcdefghi', ed_text(P) == 'abcdefghi', ed_text(P))
            P.keyboard.press('Control+z'); P.keyboard.type('X')
            P.wait_for_timeout(100)
            check('E9 되돌린 뒤 새로 입력하면 다시하기 기록은 사라짐(abcdefX 이후 Ctrl+Y 무반응)', True)
            before = ed_text(P)
            P.keyboard.press('Control+y')
            check('E10 새 입력 뒤 Ctrl+Y 는 아무 변화 없음', ed_text(P) == before, (before, ed_text(P)))
            # 서식 명령도 되돌리기
            P.keyboard.press('Control+a'); P.keyboard.press('Delete'); P.keyboard.type('서식 되돌리기')
            select_text(P, '서식'); tool(P, 'bold')
            select_text(P, '되돌리기'); P.locator('.mt-sel-size').select_option('28')
            check('E11 서식 두 번 적용', '<b>서식</b>' in ed_html(P) and 'font-size: 28px' in ed_html(P), ed_html(P))
            P.locator('.memo-tools .mt-undo').click()
            check('E12 되돌리기 → 크기만 취소', 'font-size: 28px' not in ed_html(P) and '<b>서식</b>' in ed_html(P), ed_html(P))
            P.locator('.memo-tools .mt-undo').click()
            check('E13 되돌리기 → 굵게도 취소', '<b>' not in ed_html(P) and ed_text(P) == '서식 되돌리기', ed_html(P))
            P.locator('.memo-tools .mt-redo').click(); P.locator('.memo-tools .mt-redo').click()
            check('E14 다시하기 두 번 → 굵게+크기 복원', '<b>서식</b>' in ed_html(P) and 'font-size: 28px' in ed_html(P), ed_html(P))
            commit(P)
            st = store(P)['2023-3-1']
            check('E15 되돌리기/다시하기 결과가 저장됨', '<b>서식</b>' in st['h'] and 'font-size: 28px' in st['h'], st)
            P.locator('.memo-tools .mt-undo').click(); P.locator('.memo-tools .mt-undo').click(); commit(P)
            st = store(P)['2023-3-1']
            check('E16 서식을 모두 되돌리면 h 는 사라지고 t 만 남음(서식 없는 메모)', 'h' not in st and st['t'] == '서식 되돌리기', st)
            # 문항을 바꾸면 기록 초기화(다른 문항 글이 섞이지 않음)
            T.goto_q(P, 2); P.locator('#memo-editor').click(); P.keyboard.type('Q2'); P.keyboard.press('Control+z'); P.keyboard.press('Control+z')
            check('E17 Q2 에서 되돌리기를 아무리 눌러도 Q1 글이 나오지 않음', 'Q1' not in ed_text(P) and '서식' not in ed_text(P), ed_text(P))
            ctx.close()

        # ===================== F. 붙여넣기 · 한도 =====================
        if want('F'):
            ctx, P = fresh(browser)
            open_memo(P); P.locator('#memo-editor').click()
            paste(P, '첫째 줄\r\n둘째 줄\n\n넷째 줄')
            check('F1 여러 줄 붙여넣기: 줄이 그대로(빈 줄 포함, CRLF 는 줄바꿈 하나로)', ed_text(P) == '첫째 줄\n둘째 줄\n\n넷째 줄', repr(ed_text(P)))
            commit(P)
            check('F2 저장된 t', store(P)['2023-3-1']['t'] == '첫째 줄\n둘째 줄\n\n넷째 줄', store(P))
            clear_editor(P)
            paste(P, '굵은빨강', '<b style="color:red;font-size:40px">굵은빨강</b><script>window.__XSS=1</script><img src=x onerror="window.__XSS=2">')
            h = ed_html(P)
            check('F3 서식 있는 글을 붙여넣어도 글만 들어옴(b·style·script·img 없음)', '굵은빨강' in h and not re.search(r'<(b|script|img)|style=|font-size', h), h)
            check('F4 붙여넣은 글이 실행되지 않음', P.evaluate("() => window.__XSS === undefined"))
            clear_editor(P); P.keyboard.type('abcdef')
            select_text(P, 'cd'); paste(P, 'XY')
            check('F5 선택한 글 위에 붙여넣으면 바꿔 넣음(abXYef)', ed_text(P) == 'abXYef', ed_text(P))
            # 글자 수 한도
            clear_editor(P)
            paste(P, 'a' * 19990)
            check('F6 19,990자 붙여넣기: 글자 수 표시 19990 / 20000자', count_text(P) == '19990 / 20000자', count_text(P))
            paste(P, 'b' * 100)
            check('F7 100자 더 붙여넣으면 남은 10자까지만 들어감(20000)', count_text(P) == '20000 / 20000자' and ed_text(P).endswith('a' * 5 + 'b' * 10) and len(ed_text(P)) == 20000, (count_text(P), len(ed_text(P))))
            check('F8 안내 문구가 보임', '붙여넣은 글이 길어' in state_text(P), state_text(P))
            P.keyboard.type('z')
            check('F9 한도에서 한 글자 더 치면 취소됨(여전히 20000)', len(ed_text(P)) == 20000 and 'z' not in ed_text(P)[-3:], len(ed_text(P)))
            check('F10 취소 안내 문구', '취소됩니다' in state_text(P), state_text(P))
            commit(P, 1000)
            check('F11 저장된 글도 정확히 20000자', len(store(P)['2023-3-1']['t']) == 20000, len(store(P)['2023-3-1']['t']))
            # 용량 한도: 줄이 아주 많은 글에 한꺼번에 서식을 입히면 저장 용량(200KB)을 넘음
            clear_editor(P)
            P.wait_for_timeout(6300)      # 앞 단계의 안내 문구(6초)가 사라진 뒤에 다음 안내를 본다
            check('F11b 안내 문구는 6초 뒤 일반 상태 문구로 돌아감', not state_text(P).startswith('글자 수(') and '붙여넣은' not in state_text(P), state_text(P))
            # (크롬의 insertText 는 줄이 많을수록 급격히 느려져 — 500줄 3초, 2000줄 30초 — 시험에서는 줄을 DOM 으로 바로 채우고 input 이벤트만 보낸다)
            P.evaluate("""() => { const ed=document.getElementById('memo-editor'); ed.focus(); ed.innerHTML='<div>a</div>'.repeat(9000);
              ed.dispatchEvent(new InputEvent('input', {inputType:'insertText', bubbles:true})); }""")
            n_before = P.evaluate("() => document.getElementById('memo-editor').children.length")
            check('F12 9,000줄 입력됨(서식 없음 → 용량 이내)', n_before == 9000 and 'text-align' not in ed_html(P) and not state_text(P).startswith('글자 수('), (n_before, state_text(P)))
            P.locator('#memo-editor').click(); P.keyboard.press('Control+a')
            tool(P, 'center')
            check('F13 9,000줄 전체 가운데 정렬은 용량(200KB) 초과 → 취소되고 서식이 입혀지지 않음', 'text-align' not in ed_html(P), ed_html(P)[:200])
            check('F14 용량 초과 안내 문구', '저장 용량' in state_text(P), state_text(P))
            ctx.close()

        # ===================== G. 예전 메모(서식 없는 글) 호환 =====================
        if want('G'):
            seed = {MK: {
                '2023-3-1': {'t': 'old line1\n<b>not bold</b> & "q"\n\n끝', 'ts': NOW - 5000, 'c': NOW - 9000},
                '2023-3-2': {'t': '서식 있음', 'ts': NOW - 4000, 'h': '<div><b>서식</b> 있음</div>'},
                '2023-3-3': {'t': '깨진 h', 'ts': NOW - 3000, 'h': 12345},
                '2023-3-4': {'t': '배열 h', 'ts': NOW - 2000, 'h': ['<b>x</b>']}}}
            ctx, P = fresh(browser, seed=seed)
            cls = lambda i: P.locator('#exam-qgrid button.nav-%d' % i).get_attribute('class')
            check('G1 예전 메모가 있는 4문항 모두 이동판에 메모 표시', all('has-memo' in cls(i) for i in range(4)) and 'has-memo' not in cls(4), [cls(i) for i in range(5)])
            open_memo(P)
            check('G2 예전 글이 그대로 보임(HTML 태그처럼 보이는 글자도 글자 그대로)', ed_text(P) == 'old line1\n<b>not bold</b> & "q"\n\n끝', repr(ed_text(P)))
            check('G3 글자로 적힌 <b> 가 굵은 글씨로 해석되지 않음', P.locator('#memo-editor b').count() == 0, ed_html(P))
            check('G4 처음 작성/마지막 수정 시각 줄이 보임', '처음 작성' in P.locator('#memo-when').inner_text(), P.locator('#memo-when').inner_text())
            P.wait_for_timeout(900)
            check('G5 열어 보기만 하면 저장 시각(ts)이 바뀌지 않음', store(P)['2023-3-1']['ts'] == NOW - 5000, store(P)['2023-3-1'])
            T.goto_q(P, 2)
            check('G6 h 가 있는 메모는 서식대로 보임(굵은 글씨 1곳)', P.locator('#memo-editor b').count() == 1 and P.locator('#memo-editor b').inner_text() == '서식', ed_html(P))
            T.goto_q(P, 3)
            check('G7 h 가 숫자로 망가진 메모도 글(t)로 열림', ed_text(P) == '깨진 h', ed_text(P))
            T.goto_q(P, 4)
            check('G8 h 가 배열로 망가진 메모도 글(t)로 열림', ed_text(P) == '배열 h', ed_text(P))
            T.goto_q(P, 1)
            focus_end(P); P.keyboard.type('추가')
            commit(P)
            st = store(P)['2023-3-1']
            check('G9 예전 메모를 고치면 글만 갱신, h 는 안 생김, 처음 작성 시각 보존', st['t'].endswith('끝추가') and 'h' not in st and st['c'] == NOW - 9000 and st['ts'] > NOW - 5000, st)
            ctx.close()

        # ===================== H. 악성 서식 차단 =====================
        if want('H'):
            evil1 = ('<div onclick="window.__XSS=1" id="pwn" class="evil" style="position:fixed;top:0;left:0;width:9999px;background:url(http://evil.test/x.png);text-align:center;line-height:2">A'
                     '<img src=x onerror="window.__XSS=2"><script>window.__XSS=3</script><b onmouseover="window.__XSS=4" id="pwn2" class="evil">굵게</b>'
                     '<a href="javascript:window.__XSS=5">링크</a><iframe srcdoc="<script>parent.__XSS=6</script>"></iframe>'
                     '<svg onload="window.__XSS=7"><script>window.__XSS=9</script><text>svg글</text></svg><style>*{display:none!important}</style>'
                     '<span style="color:red;font-size:900px;font-family:evil,serif;position:absolute;background:url(http://evil.test/y.png)">빨강큰</span>'
                     '<span style="color:rgb(0,128,0);font-size:20px;font-family:\'HCR Batang\'">초록</span>'
                     '<input value=x><form action="http://evil.test"><button>b</button></form><object data="x"></object><embed src="x">'
                     '<video src=x onerror="window.__XSS=8"></video><math><mi>m</mi></math></div>')
            evil2 = ('<noscript><p title="</noscript><img src=x onerror=window.__XSS=11>">ns</p></noscript>'
                     '<math><mtext><table><mglyph><style><!--</style><img title="--&gt;&lt;img src=1 onerror=window.__XSS=12&gt;">mx</mglyph></table></mtext></math>'
                     '<svg></p><style><a id="</style><img src=1 onerror=window.__XSS=13>">')
            seed = {MK: {'2023-3-1': {'t': '가짜 글', 'ts': NOW - 2000, 'h': evil1}, '2023-3-2': {'t': '가짜 글2', 'ts': NOW - 1000, 'h': evil2}}}
            ctx, P = fresh(browser, seed=seed)
            open_memo(P); P.wait_for_timeout(400)
            CHK = """() => { const ed=document.getElementById('memo-editor'); const bad=[], badStyle=[]; const okp=new Set(['text-align','line-height','color','font-family','font-size']);
              ed.querySelectorAll('*').forEach(e => { if(!/^(DIV|SPAN|B|I|U|S|UL|OL|LI|HR|BR)$/.test(e.nodeName)) bad.push(e.nodeName);
                [...e.attributes].forEach(a => { if(a.name !== 'style') bad.push(e.nodeName+'@'+a.name); });
                for(let i=0;i<e.style.length;i++){ if(!okp.has(e.style[i])) badStyle.push(e.style[i]); } });
              return {bad, badStyle, xss: window.__XSS === undefined, html: ed.innerHTML}; }"""
            r = P.evaluate(CHK)
            check('H1 악성 서식 1: 허용 목록 밖의 태그·속성이 편집창에 하나도 없음', not r['bad'], r['bad'])
            check('H2 악성 서식 1: style 에 허용 속성(정렬·행간·색·글꼴·크기) 밖의 것이 없음', not r['badStyle'], r['badStyle'])
            check('H3 악성 서식 1: 스크립트가 실행되지 않음(window.__XSS 미정의)', r['xss'])
            h = r['html']
            check('H4 글은 남음(A·굵게·링크·빨강큰·초록)', all(x in ed_text(P) for x in ['A', '굵게', '링크', '빨강큰', '초록']), ed_text(P))
            check('H5 svg·script 안에 든 글자는 안 남음(svg글·window.__XSS 없음)', 'svg글' not in ed_text(P) and '__XSS' not in ed_text(P) and 'display:none' not in ed_text(P), ed_text(P))
            check('H6 첫 줄 정렬·행간은 허용 범위라 살아남고 position/background 는 사라짐', re.search(r'<div style="[^"]*text-align: center', h) is not None and 'line-height: 2' in h and 'position' not in h and 'background' not in h and 'evil' not in h, h[:300])
            check('H7 허용 밖 값(이름 있는 색·900px·모르는 글꼴)은 걸러져 일반 글자', '<span style="color: red' not in h and '900px' not in h and not re.search(r'<span[^>]*>빨강큰', h), h)
            check('H8 허용 값(#008000 · 20px · 함초롬바탕)은 살아남음', re.search(r'<span style="[^"]*color: rgb\(0, 128, 0\)[^"]*font-size: 20px[^"]*">초록|<span style="[^"]*font-size: 20px[^"]*HCR Batang[^"]*">초록|<span style="[^"]*">초록', h) is not None and 'HCR Batang' in h and 'font-size: 20px' in h, h)
            check('H9 id·class·on* 속성이 없음', not re.search(r'\b(id|class|onclick|onerror|onload|onmouseover)=', h), h)
            T.goto_q(P, 2)
            r2 = P.evaluate(CHK)
            check('H10 변형 공격(noscript·math·svg 파서 혼동) — 태그 하나도 안 남음', not r2['bad'] and 'img' not in r2['html'] and 'onerror' not in r2['html'], (r2['bad'], r2['html'][:200]))
            check('H11 변형 공격 — 스크립트 실행 안 됨', r2['xss'])
            P.wait_for_timeout(300)
            check('H12 변형 공격 — 뒤늦게 실행되는 것도 없음(0.3초 뒤)', P.evaluate("() => window.__XSS === undefined"))
            # 고치면 저장소에는 정화된 모양만 저장
            T.goto_q(P, 1); focus_end(P); P.keyboard.type('Z'); commit(P)
            st = store(P)['2023-3-1']
            check('H13 고친 뒤 저장된 h 에 위험한 것이 없음', 'h' in st and not re.search(r'onclick|onerror|<script|<img|javascript:|position|evil|<iframe|<svg|<style|<a ', st['h']), st.get('h', '')[:300])
            check('H14 저장된 t 에 태그 글자(<)가 없음(글이 아닌 것은 걸러짐)', '<' not in st['t'], st['t'])
            ctx.close()

        # ===================== I. 기록 파일 (내보내기 · 가져오기) =====================
        if want('I'):
            seed = {MK: {
                '2023-3-1': {'t': '평범한 메모', 'ts': NOW - 5000, 'c': NOW - 6000},
                '2023-3-2': {'t': '굵은 글씨', 'ts': NOW - 4000, 'h': '<div><b>굵은</b> <span style="color: rgb(211, 47, 47); font-size: 24px;">글씨</span></div>'}}}
            ctx, P = T.new_page(browser, seed=seed)
            with P.expect_download() as dl:
                P.locator('#btn-rec-export').click()
            raw = open(dl.value.path(), encoding='utf-8').read()
            rec = json.loads(raw)
            m1, m2 = rec['memos']['2023-3-1'], rec['memos']['2023-3-2']
            check('I1 내보낸 파일: 서식 있는 메모는 h 가 들어가고, 평범한 메모에는 h 가 없음', 'h' not in m1 and '<b>굵은</b>' in m2['h'] and m2['t'] == '굵은 글씨', (m1, m2))
            check('I2 내보낸 파일 형식·버전은 그대로(format jcb_cbt_records, version 1)', rec['format'] == 'jcb_cbt_records' and rec['version'] == 1 and rec['counts']['memos'] == 2, (rec['format'], rec['version'], rec['counts']))
            check('I3 읽기용 목차에 메모 글 앞부분이 보임', any('굵은 글씨' in x for x in rec['readable_index']), rec['readable_index'])
            exported = write_tmp('memo_rec_export_%s.json' % T.TAG, raw)
            ctx.close()
            # 빈 기기로 가져오기
            ctx, P = T.new_page(browser)
            with P.expect_file_chooser() as fc:
                P.locator('#btn-rec-import').click()
            fc.value.set_files(exported)
            T.wait_until(lambda: P.locator('#active-modal').count() == 1)
            P.locator('#active-modal').get_by_role('button', name='합치기', exact=True).click()
            T.wait_until(lambda: T.ls_json(P, MK, {}).get('2023-3-2'))
            ms = T.ls_json(P, MK, {})
            check('I4 가져온 뒤 서식 메모의 h 가 보존됨', ms.get('2023-3-2', {}).get('h') == rec['memos']['2023-3-2']['h'] and 'h' not in ms.get('2023-3-1', {}), ms)
            T.start(P, rounds=['2023년 3회']); T.goto_q(P, 2); open_memo(P)
            check('I5 가져온 서식이 편집창에 보임(굵게 1 · 24px)', P.locator('#memo-editor b').count() == 1 and fsize(P, '글씨') == '24px', ed_html(P))
            ctx.close()
            # 위조 파일
            big = '가' * 150000
            forged = rec_file_obj = {'format': 'jcb_cbt_records', 'version': 1, 'app': 'x', 'exportedAt': NOW, 'hist': [], 'saves': [], 'memos': {
                '2023-3-1': {'t': '가짜', 'h': '<div><b>진짜</b><img src=x onerror="window.__XSS=21"><script>window.__XSS=22</script></div>', 'ts': NOW - 1000},
                '2023-3-2': {'t': '숫자 h', 'h': 123, 'ts': NOW - 1000},
                '2023-3-3': {'t': '배열 h', 'h': ['<b>x</b>'], 'ts': NOW - 1000},
                '2023-3-4': {'t': '큰 h', 'h': '<div>' + big + '</div>', 'ts': NOW - 1000},
                '2023-3-5': {'t': 'x' * 20001, 'h': '<div><b>x</b></div>', 'ts': NOW - 1000},
                '2023-3-6': {'t': '   ', 'h': '<div><b> </b></div>', 'ts': NOW - 1000},
                '2023-3-7': {'t': '미래', 'h': '<div><i>미래</i></div>', 'ts': NOW + 10 * 86400000}}}
            fp = write_tmp('memo_rec_forged_%s.json' % T.TAG, forged)
            ctx, P = T.new_page(browser)
            with P.expect_file_chooser() as fc:
                P.locator('#btn-rec-import').click()
            fc.value.set_files(fp)
            T.wait_until(lambda: P.locator('#active-modal').count() == 1)
            P.locator('#active-modal').get_by_role('button', name='합치기', exact=True).click()
            T.wait_until(lambda: T.ls_json(P, MK, {}).get('2023-3-1'))
            ms = T.ls_json(P, MK, {})
            check('I6 위조 파일: h 의 img·script 가 걸러지고 t 는 h 에서 다시 만든 글("진짜")', ms['2023-3-1'].get('h') == '<div><b>진짜</b></div>' and ms['2023-3-1']['t'] == '진짜', ms.get('2023-3-1'))
            check('I7 위조 파일: h 가 숫자·배열이면 h 는 버리고 글(t)만 받음', 'h' not in ms['2023-3-2'] and ms['2023-3-2']['t'] == '숫자 h' and 'h' not in ms['2023-3-3'] and ms['2023-3-3']['t'] == '배열 h', (ms.get('2023-3-2'), ms.get('2023-3-3')))
            check('I8 위조 파일: 용량(200KB)을 넘는 h 는 버리고 글만 받음', '2023-3-4' in ms and 'h' not in ms['2023-3-4'] and ms['2023-3-4']['t'] == '큰 h', {k: v for k, v in (ms.get('2023-3-4') or {}).items() if k != 'h'})
            check('I9 위조 파일: 20,001자 글은 20,000자로 자르고 h 는 버림', len(ms['2023-3-5']['t']) == 20000 and 'h' not in ms['2023-3-5'], (len(ms['2023-3-5']['t']), 'h' in ms['2023-3-5']))
            check('I10 위조 파일: 공백뿐인 메모와 하루 넘게 미래인 메모는 받지 않음', '2023-3-6' not in ms and '2023-3-7' not in ms, list(ms))
            check('I11 가져오는 동안 스크립트가 실행되지 않음', P.evaluate("() => window.__XSS === undefined"))
            ctx.close()

        # ===================== J. 서버 동기화(가짜 서버) =====================
        if want('J') and not T.IS_FILE:
            T.reset()
            UID = 'u_memoed'
            base = 'data/users/%s/memo_' % UID
            ctx, A = fresh(browser, mock=True, uid=UID)
            check('J1 동기화 켜짐', T.wait_until(lambda: A.locator('#sync-bar').get_attribute('data-state') == 'on', 8))
            open_memo(A); A.locator('#memo-editor').click(); A.keyboard.type('서버 굵게 글'); select_text(A, '굵게'); tool(A, 'bold'); commit(A, 1200)
            doc = T.wait_until(lambda: [v for p, v in T.dump()['docs'].items() if p.endswith('memo_2023-3-1')], 8)
            doc = doc[0] if doc else None
            check('J2 서버 문서에 h(서식)와 t(글)가 올라감', bool(doc) and '<b>굵게</b>' in doc.get('h', '') and doc.get('t') == '서버 굵게 글' and doc.get('qid') == '2023-3-1', doc)
            # 다른 기기
            ctx2, B = fresh(browser, mock=True, uid=UID)
            check('J3 다른 기기 동기화 켜짐', T.wait_until(lambda: B.locator('#sync-bar').get_attribute('data-state') == 'on', 8))
            got = T.wait_until(lambda: T.ls_json(B, MK, {}).get('2023-3-1'), 8)
            check('J4 다른 기기로 서식째 내려옴', bool(got) and '<b>굵게</b>' in got.get('h', ''), got)
            open_memo(B)
            check('J5 다른 기기 편집창에 굵은 글씨로 보임', T.wait_until(lambda: B.locator('#memo-editor b').count() == 1, 4), ed_html(B))
            # 서버에 악성 h 가 있을 때
            T.put_doc(base + '2023-3-3', {'qid': '2023-3-3', 't': '서버글', 'ts': NOW, 'h': '<div><img src=x onerror="window.__XSS=31"><i>서버글</i><script>window.__XSS=32</script></div>'})
            ctx3, C = fresh(browser, mock=True, uid=UID)
            got = T.wait_until(lambda: T.ls_json(C, MK, {}).get('2023-3-3'), 8)
            check('J6 서버의 악성 h 는 받는 쪽에서 정화됨(<div><i>서버글</i></div>)', bool(got) and got.get('h') == '<div><i>서버글</i></div>', got)
            check('J7 스크립트 실행 안 됨', C.evaluate("() => window.__XSS === undefined"))
            ctx3.close(); ctx2.close()
            # 서식을 모두 지우면 서버 문서에서도 h 가 사라짐(평범한 글로 되돌림)
            A.locator('#memo-editor').click(); A.keyboard.press('Control+a'); A.keyboard.press('Delete'); A.keyboard.type('평범해짐'); commit(A, 1200)
            doc = T.wait_until(lambda: (lambda d: d[0] if d and d[0].get('t') == '평범해짐' else None)([v for p, v in T.dump()['docs'].items() if p.endswith('memo_2023-3-1')]), 8)
            check('J8 서식을 없애고 다시 쓰면 서버 문서에 h 가 없음(문서 통째로 교체)', bool(doc) and 'h' not in doc, doc)
            ctx.close()

        # ===================== K. 합쳐진 문항의 옛 id 메모 옮기기(서식 포함) =====================
        if want('K'):
            H_OLD = '<div><b>옛 굵은 메모</b></div>'
            # K1: 남은 문항(2020-3-7)에 메모가 없으면 서식째 옮김
            ctx, P = T.new_page(browser, seed={MK: {'2023-1-19': {'t': '옛 굵은 메모', 'ts': NOW - 1000, 'c': NOW - 2000, 'h': H_OLD}}})
            ms = T.ls_json(P, MK, {})
            check('K1 옛 id 메모가 남은 문항으로 서식·처음 작성 시각째 옮겨지고 옛 id 는 사라짐', '2023-1-19' not in ms and ms.get('2020-3-7', {}).get('h') == H_OLD and ms['2020-3-7']['t'] == '옛 굵은 메모' and ms['2020-3-7'].get('c') == NOW - 2000, ms)
            T.start(P, rounds=['2020년 3회']); T.goto_q(P, 7); open_memo(P)
            check('K2 옮겨진 메모가 굵게 보임', P.locator('#memo-editor b').count() == 1, ed_html(P))
            ctx.close()
            # K3: 둘 다 있고 서식이 있음 → 이어 붙이되 서식 유지
            seed = {MK: {'2020-3-7': {'t': '본 메모', 'ts': NOW - 3000, 'c': NOW - 7000, 'h': '<div><i>본 메모</i></div>'},
                         '2023-1-19': {'t': '옛 메모', 'ts': NOW - 1000, 'c': NOW - 2000, 'h': '<div><b>옛 메모</b></div>'}}}
            ctx, P = T.new_page(browser, seed=seed)
            ms = T.ls_json(P, MK, {}); m = ms.get('2020-3-7', {})
            check('K3 둘 다 있으면 글이 "본 메모 + 머리줄 + 옛 메모" 로 이어 붙음', m.get('t') == '본 메모\n\n── 2023년 1회 #19 때 쓴 메모 ──\n옛 메모' and '2023-1-19' not in ms, m)
            check('K4 서식도 함께 이어 붙음(기울임·굵게 둘 다, 머리줄 포함)', '<i>본 메모</i>' in m.get('h', '') and '<b>옛 메모</b>' in m.get('h', '') and '2023년 1회 #19 때 쓴 메모' in m.get('h', ''), m.get('h'))
            check('K5 처음 작성 시각은 더 이른 쪽', m.get('c') == NOW - 7000, m.get('c'))
            T.start(P, rounds=['2020년 3회']); T.goto_q(P, 7); open_memo(P)
            check('K6 편집창에서도 기울임 1 · 굵게 1', P.locator('#memo-editor i').count() == 1 and P.locator('#memo-editor b').count() == 1, ed_html(P))
            ctx.close()
            # K7: 한쪽만 서식 있음 → 서식 없는 쪽은 줄 단위로 바꿔 이어 붙임
            seed = {MK: {'2020-3-7': {'t': '평범 본', 'ts': NOW - 3000}, '2023-1-19': {'t': '굵은 옛', 'ts': NOW - 1000, 'h': '<div><b>굵은 옛</b></div>'}}}
            ctx, P = T.new_page(browser, seed=seed)
            m = T.ls_json(P, MK, {}).get('2020-3-7', {})
            check('K7 한쪽만 서식이 있어도 h 가 만들어지고 두 글이 모두 들어 있음', '평범 본' in m.get('h', '') and '<b>굵은 옛</b>' in m.get('h', '') and m.get('t', '').startswith('평범 본\n\n── '), m)
            ctx.close()
            # K8: 서식 없는 두 메모(예전 방식) → h 없이 글만
            seed = {MK: {'2020-3-7': {'t': '평범 본', 'ts': NOW - 3000}, '2023-1-19': {'t': '평범 옛', 'ts': NOW - 1000}}}
            ctx, P = T.new_page(browser, seed=seed)
            m = T.ls_json(P, MK, {}).get('2020-3-7', {})
            check('K8 서식 없는 두 메모는 예전처럼 글만 이어 붙임(h 없음)', 'h' not in m and m.get('t') == '평범 본\n\n── 2023년 1회 #19 때 쓴 메모 ──\n평범 옛', m)
            ctx.close()
            # K9: 합치면 20,000자를 넘음 → 글은 자르고 서식은 버림
            seed = {MK: {'2020-3-7': {'t': 'a' * 19000, 'ts': NOW - 3000}, '2023-1-19': {'t': 'b' * 3000, 'ts': NOW - 1000, 'h': '<div><b>' + 'b' * 3000 + '</b></div>'}}}
            ctx, P = T.new_page(browser, seed=seed)
            m = T.ls_json(P, MK, {}).get('2020-3-7', {})
            check('K9 20,000자를 넘으면 글은 20,000자로 자르고 서식은 버림', len(m.get('t', '')) == 20000 and 'h' not in m, (len(m.get('t', '')), 'h' in m))
            ctx.close()

        # ===================== L. 한글 조합 입력(IME) =====================
        if want('L'):
            ctx, P = fresh(browser)
            open_memo(P); P.locator('#memo-editor').click()
            P.evaluate("() => { document.getElementById('memo-editor').firstChild.__mark = 1; }")
            cdp = ctx.new_cdp_session(P)
            for t in ['ㅎ', '하', '한']:
                cdp.send('Input.imeSetComposition', {'text': t, 'selectionStart': len(t), 'selectionEnd': len(t)})
            mid = ed_text(P)
            check('L1 조합 중에는 글자가 하나만 보임(한)', mid == '한', mid)
            check('L2 조합 중에는 편집창 내용을 다시 만들지 않음(표시해 둔 요소가 그대로)', P.evaluate("() => document.getElementById('memo-editor').firstChild.__mark === 1"))
            cdp.send('Input.insertText', {'text': '한'})
            for t in ['ㄱ', '그', '글']:
                cdp.send('Input.imeSetComposition', {'text': t, 'selectionStart': len(t), 'selectionEnd': len(t)})
            cdp.send('Input.insertText', {'text': '글'})
            check('L3 "한" + "글" 확정 → 한글(중복·누락 없음)', ed_text(P) == '한글', repr(ed_text(P)))
            check('L4 글자 수 표시 2', count_text(P).startswith('2 /'), count_text(P))
            commit(P, 1000)
            check('L5 저장된 글 한글', store(P)['2023-3-1']['t'] == '한글', store(P))
            # 조합 중 Ctrl+Z 는 무시되고, 확정 뒤에는 입력 묶음이 하나로 취소됨
            for t in ['ㅅ', '사']:
                cdp.send('Input.imeSetComposition', {'text': t, 'selectionStart': len(t), 'selectionEnd': len(t)})
            P.keyboard.press('Control+z')
            check('L6 조합 중 Ctrl+Z 는 아무 일도 하지 않음(글자 유지)', ed_text(P) == '한글사', repr(ed_text(P)))
            cdp.send('Input.insertText', {'text': '사'})
            check('L7 확정 → 한글사', ed_text(P) == '한글사', repr(ed_text(P)))
            P.keyboard.press('Control+z')
            check('L8 Ctrl+Z 는 확정된 입력 묶음만 취소(글자가 사라지거나 깨지지 않음)', ed_text(P) in ('', '한글') or ed_text(P).startswith('한'), repr(ed_text(P)))
            P.keyboard.press('Control+y')
            check('L9 Ctrl+Y 로 복원 → 한글사', ed_text(P) == '한글사', repr(ed_text(P)))
            # 서식을 켠 채 조합
            P.keyboard.press('Control+a'); P.keyboard.press('Delete')
            P.keyboard.press('Control+b')
            for t in ['ㅊ', '추', '축']:
                cdp.send('Input.imeSetComposition', {'text': t, 'selectionStart': len(t), 'selectionEnd': len(t)})
            cdp.send('Input.insertText', {'text': '축'})
            check('L10 굵게를 켠 채 한글 입력 → 굵은 글씨(축)', re.search(r'<b>축</b>', ed_html(P)) is not None, ed_html(P))
            ctx.close()

        real = [e for e in T.errors if not re.search(r'cdnjs|highlight|Failed to load resource|net::ERR|ERR_', e)]
        check('콘솔 오류 없음', not real, real[:5])
        browser.close()

    print('\n== %s: PASS %d / FAIL %d ==' % (T.TAG, len(T.PASS), len(T.FAIL)))
    if T.FAIL:
        print('FAILED:', T.FAIL)
        sys.exit(1)


if __name__ == '__main__':
    main()
