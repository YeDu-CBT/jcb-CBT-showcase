#!/usr/bin/env python3
"""시험용 정적 폴더 tests/_srv 를 만든다 (저장소 안의 상대 경로만 사용).

- index.html      : jcb_cbt/site/index.html(조각) 앞뒤에 문서 뼈대를 붙인 것 (Artifact가 붙이는 뼈대를 흉내)
- data.json, img/ : jcb_cbt/site 에서 복사
- standalone.html : jcb_cbt/standalone/jcb_cbt.html 복사 (먼저 build_standalone.py 로 만들어 둔다)
"""
import os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SITE = os.path.join(REPO, 'jcb_cbt', 'site')
SRV = os.path.join(HERE, '_srv')
HEAD = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head><body>')

os.makedirs(SRV, exist_ok=True)
frag = open(os.path.join(SITE, 'index.html'), encoding='utf-8').read()
open(os.path.join(SRV, 'index.html'), 'w', encoding='utf-8').write(HEAD + frag + '</body></html>')
shutil.copy(os.path.join(SITE, 'data.json'), os.path.join(SRV, 'data.json'))
shutil.rmtree(os.path.join(SRV, 'img'), ignore_errors=True)
shutil.copytree(os.path.join(SITE, 'img'), os.path.join(SRV, 'img'))
shutil.copy(os.path.join(REPO, 'jcb_cbt', 'standalone', 'jcb_cbt.html'), os.path.join(SRV, 'standalone.html'))
print('prepared', SRV)
