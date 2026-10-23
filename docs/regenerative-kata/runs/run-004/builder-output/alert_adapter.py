#!/usr/bin/env python3
"""Loopback alert receiver; standard library only."""
import argparse
import datetime
import email.message
import http.server
import ipaddress
import json
import os
import re
import smtplib
import sqlite3
import ssl
import urllib.parse
import urllib.request

TIMEOUT = 10

def require(ok):
    if not ok:
        raise ValueError('invalid configuration or input')

def safe(value, nonempty=True):
    require(isinstance(value, str) and (bool(value.strip()) or not nonempty))
    require(not any(ord(c) < 32 and c not in '\n\t' for c in value))
    return value

def header(value):
    safe(value)
    require('\r' not in value and '\n' not in value)
    return value

def loopback(host):
    if host.lower() == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False

def secret(name):
    require(isinstance(name, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name))
    require(name in os.environ and bool(os.environ[name]))
    return os.environ[name]

def load_config(path):
    with open(path, encoding='utf-8') as f:
        c = json.load(f)
    require(isinstance(c, dict) and any(k in c for k in ('email', 'github')))
    names = c.get('service_names', {})
    require(isinstance(names, dict))
    for k, v in names.items():
        header(k); header(v)
    if 'email' in c:
        e = c['email']; require(isinstance(e, dict))
        header(e['smtp_host']); header(e['from_address'])
        require(isinstance(e['smtp_port'], int) and not isinstance(e['smtp_port'], bool) and 0 < e['smtp_port'] < 65536)
        require(type(e['starttls']) is bool)
        require(isinstance(e['to_addresses'], list) and bool(e['to_addresses']))
        for a in e['to_addresses']: header(a)
        require(('username_env' in e) == ('password_env' in e))
        if 'username_env' in e:
            e['_username'] = secret(e['username_env']); e['_password'] = secret(e['password_env'])
        require(loopback(e['smtp_host']) or (e['starttls'] and 'username_env' in e))
    if 'github' in c:
        g = c['github']; require(isinstance(g, dict))
        u = urllib.parse.urlsplit(g['api_base'])
        require(u.hostname and not u.username and not u.password and not u.query and not u.fragment)
        require(u.scheme == 'https' or (u.scheme == 'http' and loopback(u.hostname)))
        require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', g['repository']) is not None)
        g['_token'] = secret(g['token_env']); header(g['_token'])
        header(g.get('user_agent', 'alert-adapter/1'))
        g['api_base'] = g['api_base'].rstrip('/')
    return c

def validate_event(e):
    require(isinstance(e, dict))
    for key in ('id', 'service_id'): header(e[key])
    require(e['type'] in ('opened', 'resolved'))
    header(e['observed_at'])
    dt = datetime.datetime.fromisoformat(e['observed_at'].replace('Z', '+00:00'))
    require(dt.tzinfo is not None and dt.utcoffset() == datetime.timedelta(0))
    safe(e['description'], False)
    require('-->' not in e['service_id'] and '<!--' not in e['service_id'])
    return e

