# 现状

## 目标

AtlasTrim 1.1 工程已提交 GitHub，保留源码历史，并提供对应的 Windows EXE 下载。

## 已定

- 图集裁剪规则见 [ADR 0001](docs/adr/0001-atlas-processing-design.md)；整体等比缩放规则见 [ADR 0002](docs/adr/0002-uniform-atlas-size.md)。
- 本轮用户已授权提交 GitHub；工程存放在 Aendier 账号的同名私有仓库，EXE 通过 Release 附件交付。

## 现状

- GitHub 仓库：[Aendier/FrameByFrameAnimationProcessing](https://github.com/Aendier/FrameByFrameAnimationProcessing)，私有，默认分支 main，已配置 origin 并推送原有提交历史。
- 1.1 源码实现归档于 `0500fb7`，发布标签 `v1.1` 对应同一提交；已实现统一尺寸、最大宽高、平滑／像素切换及一致的预览和批量导出。
- [v1.1 Release](https://github.com/Aendier/FrameByFrameAnimationProcessing/releases/tag/v1.1) 包含 AtlasTrim.exe、Usage.md（使用说明）和 SHA256SUMS.txt；3 个附件的远程 SHA-256、大小和上传状态均已核验。
- 2026-10-20 重新运行 23 项行为测试，全部通过；EXE、4 个运行源码和 requirements.txt 的 SHA-256 均与既有 1.1 构建记录一致，未重新构建 EXE。
- 原素材、Output、构建产物和本地验证证据保留在本地并排除在 Git 之外；既有 31 张素材与 EXE 验证结果见 [验证记录](docs/VALIDATION.md)。

## 下一步

用户可从私有仓库查看源码或从 v1.1 Release 下载 EXE；后续功能修改从 main 分支继续。
