"""Start/stop the isolated synthetic demo; no install, no public exposure."""
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parents[1]
runtime=root/'demo-runtime';runtime.mkdir(exist_ok=True)
record=runtime/'processes.json'
if len(sys.argv)>1 and sys.argv[1]=='stop':
    if record.exists():
        for p in json.loads(record.read_text())['processes']:
            try:
                actual=Path('/proc')/str(p['pid'])/'cmdline'
                expected=[str(x) for x in p['command']]
                parts=actual.read_bytes().decode().rstrip('\0').split('\0')
                if parts!=expected:raise SystemExit('PID identity changed; refusing to stop '+str(p['pid']))
                os.kill(p['pid'],signal.SIGTERM)
            except (ProcessLookupError,FileNotFoundError):pass
        print('Stopped recorded isolated demo processes')
    raise SystemExit()
if record.exists():raise SystemExit('Demo record already exists; inspect before starting another')
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
dependency_port=port();public_port=port()
c=json.loads((root/'builder-output/example.json').read_text())
c['services'][0]['url']=f'http://127.0.0.1:{dependency_port}/check'
c['notification_url']=f'http://127.0.0.1:{dependency_port}/events'
(runtime/'config.json').write_text(json.dumps(c,indent=2)+'\n')
processes=[]
def start(role,args):
    log=open(runtime/(role+'.log'),'ab')
    p=subprocess.Popen(args,cwd=runtime,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    processes.append({'role':role,'pid':p.pid,'command':args})
    return p
try:
    start('synthetic-dependency-and-sink',[sys.executable,str(root/'builder-output/demo.py'),'--port',str(dependency_port)])
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{dependency_port}/check',timeout=.2).close();break
        except OSError:time.sleep(.1)
    args=[sys.executable,str(root/'builder-output/status.py'),'run','--config',str(runtime/'config.json'),'--db',str(runtime/'state.sqlite'),'--output',str(runtime/'public'),'--interval','2']
    start('monitor',args)
    for _ in range(50):
        if (runtime/'public/index.html').exists():break
        time.sleep(.1)
    start('public-static-loopback',[sys.executable,'-m','http.server',str(public_port),'--bind','127.0.0.1','--directory',str(runtime/'public')])
    result={'purpose':'Live fully synthetic Groundhog Day demo; loopback-only, no external integration','dependency_port':dependency_port,'public_port':public_port,'processes':processes,'stop_command':'python3 evaluation/live_demo.py stop','policies':'2-second monitor/refresh, 20-second stale horizon, 1-second probe timeout: explicit demo choices, not user requirements'}
    record.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
except Exception:
    for p in processes:
        try:os.kill(p['pid'],signal.SIGTERM)
        except ProcessLookupError:pass
    raise
