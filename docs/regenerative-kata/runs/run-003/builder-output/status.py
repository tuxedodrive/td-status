#!/usr/bin/env python3
"""Standalone synthetic status monitor; Python standard library only."""
import argparse, datetime as dt, html, json, math, os, sqlite3, tempfile, time, urllib.request, urllib.error, urllib.parse, uuid

def stamp(value=None):
    d=dt.datetime.fromisoformat(value.replace('Z','+00:00')) if value else dt.datetime.now(dt.timezone.utc)
    if d.tzinfo is None: raise ValueError('timestamp requires timezone')
    return d.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
def positive(v):
    if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<=0: raise ValueError('policy must be positive finite number')
    return v
def urlcheck(v,schemes):
    if not isinstance(v,str): raise ValueError('URL must be string')
    p=urllib.parse.urlsplit(v)
    if p.scheme not in schemes or p.username is not None or p.password is not None or (p.scheme!='mailto' and not p.hostname): raise ValueError('invalid URL')
    if p.scheme=='mailto' and not p.path: raise ValueError('invalid support URL')
def config(path):
    with open(path) as f: c=json.load(f)
    for k in ('title','support_url'):
        if not isinstance(c.get(k),str) or not c[k].strip(): raise ValueError('missing '+k)
    urlcheck(c['support_url'],('https','mailto'))
    if not isinstance(c.get('services'),list) or not c['services']: raise ValueError('empty registry')
    ids=set()
    for s in c['services']:
        for k in ('id','name','impact'):
            if not isinstance(s.get(k),str) or not s[k].strip(): raise ValueError('invalid service text')
        if s['id'] in ids: raise ValueError('duplicate id')
        ids.add(s['id']); urlcheck(s['url'],('http','https'))
        if s.get('kind') not in ('first_party','provider_reachability'): raise ValueError('invalid kind')
        codes=s.get('expected_codes')
        if not isinstance(codes,list) or not codes or any(type(x)!=int or not 100<=x<=599 for x in codes): raise ValueError('invalid expected codes')
        if not isinstance(s.get('keywords'),list) or any(not isinstance(x,str) for x in s['keywords']): raise ValueError('invalid keywords')
        positive(s['timeout_seconds']); positive(s['stale_after_seconds'])
    positive(c.get('refresh_seconds',5))
    if c.get('notification_url') is not None: urlcheck(c['notification_url'],('http','https'))
    return c
def database(path):
    db=sqlite3.connect(path)
    db.executescript('''CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY,service_id TEXT,observed_at TEXT,success INTEGER,http_status INTEGER,elapsed_ms REAL,description TEXT);
    CREATE TABLE IF NOT EXISTS incidents(id INTEGER PRIMARY KEY,service_id TEXT,opened_at TEXT,resolved_at TEXT,description TEXT);
    CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,service_id TEXT,type TEXT,observed_at TEXT,description TEXT,delivered INTEGER DEFAULT 0);''')
    db.row_factory=sqlite3.Row
    return db
def probe(s):
    start=time.monotonic(); code=None
    try:
        try: response=urllib.request.urlopen(urllib.request.Request(s['url'],method='GET'),timeout=s['timeout_seconds'])
        except urllib.error.HTTPError as e: response=e
        with response:
            code=response.code; body=response.read(2*1024*1024).decode('utf-8','replace')
        ok=code in s['expected_codes'] and all(k.casefold() in body.casefold() for k in s['keywords'])
        reason='Expected response and content observed.' if ok else ('Unexpected HTTP status.' if code not in s['expected_codes'] else 'Required content was not observed.')
    except Exception:
        ok=False; reason='Network or timeout failure; endpoint could not be verified.'
    return ok,code,round((time.monotonic()-start)*1000,2),reason
def collect(c,db,now):
    with db:
        for s in c['services']:
            ok,code,elapsed,reason=probe(s)
            db.execute('INSERT INTO observations(service_id,observed_at,success,http_status,elapsed_ms,description) VALUES(?,?,?,?,?,?)',(s['id'],now,int(ok),code,elapsed,reason))
            incident=db.execute('SELECT id FROM incidents WHERE service_id=? AND resolved_at IS NULL ORDER BY id DESC LIMIT 1',(s['id'],)).fetchone()
            event=None
            if not ok and not incident:
                db.execute('INSERT INTO incidents(service_id,opened_at,description) VALUES(?,?,?)',(s['id'],now,'Check impaired; see the listed service impact.')); event='opened'
            elif ok and incident:
                db.execute('UPDATE incidents SET resolved_at=? WHERE id=?',(now,incident['id'])); event='resolved'
            if event and c.get('notification_url'):
                db.execute('INSERT INTO outbox(id,service_id,type,observed_at,description) VALUES(?,?,?,?,?)',(str(uuid.uuid4()),s['id'],event,now,'Check incident '+event+'.'))
