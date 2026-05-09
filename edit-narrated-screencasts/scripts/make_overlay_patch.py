#!/usr/bin/env python3
"""Create a transparent overlay patch from a clean frame."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def load_pillow():
    try:
        from PIL import Image, ImageChops, ImageFilter
    except ImportError as exc:
        raise SystemExit("Pillow is required. Install it with: python3 -m pip install pillow") from exc
    return Image, ImageChops, ImageFilter


def parse_bbox(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    try:
        parts = [int(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"bbox must be integers: {exc}") from exc
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be x,y,w,h")
    x, y, w, h = parts
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("bbox width and height must be positive")
    return x, y, w, h


def make_bbox_mask(image_module: object, size: tuple[int, int], bbox: tuple[int, int, int, int]) -> object:
    image_new = getattr(image_module, "new")
    mask = image_new("L", size, 0)
    x, y, w, h = bbox
    mask.paste(255, (x, y, x + w, y + h))
    return mask


def make_diff_mask(
    image_chops_module: object,
    image_filter_module: object,
    clean: object,
    dirty: object,
    threshold: int,
    expand: int,
) -> object:
    difference = getattr(image_chops_module, "difference")
    max_filter = getattr(image_filter_module, "MaxFilter")
    diff = difference(clean.convert("RGB"), dirty.convert("RGB")).convert("L")
    mask = diff.point(lambda value: 255 if value >= threshold else 0)
    if expand > 0:
        kernel = expand * 2 + 1
        mask = mask.filter(max_filter(kernel))
    return mask


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean", type=Path, help="Clean replacement frame")
    parser.add_argument("dirty", type=Path, help="Dirty frame with artifact")
    parser.add_argument("output", type=Path, help="Transparent PNG patch output")
    parser.add_argument("--bbox", type=parse_bbox, help="Patch rectangle as x,y,w,h")
    parser.add_argument("--mask", type=Path, help="Optional grayscale alpha mask")
    parser.add_argument("--diff-alpha", action="store_true", help="Use frame difference as alpha")
    parser.add_argument("--threshold", type=int, default=18, help="Difference threshold for --diff-alpha")
    parser.add_argument("--expand", type=int, default=3, help="Pixel expansion for --diff-alpha mask")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without writing")
    args = parser.parse_args()

    Image, ImageChops, ImageFilter = load_pillow()

    clean_path = args.clean.expanduser()
    dirty_path = args.dirty.expanduser()
    if not clean_path.exists():
        raise SystemExit(f"Clean frame not found: {clean_path}")
    if not dirty_path.exists():
        raise SystemExit(f"Dirty frame not found: {dirty_path}")

    clean = Image.open(clean_path).convert("RGBA")
    dirty = Image.open(dirty_path).convert("RGBA")
    if clean.size != dirty.size:
        raise SystemExit(f"Frame sizes differ: clean={clean.size}, dirty={dirty.size}")

    if args.mask:
        mask_path = args.mask.expanduser()
        if not mask_path.exists():
            raise SystemExit(f"Mask not found: {mask_path}")
        mask = Image.open(mask_path).convert("L").resize(clean.size)
    elif args.diff_alpha:
        mask = make_diff_mask(ImageChops, ImageFilter, clean, dirty, args.threshold, args.expand)
        if args.bbox:
            bbox_mask = make_bbox_mask(Image, clean.size, args.bbox)
            mask = ImageChops.multiply(mask, bbox_mask)
    elif args.bbox:
        mask = make_bbox_mask(Image, clean.size, args.bbox)
    else:
        raise SystemExit("Provide --bbox, --mask, or --diff-alpha.")

    alpha_bbox = mask.getbbox()
    print(f"Patch size: {clean.size[0]}x{clean.size[1]}")
    print(f"Alpha bbox: {alpha_bbox}")
    if args.dry_run:
        return 0

    patch = Image.new("RGBA", clean.size, (0, 0, 0, 0))
    patch.alpha_composite(clean)
    patch.putalpha(mask)
    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    patch.save(output)
    print(f"Patch written: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
