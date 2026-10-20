# 现状

## 目标

AtlasTrim 1.1 工程已在 GitHub 公开，提供中英文 README 和 Windows EXE 下载。

## 已定

- 图集裁剪规则见 [ADR 0001](docs/adr/0001-atlas-processing-design.md)；整体等比缩放规则见 [ADR 0002](docs/adr/0002-uniform-atlas-size.md)。
- 用户于 2026-10-20 要求公开仓库并提供中英文双文档；英文首页使用 README.md，中文使用 README.zh-CN.md，两者互相链接。

## 现状

- [Aendier/FrameByFrameAnimationProcessing](https://github.com/Aendier/FrameByFrameAnimationProcessing) 已设为公开，默认分支 main，远程 origin 已配置。
- [English README](README.md) 与[中文 README](README.zh-CN.md) 包含对应的下载、功能、快速使用、统一尺寸示例、构建与验证说明；语言切换、本地链接及两份文档中的命令一致性均已检查。
- 1.1 实现归档于 `0500fb7`，发布标签 v1.1 对应同一提交；[Release](https://github.com/Aendier/FrameByFrameAnimationProcessing/releases/tag/v1.1) 提供 AtlasTrim.exe、Usage.md 和 SHA256SUMS.txt，附件已完成校验。
- 既有 23 项行为测试通过；本轮修改为仓库可见性和文档，运行源码与 EXE 沿用已验证的 1.1。历史结果见 [验证记录](docs/VALIDATION.md)。
- 原素材、Output、构建产物和本地验证证据保留在本地，并排除在 Git 之外。

## 下一步

后续开发从 main 分支继续；更新项目介绍时同步维护中英文 README。
