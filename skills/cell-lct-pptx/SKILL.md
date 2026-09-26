---
name: cell-lct-pptx
description: >
  把用户上传的科研参考图（流程图、机制图、Graphical Abstract、综述图、示意图）
  重建为 PowerPoint 幻灯片上原生、可编辑的形状：每条 SVG 路径逐段重建成
  Freeform（三次贝塞尔 1:1 映射为 msoSegmentCurve 节点），基本图形转路径，
  文字变成原生可编辑文本框——而不是插入一张图片。当用户说"按图片在 PPT /
  PowerPoint 里画矢量图"、"把这张图转成可编辑的 PPT 形状"、"在幻灯片里描摹
  这张图"、"PPT 矢量化"、"图片转可编辑图形到 PPT"、"cell-lct PPT 版"、"不要
  插图、要能编辑的形状"时使用。用户需先打开一个 PowerPoint 演示文稿并选中
  目标幻灯片。本 skill 是 cell-lct 的 PowerPoint 后端可选项，与 Illustrator
  版共存、互不替换。
---

# Cell-lct PowerPoint 后端（原生可编辑形状）

本 skill 是 cell-lct 系列的 **PowerPoint 输出后端**，与 `cell-lct` /
`cell-lct-doubao`（Illustrator 输出）共存，作为独立可选项触发，不替换任何
已有 skill。

核心区别：不是把 SVG 或位图"插入"幻灯片（那样只是一张不可编辑的图片），
而是通过 PowerPoint COM 把**每条路径逐节点重建成原生 Freeform 形状**：

- 三次贝塞尔曲线 1:1 映射为 `msoSegmentCurve` + `msoEditingCorner` 节点，
  两个控制点和终点完全保留；
- `rect / circle / ellipse / line / polygon / polyline` 先转成路径再渲染；
- `<text>` 变成原生文本框，文字内容、字体、字号、加粗、颜色、对齐均可编辑；
- 所有形状按 SVG 底层到顶层的绘制顺序创建，最后编成一个组。

## 前置检查（每次开工前必做）

1. 用户已打开 PowerPoint 演示文稿并**选中目标幻灯片**。本 skill 只在当前
   活动幻灯片上追加形状，不新建/关闭演示文稿，也不改动幻灯片上已有的任何
   形状。若没有活动幻灯片，提示用户先打开并选中，不要自行启动 PowerPoint。
2. Python 环境可用且已装 pywin32：
   `python -c "import win32com.client"`。缺失则 `pip install pywin32`。
3. 邻居资源存在（本 skill 复用基础版 cell-lct 的矢量化与文字合并运行时）：
   - `../cell-lct/bin/vtracer.exe`（独立矢量化 CLI，不依赖 Python 扩展）
   - `../cell-lct/scripts/local_vectorize_cli.py`
   - `../cell-lct/scripts/merge_live_text.py`
   若缺失，说明基础版 cell-lct 未安装，提示先安装。
4. 在用户当前项目目录下建工作目录，所有中间文件放进去，不污染 skill 目录。

## 固定工作流

### Step 1 — 读参考图，生成 text manifest

用 Read 打开参考图（本地路径直接 Read；URL 先下载到本地再 Read）。逐段识别
图上所有可见文字，写出 `text-manifest.json`：

```json
{
  "schema_version": "1.0",
  "text_elements": [
    {
      "id": "t1",
      "content": "Stage 1\nInput",
      "x": 0.6875, "y": 0.4333,
      "coordinate_space": "normalized",
      "font_family": "Arial",
      "font_size": 28,
      "font_weight": "normal",
      "font_style": "normal",
      "fill": "#ffffff",
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

坐标用 normalized（0–1，相对于 SVG viewBox 宽高），`x`/`y` 为文字锚点。
换行用 `\n`。图上无文字时写 `"text_elements": []`。

### Step 2 — 用 Doubao 图生图模型去字

1. 本地文件先用 `FileBatchUpload` 上传，拿到云端 URL。
2. 调用 `image_edit`：
   - `image_reference_url_list`：[参考图 URL]
   - `model_version`：`seedream_4.5`（默认）；需要更强指令跟随可用
     `seedream_5.0_pro`
   - `prompt`：
     ```
     只移除图中所有可见文字和字形，并以邻近背景自然补全原位置。完整保留箭头
     及箭尾、连接线、框、坐标轴、刻度线、热图、图例、科研主体、颜色、尺寸、
     相对位置、层级和整体布局；不得新增、移动、重绘或改写任何非文字元素。不
     要生成任何新文字或伪文字。
     ```
   - `height`/`width`：与原图同比例，不要拉伸。
3. 把返回的去字图下载到工作目录，命名 `no_text.png`。

### Step 3 — 本地矢量化（独立 vtracer CLI）

```powershell
python "..\cell-lct\scripts\local_vectorize_cli.py" `
  --input ".\no_text.png" `
  --output ".\raw-vector.svg" `
  --colormode color --hierarchical stacked --mode spline `
  --filter-speckle 4 --precision 6
