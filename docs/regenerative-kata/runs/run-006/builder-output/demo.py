#!/usr/bin/env python3
"""Synthetic loopback dependency and notification sink; operator chooses port."""
import argparse,json
from http.server import HTTPServer,BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        code=502 if self.path=='/fail' else 401 if self.path=='/reachability' else 200
        self.send_response(code);self.end_headers();self.wfile.write(b'synthetic Groundhog Day OK')
    def do_POST(self):
        event=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
        print('Synthetic event',event['id'],event['type'],flush=True)
        self.send_response(204);self.end_headers()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,required=True);a=p.parse_args()
    try:HTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
    except KeyboardInterrupt:pass
