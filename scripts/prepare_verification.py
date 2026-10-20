import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.artifacts'
OUTPUT.mkdir(exist_ok=True)
FOUR = {'ACHT_Frost.png', 'ACHT_Laser.png', 'ACHT_Man01.png', 'ACHT_Manager01.png',
        'ACHT_Nurse01.png', 'ACHT_Venom.png', 'ACHT_Yelena.png'}
jobs = []
for path in sorted((ROOT / 'Origen').glob('*.png')):
    columns, rows = (4, 4) if path.name in FOUR else (5, 5)
    if path.name == 'ACHT_Jill.png':
        columns, rows = 4, 3
    if path.name == 'ACHT_FaMalehero01.png':
        columns, rows = 6, 5
    jobs.append({'file': path.name, 'options': {'columns': columns, 'rows': rows}})
manifest = {'input_folder': str(ROOT / 'Origen'), 'gui_selected': 'ACHT_Frost.png',
            'gui_grid': [4, 4], 'screenshot': str(OUTPUT / 'interface.png'),
            'gui_uniform_selected': 'ACHT_Avia.png', 'gui_uniform_grid': [5, 5],
            'expected_sizes': {'ACHT_Frost.png': [1412, 1412], 'ACHT_Yelena.png': [1564, 1564],
                               'ACHT_Jill.png': [1412, 1059]},
            'cases': [{'name': 'strict', 'jobs': jobs, 'expected': {'success': 8, 'skipped': 23, 'failed': 0}},
                      {'name': 'resampled', 'jobs': [dict(item, options=dict(item['options'], resample=True)) for item in jobs],
                       'expected': {'success': 31, 'skipped': 0, 'failed': 0}},
                      {'name': 'uniform', 'jobs': [dict(item, options=dict(item['options'], resample=True, uniform_size=True)) for item in jobs],
                       'expected': {'success': 31, 'skipped': 0, 'failed': 0}}]}
path = OUTPUT / 'verification_manifest.json'
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(path)
