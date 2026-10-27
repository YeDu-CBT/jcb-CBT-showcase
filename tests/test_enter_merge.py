# -*- coding: utf-8 -*-
"""정처기 CBT (Ver 2.4): '줄바꿈(엔터)만 다른 문제는 같은 문제로 합친다' — 2020-4 #3 + 2023-3 #15 합치기,
2021-3 #1 ↔ 2024-1 #1 은 코드가 실제로 달라(출력 3 / 4) 합치지 않고 유사 칩으로 남김.
usage: test_enter_merge.py URL TAG
"""
import os
import sys, json, re
from playwright.sync_api import sync_playwright

import test_dups as T
check, D, QS = T.check, T.D, T.QS
BK = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jcb_restored', 'backup_before_enter_merge', 'jcb_cbt', 'site', 'data.json'), encoding='utf-8'))
BQ = {q['id']: q for q in BK['questions']}
ws = lambda s: re.sub(r'\s+', '', s or '')


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')

        # ===== 0. 데이터 =====
        gone = sorted(set(BQ) - set(QS))
        new = sorted(set(QS) - set(BQ))
        check('사라진 문항은 2023-3-15 하나, 새 문항 없음', gone == ['2023-3-15'] and not new, (gone, new))
        changed = {i: sorted(k for k in set(QS[i]) | set(BQ[i]) if QS[i].get(k) != BQ[i].get(k)) for i in QS if QS[i] != BQ[i]}
        check('바뀐 문항은 정확히 3개(2020-4-3 · 2021-3-1 · 2024-1-1)', sorted(changed) == ['2020-4-3', '2021-3-1', '2024-1-1'], sorted(changed))
        check('2020-4-3 은 aliases·answer_alts·appearances 만 바뀜', changed.get('2020-4-3') == ['aliases', 'answer_alts', 'appearances'], changed.get('2020-4-3'))
        check('2021-3-1 · 2024-1-1 은 similar(설명문)만 바뀜', changed.get('2021-3-1') == ['similar'] and changed.get('2024-1-1') == ['similar'])
        q = QS['2020-4-3']
        check('2020-4-3: 출제 기록 2020-4 #3 + 2023-3 #15', [a['id'] for a in q['appearances']] == ['2020-4-3', '2023-3-15'], q['appearances'])
        check('2020-4-3: 정답 "패키지 다이어그램", 대체 정답 ["패키지"], 채점 exact', q['answer'] == '패키지 다이어그램' and q['answer_alts'] == ['패키지'] and q['grading'] == 'exact', (q['answer'], q.get('answer_alts'), q['grading']))
        check('2023-3-15 는 별칭으로만 남음', '2023-3-15' not in QS and q['aliases'] == ['2023-3-15'])
        check('meta: 403문항 / 출제 기록 420 / 합친 17', D['meta']['total_questions'] == 403 and D['meta']['total_appearances'] == 420 and D['meta']['merged_duplicates'] == 17, D['meta'])
        # 규칙의 불변식: 합친 뒤 공백 제거 지문+코드가 같은 쌍이 없다
        seen = {}
        dup = []
        for i, x in QS.items():
            k = ws(x['prompt']) + '||' + ws(x.get('code'))
            if k in seen:
                dup.append((seen[k], i))
            seen[k] = i
        check('불변식: 줄바꿈·공백만 다른 문항 쌍이 남아 있지 않음', not dup, dup)
        # 2021-3-1 / 2024-1-1 : 합치지 않았고 실제로 다름
        a, b = QS['2021-3-1'], QS['2024-1-1']
        check('2021-3-1 / 2024-1-1 은 별개 문항(정답 3 / 4)', a['answer'] == '3' and b['answer'] == '4' and not a.get('appearances') and not b.get('appearances'))
        check('두 문항 코드는 공백 제거 후에도 다르다(conn1.count() 한 줄 차이)', ws(a['code']) != ws(b['code']) and b['code'].count('count();') == a['code'].count('count();') + 1,
              (a['code'].count('count();'), b['code'].count('count();')))
        check('유사 설명문이 정정됨(반복문 → count() 호출 횟수)', '반복문' not in a['similar'][0]['note'] and 'count()' in a['similar'][0]['note'] and '한 줄 더' in a['similar'][0]['note'], a['similar'][0]['note'])

        # ===== 1. 화면: 합친 문항 칩 · 회차 풀 =====
        ctx, P = T.new_page(browser)
        chip = P.locator('.app-header-ver').inner_text()
        check('버전 칩 Ver 2.5 · 수정 21회', chip == 'Ver 2.5 · 수정 21회', chip)
        T.pick_rounds(P, ['2023년 3회'])
        check('2023년 3회만: 20문항(합쳐도 회차별 문항 수 그대로)', T.filter_count(P) == '20문항', T.filter_count(P))
        P.locator('#btn-rounds-none').click()
        T.pick_rounds(P, ['2020년 4회'])
        check('2020년 4회만: 20문항', T.filter_count(P) == '20문항', T.filter_count(P))
        T.pick_rounds(P, ['2023년 3회'])
        check('2020년 4회 + 2023년 3회: 38문항(공통 2개 = NAT 문항 G3 + 패키지 G12)', T.filter_count(P) == '38문항', T.filter_count(P))
        P.locator('#btn-rounds-all').click()
        check('전체: 403문항', T.filter_count(P) == '403문항', T.filter_count(P))
        ctx.close()

        ctx, P = T.new_page(browser)
        T.start(P, rounds=['2023년 3회'])
        T.goto_q(P, 15)
        c = T.chips(P)
        check('2023년 3회 Q15 칩 = 2020년 4회 #3 · 2023년 3회 #15 (오래된 순)', c == ['2020년 4회 · #3', '2023년 3회 · #15'], c)
        imgs = P.locator('#exam-main .q-prompt img, #exam-main img').count()
        check('그림 1장만 보임', imgs == 1, imgs)
        P.get_by_role('button', name=re.compile('정답 확인|정답 보기')).first.click()
        txt = P.locator('#exam-main').inner_text()
        check('해설이 보임(2020-4 판의 해설)', '폴더 모양의 패키지' in txt, txt[-200:])
        ctx.close()

        # ===== 2. 채점: 두 판의 정답 모두 정답, 틀린 값은 오답 =====
        for ans, exp in (('패키지 다이어그램', 'correct'), ('패키지', 'correct'), ('클래스 다이어그램', 'wrong'), ('패키지다이어그램', 'wrong')):
            s = T.solve_one(browser, ['2020년 4회'], 3, [ans], exp)
            check('2020-4-3 답 %r → %s' % (ans, exp), s == exp, s)
            s = T.solve_one(browser, ['2023년 3회'], 15, [ans], exp)
            check('2023-3-15 자리에서도 %r → %s' % (ans, exp), s == exp, s)

        # ===== 3. 유사 칩 설명문 =====
        for qid, other in (('2021-3-1', '2024년 1회 #1'), ('2024-1-1', '2021년 3회 #1')):
            y, r, n = qid.split('-')
            ctx, P = T.new_page(browser)
            T.start(P, rounds=['%s년 %s회' % (y, r)])
            T.goto_q(P, int(n))
            ch = [x.inner_text().strip() for x in P.locator('#exam-main .q-head-left .sim-chip').all()]
            ttl = P.locator('#exam-main .q-head-left .sim-chip').first.get_attribute('title')
            check('%s 유사 칩 유지: %s' % (qid, ch), len(ch) == 1 and ch[0].startswith('유사 '), ch)
            check('%s 칩 title: 상대 %s + 정정된 설명' % (qid, other), other in ttl and '한 줄 더' in ttl and '합치지 않았습니다' in ttl, ttl)
            ctx.close()

        # ===== 4. 390px 가로 스크롤 없음 =====
        ctx, P = T.new_page(browser, viewport={'width': 390, 'height': 800})
        T.start(P, rounds=['2023년 3회'])
        T.goto_q(P, 15)
        sw = P.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
        check('390px 합친 문항 가로 스크롤 없음', sw[0] <= sw[1], sw)
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
