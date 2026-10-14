import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas_batch import Job, export_batch, scan_folder, validate_output
from atlas_processor import Options


class BatchTests(unittest.TestCase):
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
