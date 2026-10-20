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
    from atlas_trim import AtlasTrimApp, PIXEL, RESAMPLE, SMOOTH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig')) if manifest_path else {}
    report = {'status': 'running', 'frozen': bool(getattr(sys, 'frozen', False)), 'python': sys.version}
    report['module_paths'] = {'pillow': PIL.__file__, 'numpy': numpy.__file__, 'tkinter': tk.__file__}
    if report['frozen']:
        bundle = Path(getattr(sys, '_MEIPASS'))
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
            completed, result = app.last_report, app.result
            assert completed is not None and result is not None
            assert completed['counts'] == {'success': 1, 'skipped': 0, 'failed': 0}
            report['gui'] = {'tk': root.tk.call('info', 'patchlevel'), 'files_scanned': len(app.entries),
                             'preview_size': list(result.atlas.size), 'export': completed['counts'],
                             'status_text': app.status.get()}
            assert str(app.width_spin.cget('state')) == 'disabled'
            assert str(app.resize_combo.cget('state')) == 'disabled'
            app.target_width.set('')
            app.target_height.set('')
            assert not app._options(key).uniform_size, 'Disabled dimensions must be ignored'

            uniform_name = manifest.get('gui_uniform_selected', name)
            uniform_key = next(str(index) for index, entry in enumerate(app.entries) if entry.path.name == uniform_name)
            uniform_columns, uniform_rows = manifest.get('gui_uniform_grid', [columns, rows])
            app.tree.selection_set(uniform_key)
            app.tree.focus(uniform_key)
            app.tree.see(uniform_key)
            app.columns.set(str(uniform_columns))
            app.rows.set(str(uniform_rows))
            app.mode.set(RESAMPLE)
            app.apply_grid()
            app.target_width.set('1024')
            app.target_height.set('1024')
            app.uniform_size.set(True)
            _wait(root, lambda: app.result is not None and app.result.atlas.size == (1024, 1024))
            assert str(app.width_spin.cget('state')) == 'normal'
            assert str(app.resize_combo.cget('state')) == 'readonly'
            app.step(1)
            app.step(-1)
            app.last_report = None
            app.output_path.set(str(report_path.parent / 'gui_uniform_output'))
            app.export(selected=True)
            _wait(root, lambda: app.last_report is not None and not app.busy)
            completed, result = app.last_report, app.result
            assert completed is not None and result is not None
            assert completed['counts'] == {'success': 1, 'skipped': 0, 'failed': 0}
            with Image.open(completed['results'][0]['output']) as exported_image:
                assert exported_image.size == (1024, 1024)
                assert exported_image.tobytes() == result.atlas.tobytes(), 'Preview and output differ'
            report['uniform_gui'] = {'preview_size': list(result.atlas.size),
                                     'logical_frame_size': list(result.output_frame_size),
                                     'preview_export_pixels_equal': True, 'smooth_export': completed['counts']}

            app.target_height.set('512')
            app.resize_mode.set(PIXEL)
            _wait(root, lambda: app.result is not None and app.result.atlas.size == (512, 512))
            app.last_report = None
            app.export(selected=True)
            _wait(root, lambda: app.last_report is not None and not app.busy)
            completed, result = app.last_report, app.result
            assert completed is not None and result is not None
            assert completed['counts'] == {'success': 1, 'skipped': 0, 'failed': 0}
            assert completed['results'][0]['options']['resize_filter'] == 'nearest'
            with Image.open(completed['results'][0]['output']) as exported_image:
                assert exported_image.tobytes() == result.atlas.tobytes()
            report['uniform_gui']['pixel_export'] = {'size': list(result.atlas.size), 'pixels_equal': True}

            unscaled_size = (result.plan.side * uniform_columns, result.plan.side * uniform_rows)
            app.uniform_size.set(False)
            _wait(root, lambda: app.result is not None and app.result.atlas.size == unscaled_size)
            assert app.result is not None and app.result.output_scale == (1, 1)
            assert str(app.width_spin.cget('state')) == 'disabled'
            report['uniform_gui']['toggle_off_restores_unscaled'] = True
            app.target_height.set('1024')
            app.resize_mode.set(SMOOTH)
            app.uniform_size.set(True)
            _wait(root, lambda: app.result is not None and app.result.atlas.size == (1024, 1024))
            if manifest.get('screenshot'):
                app.playing = False
                root.deiconify()
                root.update()
                time.sleep(.3)
                root.update()
                ImageGrab.grab(window=int(root.wm_frame(), 0)).save(manifest['screenshot'])
            root.deiconify()
            root.geometry('1050x700')
            root.update()
            hint = app.mode_hint
            hint_bottom = hint.winfo_rooty() + hint.winfo_height()
            assert hint.winfo_height() >= hint.winfo_reqheight(), 'Mode instructions are clipped'
            assert hint_bottom <= hint.master.winfo_rooty() + hint.master.winfo_height()
            assert app.progress.winfo_rooty() + app.progress.winfo_height() <= root.winfo_rooty() + root.winfo_height()
            assert min(canvas.winfo_height() for canvas in app.canvases) >= 100, 'Animation preview is too small'
            assert app.tree.winfo_height() >= 100, 'File list has no usable rows'
            assert app.height_spin.winfo_rootx() + app.height_spin.winfo_width() <= app.height_spin.master.winfo_rootx() + app.height_spin.master.winfo_width(), 'Uniform size controls are clipped'
            app.toggle_log()
            root.update()
            assert app.log_area.winfo_ismapped()
            app.toggle_log()
            root.update()
            report['gui']['minimum_window_layout'] = 'passed'
            if manifest.get('screenshot'):
                time.sleep(.2)
                root.update()
                ImageGrab.grab(window=int(root.wm_frame(), 0)).save(str(Path(manifest['screenshot']).with_name('interface_minimum.png')))
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
                            if item['options'].get('uniform_size'):
                                expected = ([1024, 1024] if columns == rows else
                                            [1024, 768] if (columns, rows) == (4, 3) else [1024, 853])
                                assert list(result.size) == expected, result.size
                                assert item['output_frame_size'] == [result.width / columns, result.height / rows]
                            else:
                                assert result.width % columns == result.height % rows == 0
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
