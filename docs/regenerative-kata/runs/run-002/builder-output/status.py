#!/usr/bin/env python3
"""Standalone dependency observations and static status snapshots."""
import argparse
import datetime as dt
import html
import json
import math
import os
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

UTC = dt.timezone.utc

def stamp(value=None):
    d = dt.datetime.now(UTC) if value is None else dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None or d.utcoffset() != dt.timedelta(0):
        raise ValueError('Timestamp must include UTC timezone')
    return d.isoformat().replace('+00:00', 'Z')

def seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('Timing values must be positive finite numbers')
    return value

def config(path):
    with open(path, encoding='utf-8') as f:
        c = json.load(f)
    for key in ('title', 'support_url'):
        if not isinstance(c.get(key), str) or not c[key].strip():
            raise ValueError('Missing title or support URL')
    u = urllib.parse.urlsplit(c['support_url'])
    if u.scheme not in ('https', 'mailto') or (u.scheme == 'https' and not u.hostname) or (u.scheme == 'mailto' and not u.path) or u.username or u.password:
        raise ValueError('Invalid support URL')
    if not isinstance(c.get('services'), list) or not c['services']:
        raise ValueError('Registry must be nonempty')
    ids = set()
    for s in c['services']:
        for k in ('id', 'name', 'url', 'kind', 'impact'):
            if not isinstance(s.get(k), str) or not s[k].strip():
                raise ValueError('Missing service field')
        if s['id'] in ids:
            raise ValueError('Duplicate service id')
        ids.add(s['id'])
        u = urllib.parse.urlsplit(s['url'])
        if u.scheme not in ('http', 'https') or not u.hostname or u.username is not None or u.password is not None:
            raise ValueError('Invalid probe URL')
        u.port
        if s['kind'] not in ('first_party', 'provider_reachability'):
            raise ValueError('Invalid service kind')
        codes = s.get('expected_codes')
        if not isinstance(codes, list) or not codes or any(type(v) is not int or not 100 <= v <= 599 for v in codes):
            raise ValueError('Invalid expected codes')
        if not isinstance(s.get('keywords'), list) or any(not isinstance(v, str) or not v.strip() for v in s['keywords']):
            raise ValueError('Invalid keywords')
        seconds(s.get('timeout_seconds'))
        seconds(s.get('stale_after_seconds'))
    return c