class Adapter:
    def __init__(self, config, path):
        self.c = config
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS deliveries (event_id TEXT, transport TEXT, PRIMARY KEY(event_id, transport));
        CREATE TABLE IF NOT EXISTS issues (service_id TEXT PRIMARY KEY, number INTEGER NOT NULL);''')
        self.db.commit()

    def request(self, method, suffix, data=None):
        g = self.c['github']
        req = urllib.request.Request(g['api_base'] + '/repos/' + g['repository'] + suffix,
            data=None if data is None else json.dumps(data).encode(), method=method,
            headers={'Authorization': 'Bearer ' + g['_token'], 'Accept': 'application/vnd.github+json',
                     'User-Agent': g.get('user_agent', 'alert-adapter/1'), 'Content-Type': 'application/json'})
        # Do not follow redirects: credentials must stay on the configured destination.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=TIMEOUT) as response:
            require(200 <= response.status < 300)
            body = response.read(2 * 1024 * 1024 + 1)
            require(len(body) <= 2 * 1024 * 1024)
            return json.loads(body) if body else None

    def github(self, e, name, body):
        service = e['service_id']
        marker = '<!-- status-service:' + service + ' -->'
        row = self.db.execute('SELECT number FROM issues WHERE service_id=?', (service,)).fetchone()
        number = row[0] if row else None
        if e['type'] == 'opened':
            if number is None:
                result = self.request('POST', '/issues', {'title': 'Service Alert: ' + name, 'body': body + '\n' + marker})
                require(isinstance(result, dict) and type(result.get('number')) is int and result['number'] > 0)
                self.db.execute('INSERT INTO issues VALUES (?,?)', (service, result['number']))
        else:
            if number is None:
                result = self.request('GET', '/issues?state=open&per_page=100')
                require(isinstance(result, list))
                for issue in result:
                    require(isinstance(issue, dict))
                    if marker in (issue.get('body') or '') and not issue.get('pull_request'):
                        require(type(issue.get('number')) is int and issue['number'] > 0)
                        number = issue['number']; break
            if number is not None:
                result = self.request('PATCH', '/issues/' + str(number), {'state': 'closed', 'state_reason': 'completed'})
                require(isinstance(result, dict) and type(result.get('number')) is int and result['number'] == number)
            self.db.execute('DELETE FROM issues WHERE service_id=?', (service,))

    def email(self, e, name, body):
        c = self.c['email']
        msg = email.message.EmailMessage()
        msg['From'] = c['from_address']; msg['To'] = ', '.join(c['to_addresses'])
        msg['Subject'] = 'Service Alert: ' + name + ' — ' + e['type']
        msg.set_content(body, charset='utf-8')
        with smtplib.SMTP(c['smtp_host'], c['smtp_port'], timeout=TIMEOUT) as smtp:
            if c['starttls']: smtp.starttls(context=ssl.create_default_context())
            if '_username' in c: smtp.login(c['_username'], c['_password'])
            refused = smtp.send_message(msg)
            require(not refused)

    def deliver(self, e):
        payload = json.dumps(e, sort_keys=True, ensure_ascii=False)
        row = self.db.execute('SELECT payload FROM events WHERE id=?', (e['id'],)).fetchone()
        if row:
            require(row[0] == payload)
        else:
            self.db.execute('INSERT INTO events VALUES (?,?)', (e['id'], payload)); self.db.commit()
        name = self.c.get('service_names', {}).get(e['service_id'], e['service_id'])
        body = '\n'.join(('Service: ' + name, 'Type: ' + e['type'], 'Time: ' + e['observed_at'],
                          'Description: ' + e['description'], 'Event id: ' + e['id']))
        for transport in ('email', 'github'):
            if transport not in self.c: continue
            if self.db.execute('SELECT 1 FROM deliveries WHERE event_id=? AND transport=?', (e['id'], transport)).fetchone(): continue
            try:
                getattr(self, transport)(e, name, body)
                self.db.execute('INSERT INTO deliveries VALUES (?,?)', (e['id'], transport)); self.db.commit()
            except Exception:
                self.db.rollback(); raise

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, status):
        self.send_response(status); self.send_header('Content-Length', '0'); self.end_headers()
    def do_POST(self):
        if self.path != '/events': self.reply(404); return
        try:
            require(not self.headers.get('Transfer-Encoding'))
            length = int(self.headers.get('Content-Length', '0')); require(0 < length <= 1024 * 1024)
            e = validate_event(json.loads(self.rfile.read(length)))
        except Exception:
            self.reply(400); return
        try: self.server.adapter.deliver(e)
        except Exception: self.reply(503); return
        self.reply(204)
    def do_GET(self): self.reply(404)
    def setup(self):
        super().setup(); self.connection.settimeout(TIMEOUT)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--db', required=True)
    p.add_argument('--host', default='127.0.0.1'); p.add_argument('--port', type=int, required=True)
    args = p.parse_args()
    try:
        require(loopback(args.host) and 0 <= args.port <= 65535)
        adapter = Adapter(load_config(args.config), args.db)
        class Server(http.server.HTTPServer): pass
        if ':' in args.host:
            import socket
            Server.address_family = socket.AF_INET6
        server = Server((args.host, args.port), Handler); server.adapter = adapter
    except Exception:
        p.exit(1, 'alert adapter startup failed: invalid configuration or unavailable storage/listener\n')
    print(json.dumps({'host': args.host, 'port': server.server_address[1]}), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close(); adapter.db.close()

if __name__ == '__main__': main()
