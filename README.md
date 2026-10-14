# AtlasTrim

离线 Windows 图集裁剪工具。对同一图集的所有帧应用统一裁剪，补成相同尺寸的正方形帧，保留帧间位移、空帧、原网格和帧序。

直接运行 `dist/AtlasTrim.exe`，操作和示例网格见 [使用说明](使用说明.md)。算法与验收约定见 [ADR 0001](docs/adr/0001-atlas-processing-design.md)。

## 开发与构建

构建环境：Windows x64、Python 3.10.11（包含 tkinter）。在项目目录执行：

```powershell
python -I -X utf8 -m pip install -r requirements.txt
python -I -X utf8 atlas_trim.py
python -I -X utf8 -m unittest discover -s tests -v
npm.cmd exec --yes --package=pyright -- pyright --pythonpath python atlas_processor.py atlas_batch.py atlas_trim.py verify_runtime.py
.\build.ps1 -PythonPath python
```

`build.ps1` 使用 UTF-8 BOM，以兼容 Windows PowerShell 5.1；生成单文件 EXE 和配套使用说明。

## 实际素材和 EXE 验证

使用当前 `Origen/` 示例时：

```powershell
python -I -X utf8 scripts/prepare_verification.py
.\scripts\verify_exe.ps1
```

验证会调用 EXE 内的实际窗口扫描、预览、逐帧和导出动作，并处理 31 张示例。输出写入 `.artifacts/`；验证报告检查成功数量、正方形帧、三张已知尺寸、原文件 SHA-256，以及运行依赖确实来自 EXE 内部。脚本对启动的 EXE 清空外部 Python 路径，并将 `PYTHONHOME` 指向不存在的位置。

测试目录涵盖统一偏移、像素复制、透明阈值、空帧、非整数网格、半像素位移、插值边缘、跨格颜色隔离、重名、失败隔离、清单写入失败、停止和输出目录链接检查。

`Origen/`、`dist/`、`build/` 和 `.artifacts/` 不纳入 Git；处理过程不会改动原素材。
