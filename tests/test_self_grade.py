from playwright.sync_api import sync_playwright
import time

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page(viewport={'width':1280,'height':1200})
    page.on('console', lambda m: errors.append(m.text) if m.type=='error' else None)
    page.on('pageerror', lambda exc: errors.append('PAGEERROR: ' + str(exc)))

    page.goto('http://localhost:9844/index.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)

    # 2020년 1회만 선택 (서술형 문항 다수 포함되는 걸 앞서 분석에서 확인한 회차)
    page.get_by_role("button", name="2020년 1회", exact=True).click()
    time.sleep(0.2)
    range_input = page.locator('input[type=range]')
    range_input.fill('20')
    time.sleep(0.1)
    # 실전 모드 그대로 (기본값) 시작 -> 바로 제출
    page.get_by_role("button", name="시작하기").click()
    page.wait_for_selector('#screen-exam:not([hidden])', timeout=10000)
    time.sleep(0.2)

    page.locator('.exam-top-right').get_by_role("button", name="제출", exact=True).click()
    time.sleep(0.2)
    page.locator('#active-modal').get_by_role("button", name="제출하기").click()
    page.wait_for_selector('#screen-result:not([hidden])', timeout=10000)
    time.sleep(0.3)

    pending_count_before = page.locator('.self-grade-row').count()
    print("자가채점 대상(서술형) 리뷰카드 수:", pending_count_before)

    sg_btn = page.locator('.self-grade-row button.sg-correct').first
    sg_btn.click()
    time.sleep(0.3)

    print("클릭 후 result 화면 여전히 표시됨:", page.locator('#screen-result:not([hidden])').count() > 0)
    print("클릭 후 PAGEERROR 발생 여부:", any('PAGEERROR' in e for e in errors))
    page.screenshot(path='/tmp/jcb_selfgrade_after.png', full_page=True)

    browser.close()

print("---CONSOLE ERRORS---")
for e in errors:
    print(e)
print("---DONE---")