```

独立 exe 不经过会崩溃的 pip 原生扩展。若已有现成 SVG，可跳过 Step 2–3。

### Step 4 — 把真实文字合并回 SVG

```powershell
python "..\cell-lct\scripts\merge_live_text.py" `
  --input-svg ".\raw-vector.svg" `
  --text-manifest ".\text-manifest.json" `
  --output-svg ".\figure-master.svg"
```

失败时报 `TEXT_MERGE_ERROR|...`，按提示修 manifest（常见：id 重复、坐标非
数字、颜色不合法）。

### Step 5 — 渲染进当前 PowerPoint 幻灯片

先 dry-run 核对几何（不碰 PowerPoint）：

```powershell
python ".\scripts\svg_to_pptx.py" --input ".\figure-master.svg" --dry-run
```

确认真实渲染：

```powershell
python ".\scripts\svg_to_pptx.py" `
  --input ".\figure-master.svg" `
  --placement center `
  --max-width-fraction 0.85 --max-height-fraction 0.85 `
  --group-name "Vector Figure"
```

`--placement` 可选 `center / top-center / bottom-center / top-right /
bottom-right / top-left / bottom-left / left-center / right-center`。
脚本连接当前活动幻灯片，按绘制顺序追加形状并编组，已有形状保持不变。

## 关键技术约定（排错必读）

- **曲线节点必须用 `msoEditingCorner`**：`msoEditingAuto` 的曲线段只接受
  "终点"，PowerPoint 会自行计算控制点；若传入两个显式控制点会被错位解释，
  圆会变成尖菱形。Corner 节点接受完整的（控制点1、控制点2、终点）三元组，
  与 SVG `C` 命令一一对应。
- **开放路径不能设置填充**：PowerPoint 禁止对开放 Freeform 设置 Fill。
  开放子路径（如 `<line>`、未闭合的 polyline/path）按以下方式还原外观：
  1. 需要填充时，先建一个"闭合的 fill-only 孪生形状"（末尾补一条回到起点
     的线，描边隐藏）；
  2. 再建一个"开放的 stroke-only 形状"（填充隐藏）。
  闭合子路径则正常用一个形状同时承载填充与描边。
- 文本框按文字长度给足初始宽度、关闭自动换行（`WordWrap=0`），再按
  `text-anchor` 用最终尺寸重新定位，避免文字被裁切或换行。
- 支持：纯色填充/描边、不透明度、三次贝塞尔、直线、开闭路径、多子路径、
  圆弧（转三次贝塞尔）、transform 矩阵、原生文本。
- 不支持（遇到先在 SVG 侧简化，不要伪装）：渐变、图案、裁剪路径、滤镜、
  内嵌位图 `<image>`、网格/符号。

## 输出契约

- 矢量化阶段输出：`正在识别并矢量化结构...`
- 渲染阶段输出：`正在 PPT 中生成可编辑形状...`
- 成功后输出：`完成。已在当前幻灯片生成可编辑的原生形状组。` 并说明组名；
  可按需让用户另存演示文稿。
- 出错时简明指出失败步骤与用户需做的动作（例如"请先打开 PowerPoint 并选中
  一张幻灯片"）。

## 与其他 cell-lct skill 的边界

- `cell-lct` / `cell-lct-doubao` 输出到 **Adobe Illustrator**（COM/JSX）；
  本 skill 输出到 **PowerPoint**（COM Freeform）。三者共存、按需触发。
- 矢量化（vtracer CLI）、文字清单与合并、去字、绘制顺序与"不破坏已有内容"
  等约束与基础版一致；本 skill 只替换最终的"播放/渲染目标"。
- 用户明确说"用 Illustrator / AI"时切到 `cell-lct` 或 `cell-lct-doubao`；
  明确说"用 PPT / PowerPoint / 幻灯片"时用本 skill。
