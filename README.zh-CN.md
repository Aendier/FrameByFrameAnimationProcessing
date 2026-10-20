# AtlasTrim

[English](README.md) | **简体中文**

离线 Windows 序列帧图集裁剪工具。对所有帧应用同一个正方形裁剪区域，去除透明空白边缘后，按原网格重新合成图集，保留帧间相对位置、动画位移、空帧和帧序。

## 下载

从 [GitHub Releases](https://github.com/Aendier/FrameByFrameAnimationProcessing/releases/tag/v1.1) 下载 `AtlasTrim.exe`，双击即可运行。Windows x64 单文件程序处理图片无需联网，也无需安装 Python。

程序界面和[详细使用说明](使用说明.md)目前为中文。

## 功能

- 所有帧共用一个裁剪区域，保持动画播放时的相对位置。
- 可逐张设置图集行列数、透明度阈值、留边，以及是否保留原画布中心。
- 提供严格整数裁剪；源尺寸不能被网格整除时，可显式启用亚像素重采样。
- 支持原图与处理结果同步播放、逐帧对比。
- 支持导出选中图片或批量导出 RGBA PNG，生成 CSV、JSON 处理清单，原图保持不变。
- 可开启统一尺寸，对最终合成的整张图集等比缩放，提供平滑／像素两种方式。

## 快速使用

1. 启动 `AtlasTrim.exe`，选择输入和输出文件夹。输出文件夹必须位于输入文件夹之外。
2. 扫描 PNG，为每张图集设置正确的列数和行数，默认 5 × 5。
3. 查看同步预览并调整裁剪参数。源尺寸不能被网格整除时，先核对网格，再按需显式启用重采样。
4. 如需限制最终图集大小，开启“统一尺寸”，填写最大宽高并选择缩放方式。
5. 导出选中图片或全部图片，在输出目录查看图片和处理清单。

## 统一尺寸

处理顺序：**所有帧统一裁剪 → 按原网格重新合成图集 → 对整张图集等比缩放**。

默认关闭；开启后默认最大宽高为 1024 × 1024，使用平滑缩放。大图缩小，小图也会放大。不为了达到目标尺寸补透明外边，也不为了网格整除调整最终尺寸。

设置 1024 × 1024 时：

| 合成后的图集 | 最终输出 |
|---|---|
| 2048 × 1024 | 1024 × 512 |
| 512 × 256 | 1024 × 512 |
| 任意正方形图集 | 1024 × 1024 |

最大宽高可以分别设置。至少一边精确达到设置值，另一边按比例四舍五入到整数像素，最少为 1 像素。因此，5 × 5 图集可以精确输出 1024 × 1024，每帧逻辑尺寸为 204.8 × 204.8。外部播放器应按完整图集等分，避免直接截断每格的小数宽度。

开启统一尺寸不会绕过严格裁剪模式对源网格的校验。预览与导出使用同一张最终图集。

## 开发与构建

已验证的构建环境为 Windows x64、Python 3.10.11（包含 tkinter）。在项目目录执行以下命令；Pyright 命令还需要 Node.js 和 npm。

```powershell
python -I -X utf8 -m pip install -r requirements.txt
python -I -X utf8 atlas_trim.py
python -I -X utf8 -m unittest discover -s tests -v
npm.cmd exec --yes --package=pyright -- pyright --pythonpath python atlas_processor.py atlas_batch.py atlas_trim.py verify_runtime.py
.\build.ps1 -PythonPath python
```

`build.ps1` 使用 UTF-8 BOM，以兼容 Windows PowerShell 5.1；生成 `dist/AtlasTrim.exe` 和配套使用说明。

## 验证

23 项行为测试涵盖统一裁剪偏移、像素保留、透明度阈值、空帧、非整数网格、半像素位移、插值边缘、跨格颜色隔离、统一尺寸、重名、失败隔离、清单写入失败、停止和输出目录链接检查。

原有 31 张示例素材保留在本地，未包含在仓库中。具备这套 `Origen/` 数据时，可额外执行打包 EXE 验证：

```powershell
python -I -X utf8 scripts/prepare_verification.py
.\scripts\verify_exe.ps1
```

验证会操作实际 EXE 的扫描、预览、逐帧和导出功能，检查尺寸、两种缩放方式、预览与导出像素一致、原素材 SHA-256 不变，以及运行依赖来自 EXE 内部。结果写入 `.artifacts/`。脚本会清空启动 EXE 时的外部 Python 路径，并将 `PYTHONHOME` 指向不存在的位置。

详细结果见[验证记录](docs/VALIDATION.md)，算法规则见[裁剪设计](docs/adr/0001-atlas-processing-design.md)和[统一尺寸设计](docs/adr/0002-uniform-atlas-size.md)。这些文档目前为中文。

`Origen/`、`Output/`、`dist/`、`build/` 和 `.artifacts/` 不纳入 Git。EXE 通过 GitHub Releases 提供。
