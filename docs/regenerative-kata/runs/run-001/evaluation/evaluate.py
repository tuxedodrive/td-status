"""Independent snapshot checks; no import of builder implementation."""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.text = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.nodes.append((tag, attrs))
        if tag in ('style', 'script'):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('style', 'script'):
            self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)

oracle = json.loads(Path(__file__).with_name('oracle.json').read_text())
results = []
for expected in oracle['expected']:
    page = Page()
    page.feed((Path(sys.argv[1]) / expected['file']).read_text())
    visible = ' '.join(page.text)
    statuses = [attrs for _, attrs in page.nodes if attrs.get('data-component-id') == 'groundhog-day-wash']
    assert len(statuses) == 1, expected['file'] + ': one status container required'
    status = statuses[0]
    assert status.get('data-state') == expected['state'], expected['file'] + ': state'
    assert re.search(r'(?:^|;)\s*color\s*:\s*' + expected['color'] + r'\s*(?:;|$)', status.get('style', ''), re.I), expected['file'] + ': color'
    assert 'Groundhog Day Wash' in visible, expected['file'] + ': component name'
    assert expected['timestamp'] in visible, expected['file'] + ': visible observation time'
    assert any(tag == 'time' and attrs.get('datetime') == expected['timestamp'] for tag, attrs in page.nodes), expected['file'] + ': semantic observation time'
    assert re.search(r'help|support', visible, re.I), expected['file'] + ': help'
    assert re.search(r'synthetic|experiment|illustrative', visible, re.I), expected['file'] + ': experiment label'
    if expected['state'] == 'impaired':
        assert re.search(r'unreachable|bad gateway|failed|failure|unavailable|error', visible, re.I), 'failure description'
    else:
        assert re.search(r'healthy|operational|success', visible, re.I), 'healthy description'
    results.append({'snapshot': expected['file'], 'outcome': 'pass', 'expected_state': expected['state']})
print(json.dumps({'scope': 'Static HTML semantics and explicit inline status color; not browser rendering', 'results': results}, indent=2))
