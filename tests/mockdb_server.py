#!/usr/bin/env python3
"""테스트용: tests/_srv 정적 파일 + 가짜 개인 저장소(/__db/...) 서버.
 - GET  /__db/list?col=<경로>        -> {"docs":[{"id":..,"data":{..}}]}
 - PUT  /__db/doc?path=<경로>        본문 JSON 으로 문서 전체 교체
 - DELETE /__db/doc?path=<경로>
 - GET  /__db/dump                   -> {"docs":{경로: 데이터}, "log":[...], "violations":[...]}
 - POST /__db/reset                  -> 전부 비움
 같은 문서에 쓰기가 겹치면 violations 에 기록한다(실제 런타임의 '문서당 한 번에 하나' 규칙 점검용).
"""
import json, os, sys, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9881
# 기본값: 이 파일 옆의 _srv 폴더(prepare_srv.py가 만든다)
ROOT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '_srv')
DOCS, LOG, VIOL, INFLIGHT = {}, [], [], set()
MAXPAR = [0]
LOCK = threading.Lock()
WRITE_MS = 40


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,PUT,DELETE,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'content-type')

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/__db/list':
            col = parse_qs(u.query)['col'][0]
            with LOCK:
                docs = [{'id': p.rsplit('/', 1)[1], 'data': d} for p, d in DOCS.items() if p.rsplit('/', 1)[0] == col]
            return self._json({'docs': docs})
        if u.path == '/__db/dump':
            with LOCK:
                return self._json({'docs': DOCS, 'log': LOG, 'violations': VIOL, 'maxpar': MAXPAR[0]})
        return super().do_GET()

    def _write(self, op):
        u = urlparse(self.path)
        path = parse_qs(u.query)['path'][0]
        body = None
        if op == 'PUT':
            n = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(n).decode('utf-8'))
        with LOCK:
            if path in INFLIGHT:
                VIOL.append('겹친 쓰기: ' + path)
            INFLIGHT.add(path)
            MAXPAR[0] = max(MAXPAR[0], len(INFLIGHT))
        time.sleep(WRITE_MS / 1000.0)
        with LOCK:
            if op == 'PUT':
                DOCS[path] = body
            else:
                DOCS.pop(path, None)
            LOG.append([op, path])
            INFLIGHT.discard(path)
        self._json({'ok': True})

    def do_PUT(self):
        if urlparse(self.path).path == '/__db/doc':
            return self._write('PUT')
        self._json({'ok': False}, 404)

    def do_DELETE(self):
        if urlparse(self.path).path == '/__db/doc':
            return self._write('DELETE')
        self._json({'ok': False}, 404)

    def do_POST(self):
        if urlparse(self.path).path == '/__db/reset':
            with LOCK:
                DOCS.clear(); LOG.clear(); VIOL.clear(); INFLIGHT.clear(); MAXPAR[0] = 0
            return self._json({'ok': True})
        self._json({'ok': False}, 404)


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
