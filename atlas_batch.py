"""Directory scanning and failure-isolated, non-overwriting batch export."""
from __future__ import annotations

import csv
import json
import struct
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from PIL import Image, PngImagePlugin

from atlas_processor import Options, ProcessingSkipped, has_transparency, process_atlas


@dataclass(frozen=True)
class FileEntry:
    path: Path
    relative: str
    width: int = 0
    height: int = 0
    error: str = ''


@dataclass(frozen=True)
class Job:
    path: Path
    options: Options


def scan_folder(folder: str | Path, recursive: bool = False) -> list[FileEntry]:
    root = Path(folder).resolve()
    if not root.is_dir():
        raise ValueError('输入文件夹不存在')
    candidates = root.rglob('*') if recursive else root.iterdir()
    paths = sorted((p for p in candidates if p.is_file() and p.suffix.lower() == '.png'),
                   key=lambda p: str(p.relative_to(root)).casefold())
    entries = []
    for path in paths:
        relative = str(path.relative_to(root))
        try:
            with Image.open(path) as image:
                if image.format != 'PNG':
                    raise ValueError('文件内容不是PNG')
                if not has_transparency(image):
                    raise ValueError('PNG没有透明信息')
                width, height = image.size
            entries.append(FileEntry(path, relative, width, height))
        except Exception as error:
            entries.append(FileEntry(path, relative, error=str(error)))
    return entries


def validate_output(input_folder: str | Path, output_folder: str | Path) -> tuple[Path, Path]:
    source, target = Path(input_folder).resolve(), Path(output_folder).resolve()
    if not source.is_dir():
        raise ValueError('输入文件夹不存在')
    if target == source or source in target.parents:
        raise ValueError('输出文件夹不能与输入文件夹相同或位于输入目录内部')
    if target.exists() and not target.is_dir():
        raise ValueError('输出路径不是文件夹')
    return source, target


def _exclusive_file(path: Path):
    """Reserve the name atomically; existing output is never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    number = 0
    while True:
        candidate = path if number == 0 else path.with_name(f'{path.stem}_{number}{path.suffix}')
        try:
            return candidate, candidate.open('xb')
        except FileExistsError:
            number += 1


def _save_png(result, target: Path) -> Path:
    pnginfo = PngImagePlugin.PngInfo()
    info = result.metadata
    if 'srgb' in info:
        pnginfo.add(b'sRGB', bytes([info['srgb']]))
    if 'gamma' in info:
        pnginfo.add(b'gAMA', struct.pack('>I', round(info['gamma'] * 100000)))
    if 'chromaticity' in info:
        pnginfo.add(b'cHRM', struct.pack('>8I', *(round(value * 100000)
                                              for value in info['chromaticity'])))
    arguments = {'pnginfo': pnginfo}
    for key in ('icc_profile', 'dpi'):
        if key in info:
            arguments[key] = info[key]
    path, stream = _exclusive_file(target)
    try:
        with stream:
            result.atlas.save(stream, format='PNG', **arguments)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def export_batch(jobs: list[Job], input_folder: str | Path, output_folder: str | Path,
                 on_result: Callable[[int, dict], None] | None = None,
                 cancel: threading.Event | None = None) -> dict:
    source, target = validate_output(input_folder, output_folder)
    target.mkdir(parents=True, exist_ok=True)
    records = []
    counts = {'success': 0, 'skipped': 0, 'failed': 0}
    for index, job in enumerate(jobs):
        if cancel is not None and cancel.is_set():
            break
        record = {'input': str(job.path), 'options': asdict(job.options), 'warnings': []}
        try:
            # Derive the target from the actual source, never from an unchecked relative name.
            relative = job.path.resolve().relative_to(source)
            result = process_atlas(job.path, job.options)
            output = _save_png(result, target / relative)
            record.update(status='success', output=str(output), reason='',
                          source_size=list(result.source_size), output_size=list(result.atlas.size),
                          crop=asdict(result.plan), warnings=result.warnings)
            del result
        except ProcessingSkipped as error:
            record.update(status='skipped', reason=str(error), code=error.code)
        except Exception as error:
            record.update(status='failed', reason=f'{type(error).__name__}: {error}')
        counts[record['status']] += 1
        records.append(record)
        if on_result:
            on_result(index, record)
    report = {'version': 1, 'created_at': datetime.now().astimezone().isoformat(),
              'input_folder': str(source), 'output_folder': str(target),
              'counts': counts, 'total_requested': len(jobs),
              'cancelled': len(records) < len(jobs), 'results': records}
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path, stream = _exclusive_file(target / f'处理清单_{stamp}.json')
    report['report_path'] = str(json_path)
    with stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8'))
    csv_path, csv_stream = _exclusive_file(target / f'处理清单_{stamp}.csv')
    with csv_stream:
        import io
        text_stream = io.TextIOWrapper(csv_stream, encoding='utf-8-sig', newline='')
        writer = csv.writer(text_stream)
        writer.writerow(['输入', '状态', '输出', '原因', '警告'])
        labels = {'success': '成功', 'skipped': '跳过', 'failed': '失败'}
        for record in records:
            writer.writerow([record['input'], labels[record['status']], record.get('output', ''),
                             record['reason'], '；'.join(record['warnings'])])
        text_stream.flush()
        text_stream.detach()
    report['csv_path'] = str(csv_path)
    return report
