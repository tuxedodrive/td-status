"""Quiet read-only comparison against the existing page's exact data endpoint."""
import datetime as dt
import hashlib
import json
import signal
import threading
import time
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RUNTIME=ROOT/'runtime';STOP=threading.Event()
URL='https://raw.githubusercontent.com/tuxedodrive/td-status/master/history/summary.json'
def now():return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def main():
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:STOP.set())
    manifest=json.loads((RUNTIME/'trial.json').read_text());end=dt.datetime.fromisoformat(manifest['planned_end'].replace('Z','+00:00'))
    config=json.loads((ROOT/'private-config.json').read_text());mapping={x['source_id']:x['neutral_id'] for x in config['comparison_mapping']}
    samples=[];previous={};changes=[]
    while not STOP.is_set() and dt.datetime.now(dt.timezone.utc)<end:
        sample={'fetched_at':now(),'source':'Exact JSON endpoint used by the current public page','freshness':'Summary does not provide per-observation timestamps; HTTP response time is not observation time'}
        try:
            req=urllib.request.Request(URL,headers={'User-Agent':'ObservationTrial/1'})
            with urllib.request.urlopen(req,timeout=5) as r:body=r.read(500000);sample.update(http_status=r.status,etag=r.headers.get('ETag'),http_date=r.headers.get('Date'))
            source=json.loads(body);states={mapping[x['slug']]:x.get('status') for x in source if x.get('slug') in mapping}
            sample.update(content_sha256=hashlib.sha256(body).hexdigest(),service_states=states,coverage_count=len(states),source_observation_times_available=False)
            for sid,state in states.items():
                if sid in previous and previous[sid]!=state:changes.append({'noticed_at':sample['fetched_at'],'service_id':sid,'from':previous[sid],'to':state,'caveat':'Change noticed at fetch time; actual transition time not supplied'})
            previous=states
            candidate=json.loads((RUNTIME/'public/status.json').read_text());sample['candidate_observations']=[{'service_id':s['id'],'state':s['state'],'observed_at':s['observed_at']} for s in candidate['services']]
        except Exception as e:sample.update(error=type(e).__name__)
        samples.append(sample)
        with (RUNTIME/'live-reference.jsonl').open('a') as f:f.write(json.dumps(sample)+'\n')
        STOP.wait(min(900,max(0,(end-dt.datetime.now(dt.timezone.utc)).total_seconds())))
    report={'reported_at':now(),'samples':len(samples),'successful_samples':sum(s.get('http_status')==200 for s in samples),'coverage_counts':[s.get('coverage_count',0) for s in samples],'reference_changes_noticed':changes,'observation_time_caveat':'Live summary has no per-observation timestamps; do not infer correctness or actual outage boundaries from summary fetch times. Main-branch dated history is retained separately and may be stale.','no_external_messages':True}
    (RUNTIME/'live-reference-completion.json').write_text(json.dumps(report,indent=2)+'\n')
    if not STOP.is_set():
        for _ in range(120):
            path=RUNTIME/'completion-report.json'
            if path.exists():
                combined=json.loads(path.read_text());combined['live_page_reference']=report;path.write_text(json.dumps(combined,indent=2)+'\n');(RUNTIME/'completion-report.md').write_text('# Observation trial report\n\n'+json.dumps(combined,indent=2)+'\n');break
            time.sleep(1)
if __name__=='__main__':main()
