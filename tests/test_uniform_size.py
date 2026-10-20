import math
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas_batch import Job, export_batch
from atlas_processor import Options, ProcessingSkipped, process_atlas


class UniformSizeTests(unittest.TestCase):
    def test_disabled_mode_preserves_pixels_and_ignores_unused_dimensions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.png'
            image = Image.new('RGBA', (20, 10), (230, 10, 180, 0))
            image.putpixel((3, 2), (40, 100, 160, 128))
            image.putpixel((14, 4), (220, 20, 70, 255))
            image.save(path)
            options = Options(columns=2, rows=1)
            original = process_atlas(path, options)
            disabled = process_atlas(path, replace(options, target_width=0, target_height=-1))
            self.assertEqual(original.atlas.size, disabled.atlas.size)
            self.assertEqual(original.atlas.tobytes(), disabled.atlas.tobytes())
            self.assertEqual(disabled.output_scale, (1, 1))

    def test_requested_downscale_and_upscale_examples_have_no_canvas_padding(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'example.png'
            for size in ((2048, 1024), (512, 256)):
                with self.subTest(source=size):
                    Image.new('RGBA', size, (25, 90, 170, 255)).save(path)
                    result = process_atlas(path, Options(columns=8, rows=4, padding=0, uniform_size=True))
                    self.assertEqual(result.atlas.size, (1024, 512))
                    self.assertEqual(result.atlas.getchannel('A').getextrema(), (255, 255))
                    self.assertEqual(result.atlas.getpixel((1023, 511)), (25, 90, 170, 255))

    def test_five_by_five_resizes_complete_atlas_to_exact_size_in_both_modes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'five.png'
            image = Image.new('RGBA', (50, 50))
            for y in range(50):
                for x in range(50):
                    image.putpixel((x, y), ((x * 17) % 256, (y * 31) % 256,
                                           (x + y) % 256, 80 + (x * 3 + y) % 176))
            image.save(path)
            for mode, filter_value in (('smooth', Image.Resampling.LANCZOS), ('nearest', Image.Resampling.NEAREST)):
                with self.subTest(mode=mode):
                    result = process_atlas(path, Options(padding=0, uniform_size=True, resize_filter=mode))
                    self.assertEqual(result.atlas.size, (1024, 1024))
                    self.assertEqual(result.atlas.tobytes(), image.resize((1024, 1024), filter_value).tobytes())
                    self.assertEqual(result.output_frame_size, (204.8, 204.8))
                    self.assertEqual(len(result.frames), 25)
                    for index, frame in enumerate(result.frames):
                        column, row = index % 5, index // 5
                        left, top = column * 1024 // 5, row * 1024 // 5
                        right, bottom = math.ceil((column + 1) * 1024 / 5), math.ceil((row + 1) * 1024 / 5)
                        self.assertEqual(frame.tobytes(), result.atlas.crop((left, top, right, bottom)).tobytes())
                        offset_x, offset_y = result.frame_offsets[index]
                        self.assertAlmostEqual(left - offset_x, column * 204.8)
                        self.assertAlmostEqual(top - offset_y, row * 204.8)

    def test_non_square_targets_and_non_integral_other_dimension(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'wide.png'
            for columns, rows, target, expected in (
                (8, 4, (1000, 512), (1000, 500)),
                (8, 4, (1024, 300), (600, 300)),
                (4, 3, (1024, 500), (667, 500)),
                (6, 5, (1024, 1024), (1024, 853)),
                (8, 4, (1, 1), (1, 1)),
            ):
                with self.subTest(grid=(columns, rows), target=target):
                    Image.new('RGBA', (columns * 4, rows * 4), (50, 60, 70, 255)).save(path)
                    result = process_atlas(path, Options(columns=columns, rows=rows, padding=0,
                                           uniform_size=True, target_width=target[0], target_height=target[1]))
                    self.assertEqual(result.atlas.size, expected)
                    self.assertLessEqual(result.atlas.width, target[0])
                    self.assertLessEqual(result.atlas.height, target[1])

    def test_nearest_scale_preserves_common_motion_and_empty_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'motion.png'
            source = Image.new('RGBA', (30, 8))
            source.putpixel((2, 2), (120, 30, 70, 255))
            source.putpixel((14, 3), (120, 30, 70, 255))
            source.save(path)
            result = process_atlas(path, Options(columns=3, rows=1, padding=0, uniform_size=True,
                                   target_width=18, target_height=18, resize_filter='nearest'))
            self.assertEqual(result.atlas.size, (18, 6))
            self.assertEqual(result.frames[0].getchannel('A').getbbox(), (0, 0, 2, 2))
            self.assertEqual(result.frames[1].getchannel('A').getbbox(), (4, 2, 6, 4))
            self.assertIsNone(result.frames[2].getchannel('A').getbbox())

    def test_smooth_scale_ignores_hidden_rgb_and_keeps_transparent_edges_bright(self):
        with tempfile.TemporaryDirectory() as folder:
            results = []
            for index, hidden in enumerate(((0, 0, 0, 0), (255, 0, 255, 0))):
                path = Path(folder) / f'{index}.png'
                source = Image.new('RGBA', (9, 9), hidden)
                source.putpixel((4, 4), (255, 255, 255, 255))
                source.save(path)
                result = process_atlas(path, Options(columns=1, rows=1, padding=2,
                                       uniform_size=True, target_width=31, target_height=31))
                results.append(result.atlas)
            self.assertEqual(results[0].tobytes(), results[1].tobytes())
            self.assertTrue(all(pixel[:3] == (255, 255, 255) for pixel in results[0].get_flattened_data() if pixel[3]))

    def test_noop_size_keeps_source_pixels_including_hidden_rgb(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'noop.png'
            source = Image.new('RGBA', (5, 5), (255, 0, 255, 0))
            source.putpixel((2, 2), (100, 70, 30, 150))
            source.save(path)
            result = process_atlas(path, Options(columns=1, rows=1, padding=2, uniform_size=True,
                                   target_width=5, target_height=5))
            self.assertEqual(result.atlas.tobytes(), source.tobytes())

    def test_invalid_and_excessive_output_sizes_are_rejected_before_resize(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'small.png'
            Image.new('RGBA', (4, 4), (255, 255, 255, 255)).save(path)
            for width, height, code in ((0, 1024, 'target_size'), (1024, -1, 'target_size'),
                                        (100000, 100000, 'size')):
                with self.subTest(target=(width, height)):
                    with self.assertRaises(ProcessingSkipped) as error:
                        process_atlas(path, Options(columns=1, rows=1, uniform_size=True,
                                      target_width=width, target_height=height))
                    self.assertEqual(error.exception.code, code)

    def test_uniform_size_does_not_bypass_strict_source_grid_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fractional.png'
            Image.new('RGBA', (51, 51), (50, 60, 70, 255)).save(path)
            with self.assertRaises(ProcessingSkipped) as error:
                process_atlas(path, Options(uniform_size=True))
            self.assertEqual(error.exception.code, 'non_integral')
            result = process_atlas(path, Options(uniform_size=True, resample=True))
            self.assertEqual(result.atlas.size, (1024, 1024))

    def test_batch_report_matches_real_output_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input'
            source.mkdir()
            path = source / 'five.png'
            Image.new('RGBA', (50, 50), (30, 60, 90, 255)).save(path)
            original = path.read_bytes()
            report = export_batch([Job(path, Options(padding=0, uniform_size=True))], source, Path(folder) / 'output')
            self.assertEqual(report['counts'], {'success': 1, 'skipped': 0, 'failed': 0})
            record = report['results'][0]
            self.assertEqual(record['output_size'], [1024, 1024])
            self.assertEqual(record['output_frame_size'], [204.8, 204.8])
            self.assertEqual(record['crop']['side'], 10)
            self.assertEqual(record['output_scale'], [20.48, 20.48])
            with Image.open(record['output']) as output:
                self.assertEqual(output.size, (1024, 1024))
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
