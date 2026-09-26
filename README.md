# TC-cell-lct

包含三个互相协作的科研绘图 skill。仓库名称：`TC-Cell-lct-skills`。

| Skill | 用途 |
| --- | --- |
| [cell-lct](skills/cell-lct/SKILL.md) | 基础矢量化、真实文字合并、Adobe Illustrator 输出与共享运行时 |
| [cell-lct-doubao](skills/cell-lct-doubao/SKILL.md) | 使用 Doubao 图生图去字，复用基础版运行时输出到 Illustrator |
| [cell-lct-pptx](skills/cell-lct-pptx/SKILL.md) | 将 SVG 重建为 PowerPoint 原生可编辑路径和文本框 |

## 安装

下载本仓库，将 `skills/` 内的三个文件夹一起复制到你的 AI 工具的 skills 目录。保持三个文件夹并列；Doubao 和 PPTX 版本依赖 `../cell-lct/`，不能单独安装。

```text
<你的 skills 目录>/
├── cell-lct/
├── cell-lct-doubao/
└── cell-lct-pptx/
```

例如 Codex 默认目录是 `%USERPROFILE%\.codex\skills`，本集合原始 Doubao 目录是 `%USERPROFILE%\DoubaoWork\skills`。目标位置若已有同名 skill，先备份再自行决定是否替换。复制完成后重新加载工具，使其发现 skill。

## 运行条件

- Windows；Illustrator 输出需要 Adobe Illustrator 和活动文档；PPTX 输出需要桌面版 PowerPoint 和已选中的幻灯片。
- Python 3.10 或更高版本。按所用后端安装依赖：`python -m pip install fonttools vtracer pywin32`。
- 基础版带有 `bin/vtracer.exe`，PPTX 流程可使用独立 CLI；它与 Python 的 vtracer 扩展是两条可选执行路径。
- 去字需要宿主提供的图像编辑能力，或用户已准备好的去字图片。Doubao 的 `FileBatchUpload` / `image_edit` 并非所有宿主都有。
- 本地矢量化不调用云服务；图像生成或去字阶段是否联网、收费取决于所选宿主和服务，不能将整个流程视为必然免费或离线。

## 使用示例

- `使用 $cell-lct，将这张参考图重建到当前 Illustrator 文档，保留可编辑文字。`
- `使用 $cell-lct-doubao，通过豆包去字后生成 Illustrator 可编辑矢量图。`
- `使用 $cell-lct-pptx，将这张参考图重建为当前 PowerPoint 幻灯片上的原生可编辑形状。`

运行 skill 文档中的命令时，将脚本路径解析为实际安装目录的绝对路径；输入、输出及缓存放在工作项目目录中。文档里的相对路径不表示可以从任意目录直接执行。

## 打包说明与已有局限

本集合保留用户提供的三个 skill 及其共享脚本、参考资料和二进制文件。原始文件未改写；此仓库增加统一的集合说明。

- 基础版文档提及的 `setup.ps1` 不在原始文件中，安装依赖可使用上面的 Python 命令。
- 原版保留了小喵云相关辅助脚本，Doubao 文档中的历史描述与基础版“免费离线”表述存在差异；是否调用云服务以实际选择的工作流为准。
- 本次验证包括文件完整性、skill 元数据和 Python 语法；不代表已在 Illustrator、PowerPoint 或 Doubao 中完成端到端绘图测试。
- 原始目录没有提供整体授权许可证。本打包不擅自为原始代码或随附第三方二进制授予新许可证；再分发时需核实相应权利和第三方许可证。
