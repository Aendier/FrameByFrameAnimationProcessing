# AtlasTrim

**English** | [简体中文](README.zh-CN.md)

An offline Windows tool for trimming transparent margins from sprite animation atlases while preserving frame alignment and motion. It applies one shared square crop to every frame, then rebuilds the atlas with its original grid, frame order, and empty frames.

## Download

Download `AtlasTrim.exe` from [GitHub Releases](https://github.com/Aendier/FrameByFrameAnimationProcessing/releases/tag/v1.1) and run it directly. The Windows x64 executable requires no Python installation or network connection to process images.

The application interface and the [detailed usage guide](使用说明.md) are currently in Chinese.

## Features

- Use a shared crop across all frames to preserve their relative positions during playback.
- Configure the grid per image, the alpha threshold, transparent padding, and whether to preserve the original canvas center.
- Choose strict integer cropping or explicitly enable subpixel resampling for source grids that do not divide evenly.
- Compare the original and processed animation with synchronized playback and frame stepping.
- Export selected images or a batch as RGBA PNG files, with CSV and JSON processing reports. Source images remain unchanged.
- Optionally resize the entire assembled atlas to fit a target width and height, with smooth or nearest-neighbor scaling.

## Quick start

1. Run `AtlasTrim.exe` and choose separate input and output folders. The output folder must be outside the input folder.
2. Scan for PNG files and set the correct columns and rows for each atlas. The default is 5 × 5.
3. Check the synchronized preview and adjust the crop settings. If the source dimensions are not divisible by its grid, verify the grid or explicitly enable resampling.
4. Optionally enable uniform sizing, set the maximum width and height, and choose the scaling filter.
5. Export the selected images or the entire batch, then check the processing reports in the output folder.

## Uniform sizing

Processing order: **crop every frame with the same region → rebuild the atlas → resize the entire atlas proportionally**.

Uniform sizing is disabled by default. When enabled, the default maximum dimensions are 1024 × 1024, with smooth scaling. Smaller images are enlarged as well as larger images being reduced. No transparent border is added to reach the target size, and the final dimensions are not adjusted to grid multiples.

With a 1024 × 1024 target:

| Assembled atlas | Final output |
|---|---|
| 2048 × 1024 | 1024 × 512 |
| 512 × 256 | 1024 × 512 |
| Any square atlas | 1024 × 1024 |

Width and height can be set independently. At least one side reaches its configured limit; the other is rounded to the nearest whole pixel, with a minimum of one pixel. A 5 × 5 atlas can therefore be exactly 1024 × 1024 with logical cells of 204.8 × 204.8 pixels. External players should divide the full atlas into equal cells without truncating each cell's width to an integer.

Uniform sizing does not bypass source-grid validation in strict cropping mode. The preview and export use the same final atlas.

## Development and build

Validated build environment: Windows x64 with Python 3.10.11, including tkinter. Run these commands from the project directory. The Pyright command also requires Node.js and npm.

```powershell
python -I -X utf8 -m pip install -r requirements.txt
python -I -X utf8 atlas_trim.py
python -I -X utf8 -m unittest discover -s tests -v
npm.cmd exec --yes --package=pyright -- pyright --pythonpath python atlas_processor.py atlas_batch.py atlas_trim.py verify_runtime.py
.\build.ps1 -PythonPath python
```

`build.ps1` uses UTF-8 with BOM for Windows PowerShell 5.1 compatibility and creates `dist/AtlasTrim.exe` plus its usage guide.

## Validation

The 23 behavior tests cover shared crop offsets, pixel preservation, transparency thresholds, empty frames, fractional grids, half-pixel motion, interpolation edges, isolation between neighboring cells, uniform resizing, filename collisions, failure isolation, report-writing errors, cancellation, and output-directory links.

The original 31-image sample set is kept locally and is not included in the repository. If that `Origen/` dataset is available, run the optional packaged-EXE checks:

```powershell
python -I -X utf8 scripts/prepare_verification.py
.\scripts\verify_exe.ps1
```

These checks exercise scanning, preview, frame stepping, and export in the actual executable. They verify dimensions, both scaling filters, preview/export pixel consistency, unchanged source SHA-256 hashes, and bundled runtime dependencies. Results are written to `.artifacts/`. The launched EXE receives no external Python path, and `PYTHONHOME` points to a nonexistent location.

See the [validation record](docs/VALIDATION.md), [cropping design](docs/adr/0001-atlas-processing-design.md), and [uniform sizing design](docs/adr/0002-uniform-atlas-size.md) for details. These documents are in Chinese.

`Origen/`, `Output/`, `dist/`, `build/`, and `.artifacts/` are excluded from Git. Executables are distributed through GitHub Releases.
