"""Independent hung-fetch -> available-recovery browser boundary exercise."""
import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
root=Path(__file__).resolve().parents[1]
pointer=root/'evidence/latest-functional-work.json'
work=root/json.loads(pointer.read_text())['relative_path'] if pointer.exists() else root/'evaluation/work'
failed=json.loads((work/'failed/status.json').read_text());recovered=json.loads((work/'recovered/status.json').read_text())
failed['refresh_seconds']=1;failed['refresh_timeout_seconds']=.5
html=(work/'failed/index.html').read_text()
html=re.sub(r'(<script id="status-data" type="application/json">).*?(</script>)',lambda m:m.group(1)+json.dumps(failed).replace('<','\\u003c')+m.group(2),html,flags=re.S)
setup='const testStarted=performance.now();Date.now=()=>performance.now()-testStarted+Date.parse('+json.dumps(failed['generated_at'])+');let testCalls=0;window.fetch=(url,opts={})=>{testCalls++;if(testCalls===1){return new Promise((resolve,reject)=>{if(opts.signal){opts.signal.addEventListener("abort",()=>reject(new DOMException("Aborted","AbortError")));}});}return Promise.resolve({ok:true,json:()=>Promise.resolve('+json.dumps(recovered).replace('<','\\u003c')+')});};'
html=html.replace('<script>','<script>'+setup,1)
probe='''<script>setTimeout(()=>{const e=document.createElement('script');e.id='hung-proof';e.type='application/json';e.textContent=JSON.stringify({calls:testCalls,states:[...document.querySelectorAll('[data-service-id]')].map(x=>x.dataset.state)});document.body.append(e);},3500);</script>'''
html=html.replace('</html>',probe+'</html>')
class H(BaseHTTPRequestHandler):
 def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(html.encode())
 def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),H);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 args=[sys.argv[1],'--headless','--user-data-dir=/tmp/priory-hung-fetch-review','--disable-background-networking','--disable-component-update','--no-first-run','--window-size=390,844','--virtual-time-budget=4500','--dump-dom',f'http://127.0.0.1:{server.server_port}/']
 r=subprocess.run(args,capture_output=True,text=True,timeout=20,check=True)
 match=re.search(r'<script id="hung-proof" type="application/json">(.*?)</script>',r.stdout,re.S);assert match,'browser proof missing'
 result=json.loads(match.group(1));result['fixture']='First fetch never resolves unless aborted; subsequent requests expose successful recovery';result['policy']='1s polling / 0.5s deadline; result captured at 3.5s synthetic browser time';result['passed']=result['calls']>=2 and len(result['states'])==10 and all(s=='healthy' for s in result['states'])
 (root/'evidence/browser-hung-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['passed'],'Hung fetch prevented later recovery'
finally:server.shutdown();server.server_close()
