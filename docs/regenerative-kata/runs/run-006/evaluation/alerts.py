"""Independent durable notification boundary checks with loopback HTTP fixtures."""
import json
import tempfile
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

root=Path(__file__).resolve().parents[1]
generated=root/'evaluation/generated';generated.mkdir(parents=True,exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='alerts-',dir=generated))
state={'dependency':200,'sink':503}; received=[]; commands=[]; checks=[]
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(state['dependency']);self.end_headers();self.wfile.write(b'healthy')
    def do_POST(self):
        received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(state['sink']);self.end_headers()
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),H)
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}'
c={'title':'Groundhog Day alert demo','support_url':'https://support.example.invalid/help','refresh_seconds':1,'notification_url':url+'/sink','services':[{'id':'gd-app','name':'Groundhog Day Application','url':url+'/health','kind':'first_party','impact':'Core platform endpoint only','expected_codes':[200],'keywords':['healthy'],'timeout_seconds':.3,'stale_after_seconds':60}]}
(work/'config.json').write_text(json.dumps(c))
clock=datetime.now(timezone.utc)-timedelta(seconds=10)
def run(n):
    args=[sys.executable,str(root/'builder-output/status.py'),'collect','--config',str(work/'config.json'),'--db',str(work/'state.sqlite'),'--output',str(work/'public'),'--now',(clock+timedelta(seconds=n)).isoformat()]
    r=subprocess.run(args,capture_output=True,text=True,timeout=15);commands.append({'command':args,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr});assert r.returncode==0,r.stderr
    deliver_args=[sys.executable,str(root/'builder-output/status.py'),'deliver','--config',str(work/'config.json'),'--db',str(work/'state.sqlite'),'--max-events','10']
    delivered=subprocess.run(deliver_args,capture_output=True,text=True,timeout=15);assert delivered.returncode==0,delivered.stderr
    export_args=[sys.executable,str(root/'builder-output/status.py'),'export','--config',str(work/'config.json'),'--db',str(work/'state.sqlite'),'--output',str(work/'public'),'--now',(clock+timedelta(seconds=n)).isoformat()]
    exported=subprocess.run(export_args,capture_output=True,text=True,timeout=10);assert exported.returncode==0,exported.stderr
    commands.append({'command':deliver_args,'exit':delivered.returncode});commands.append({'command':export_args,'exit':exported.returncode})
    return json.loads((work/'public/status.json').read_text())
def check(name,condition):
    assert condition,name
    checks.append({'check':name,'outcome':'pass'})
try:
    a=run(0);check('Healthy initial observation sends no alert',not received)
    state['dependency']=502;b=run(1)
    events=b['notification_events'];check('Failure commits one pending opened event despite sink 503',len(events)==1 and events[0]['type']=='opened' and not events[0]['delivered'] and b['services'][0]['state']=='impaired')
    first_id=events[0]['id'];check('Pending event POST attempted with stable id',len(received)==1 and received[0]['id']==first_id)
    state['sink']=204;c=run(2)
    check('Restarted collection retries same event and marks delivered',len(received)==2 and received[1]['id']==first_id and c['notification_events'][0]['delivered'])
    d=run(3);check('Repeated impairment neither duplicates nor resends delivered event',len(received)==2 and len(d['notification_events'])==1)
    state['dependency']=200;e=run(4)
    check('Recovery sends one distinct resolved event',len(received)==3 and received[-1]['type']=='resolved' and received[-1]['id']!=first_id and all(x['delivered'] for x in e['notification_events']))
    f=run(5);check('Repeated success sends no duplicate recovery',len(received)==3)
    check('Alert payload contains safe event identity and no private probe URL',all(set(['id','service_id','type','observed_at','description'])<=set(x) and url not in json.dumps(x) for x in received))
finally:
    server.shutdown();server.server_close()
    (root/'evidence/alert-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    (root/'evidence/alert-results.json').write_text(json.dumps({'checks':checks,'received':received,'passed':len(checks)},indent=2)+'\n')
print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
