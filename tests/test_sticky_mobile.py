from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page(viewport={'width':375,'height':700})
    page.goto('http://localhost:9123/index.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    time.sleep(0.2)

    h_var = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--app-header-h')")
    print("mobile --app-header-h:", h_var)
    box0 = page.locator('#app-header').bounding_box()
    print("mobile header box:", box0)

    page.mouse.wheel(0, 1000)
    time.sleep(0.2)
    box1 = page.locator('#app-header').bounding_box()
    print("mobile header box after scroll:", box1)
    print("still stuck at top:", box1['y'] == 0)
    page.screenshot(path='/tmp/sticky_mobile_scrolled.png', full_page=False)

    browser.close()
