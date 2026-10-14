"""PNG -> uniformly cropped square-frame atlas. No UI or global settings."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np

from PIL import Image

MAX_OUTPUT_PIXELS = 64_000_000


class ProcessingSkipped(Exception):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code


@dataclass(frozen=True)
class Options:
    columns: int = 5
    rows: int = 5
    padding: int = 2
    threshold: int = 0
    keep_center: bool = False
    resample: bool = False

    def validate(self) -> None:
        if not 1 <= self.columns <= 4096 or not 1 <= self.rows <= 4096:
            raise ProcessingSkipped('grid', '行列数必须为1～4096的正整数')
        if self.columns * self.rows > 4096:
            raise ProcessingSkipped('grid', '单张图集最多支持4096帧')
        if not 0 <= self.padding <= 4096:
            raise ProcessingSkipped('padding', '留边必须为0～4096像素')
        if not 0 <= self.threshold <= 255:
            raise ProcessingSkipped('threshold', 'alpha阈值必须为0～255')


@dataclass(frozen=True)
class CropPlan:
    frame_width: float
    frame_height: float
    crop_x: float
    crop_y: float
    side: int
    columns: int
    rows: int


@dataclass
class ProcessedAtlas:
    atlas: Image.Image
    originals: list[Image.Image]
    frames: list[Image.Image]
    plan: CropPlan
    source_size: tuple[int, int]
    warnings: list[str]
    metadata: dict


def check_geometry(width: int, height: int, options: Options) -> None:
    options.validate()
    if options.columns > width or options.rows > height:
        raise ProcessingSkipped('grid', '网格不能多于图像像素：每帧至少需要1像素')
    if not options.resample:
        if width % options.columns or height % options.rows:
            raise ProcessingSkipped('non_integral',
                f'{width}×{height}不能被{options.columns}列×{options.rows}行整除；'
                '请核对网格，或显式启用重采样')
        if options.keep_center and (width // options.columns - height // options.rows) % 2:
            raise ProcessingSkipped('center_parity',
                '原帧宽高一奇一偶，无法整数对齐原中心；关闭保留中心或启用重采样')


def has_transparency(image: Image.Image) -> bool:
    return 'A' in image.getbands() or 'transparency' in image.info


def _resampled_frames(source: Image.Image, options: Options):
    """A shared unit-pixel lattice, centered on each continuous source cell.

    Bilinear donors are premultiplied and restricted to this cell. Cropping
    afterwards uses integer offsets on this lattice, so there is no second
    interpolation and no frame-specific recentering.
    """
    width = source.width / options.columns
    height = source.height / options.rows
    side = math.ceil(max(width, height))
    if side * side * options.columns * options.rows > MAX_OUTPUT_PIXELS:
        raise ProcessingSkipped('size', '重采样工作画布超过6400万像素；请检查网格')
    origin_x, origin_y = (width - side) / 2, (height - side) / 2
    pixels = np.asarray(source)
    frames = []
    for row in range(options.rows):
        for column in range(options.columns):
            cell_x, cell_y = column * width, row * height
            x = cell_x + origin_x + np.arange(side) + 0.5
            y = cell_y + origin_y + np.arange(side) + 0.5
            ix = np.floor(x - 0.5).astype(np.int64)
            iy = np.floor(y - 0.5).astype(np.int64)
            fx, fy = x - 0.5 - ix, y - 0.5 - iy
            inside_x = (x >= cell_x) & (x < cell_x + width)
            inside_y = (y >= cell_y) & (y < cell_y + height)
            summed = np.zeros((side, side, 4), dtype=np.float32)
            for offset_y, weight_y in [(0, 1 - fy), (1, fy)]:
                donor_y = iy + offset_y
                valid_y = ((donor_y >= 0) & (donor_y < source.height) &
                           (donor_y + 0.5 >= cell_y) &
                           (donor_y + 0.5 < cell_y + height) & inside_y)
                weight_y = np.where(valid_y, weight_y, 0)
                for offset_x, weight_x in [(0, 1 - fx), (1, fx)]:
                    donor_x = ix + offset_x
                    valid_x = ((donor_x >= 0) & (donor_x < source.width) &
                               (donor_x + 0.5 >= cell_x) &
                               (donor_x + 0.5 < cell_x + width) & inside_x)
                    weight_x = np.where(valid_x, weight_x, 0)
                    samples = pixels[np.ix_(np.clip(donor_y, 0, source.height - 1),
                                            np.clip(donor_x, 0, source.width - 1))].astype(np.float32)
                    samples[..., :3] *= samples[..., 3:4] / 255.0
                    weights = (weight_y[:, None] * weight_x[None, :]).astype(np.float32)
                    summed += samples * weights[..., None]
            alpha = summed[..., 3:4]
            np.divide(summed[..., :3] * 255, alpha, out=summed[..., :3], where=alpha > 0)
            summed[..., :3][np.repeat(alpha <= 0, 3, axis=2)] = 0
            frames.append(Image.fromarray(np.clip(np.rint(summed), 0, 255).astype(np.uint8)))
    return frames, width, height, origin_x, origin_y


def _crop_frames(frames: list[Image.Image], options: Options,
                 width: float, height: float, origin_x: float = 0,
                 origin_y: float = 0) -> tuple[list[Image.Image], CropPlan, list[str]]:
    boxes = []
    edges = []
    lut = [255 if value > options.threshold else 0 for value in range(256)]
    for number, frame in enumerate(frames):
        box = frame.getchannel('A').point(lut).getbbox()
        if box is not None:
            boxes.append(box)
            left, top, right, bottom = box
            if (left <= -origin_x or top <= -origin_y or
                    right >= width - origin_x or bottom >= height - origin_y):
                edges.append(number + 1)
    if not boxes:
        raise ProcessingSkipped('empty', '当前alpha阈值下整张图集没有有效内容')
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    bottom = max(box[3] for box in boxes)
    work_width, work_height = frames[0].size
    if options.keep_center:
        side = max(work_width - 2 * left, 2 * right - work_width,
                   work_height - 2 * top, 2 * bottom - work_height) + 2 * options.padding
        crop_x = (work_width - side) // 2
        crop_y = (work_height - side) // 2
    else:
        core = max(right - left, bottom - top)
        side = core + 2 * options.padding
        crop_x = left - options.padding - (core - (right - left)) // 2
        crop_y = top - options.padding - (core - (bottom - top)) // 2
    if side * side * options.columns * options.rows > MAX_OUTPUT_PIXELS:
        raise ProcessingSkipped('size', '输出超过6400万像素；请减少留边或网格帧数')
    box = (crop_x, crop_y, crop_x + side, crop_y + side)
    result = [frame.crop(box) for frame in frames]
    plan = CropPlan(width, height, crop_x + origin_x, crop_y + origin_y,
                    side, options.columns, options.rows)
    warnings = []
    if edges:
        detail = '、'.join(map(str, edges[:8])) + ('…' if len(edges) > 8 else '')
        warnings.append(f'第{detail}帧内容触及原格边缘；源图已缺失的内容无法恢复')
    return result, plan, warnings


def process_atlas(path: str | Path, options: Options) -> ProcessedAtlas:
    options.validate()
    with Image.open(path) as image:
        if image.format != 'PNG':
            raise ProcessingSkipped('format', '只支持PNG图集')
        if not has_transparency(image):
            raise ProcessingSkipped('transparency', 'PNG没有透明通道或透明信息')
        check_geometry(*image.size, options)
        metadata = dict(image.info)
        source = image.convert('RGBA')
    width, height = source.size
    if options.resample:
        originals, frame_width, frame_height, origin_x, origin_y = _resampled_frames(source, options)
    else:
        frame_width = width // options.columns
        frame_height = height // options.rows
        originals = [source.crop((column * frame_width, row * frame_height,
                                  (column + 1) * frame_width, (row + 1) * frame_height))
                     for row in range(options.rows) for column in range(options.columns)]
        origin_x = origin_y = 0
    source.close()
    frames, plan, warnings = _crop_frames(originals, options, frame_width, frame_height,
                                         origin_x, origin_y)
    atlas = Image.new('RGBA', (plan.side * options.columns, plan.side * options.rows))
    for index, frame in enumerate(frames):
        atlas.paste(frame, ((index % options.columns) * plan.side,
                            (index // options.columns) * plan.side))
    return ProcessedAtlas(atlas, originals, frames, plan, (width, height), warnings, metadata)
