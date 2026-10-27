from playwright.sync_api import sync_playwright
import time, os

console_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page(viewport={'width':1280,'height':1400}, accept_downloads=True)

    def on_console(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)
    page.on('console', on_console)
    page.on('pageerror', lambda exc: console_errors.append('PAGEERROR: ' + str(exc)))

    page.goto('http://localhost:8866/istqb_cbt.html')
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)

    # 1) 시험 시작 (기본 40문항), 절반은 오답 유도(첫 보기 선택), 나머지는 두번째 보기 선택 -> 혼합 결과
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

    score_text_first = page.locator('.score-ring-num .pct').inner_text()
    print("1st result score pct:", score_text_first)

    chapter_box_exists = page.locator('.chapter-summary').count()
    print("chapter summary box exists:", chapter_box_exists)

    # 2) 이미지로 저장 버튼 클릭 -> 다운로드 검증
    if chapter_box_exists:
        with page.expect_download(timeout=10000) as dl_info:
            page.locator('.cs-export-btn').click()
        download = dl_info.value
        save_path = '/tmp/standalone_chapter_summary_export.png'
        download.save_as(save_path)
        size = os.path.getsize(save_path)
        print("downloaded file:", download.suggested_filename, "size:", size, "bytes")
    else:
        print("WARNING: no chapter summary box, skipping export test")

    # 3) 홈으로 이동, 연습기록 클릭 가능한지 확인
    page.get_by_role("button", name="처음으로", exact=True).click()
    page.wait_for_selector('#screen-home:not([hidden])', timeout=10000)
    time.sleep(0.2)

    hist_rows = page.locator('.history-row')
    print("history rows count:", hist_rows.count())
    clickable_rows = page.locator('.history-row.history-row-clickable')
    print("clickable history rows count:", clickable_rows.count())

    first_row = clickable_rows.first
    first_row.scroll_into_view_if_needed()
    page.screenshot(path='/tmp/standalone_home_before_click.png', full_page=True)
    first_row.click()
    page.wait_for_selector('#screen-result:not([hidden])', timeout=10000)
    time.sleep(0.3)

    score_text_replay = page.locator('.score-ring-num .pct').inner_text()
    print("replayed result score pct:", score_text_replay)
    print("scores match:", score_text_first == score_text_replay)

    page.screenshot(path='/tmp/standalone_result_from_history.png', full_page=True)

    # 오답 목록도 재구성되어 보이는지 확인
    review_cards = page.locator('.review-card')
    print("review cards count on replay:", review_cards.count())

    browser.close()

print("---CONSOLE ERRORS---")
for e in console_errors:
    print(e)
print("---DONE---")
