import sys
import tempfile
import unittest
import os
import subprocess
import threading
from unittest.mock import patch
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas_batch import Job, export_batch, scan_folder, validate_output
from atlas_processor import Options


class BatchTests(unittest.TestCase):
    def test_summary_write_failure_does_not_hide_completed_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'input'
            source.mkdir()
            image = Image.new('RGBA', (8, 8), (20, 40, 80, 255))
            image.save(source / 'one.png')
            real_open = Path.open
            def filesystem_failure(path, *args, **kwargs):
                if path.suffix in ('.csv', '.json'):
                    raise OSError('simulated full disk')
                return real_open(path, *args, **kwargs)
            with patch.object(Path, 'open', filesystem_failure):
                report = export_batch([Job(source / 'one.png', Options(columns=1, rows=1))], source, root / 'out')
            self.assertEqual(report['counts']['success'], 1)
            self.assertEqual(len(report['report_errors']), 2)
            self.assertTrue((root / 'out' / 'one.png').exists())

    def test_nested_output_link_cannot_write_back_into_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / 'input', root / 'output'
            (source / 'child').mkdir(parents=True)
            output.mkdir()
            path = source / 'child' / 'one.png'
            Image.new('RGBA', (8, 8), (20, 40, 80, 255)).save(path)
            link = output / 'child'
            if os.name == 'nt':
                subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(link), str(source / 'child')],
                               check=True, capture_output=True)
            else:
                link.symlink_to(source / 'child', target_is_directory=True)
            try:
                report = export_batch([Job(path, Options(columns=1, rows=1))], source, output)
                self.assertEqual(report['counts'], {'success': 0, 'skipped': 1, 'failed': 0})
                self.assertEqual([p.name for p in (source / 'child').iterdir()], ['one.png'])
            finally:
                if os.name == 'nt':
                    os.rmdir(link)
                else:
                    link.unlink()

    def test_stop_finishes_current_image_and_keeps_a_partial_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'input'
            source.mkdir()
            paths = [source / f'{i}.png' for i in range(2)]
            for path in paths:
                Image.new('RGBA', (8, 8), (20, 40, 80, 255)).save(path)
            cancel = threading.Event()
            report = export_batch([Job(path, Options(columns=1, rows=1)) for path in paths], source, root / 'out',
                                  lambda index, record: cancel.set(), cancel)
            self.assertTrue(report['cancelled'])
            self.assertEqual(report['counts']['success'], 1)
            self.assertTrue(Path(report['report_path']).exists())

    def test_output_inside_input_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            with self.assertRaises(ValueError):
                validate_output(source, source / 'output')
            self.assertFalse((source / 'output').exists())

    def test_recursive_output_collision_and_failure_isolation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs, outputs = root / 'input', root / 'output'
            (inputs / '子目录').mkdir(parents=True)
            (outputs / '子目录').mkdir(parents=True)
            good = inputs / '子目录' / '动画.png'
            image = Image.new('RGBA', (8, 8))
            image.putpixel((4, 4), (45, 78, 120, 200))
            image.save(good)
            (inputs / '坏文件.png').write_bytes(b'not a png')
            existing = outputs / '子目录' / '动画.png'
            existing.write_bytes(b'must be preserved')
            entries = scan_folder(inputs, recursive=True)
            jobs = [Job(entry.path, Options(columns=1, rows=1)) for entry in entries]
            report = export_batch(jobs, inputs, outputs)
            self.assertEqual(report['counts'], {'success': 1, 'skipped': 0, 'failed': 1})
            self.assertEqual(existing.read_bytes(), b'must be preserved')
            self.assertTrue((outputs / '子目录' / '动画_1.png').exists())
            self.assertTrue(Path(report['report_path']).exists())


if __name__ == '__main__':
    unittest.main()
