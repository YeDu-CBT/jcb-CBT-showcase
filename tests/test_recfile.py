# -*- coding: utf-8 -*-
"""정처기 CBT: 기록 파일(내보내기·가져오기·폴더 연결) + 메모 작성 시각 테스트.
usage: test_recfile.py URL TAG
  URL = http://localhost:9881/index.html | http://localhost:9881/standalone.html | file:///.../jcb_cbt.html
폴더 연결은 진짜 폴더 선택 창을 띄울 수 없으므로, showDirectoryPicker 를 'OPFS(브라우저 안의 진짜 파일 시스템 핸들)'로 바꿔 시험한다.
OPFS 는 http 에서만 열리므로 file:// 에서는 폴더 연결 부분은 건너뛴다(화면 요소만 확인).
"""
import os
import sys, json, time, re, urllib.request, urllib.parse, datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

URL, TAG = sys.argv[1], sys.argv[2]
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_out')   # 스크린샷 등 시험 산출물
os.makedirs(SP, exist_ok=True)
IS_FILE = URL.startswith('file:')
TZ = ZoneInfo('Asia/Seoul')
DB = 'http://localhost:9881/__db/'
PASS, FAIL = [], []
errors = []
FNAME = 'jcb_cbt_records.json'
_D = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jcb_cbt', 'site', 'data.json'), encoding='utf-8'))
_IDS = {q['id'] for q in _D['questions']}
Q23 = [i for i in ['2023-1-%d' % n for n in range(1, 21)] if i in _IDS]   # 2023-1-15·19 는 다른 회차 문항에 합쳐져 id 가 사라짐


def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + str(extra)[:300]) if extra != '' else ''))


def fmt(ts):
    return datetime.datetime.fromtimestamp(ts / 1000, TZ).strftime('%Y-%m-%d %H:%M')


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


def mk_hist(ts, label='2023년 1회 · 전체', total=3, mode='study'):
    return {'ts': ts, 'sourceLabel': label, 'total': total, 'examCount': 3, 'examCorrect': 2, 'scorePct': 67, 'selfCount': 0,
            'mode': mode, 'elapsedSec': 100, 'results': [{'qid': '2023-1-1', 'inputValue': 'a', 'selfMark': None, 'status': 'ok', 'flagged': False}]}


def mk_save(sid, ts, label='2023년 1회'):
    return {'id': sid, 'ts': ts, 'sourceLabel': label, 'mode': 'study', 'ids': Q23[:3], 'idx': 1, 'answers': {'2023-1-1': 'x'},
            'selfMarks': {}, 'revealed': {}, 'flagged': {}, 'vers': {}, 'ansByVer': {}, 'timeLimitSec': 0, 'remainingSec': 0, 'elapsedSec': 50, 'answered': 1}


def rec_file(hist=(), saves=(), memos=None, **extra):
    r = {'format': 'jcb_cbt_records', 'version': 1, 'app': '정보처리기사 실기 CBT', 'exportedAt': int(time.time() * 1000), 'exportedAtText': fmt(time.time() * 1000),
         'hist': list(hist), 'saves': list(saves), 'memos': memos or {}}
    r.update(extra)
    return r


def write_tmp(name, obj):
    p = SP + '/' + name
    open(p, 'w', encoding='utf-8').write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False))
    return p


PICKER_JS = """
(function(){
  window.__PICKS = 0;
  window.showDirectoryPicker = async function(){
    window.__PICKS++;
    if(localStorage.getItem('__pick_abort') === '1'){ var e = new Error('x'); e.name = 'AbortError'; throw e; }
    var root = await navigator.storage.getDirectory();
    return root.getDirectoryHandle(window.__DIRNAME || 'cloud', {create: true});
  };
  if(window.FileSystemHandle){
    var P = FileSystemHandle.prototype, oq = P.queryPermission;
    P.queryPermission = function(o){
      if(localStorage.getItem('__perm') === 'prompt' && !window.__GRANTED) return Promise.resolve('prompt');
      return oq.call(this, o);
    };
    P.requestPermission = function(o){ window.__GRANTED = true; window.__REQ = (window.__REQ || 0) + 1; return Promise.resolve('granted'); };
  }
})();
"""


