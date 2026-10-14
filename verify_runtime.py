"""Development-only verification entry, also executable in the frozen EXE."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path
import tkinter as tk
import PIL
import numpy

from PIL import Image, ImageGrab

from atlas_batch import Job, export_batch
from atlas_processor import Options


def _wait(root, condition, seconds=30):
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError('GUI worker did not finish')
        root.update()
        time.sleep(.01)
    root.update()


def verify_runtime(report_path: Path, manifest_path=None):
    from atlas_trim import AtlasTrimApp
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8')) if manifest_path else {}
    report = {'status': 'running', 'frozen': bool(getattr(sys, 'frozen', False)), 'python': sys.version}
    report['module_paths'] = {'pillow': PIL.__file__, 'numpy': numpy.__file__, 'tkinter': tk.__file__}
    if report['frozen']:
        bundle = Path(sys._MEIPASS)
        assert all(Path(path).is_relative_to(bundle) for path in report['module_paths'].values())
    root = None
    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    try:
        with tempfile.TemporaryDirectory() as temporary:
            fallback_source = Path(temporary) / 'input'
            fallback_source.mkdir()
            image = Image.new('RGBA', (10, 10))
            image.putpixel((5, 5), (200, 100, 30, 255))
            image.save(fallback_source / 'test.png')
            source = Path(manifest.get('input_folder', fallback_source))
            paths = sorted(source.rglob('*.png'))
            hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
            root = tk.Tk()
            root.withdraw()
            app = AtlasTrimApp(root, autodetect=False)
            app.input_path.set(str(source))
            app.output_path.set(str(report_path.parent / 'gui_output'))
            app.scan()
            _wait(root, lambda: bool(app.entries) and not app.busy)
            name = manifest.get('gui_selected', 'test.png')
            key = next(str(index) for index, entry in enumerate(app.entries) if entry.path.name == name)
            app.tree.selection_set(key)
            app.tree.focus(key)
            app.tree.see(key)
            root.update()
            columns, rows = manifest.get('gui_grid', [1, 1])
            app.columns.set(str(columns))
            app.rows.set(str(rows))
            app.apply_grid()
            _wait(root, lambda: app.result is not None and app.result.plan.columns == columns)
            app.step(1)
            app.export(selected=True)
            _wait(root, lambda: app.last_report is not None and not app.busy)
            assert app.last_report['counts'] == {'success': 1, 'skipped': 0, 'failed': 0}
            report['gui'] = {'tk': root.tk.call('info', 'patchlevel'), 'files_scanned': len(app.entries),
                             'preview_size': list(app.result.atlas.size), 'export': app.last_report['counts'],
                             'status_text': app.status.get()}
            if manifest.get('screenshot'):
                app.playing = False
                root.deiconify()
                root.update()
                time.sleep(.3)
                root.update()
                box = (root.winfo_rootx(), root.winfo_rooty(),
                       root.winfo_rootx() + root.winfo_width(), root.winfo_rooty() + root.winfo_height())
                ImageGrab.grab(bbox=box).save(manifest['screenshot'])
            root.deiconify()
            root.geometry('1050x700')
            root.update()
            hint = app.mode_hint
            hint_bottom = hint.winfo_rooty() + hint.winfo_height()
            assert hint.winfo_height() >= hint.winfo_reqheight(), 'Mode instructions are clipped'
            assert hint_bottom <= hint.master.winfo_rooty() + hint.master.winfo_height()
            assert app.progress.winfo_rooty() + app.progress.winfo_height() <= root.winfo_rooty() + root.winfo_height()
            report['gui']['minimum_window_layout'] = 'passed'
            if manifest.get('screenshot'):
                time.sleep(.2)
                root.update()
                box = (root.winfo_rootx(), root.winfo_rooty(),
                       root.winfo_rootx() + root.winfo_width(), root.winfo_rooty() + root.winfo_height())
                ImageGrab.grab(bbox=box).save(str(Path(manifest['screenshot']).with_name('interface_minimum.png')))
            root.withdraw()
            app.close()
            root = None
            save()
            for case in manifest.get('cases', []):
                jobs = [Job(source / item['file'], Options(**item['options'])) for item in case['jobs']]
                started = time.monotonic()
                exported = export_batch(jobs, source, report_path.parent / case['name'])
                assert exported['counts'] == case['expected'], exported['counts']
                for item in exported['results']:
                    expected_size = manifest.get('expected_sizes', {}).get(Path(item['input']).name)
                    if item['status'] == 'success':
                        with Image.open(item['output']) as result:
                            assert result.mode == 'RGBA'
                            assert list(result.size) == item['output_size']
                            columns, rows = item['options']['columns'], item['options']['rows']
                            assert result.width // columns == result.height // rows
                            if case['name'] == 'strict' and expected_size:
                                assert list(result.size) == expected_size, result.size
                report[case['name']] = {'counts': exported['counts'], 'seconds': round(time.monotonic() - started, 2),
                                        'report': exported['report_path']}
                save()
            assert hashes == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
            report['source_hashes_unchanged'] = True
            report['status'] = 'passed'
            save()
    except Exception:
        report['status'] = 'failed'
        report['error'] = traceback.format_exc()
        save()
        if root is not None:
            root.destroy()
        raise
