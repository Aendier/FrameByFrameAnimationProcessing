import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas_processor import Options, ProcessingSkipped, process_atlas


class ProcessorTests(unittest.TestCase):
    def test_fractional_grid_keeps_last_frame_and_ignores_hidden_rgb(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for number, background in enumerate([(0, 0, 0, 0), (255, 50, 190, 0)]):
                image = Image.new('RGBA', (14, 7), background)
                image.putpixel((1, 3), (20, 160, 90, 255))
                image.putpixel((13, 3), (20, 160, 90, 255))
                path = Path(folder) / f'{number}.png'
                image.save(path)
                paths.append(path)
            options = Options(columns=3, rows=1, padding=2, resample=True)
            a, b = [process_atlas(path, options) for path in paths]
            self.assertIsNotNone(a.frames[2].getchannel('A').getbbox())
            self.assertEqual(a.atlas.tobytes(), b.atlas.tobytes())

    def test_uniform_crop_preserves_motion_pixels_and_empty_frame(self):
        # Three 10x8 frames. The third stays empty; the first two move by (2,1).
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'moving.png'
            source = Image.new('RGBA', (30, 8))
            source.putpixel((2, 2), (120, 30, 70, 255))
            source.putpixel((14, 3), (10, 220, 40, 90))
            source.save(path)
            result = process_atlas(path, Options(columns=3, rows=1, padding=0))
            self.assertEqual(result.atlas.size, (9, 3))
            self.assertEqual(result.frames[0].getpixel((0, 0)), (120, 30, 70, 255))
            self.assertEqual(result.frames[1].getpixel((2, 1)), (10, 220, 40, 90))
            self.assertIsNone(result.frames[2].getchannel('A').getbbox())

    def test_fractional_sampling_preserves_half_pixel_motion(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'motion.png'
            image = Image.new('RGBA', (9, 3))
            for x in (1, 2, 6, 7):
                image.putpixel((x, 1), (200, 60, 30, 255))
            image.save(path)
            result = process_atlas(path, Options(columns=2, rows=1, resample=True))
            centers = []
            for frame in result.frames:
                weights = [sum(frame.getpixel((x, y))[3] for y in range(frame.height)) for x in range(frame.width)]
                centers.append(sum((x + .5) * value for x, value in enumerate(weights)) / sum(weights))
            # Original continuous-cell centers differ by half a source pixel, not one pixel.
            self.assertAlmostEqual(centers[1] - centers[0], .5, delta=.003)

    def test_resampling_never_pulls_color_from_adjacent_cell(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'neighbors.png'
            image = Image.new('RGBA', (9, 3))
            for y in range(3):
                for x in range(9):
                    image.putpixel((x, y), (255, 0, 0, 255) if x < 4 else (0, 0, 255, 255))
            image.save(path)
            result = process_atlas(path, Options(columns=2, rows=1, resample=True))
            self.assertTrue(all(pixel[2] == 0 for pixel in result.frames[0].get_flattened_data() if pixel[3]))
            self.assertTrue(all(pixel[0] == 0 for pixel in result.frames[1].get_flattened_data() if pixel[3]))

    def test_threshold_does_not_clean_pixels_inside_crop(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'faint.png'
            image = Image.new('RGBA', (10, 10))
            image.putpixel((5, 5), (30, 60, 90, 255))
            image.putpixel((6, 5), (90, 30, 60, 1))
            image.putpixel((1, 1), (10, 10, 10, 1))
            image.save(path)
            result = process_atlas(path, Options(columns=1, rows=1, padding=1, threshold=1))
            self.assertEqual(result.atlas.size, (3, 3))
            self.assertEqual(result.atlas.getpixel((2, 1)), (90, 30, 60, 1))

    def test_center_mode_is_exact_and_mixed_parity_requires_resampling(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'center.png'
            image = Image.new('RGBA', (7, 4))
            image.putpixel((1, 1), (255, 20, 20, 255))
            image.save(path)
            with self.assertRaises(ProcessingSkipped) as error:
                process_atlas(path, Options(columns=1, rows=1, keep_center=True))
            self.assertEqual(error.exception.code, 'center_parity')
            result = process_atlas(path, Options(columns=1, rows=1, keep_center=True, resample=True))
            self.assertEqual(result.plan.crop_x + result.plan.side / 2, 3.5)
            self.assertEqual(result.plan.crop_y + result.plan.side / 2, 2)

    def test_non_integral_and_fully_empty_inputs_are_explicitly_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'empty.png'
            Image.new('RGBA', (13, 13)).save(path)
            with self.assertRaises(ProcessingSkipped) as error:
                process_atlas(path, Options())
            self.assertEqual(error.exception.code, 'non_integral')
            with self.assertRaises(ProcessingSkipped) as error:
                process_atlas(path, Options(columns=1, rows=1))
            self.assertEqual(error.exception.code, 'empty')


if __name__ == '__main__':
    unittest.main()
