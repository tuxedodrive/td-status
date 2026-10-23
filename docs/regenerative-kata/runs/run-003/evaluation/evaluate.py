"""Independent functional replacement checks; controls synthetic HTTP dependencies."""
import json
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

root = Path(__file__).resolve().parents[1]
app = root / 'builder-output/status.py'
work = root / 'evaluation/work'
work.mkdir(parents=True, exist_ok=False)
responses = {}
class Dependency(BaseHTTPRequestHandler):
    def do_GET(self):
        code, body, delay = responses.get(self.path, (404, 'not found', 0))
        time.sleep(delay)
        self.send_response(code)
        self.end_headers()
        try:
            self.wfile.write(body.encode())
        except (BrokenPipeError, ConnectionResetError):
            pass
    def log_message(self, *args):
        pass
server = ThreadingHTTPServer(('127.0.0.1', 0), Dependency)
threading.Thread(target=server.serve_forever, daemon=True).start()
port = server.server_port
names = ['Application', 'Edge', 'Payments', 'Email', 'SMS', 'Authentication', 'Weather', 'Pollen', 'Hosting', 'Secrets']
services = []
for i, name in enumerate(names):
    code = 200 if i < 2 or i in (5, 8) else 401
    responses['/' + str(i)] = (code, 'healthy status SENTINEL_PRIVATE_BODY', 0)
    services.append({'id': 'gd-' + name.lower(), 'name': 'Groundhog Day ' + name,
                     'url': f'http://127.0.0.1:{port}/{i}',
                     'kind': 'first_party' if i < 2 else 'provider_reachability',
                     'impact': 'Core platform health endpoint' if i < 2 else 'This dependency only; other wash operations may be unaffected',
                     'expected_codes': [code], 'keywords': ['healthy'] if i < 2 else [],
                     'timeout_seconds': 0.2, 'stale_after_seconds': 60})
config = {'title': 'Groundhog Day synthetic status', 'support_url': 'https://support.example.invalid/help', 'services': services}
config_path = work / 'config.json'
config_path.write_text(json.dumps(config))
db = work / 'observations.sqlite'
public = work / 'public'
t0 = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=140)
commands, checks = [], []
def iso(seconds):
    return (t0 + timedelta(seconds=seconds)).isoformat().replace('+00:00', 'Z')
