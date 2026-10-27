from playwright.sync_api import sync_playwright
import time

console_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page(viewport={'width':1280,'height':700})

    def on_console(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)
    page.on('console', on_console)
    page.on('pageerror', lambda exc: console_errors.append('PAGEERROR: ' + str(exc)))

    page.goto('http://localhost:9789/index.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    time.sleep(0.2)

    header_h_var = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--app-header-h')")
    print("--app-header-h on home:", header_h_var)

    # 홈 화면: 스크롤 전/후 헤더 위치 비교
    box_before = page.locator('#app-header').bounding_box()
    print("home header box before scroll:", box_before)
    page.mouse.wheel(0, 1200)
    time.sleep(0.2)
    box_after = page.locator('#app-header').bounding_box()
    print("home header box after scroll 1200px:", box_after)
    print("header still at y=0 after scrolling (sticky works):", box_after['y'] == 0)
    page.screenshot(path='/tmp/sticky_home_scrolled.png', full_page=False)

    # 헤더 클릭으로 홈 복귀 확인(스크롤된 상태에서도 클릭 가능해야 함)
    page.locator('#app-header').click()
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    print("header click from scrolled position -> still on home (already home, no-op): OK")

    # 시험 화면 진입 -> 스크롤 -> exam-top이 헤더 바로 아래에 붙는지 확인(겹침 없는지)
    page.get_by_role("button", name="시작하기", exact=True).click()
    page.wait_for_selector('#screen-exam:not([hidden])', timeout=10000)
    time.sleep(0.2)
    header_box = page.locator('#app-header').bounding_box()
    examtop_box = page.locator('.exam-top').bounding_box()
    print("exam: header box:", header_box, "exam-top box:", examtop_box)
    gap = examtop_box['y'] - (header_box['y'] + header_box['height'])
    print("exam-top sits right below header (gap ~0):", gap)

    # 문항 조금 풀고 스크롤 다운 -> 헤더 계속 상단에 떠 있어야
    page.mouse.wheel(0, 800)
    time.sleep(0.2)
    header_box2 = page.locator('#app-header').bounding_box()
    examtop_box2 = page.locator('.exam-top').bounding_box()
    print("after scroll: header box:", header_box2, "exam-top box:", examtop_box2)
    print("header sticky at top during exam scroll:", header_box2['y'] == 0)
    print("exam-top still docked right under header:", abs((examtop_box2['y']) - (header_box2['y']+header_box2['height'])) < 1)
    page.screenshot(path='/tmp/sticky_exam_scrolled.png', full_page=False)

    # 시험 중 헤더 클릭 -> 종료 확인 모달 (스크롤된 상태에서도)
    page.locator('#app-header').click()
    page.wait_for_selector('#active-modal', timeout=5000)
    print("exit-confirm modal appears even when scrolled: OK")
    page.get_by_role("button", name="종료하기", exact=True).click()
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)

    # 결과 화면까지 풀어서 filter-bar와의 관계 확인
    page.get_by_role("button", name="시작하기", exact=True).click()
    page.wait_for_selector('#screen-exam:not([hidden])', timeout=10000)
    for i in range(40):
        opts = page.locator('.opt-row')
        idx = 0 if i % 2 == 0 else min(1, opts.count()-1)
        opts.nth(idx).click()
        if i < 39:
            page.get_by_role("button", name="다음 →", exact=True).click()
        time.sleep(0.005)
    page.get_by_role("button", name="제출하기", exact=True).click()
    time.sleep(0.2)
    page.locator('#active-modal').get_by_role("button", name="제출하기", exact=True).click()
    page.wait_for_selector('#screen-result:not([hidden])', timeout=10000)
    time.sleep(0.3)

    page.mouse.wheel(0, 1500)
    time.sleep(0.2)
    header_box3 = page.locator('#app-header').bounding_box()
    print("result: header box after scroll:", header_box3)
    print("header sticky at top during result scroll:", header_box3['y'] == 0)
    filterbar = page.locator('.filter-bar')
    if filterbar.count() > 0:
        fb_box = filterbar.bounding_box()
        print("filter-bar box:", fb_box)
        if fb_box:
            print("filter-bar not overlapped by header (y >= header bottom):", fb_box['y'] >= header_box3['y']+header_box3['height'] - 1)
    page.screenshot(path='/tmp/sticky_result_scrolled.png', full_page=False)

    # 결과 화면 헤더 클릭 -> 바로 홈
    page.locator('#app-header').click()
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    print("result screen header click -> home: OK")

    browser.close()

print("---CONSOLE ERRORS---")
for e in console_errors:
    print(e)
print("---DONE---")
