#!/usr/bin/env python3
"""
local_vectorize.py - High quality local & free raster-to-SVG vectorizer for Cell-lct.
Uses open-source vtracer (Rust-backed high-speed vectorization engine) with zero API keys or cloud dependencies.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def ensure_ids_and_viewbox(svg_path: Path) -> None:
    """Post-process SVG to guarantee compliant viewBox and unique stable IDs for all paths."""
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Normalize tag name
    tag_clean = root.tag.rsplit("}", 1)[-1]
    if tag_clean != "svg":
        return

    # Check / fix viewBox
    view_box = root.attrib.get("viewBox")
    if not view_box:
        w = root.attrib.get("width", "").replace("px", "").strip()
        h = root.attrib.get("height", "").replace("px", "").strip()
        try:
            wf = float(w)
            hf = float(h)
            if wf > 0 and hf > 0:
                root.attrib["viewBox"] = f"0 0 {wf:.2f} {hf:.2f}"
        except ValueError:
            pass

    # Assign stable IDs to vector elements
    vector_tags = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "g"}
    index = 0
    for elem in root.iter():
        elem_tag = elem.tag.rsplit("}", 1)[-1]
        if elem_tag in vector_tags:
            if not elem.attrib.get("id"):
                elem.attrib["id"] = f"vec_{elem_tag}_{index:05d}"
                index += 1

    tree.write(svg_path, encoding="utf-8", xml_declaration=False)


def run_vectorization(input_image: Path, output_svg: Path, colormode: str = "color", precision: int = 6) -> None:
    try:
        import vtracer
    except ImportError:
        sys.stderr.write(
            "ERROR: 'vtracer' is not installed in Python environment.\n"
            "Please run: pip install vtracer\n"
        )
        sys.exit(1)

    output_svg.parent.mkdir(parents=True, exist_ok=True)

    # Convert image to SVG using vtracer
    vtracer.convert_image_to_svg_py(
        str(input_image),
        str(output_svg),
        colormode=colormode,       # "color" or "binary"
        hierarchical="stacked",   # "stacked" or "cutout"
        mode="spline",            # "spline" (smooth beziers), "polygon", "none"
        filter_speckle=4,         # clean small noisy spots
        color_precision=precision, # 6-8 bits color quantization
        layer_difference=16,      # layer grouping
        corner_threshold=60,      # corner smoothing angle
        length_threshold=4.0,     # segment length
        splice_threshold=45       # curve splice angle
    )

    # Post-process for Cell-lct geometry compatibility
    ensure_ids_and_viewbox(output_svg)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Free Image-to-SVG Vectorizer for Cell-lct")
    parser.add_argument("--input", "-i", required=True, type=Path, help="Input raster image file (.png, .jpg, .webp)")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Output destination .svg file")
    parser.add_argument("--colormode", choices=["color", "binary"], default="color", help="Color mode")
    parser.add_argument("--precision", type=int, default=6, help="Color precision level (1-8)")
    
    args = parser.parse_args()

    if not args.input.exists():
        sys.stderr.write(f"Input file not found: {args.input}\n")
        return 1

    run_vectorization(args.input, args.output, args.colormode, args.precision)
    sys.stdout.write(f"Vectorized successfully: {args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
