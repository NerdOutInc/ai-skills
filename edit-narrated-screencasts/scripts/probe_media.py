#!/usr/bin/env python3
"""Summarize media metadata with ffprobe."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


def run_ffprobe(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise SystemExit("ffprobe was not found. Install ffmpeg first.")
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    cmd = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.stderr.strip() or f"ffprobe failed for {path}") from exc
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Could not parse ffprobe JSON for {path} (line {exc.lineno}, col {exc.colno}): {exc.msg}"
        ) from exc


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def human_duration(value: Any) -> str:
    seconds = as_float(value)
    if seconds is None:
        return "unknown"
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:
        millis = 0
        whole += 1
    minutes, sec = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{sec:02d}.{millis:03d}"
    return f"{minutes:d}:{sec:02d}.{millis:03d}"


def human_bytes(value: Any) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "unknown"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit = 0
    while size >= 1024 and unit < len(units) - 1:
        size /= 1024
        unit += 1
    return f"{size:.1f} {units[unit]}"


def human_bitrate(value: Any) -> str:
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if rate >= 1_000_000:
        return f"{rate / 1_000_000:.2f} Mbps"
    if rate >= 1_000:
        return f"{rate / 1_000:.1f} kbps"
    return f"{rate:.0f} bps"


def fps_value(stream: dict[str, Any]) -> str:
    raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not raw or raw == "0/0":
        return "unknown"
    try:
        fraction = Fraction(raw)
    except (ValueError, ZeroDivisionError):
        return str(raw)
    return f"{float(fraction):.3f}".rstrip("0").rstrip(".")


def summarize(path: Path, data: dict[str, Any]) -> str:
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]

    lines = [
        f"File: {path}",
        f"  Duration: {human_duration(fmt.get('duration'))}",
        f"  Size: {human_bytes(fmt.get('size'))}",
        f"  Container bitrate: {human_bitrate(fmt.get('bit_rate'))}",
    ]

    for index, stream in enumerate(video, start=1):
        lines.extend(
            [
                f"  Video stream {index}:",
                f"    Codec: {stream.get('codec_name', 'unknown')}",
                f"    Size: {stream.get('width', 'unknown')}x{stream.get('height', 'unknown')}",
                f"    FPS: {fps_value(stream)}",
                f"    Pixel format: {stream.get('pix_fmt', 'unknown')}",
                f"    Bitrate: {human_bitrate(stream.get('bit_rate'))}",
                f"    Frames: {stream.get('nb_frames', 'unknown')}",
            ]
        )

    for index, stream in enumerate(audio, start=1):
        lines.extend(
            [
                f"  Audio stream {index}:",
                f"    Codec: {stream.get('codec_name', 'unknown')}",
                f"    Channels: {stream.get('channels', 'unknown')}",
                f"    Sample rate: {stream.get('sample_rate', 'unknown')} Hz",
                f"    Bitrate: {human_bitrate(stream.get('bit_rate'))}",
            ]
        )

    if video:
        first = video[0]
        width = first.get("width", "source width")
        height = first.get("height", "source height")
        fps = fps_value(first)
        lines.extend(
            [
                "  Suggested output constraints:",
                f"    HQ: keep {width}x{height} at {fps} fps, H.264 CRF 18, preset slow",
                f"    Preview: scale to about 1280px wide, H.264 CRF 28, preset veryfast",
            ]
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Media files to inspect")
    parser.add_argument("--json", action="store_true", help="Print raw ffprobe JSON")
    args = parser.parse_args()

    payload: dict[str, Any] = {}
    for path in args.paths:
        expanded = path.expanduser()
        data = run_ffprobe(expanded)
        payload[str(expanded)] = data
        if args.json:
            continue
        print(summarize(expanded, data))
        print()

    if args.json:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
