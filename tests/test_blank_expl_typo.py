# -*- coding: utf-8 -*-
"""정처기 CBT (Ver 2.3 에서도 유효): 괄호(빈칸)별 답안칸 9문항 + 해설 항목 줄바꿈 확인 + 코드 오탈자 수정 15문항 + 버전 칩.
usage: test_blank_expl_typo.py URL TAG
"""
import os
import sys, json, re, urllib.request
from playwright.sync_api import sync_playwright

sys.argv_backup = list(sys.argv)
import test_dups as T   # 도우미(new_page/start/goto_q/status_of/check ...)를 빌려 쓴다. 같은 인자(URL TAG)로 읽힌다.

URL, TAG = T.URL, T.TAG
check = T.check
D = T.D
QS = T.QS
BK = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jcb_restored', 'backup_before_expl_blank_typo', 'jcb_cbt', 'site', 'data.json'), encoding='utf-8'))
BQ = {q['id']: q for q in BK['questions']}

EXP_PARTS = {
    '2022-2-10': [('1', '베타'), ('2', '알파')],
    '2022-3-2': [('합집합', 'U'), ('차집합', '-'), ('카티션 프로덕트', 'X'), ('프로젝트', 'π'), ('조인', '⋈')],
    '2022-3-16': [('1', 'SJF'), ('2', 'RR'), ('3', 'SRT')],
    '2023-1-5': [('1', '가상회선'), ('2', '데이터그램')],
    '2023-1-9': [('(a)', '%'), ('(b)', '10')],
    '2023-2-2': [('a', 'm/1000'), ('b', '(m%1000)/500'), ('c', '(m%500)/100'), ('d', '(m%100)/10')],
    '2023-2-15': [('대칭키', 'DES, AES, ARIA, SEED'), ('비대칭키', 'RSA, ECC')],
    '2024-1-10': [('1', '6'), ('2', '3'), ('3', '1'), ('4', '7'), ('5', '2')],
    '2025-3-19': [('1', 'ㄱ'), ('2', 'ㄹ'), ('3', 'ㅁ')],
}
CODE_FIXED = ['2020-2-5', '2020-2-19', '2020-3-13', '2020-4-6', '2020-4-9', '2020-4-18', '2021-1-7', '2021-1-15', '2021-2-17',
              '2021-2-18', '2022-1-11', '2022-2-17', '2022-3-19', '2023-1-9', '2023-2-14']
EXPL_LINE_IDS = ['2020-2-1', '2020-3-10', '2020-3-11', '2020-3-12', '2020-3-18', '2020-4-2', '2020-4-17', '2020-4-20', '2021-2-18', '2021-2-19']


def rnd_of(qid):
    y, r, n = qid.split('-')
    return '%s년 %s회' % (y, r), int(n)


def open_q(browser, qid, mode='학습 모드', viewport=None):
    ctx, p = T.new_page(browser, viewport=viewport)
    rl, n = rnd_of(qid)
    T.start(p, rounds=[rl], mode=mode)
    T.goto_q(p, n)
    return ctx, p


def inputs(p):
    return p.locator('#exam-main .answer-wrap .answer-input')


def labels(p):
    return [l.inner_text().strip() for l in p.locator('#exam-main .answer-wrap .ap-label').all()]


def fill(p, vals):
    f = inputs(p)
    for i, v in enumerate(vals):
        f.nth(i).fill(v)


def reveal(p):
    p.get_by_role('button', name=re.compile('정답 확인|정답 보기')).first.click()


def status_after(browser, qid, vals, mode='학습 모드'):
    ctx, p = open_q(browser, qid, mode)
    fill(p, vals)
    reveal(p)
    rl, n = rnd_of(qid)
    st = T.status_of(p, n)
    oks = [('ap-ok' in (inputs(p).nth(i).get_attribute('class') or '')) for i in range(inputs(p).count())]
    ctx.close()
    return st, oks


