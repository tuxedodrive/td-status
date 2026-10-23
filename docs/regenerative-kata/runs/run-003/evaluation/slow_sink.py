"""Observe notification/publication coupling with a bounded synthetic slow sink."""
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
root=Path(__file__).resolve().parents[1];work=root/'evaluation/slow-sink-work';work.mkdir(parents=True,exist_ok=False)
state={'code':200,'delay':0};first_post=threading.Event();posts=[]
class H(BaseHTTPRequestHandler):
    def do_GET(self):self.send_response(state['code']);self.end_headers();self.wfile.write(b'healthy')
    def do_POST(self):
        posts.append(time.monotonic());first_post.set();time.sleep(state['delay']);self.send_response(204);self.end_headers()
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),H);threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}';config={'title':'Groundhog Day slow-sink test','support_url':'https://support.example.invalid/help','notification_url':url+'/events','services':[{'id':'gd-'+str(i),'name':'Groundhog Day '+str(i),'url':url+'/check','kind':'first_party','impact':'Synthetic check only','expected_codes':[200],'keywords':['healthy'],'timeout_seconds':.3,'stale_after_seconds':60} for i in range(3)]}
(work/'config.json').write_text(json.dumps(config));args=[sys.executable,str(root/'builder-output/status.py'),'collect','--config',str(work/'config.json'),'--db',str(work/'state.sqlite'),'--output',str(work/'public')]
result={}
try:
 subprocess.run(args,check=True,timeout=10,capture_output=True)
 before=json.loads((work/'public/status.json').read_text())
 state.update(code=502,delay=2);start=time.monotonic();process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 assert first_post.wait(5),'no queued alert attempt'
 time.sleep(.5);during=json.loads((work/'public/status.json').read_text())
 process.communicate(timeout=12);elapsed=time.monotonic()-start;after=json.loads((work/'public/status.json').read_text())
 result={'sink_delay_seconds_per_event':2,'queued_events':len(posts),'observation':'Checked public file 0.5 seconds after first slow POST began','public_states_during_delivery':[s['state'] for s in during['services']],'public_states_after_delivery':[s['state'] for s in after['services']],'public_generation_unchanged_while_delivery':during['generated_at']==before['generated_at'],'collect_elapsed_seconds':round(elapsed,3),'confirmed_publication_coupling':during['generated_at']==before['generated_at'] and all(s['state']=='impaired' for s in after['services']),'command':args,'scope':'Synthetic loopback fixture only; current demo unchanged'}
finally:
 server.shutdown();server.server_close();(root/'evidence/slow-sink-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
