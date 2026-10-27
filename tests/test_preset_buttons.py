from playwright.sync_api import sync_playwright
import time

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page(viewport={'width':1280,'height':1200})
    page.on('console', lambda m: errors.append(m.text) if m.type=='error' else None)
    page.on('pageerror', lambda exc: errors.append('PAGEERROR: ' + str(exc)))

    page.goto('http://localhost:9912/index.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    time.sleep(0.3)

    # 이론 문제만 버튼 클릭
    page.get_by_role("button", name="이론 문제만 (기타)").click()
    time.sleep(0.2)
    filt_text = page.locator('.filter-count').inner_text()
    print("이론 문제만 클릭 후 필터 카운트:", filt_text)
    pressed_chips = page.locator('.lang-chip.active').all_inner_texts()
    print("선택된 언어 칩:", pressed_chips)
    page.screenshot(path='/tmp/jcb_preset_theory.png', full_page=True)

    # 코드 문제만 버튼 클릭
    page.get_by_role("button", name="코드 문제만 (기타 제외)").click()
    time.sleep(0.2)
    filt_text2 = page.locator('.filter-count').inner_text()
    print("코드 문제만 클릭 후 필터 카운트:", filt_text2)
    pressed_chips2 = page.locator('.lang-chip.active').all_inner_texts()
    print("선택된 언어 칩:", pressed_chips2)
    page.screenshot(path='/tmp/jcb_preset_code.png', full_page=True)

    browser.close()

print("---CONSOLE ERRORS---")
for e in errors:
    print(e)
print("---DONE---")