def want_label(l):
    return '(%s)' % l if re.fullmatch(r'[0-9]+', l) else l


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
        # Ver 2.3(이 시험 다음 작업)에서 더 바뀐 것: 정답을 실제 출력으로 고친 7문항(answer) + 유사 칩 6문항(similar). 이 둘만 추가로 허용한다.
        NEW_ANS = {'2020-2-19', '2020-4-9', '2020-4-18', '2022-3-9', '2023-1-2', '2023-2-14', '2023-3-10'}
        NEW_SIM = {'2021-3-1', '2024-1-1', '2020-4-19', '2023-3-11', '2020-4-18', '2023-3-10'}
        for i in list(changed):
            ks = [k for k in changed[i] if not ((k == 'answer' and i in NEW_ANS) or (k == 'similar' and i in NEW_SIM)) and not (i == '2020-4-3' and k in ('aliases', 'answer_alts', 'appearances'))]   # 2023-3-15 합치기(Ver 2.4)
            if ks:
                changed[i] = ks
            else:
                del changed[i]
        want_ids = set(CODE_FIXED) | set(EXP_PARTS)
        check('data.json: 403문항(2023-3-15 합침) / 바뀐 문항 id 가 의도한 목록과 정확히 같음', len(QS) == 403 and set(changed) == want_ids, sorted(set(changed) ^ want_ids))
        only_code = [i for i in CODE_FIXED if i not in EXP_PARTS]
        check('코드 수정 문항은 code 필드만 바뀜(2023-1-9 제외)', all(changed[i] == ['code'] for i in only_code), {i: changed[i] for i in only_code if changed[i] != ['code']})
        check('칸 나눈 문항은 answer_parts 만 바뀜(2023-1-9 는 code·answer_alts 도)',
              all(sorted(changed[i]) == (['answer_alts', 'answer_parts', 'code'] if i == '2023-1-9' else ['answer_parts']) for i in EXP_PARTS), {i: changed[i] for i in EXP_PARTS})
        check('prompt/answer/explanation/grading 은 한 문항도 안 바뀜', not [i for i, ks in changed.items() if set(ks) & {'prompt', 'prompt_blocks', 'answer', 'explanation', 'explanation_lines', 'grading'}])
        for i, exp in EXP_PARTS.items():
            got = [(p['label'], p['value']) for p in QS[i]['answer_parts']]
            check('칸 정의 ' + i, got == exp, got)
        check('번호별 답안란 문항 98개(89+9)', sum(1 for q in D['questions'] if q.get('answer_parts')) == 98)
        check('2023-1-9 answer_alts', QS['2023-1-9']['answer_alts'] == ['%\n5', '%\n2', '&\n1'], QS['2023-1-9'].get('answer_alts'))
        check('2025-3-19 는 자가채점 그대로', QS['2025-3-19']['grading'] == 'self')
        check('2023-2-2 b·c·d 칸 alts(괄호 뺀 꼴)', [p.get('alts') for p in QS['2023-2-2']['answer_parts']] == [None, ['m%1000/500'], ['m%500/100'], ['m%100/10']])
        bad_old = ['system.out', 'studio.h', '.Length', 'class parent', "'Programming'"]
        leftovers = [(i, b) for i in CODE_FIXED for b in bad_old if b in QS[i]['code']]
        check('고친 문항 코드에 옛 오탈자가 남지 않음', not leftovers, leftovers)
        check('2020-4-6 출력에 공백', 'print(a[i][j]+" ")' in QS['2020-4-6']['code'])
        check('해설에 줄 나눈 문항 10개 그대로', sorted(q['id'] for q in D['questions'] if q.get('explanation_lines')) == sorted(EXPL_LINE_IDS))

        # =================================================================
        # 1. 버전 칩
        # =================================================================
        ctx, P = T.new_page(browser)
        chip = P.locator('.app-header-ver').inner_text()
        check('버전 칩 Ver 2.5 · 수정 21회', chip == 'Ver 2.5 · 수정 21회', chip)
        t = P.locator('.app-header-ver').get_attribute('title')
        check('버전 칩 title', 'Ver 2.5' in t and '수정 21회' in t, t)
        ctx.close()

        # =================================================================
        # 2. 해설 항목 줄바꿈 (학습 모드 '정답 확인' 뒤 해설 상자)
        # =================================================================
        for qid in EXPL_LINE_IDS:
            ctx, p = open_q(browser, qid)
            reveal(p)
            nl = p.locator('.explain-box .expl-line').count()
            want = len(QS[qid]['explanation_lines'])
            first = p.locator('.explain-box .expl-line').first.inner_text() if nl else ''
            has_sep = any(' / ' in x.inner_text() for x in p.locator('.explain-box .expl-line').all())
            check('해설 줄바꿈 ' + qid + ' (%d줄)' % want, nl == want and not has_sep, (nl, want, has_sep, first[:30]))
            ctx.close()
        ctx, p = open_q(browser, '2020-4-15')
        reveal(p)
        txt = p.locator('.explain-box').inner_text()
        check('2020-4-15 해설은 문장 안 병기라 한 줄 그대로', p.locator('.explain-box .expl-line').count() == 0 and '유효 값 / 무효 값' in txt)
        ctx.close()

        # =================================================================
        # 3. 괄호 칸 나누기: 문항마다 칸 수·이름·채점
        # =================================================================
        for qid, exp in EXP_PARTS.items():
            ctx, p = open_q(browser, qid)
            check('%s 입력칸 %d개' % (qid, len(exp)), inputs(p).count() == len(exp), inputs(p).count())
            check('%s 칸 이름' % qid, labels(p) == [want_label(l) for l, _ in exp], labels(p))
            check('%s 라벨 문구 "번호별로 입력"' % qid, '번호별로 입력' in p.locator('#exam-main .answer-label').inner_text())
            ctx.close()

        # 정답 → correct, 한 칸 틀림 → wrong (자가채점 2025-3-19 제외)
        for qid, exp in EXP_PARTS.items():
            if QS[qid]['grading'] != 'exact':
                continue
            vals = [v for _, v in exp]
            st, oks = status_after(browser, qid, vals)
            check('%s 정답 입력 → 정답, 모든 칸 초록' % qid, st == 'correct' and all(oks), (st, oks))
            bad = list(vals)
            bad[-1] = bad[-1] + 'X'
            st, oks = status_after(browser, qid, bad)
            check('%s 마지막 칸만 틀림 → 오답, 그 칸만 빨강' % qid, st == 'wrong' and oks == [True] * (len(vals) - 1) + [False], (st, oks))
        # 칸 앞뒤 공백은 무시
        st, _ = status_after(browser, '2022-3-16', ['  SJF ', 'RR  ', ' SRT'])
        check('2022-3-16 칸 앞뒤 공백 무시', st == 'correct', st)
        # 칸 한 개만 비면 오답
        st, oks = status_after(browser, '2024-1-10', ['6', '3', '', '7', '2'])
        check('2024-1-10 한 칸 빔 → 오답', st == 'wrong' and oks == [True, True, False, True, True], (st, oks))
        # 모두 빈칸이면 미답변
        ctx, p = open_q(browser, '2022-2-10')
        reveal(p)
        check('2022-2-10 입력 없이 정답 확인 → "미답변" 해설 제목(일반 문항과 같은 동작)', p.locator('.explain-box .exp-title').inner_text().startswith('미답변'), p.locator('.explain-box .exp-title').inner_text())
        ctx.close()

        # Enter 로 다음 칸 이동
        ctx, p = open_q(browser, '2024-1-10')
        inputs(p).nth(0).focus()
        p.keyboard.press('Enter')
        idx = p.evaluate("() => Array.from(document.querySelectorAll('#exam-main .answer-wrap .answer-input')).indexOf(document.activeElement)")
        check('Enter → 다음 칸으로 이동', idx == 1, idx)
        ctx.close()

        # 2022-3-2 기호 칸: π ⋈ 입력
        st, oks = status_after(browser, '2022-3-2', ['U', '-', 'X', 'π', '⋈'])
        check('2022-3-2 기호 5칸 정답', st == 'correct', (st, oks))
        st, oks = status_after(browser, '2022-3-2', ['U', '-', 'x', 'π', '⋈'])
        check('2022-3-2 대소문자 다르면 오답(완전일치 정책)', st == 'wrong' and oks == [True, True, False, True, True], (st, oks))

        # 2023-2-15: 칸 안은 쉼표 순서까지 완전일치
        st, _ = status_after(browser, '2023-2-15', ['DES, AES, ARIA, SEED', 'RSA, ECC'])
        check('2023-2-15 정답', st == 'correct', st)
        st, _ = status_after(browser, '2023-2-15', ['AES, DES, ARIA, SEED', 'RSA, ECC'])
        check('2023-2-15 순서 바뀌면 오답(완전일치 정책, 기존과 동일)', st == 'wrong', st)

        # =================================================================
        # 4. 2023-1-9: 같은 뜻의 짝 (%,10 / %,5 / %,2 / &,1)
        # =================================================================
        for combo in (['%', '10'], ['%', '5'], ['%', '2'], ['&', '1'], [' % ', '5 '], ['&', ' 1']):
            st, oks = status_after(browser, '2023-1-9', combo)
            check('2023-1-9 %r → 정답, 두 칸 모두 초록' % combo, st == 'correct' and oks == [True, True], (st, oks))
        for combo in (['&', '10'], ['%', '1'], ['&', '5'], ['%', ''], ['', '10'], ['5', '%']):
            st, oks = status_after(browser, '2023-1-9', combo)
            check('2023-1-9 %r → 오답' % combo, st == 'wrong', (st, oks))
        ctx, p = open_q(browser, '2023-1-9')
        fill(p, ['&', '10'])
        reveal(p)
        oks = [('ap-ok' in (inputs(p).nth(i).get_attribute('class') or '')) for i in range(2)]
        check('2023-1-9 (&,10): (a) 빨강 · (b) 초록', oks == [False, True], oks)
        alts = p.locator('.ma-alts').inner_text()
        check('"이 표기도 정답으로 인정" 에 칸 이름 붙여 표시', '(a): %, (b): 5' in alts and '(a): %, (b): 2' in alts and '(a): &, (b): 1' in alts and '⏎' not in alts, alts)
        ma = p.locator('.model-answer-box .ma-value').inner_text()
        check('정답 상자: (a): % / (b): 10', ma == '(a): %\n(b): 10', repr(ma))
        ctx.close()
        # 컴파일 가능한 코드로 바뀜: 세미콜론
        check('2023-1-9 코드 break; 세미콜론', 'if (input == 0) break;' in QS['2023-1-9']['code'])

        # =================================================================
        # 5. 2023-2-2: Java 판 4칸 + 괄호 뺀 꼴 + C 탭 따로
        # =================================================================
        ctx, p = open_q(browser, '2023-2-2')
        sel = p.locator('.ver-tab[aria-selected="true"] .vt-lang').inner_text().strip()
        check('2023-2-2 기본 탭 Java · 4칸', sel == 'Java' and inputs(p).count() == 4 and labels(p) == ['a', 'b', 'c', 'd'], (sel, labels(p)))
        fill(p, ['m/1000', 'm%1000/500', 'm%500/100', 'm%100/10'])
        reveal(p)
        check('2023-2-2 Java: 괄호 뺀 꼴도 정답', T.status_of(p, 2) == 'correct')
        ctx.close()
        ctx, p = open_q(browser, '2023-2-2')
        fill(p, ['m/1000', 'm%1000/500', 'm%500/100', 'm%100/1'])
        reveal(p)
        check('2023-2-2 Java: d 틀리면 오답', T.status_of(p, 2) == 'wrong')
        ctx.close()
        ctx, p = open_q(browser, '2023-2-2')
        p.locator('.ver-tab', has_text='C').click()
        p.wait_for_timeout(80)
        check('2023-2-2 C 탭은 ①~④ 4칸(기존)', labels(p) == ['①', '②', '③', '④'], labels(p))
        ctx.close()

        # =================================================================
        # 6. 2025-3-19: 자가채점 + 3칸
        # =================================================================
        ctx, p = open_q(browser, '2025-3-19')
        fill(p, ['ㄱ', 'ㄹ', 'ㅁ'])
        reveal(p)
        ma = p.locator('.model-answer-box .ma-value').inner_text()
        check('2025-3-19 정답 상자 (1)(2)(3)', ma == '(1) ㄱ\n(2) ㄹ\n(3) ㅁ', repr(ma))
        check('2025-3-19 자가채점 버튼 있음', p.get_by_role('button', name=re.compile('맞았음')).count() >= 1 and p.get_by_role('button', name=re.compile('틀렸음')).count() >= 1)
        ctx.close()

        # =================================================================
        # 7. 결과 화면(실전 모드): 칸 나눈 문항의 내 답안·초록/빨강
        # =================================================================
        ctx, p = open_q(browser, '2023-1-9', mode='실전 모드')
        fill(p, ['%', '5'])
        T.goto_q(p, 5)
        fill(p, ['가상회선', '데이터그램x'])
        p.locator('.exam-top-right .btn-sm', has_text='제출').click()
        p.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click()
        p.wait_for_selector('#screen-result:not([hidden]) .review-card')
        c9 = p.locator('.review-card', has_text='2023년 1회 · #9').first
        c5 = p.locator('.review-card', has_text='2023년 1회 · #5').first
        k9 = [('ap-ok' in (c9.locator('.answer-input').nth(i).get_attribute('class') or '')) for i in range(c9.locator('.answer-input').count())]
        k5 = [('ap-ok' in (c5.locator('.answer-input').nth(i).get_attribute('class') or '')) for i in range(c5.locator('.answer-input').count())]
        check('결과 #9: 칸 2개, 대체 정답(%,5)이라 모두 초록', k9 == [True, True], k9)
        check('결과 #5: 칸 2개, 첫 칸 초록 · 둘째 칸 빨강', k5 == [True, False], k5)
        check('결과 #9 카드에 "정답" 표시', '정답' in c9.inner_text()[:80], c9.inner_text()[:80])
        ctx.close()

        # 7b. 결과 화면 복습 카드의 해설도 줄로 나뉨
        ctx, p = open_q(browser, '2020-4-2', mode='실전 모드')
        p.locator('.exam-top-right .btn-sm', has_text='제출').click()
        p.locator('#active-modal').get_by_role('button', name='제출하기', exact=True).click()
        p.wait_for_selector('#screen-result:not([hidden]) .review-card')
        card = p.locator('.review-card', has_text='2020년 4회 · #2').first
        n_lines = card.locator('.expl-line').count()
        check('결과 복습 카드(2020-4#2) 해설 7줄, 줄 안에 " / " 없음', n_lines == 7 and not any(' / ' in x.inner_text() for x in card.locator('.expl-line').all()), n_lines)
        ctx.close()

        # =================================================================
        # 8. 휴대폰 폭(390px): 가로 스크롤 없음 · 칸 라벨이 긴 문항
        # =================================================================
        for qid in ('2022-3-2', '2023-2-15', '2024-1-10', '2023-2-2'):
            ctx, p = open_q(browser, qid, viewport={'width': 390, 'height': 800})
            sw = p.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
            w = p.evaluate("() => Array.from(document.querySelectorAll('#exam-main .answer-wrap .answer-input')).map(e => Math.round(e.getBoundingClientRect().width))")
            check('390px %s 가로 스크롤 없음 · 입력칸 폭 120px 이상' % qid, sw[0] <= sw[1] and min(w) >= 120, (sw, w))
            ctx.close()

        # =================================================================
        # 9. 고친 코드가 화면에 반영(코드 상자 글자)
        # =================================================================
        for qid, needle in (('2020-3-13', '#include <stdio.h>'), ('2021-1-15', 'p-> age);\n }'), ('2022-3-19', '.length'), ('2023-2-14', 'String str1 = "Programming";')):
            ctx, p = open_q(browser, qid)
            code = p.locator('#exam-main .q-code code').inner_text()
            check('코드 화면 ' + qid, needle in code, code[:80])
            ctx.close()

        real = [e for e in T.errors if not re.search(r'cdnjs|highlight|Failed to load resource|net::ERR|ERR_', e)]
        check('콘솔 오류 없음', not real, real[:5])
        browser.close()

    print('\n== %s: PASS %d / FAIL %d ==' % (TAG, len(T.PASS), len(T.FAIL)))
    if T.FAIL:
        print('FAILED:', T.FAIL)
        sys.exit(1)


if __name__ == '__main__':
    main()
