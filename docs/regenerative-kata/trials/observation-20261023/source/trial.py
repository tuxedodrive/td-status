"""48-hour private observation trial; loopback serving, no external alerts."""
import datetime as dt
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime';PUBLIC=RUNTIME/'public'
RUNTIME.mkdir(exist_ok=True);PUBLIC.mkdir(exist_ok=True)
STOP=threading.Event();INTERVAL=900;STALE=1800;DURATION=48*3600
def now():return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def save(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)
def append(path,value):
    with path.open('a') as f:f.write(json.dumps(value)+'\n')
class Quiet(BaseHTTPRequestHandler):
    server_version='ObservationBoard';sys_version=''
    def log_message(self,*args):pass
    def respond(self,code,body,kind='text/plain; charset=utf-8'):
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('X-Robots-Tag','noindex, nofollow, noarchive');self.send_header('Cache-Control','no-store');self.end_headers()
        if self.command!='HEAD':self.wfile.write(body)
class Page(Quiet):
    def do_GET(self):
        name={'/':'index.html','/index.html':'index.html','/status.json':'status.json','/robots.txt':'robots.txt'}.get(urllib.parse.urlsplit(self.path).path)
        if not name:return self.respond(404,b'Not found')
        path=PUBLIC/name
        if not path.exists():return self.respond(503,b'Observations not published yet')
        self.respond(200,path.read_bytes(),'text/html; charset=utf-8' if name.endswith('.html') else 'application/json' if name.endswith('.json') else 'text/plain')
    do_HEAD=do_GET
    def do_POST(self):self.respond(405,b'Read-only endpoint')
class Sink(Quiet):
    def do_POST(self):
        if self.path!='/events':return self.respond(404,b'Not found')
        size=int(self.headers.get('Content-Length','0'))
        if not 0<size<=65536:return self.respond(400,b'Invalid event')
        try:event=json.loads(self.rfile.read(size))
        except (ValueError,UnicodeError):return self.respond(400,b'Invalid event')
        append(RUNTIME/'local-events.jsonl',{'received_at':now(),'event':event});self.respond(204,b'')
    def do_GET(self):self.respond(404,b'Not found')
def serve(handler):
    server=ThreadingHTTPServer(('127.0.0.1',0),handler);server.daemon_threads=True
    threading.Thread(target=server.serve_forever,daemon=True).start();return server
def compare(mapping,model):
    candidate={s['id']:s for s in model['services']};result=[]
    for entry in mapping:
        item={'service_id':entry['neutral_id'],'fetched_at':now(),'source':'Existing repository observation, not a live truth oracle'}
        try:
            request=urllib.request.Request('https://raw.githubusercontent.com/tuxedodrive/td-status/main/history/'+entry['source_id']+'.yml',headers={'User-Agent':'ObservationTrial/1'})
            with urllib.request.urlopen(request,timeout=5) as response:text=response.read(16384).decode()
            fields=dict(line.split(':',1) for line in text.splitlines() if ':' in line)
            item.update(recorded_state=fields.get('status','').strip(),source_observed_at=fields.get('lastUpdated','').strip())
            source_at=dt.datetime.fromisoformat(item['source_observed_at'].replace('Z','+00:00'));actual=candidate[entry['neutral_id']]
            observed=dt.datetime.fromisoformat(actual['observed_at'].replace('Z','+00:00'))
            delta=abs((observed-source_at).total_seconds());item.update(candidate_state=actual['state'],candidate_observed_at=actual['observed_at'],timestamp_separation_seconds=delta,comparable_by_time=delta<=STALE)
            item['interpretation']='time-aligned comparison only, not correctness proof' if delta<=STALE else 'stale or temporally unaligned reference; not a candidate failure'
        except Exception as e:item.update(comparable_by_time=False,reference_unavailable=type(e).__name__)
        result.append(item)
    append(RUNTIME/'comparison.jsonl',{'at':now(),'comparisons':result})
