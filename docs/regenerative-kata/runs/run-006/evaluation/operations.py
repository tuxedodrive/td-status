"""Independent loopback serving/backup boundary exercises; no builder imports."""
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parents[1]
work=root/json.loads((root/'evidence/latest-functional-work.json').read_text())['relative_path']
public=work/'public'
with socket.socket() as s:
    s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
process=subprocess.Popen([sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1','--directory',str(public)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
result={}
try:
    for _ in range(30):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=1) as r:
                page=r.read().decode(); result['http_status']=r.status
            break
        except OSError:
            time.sleep(.1)
    assert result.get('http_status')==200 and 'Groundhog Day' in page
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/status.json') as r:
        model=json.load(r)
    assert all(s['state']=='impaired' for s in model['services'])
    result['published_site_works_with_dependencies_and_monitor_stopped']=True
    backup=work/'backup.sqlite'; shutil.copy2(work/'observations.sqlite',backup)
    restored=work/'restored-public'
    args=[sys.executable,str(root/'builder-output/status.py'),'export','--config',str(work/'config.json'),'--db',str(backup),'--output',str(restored)]
    r=subprocess.run(args,capture_output=True,text=True,timeout=10)
    assert r.returncode==0, r.stderr
    model2=json.loads((restored/'status.json').read_text())
    assert [s['history'] for s in model2['services']]==[s['history'] for s in model['services']]
    assert model2['incidents']==model['incidents']
    result['backup_restore_preserves_observations_and_incidents']=True
    result['exposure']='127.0.0.1 only; temporary server stopped in finally'
finally:
    process.terminate(); process.wait(timeout=5)
    result['temporary_server_stopped']=process.poll() is not None
(root/'evidence/operations-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
