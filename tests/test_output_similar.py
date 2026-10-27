# -*- coding: utf-8 -*-
"""정처기 CBT (Ver 2.3): ① 정답을 코드의 실제 출력으로 고친 7문항 ② 비슷하지만 정답이 다른 3쌍(6문항)의 '유사 연도·회차' 칩.
usage: test_output_similar.py URL TAG
"""
import os
import sys, json, re
from playwright.sync_api import sync_playwright

import test_blank_expl_typo as B     # open_q / inputs / fill / reveal 도우미(안에서 test_dups 를 쓴다)
T = B.T
check = T.check
D, QS = T.D, T.QS
BK = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jcb_restored', 'backup_before_output_similar', 'jcb_cbt', 'site', 'data.json'), encoding='utf-8'))
BQ = {q['id']: q for q in BK['questions']}

NEW_ANS = {
    '2020-2-19': 'a=10',
    '2020-4-9': '[1, 2, 3]\n7\n123\n45\n6789',
    '2020-4-18': 'KOREA\nEA\nK\nE\nM',
    '2022-3-9': '[101, 102, 103, 104, 105]',
    '2023-1-2': 'Art\nA\nA\nArt\nArt',
    '2023-2-14': 'true\nfalse\ntrue\ntrue',
    '2023-3-10': 'KOREA\nOREA\nK\nE\nO',
}
OLD_ANS = {
    '2020-2-19': 'a = 10',
    '2020-4-9': '[1,2,3] / 7 / 123 / 45 / 6789',
    '2020-4-18': 'KOREA / EA / K / E / M',
    '2022-3-9': '[101,102,103,104,105]',
    '2023-1-2': 'Art / A / A / Art / Art',
    '2023-2-14': 'true / false / true / true',
    '2023-3-10': 'KOREA / OREA / K / E / O',
}
# id -> 칩에 보여야 하는 상대 문제의 연도·회차
SIM = {
    '2021-3-1': ['유사 2024년 1회'],
    '2024-1-1': ['유사 2021년 3회'],
    '2020-4-19': ['유사 2023년 3회'],
    '2023-3-11': ['유사 2020년 4회'],
    '2020-4-18': ['유사 2023년 3회'],
    '2023-3-10': ['유사 2020년 4회'],
}
SIM_NUM = {'2021-3-1': '2024-1-1', '2024-1-1': '2021-3-1', '2020-4-19': '2023-3-11', '2023-3-11': '2020-4-19',
           '2020-4-18': '2023-3-10', '2023-3-10': '2020-4-18'}


def sim_chips(p):
    return [c.inner_text().strip() for c in p.locator('#exam-main .q-head-left .sim-chip').all()]