def report(manifest,reason):
    cycles=[json.loads(x) for x in (RUNTIME/'cycles.jsonl').read_text().splitlines()] if (RUNTIME/'cycles.jsonl').exists() else []
    comparisons=[json.loads(x) for x in (RUNTIME/'comparison.jsonl').read_text().splitlines()] if (RUNTIME/'comparison.jsonl').exists() else []
    states={};transitions=[]
    for cycle in cycles:
        for service in cycle.get('services',[]):
            prior=states.get(service['id']);current=service['state']
            if prior is not None and prior!=current:transitions.append({'at':cycle['at'],'service_id':service['id'],'from':prior,'to':current})
            states[service['id']]=current
    flat=[x for c in comparisons for x in c['comparisons']]
    result={'trial_started_at':manifest.get('verified_at'),'planned_end':manifest.get('planned_end'),'reported_at':now(),'reason':reason,'cycles':len(cycles),'collection_failures':sum(c.get('exit')!=0 for c in cycles),'transitions':transitions,'last_states':states,'comparison_samples':len(flat),'time_aligned_reference_samples':sum(x.get('comparable_by_time',False) for x in flat),'unaligned_or_unavailable_samples':sum(not x.get('comparable_by_time',False) for x in flat),'caveat':'Stale reference history is not truth; no correctness score is inferred from unaligned observations. Raw cycles, timings, transitions and reference timestamps are retained privately. No customer writes or real notifications.'}
    save(RUNTIME/'completion-report.json',result)
    (RUNTIME/'completion-report.md').write_text('# Observation trial report\n\n'+json.dumps(result,indent=2)+'\n')
def main():
    if (RUNTIME/'trial.json').exists():raise SystemExit('Trial record already exists; inspect it before any restart')
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:STOP.set())
    page=serve(Page);sink=serve(Sink)
    private=json.loads((ROOT/'private-config.json').read_text());mapping=private.pop('comparison_mapping')
    private['notification_url']='http://127.0.0.1:'+str(sink.server_port)+'/events';save(RUNTIME/'config.json',private)
    (PUBLIC/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    base=[sys.executable,str(ROOT/'source/status.py')];args=['--config',str(RUNTIME/'config.json'),'--db',str(RUNTIME/'observations.sqlite')]
    manifest={'pid':os.getpid(),'command':[sys.executable,str(Path(__file__).resolve())],'url':'http://127.0.0.1:'+str(page.server_port)+'/','sink_port':sink.server_port,'access':'Existing authorized SSH forwarding only; loopback bind; noindex is not access control','base_revision':'f6cd5de26e30264947907aaa64526ba3e2e10c2a','interval_seconds':INTERVAL,'stale_after_seconds':STALE,'duration_seconds':DURATION,'prepared_at':now()};save(RUNTIME/'trial.json',manifest)
    deadline=None;reason='stopped';next_due=time.monotonic()
    try:
        while not STOP.is_set():
            started=time.monotonic()
            try:
                result=subprocess.run(base+['collect']+args+['--output',str(PUBLIC)],capture_output=True,text=True,timeout=75)
                model=json.loads((PUBLIC/'status.json').read_text()) if (PUBLIC/'status.json').exists() else {'services':[]}
                append(RUNTIME/'cycles.jsonl',{'at':now(),'exit':result.returncode,'elapsed_seconds':time.monotonic()-started,'services':model['services'],'stderr':result.stderr[:1000]})
                if result.returncode==0:
                    if deadline is None:
                        with urllib.request.urlopen(manifest['url'],timeout=3) as verified:assert verified.status==200
                        manifest['verified_at']=now();manifest['planned_end']=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=DURATION)).isoformat().replace('+00:00','Z');save(RUNTIME/'trial.json',manifest);deadline=time.monotonic()+DURATION
                    # Local delivery only, separate from collection/publication.
                    delivery=subprocess.run(base+['deliver']+args+['--max-events','20'],capture_output=True,text=True,timeout=65)
                    append(RUNTIME/'delivery.jsonl',{'at':now(),'exit':delivery.returncode,'destination':'Controlled loopback sink only'})
                    compare(mapping,model)
            except Exception as e:append(RUNTIME/'cycles.jsonl',{'at':now(),'exit':-1,'error':type(e).__name__})
            if deadline is not None and time.monotonic()>=deadline:reason='two-day interval completed';break
            if deadline is None and time.monotonic()-next_due>180:reason='initial verification failed';break
            next_due+=INTERVAL;wait=max(0,next_due-time.monotonic())
            if deadline is not None:wait=min(wait,max(0,deadline-time.monotonic()))
            STOP.wait(wait)
            if deadline is not None and time.monotonic()>=deadline:reason='two-day interval completed';break
    finally:
        report(manifest,reason);page.shutdown();page.server_close();sink.shutdown();sink.server_close();manifest['stopped_at']=now();manifest['stop_reason']=reason;save(RUNTIME/'trial.json',manifest)
if __name__=='__main__':main()
