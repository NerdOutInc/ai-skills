#!/usr/bin/env python3
"""Generate branded intro and outro title cards."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def load_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit("Pillow is required. Install it with: python3 -m pip install pillow") from exc
    return Image, ImageDraw, ImageFont


Image, ImageDraw, ImageFont = load_pillow()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Expected #RRGGBB color, got {value!r}")
    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def mix(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(a[i] * (1 - amount) + b[i] * amount) for i in range(3))  # type: ignore[return-value]


def resolve_path(path: str | None, base: Path) -> Path | None:
    if not path:
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate


def find_font(size: int, bold: bool = False) -> Any:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_vertical_gradient(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Any:
    image = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        amount = y / max(1, height - 1)
        draw.line([(0, y), (width, y)], fill=mix(top, bottom, amount))
    return image


def apply_vignette(image: Any, strength: float) -> Any:
    if strength <= 0:
        return image
    width, height = image.size
    center_x = width * 0.5
    center_y = height * 0.42
    max_distance = math.hypot(center_x, center_y)
    pixels = []
    for y in range(height):
        for x in range(width):
            distance = math.hypot(x - center_x, y - center_y) / max_distance
            alpha = min(1.0, distance * distance * strength)
            pixels.append(round(alpha * 255))
    mask = Image.new("L", (width, height))
    mask.putdata(pixels)
    dark = Image.new("RGB", (width, height), (15, 28, 18))
    return Image.composite(dark, image, mask)


def draw_wave_texture(image: Any, color: tuple[int, int, int], contrast: float) -> None:
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alpha = max(0, min(255, int(255 * contrast)))
    if alpha == 0:
        return
    line_color = (*color, alpha)
    spacing = height / 9
    amplitude = height * 0.018
    wavelength = width / 4.2
    for row in range(-1, 11):
        base_y = row * spacing + height * 0.07
        points = []
        for x in range(-40, width + 41, 16):
            y = base_y + math.sin((x / wavelength) * math.tau) * amplitude
            points.append((x, y))
        draw.line(points, fill=line_color, width=max(1, int(height / 720)))
    image.alpha_composite(overlay)


def draw_leaf(layer: Any, center: tuple[float, float], length: float, angle: float, color: tuple[int, int, int, int]) -> None:
    leaf_width = max(8, int(length * 0.42))
    leaf_height = max(8, int(length))
    leaf = Image.new("RGBA", (leaf_width * 2, leaf_height * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(leaf)
    box = (leaf_width * 0.45, leaf_height * 0.2, leaf_width * 1.55, leaf_height * 1.8)
    draw.ellipse(box, fill=color)
    rotated = leaf.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    x = int(center[0] - rotated.width / 2)
    y = int(center[1] - rotated.height / 2)
    layer.alpha_composite(rotated, (x, y))


def draw_wheat(image: Any, wheat: dict[str, Any], color: tuple[int, int, int], contrast: float) -> None:
    if not wheat.get("enabled", False):
        return
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alpha = max(0, min(255, int(255 * contrast * float(wheat.get("opacity_multiplier", 1.3)))))
    rgba = (*color, alpha)
    stems = wheat.get("stems") or [
        {"x": 0.085, "y1": 0.02, "y2": 0.44, "side": "left"},
        {"x": 0.92, "y1": 0.02, "y2": 0.50, "side": "right"},
        {"x": 0.865, "y1": 0.16, "y2": 0.43, "side": "right"},
    ]
    for stem in stems:
        x = width * float(stem.get("x", 0.9))
        y1 = height * float(stem.get("y1", 0.05))
        y2 = height * float(stem.get("y2", 0.45))
        side = -1 if stem.get("side") == "left" else 1
        draw.line([(x, y1), (x, y2)], fill=rgba, width=max(2, int(width / 900)))
        count = int(stem.get("leaves", 8))
        for index in range(count):
            y = y1 + (y2 - y1) * (index + 1) / (count + 2)
            direction = side if index % 2 == 0 else -side
            length = height * float(wheat.get("leaf_length", 0.045)) * (1 - index * 0.035)
            center = (x + direction * length * 0.38, y)
            angle = direction * 54
            draw_leaf(overlay, center, length, angle, rgba)
    image.alpha_composite(overlay)


def make_background(config: dict[str, Any], width: int, height: int) -> Any:
    background = config.get("background", {})
    top = hex_to_rgb(background.get("top_color", "#6F7F5E"))
    bottom = hex_to_rgb(background.get("bottom_color", "#536649"))
    image = draw_vertical_gradient(width, height, top, bottom).convert("RGBA")
    image = apply_vignette(image.convert("RGB"), float(background.get("vignette_strength", 0.12))).convert("RGBA")
    texture_color = hex_to_rgb(background.get("texture_color", "#D8E0CE"))
    contrast = float(background.get("texture_contrast", 0.045))
    draw_wave_texture(image, texture_color, contrast)
    draw_wheat(image, background.get("wheat", {}), texture_color, contrast)
    return image


def draw_centered_text(draw: Any, xy: tuple[float, float], text: str, font: Any, fill: tuple[int, int, int, int]) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text((xy[0] - width / 2, xy[1] - height / 2), text, font=font, fill=fill)


def paste_logo(image: Any, logo_path: Path | None, y: int, max_width: int) -> int:
    if not logo_path:
        return y
    if not logo_path.exists():
        raise SystemExit(f"Logo not found: {logo_path}")
    logo = Image.open(logo_path).convert("RGBA")
    scale = min(max_width / logo.width, 1.0)
    logo = logo.resize((int(logo.width * scale), int(logo.height * scale)), Image.Resampling.LANCZOS)
    x = (image.width - logo.width) // 2
    image.alpha_composite(logo, (x, y))
    return y + logo.height


def render_card(card: dict[str, Any], config: dict[str, Any], base_dir: Path, output_dir: Path | None) -> Path:
    width = int(config.get("width", 3600))
    height = int(config.get("height", 2160))
    image = make_background(config, width, height)
    draw = ImageDraw.Draw(image)

    layout = config.get("layout", {})
    logo_path = resolve_path(card.get("logo") or config.get("logo"), base_dir)
    logo_y = int(height * float(layout.get("logo_y", 0.27)))
    logo_width = int(width * float(layout.get("logo_width", 0.34)))
    logo_bottom = paste_logo(image, logo_path, logo_y, logo_width)

    title_font = find_font(int(height * float(layout.get("title_size", 0.078))), bold=True)
    subtitle_font = find_font(int(height * float(layout.get("subtitle_size", 0.032))), bold=False)
    title_y = int(height * float(card.get("title_y", layout.get("title_y", 0.55))))
    subtitle_y = int(height * float(card.get("subtitle_y", layout.get("subtitle_y", 0.64))))
    title_color = (*hex_to_rgb(card.get("title_color", config.get("title_color", "#FFFFFF"))), 255)
    subtitle_color = (*hex_to_rgb(card.get("subtitle_color", config.get("subtitle_color", "#E8ECE2"))), 230)

    title = str(card.get("title", "")).strip()
    subtitle = str(card.get("subtitle", "")).strip()
    if title:
        draw_centered_text(draw, (width / 2, title_y), title, title_font, title_color)
    if subtitle:
        draw_centered_text(draw, (width / 2, subtitle_y), subtitle, subtitle_font, subtitle_color)

    output = resolve_path(card.get("output"), base_dir)
    if output_dir:
        output = output_dir / (output.name if output else f"{card.get('name', 'card')}.png")
    if not output:
        output = base_dir / f"{card.get('name', 'card')}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs: dict[str, Any] = {}
    if output.suffix.lower() in {".jpg", ".jpeg"}:
        save_kwargs["quality"] = 95
    image.convert("RGB").save(output, **save_kwargs)
    print(f"Rendered {card.get('name', 'card')}: {output}")
    return output


def load_config(path: Path | None) -> tuple[dict[str, Any], Path]:
    if path:
        expanded = path.expanduser()
        data = json.loads(expanded.read_text())
        return data, expanded.parent
    return {"cards": []}, Path.cwd()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="JSON style/config file")
    parser.add_argument("--output-dir", type=Path, help="Override output directory for all cards")
    parser.add_argument("--title", help="Single-card title when not using config cards")
    parser.add_argument("--subtitle", help="Single-card subtitle when not using config cards")
    parser.add_argument("--logo", help="Logo path for a single card")
    parser.add_argument("--output", type=Path, help="Single-card output path")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and list outputs without rendering")
    args = parser.parse_args()

    config, base_dir = load_config(args.config)
    cards = list(config.get("cards") or [])
    if args.title or args.subtitle or args.output:
        cards.append(
            {
                "name": "card",
                "title": args.title or "",
                "subtitle": args.subtitle or "",
                "logo": args.logo,
                "output": str(args.output or "title-card.png"),
            }
        )
    if not cards:
        raise SystemExit("No cards to render. Provide --config with cards or --title/--output.")

    output_dir = args.output_dir.expanduser() if args.output_dir else None
    for card in cards:
        output = resolve_path(card.get("output"), base_dir)
        if output_dir:
            output = output_dir / (output.name if output else f"{card.get('name', 'card')}.png")
        if args.dry_run:
            print(f"Would render {card.get('name', 'card')} -> {output}")
            continue
        render_card(card, config, base_dir, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