def run_answer(browser, qid, text):
    ctx, p = B.open_q(browser, qid)
    f = B.inputs(p)
    f.first.fill(text)
    B.reveal(p)
    rl, n = B.rnd_of(qid)
    st = T.status_of(p, n)
    kind = p.evaluate("() => document.querySelector('#exam-main .answer-wrap .answer-input').tagName")
    ctx.close()
    return st, kind


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')

        # =================================================================
        # 0. 데이터
        # =================================================================
        changed = {}
        for i, q in QS.items():
            for k in set(q) | set(BQ[i]):
                if q.get(k) != BQ[i].get(k):
                    changed.setdefault(i, []).append(k)
        want_ids = set(NEW_ANS) | set(SIM) | {'2020-4-3'}      # 2020-4-3: Ver 2.4 에서 2023-3-15 를 합침(aliases·answer_alts·appearances)
        check('data.json: 403문항 / 바뀐 문항 id 가 의도한 목록과 정확히 같음', len(QS) == 403 and set(changed) == want_ids, sorted(set(changed) ^ want_ids))
        check('정답만 고친 문항은 answer 필드만 바뀜',
              all(changed[i] == ['answer'] for i in NEW_ANS if i not in SIM), {i: changed[i] for i in NEW_ANS if i not in SIM and changed[i] != ['answer']})
        check('유사 표시만 한 문항은 similar 필드만 바뀜', all(changed[i] == ['similar'] for i in SIM if i not in NEW_ANS), {i: changed[i] for i in SIM if i not in NEW_ANS})
        check('둘 다 해당하는 2020-4-18 · 2023-3-10 은 answer + similar', all(sorted(changed[i]) == ['answer', 'similar'] for i in ('2020-4-18', '2023-3-10')), {i: changed[i] for i in ('2020-4-18', '2023-3-10')})
        for i, a in NEW_ANS.items():
            check('정답 ' + i, QS[i]['answer'] == a and BQ[i]['answer'] == OLD_ANS[i], (QS[i]['answer'], BQ[i]['answer']))
        check('채점 방식은 한 문항도 안 바뀜(전부 exact 유지)', all(QS[i]['grading'] == BQ[i]['grading'] == 'exact' for i in NEW_ANS))
        check('answer_alts·answer_parts 는 이 7문항에 없음', all(not QS[i].get('answer_alts') and not QS[i].get('answer_parts') for i in NEW_ANS))
        check('prompt/code/explanation 은 한 문항도 안 바뀜', not [i for i, ks in changed.items() if set(ks) & {'prompt', 'prompt_blocks', 'code', 'explanation', 'explanation_lines'}])
        sims = {i: q['similar'] for i, q in QS.items() if q.get('similar')}
        check('similar 가 붙은 문항은 정확히 6개', sorted(sims) == sorted(SIM), sorted(sims))
        check('각 문항의 similar 는 상대 한 문항', all(len(v) == 1 and v[0]['id'] == SIM_NUM[i] for i, v in sims.items()), sims)
        check('상대 문항과 정답이 실제로 다름', all(QS[i]['answer'].strip() != QS[SIM_NUM[i]]['answer'].strip() for i in SIM))
        check('similar 문항은 합쳐지지 않음(appearances/aliases 없음)', all(not QS[i].get('appearances') and not QS[i].get('aliases') for i in SIM))
        check('meta.similar_pairs == 3', D['meta'].get('similar_pairs') == 3, D['meta'].get('similar_pairs'))
        check('합친 문항 수·출제 기록 수(403 / 420 / 17)', D['meta']['total_questions'] == 403 and D['meta']['total_appearances'] == 420 and D['meta']['merged_duplicates'] == 17)
        # 같은 개념·다른 문장은 아무 표시도 없음
        for qid in ('2021-2-8', '2024-2-7', '2023-1-4', '2025-2-8', '2020-3-3', '2024-1-7', '2026-2-4'):
            check('같은 개념·다른 문장 %s 에는 similar 없음' % qid, not QS[qid].get('similar'))

        # =================================================================
        # 1. 버전 칩
        # =================================================================
        ctx, P = T.new_page(browser)
        chip = P.locator('.app-header-ver').inner_text()
        check('버전 칩 Ver 2.5 · 수정 21회', chip == 'Ver 2.5 · 수정 21회', chip)
        check('버전 칩 title', '수정 21회' in P.locator('.app-header-ver').get_attribute('title') and 'Ver 2.5' in P.locator('.app-header-ver').get_attribute('title'))
        ctx.close()

        # =================================================================
        # 2. 유사 칩 표시 (학습 모드 문항 화면)
        # =================================================================
        for qid, want in SIM.items():
            ctx, p = B.open_q(browser, qid)
            got = sim_chips(p)
            check('%s 번호 옆 유사 칩 %s' % (qid, want), got == want, got)
            app = [c.inner_text() for c in p.locator('#exam-main .q-head-left .app-chip').all()]
            rl, n = B.rnd_of(qid)
            check('%s 출제 칩은 자기 회차 하나뿐(유사 문제를 출제 기록으로 섞지 않음)' % qid, app == ['%s · #%d' % (rl, n)], app)
            ttl = p.locator('#exam-main .q-head-left .sim-chip').first.get_attribute('title')
            other = SIM_NUM[qid].split('-')
            check('%s 칩 title 에 상대 번호와 "합치지 않았습니다"' % qid, ('#' + other[2]) in ttl and '합치지 않았습니다' in ttl, ttl)
            # 점선 테두리·연노랑(실제 출제 칩과 구별)
            sty = p.evaluate("() => { const c = document.querySelector('#exam-main .q-head-left .sim-chip'); const s = getComputedStyle(c); return [s.borderTopStyle, s.backgroundColor]; }")
            check('%s 칩 모양: 점선' % qid, sty[0] == 'dashed', sty)
            ctx.close()
        # 칩이 없는 문항
        for qid in ('2021-2-8', '2020-3-13', '2020-1-6'):
            ctx, p = B.open_q(browser, qid)
            check('%s 에는 유사 칩 없음' % qid, sim_chips(p) == [], sim_chips(p))
            ctx.close()

        # =================================================================
        # 3. 채점: 새 정답(실제 출력)은 정답, 옛 표기는 오답
        # =================================================================
        for qid, newa in NEW_ANS.items():
            st, kind = run_answer(browser, qid, newa)
            check('%s 실제 출력을 입력 → 정답' % qid, st == 'correct', st)
            check('%s 입력창 종류: %s' % (qid, 'textarea(여러 줄)' if '\n' in newa else 'input(한 줄)'), kind == ('TEXTAREA' if '\n' in newa else 'INPUT'), kind)
            st, _ = run_answer(browser, qid, OLD_ANS[qid])
            check('%s 옛 표기 입력 → 오답(완전일치 정책)' % qid, st == 'wrong', st)

        # =================================================================
        # 4. 결과 화면 복습 카드에도 유사 칩
        # =================================================================
        ctx, p = B.open_q(browser, '2020-4-18', mode='실전 모드')
        B.inputs(p).first.fill('KOREA\nEA\nK\nE\nM')
        p.locator('.exam-top-right .btn-sm', has_text='제출').click()
        p.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click()
        p.wait_for_selector('#screen-result:not([hidden]) .review-card')
        card = p.locator('.review-card', has_text='2020년 4회 · #18').first
        check('결과 카드 2020-4#18: 유사 2023년 3회 칩', [c.inner_text().strip() for c in card.locator('.sim-chip').all()] == ['유사 2023년 3회'])
        check('결과 카드 2020-4#18: 정답 처리', '정답' in card.inner_text()[:120], card.inner_text()[:120])
        ctx.close()

        # =================================================================
        # 5. 휴대폰 폭: 칩이 줄바꿈될 뿐 가로 스크롤 없음
        # =================================================================
        for qid in ('2020-4-18', '2023-3-11'):
            ctx, p = B.open_q(browser, qid, viewport={'width': 390, 'height': 800})
            sw = p.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
            r = p.evaluate("() => { const c = document.querySelector('#exam-main .q-head-left .sim-chip').getBoundingClientRect(); return [Math.round(c.left), Math.round(c.right)]; }")
            check('390px %s 가로 스크롤 없음 · 칩이 화면 안' % qid, sw[0] <= sw[1] and 0 <= r[0] and r[1] <= 390, (sw, r))
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
