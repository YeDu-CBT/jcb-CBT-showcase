#!/usr/bin/env python3
"""site/index.html(fragment) 최신 내용 + site/data.json을 standalone/jcb_cbt.html(단일 파일, 오프라인용)로 합친다.

ISTQB 사이트의 build_standalone.py와 동일한 패턴:
- <style> 블록, #app-header...#modal-root 블록, 메인 <script> 블록을 site/index.html에서 그대로 가져오고
- 메인 스크립트 안의 fetch('data.json') 로더만 window.__JCB_DATA__ 기반 로더로 치환.
- highlight.js CDN <link>/<script> 태그도 그대로 가져온다(오프라인 환경에서는 문법 강조만 비활성화되고
  나머지 기능은 정상 동작 — applyHighlight()가 window.hljs 존재 여부를 확인하기 때문).
"""
import base64
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))   # 이 스크립트가 있는 폴더(jcb_cbt)
FRAG_PATH = ROOT + '/site/index.html'
DATA_PATH = ROOT + '/site/data.json'
STANDALONE_PATH = ROOT + '/standalone/jcb_cbt.html'

LOADER_RE = re.compile(
    r"fetch\('data\.json'\)\.then\(function\(r\)\{ return r\.json\(\); \}\)\.then\(function\(json\)\{\s*"
    r"DATA = json;\s*"
    r"(?P<body>.*?)"
    r"\}\)\.catch\(function\(err\)\{\s*"
    r"(?P<errbody>.*?)"
    r"\}\);",
    re.S
)


def main():
    with open(FRAG_PATH, 'r', encoding='utf-8') as f:
        frag = f.read()
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data_obj = json.load(f)
    # 그림(img/*.png)을 data URI 로 박아 넣어 파일 하나로도 그림이 보이게 한다(오프라인용).
    # 사이트(fetch) 쪽은 b.file 상대경로를, 단일 파일 쪽은 b.src(data URI)를 쓴다(JS: b.src || b.file).
    n_img = 0
    for q in data_obj['questions']:
        for b in q.get('prompt_blocks', []):
            if b.get('kind') == 'image':
                with open(os.path.join(ROOT, 'site', b['file']), 'rb') as imf:
                    b['src'] = 'data:image/png;base64,' + base64.b64encode(imf.read()).decode('ascii')
                n_img += 1
    print('inlined image blocks:', n_img)
    data_text = json.dumps(data_obj, ensure_ascii=False)

    m_cdn = re.findall(r'<(?:link|script)[^>]*highlight\.js[^>]*>(?:</script>)?', frag)
    cdn_block = '\n'.join(m_cdn)
    if not cdn_block:
        sys.exit('ERROR: highlight.js CDN tags not found in fragment')

    m_style = re.search(r'<style>.*?</style>', frag, re.S)
    if not m_style:
        sys.exit('ERROR: no <style> block found in fragment')
    style_block = m_style.group(0)

    m_body = re.search(r'(<header id="app-header".*?<div id="modal-root"></div>(?:\s*<div id="toast-root"[^>]*></div>)?)', frag, re.S)   # 2026-10-11: 중간 저장 토스트 영역(#toast-root)까지 포함
    if not m_body:
        sys.exit('ERROR: no #app-header...#modal-root block found in fragment')
    body_block = m_body.group(1)

    m_script = re.search(r'<script>\s*\(function\(\)\{.*?\}\)\(\);\s*</script>', frag, re.S)
    if not m_script:
        sys.exit('ERROR: no main <script> block found in fragment')
    script_block = m_script.group(0)

    m_loader = LOADER_RE.search(script_block)
    if not m_loader:
        sys.exit('ERROR: fetch-based loader pattern not found in fragment script (did the loader shape change?)')
    body = m_loader.group('body')
    errbody = m_loader.group('errbody')
    new_loader = (
        "try{\n    DATA = window.__JCB_DATA__;\n"
        "    if(!DATA) throw new Error('데이터를 찾을 수 없습니다.');\n"
        "    " + body.strip() + "\n"
        "  }catch(err){\n"
        "    " + errbody.strip() + "\n"
        "  }"
    )
    script_block_standalone = script_block[:m_loader.start()] + new_loader + script_block[m_loader.end():]

    new_standalone = (
        '<!doctype html>\n'
        '<html lang="ko">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<title>정보처리기사 실기 CBT</title>\n'
        + cdn_block + '\n'
        '</head>\n'
        '<body>\n'
        '<script>window.__JCB_DATA__ = ' + data_text + ';</script>\n'
        + style_block + '\n\n'
        + body_block + '\n\n'
        + script_block_standalone + '\n'
        '</body>\n'
        '</html>\n'
    )

    with open(STANDALONE_PATH, 'w', encoding='utf-8') as f:
        f.write(new_standalone)

    print('OK: standalone rebuilt,', len(new_standalone), 'chars')


if __name__ == '__main__':
    main()
