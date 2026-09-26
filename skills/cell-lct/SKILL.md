---
name: cell-lct
description: Create, reconstruct, and append editable scientific vector figures with live editable text in the user's currently open Adobe Illustrator document. Use for scientific subjects, mechanism diagrams, workflows, graphical abstracts, review figures, reference-image recreation, and continued drawing while preserving existing artwork (100% Free & Offline version).
---

# Cell-lct (Free & Local Edition)

Use one fixed workflow:

`text manifest -> Image 2 text-only cleanup -> local vectorization (vtracer) -> live text merged into master SVG -> one-time geometry cache -> persistent Illustrator playback`

Read [references/workflow.md](references/workflow.md), [references/workflow-spec.md](references/workflow-spec.md), and [references/illustrator-runtime.md](references/illustrator-runtime.md) before execution.

## Public-response contract

- Before visible drawing begins, output: `正在识别并矢量化结构...`
- While visible drawing is in progress, output: `正在画图...`
- On success, return: `完成。已生成可编辑矢量图并导入 Illustrator 画板。`
- 100% free and offline: No API keys, no tokens, no credit deductions.

## First-use setup

- Let the user open and manage Illustrator (2026 or compatible version) and the target document.
- Ensure dependencies are installed via `setup.ps1` (`pip install fonttools vtracer`).
- No API configuration needed.

## Input routing

1. Treat every newly uploaded PNG, JPEG, or WebP as a Cell-lct vectorization job.
2. Before any reference image is processed, record a text manifest containing every visible text run's content, position, bounding box, font family, font size, font weight, color, rotation, alignment, opacity, z-index, and paint order.
3. Use Image 2 (or clean graphic layer) to remove text from the reference image, preserving all lines, arrows, frames, axes, heatmaps, legends, and subjects.
4. Run the local vectorizer (`scripts/vectorize-local.ps1` / `scripts/local_vectorize.py`) to produce a true-vector SVG.
5. Merge the recorded text back into the vector result as real editable SVG `<text>` elements at original positions and z-order via `scripts/merge_live_text.py`.
6. Validate geometry and run `scripts/run_cell_lct.ps1` to draw directly into the user's active Illustrator artboard.

## Reconstruction contract

1. Preserve the untouched reference and create the complete text manifest before cleanup.
2. Produce smooth, clean Bezier vector geometry using local high-speed vectorization.
3. Validate that no raster nodes remain in final paths.
4. Keep live `<text>` elements in the Master SVG before parsing to retain full typography editability.
5. Parse the Master SVG once with `scripts/prepare_geometry_cache.py`.
6. Batch paths in groups of 20–50 atoms to avoid COM blocking.
7. Append paths in exact paint order without altering or deleting existing artboard artwork.

## Scientific style

1. Clear scientific vector-illustration style, pure white background, flat 2D layout.
2. Clean lines, solid fills, standard hierarchy, and consistent recurring elements.
