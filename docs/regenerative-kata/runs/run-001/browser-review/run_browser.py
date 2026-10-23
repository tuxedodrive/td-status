"""Render local review copies with an existing Chrome headless binary; no installs."""
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
results = []
for label, width, height in [('phone', 390, 844), ('square', 720, 720), ('tablet', 820, 1180)]:
    for index in range(3):
        name = f'{label}-step-{index:03d}'
        command = [sys.argv[1], '--headless', '--user-data-dir=/tmp/priory-kata-browser-run001',
                   '--disable-background-networking', '--disable-component-update', '--no-first-run',
                   f'--window-size={width},{height}',
                   f'--screenshot={root / "screenshots" / (name + ".png")}',
                   '--dump-dom', (root / 'pages' / f'step-{index:03d}.html').as_uri()]
        run = subprocess.run(command, capture_output=True, text=True, check=True)
        (root / (name + '.dom.html')).write_text(run.stdout)
        match = re.search(r'<script id="browser-review-result" type="application/json">(.*?)</script>', run.stdout, re.S)
        assert match, name + ': review script did not execute'
        result = json.loads(match.group(1))
        result['case'] = name
        expected_color = 'rgb(255, 0, 0)' if index == 1 else 'rgb(0, 128, 0)'
        assert result['width'] == width and result['height'] == height, name + ': viewport'
        assert result['noHorizontalOverflow'], name + ': overflow'
        assert result['status']['color'] == expected_color, name + ': computed status color'
        for field in ['status', 'help']:
            box = result[field]
            assert box['width'] > 0 and box['height'] > 0 and box['display'] != 'none' and box['visibility'] == 'visible', name + ': visible text'
            assert float(box['fontSize'].removesuffix('px')) >= 16, name + ': readable base size'
        assert 'Help' in result['help']['text'], name + ': help text'
        assert ('502' in result['status']['text']) if index == 1 else ('Healthy' in result['status']['text']), name + ': status text'
        result['outcome'] = 'pass'
        results.append(result)
version = subprocess.run([sys.argv[1], '--version'], capture_output=True, text=True, check=True).stdout.strip()
(root / 'results.json').write_text(json.dumps({'browser': version, 'route': 'Local file copies of Priory output with evaluation-only DOM probe; no app changes', 'results': results}, indent=2) + '\n')
print(json.dumps({'browser': version, 'cases': len(results), 'passed': len(results)}, indent=2))
