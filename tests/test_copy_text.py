from playwright.sync_api import sync_playwright
import time

console_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    context = browser.new_context(viewport={'width':1280,'height':1400}, permissions=['clipboard-read','clipboard-write'])
    page = context.new_page()

    def on_console(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)
    page.on('console', on_console)
    page.on('pageerror', lambda exc: console_errors.append('PAGEERROR: ' + str(exc)))

    page.goto('http://localhost:8877/index.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)

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

    # 관련 섹션 컬럼이 줄바꿈으로 나뉘어 표시되는지 확인
    first_row_sections = page.locator('.cs-table tbody tr').first.locator('.cs-sections .cs-section-line')
    print("first row section line count:", first_row_sections.count())
    for i in range(min(3, first_row_sections.count())):
        print("  line", i, ":", first_row_sections.nth(i).inner_text())

    page.screenshot(path='/tmp/copytext_result_top.png', full_page=False)

    # 텍스트로 복사 버튼 클릭 -> 모달 오픈 확인
    page.locator('.cs-export-btn').click()
    page.wait_for_selector('#active-modal', timeout=5000)
    time.sleep(0.3)

    ta_value = page.locator('.copy-textarea').input_value()
    print("---TEXTAREA CONTENT---")
    print(ta_value)
    print("---END---")

    page.screenshot(path='/tmp/copytext_modal.png', full_page=False)

    # 복사하기 버튼 클릭 -> 실제 클립보드에 반영됐는지 확인
    page.get_by_role("button", name="복사하기", exact=True).click()
    time.sleep(0.3)
    clipboard_text = page.evaluate("navigator.clipboard.readText()")
    print("clipboard matches textarea:", clipboard_text == ta_value)
    print("copy feedback text:", page.locator('.copy-feedback').inner_text())

    page.screenshot(path='/tmp/copytext_modal_after_copy.png', full_page=False)

    browser.close()

print("---CONSOLE ERRORS---")
for e in console_errors:
    print(e)
print("---DONE---")
