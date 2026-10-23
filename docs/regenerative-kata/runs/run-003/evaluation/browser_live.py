"""Independent open-page recovery/failed-refresh exercise via loopback HTTP only."""
import json
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

root=Path(__file__).resolve().parents[1]
work=root/'evaluation/work'
out=root/'browser-live';out.mkdir(exist_ok=True)
requests=[]
healthy=json.loads((work/'healthy/status.json').read_text())
recovered=json.loads((work/'recovered/status.json').read_text())
if os.environ.get('KATA_NEGATIVE_CONTROL')=='1':
    for service in recovered['services']: service['state']='impaired'
def page(case):
    source='failed' if case=='recover' else 'healthy'
    model=json.loads((work/source/'status.json').read_text())
    html=(work/source/'index.html').read_text()
    clock='let testNow=Date.parse('+json.dumps(model['generated_at'])+');Date.now=()=>testNow;'
    if case=='offline':clock+='setTimeout(()=>{testNow+=120000;},500);'
    html=html.replace('<script>','<script>'+clock,1)
    probe='''<script>setTimeout(()=>{const cards=[...document.querySelectorAll('[data-service-id]')];const e=document.createElement('script');e.id='live-proof';e.type='application/json';e.textContent=JSON.stringify({states:cards.map(c=>({id:c.dataset.serviceId,state:c.dataset.state,text:c.innerText})),summary:document.querySelector('#summary').innerText,support:document.querySelector('#support-link').href,aging:/out of date/i.test(document.querySelector('#banner').innerText),width:innerWidth,documentWidth:document.documentElement.scrollWidth});document.body.append(e);},12000);</script>'''
    return html.replace('</html>',probe+'</html>')
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        if self.path.endswith('status.json'):
            if self.path.startswith('/offline/'):
                self.send_response(503);self.end_headers();return
            data=json.dumps(recovered).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
        elif self.path.endswith('index.html'):
            data=page('offline' if self.path.startswith('/offline/') else 'recover').encode();self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(data)
        else:
            self.send_response(404);self.end_headers()
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),H)
threading.Thread(target=server.serve_forever,daemon=True).start()
results=[]
try:
    for case in ['recover','offline']:
        for label,w,h in [('phone',390,844),('square',720,720),('tablet',820,1180)]:
            name=case+'-'+label
            args=[sys.argv[1],'--headless','--user-data-dir=/tmp/priory-kata-browser-live003','--disable-background-networking','--disable-component-update','--no-first-run',f'--window-size={w},{h}','--virtual-time-budget=14000',f'--screenshot={out/(name+".png")}','--dump-dom',f'http://127.0.0.1:{server.server_port}/{case}/index.html']
            r=subprocess.run(args,capture_output=True,text=True,check=True,timeout=30)
            match=re.search(r'<script id="live-proof" type="application/json">(.*?)</script>',r.stdout,re.S);assert match,name+': no proof'
            proof=json.loads(match.group(1));proof['case']=name
            expected='healthy' if case=='recover' else 'unknown'
            assert len(proof['states'])==10 and all(x['state']==expected for x in proof['states']),(name,proof)
            assert proof['documentWidth']<=w,name+': overflow'
            assert proof['support']=='https://support.example.invalid/help',name+': support'
            if case=='offline':assert proof['aging'],name+': stale publication warning'
            proof['outcome']='pass';results.append(proof)
    assert any('/recover/status.json' in r for r in requests),'No live model poll occurred'
    assert any('/offline/status.json' in r for r in requests),'No failed refresh exercised'
finally:
    server.shutdown();server.server_close()
(out/'results.json').write_text(json.dumps({'results':results,'requests':requests,'server':'Temporary loopback-only evaluator fixture; stopped','scope':'Open-page recovery without manual reload, failed refresh preserves evidence age'},indent=2)+'\n')
print(json.dumps({'passed':len(results),'requests':len(requests)},indent=2))
