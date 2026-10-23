#!/usr/bin/env python3
import argparse, datetime as dt, html, json, math, sqlite3, time, urllib.request, urllib.error, urllib.parse, uuid, os, tempfile

def stamp(value=None):
    d=dt.datetime.fromisoformat(value.replace('Z','+00:00')) if value else dt.datetime.now(dt.timezone.utc)
    if d.tzinfo is None: raise ValueError('UTC timestamp needs timezone')
    return d.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
def seconds(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0: raise ValueError('positive finite policy required')
    return v
def url(v, schemes):
    if not isinstance(v,str): raise ValueError('URL required')
    p=urllib.parse.urlsplit(v)
    if p.scheme not in schemes or p.username is not None or p.password is not None or (p.scheme in ('http','https') and not p.hostname): raise ValueError('invalid URL')
    return v
def config(path):
    with open(path) as f: c=json.load(f)
    for k in ('title','support_url'):
        if not isinstance(c.get(k),str) or not c[k].strip(): raise ValueError('missing title/support')
    url(c['support_url'],('https','mailto'))
    if c.get('notification_url') is not None: url(c['notification_url'],('http','https'))
    c.setdefault('refresh_seconds',5); c.setdefault('refresh_timeout_seconds',3)
    seconds(c['refresh_seconds']); seconds(c['refresh_timeout_seconds'])
    if not isinstance(c.get('services'),list) or not c['services']: raise ValueError('empty registry')
    ids=set()
    for s in c['services']:
        for k in ('id','name','impact'):
            if not isinstance(s.get(k),str) or not s[k].strip(): raise ValueError('empty service field')
        if s['id'] in ids: raise ValueError('duplicate service id')
        ids.add(s['id']); url(s['url'],('http','https'))
        if s.get('kind') not in ('first_party','provider_reachability'): raise ValueError('invalid kind')
        codes=s.get('expected_codes')
        if not isinstance(codes,list) or not codes or any(type(x) is not int or not 100<=x<=599 for x in codes): raise ValueError('invalid codes')
        if not isinstance(s.get('keywords'),list) or any(not isinstance(x,str) for x in s['keywords']): raise ValueError('invalid keywords')
        seconds(s.get('timeout_seconds')); seconds(s.get('stale_after_seconds'))
    return c
def connect(path):
    db=sqlite3.connect(path,timeout=15); db.row_factory=sqlite3.Row
    db.executescript('''PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY,service_id TEXT,observed_at TEXT,outcome TEXT,http_status INTEGER,elapsed_ms INTEGER,description TEXT);
CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY,service_id TEXT,opened_at TEXT,resolved_at TEXT,description TEXT);
CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,service_id TEXT,type TEXT,observed_at TEXT,description TEXT,delivered INTEGER DEFAULT 0);
'''); return db
def probe(s):
    start=time.monotonic(); code=None
    try:
        try: r=urllib.request.urlopen(s['url'],timeout=s['timeout_seconds'])
        except urllib.error.HTTPError as e: r=e
        with r:
            code=r.code; body=r.read(2*1024*1024).decode('utf-8','replace')
        ok=code in s['expected_codes'] and all(k.lower() in body.lower() for k in s['keywords'])
        reason='Expected response and content observed.' if ok else ('Unexpected HTTP status.' if code not in s['expected_codes'] else 'Required content missing.')
    except Exception:
        ok=False; reason='Network request failed or timed out.'
    return ('healthy' if ok else 'impaired',code,round((time.monotonic()-start)*1000),reason)
def collect(c,db,now):
    results=[(s,probe(s)) for s in c['services']]
    with db:
        for s,(out,code,elapsed,reason) in results:
            db.execute('INSERT INTO observations(service_id,observed_at,outcome,http_status,elapsed_ms,description) VALUES(?,?,?,?,?,?)',(s['id'],now,out,code,elapsed,reason))
            active=db.execute('SELECT id FROM incidents WHERE service_id=? AND resolved_at IS NULL',(s['id'],)).fetchone()
            typ=None
            if out=='impaired' and not active:
                db.execute('INSERT INTO incidents VALUES(?,?,?,?,?)',(str(uuid.uuid4()),s['id'],now,None,reason)); typ='opened'
            elif out=='healthy' and active:
                db.execute('UPDATE incidents SET resolved_at=? WHERE id=?',(now,active['id'])); typ='resolved'
            if typ and c.get('notification_url'):
                db.execute('INSERT INTO outbox(id,service_id,type,observed_at,description) VALUES(?,?,?,?,?)',(str(uuid.uuid4()),s['id'],typ,now,reason))
def model(c,db,now):
    m={k:c[k] for k in ('title','support_url','refresh_seconds','refresh_timeout_seconds')}; m.update(generated_at=now,services=[],incidents=[],notification_events=[])
    current=dt.datetime.fromisoformat(now.replace('Z','+00:00'))
    for s in c['services']:
        rows=[dict(r) for r in db.execute('SELECT observed_at,outcome,http_status,elapsed_ms,description FROM observations WHERE service_id=? ORDER BY id DESC LIMIT 100',(s['id'],))][::-1]
        last=rows[-1] if rows else None
        state=last['outcome'] if last and (current-dt.datetime.fromisoformat(last['observed_at'].replace('Z','+00:00'))).total_seconds()<=s['stale_after_seconds'] else 'unknown'
        v={k:s[k] for k in ('id','name','kind','impact','stale_after_seconds')}; v.update(state=state,observed_at=last['observed_at'] if last else None,http_status=last['http_status'] if last else None,description=last['description'] if last else 'No observation available.',history=rows); m['services'].append(v)
        m['incidents'] += [dict(r) for r in db.execute('SELECT service_id,opened_at,resolved_at,description FROM incidents WHERE service_id=? ORDER BY opened_at',(s['id'],))]
        m['notification_events'] += [dict(r) for r in db.execute('SELECT id,service_id,type,observed_at,delivered FROM outbox WHERE service_id=? ORDER BY rowid',(s['id'],))]
    for e in m['notification_events']: e['delivered']=bool(e['delivered'])
    return m

def card(s):
    e=html.escape; state=s['state']; label=state.capitalize()
    return '<article data-service-id="'+e(s['id'],quote=True)+'" data-state="'+state+'"><h2>'+e(s['name'])+'</h2><strong class="state '+state+'">'+label+'</strong><p>'+e(s['impact'])+'</p><p>'+e(s['description'])+'</p><p>Snapshot observation: '+('<time datetime="'+e(s['observed_at'],quote=True)+'">'+e(s['observed_at'])+'</time>' if s['observed_at'] else 'none')+'</p><p>Evidence expires after '+str(s['stale_after_seconds'])+' seconds.</p>'+('<p>Provider reachability does not prove account credentials or end-to-end business health.</p>' if s['kind']=='provider_reachability' else '')+'</article>'
JS=r'''
let m=JSON.parse(document.getElementById('status-data').textContent), busy=false;
const el=(tag,text)=>{let n=document.createElement(tag);n.textContent=text;return n};
function render(){
 let now=Date.now(), unknown=0, impaired=0; let box=document.getElementById('services');box.replaceChildren();
 document.getElementById('title').textContent=m.title;document.getElementById('support-link').href=m.support_url;
 for(let s of m.services){let state=(!s.observed_at||now-Date.parse(s.observed_at)>s.stale_after_seconds*1000)?'unknown':s.state;
 if(state==='unknown')unknown++;if(state==='impaired')impaired++;
 let a=el('article','');a.dataset.serviceId=s.id;a.dataset.state=state;a.append(el('h2',s.name));let st=el('strong',state[0].toUpperCase()+state.slice(1));st.className='state '+state;a.append(st,el('p',s.impact),el('p',s.description));let p=el('p','Snapshot observation: ');if(s.observed_at){let t=el('time',s.observed_at);t.dateTime=s.observed_at;p.append(t)}else p.append('none');a.append(p,el('p','Evidence expires after '+s.stale_after_seconds+' seconds.'));if(s.kind==='provider_reachability')a.append(el('p','Provider reachability does not prove account credentials or end-to-end business health.'));box.append(a)}
 document.getElementById('summary').textContent=impaired+' listed checks impaired; '+unknown+' unknown. Scope and impact are shown for each check.';
 let limit=Math.min(...m.services.map(s=>s.stale_after_seconds));document.getElementById('banner').textContent=now-Date.parse(m.generated_at)>limit*1000?'Snapshot may be out of date. Published '+m.generated_at:'Published snapshot: '+m.generated_at;
 let history=document.getElementById('incidents');history.replaceChildren(el('h2','Incident history'));for(let i of m.incidents)history.append(el('p',i.service_id+': '+i.description+' Opened '+i.opened_at+(i.resolved_at?' Resolved '+i.resolved_at:' Unresolved')));
}
function valid(x){return x&&typeof x.title==='string'&&typeof x.support_url==='string'&&/^(https:|mailto:)/.test(x.support_url)&&Number.isFinite(x.refresh_seconds)&&x.refresh_seconds>0&&Number.isFinite(x.refresh_timeout_seconds)&&x.refresh_timeout_seconds>0&&Number.isFinite(Date.parse(x.generated_at))&&Array.isArray(x.services)&&x.services.length&&x.services.every(s=>typeof s.id==='string'&&typeof s.name==='string'&&typeof s.impact==='string'&&typeof s.description==='string'&&['healthy','impaired','unknown'].includes(s.state)&&Number.isFinite(s.stale_after_seconds)&&s.stale_after_seconds>0&&(s.observed_at===null||Number.isFinite(Date.parse(s.observed_at))))&&Array.isArray(x.incidents)}
async function poll(){if(busy)return;busy=true;let ac=new AbortController(),timer=setTimeout(()=>ac.abort(),m.refresh_timeout_seconds*1000);try{let r=await fetch('status.json',{cache:'no-store',signal:ac.signal});if(!r.ok)throw Error();let x=await r.json();if(!valid(x))throw Error();m=x;render()}catch(e){}finally{clearTimeout(timer);busy=false;setTimeout(poll,m.refresh_seconds*1000)}}
render();setInterval(render,1000);if(location.protocol==='http:'||location.protocol==='https:')setTimeout(poll,m.refresh_seconds*1000);
'''
def publish(c,db,out,now):
    m=model(c,db,now); data=json.dumps(m,ensure_ascii=True); safe=data.replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Service status</title><style>*{box-sizing:border-box}body{margin:0 auto;padding:18px;max-width:1000px;font:16px/1.5 system-ui;background:#f5f7fa;color:#17212b;overflow-wrap:anywhere}header{padding:10px 0}h1{margin:0 0 10px}#support-link{display:inline-block;background:#164a80;color:white;padding:12px 20px;border-radius:6px;font-weight:bold}#services{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:16px}article{background:white;padding:20px;border:1px solid #ccc;border-radius:8px}.state{display:inline-block;padding:5px 10px;border-radius:4px}.healthy{color:#11632b;background:#dcf5e4}.impaired{color:#a11818;background:#ffe3e3}.unknown{color:#795000;background:#fff0c2}#banner{padding:12px;background:#fff0c2}time{font-size:.9em}</style><header><h1 id="title">'''+html.escape(c['title'])+'</h1><a id="support-link" href="'+html.escape(c['support_url'],quote=True)+'">Contact support</a></header><p id="summary">Listed snapshot checks; see individual scope and impact.</p><p id="banner">Published snapshot: '+html.escape(now)+'</p><noscript>These are snapshot observations, not a claim of current live health. JavaScript is required to reassess aging evidence.</noscript><main id="services">'+''.join(card(s) for s in m['services'])+'</main><section id="incidents"><h2>Incident history</h2>'+''.join('<p>'+html.escape(i['service_id']+': '+i['description']+' Opened '+i['opened_at']+(' Resolved '+i['resolved_at'] if i['resolved_at'] else ' Unresolved'))+'</p>' for i in m['incidents'])+'</section><script id="status-data" type="application/json">'+safe+'</script><script>'+JS+'</script></html>'
    os.makedirs(out,exist_ok=True)
    for name,content in [('status.json',data),('index.html',page)]:
        fd,tmp=tempfile.mkstemp(dir=out,prefix='.publish-')
        try:
            with os.fdopen(fd,'w') as f: f.write(content);f.flush();os.fsync(f.fileno())
            os.replace(tmp,os.path.join(out,name))
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
def deliver(c,db,n):
    if not c.get('notification_url'):return
    ids={s['id'] for s in c['services']}
    rows=db.execute('SELECT id,service_id,type,observed_at,description FROM outbox WHERE delivered=0 AND service_id IN ('+','.join('?' for _ in ids)+') ORDER BY rowid LIMIT ?',(*ids,n)).fetchall()
    attempted=0
    for row in rows:
        if row['service_id'] not in ids:continue
        if attempted>=n:break
        attempted+=1
        req=urllib.request.Request(c['notification_url'],data=json.dumps(dict(row)).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=3) as r:ok=200<=r.status<300
        except Exception:ok=False
        if ok:
            with db:db.execute('UPDATE outbox SET delivered=1 WHERE id=?',(row['id'],))
def main():
    p=argparse.ArgumentParser(description='Standalone synthetic status monitor and separate delivery worker');sub=p.add_subparsers(dest='command',required=True)
    for cmd in ('collect','export','run','deliver'):
        q=sub.add_parser(cmd);q.add_argument('--config',required=True);q.add_argument('--db',required=True)
        if cmd!='deliver':q.add_argument('--output',required=True)
        if cmd in ('collect','export'):q.add_argument('--now')
        if cmd=='run':q.add_argument('--interval',required=True,type=float);q.add_argument('--iterations',type=int)
        if cmd=='deliver':q.add_argument('--max-events',required=True,type=int)
    a=p.parse_args()
    try:
        c=config(a.config)
        if a.command=='run':
            seconds(a.interval)
            if a.iterations is not None and a.iterations<1:raise ValueError('iterations must be positive')
        if a.command=='deliver' and a.max_events<0:raise ValueError('max-events must be nonnegative')
        db=connect(a.db)
        try:
            if a.command=='deliver':deliver(c,db,a.max_events)
            elif a.command=='run':
                count=0
                while a.iterations is None or count<a.iterations:
                    now=stamp();collect(c,db,now);publish(c,db,a.output,now);count+=1
                    if a.iterations is None or count<a.iterations:time.sleep(a.interval)
            else:
                now=stamp(a.now)
                if a.command=='collect':collect(c,db,now)
                publish(c,db,a.output,now)
        finally:db.close()
    except KeyboardInterrupt:return 0
    except Exception as e:
        p.exit(1,'Operation failed ('+type(e).__name__+'). Check configuration, database and output access.\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
