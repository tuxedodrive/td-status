#!/usr/bin/env python3
"""Synthetic loopback dependency and sink. Change demo-state.json while running."""
import argparse,json,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            with open('demo-state.json') as f: state=json.load(f)
        except FileNotFoundError: state={'code':200,'body':'Groundhog ready','delay':0}
        time.sleep(float(state.get('delay',0)))
        self.send_response(int(state.get('code',200)));self.end_headers()
        try:self.wfile.write(state.get('body','Groundhog ready').encode())
        except BrokenPipeError:pass
    def do_POST(self):
        body=self.rfile.read(int(self.headers.get('Content-Length',0)))
        with open('demo-events.jsonl','ab') as f:f.write(body+b'\n')
        self.send_response(204);self.end_headers()
    def log_message(self,*args):pass
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,required=True);a=p.parse_args()
try:ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
except KeyboardInterrupt:pass
