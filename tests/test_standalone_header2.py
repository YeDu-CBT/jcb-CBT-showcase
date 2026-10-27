from playwright.sync_api import sync_playwright
import time

console_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page(viewport={'width':1280,'height':900})

    def on_console(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)
    page.on('console', on_console)
    page.on('pageerror', lambda exc: console_errors.append('PAGEERROR: ' + str(exc)))

    page.goto('http://localhost:9456/istqb_cbt.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)

    header_box_home = page.locator('#app-header').bounding_box()
    print("home header box:", header_box_home)

    page.get_by_role("button", name="시작하기", exact=True).click()
    page.wait_for_selector('#screen-exam:not([hidden])', timeout=10000)
    header_box_exam = page.locator('#app-header').bounding_box()
    print("exam header box:", header_box_exam)
    print("same position home vs exam:", header_box_home == header_box_exam)

    # 시험 중 헤더 클릭 -> 확인 모달
    page.locator('#app-header').click()
    page.wait_for_selector('#active-modal', timeout=5000)
    print("exit-confirm modal title:", page.locator('.modal-box h3').inner_text())
    page.get_by_role("button", name="종료하기", exact=True).click()
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    print("after confirm exit, back on home: OK")

    # 다시 시험 시작 -> 끝까지 풀고 제출 -> 결과 화면
    page.get_by_role("button", name="시작하기", exact=True).click()
    page.wait_for_selector('#screen-exam:not([hidden])', timeout=10000)
    for i in range(40):
        opts = page.locator('.opt-row')
        idx = 0 if i % 2 == 0 else min(1, opts.count()-1)
        opts.nth(idx).click()
        if i < 39:
            page.get_by_role("button", name="다음 →", exact=True).click()
        time.sleep(0.01)
    page.get_by_role("button", name="제출하기", exact=True).click()
    time.sleep(0.2)
    page.locator('#active-modal').get_by_role("button", name="제출하기", exact=True).click()
    page.wait_for_selector('#screen-result:not([hidden])', timeout=10000)
    time.sleep(0.3)

    header_box_result = page.locator('#app-header').bounding_box()
    print("result header box:", header_box_result)
    print("same position home vs result:", header_box_home == header_box_result)

    # 결과 화면에서 헤더 클릭 -> 바로 홈으로
    page.locator('#app-header').click()
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    print("after clicking header on result screen, now on home (no confirm needed): OK")

    # 키보드 접근성
    page.get_by_role("button", name="시작하기", exact=True).click()
    page.wait_for_selector('#screen-exam:not([hidden])', timeout=10000)
    page.locator('#app-header').focus()
    page.keyboard.press('Enter')
    page.wait_for_selector('#active-modal', timeout=5000)
    print("keyboard Enter on header triggers exit-confirm modal: OK")
    page.get_by_role("button", name="계속 풀기", exact=True).click()

    browser.close()

print("---CONSOLE ERRORS---")
for e in console_errors:
    print(e)
print("---DONE---")