def database(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''CREATE TABLE IF NOT EXISTS observations (
        seq INTEGER PRIMARY KEY, service_id TEXT NOT NULL, observed_at TEXT NOT NULL,
        outcome TEXT NOT NULL, http_status INTEGER, elapsed_ms REAL NOT NULL, description TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS observation_service ON observations(service_id,seq);
        CREATE TABLE IF NOT EXISTS incidents (
        seq INTEGER PRIMARY KEY, service_id TEXT NOT NULL, opened_at TEXT NOT NULL,
        resolved_at TEXT, description TEXT NOT NULL);''')
    return db

def probe(s):
    start = time.monotonic()
    code = None
    try:
        req = urllib.request.Request(s['url'], method='GET', headers={'User-Agent': 'GroundhogStatus/1'})
        try:
            response = urllib.request.urlopen(req, timeout=s['timeout_seconds'])
        except urllib.error.HTTPError as e:
            response = e
        with response:
            code = response.code
            # Bound downloaded evidence and total reading time, even for streaming endpoints.
            deadline = start + s['timeout_seconds']
            chunks = []
            size = 0
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError()
                chunk = response.read1(8192)
                if not chunk:
                    break
                size += len(chunk)
                if size > 2 * 1024 * 1024:
                    return ('impaired', code, (time.monotonic()-start)*1000, 'Response exceeded evidence size limit.')
                chunks.append(chunk)
            body = b''.join(chunks).decode('utf-8', errors='replace').casefold()
        if code not in s['expected_codes']:
            outcome, reason = 'impaired', 'HTTP response did not match the configured expected codes.'
        elif not all(word.casefold() in body for word in s['keywords']):
            outcome, reason = 'impaired', 'Required response content was missing.'
        else:
            outcome, reason = 'healthy', 'Configured HTTP and content checks passed.'
    except (TimeoutError, OSError, urllib.error.URLError, ValueError):
        outcome, reason = 'impaired', 'Network request failed or exceeded its timeout.'
    return outcome, code, round((time.monotonic()-start)*1000, 2), reason

def collect(c, db, now):
    results = [(s['id'], stamp(now), *probe(s)) for s in c['services']]
    with db:
        for sid, observed, outcome, code, elapsed, reason in results:
            db.execute('INSERT INTO observations(service_id,observed_at,outcome,http_status,elapsed_ms,description) VALUES(?,?,?,?,?,?)', (sid, observed, outcome, code, elapsed, reason))
            active = db.execute('SELECT seq FROM incidents WHERE service_id=? AND resolved_at IS NULL', (sid,)).fetchone()
            if outcome == 'impaired' and not active:
                db.execute('INSERT INTO incidents(service_id,opened_at,description) VALUES(?,?,?)', (sid, observed, reason))
            if outcome == 'healthy' and active:
                db.execute('UPDATE incidents SET resolved_at=? WHERE seq=?', (observed, active[0]))

def model(c, db, now):
    public = {'generated_at': stamp(now), 'services': [], 'incidents': []}
    at = dt.datetime.fromisoformat(public['generated_at'].replace('Z', '+00:00'))
    for s in c['services']:
        rows = db.execute('SELECT observed_at,outcome,http_status,elapsed_ms,description FROM (SELECT * FROM observations WHERE service_id=? ORDER BY seq DESC LIMIT 200) ORDER BY seq', (s['id'],)).fetchall()
        history = [dict(zip(('observed_at','outcome','http_status','elapsed_ms','description'), r)) for r in rows]
        last = history[-1] if history else None
        fresh = last and (at - dt.datetime.fromisoformat(last['observed_at'].replace('Z','+00:00'))).total_seconds() <= s['stale_after_seconds']
        item = {k:s[k] for k in ('id','name','kind','impact','stale_after_seconds')}
        item.update(state=last['outcome'] if fresh else 'unknown', observed_at=last['observed_at'] if last else None, http_status=last['http_status'] if last else None, description=last['description'] if fresh else 'No fresh observation is available; current health is unknown.', history=history)
        public['services'].append(item)
        for row in db.execute('SELECT opened_at,resolved_at,description FROM incidents WHERE service_id=? ORDER BY seq DESC LIMIT 200', (s['id'],)):
            public['incidents'].append(dict(service_id=s['id'], opened_at=row[0], resolved_at=row[1], description=row[2]))
    public['incidents'].sort(key=lambda x:x['opened_at'])
    return public

def render(c, m):
    e = html.escape
    cards = []
    for s in m['services']:
        limit = ('This checks provider reachability only; it does not prove account credentials or end-to-end business health.' if s['kind']=='provider_reachability' else 'This checks the configured endpoint and required content; it does not prove every customer workflow.')
        observed = '<time datetime="'+e(s['observed_at'])+'">'+e(s['observed_at'])+'</time>' if s['observed_at'] else 'No observation yet'
        cards.append(f'<article data-service-id="{e(s["id"],quote=True)}" data-state="{s["state"]}"><h2>{e(s["name"])}</h2><strong class="state">{s["state"].title()}</strong><p class="description">{e(s["description"])}</p><p>Impact: {e(s["impact"])}</p><p>Observed: {observed}</p><p>Evidence expires after {s["stale_after_seconds"]} seconds. {limit}</p></article>')
    events = ''.join('<li>'+e(i['service_id'])+': '+e(i['description'])+' Opened <time datetime="'+e(i['opened_at'])+'">'+e(i['opened_at'])+'</time>; '+('resolved <time datetime="'+e(i['resolved_at'])+'">'+e(i['resolved_at'])+'</time>' if i['resolved_at'] else 'unresolved')+'</li>' for i in m['incidents'])
    data = json.dumps(m, ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+e(c['title'])+'''</title><style>
*{box-sizing:border-box}body{font:17px/1.5 system-ui,sans-serif;margin:auto;padding:20px;max-width:1100px;color:#172331;background:#f5f7fa;overflow-wrap:anywhere}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:16px}article{background:white;border:1px solid #ccd3dc;border-radius:12px;padding:20px;min-width:0}.state{display:inline-block;padding:4px 12px;border-radius:5px}article[data-state=healthy] .state{color:#126331;background:#daf4e2}article[data-state=impaired] .state{color:#a31823;background:#ffe1e4}article[data-state=unknown] .state{color:#805400;background:#fff0bc}a{color:#164fa2}#aging{background:#fff0bc;padding:12px}h1{font-size:2rem}time{font-size:.9em}</style><body><h1>'''+e(c['title'])+'''</h1><p id="summary">Snapshot observations of listed checks; review individual scopes and timestamps.</p><p>Snapshot generated <time datetime="'''+e(m['generated_at'])+'">'+e(m['generated_at'])+'''</time>.</p><p id="aging">Snapshot evidence ages over time. Current health may be unknown.</p><noscript><p>JavaScript is disabled: these are snapshot observations, not current live health. Compare observation times before relying on them.</p></noscript><p><a id="support-link" href="'''+e(c['support_url'],quote=True)+'''">Contact support</a></p><main>'''+''.join(cards)+'''</main><h2>Incident history</h2><ul>'''+(events or '<li>No recorded incidents for listed checks.</li>')+'''</ul><script id="status-data" type="application/json">'''+data+'''</script><script>
const model=JSON.parse(document.getElementById('status-data').textContent);
function refresh(){const now=Date.now();let impaired=0,unknown=0;const cards=Array.from(document.querySelectorAll('[data-service-id]'));for(const s of model.services){const card=cards.find(c=>c.dataset.serviceId===s.id);const old=!s.observed_at||now-Date.parse(s.observed_at)>s.stale_after_seconds*1000;const state=old?'unknown':s.state;card.dataset.state=state;card.querySelector('.state').textContent=state[0].toUpperCase()+state.slice(1);if(old)card.querySelector('.description').textContent='Evidence is missing or stale; current health is unknown.';impaired+=state==='impaired';unknown+=state==='unknown';}document.getElementById('summary').textContent=impaired||unknown?`${impaired} listed checks impaired; ${unknown} unknown. Review each check for its customer impact.`:'All listed checks have healthy observations within their evidence limits.';const age=now-Date.parse(model.generated_at);const limit=Math.min(...model.services.map(s=>s.stale_after_seconds))*1000;document.getElementById('aging').hidden=age<=limit;document.getElementById('aging').textContent='This snapshot may be out of date. Review evidence timestamps; the monitor may be offline.';}
refresh();setInterval(refresh,1000);
</script></body></html>'''

def atomic(path, content):
    fd, temporary = tempfile.mkstemp(prefix='.status-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def export(c, db, output, now):
    m = model(c, db, now)
    os.makedirs(output, exist_ok=True)
    atomic(os.path.join(output,'status.json'), json.dumps(m, indent=2)+'\n')
    atomic(os.path.join(output,'index.html'), render(c,m))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('collect','export','run'):
        a = sub.add_parser(name)
        a.add_argument('--config', required=True)
        a.add_argument('--db', required=True)
        a.add_argument('--output', required=True)
        if name != 'run':
            a.add_argument('--now', help='UTC ISO timestamp for deterministic observation/export')
        else:
            a.add_argument('--interval', type=float, required=True)
            a.add_argument('--iterations', type=int)
    args = p.parse_args()
    try:
        c = config(args.config)
        if args.command == 'run':
            seconds(args.interval)
            if args.iterations is not None and args.iterations <= 0:
                raise ValueError('Iterations must be positive')
        now = stamp(getattr(args,'now',None))
        with database(args.db) as db:
            if args.command == 'run':
                count = 0
                while args.iterations is None or count < args.iterations:
                    collect(c, db, None)
                    export(c, db, args.output, None)
                    count += 1
                    if args.iterations is None or count < args.iterations:
                        time.sleep(args.interval)
            else:
                if args.command == 'collect':
                    collect(c, db, now)
                export(c, db, args.output, now)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print('Status operation failed: check configuration, database and output permissions.', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