def run(command, seconds=0, extra=None, expected_exit=0, config_override=None, db_override=None, output_override=None):
    args = [sys.executable, str(app), command, '--config', str(config_override or config_path), '--db', str(db_override or db), '--output', str(output_override or public)]
    if seconds is not None:
        args += ['--now', iso(seconds)]
    args += extra or []
    result = subprocess.run(args, capture_output=True, text=True, timeout=20)
    commands.append({'command': args, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert (result.returncode == 0) if expected_exit == 0 else (result.returncode != 0), (args, result.stderr)
    if expected_exit:
        return None
    return json.loads((output_override or public).joinpath('status.json').read_text())
def states(data):
    return {s['id']: s['state'] for s in data['services']}
def check(name, condition):
    assert condition, name
    checks.append({'check': name, 'outcome': 'pass'})
def snapshot(name):
    import shutil
    shutil.copytree(public, work / name)
try:
    absent = run('export', db_override=work/'empty.sqlite', output_override=work/'absent')
    check('Registered services without observations are unknown', set(states(absent).values()) == {'unknown'} and len(absent['services']) == 10)
    healthy = run('collect')
    check('All ten explicit checks healthy, including expected 401 provider reachability', len(healthy['services']) == 10 and set(states(healthy).values()) == {'healthy'})
    snapshot('healthy')
    responses['/0'] = (502, 'SENTINEL_PRIVATE_BODY internal details', 0)
    failed = run('collect', 15)
    check('Received 502 marks only affected component impaired', states(failed)['gd-application'] == 'impaired' and sum(s == 'impaired' for s in states(failed).values()) == 1)
    service = next(s for s in failed['services'] if s['id'] == 'gd-application')
    check('Failure has code, description and observation timestamp', service['http_status'] == 502 and service['description'] and service['observed_at'] == iso(15))
    snapshot('failed')
    repeated = run('collect', 20)
    check('Repeated failure retains one open incident', len([i for i in repeated['incidents'] if i['service_id'] == 'gd-application' and not i['resolved_at']]) == 1)
    responses['/0'] = (200, 'healthy status SENTINEL_PRIVATE_BODY', 0)
    responses['/7'] = (502, 'SENTINEL_PRIVATE_BODY', 0)
    minor = run('collect', 30)
    check('Fresh success recovers core while minor dependency stays scoped', states(minor)['gd-application'] == 'healthy' and states(minor)['gd-pollen'] == 'impaired')
    check('Incident resolves on recovery evidence', any(i['service_id'] == 'gd-application' and i['resolved_at'] == iso(30) for i in minor['incidents']))
    snapshot('minor')
    responses['/7'] = (401, 'provider response', 0)
    recovered = run('collect', 40)
    check('Full recovery restores healthy', set(states(recovered).values()) == {'healthy'})
    check('History survives separate process restarts', all(len(s['history']) >= 5 for s in recovered['services']))
    check('Resolved incidents retained', len(recovered['incidents']) == 2 and all(i['resolved_at'] for i in recovered['incidents']))
    snapshot('recovered')
    stale = run('export', 101)
    check('Aged successful evidence is unknown, not current healthy', set(states(stale).values()) == {'unknown'} and all(s['observed_at'] == iso(40) for s in stale['services']))
    snapshot('stale')
    responses['/1'] = (200, 'wrong keyword SENTINEL_PRIVATE_BODY', 0)
    keyword = run('collect', 110)
    check('Expected code with missing keyword is impaired', states(keyword)['gd-edge'] == 'impaired')
    responses['/1'] = (200, 'healthy', 0.5)
    timeout = run('collect', 120)
    check('Probe timeout is impaired without crashing cycle', states(timeout)['gd-edge'] == 'impaired')
    check('Provider meaning and scope remain explicit', all(s['kind'] == 'provider_reachability' and s['impact'] for s in timeout['services'][2:]))
    data = (public/'status.json').read_text() + (public/'index.html').read_text()
    check('Public files omit private URL/body/traceback', 'SENTINEL_PRIVATE_BODY' not in data and f'127.0.0.1:{port}' not in data and 'Traceback' not in data)
    before_count = len(next(s for s in timeout['services'] if s['id']=='gd-edge')['history'])
    responses['/1'] = (200, 'healthy', 0)
    loop = run('run', None, ['--interval', '0.05', '--iterations', '2'])
    check('Bounded monitor loop collects and persists two cycles', len(next(s for s in loop['services'] if s['id']=='gd-edge')['history']) == before_count+2)
    bad = dict(config, services=services+[services[0]])
    bad_path = work/'bad-config.json'; bad_path.write_text(json.dumps(bad))
    run('collect', 130, expected_exit=1, config_override=bad_path)
    check('Duplicate registry rejected', True)
    removed = dict(config, services=services[1:]); removed_path=work/'removed.json'; removed_path.write_text(json.dumps(removed))
    removed_data=run('export', 140, config_override=removed_path)
    check('Removed service absent from public registry and incidents', 'gd-application' not in states(removed_data) and all(i['service_id']!='gd-application' for i in removed_data['incidents']))
    server.shutdown(); server.server_close()
    offline=run('collect', None)
    check('Stopped dependencies cannot masquerade as healthy', set(states(offline).values()) == {'impaired'})
    check('Published site still exists while all dependencies offline', (public/'index.html').is_file() and (public/'index.html').stat().st_size>1000)
    snapshot('offline')
finally:
    (root/'evidence/functional-commands.json').write_text(json.dumps(commands, indent=2)+'\n')
    (root/'evidence/functional-results.json').write_text(json.dumps({'checks':checks,'passed':len(checks)}, indent=2)+'\n')
print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
