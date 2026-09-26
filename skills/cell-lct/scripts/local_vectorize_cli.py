#!/usr/bin/env python3
"""
local_vectorize_cli.py - Raster-to-SVG vectorizer backed by the standalone
VTracer command-line binary.

This is an ALTERNATIVE to local_vectorize.py (which imports the `vtracer` pip
package). On some Python versions the pip package's native extension crashes
(access violation); the prebuilt vtracer.exe is self-contained and does not
depend on the Python interpreter at all. Both scripts are kept so the workflow
stays compatible across machines.

CLI reference (VTracer 0.6.x):
  vtracer --input IN --output OUT --colormode color|binary
          --hierarchical stacked|cutout --mode spline|polygon|none
          --filter_speckle N --color_precision N
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Reuse the post-processing (viewBox + stable ids) from the pip-backed script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_vectorize import ensure_ids_and_viewbox  # noqa: E402


def resolve_binary(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        raise FileNotFoundError(f"vtracer binary not found: {p}")
    # default layout: <skill>/bin/vtracer.exe next to <skill>/scripts/
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "bin" / "vtracer.exe",
        here.parent / "bin" / "vtracer",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "Could not locate vtracer binary. Place it at ../bin/vtracer.exe or "
        "pass --binary explicitly."
    )


def run(input_image: Path, output_svg: Path, binary: Path,
        colormode: str, hierarchical: str, mode: str,
        filter_speckle: int, color_precision: int) -> None:
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(binary),
        "--input", str(input_image),
        "--output", str(output_svg),
        "--colormode", colormode,
        "--hierarchical", hierarchical,
        "--mode", mode,
        "--filter_speckle", str(filter_speckle),
        "--color_precision", str(color_precision),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"vtracer CLI failed (exit {proc.returncode})")
    ensure_ids_and_viewbox(output_svg)


def main() -> int:
    ap = argparse.ArgumentParser(description="Local image-to-SVG via VTracer CLI")
    ap.add_argument("--input", "-i", required=True, type=Path)
    ap.add_argument("--output", "-o", required=True, type=Path)
    ap.add_argument("--binary", default=None,
                    help="path to vtracer.exe (default: ../bin/vtracer.exe)")
    ap.add_argument("--colormode", choices=["color", "binary"], default="color")
    ap.add_argument("--hierarchical", choices=["stacked", "cutout"], default="stacked")
    ap.add_argument("--mode", choices=["spline", "polygon", "none"], default="spline")
    ap.add_argument("--filter-speckle", type=int, default=4)
    ap.add_argument("--precision", "--color-precision", dest="precision",
                    type=int, default=6)
    args = ap.parse_args()

    if not args.input.exists():
        sys.stderr.write(f"Input file not found: {args.input}\n")
        return 1
    binary = resolve_binary(args.binary)
    run(args.input, args.output, binary, args.colormode,
        args.hierarchical, args.mode, args.filter_speckle, args.precision)
    sys.stdout.write(f"Vectorized successfully: {args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
