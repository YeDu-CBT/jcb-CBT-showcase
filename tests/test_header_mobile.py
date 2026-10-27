from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page(viewport={'width':375,'height':700})
    page.goto('http://localhost:8899/index.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    page.screenshot(path='/tmp/header_mobile.png', full_page=False)
    browser.close()
