#!/usr/bin/env python3
"""Extract timestamped review frames and an optional contact sheet."""

from __future__ import annotations

import argparse
import importlib
import math
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def install_pillow(no_install: bool) -> None:
    if no_install:
        raise SystemExit(
            "Pillow is required for contact sheets. Install it with:\n"
            "  python3 -m pip install --user pillow\n"
            "Or use --no-sheet to skip contact sheet generation."
        )
    cmd = [sys.executable, "-m", "pip", "install", "--user", "pillow"]
    print(shlex.join(cmd), file=sys.stderr, flush=True)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Automatic Pillow install failed. Install it with:\n"
            "  python3 -m pip install --user pillow\n"
            "Or use --no-sheet to skip contact sheet generation."
        ) from exc


def load_pillow(no_install: bool):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        install_pillow(no_install)
        importlib.invalidate_caches()
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise SystemExit(
                "Pillow was installed, but this Python process still cannot import PIL. "
                "Try rerunning the command."
            ) from exc
    return Image, ImageDraw, ImageFont


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
    result = hours * 3600 + minutes * 60 + seconds
    if not math.isfinite(result):
        raise ValueError(f"timestamp must be finite: {value}")
    if result < 0:
        raise ValueError(f"timestamp must be non-negative: {value}")
    return result


def timestamp_label(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:
        millis = 0
        whole += 1
    minutes, sec = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}-{minutes:02d}-{sec:02d}-{millis:03d}"
    return f"{minutes:02d}-{sec:02d}-{millis:03d}"


def positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return result


def load_timestamps(args: argparse.Namespace) -> list[float]:
    values: list[str] = []
    values.extend(args.timestamps or [])
    if args.timestamps_file:
        timestamps_file = args.timestamps_file.expanduser()
        if not timestamps_file.exists():
            raise SystemExit(f"Timestamps file not found: {timestamps_file}")
        for raw in timestamps_file.read_text().splitlines():
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
    print(shlex.join(cmd), flush=True)
    if dry_run:
        return
    try:
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        if not stderr:
            raise SystemExit(f"ffmpeg failed with exit code {exc.returncode}") from exc
        lines = stderr.splitlines()
        if len(lines) > 20:
            lines = lines[-20:]
        snippet = "\n".join(lines)
        if len(snippet) > 4000:
            snippet = snippet[-4000:]
        raise SystemExit(
            f"ffmpeg failed with exit code {exc.returncode}\n\nffmpeg stderr:\n{snippet}"
        ) from exc


def extract_frames(video: Path, output_dir: Path, timestamps: list[float], args: argparse.Namespace) -> list[Path]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        if not args.dry_run:
            raise SystemExit("ffmpeg was not found. Install ffmpeg first.")
        ffmpeg = "ffmpeg"
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    for index, seconds in enumerate(timestamps, start=1):
        label = timestamp_label(seconds)
        frame = output_dir / f"{args.prefix}_{index:03d}_{label}.jpg"
        # Fast-seek to a keyframe near the target, then accurate-seek the
        # remainder so the extracted frame matches the requested timestamp
        # even when the source has long GOPs (common in screen recordings).
        coarse = max(0.0, seconds - 5.0)
        fine = seconds - coarse
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{coarse:.3f}",
            "-i",
            str(video),
            "-ss",
            f"{fine:.3f}",
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


def make_contact_sheet(
    frames: list[Path],
    timestamps: list[float],
    output: Path,
    width: int,
    cols: int,
    no_install: bool,
) -> None:
    Image, ImageDraw, ImageFont = load_pillow(no_install)
    existing_pairs = [(frame, ts) for frame, ts in zip(frames, timestamps) if frame.exists()]
    if not existing_pairs:
        raise SystemExit("No extracted frames exist; cannot build contact sheet.")

    images = []
    for frame, ts in existing_pairs:
        with Image.open(frame) as source:
            image = source.convert("RGB")
        ratio = width / image.width
        images.append((image.resize((width, int(image.height * ratio))), ts))

    label_height = 36
    rows = math.ceil(len(images) / cols)
    cell_height = max(image.height for image, _ in images) + label_height
    sheet = Image.new("RGB", (cols * width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, (image, ts) in enumerate(images):
        col = index % cols
        row = index // cols
        x = col * width
        y = row * cell_height
        sheet.paste(image, (x, y + label_height))
        label = f"{index + 1}: {ts:.3f}s"
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
    parser.add_argument("--sheet-width", type=positive_int, default=640, help="Width of each contact sheet cell")
    parser.add_argument("--cols", type=positive_int, default=3, help="Contact sheet columns")
    parser.add_argument("--no-sheet", action="store_true", help="Skip contact sheet generation")
    parser.add_argument("--no-install", action="store_true", help="Do not install Pillow automatically")
    parser.add_argument("--dry-run", action="store_true", help="Print ffmpeg commands without running them")
    args = parser.parse_args()

    video = args.video.expanduser()
    if not args.dry_run and not video.exists():
        raise SystemExit(f"Video not found: {video}")

    timestamps = load_timestamps(args)
    frames = extract_frames(video, args.output_dir.expanduser(), timestamps, args)
    if not args.no_sheet and not args.dry_run:
        sheet = args.sheet or args.output_dir.expanduser() / "contact-sheet.jpg"
        make_contact_sheet(frames, timestamps, sheet, args.sheet_width, args.cols, args.no_install)
    return 0


if __name__ == "__main__":
    sys.exit(main())
