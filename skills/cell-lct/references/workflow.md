# Cell-lct Workflow (100% Free & Local)

## 1. Prepare one complete reference

Keep the untouched source. Before vectorization, record all visible text as a text manifest with content, coordinates, dimensions, font, size, weight, color, rotation, alignment, opacity, z-index, and paint order.

Use image editing / Image 2 to remove text only. The cleaned reference retains arrows, connectors, frames, axes, heatmaps, legends, scientific subjects, colors, spacing, and layout.

## 2. Build one Master SVG

Send the complete text-cleaned reference to the local vector engine (`local_vectorize.py` using `vtracer`). This runs 100% locally on your computer with no cloud APIs, tokens, or credits.

Add the recorded text back as live SVG `<text>` elements before caching, at the original coordinates and z-order.

## 3. Normalize and cache once

Resolve transforms and convert supported primitives to Illustrator-compatible solid geometry while preserving paint order, style, open/closed state, compound-path membership, and live text.

Run `prepare_geometry_cache.py` to create `geometry-cache.json` and `playback.json`.

## 4. Batch policy

- Ordinary batches contain 20–50 consecutive atoms.
- Rebalance the final ordinary batch so it is not reduced to 1–4 atoms.
- Only a genuinely complex atom may form a singleton batch.
- Preserve compound and clipping units that would change appearance if split.

## 5. One Illustrator session

Capture the active Illustrator document and create one COM connection at playback start. Reuse both until completion.

Append each batch in Master SVG paint order. Existing artwork remains untouched.

## 6. Save, export, and recover

Save on a timer and at completion. Export PNG once after all batches finish.