def new_device(browser, seed=None, picker=True, dirname='cloud', viewport=None, mock_claude=False, downloads=None, no_picker=False):
    ctx = browser.new_context(viewport=viewport or {'width': 1280, 'height': 1000}, timezone_id='Asia/Seoul', locale='ko-KR', accept_downloads=True)
    if mock_claude:
        ctx.add_init_script("window.__MOCK_CFG = %s;" % json.dumps({'uid': 'u_rec1'}))
        ctx.add_init_script(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_claude.js'))
        if downloads:
            ctx.add_init_script("""
(function(){
  var orig = window.claude.use; window.__DL = [];
  window.claude.use = function(name){
    if(name === 'downloads'){
      return Promise.resolve({save: function(req){
        window.__DL.push(req);
        var mode = window.__DLMODE || 'ok';
        if(mode === 'declined') return Promise.reject({code: 'declined', message: 'no'});
        return Promise.resolve({status: 'saved'});
      }});
    }
    return orig.call(window.claude, name);
  };
})();""")
        if downloads == 'null':
            ctx.add_init_script("""(function(){ var orig = window.claude.use; window.claude.use = function(n){ return n === 'downloads' ? Promise.resolve(null) : orig.call(window.claude, n); }; })();""")
    if no_picker:
        ctx.add_init_script("try{ delete window.showDirectoryPicker; }catch(e){ window.showDirectoryPicker = undefined; }")
    elif picker and not IS_FILE:
        ctx.add_init_script("window.__DIRNAME = %s;" % json.dumps(dirname))
        ctx.add_init_script(PICKER_JS)
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


def ls(page, key):
    return page.evaluate("(k) => localStorage.getItem(k)", key)


def ls_json(page, key, default=None):
    v = ls(page, key)
    return json.loads(v) if v else default


def toast(page):
    return page.evaluate("() => { const t = document.querySelector('#toast-root .toast'); return t ? t.textContent : ''; }")


def wait_toast(page, sub, timeout=5):
    return wait_until(lambda: sub in toast(page), timeout)


def modal_text(page):
    return page.evaluate("() => { const m = document.querySelector('#active-modal'); return m ? m.innerText : ''; }")


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


def memo_open(page):
    if page.locator('#memo-panel').is_hidden():
        page.locator('#btn-memo').click()
    page.wait_for_selector('#memo-panel:not([hidden])')


def goto_home_from_exam(page):
    page.locator('.exam-top .exit-btn').click()
    page.locator('#active-modal').get_by_role('button', name='저장 없이 종료', exact=True).click()
    page.wait_for_selector('#screen-home:not([hidden]) .start-bar')


def opfs_read(page, d='cloud'):
    return page.evaluate("""async (dir) => { const root = await navigator.storage.getDirectory(); const d = await root.getDirectoryHandle(dir, {create:true});
        try { const f = await (await d.getFileHandle('jcb_cbt_records.json')).getFile(); return await f.text(); } catch(e){ return null; } }""", d)


def opfs_write(page, text, d='cloud'):
    return page.evaluate("""async ([dir, text]) => { const root = await navigator.storage.getDirectory(); const d = await root.getDirectoryHandle(dir, {create:true});
        const fh = await d.getFileHandle('jcb_cbt_records.json', {create:true}); const w = await fh.createWritable(); await w.write(text); await w.close(); return true; }""", [d, text])


def opfs_json(page, d='cloud'):
    t = opfs_read(page, d)
    return json.loads(t) if t else None


def fstate(page):
    return page.locator('#file-bar').get_attribute('data-state')


def main():
    now = int(time.time() * 1000)
    H = 3600 * 1000
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')

        # =================================================================
        # 1. 화면 · 내보낼 것이 없을 때
        # =================================================================
        ctx, A = new_device(browser)
        check('칩: Ver 2.5 · 수정 21회', A.locator('.app-header-ver').inner_text().strip() == 'Ver 2.5 · 수정 21회')
        check('칩 title', A.locator('.app-header-ver').get_attribute('title') == '최초 공개 이후 수정 21회 반영 (Ver 2.5)')
        check('기록 파일 구역이 하나', A.locator('#file-bar').count() == 1)
        check('내보내기·가져오기 버튼', A.locator('#btn-rec-export').count() == 1 and A.locator('#btn-rec-import').count() == 1)
        check('안내문: 되살아날 수 있음 + 작성 시각', '되살아날 수 있습니다' in A.locator('.fb-text').inner_text() and '시각' in A.locator('.fb-text').inner_text())
        A.locator('#btn-rec-export').click()
        check('내보낼 게 없으면 안내 토스트', wait_toast(A, '내보낼 내용이 아직 없습니다'), toast(A))
        if not IS_FILE:
            check('폴더 연결 버튼(크롬·엣지)', A.locator('#btn-file-connect').count() == 1)
            check('처음 상태: 연결 안 됨', fstate(A) == 'off' and '폴더 연결 안 됨' in A.locator('.fb-state-text').inner_text())
        else:
            check('(file://) 폴더 연결 버튼 표시', A.locator('#btn-file-connect').count() == 1)
        ctx.close()

        # =================================================================
        # 2. 내보내기 — 파일 내용
        # =================================================================
        t_h1, t_h2 = now - 5 * H, now - 30 * H
        t_s1 = now - 2 * H
        t_m1_c, t_m1_ts, t_m2 = now - 26 * H, now - 3 * H, now - 50 * H
        seed = {
            'jcb_cbt_history_v1': [mk_hist(t_h1), mk_hist(t_h2, '2021년 2회 · 전체', 5, 'exam')],
            'jcb_cbt_saves_v1': [mk_save('sA1', t_s1)],
            'jcb_cbt_memos_v1': {'2023-1-1': {'t': '첫 메모\n둘째 줄 "따옴표" 한글', 'ts': t_m1_ts, 'c': t_m1_c}, '2023-1-2': {'t': '옛 메모(c 없음)', 'ts': t_m2}},
        }
        ctx, A = new_device(browser, seed=seed)
        check('시드된 기록이 처음 화면에 보임', A.locator('.history-row').count() == 2)
        check('기록 줄 title 에 제출한 전체 시각', A.locator('.history-row').first.get_attribute('title') == '제출한 시각 ' + fmt(t_h1), A.locator('.history-row').first.get_attribute('title'))
        with A.expect_download() as dl:
            A.locator('#btn-rec-export').click()
        d = dl.value
        check('파일 이름 형식', re.fullmatch(r'jcb_cbt_records_\d{8}-\d{4}\.json', d.suggested_filename) is not None, d.suggested_filename)
        raw = open(d.path(), encoding='utf-8').read()
        rec = json.loads(raw)
        check('format/version', rec['format'] == 'jcb_cbt_records' and rec['version'] == 1)
        check('counts', rec['counts'] == {'hist': 2, 'saves': 1, 'memos': 2}, rec['counts'])
        check('내보낸 시각 글자', re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', rec['exportedAtText']) is not None, rec['exportedAtText'])
        ri = rec['readable_index']
        check('읽기용 목차 5줄', len(ri) == 5, ri)
        check('목차는 최신순', ri[0].startswith(fmt(t_s1)) and ri[-1].startswith(fmt(t_m2)), ri)
        check('목차에 모든 시각(YYYY-MM-DD HH:mm)', all(re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}( \(처음 작성 \d{4}-\d{2}-\d{2} \d{2}:\d{2}\))? · ', x) for x in ri))
        check('메모 목차: 처음 작성 시각 병기', any('처음 작성 ' + fmt(t_m1_c) in x for x in ri), ri)
        check('기록 항목에 tsText', rec['hist'][0]['tsText'] == fmt(t_h1) and rec['saves'][0]['tsText'] == fmt(t_s1))
        check('메모 항목에 ts/c/tsText/cText', rec['memos']['2023-1-1']['ts'] == t_m1_ts and rec['memos']['2023-1-1']['c'] == t_m1_c and
              rec['memos']['2023-1-1']['tsText'] == fmt(t_m1_ts) and rec['memos']['2023-1-1']['cText'] == fmt(t_m1_c))
        check('c 없는 옛 메모는 c 없이', 'c' not in rec['memos']['2023-1-2'])
        check('한글·줄바꿈·따옴표 보존', rec['memos']['2023-1-1']['t'] == '첫 메모\n둘째 줄 "따옴표" 한글')
        check('UTF-8 한글이 그대로(이스케이프 아님)', '첫 메모' in raw)
        check('내보낸 뒤 토스트', wait_toast(A, '내보냈습니다'), toast(A))
        time.sleep(1.8)
        check('내려받기용 임시 링크가 남지 않음', A.locator('a[download]').count() == 0)
        exported_path = write_tmp('rec_export_%s.json' % TAG, raw)
        ctx.close()

        # =================================================================
        # 3. 가져오기 — 빈 기기에 합치기
        # =================================================================
        ctx, B = new_device(browser)
        with B.expect_file_chooser() as fc:
            B.locator('#btn-rec-import').click()
        fc.value.set_files(exported_path)
        check('가져오기 요약 창', wait_until(lambda: B.locator('#active-modal').count() == 1), modal_text(B))
        mt = modal_text(B)
        check('요약: 새로 추가 5건', '새로 추가 5건' in mt and '갱신 0건' in mt, mt[:200])
        check('요약: 지우지 않음·되살아날 수 있음 안내', '지우지 않습니다' in mt and '되살아날 수 있으니' in mt)
        check('요약: 5줄 모두 시각 표시', B.locator('.imp-row').count() == 5 and all(re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', B.locator('.imp-when').nth(i).inner_text()) for i in range(5)))
        check('요약: 메모 줄에 처음 작성 시각', any('처음 작성 ' + fmt(t_m1_c) in B.locator('.imp-when').nth(i).inner_text() for i in range(5)))
        check('요약: 추가 배지', B.locator('.imp-badge.add').count() == 5)
        B.locator('#active-modal').get_by_role('button', name='취소', exact=True).click()
        check('취소하면 아무것도 바뀌지 않음', ls(B, 'jcb_cbt_history_v1') is None and ls(B, 'jcb_cbt_memos_v1') is None and ls(B, 'jcb_cbt_saves_v1') is None)
        with B.expect_file_chooser() as fc:
            B.locator('#btn-rec-import').click()
        fc.value.set_files(exported_path)
        B.wait_for_selector('#active-modal')
        B.locator('#active-modal').get_by_role('button', name='합치기', exact=True).click()
        check('합친 토스트', wait_toast(B, '합쳤습니다: 새로 5건'), toast(B))
        hist = ls_json(B, 'jcb_cbt_history_v1', [])
        saves = ls_json(B, 'jcb_cbt_saves_v1', [])
        memos = ls_json(B, 'jcb_cbt_memos_v1', {})
        check('기록 2건·최신순', len(hist) == 2 and hist[0]['ts'] == t_h1 and hist[1]['ts'] == t_h2, [h['ts'] for h in hist])
        check('저장 1칸', len(saves) == 1 and saves[0]['id'] == 'sA1')
        check('메모 2개·c 보존', set(memos) == {'2023-1-1', '2023-1-2'} and memos['2023-1-1']['c'] == t_m1_c and memos['2023-1-1']['ts'] == t_m1_ts, memos)
        check('읽기용 글자(tsText 등)가 저장소로 들어오지 않음', 'tsText' not in hist[0] and 'tsText' not in saves[0] and 'tsText' not in memos['2023-1-1'] and 'cText' not in memos['2023-1-1'])
        check('처음 화면에 기록 2줄·이어서 풀기 구역', B.locator('.history-row').count() == 2 and B.locator('#save-section').count() == 1)
        # 같은 파일 한 번 더 → 합칠 게 없음
        with B.expect_file_chooser() as fc:
            B.locator('#btn-rec-import').click()
        fc.value.set_files(exported_path)
        check('같은 파일 재가져오기: 합칠 새 내용 없음', wait_toast(B, '합칠 새 내용이 없습니다') and B.locator('#active-modal').count() == 0, toast(B))

        # 새 시각이 이긴다 / 옛 시각은 무시
        newer = json.loads(raw)
        newer['memos']['2023-1-1']['t'] = '다른 기기에서 고친 메모'
        newer['memos']['2023-1-1']['ts'] = t_m1_ts + H
        newer['memos']['2023-1-1']['c'] = t_m1_c - 5 * H            # 더 이른 처음 작성 시각
        newer['memos']['2023-1-2']['t'] = '더 옛날 글(무시되어야 함)'
        newer['memos']['2023-1-2']['ts'] = t_m2 - H
        newer['saves'][0]['ts'] = t_s1 + H
        newer['saves'][0]['answered'] = 7
        p_new = write_tmp('rec_newer_%s.json' % TAG, newer)
        with B.expect_file_chooser() as fc:
            B.locator('#btn-rec-import').click()
        fc.value.set_files(p_new)
        B.wait_for_selector('#active-modal')
        mt = modal_text(B)
        check('갱신 2건(메모 1·저장 1), 이미 같거나 더 최신 3건', '갱신 2건' in mt and '새로 추가 0건' in mt and '이미 같거나 이 기기가 더 최신 3건' in mt, mt[:260])
        check('갱신 배지 2개', B.locator('.imp-badge.upd').count() == 2)
        B.locator('#active-modal').get_by_role('button', name='합치기', exact=True).click()
        time.sleep(0.3)
        memos = ls_json(B, 'jcb_cbt_memos_v1', {})
        saves = ls_json(B, 'jcb_cbt_saves_v1', [])
        check('늦은 시각의 메모가 이김', memos['2023-1-1']['t'] == '다른 기기에서 고친 메모' and memos['2023-1-1']['ts'] == t_m1_ts + H)
        check('처음 작성 시각은 더 이른 쪽', memos['2023-1-1']['c'] == t_m1_c - 5 * H, memos['2023-1-1'])
        check('이른 시각의 메모는 무시', memos['2023-1-2']['t'] == '옛 메모(c 없음)')
        check('저장 칸 갱신', saves[0]['answered'] == 7 and saves[0]['ts'] == t_s1 + H)

        # 지운 기록은 파일에 남아 있으면 되살아난다(허용된 동작) + 작성 시각이 보인다
        B.locator('#save-section button', has_text='삭제').first.click()
        B.locator('#active-modal').get_by_role('button', name='삭제', exact=True).click()
        time.sleep(0.3)
        check('저장 칸을 지웠다', len(ls_json(B, 'jcb_cbt_saves_v1', [])) == 0)
        with B.expect_file_chooser() as fc:
            B.locator('#btn-rec-import').click()
        fc.value.set_files(p_new)
        B.wait_for_selector('#active-modal')
        rows = [B.locator('.imp-row').nth(i).inner_text() for i in range(B.locator('.imp-row').count())]
        check('지운 저장 칸이 "추가"로 다시 나타남 + 저장 시각 표시', len(rows) == 1 and '추가' in rows[0] and fmt(t_s1 + H) in rows[0] and '중간 저장' in rows[0], rows)
        B.locator('#active-modal').get_by_role('button', name='합치기', exact=True).click()
        time.sleep(0.3)
        check('되살아남(수동 가져오기는 지움 표시를 무시)', len(ls_json(B, 'jcb_cbt_saves_v1', [])) == 1)
        ctx.close()

        # =================================================================
        # 4. 가져오기 — 잘못된 파일 · 검증
        # =================================================================
        ctx, C = new_device(browser)
        def try_import(path):
            with C.expect_file_chooser() as fc:
                C.locator('#btn-rec-import').click()
            fc.value.set_files(path)
            time.sleep(0.5)
        try_import(write_tmp('bad1_%s.json' % TAG, 'this is not json {'))
        check('JSON 아님 → 거절', wait_toast(C, '가져오지 못했습니다') and 'JSON 형식이 아닙니다' in toast(C), toast(C))
        try_import(write_tmp('bad2_%s.json' % TAG, {'hello': 1}))
        check('다른 형식 → 거절', 'format: jcb_cbt_records' in toast(C), toast(C))
        try_import(write_tmp('bad3_%s.json' % TAG, rec_file(version=2)))
        check('더 새 버전 → 거절', '파일 버전(2)' in toast(C), toast(C))
        try_import(write_tmp('bad4_%s.json' % TAG, '[1,2,3]'))
        check('배열 → 거절', 'format: jcb_cbt_records' in toast(C), toast(C))
        check('거절하면 저장소가 비어 있음', ls(C, 'jcb_cbt_history_v1') is None and ls(C, 'jcb_cbt_memos_v1') is None)
        # 부분 오류: 잘못된 항목은 건너뛰고 나머지만
        big_t = 'x' * 25000
        mixed = rec_file(
            hist=[mk_hist(now - 3 * H, '<img src=x onerror="window.__XSS=1"> 라벨'), {'ts': 'abc'}, {'ts': now + 10 * 86400000}, 'text', {'ts': now - 4 * H, 'results': 'nope'}],
            saves=[mk_save('ok_1', now - H), {'id': '../evil', 'ts': now, 'ids': []}, {'id': 'noids', 'ts': now}],
            memos={'2023-1-3': {'t': big_t, 'ts': now - H}, '9999-9-9': {'t': 'no such question', 'ts': now - H}, '2023-1-4': {'t': '   ', 'ts': now - H},
                   '2023-1-5': {'t': 'future', 'ts': now + 9 * 86400000}, '2023-1-6': {'t': '정상', 'ts': now - 2 * H, 'c': now + 5 * H}})
        try_import(write_tmp('mixed_%s.json' % TAG, mixed))
        C.wait_for_selector('#active-modal')
        mt = modal_text(C)
        check('요약: 형식 오류 건너뜀 건수', '형식 오류로 건너뜀 8건' in mt, mt[:500].replace('\n',' / '))      # 기록 4 + 저장 2 + 메모(빈 글·미래 시각) 2 → 8? 아래에서 실제 값 확인
        check('요약: 없는 문항 메모 건너뜀 1건', '이 사이트에 없는 문항의 메모 1건' in mt, mt[:400])
        check('XSS: 요약 창에 img 요소가 생기지 않음', C.locator('#active-modal img').count() == 0)
        C.locator('#active-modal').get_by_role('button', name='합치기', exact=True).click()
        time.sleep(0.4)
        check('XSS: 스크립트가 실행되지 않음', C.evaluate("() => window.__XSS === undefined"))
        check('XSS: 처음 화면 기록 줄에도 img 요소 없음, 글자로만', C.locator('.history-row img').count() == 0 and '<img src=x' in C.locator('.history-row').first.inner_text())
        memos = ls_json(C, 'jcb_cbt_memos_v1', {})
        check('메모: 길이 상한(20000)으로 잘림', len(memos.get('2023-1-3', {}).get('t', '')) == 20000)
        check('메모: 없는 문항·빈 글·미래 시각은 들어오지 않음', set(memos) == {'2023-1-3', '2023-1-6'}, list(memos))
        check('메모: 처음 작성 시각이 수정 시각보다 늦으면 버림', 'c' not in memos['2023-1-6'], memos['2023-1-6'])
        check('기록 1건·저장 1칸만 들어옴', len(ls_json(C, 'jcb_cbt_history_v1', [])) == 1 and [s['id'] for s in ls_json(C, 'jcb_cbt_saves_v1', [])] == ['ok_1'])
        # 보관 한도(25건)
        many = rec_file(hist=[mk_hist(now - (i + 1) * 60000, '기록%d' % i) for i in range(30)])
        try_import(write_tmp('many_%s.json' % TAG, many))
        C.wait_for_selector('#active-modal')
        mt = modal_text(C)
        check('기록 30건: 보관 한도 밖 제외 문구', '보관 한도(25건) 밖이라 제외' in mt, mt[:400])
        C.locator('#active-modal').get_by_role('button', name='합치기', exact=True).click()
        time.sleep(0.4)
        h = ls_json(C, 'jcb_cbt_history_v1', [])
        check('기록은 최신 25건만 남음', len(h) == 25 and h == sorted(h, key=lambda x: -x['ts']), len(h))
        ctx.close()

        # =================================================================
        # 5. 메모 — 처음 작성 · 마지막 수정 시각
        # =================================================================
        mseed = {'jcb_cbt_memos_v1': {q: {'t': '시드 메모', 'ts': t_m1_ts, 'c': t_m1_c} for q in Q23}}
        ctx, M = new_device(browser, seed=mseed)
        start_study(M)
        memo_open(M)
        want = '처음 작성 %s · 마지막 수정 %s' % (fmt(t_m1_c), fmt(t_m1_ts))
        check('메모패드에 처음 작성·마지막 수정 시각', M.locator('#memo-when').inner_text() == want, M.locator('#memo-when').inner_text())
        M.locator('#memo-editor').click()
        M.keyboard.press('End')
        M.keyboard.type(' 추가')
        time.sleep(1.0)
        memos = ls_json(M, 'jcb_cbt_memos_v1', {})
        q1 = [q for q in Q23 if memos[q]['t'] != '시드 메모']
        check('고치면 ts 는 새로, c 는 그대로', len(q1) == 1 and memos[q1[0]]['c'] == t_m1_c and memos[q1[0]]['ts'] > now - 60000, memos.get(q1[0]) if q1 else memos)
        now_txt = fmt(memos[q1[0]]['ts']) if q1 else ''
        check('표시가 마지막 수정 시각으로 바뀜', M.locator('#memo-when').inner_text() == '처음 작성 %s · 마지막 수정 %s' % (fmt(t_m1_c), now_txt), M.locator('#memo-when').inner_text())
        # 다음 문항: 시드 메모 시각, 그다음 새 메모
        M.locator('#exam-qgrid button', has_text=re.compile(r'^2$')).click()
        time.sleep(0.2)
        check('다른 문항은 그 문항의 시각', M.locator('#memo-when').inner_text() == want, M.locator('#memo-when').inner_text())
        ctx.close()
        ctx, M = new_device(browser)
        start_study(M)
        memo_open(M)
        check('메모가 없으면 시각 줄이 비어 숨겨짐', M.locator('#memo-when').inner_text() == '' and M.locator('#memo-when').is_hidden())
        M.locator('#memo-editor').click()
        M.keyboard.type('새 메모')
        time.sleep(1.0)
        memos = ls_json(M, 'jcb_cbt_memos_v1', {})
        k = list(memos)[0]
        check('새 메모는 c == ts', memos[k]['c'] == memos[k]['ts'])
        check('새 메모 표시: 작성 시각', M.locator('#memo-when').inner_text() == '작성 ' + fmt(memos[k]['ts']), M.locator('#memo-when').inner_text())
        ctx.close()
        # 옛 메모(c 없음)
        lseed = {'jcb_cbt_memos_v1': {q: {'t': '옛', 'ts': t_m2} for q in Q23}}
        ctx, M = new_device(browser, seed=lseed)
        start_study(M)
        memo_open(M)
        check('c 없는 옛 메모: 마지막 수정만 표시', M.locator('#memo-when').inner_text() == '마지막 수정 ' + fmt(t_m2), M.locator('#memo-when').inner_text())
        M.locator('#memo-editor').click()
        M.keyboard.type('!')
        time.sleep(1.0)
        memos = ls_json(M, 'jcb_cbt_memos_v1', {})
        k = [q for q in Q23 if memos[q]['t'] != '옛'][0]
        check('옛 메모를 고치면 c = 그 전의 ts', memos[k]['c'] == t_m2, memos[k])
        ctx.close()

        # =================================================================
        # 6. 폴더 연결 (OPFS 로 흉내 낸 진짜 폴더 핸들) — http 에서만
        # =================================================================
        if not IS_FILE:
            fseed = {
                'jcb_cbt_history_v1': [mk_hist(t_h1)],
                'jcb_cbt_saves_v1': [mk_save('sF1', t_s1), mk_save('sF2', t_s1 - H)],
                'jcb_cbt_memos_v1': {'2023-1-1': {'t': '폴더 메모', 'ts': t_m1_ts, 'c': t_m1_c}},
            }
            ctx, F = new_device(browser, seed=fseed, dirname='cloudA')
            F.locator('#btn-file-connect').click()
            check('연결 → 켜짐', wait_until(lambda: fstate(F) == 'on', 6), fstate(F))
            check('연결 토스트', '폴더를 연결했습니다' in toast(F), toast(F))
            jf = opfs_json(F, 'cloudA')
            check('폴더에 기록 파일이 만들어짐', jf is not None and jf['format'] == 'jcb_cbt_records', jf and jf.get('counts'))
            check('내용: 기록1·저장2·메모1', jf['counts'] == {'hist': 1, 'saves': 2, 'memos': 1}, jf['counts'])
            check('상태 문구: 폴더 이름·파일 이름', 'cloudA' in F.locator('.fb-state-text').inner_text() and FNAME in F.locator('.fb-state-text').inner_text(), F.locator('.fb-state-text').inner_text())
            check('버튼: 지금 맞추기·연결 해제, 폴더 연결 버튼은 사라짐', F.locator('#btn-file-sync').count() == 1 and F.locator('#btn-file-disconnect').count() == 1 and F.locator('#btn-file-connect').count() == 0)
            check('저장본 안내 문구가 폴더 연결 상태로', '연결한 폴더의 기록 파일' in F.locator('.save-note').inner_text(), F.locator('.save-note').inner_text())

            # 6-1. 이 기기에서 지우면 파일에서도 사라지고 되살아나지 않는다
            F.locator('#save-section button', has_text='삭제').first.click()      # 최신 저장 칸(sF1)
            F.locator('#active-modal').get_by_role('button', name='삭제', exact=True).click()
            ok = wait_until(lambda: (opfs_json(F, 'cloudA') or {}).get('counts', {}).get('saves') == 1, 6)
            check('지운 저장 칸이 파일에서도 사라짐', ok, (opfs_json(F, 'cloudA') or {}).get('counts'))
            F.locator('#btn-file-sync').click()
            time.sleep(0.8)
            check('지금 맞추기 후에도 되살아나지 않음(지움 표시)', [s['id'] for s in ls_json(F, 'jcb_cbt_saves_v1', [])] == ['sF2'])
            tomb = ls_json(F, 'jcb_cbt_filetomb_v1', {})
            check('지움 표시가 저장소에 남음', 'save_sF1' in tomb, tomb)
            # 다른 기기가 같은 칸(옛 시각)을 다시 파일에 넣어도 무시, 더 새로운 수정이면 받는다
            cur = opfs_json(F, 'cloudA')
            cur['saves'].append(dict(mk_save('sF1', t_s1), tsText='x'))
            opfs_write(F, json.dumps(cur, ensure_ascii=False), 'cloudA')
            F.locator('#btn-file-sync').click(); time.sleep(0.8)
            check('옛 시각의 같은 칸은 무시', [s['id'] for s in ls_json(F, 'jcb_cbt_saves_v1', [])] == ['sF2'])
            check('무시한 항목은 파일에서도 정리됨', (opfs_json(F, 'cloudA') or {}).get('counts', {}).get('saves') == 1, (opfs_json(F, 'cloudA') or {}).get('counts'))
            cur = opfs_json(F, 'cloudA')
            cur['saves'].append(mk_save('sF1', int(time.time() * 1000) + 5000))
            opfs_write(F, json.dumps(cur, ensure_ascii=False), 'cloudA')
            F.locator('#btn-file-sync').click(); time.sleep(0.8)
            check('지운 뒤에 더 새로 고쳐진 칸은 받음', sorted(s['id'] for s in ls_json(F, 'jcb_cbt_saves_v1', [])) == ['sF1', 'sF2'])

            # 6-2. 메모를 쓰면 자동으로 파일에 반영
            start_study(F)
            memo_open(F)
            F.locator('#memo-editor').click()
            F.keyboard.type('폴더 자동 저장')
            ok = wait_until(lambda: any('폴더 자동 저장' in (m.get('t') or '') for m in (opfs_json(F, 'cloudA') or {}).get('memos', {}).values()), 7)
            check('메모 입력이 몇 초 안에 파일에 반영됨', ok)
            jf = opfs_json(F, 'cloudA')
            mm = [m for m in jf['memos'].values() if '폴더 자동 저장' in m['t']][0]
            check('파일의 메모에 시각 글자', re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', mm['tsText']) is not None and re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', mm['cText']) is not None and mm['cText'] < mm['tsText'], mm)
            check('메모패드 문구: 폴더 기록 파일에도 저장', '연결한 폴더의 기록 파일' in F.locator('#memo-state').inner_text(), F.locator('#memo-state').inner_text())
            goto_home_from_exam(F)

            # 6-3. 다른 기기가 파일에 넣은 것을 받는다
            ext_ts = int(time.time() * 1000) - 7 * H
            cur = opfs_json(F, 'cloudA')
            cur['hist'].append(mk_hist(ext_ts, '다른 기기 기록', 9))
            cur['memos']['2023-1-9'] = {'t': '다른 기기 메모', 'ts': ext_ts, 'c': ext_ts - H}
            opfs_write(F, json.dumps(cur, ensure_ascii=False), 'cloudA')
            F.locator('#btn-file-sync').click()
            check('파일에서 합쳤다는 토스트', wait_toast(F, '에서 2건을 합쳤습니다', 5), toast(F))
            check('토스트: 되살아남 주의 문구', '작성 시각을 확인하세요' in toast(F))
            memos = ls_json(F, 'jcb_cbt_memos_v1', {})
            check('다른 기기 메모가 들어옴(c 보존)', memos.get('2023-1-9', {}).get('c') == ext_ts - H, memos.get('2023-1-9'))
            check('처음 화면 기록 줄이 늘어남', F.locator('.history-row').count() == 2)
            check('상태 문구에 합친 건수', '파일에서 합친 2건' in F.locator('.fb-state-text').inner_text(), F.locator('.fb-state-text').inner_text())

            # 6-4. 새로고침 → 기억해 둔 폴더를 자동으로 다시 연다
            F.reload()
            F.wait_for_selector('#screen-home:not([hidden]) .start-bar')
            check('새로고침 뒤 자동으로 켜짐(허용 유지)', wait_until(lambda: fstate(F) == 'on', 6), fstate(F))
            check('연결 버튼 없이 지금 맞추기만', F.locator('#btn-file-connect').count() == 0 and F.locator('#btn-file-sync').count() == 1)
            ctx.close()

            # 6-5. 허용을 다시 받아야 하는 경우(브라우저 재시작 뒤처럼)
            ctx, G = new_device(browser, seed=dict(fseed, **{'__perm': 'prompt'}), dirname='cloudG')
            G.locator('#btn-file-connect').click()
            check('G: 연결 켜짐', wait_until(lambda: fstate(G) == 'on', 6), fstate(G))
            G.reload()
            G.wait_for_selector('#screen-home:not([hidden]) .start-bar')
            check('허용이 필요하면 needperm 상태', wait_until(lambda: fstate(G) == 'needperm', 6), fstate(G))
            check('[연결 복원] 버튼, 문구', G.locator('#btn-file-restore').count() == 1 and '쓰기 허용을 다시 받아야' in G.locator('.fb-state-text').inner_text())
            before = opfs_read(G, 'cloudG')
            G.locator('#btn-file-restore').click()
            check('복원하면 켜짐', wait_until(lambda: fstate(G) == 'on', 6), fstate(G))
            check('requestPermission 이 호출됨', G.evaluate("() => window.__REQ") == 1)
            ctx.close()

            # 6-6. 깨진 파일은 덮어쓰지 않는다
            ctx, K = new_device(browser, seed=fseed, dirname='cloudK')
            K.locator('#btn-file-connect').click()
            wait_until(lambda: fstate(K) == 'on', 6)
            opfs_write(K, '{"format": "jcb_cbt_records", "version": 1, "hist": [ {"ts": 12', 'cloudK')      # 잘린 JSON(클라우드가 반쯤 받은 파일)
            K.locator('#btn-file-sync').click()
            check('깨진 파일 → 오류 상태', wait_until(lambda: fstate(K) == 'error', 5), fstate(K))
            check('오류 문구: 덮어쓰지 않음', '덮어쓰지 않았습니다' in K.locator('.fb-state-text').inner_text(), K.locator('.fb-state-text').inner_text())
            check('파일이 그대로(덮어쓰이지 않음)', (opfs_read(K, 'cloudK') or '').startswith('{"format": "jcb_cbt_records", "version": 1, "hist": [ {"ts": 12'))
            # 메모를 써도 깨진 파일은 건드리지 않는다
            start_study(K); memo_open(K)
            K.locator('#memo-editor').click(); K.keyboard.type('깨진 파일 중에도 쓰는 메모')
            time.sleep(3.0)
            check('입력이 있어도 깨진 파일은 그대로', (opfs_read(K, 'cloudK') or '').startswith('{"format": "jcb_cbt_records", "version": 1, "hist": [ {"ts": 12'))
            check('메모는 이 브라우저에는 저장됨', any('깨진 파일 중에도' in m['t'] for m in ls_json(K, 'jcb_cbt_memos_v1', {}).values()))
            goto_home_from_exam(K)
            # 고쳐진 파일(정상 JSON)이 오면 다시 맞춰진다
            good = rec_file(hist=[mk_hist(now - 40 * H, '복구된 기록')])
            opfs_write(K, json.dumps(good, ensure_ascii=False), 'cloudK')
            K.locator('#btn-file-sync').click()
            check('정상 파일이 오면 다시 켜짐', wait_until(lambda: fstate(K) == 'on', 6), fstate(K))
            jf = opfs_json(K, 'cloudK')
            check('합친 결과가 파일에 다시 쓰임(메모 포함)', jf is not None and jf['counts']['hist'] >= 2 and any('깨진 파일 중에도' in m['t'] for m in jf['memos'].values()), jf and jf['counts'])
            # 6-7. 연결 해제
            K.locator('#btn-file-disconnect').click()
            check('연결 해제: 상태 꺼짐·연결 버튼 복귀', fstate(K) == 'off' and K.locator('#btn-file-connect').count() == 1)
            check('해제해도 파일은 그대로', opfs_read(K, 'cloudK') is not None)
            K.reload(); K.wait_for_selector('#screen-home:not([hidden]) .start-bar')
            time.sleep(0.6)
            check('해제 뒤 새로고침해도 연결되지 않음', fstate(K) == 'off')
            # 6-8. 폴더 선택 취소
            K.evaluate("() => localStorage.setItem('__pick_abort','1')")
            K.locator('#btn-file-connect').click()
            check('선택 취소 → 안내 토스트·상태 그대로', wait_toast(K, '고르지 않았거나') and fstate(K) == 'off', toast(K))
            ctx.close()

            # 6-9. 두 컴퓨터가 같은 폴더(클라우드)를 쓰는 흐름 — 파일 복사로 클라우드 동기화를 흉내
            ctx, D1 = new_device(browser, seed={'jcb_cbt_memos_v1': {'2023-1-1': {'t': '컴퓨터1 메모', 'ts': now - 9 * H, 'c': now - 9 * H}}}, dirname='pc1')
            D1.locator('#btn-file-connect').click(); wait_until(lambda: fstate(D1) == 'on', 6)
            file1 = opfs_read(D1, 'pc1')
            ctx2, D2 = new_device(browser, seed={'jcb_cbt_memos_v1': {'2023-1-2': {'t': '컴퓨터2 메모', 'ts': now - 8 * H, 'c': now - 8 * H}},
                                                'jcb_cbt_history_v1': [mk_hist(now - 6 * H, '컴퓨터2 기록')]}, dirname='pc2')
            opfs_write(D2, file1, 'pc2')                       # 클라우드가 파일을 PC2 폴더로 내려보냄
            D2.locator('#btn-file-connect').click()
            check('PC2: 연결하자 PC1 의 메모를 합침', wait_until(lambda: '컴퓨터1 메모' in (ls(D2, 'jcb_cbt_memos_v1') or ''), 6), toast(D2))
            check('PC2: 자기 것도 유지', '컴퓨터2 메모' in ls(D2, 'jcb_cbt_memos_v1') and D2.locator('.history-row').count() == 1)
            jf2 = opfs_json(D2, 'pc2')
            check('PC2: 합친 결과를 파일에 씀(메모 2·기록 1)', jf2['counts']['memos'] == 2 and jf2['counts']['hist'] == 1, jf2['counts'])
            opfs_write(D1, json.dumps(jf2, ensure_ascii=False), 'pc1')       # 클라우드가 PC1 로 내려보냄
            D1.locator('#btn-file-sync').click()
            check('PC1: 맞추면 PC2 의 메모·기록이 들어옴', wait_until(lambda: '컴퓨터2 메모' in (ls(D1, 'jcb_cbt_memos_v1') or '') and D1.locator('.history-row').count() == 1, 6))
            ctx2.close(); ctx.close()

            # 6-10. 폴더 연결을 못 쓰는 브라우저(파이어폭스·사파리처럼 API 없음)
            ctx, N = new_device(browser, no_picker=True)
            check('API 없음: 폴더 연결 버튼 없음', N.locator('#btn-file-connect').count() == 0)
            check('API 없음: 안내 문구', '폴더 연결을 쓸 수 없습니다' in N.locator('.fb-note').inner_text())
            check('API 없음: 내보내기·가져오기는 있음', N.locator('#btn-rec-export').count() == 1 and N.locator('#btn-rec-import').count() == 1)
            ctx.close()
        else:
            ctx, F = new_device(browser, picker=False)
            F.evaluate("() => { window.showDirectoryPicker = () => Promise.reject(Object.assign(new Error('x'), {name:'AbortError'})); }")
            F.locator('#btn-file-connect').click()
            check('(file://) 선택 취소 안내', wait_toast(F, '고르지 않았거나'), toast(F))
            ctx.close()

        # =================================================================
        # 7. Artifact 화면(가짜 window.claude): 폴더 연결 숨김, downloads 로 저장, 가져오면 서버로도 올라감
        # =================================================================
        if not IS_FILE and URL.endswith('index.html'):
            urllib.request.urlopen(urllib.request.Request(DB + 'reset', method='POST', data=b'{}'))
            aseed = {'jcb_cbt_history_v1': [mk_hist(t_h1)], 'jcb_cbt_memos_v1': {'2023-1-1': {'t': '아티팩트 메모', 'ts': t_m1_ts, 'c': t_m1_c}}}
            ctx, R = new_device(browser, seed=aseed, mock_claude=True, downloads='ok')
            check('Artifact: 동기화 켜짐', wait_until(lambda: R.locator('#sync-bar').get_attribute('data-state') == 'on', 6))
            check('Artifact: 폴더 연결 버튼 숨김', R.locator('#btn-file-connect').count() == 0)
            check('Artifact: 안내 문구', '기기 간 동기화' in R.locator('.fb-note').inner_text(), R.locator('.fb-note').inner_text())
            R.locator('#btn-rec-export').click()
            check('Artifact: downloads.save 호출', wait_until(lambda: R.evaluate("() => window.__DL.length") == 1, 4))
            dlreq = R.evaluate("() => window.__DL[0]")
            check('Artifact: .json 이름·내용 파싱', re.fullmatch(r'jcb_cbt_records_\d{8}-\d{4}\.json', dlreq['filename']) and json.loads(dlreq['data'])['counts']['memos'] == 1, dlreq['filename'])
            check('Artifact: 저장 토스트(다운로드 폴더 문구 없음)', wait_toast(R, '내보냈습니다') and '다운로드 폴더' not in toast(R), toast(R))
            R.evaluate("() => { window.__DLMODE = 'declined'; }")
            R.locator('#btn-rec-export').click()
            check('Artifact: 저장 거절 → 취소 토스트', wait_toast(R, '저장을 취소했습니다'), toast(R))
            # 가져오기 → 서버 문서로도 올라간다
            imp = rec_file(hist=[mk_hist(now - 20 * H, '가져온 기록')], saves=[mk_save('sImp', now - 21 * H)], memos={'2023-1-7': {'t': '가져온 메모', 'ts': now - 22 * H, 'c': now - 23 * H}})
            with R.expect_file_chooser() as fc:
                R.locator('#btn-rec-import').click()
            fc.value.set_files(write_tmp('art_imp_%s.json' % TAG, imp))
            R.wait_for_selector('#active-modal')
            R.locator('#active-modal').get_by_role('button', name='합치기', exact=True).click()
            def srv_docs():
                return json.load(urllib.request.urlopen(DB + 'dump'))['docs']
            ok = wait_until(lambda: any(k.endswith('/hist_%d' % (now - 20 * H)) for k in srv_docs()) and any(k.endswith('/save_sImp') for k in srv_docs()) and any(k.endswith('/memo_2023-1-7') for k in srv_docs()), 8)
            check('Artifact: 가져온 기록·저장·메모가 서버 문서로 올라감', ok, [k.split('/')[-1] for k in srv_docs()])
            md = [d for k, d in srv_docs().items() if k.endswith('/memo_2023-1-7')]
            check('Artifact: 서버 메모 문서에 c(처음 작성 시각)', md and md[0].get('c') == now - 23 * H, md)
            ctx.close()
            # downloads 기능이 없는 화면 → 글로 보여 주기
            ctx, R2 = new_device(browser, seed=aseed, mock_claude=True, downloads='null')
            R2.locator('#btn-rec-export').click()
            check('Artifact(downloads 없음): 글로 보여주는 창', wait_until(lambda: R2.locator('#active-modal textarea.copy-textarea').count() == 1, 4))
            txt = R2.locator('#active-modal textarea.copy-textarea').input_value()
            check('창 안의 글이 올바른 기록 파일', json.loads(txt)['format'] == 'jcb_cbt_records')
            ctx.close()

        # =================================================================
        # 8. 좁은 화면(390px)
        # =================================================================
        ctx, P = new_device(browser, seed=seed, viewport={'width': 390, 'height': 844})
        check('390px: 가로 스크롤 없음', P.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth"))
        bb = P.locator('#file-bar').bounding_box()
        check('390px: 기록 파일 구역이 화면 안', bb['x'] >= 0 and bb['x'] + bb['width'] <= 390 + 1, bb)
        btns = [P.locator(i).bounding_box() for i in ('#btn-rec-export', '#btn-rec-import')]
        check('390px: 버튼이 구역 안', all(b and b['x'] + b['width'] <= bb['x'] + bb['width'] + 1 for b in btns))
        with P.expect_file_chooser() as fc:
            P.locator('#btn-rec-import').click()
        fc.value.set_files(write_tmp('mob_%s.json' % TAG, rec_file(hist=[mk_hist(now - 77 * H, '모바일 가져오기 기록')] + [mk_hist(now - (i + 100) * H, 'x%d' % i) for i in range(5)])))
        P.wait_for_selector('#active-modal')
        mb = P.locator('#active-modal .modal-box').bounding_box()
        check('390px: 가져오기 창이 화면 안', mb['x'] >= 0 and mb['x'] + mb['width'] <= 391 and mb['y'] >= 0 and mb['y'] + mb['height'] <= 845, mb)
        check('390px: 창 안에서 가로 넘침 없음', P.evaluate("() => { const l = document.querySelector('.imp-list'); return l.scrollWidth <= l.clientWidth + 1; }"))
        P.locator('#active-modal').get_by_role('button', name='취소', exact=True).click()
        ctx.close()

        browser.close()

    real = [e for e in errors if 'Failed to load resource' not in e and 'cdnjs' not in e and 'ERR_' not in e]
    check('콘솔 오류 없음(막힌 CDN 요청 제외)', not real, real[:5])
    print('\n[%s] PASS %d / FAIL %d' % (TAG, len(PASS), len(FAIL)))
    for f in FAIL:
        print('  FAILED:', f)
    sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
