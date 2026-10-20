# AtlasTrim 验证记录

## 2026-10-20：GitHub 归档

- 已将源码、测试、文档和完整本地提交历史推送至 [GitHub 仓库](https://github.com/Aendier/FrameByFrameAnimationProcessing) 的 main 分支。
- 重新运行全部 23 项行为测试，全部通过；未修改运行代码或重新构建 EXE。
- 本地 EXE、atlas_trim.py、atlas_processor.py、atlas_batch.py、verify_runtime.py 和 requirements.txt 的 SHA-256 均与既有 1.1 构建记录一致。
- [v1.1 Release](https://github.com/Aendier/FrameByFrameAnimationProcessing/releases/tag/v1.1) 对应源码提交 `0500fb7`，包含 AtlasTrim.exe、Usage.md（使用说明）和 SHA256SUMS.txt。三个附件的 GitHub SHA-256 均与本地文件一致，大小匹配，上传状态均为 uploaded。
- 已将 Output/ 加入忽略列表。原始素材、批量输出、构建目录和本地验证证据未上传。

## 2026-10-16：1.1 统一尺寸模式

最终交付为 `dist/AtlasTrim.exe`，28,423,066 字节，配套 `dist/使用说明.md`。EXE SHA-256：`F4854D74F29901D88C2B2B87481CF10334F81F5179BE9A456A0A4FFC8930ADA1`。

本次构建时使用 `586d4cf` 基线上的工作区修改；对应源码和测试现已归档到 `0500fb7`（发布标签 `v1.1`）。源码文件和 EXE 的精确哈希记录于 [build.json](../.artifacts/packaged-1.1/build.json)。规则见 [ADR 0002](adr/0002-uniform-atlas-size.md)。

| 检查 | 结果 |
|---|---|
| 行为测试 | 23 项通过，含原有 13 项及新增 10 项 |
| Pyright 静态检查 | 0 错误、0 警告 |
| 用户指定的缩小／放大示例 | 2048×1024、512×256 均输出 1024×512，无新增透明外边 |
| 5×5 精确尺寸 | 输出 1024×1024，逻辑帧 204.8×204.8；两种滤镜均与对完整图集缩放的结果逐字节一致 |
| EXE 统一尺寸窗口操作 | 开启后平滑输出 1024×1024，改为像素及非正方形目标后输出 512×512；预览与导出像素一致 |
| 关闭开关 | 恢复未缩放尺寸；宽高和滤镜控件禁用，未填写的目标宽高不影响原流程 |
| 最小窗口 1050×700 | 文件列表可选择、预览高度至少 100px、新尺寸控件可见、处理记录可展开 |
| 最终 EXE 原严格模式 | 成功 8，跳过 23，失败 0；0.67 秒 |
| 最终 EXE 原重采样模式 | 成功 31，跳过 0，失败 0；34.95 秒 |
| 最终 EXE 统一尺寸模式 | 成功 31，跳过 0，失败 0；33.05 秒 |
| 原素材 SHA-256 | 31 张全部未变 |

打包验证仍清空外部 Python 路径，并将 `PYTHONHOME` 指向不存在的位置。`frozen=true`，Pillow、numpy、tkinter 来自 EXE 内嵌依赖。当前 Windows x64 机器实测通过；未在其他机器重复测试。

全部结果见 [打包验证报告](../.artifacts/packaged-1.1/report.json)。31 张实际素材统一尺寸的预期输出为：5×5 与 4×4 输出 1024×1024，4×3 输出 1024×768，6×5 输出 1024×853。最后一种仅将非受限边舍入到整数像素，不为网格整除改动尺寸。处理清单区分缩放前裁剪参数、最终逻辑帧尺寸及实际横纵缩放比例。

输出和验证过程写入 `.artifacts/` 或测试临时目录，未改动用户已有 `Output/`。界面截图位于 `.artifacts/interface.png` 与 `.artifacts/interface_minimum.png`。

## 2026-10-14：初版验证归档

日期：2026-10-14。最终构建对应源码 `a4591d9`。目标为 Windows 10/11 x64，实测环境为当前 Windows x64 机器；未声称在第二台 Windows 10/11 机器上分别测试。

## 交付文件

- `dist/AtlasTrim.exe`，单文件，28,419,309 字节。
- `dist/使用说明.md`。
- EXE SHA-256：`0D964A5101DEC770BDB396797E43E667808382C5888E8A5EE3D7CF1098830D30`。

## 检查结果

| 检查 | 结果 |
|---|---|
| 行为测试 | 13 项通过 |
| Pyright 静态检查 | 0 错误、0 警告 |
| EXE 窗口扫描、同步预览、逐帧、导出选中 | 通过；扫描 31 张，Frost 输出 1412×1412 |
| 最小窗口 1050×700 | 说明和进度可见，预览高度至少 100px，处理记录可展开 |
| 严格模式实际素材 | 成功 8，跳过 23，失败 0；耗时 0.67 秒 |
| 重采样模式实际素材 | 成功 31，跳过 0，失败 0；耗时 32.38 秒 |
| 原文件 SHA-256 | 31 张全部未变 |
| 规范与需求独立审查 | 均通过，遗留发现 0 |
| 打包验证失败路径 | 等号形式参数返回退出码 1，2.14 秒内结束，无模态窗口 |

最终 EXE 使用 `scripts/verify_exe.ps1` 验证。启动环境的 PATH 只保留 System32、PYTHONPATH 为空、PYTHONHOME 指向不存在的位置。报告的 `frozen` 为 true，Pillow、numpy、tkinter 路径全部位于 EXE 自解包目录内。无需另外安装 Python。

完整实际素材报告保存在 [report.json](../.artifacts/packaged/report.json)。窗口检查截图在 `.artifacts/interface.png` 和 `.artifacts/interface_minimum.png`，通过窗口句柄抓取程序本身。

三张严格模式基准输出为 Frost 1412×1412、Yelena 1564×1564、Jill 1412×1059。所有成功输出均为 RGBA PNG，单帧宽高相等、保留原网格。非整数网格需要用户显式启用重采样，半透明边缘的像素值允许变化；严格模式测试比较原像素和帧间位置。

批量输出、处理清单写入和错误路径均在 `.artifacts/` 或测试临时目录验证，没有替用户写入默认 `Output/`。具体测试范围与复现命令见 [README](../README.md)，独立审查结果见 [REVIEW](REVIEW.md)。
