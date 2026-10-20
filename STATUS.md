# 现状

## 目标

将 AtlasTrim 1.1 工程完整提交到 GitHub，保留源码历史，并提供对应的 Windows EXE 下载。

## 已定

- 图集裁剪规则见 [ADR 0001](docs/adr/0001-atlas-processing-design.md)；整体等比缩放规则见 [ADR 0002](docs/adr/0002-uniform-atlas-size.md)。
- 本轮用户已授权提交 GitHub；使用当前账号 Aendier，默认创建同名私有仓库，EXE 通过 Release 附件交付。

## 现状

- 1.1 已实现统一尺寸、最大宽高、平滑／像素切换及一致的预览、批量导出。
- 2026-10-20 重新运行 23 项行为测试，全部通过；EXE、4 个运行源码和 requirements.txt 的 SHA-256 均与既有 1.1 构建记录一致，未重新构建 EXE。
- 已整理源码、测试和文档的提交范围；素材、Output、构建产物和本地验证证据排除在 Git 之外。
- 原有 31 张素材与 EXE 验证结果见 [验证记录](docs/VALIDATION.md)。

## 下一步

提交本地更改，创建 Aendier/FrameByFrameAnimationProcessing 私有仓库并推送 main，上传 v1.1 的 EXE 和使用说明，核验远程内容。
