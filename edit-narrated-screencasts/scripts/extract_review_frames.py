#!/usr/bin/env python3
"""Extract timestamped review frames and an optional contact sheet."""

from __future__ import annotations

import argparse
import math
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def parse_timestamp(value: str) -> float:
    text = value.strip()
    if not text:
        raise ValueError("empty timestamp")
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"invalid timestamp: {value}")
    seconds = float(parts[-1])
    minutes = int(parts[-2])
    hours = int(parts[-3]) if len(parts) == 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def timestamp_label(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    minutes, sec = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}-{minutes:02d}-{sec:02d}-{millis:03d}"
    return f"{minutes:02d}-{sec:02d}-{millis:03d}"


def load_timestamps(args: argparse.Namespace) -> list[float]:
    values: list[str] = []
    values.extend(args.timestamps or [])
    if args.timestamps_file:
        for raw in args.timestamps_file.expanduser().read_text().splitlines():
            clean = raw.split("#", 1)[0].strip()
            if clean:
                values.append(clean.split()[0])
    if not values:
        raise SystemExit("Provide timestamps with --timestamps or --timestamps-file.")
    parsed: list[float] = []
    for value in values:
        try:
            parsed.append(parse_timestamp(value))
        except ValueError as exc:
            raise SystemExit(f"Invalid timestamp '{value}': {exc}") from exc
    return sorted(parsed)


def run_command(cmd: list[str], dry_run: bool) -> None:
    print(shlex.join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def extract_frames(video: Path, output_dir: Path, timestamps: list[float], args: argparse.Namespace) -> list[Path]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg was not found. Install ffmpeg first.")
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    for index, seconds in enumerate(timestamps, start=1):
        label = timestamp_label(seconds)
        frame = output_dir / f"{args.prefix}_{index:03d}_{label}.jpg"
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{seconds:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-update",
            "1",
            str(frame),
        ]
        run_command(cmd, args.dry_run)
        frames.append(frame)
    return frames


def make_contact_sheet(frames: list[Path], timestamps: list[float], output: Path, width: int, cols: int) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit("Pillow is required for contact sheets. Install pillow or use --no-sheet.") from exc

    existing = [frame for frame in frames if frame.exists()]
    if not existing:
        raise SystemExit("No extracted frames exist; cannot build contact sheet.")

    images = []
    for frame in existing:
        image = Image.open(frame).convert("RGB")
        ratio = width / image.width
        images.append(image.resize((width, int(image.height * ratio))))

    label_height = 36
    rows = math.ceil(len(images) / cols)
    cell_height = max(image.height for image in images) + label_height
    sheet = Image.new("RGB", (cols * width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, image in enumerate(images):
        col = index % cols
        row = index // cols
        x = col * width
        y = row * cell_height
        sheet.paste(image, (x, y + label_height))
        label = f"{index + 1}: {timestamps[index]:.3f}s"
        draw.text((x + 10, y + 10), label, fill=(32, 32, 32), font=font)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)
    print(f"Contact sheet: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="Video to sample")
    parser.add_argument("output_dir", type=Path, help="Directory for extracted frames")
    parser.add_argument("--timestamps", nargs="*", help="Timestamps in seconds or HH:MM:SS.mmm")
    parser.add_argument("--timestamps-file", type=Path, help="Text file with one timestamp per line")
    parser.add_argument("--prefix", default="frame", help="Output filename prefix")
    parser.add_argument("--sheet", type=Path, help="Contact sheet path")
    parser.add_argument("--sheet-width", type=int, default=640, help="Width of each contact sheet cell")
    parser.add_argument("--cols", type=int, default=3, help="Contact sheet columns")
    parser.add_argument("--no-sheet", action="store_true", help="Skip contact sheet generation")
    parser.add_argument("--dry-run", action="store_true", help="Print ffmpeg commands without running them")
    args = parser.parse_args()

    video = args.video.expanduser()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")

    timestamps = load_timestamps(args)
    frames = extract_frames(video, args.output_dir.expanduser(), timestamps, args)
    if not args.no_sheet and not args.dry_run:
        sheet = args.sheet or args.output_dir.expanduser() / "contact-sheet.jpg"
        make_contact_sheet(frames, timestamps, sheet, args.sheet_width, args.cols)
    return 0


if __name__ == "__main__":
    sys.exit(main())
