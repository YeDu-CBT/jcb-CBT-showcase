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
    score1 = page.locator('.score-ring-num .pct').inner_text()
    print("1st score:", score1)

    # 텍스트 복사 모달
    page.locator('.cs-export-btn').click()
    page.wait_for_selector('#active-modal', timeout=5000)
    ta_value = page.locator('.copy-textarea').input_value()
    print("textarea non-empty:", len(ta_value) > 0)
    print("has multi-line sections (contains '\\n- '):", '\n- ' in ta_value)
    page.get_by_role("button", name="닫기", exact=True).click()
    time.sleep(0.2)

    # 홈으로 이동 -> 연습 기록 클릭 -> 상세 재조회
    page.get_by_role("button", name="처음으로", exact=True).click()
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    time.sleep(0.2)
    clickable = page.locator('.history-row.history-row-clickable')
    print("clickable history rows:", clickable.count())
    clickable.first.click()
    page.wait_for_selector('#screen-result:not([hidden])', timeout=10000)
    time.sleep(0.3)
    score2 = page.locator('.score-ring-num .pct').inner_text()
    print("replayed score:", score2, "match:", score1 == score2)
    review_cards = page.locator('.review-card')
    print("review cards on replay:", review_cards.count())

    # 재조회 화면에서도 텍스트 복사가 정상 동작하는지
    page.locator('.cs-export-btn').click()
    page.wait_for_selector('#active-modal', timeout=5000)
    ta_value2 = page.locator('.copy-textarea').input_value()
    print("replay textarea non-empty:", len(ta_value2) > 0)

    browser.close()

print("---CONSOLE ERRORS---")
for e in console_errors:
    print(e)
print("---DONE---")
