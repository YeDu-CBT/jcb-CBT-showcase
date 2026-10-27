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

    page.goto('http://localhost:9789/index.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    time.sleep(0.2)
    page.screenshot(path='/tmp/restyled_home_top.png', full_page=False)

    header_box = page.locator('#app-header').bounding_box()
    print("home header box:", header_box)

    # 스크롤 후에도 고정되는지
    page.mouse.wheel(0, 400)
    time.sleep(0.2)
    header_box_scrolled = page.locator('#app-header').bounding_box()
    print("home header box after scroll:", header_box_scrolled)
    print("still sticky:", header_box_scrolled['y'] == 0)
    page.screenshot(path='/tmp/restyled_home_scrolled.png', full_page=False)

    # 시험 화면
    page.mouse.wheel(0, -400)
    page.get_by_role("button", name="시작하기", exact=True).click()
    page.wait_for_selector('#screen-exam:not([hidden])', timeout=10000)
    time.sleep(0.2)
    header_box_exam = page.locator('#app-header').bounding_box()
    print("exam header box:", header_box_exam, "same as home:", header_box_exam==header_box)
    page.screenshot(path='/tmp/restyled_exam.png', full_page=False)

    # 헤더 클릭 -> 시험 중 확인창
    page.locator('#app-header').click()
    page.wait_for_selector('#active-modal', timeout=5000)
    print("exit-confirm modal title:", page.locator('.modal-box h3').inner_text())
    page.get_by_role("button", name="종료하기", exact=True).click()
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    print("after confirm exit, back on home: OK")

    browser.close()

print("---CONSOLE ERRORS---")
for e in console_errors:
    print(e)
print("---DONE---")
