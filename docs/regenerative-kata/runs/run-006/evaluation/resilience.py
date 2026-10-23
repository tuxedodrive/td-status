"""Independent collection/publication versus stalled alert worker boundary."""
import json
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
root=Path(__file__).resolve().parents[1];generated=root/'evaluation/generated';generated.mkdir(parents=True,exist_ok=True);work=Path(tempfile.mkdtemp(prefix='resilience-',dir=generated));state={'code':200,'delay':2};posts=[];first=threading.Event();checks=[]
class H(BaseHTTPRequestHandler):
 def do_GET(self):self.send_response(state['code']);self.end_headers();self.wfile.write(b'healthy')
 def do_POST(self):
  posts.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))));first.set();time.sleep(state['delay']);self.send_response(204);self.end_headers()
 def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),H);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
c={'title':'Groundhog Day independent alert worker test','support_url':'https://support.example.invalid/help','notification_url':url+'/events','services':[{'id':'gd-'+str(i),'name':'Groundhog Day '+str(i),'url':url+'/health','kind':'first_party','impact':'Synthetic endpoint only','expected_codes':[200],'keywords':['healthy'],'timeout_seconds':.3,'stale_after_seconds':60} for i in range(3)]}
(work/'config.json').write_text(json.dumps(c));base=['--config',str(work/'config.json'),'--db',str(work/'state.sqlite')]
def cli(command,extra=None):
 args=[sys.executable,str(root/'builder-output/status.py'),command]+base+(extra or []);start=time.monotonic();r=subprocess.run(args,capture_output=True,text=True,timeout=12);assert r.returncode==0,(args,r.stderr);return time.monotonic()-start
def collect():return cli('collect',['--output',str(work/'public')])
def model():return json.loads((work/'public/status.json').read_text())
def check(name,ok):assert ok,name;checks.append({'check':name,'outcome':'pass'})
worker=None
try:
 collect();state['code']=502;elapsed=collect()
 check('Collection never calls sink and publishes impairment independently',not posts and elapsed<1.5 and all(s['state']=='impaired' for s in model()['services']))
 args=[sys.executable,str(root/'builder-output/status.py'),'deliver']+base+['--max-events','1'];worker=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 assert first.wait(5),'worker did not attempt queued event'
 state['code']=200;elapsed2=collect()
 check('Recovery collection/export proceeds while delivery worker is stalled',elapsed2<1.5 and all(s['state']=='healthy' for s in model()['services']))
 worker.communicate(timeout=8);assert worker.returncode==0
 check('Delivery max-events bounds backlog drain',len(posts)==1)
 state['delay']=0;cli('deliver',['--max-events','10']);cli('export',['--output',str(work/'public')])
 events=model()['notification_events'];check('Queued openings and recoveries survive then deliver without loss',len(events)==6 and all(e['delivered'] for e in events) and len({e['id'] for e in posts})==6)
 result={'checks':checks,'passed':len(checks),'failure_collect_seconds':elapsed,'recovery_collect_during_stall_seconds':elapsed2,'sink_delay_seconds':2,'synthetic_budget_seconds':1.5,'explanation':'1.5s is a local test budget with fast loopback probes, not a production service promise','relative_work':str(work.relative_to(root))}
finally:
 if worker and worker.poll() is None:worker.terminate();worker.wait(timeout=5)
 server.shutdown();server.server_close()
(root/'evidence/resilience-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
