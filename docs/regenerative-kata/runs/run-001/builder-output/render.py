#!/usr/bin/env python3
"""Render fixed component observations as standalone HTML snapshots."""
import html
import json
import sys
from pathlib import Path


def escape(value):
    return html.escape(str(value), quote=True)


def render(component, observation):
    result = observation.get('result', {})
    healthy = result.get('kind') == 'success'
    state, color = ('healthy', 'green') if healthy else ('impaired', 'red')
    if healthy:
        message = 'Healthy — this component responded successfully.'
    elif result.get('http_status') == 502:
        message = 'Failure — this component returned HTTP 502 (Bad Gateway).'
    elif result.get('kind') == 'http_failure':
        message = 'Failure — this component returned an HTTP error.'
    else:
        message = 'Status uncertain — this observation does not establish a successful response.'
    timestamp = escape(observation['observed_at'])
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(component)} — observation</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f4f6f8; color: #17212b; font: 1rem/1.6 system-ui, sans-serif; }}
main {{ width: min(100%, 46rem); margin: auto; padding: clamp(1rem, 4vw, 2.5rem); }}
section {{ background: white; border: 1px solid #cbd2da; border-radius: .8rem; padding: clamp(1rem, 3vw, 1.6rem); margin: 1.2rem 0; }}
h1 {{ font-size: clamp(1.5rem, 5vw, 2rem); line-height: 1.25; }}
h2 {{ font-size: 1.2rem; }}
p, h1, h2, time, a {{ overflow-wrap: anywhere; }}
a {{ color: #0645ad; }}
.status {{ font-size: 1.15rem; font-weight: 650; }}
</style>
</head>
<body><main>
<p>Synthetic experiment · fixed observations</p>
<h1>{escape(component)}</h1>
<section aria-label="Component observation">
<div class="status" data-component-id="{escape(observation['component_id'])}" data-state="{state}" style="color: {color}">{escape(message)}</div>
<p>Observed at <time datetime="{timestamp}">{timestamp}</time></p>
<p>This is a recorded observation, not a live freshness guarantee. It describes only the listed component; it does not establish whether every wash operation is healthy or down.</p>
</section>
<section aria-labelledby="help-title">
<h2 id="help-title">Help with a wash problem</h2>
<p>A component observation cannot diagnose every wash problem. Help remains available here regardless of the displayed status.</p>
<p><a href="#illustrative-help">Illustrative help destination — demonstration only</a></p>
<div id="illustrative-help"><p>This example help destination does not contact a support team or promise a response. In a real service, consult its verified support information.</p></div>
</section>
<p>The component name, dates, and spacing are synthetic fixture values, not a real incident or a monitoring policy.</p>
</main></body></html>'''


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python3 render.py INPUT.json OUTPUT_DIRECTORY')
    data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    components = {component['id']: component['name'] for component in data['components']}
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    for index, observation in enumerate(data['observations']):
        name = components[observation['component_id']]
        (output / f'step-{index:03d}.html').write_text(render(name, observation), encoding='utf-8')


if __name__ == '__main__':
    main()
