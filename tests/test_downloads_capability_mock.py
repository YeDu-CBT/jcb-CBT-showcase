from playwright.sync_api import sync_playwright
import time

console_errors = []
console_logs = []

MOCK_JS = """
window.__savedCalls = [];
window.claude = {
  use: function(name){
    return new Promise(function(resolve){
      setTimeout(function(){
        if(name !== 'downloads'){ resolve(null); return; }
        resolve({
          save: function(req){
            window.__savedCalls.push({filename: req.filename, dataType: (req.data && req.data.constructor && req.data.constructor.name) || typeof req.data, dataSize: req.data && req.data.size});
            return Promise.resolve({status: 'saved'});
          }
        });
      }, 10);
    });
  }
};
"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page(viewport={'width':1280,'height':1400})
    page.add_init_script(MOCK_JS)

    def on_console(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)
        console_logs.append(msg.text)
    page.on('console', on_console)
    page.on('pageerror', lambda exc: console_errors.append('PAGEERROR: ' + str(exc)))

    page.goto('http://localhost:8855/index.html')
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

    page.locator('.cs-export-btn').click()
    time.sleep(0.8)  # mock save has a 10ms delay + toBlob async

    calls = page.evaluate("window.__savedCalls")
    print("mock downloads.save calls:", calls)

    browser.close()

print("---CONSOLE ERRORS---")
for e in console_errors:
    print(e)
print("---DONE---")
