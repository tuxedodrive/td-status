"""Per-obligation contract coverage for run 007 (Python stdlib only).

Reads obligations from builder-input/contracts/status/service.intent.md,
reads `# proves[...]: <ids>` tags from the evaluator sources, and reads this
run's evaluation results. A check passes only when this run's results record
it passing. Reports, per obligation, tagged checks and passing checks, and
lists every active obligation with no passing check. Exits 1 when any active
obligation is uncovered or a tag names an unknown obligation.

Check units:
- evaluate.py / alerts.py / resilience.py: each check('<name>', ...) line;
  passes when its name is in that stage's results `checks` with outcome pass.
- operations.py: each tagged result key; passes when the key is true.
- browser.py / browser_live.py / browser_hung.py: each tagged assertion; the
  script aborts on the first failed assertion and writes results only on
  success, so a unit passes when the stage's results show every expected case
  passing (21, 6 and passed=true respectively).
"""
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
intent = root / 'builder-input/contracts/status/service.intent.md'
ev = root / 'evaluation'

obligations = {}
for block in re.split(r'^### ', intent.read_text(), flags=re.M)[1:]:
    m = re.match(r'(status\.service\.I\d+) — (.*)', block)
    if not m:
        continue
    status = re.search(r'\*\*status:\*\* (\w+)', block).group(1)
    obligations[m.group(1)] = {'title': m.group(2).strip(), 'status': status, 'tagged': [], 'passing': []}


def load(path):
    p = root / path
    return json.loads(p.read_text()) if p.exists() else None


def named_checks(path):
    data = load(path)
    return {c['check'] for c in (data or {}).get('checks', []) if c.get('outcome') == 'pass'}


def all_cases(path, count):
    data = load(path)
    results = (data or {}).get('results', [])
    return len(results) == count and all(r.get('outcome') == 'pass' for r in results)


hung = load('evidence/browser-hung-result.json')
operations = load('evidence/operations-results.json') or {}
stage_pass = {
    'evaluate.py': named_checks('evidence/functional-results.json'),
    'alerts.py': named_checks('evidence/alert-results.json'),
    'resilience.py': named_checks('evidence/resilience-results.json'),
    'browser.py': all_cases('browser-review/results.json', 21),
    'browser_live.py': all_cases('browser-live/results.json', 6),
    'browser_hung.py': bool(hung and hung.get('passed') is True),
}

unknown_tags, units = [], []
tag_re = re.compile(r'#\s*proves(?:\[([^\]]+)\])?:\s*(.+)$')
for f in ['evaluate.py', 'alerts.py', 'resilience.py', 'operations.py', 'browser.py', 'browser_live.py', 'browser_hung.py']:
    for n, line in enumerate((ev / f).read_text().splitlines(), 1):
        m = tag_re.search(line)
        if not m:
            continue
        ids = m.group(2).split()
        unit = m.group(1)
        if unit is None:
            unit = re.search(r"check\((['\"])(.*?)\1", line).group(2)
        if f in ('evaluate.py', 'alerts.py', 'resilience.py'):
            passed = unit in stage_pass[f]
        elif f == 'operations.py':
            passed = operations.get(unit) is True
        else:
            passed = stage_pass[f]
        label = f'{f}:{n} {unit}'
        units.append({'check': label, 'obligations': ids, 'passed': passed})
        for i in ids:
            if i not in obligations:
                unknown_tags.append((label, i))
                continue
            obligations[i]['tagged'].append(label)
            if passed:
                obligations[i]['passing'].append(label)

active = {k: v for k, v in obligations.items() if v['status'] == 'active'}
retired_tagged = [k for k, v in obligations.items() if v['status'] != 'active' and v['tagged']]
untested = [k for k, v in active.items() if not v['tagged']]
tagged_not_passing = [k for k, v in active.items() if v['tagged'] and not v['passing']]
covered = [k for k, v in active.items() if v['passing']]
key = lambda k: int(k.rsplit('I', 1)[1])
report = {
    'obligations_total': len(obligations),
    'active': len(active),
    'retired': len(obligations) - len(active),
    'active_with_passing_check': len(covered),
    'active_tagged_but_no_passing_check': sorted(tagged_not_passing, key=key),
    'active_with_no_tagged_check': sorted(untested, key=key),
    'retired_obligations_with_tags': retired_tagged,
    'unknown_tags': unknown_tags,
    'check_units': len(units),
    'check_units_passing': sum(u['passed'] for u in units),
    'per_obligation': {k: obligations[k] for k in sorted(obligations, key=key)},
    'units': units,
}
(root / 'evidence/coverage.json').write_text(json.dumps(report, indent=2) + '\n')

lines = [f"obligations {len(obligations)} (active {len(active)}, retired {len(obligations) - len(active)}); "
         f"check units {report['check_units']} passing {report['check_units_passing']}; "
         f"active with a passing check {len(covered)}/{len(active)}", '',
         f"{'obligation':<22} {'status':<8} {'tagged':>6} {'passing':>7}  title"]
for k in sorted(obligations, key=key):
    o = obligations[k]
    flag = '' if o['status'] != 'active' or o['passing'] else '  <-- NO PASSING CHECK'
    lines.append(f"{k:<22} {o['status']:<8} {len(o['tagged']):>6} {len(o['passing']):>7}  {o['title']}{flag}")
lines += ['', 'active obligations with no tagged check: ' + (', '.join(report['active_with_no_tagged_check']) or 'none'),
          'active obligations tagged but not passing: ' + (', '.join(report['active_tagged_but_no_passing_check']) or 'none'),
          'unknown tags: ' + (', '.join(f'{a} -> {b}' for a, b in unknown_tags) or 'none')]
text = '\n'.join(lines) + '\n'
(root / 'evidence/coverage.txt').write_text(text)
print(text)
sys.exit(1 if (untested or tagged_not_passing or unknown_tags) else 0)
