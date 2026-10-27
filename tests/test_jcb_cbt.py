from playwright.sync_api import sync_playwright
import time, sys

errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page(viewport={'width':1280,'height':900})

    def on_console(msg):
        if msg.type == 'error':
            errors.append(msg.text)
    page.on('console', on_console)
    page.on('pageerror', lambda exc: errors.append('PAGEERROR: ' + str(exc)))

    page.goto('http://localhost:9833/index.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    time.sleep(0.3)
    print("=== HOME 로드 OK ===")
    page.screenshot(path='/tmp/jcb_home.png', full_page=True)

    # 헤더 sticky 체크
    header_box = page.locator('#app-header').bounding_box()
    print("header box:", header_box)

    # 필터: 언어 Python 선택
    page.get_by_role("button", name="Python (23)").click()
    time.sleep(0.2)
    filt_text = page.locator('.filter-count').inner_text()
    print("필터 적용 후:", filt_text)

    # 연도/회차 필터: 2020년 1회 선택
    page.get_by_role("button", name="2020년 1회", exact=True).click()
    time.sleep(0.2)
    filt_text2 = page.locator('.filter-count').inner_text()
    print("회차+언어 필터 적용 후:", filt_text2)

    # 필터 초기화 (언어만)
    page.get_by_role("button", name="전체로 초기화").nth(1).click()
    time.sleep(0.2)

    # 전체 회차도 초기화
    page.get_by_role("button", name="전체로 초기화").nth(0).click()
    time.sleep(0.2)
    filt_text3 = page.locator('.filter-count').inner_text()
    print("초기화 후:", filt_text3)

    # 학습 모드로 전환, 문항수 5개로, 시작
    page.get_by_role("button", name="학습 모드").click()
    time.sleep(0.1)
    range_input = page.locator('input[type=range]')
    range_input.fill('5')
    time.sleep(0.1)
    page.get_by_role("button", name="시작하기").click()
    page.wait_for_selector('#screen-exam:not([hidden])', timeout=10000)
    time.sleep(0.3)
    print("=== EXAM 진입 OK (학습모드) ===")
    page.screenshot(path='/tmp/jcb_exam1.png', full_page=True)

    exam_header_box = page.locator('#app-header').bounding_box()
    print("exam header box same as home:", exam_header_box == header_box)

    # grading chip 텍스트 확인
    grading_chip = page.locator('.grading-chip').inner_text()
    print("첫 문항 grading:", grading_chip)

    # 답 입력 후 정답 확인 버튼 클릭 (틀린 답 입력)
    answer_input = page.locator('.answer-input').first
    answer_input.fill('테스트오답')
    time.sleep(0.1)
    check_btn = page.get_by_role("button", name="정답 확인").or_(page.get_by_role("button", name="정답 보기"))
    check_btn.first.click()
    time.sleep(0.3)
    print("정답 확인 후 explain-box 존재:", page.locator('.explain-box').count() > 0)
    page.screenshot(path='/tmp/jcb_exam2_revealed.png', full_page=True)

    # 다음 문항으로 이동 2번, 제출
    for i in range(4):
        nxt = page.get_by_role("button", name="다음 →")
        if nxt.count() > 0:
            nxt.click()
            time.sleep(0.15)
        else:
            break

    page.locator('#exam-main').get_by_role("button", name="제출하기").click()
    time.sleep(0.2)
    # 확인 모달
    if page.locator('#active-modal').count() > 0:
        page.locator('#active-modal').get_by_role("button", name="제출하기").click()
    page.wait_for_selector('#screen-result:not([hidden])', timeout=10000)
    time.sleep(0.3)
    print("=== RESULT 화면 진입 OK ===")
    page.screenshot(path='/tmp/jcb_result.png', full_page=True)

    result_header_box = page.locator('#app-header').bounding_box()
    print("result header box same as home:", result_header_box == header_box)

    # 오답 필터 클릭
    wrong_btn = page.locator('.filter-bar button', has_text='오답')
    if wrong_btn.count() > 0:
        wrong_btn.first.click()
        time.sleep(0.2)
    print("오답 필터 후 리뷰카드 수:", page.locator('.review-card').count())

    # 전체로 돌아가서, 자가채점 대기 버튼이 있으면 "맞았음" 눌러 결과화면 크래시 여부 확인
    page.locator('.filter-bar button', has_text='전체').first.click()
    time.sleep(0.2)
    sg_btn = page.locator('.self-grade-row button.sg-correct')
    if sg_btn.count() > 0:
        sg_btn.first.click()
        time.sleep(0.3)
        print("자가채점 '맞았음' 클릭 후 에러 없이 렌더됨:", page.locator('#screen-result:not([hidden])').count() > 0)
        print("자가채점 대기 뱃지 남은 개수:", page.locator('.chip', has_text='자가채점 대기').count())
    else:
        print("자가채점 대기 문항 없음 (스킵)")

    # highlight.js 적용 여부 (코드블록 있는 문항 있으면 hljs 클래스 확인)
    hljs_count = page.locator('code.hljs').count()
    print("hljs 적용된 code 블록 수:", hljs_count)

    # 헤더 클릭 -> 홈 이동 확인
    page.locator('#app-header').click()
    time.sleep(0.3)
    print("헤더 클릭 후 home 화면:", page.locator('#screen-home:not([hidden])').count() > 0)

    # 스크롤 후 sticky 유지 확인
    page.mouse.wheel(0, 800)
    time.sleep(0.2)
    scrolled_box = page.locator('#app-header').bounding_box()
    print("스크롤 후 헤더 y:", scrolled_box['y'], "(0 이어야 sticky 정상)")

    browser.close()

print("---CONSOLE ERRORS---")
for e in errors:
    print(e)
print("---DONE---")
