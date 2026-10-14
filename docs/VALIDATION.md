# AtlasTrim 验证记录

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