def deliver(c,db):
    if not c.get('notification_url'): return
    ids={s['id'] for s in c['services']}
    for row in db.execute('SELECT * FROM outbox WHERE delivered=0 ORDER BY rowid').fetchall():
        if row['service_id'] not in ids: continue
        event={k:row[k] for k in ('id','service_id','type','observed_at','description')}
        try:
            req=urllib.request.Request(c['notification_url'],data=json.dumps(event).encode(),headers={'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req,timeout=5) as r:
                if 200<=r.status<300:
                    with db: db.execute('UPDATE outbox SET delivered=1 WHERE id=?',(row['id'],))
        except Exception: pass

def model(c,db,now):
    m={'generated_at':now,'title':c['title'],'support_url':c['support_url'],'refresh_seconds':c.get('refresh_seconds',5),'services':[],'incidents':[],'notification_events':[]}
    ids={s['id'] for s in c['services']}
    for s in c['services']:
        rows=db.execute('SELECT observed_at,success,http_status,elapsed_ms,description FROM observations WHERE service_id=? ORDER BY id DESC LIMIT 100',(s['id'],)).fetchall()[::-1]
        history=[dict(r) for r in rows]; last=history[-1] if history else None
        fresh=last and (dt.datetime.fromisoformat(now.replace('Z','+00:00'))-dt.datetime.fromisoformat(last['observed_at'].replace('Z','+00:00'))).total_seconds()<=s['stale_after_seconds']
        v={k:s[k] for k in ('id','name','kind','impact','stale_after_seconds')}
        v.update(state=('healthy' if last['success'] else 'impaired') if fresh else 'unknown',observed_at=last['observed_at'] if last else None,http_status=last['http_status'] if last else None,description=last['description'] if fresh else 'Evidence missing or stale; current health is unknown.',history=history)
        m['services'].append(v)
    for r in db.execute('SELECT service_id,opened_at,resolved_at,description FROM incidents ORDER BY id'):
        if r['service_id'] in ids: m['incidents'].append(dict(r))
    for r in db.execute('SELECT id,service_id,type,observed_at,delivered FROM outbox ORDER BY rowid'):
        if r['service_id'] in ids:
            x=dict(r); x['delivered']=bool(x['delivered']); m['notification_events'].append(x)
    return m

def page(m):
    esc=lambda x:html.escape(str(x),quote=True)
    cards=''.join('<article data-service-id="'+esc(s['id'])+'" data-state="'+s['state']+'"><h2>'+esc(s['name'])+'</h2><strong class="state">'+s['state'].title()+'</strong><p>'+esc(s['impact'])+'</p><time datetime="'+esc(s['observed_at'] or '')+'">'+esc(s['observed_at'] or 'No observation')+'</time><p>'+esc(s['description'])+'</p><p>Evidence expires after '+esc(s['stale_after_seconds'])+' seconds. '+('Provider reachability does not prove account credentials or end-to-end business health.' if s['kind']=='provider_reachability' else 'This check covers only the listed scope.')+'</p></article>' for s in m['services'])
    data=json.dumps(m).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+esc(m['title'])+'''</title><style>body{font:17px system-ui;margin:auto;padding:20px;max-width:960px;overflow-wrap:anywhere;background:#f6f8fa;color:#18212b}article{padding:18px;background:white;border:1px solid #ccd3db;border-radius:12px;margin:16px 0}.state{padding:4px 9px;border-radius:4px}[data-state=healthy] .state{color:#12612d;background:#d9f5e2}[data-state=impaired] .state{color:#a01a1a;background:#ffe1e1}[data-state=unknown] .state{color:#775000;background:#fff0bb}time{display:block}a{color:#164fa3}#support-link{display:inline-block;padding:10px 14px;border:2px solid #164fa3;border-radius:6px;font-weight:600}#banner{padding:12px;background:#fff0bb}</style><h1>'''+esc(m['title'])+'''</h1><p><a id="support-link" href="'''+esc(m['support_url'])+'''">Contact support</a></p><p>Snapshot observations of listed checks; scope is limited to each check.</p><noscript>JavaScript is disabled. These are snapshot observations, not a claim of current live health. Compare timestamps with the evidence limits.</noscript><p id="banner">Snapshot generated '''+esc(m['generated_at'])+'''</p><p id="summary"></p><main id="services">'''+cards+'''</main><h2>Incident history</h2><section id="incidents">'''+''.join('<p>'+esc(i['service_id'])+' — '+esc(i['opened_at'])+' — '+esc(i['resolved_at'] or 'Open')+'</p>' for i in m['incidents'])+'''</section><script id="status-data" type="application/json">'''+data+'''</script><script>
let model=JSON.parse(document.getElementById('status-data').textContent);
const el=(tag,text)=>{let n=document.createElement(tag);n.textContent=text;return n};
function valid(m){return m&&Number.isFinite(Date.parse(m.generated_at))&&Array.isArray(m.services)&&Array.isArray(m.incidents)&&m.services.every(s=>typeof s.id==='string'&&typeof s.name==='string'&&typeof s.impact==='string'&&['healthy','impaired','unknown'].includes(s.state)&&Number.isFinite(s.stale_after_seconds)&&s.stale_after_seconds>0&&(s.observed_at===null||Number.isFinite(Date.parse(s.observed_at))))}
function render(){let root=document.getElementById('services');root.replaceChildren();let count=0;
for(let s of model.services){let state=s.state;if(!s.observed_at||Date.now()-Date.parse(s.observed_at)>s.stale_after_seconds*1000)state='unknown';if(state!=='healthy')count++;
let a=el('article','');a.dataset.serviceId=s.id;a.dataset.state=state;a.append(el('h2',s.name));let st=el('strong',state[0].toUpperCase()+state.slice(1));st.className='state';a.append(st,el('p',s.impact));let t=el('time',s.observed_at||'No observation');if(s.observed_at)t.dateTime=s.observed_at;a.append(t,el('p',state==='unknown'?'Evidence missing or stale; current health is unknown.':s.description),el('p','Evidence expires after '+s.stale_after_seconds+' seconds. '+(s.kind==='provider_reachability'?'Provider reachability does not prove account credentials or end-to-end business health.':'This check covers only the listed scope.')));root.append(a)}
document.getElementById('summary').textContent=count?'Some listed checks are impaired or unknown; see individual impacts.':'All listed checks have healthy evidence within their observation limits.';
let age=Date.now()-Date.parse(model.generated_at);let limit=Math.min(...model.services.map(s=>s.stale_after_seconds))*1000;document.getElementById('banner').textContent=(age>limit?'Snapshot may be out of date. ':'Snapshot observations. ')+'Generated '+model.generated_at;
let incidents=document.getElementById('incidents');incidents.replaceChildren();for(let i of model.incidents)incidents.append(el('p',i.service_id+' — opened '+i.opened_at+' — '+(i.resolved_at?'resolved '+i.resolved_at:'Open')+' — '+i.description));}
render();setInterval(render,1000);
if(location.protocol==='http:'||location.protocol==='https:'){let busy=false;setInterval(async()=>{if(busy)return;busy=true;try{let r=await fetch('status.json',{cache:'no-store'});if(r.ok){let next=await r.json();if(valid(next)){model=next;render()}}}catch(e){}finally{busy=false}},model.refresh_seconds*1000)}
</script></html>'''
def atomic(path,content):
    fd,tmp=tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def export(c,db,out,now):
    m=model(c,db,now); os.makedirs(out,exist_ok=True)
    atomic(os.path.join(out,'status.json'),json.dumps(m,indent=2));atomic(os.path.join(out,'index.html'),page(m))
def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    for name in ('collect','export','run'):
        q=sub.add_parser(name)
        for k in ('config','db','output'): q.add_argument('--'+k,required=True)
        if name!='run': q.add_argument('--now')
        else: q.add_argument('--interval',type=float,required=True);q.add_argument('--iterations',type=int)
    a=p.parse_args()
    try:
        c=config(a.config)
        if a.command=='run':
            positive(a.interval)
            if a.iterations is not None and a.iterations<=0: raise ValueError('iterations must be positive')
        db=database(a.db)
        try:
            n=0
            while True:
                now=stamp(getattr(a,'now',None))
                if a.command!='export': collect(c,db,now);deliver(c,db)
                export(c,db,a.output,now);n+=1
                if a.command!='run' or (a.iterations is not None and n>=a.iterations): break
                time.sleep(a.interval)
        finally: db.close()
    except KeyboardInterrupt: return 0
    except Exception:
        print('Status operation failed: check configuration, database and output permissions.',file=__import__('sys').stderr);return 1
    return 0
if __name__=='__main__': raise SystemExit(main())
