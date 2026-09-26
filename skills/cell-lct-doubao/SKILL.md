---
name: cell-lct-doubao
description: >
  把用户上传的科研参考图（流程图、机制图、Graphical Abstract、综述图、示意
  图）重建为 Adobe Illustrator 中可编辑的矢量路径和真实文字。本版本是
  cell-lct 的 Doubao 适配分支：保留原 cell-lct 的本地 vtracer 矢量化、文字
  合并和 Illustrator COM 播放脚本，仅把"去字"这一步替换为 Doubao 自带的图
  生图模型（不依赖 Codex Image 2 或第三方 API Key）。当用户说"按图片在
  Illustrator 里画矢量图"、"把这张图转成可编辑矢量"、"科研图矢量化"、
  "image trace 到 AI"、"描摹这张图"、"cell-lct"、"把图变成 Illustrator 路径"
  时使用。用户需先在 Illustrator 2026（或 2020–2025 兼容 COM 的版本）中打开
  目标文档。
---

# Cell-lct Doubao 适配版

本 skill 复用同目录邻居 `../cell-lct/scripts/` 下的全部 Python/PowerShell
运行时，不重复维护脚本。与原版 `cell-lct` 的唯一差异是：**去字步骤由 Doubao
自身的图生图模型完成**，而不是调用 Codex Image 2 或第三方云 API。

## 前置检查（每次开工前必做）

1. 确认用户已经在 Illustrator 里打开了目标文档。如果没开，提示用户先打开再
   继续；不要自己启动 Illustrator。
2. 确认脚本目录存在：`../cell-lct/scripts/local_vectorize.py`、
   `merge_live_text.py`、`run_cell_lct.ps1`。若缺失，说明原版 cell-lct 未安装，
   提示用户先装原版。
3. 确认 Python 可用：`python -c "import vtracer, fontTools"`。
4. 工作目录建在用户当前项目目录下，所有中间文件放进去，不要污染 skill 目录。

## 固定工作流

### Step 1 — 读参考图，生成 text manifest

用 Read 工具打开用户上传的参考图（本地路径直接 Read；URL 先下载到本地再
Read）。逐段识别图上所有可见文字，写出
`text-manifest.json`，schema 如下：

```json
{
  "schema_version": "1.0",
  "text_elements": [
    {
      "id": "t1",
      "content": "Stage 1\nInput",
      "x": 0.5, "y": 0.12,
      "coordinate_space": "normalized",
      "font_family": "Arial",
      "font_size": 14,
      "font_weight": "bold",
      "font_style": "normal",
      "fill": "#1f3a5f",
      "opacity": 1.0,
      "rotation": 0,
      "text_anchor": "middle",
      "alignment_baseline": "middle",
      "z_index": 10,
      "paint_order": 10,
      "line_height": 1.2
    }
  ]
}
```

坐标用 normalized（0–1，相对于 SVG viewBox 宽高），`x`/`y` 是文字锚点位置。
换行用 `\n`。如果图上确实没有任何文字，写 `"text_elements": []`。

### Step 2 — 用 Doubao 图生图模型去字

1. 如果参考图是本地文件，先用 `FileBatchUpload` 上传，拿到云端 URL。
2. 调用 `image_edit` 工具：
   - `image_reference_url_list`: [参考图 URL]
   - `model_version`: `seedream_4.5`（默认）；如果需要更强的指令跟随可用
     `seedream_5.0_pro`
   - `prompt`:
     ```
     只移除图中所有可见文字和字形，并以邻近背景自然补全原位置。完整保留箭头
     及箭尾、连接线、框、坐标轴、刻度线、热图、图例、科研主体、颜色、尺寸、
     相对位置、层级和整体布局；不得新增、移动、重绘或改写任何非文字元素。不
     要生成任何新文字或伪文字。
     ```
   - `height`/`width`: 与原图保持相同比例（读原图分辨率后设定，不要拉伸）。
3. 把模型返回的去字图 URL 下载到本地工作目录，命名 `no_text.png`。

### Step 3 — 本地 vtracer 矢量化

```powershell
python "..\cell-lct\scripts\local_vectorize.py" `
  --input ".\no_text.png" `
  --output ".\raw-vector.svg" `
  --colormode color --precision 6
```

### Step 4 — 把真实文字合并回 SVG

```powershell
python "..\cell-lct\scripts\merge_live_text.py" `
  --input-svg ".\raw-vector.svg" `
  --text-manifest ".\text-manifest.json" `
  --output-svg ".\figure-master.svg"
```

这一步失败时会报 `TEXT_MERGE_ERROR|...`，按错误信息修 manifest（常见：id
重复、坐标非数字、颜色值不合法）。

### Step 5 — 渲染进 Illustrator

```powershell
powershell -ExecutionPolicy Bypass -File "..\cell-lct\scripts\run_cell_lct.ps1" `
  -InputSvg ".\figure-master.svg" `
  -WorkDir ".\.cache" `
  -OutputAi ".\output.ai" `
  -OutputPng ".\output.png" `
  -Placement center -MaxWidthFraction 0.72 -MaxHeightFraction 0.78
```

如果想先不真的写 Illustrator、只验证几何，可以加 `-DryRun`。

## 输出契约

- 开始画图前输出：`正在识别并矢量化结构...`
- 画图过程中输出：`正在画图...`
- 成功后输出：`完成。已生成可编辑矢量图并导入 Illustrator 画板。` 并附上
  `.ai` 和 `.png` 的本地路径。
- 出错时简明说明失败在哪一步、需要用户做什么（例如"请先在 Illustrator 里
  打开目标文档"）。

## 与原版 cell-lct 的边界

- 原版 `cell-lct` 走 Codex Image 2 / 小喵云 API 去字，需要 API Key；本版走
  Doubao 图生图模型，无 Key 但出图风格可能略有差异。
- 两个 skill 可以共存，用户按需触发。如果用户明确说"用原版/付费版/小喵"，
  切到 `cell-lct`；否则默认用本版。
- Illustrator COM 播放、vtracer 参数、批次策略、不破坏已有画布等约束全部
  继承原版，不另立规矩。详见 `../cell-lct/references/workflow-spec.md`。
