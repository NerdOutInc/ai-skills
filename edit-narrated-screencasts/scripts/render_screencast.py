#!/usr/bin/env python3
"""Render a narrated screencast from a JSON edit spec."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "preview": {
        "video_codec": "libx264",
        "preset": "veryfast",
        "crf": 28,
        "scale_width": 1280,
        "audio_codec": "aac",
        "audio_bitrate": "128k",
        "movflags_faststart": True,
    },
    "hq": {
        "video_codec": "libx264",
        "preset": "slow",
        "crf": 18,
        "audio_codec": "copy",
        "movflags_faststart": True,
    },
}

TIMING_TOLERANCE = 1e-6
UNEXPANDED_POSIX_VAR_PATTERN = re.compile(r"(?<!\\)\$(?:\{[A-Za-z_][A-Za-z0-9_]*\}|[A-Za-z_][A-Za-z0-9_]*)")
UNEXPANDED_WINDOWS_VAR_PATTERN = re.compile(r"%[A-Za-z_][A-Za-z0-9_]*%")


def detect_audio_codec(path: Path) -> str | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=nk=1:nw=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    return result.stdout.strip() or None


def detect_video_size(path: Path) -> tuple[int, int] | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.exists():
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0:s=x",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    raw = result.stdout.strip()
    if "x" not in raw:
        return None
    width_text, height_text = raw.split("x", 1)
    try:
        width = int(width_text)
        height = int(height_text)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def parse_frame_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        rate = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    if rate <= 0:
        return None
    return float(rate)


def detect_video_fps(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.exists():
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=avg_frame_rate,r_frame_rate",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    streams = data.get("streams") or []
    if not streams:
        return None
    stream = streams[0]
    return parse_frame_rate(stream.get("avg_frame_rate")) or parse_frame_rate(stream.get("r_frame_rate"))


def ensure_timeline_defaults(spec: dict[str, Any], source_video: Path | None) -> None:
    timeline = spec.setdefault("timeline", {})
    width = timeline.get("width")
    height = timeline.get("height")
    if not source_video:
        return

    if width is None or height is None:
        detected_size = detect_video_size(source_video)
        if detected_size:
            detected_width, detected_height = detected_size
            if width is None:
                timeline["width"] = detected_width
            if height is None:
                timeline["height"] = detected_height

    if "fps" not in timeline or timeline.get("fps") is None:
        detected_fps = detect_video_fps(source_video)
        if detected_fps:
            timeline["fps"] = detected_fps


def resolve_path(value: Any, base: Path, label: str = "path") -> Path | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise SystemExit(f"{label} must be a string path")
    expanded = os.path.expandvars(value)
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = base / path
    return path


def has_unexpanded_env_var(path: Path) -> bool:
    text = str(path)
    return bool(UNEXPANDED_POSIX_VAR_PATTERN.search(text) or UNEXPANDED_WINDOWS_VAR_PATTERN.search(text))


def require_file(path: Path | None, label: str, dry_run: bool) -> None:
    if not path:
        raise SystemExit(f"Missing required path: {label}")
    if not dry_run and not path.exists():
        raise SystemExit(f"{label} not found: {path}")


def seconds(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or value is None:
        raise SystemExit(f"{label} must be a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{label} must be a number") from exc
    if not math.isfinite(result):
        raise SystemExit(f"{label} must be finite")
    if positive:
        if result <= 0:
            raise SystemExit(f"{label} must be greater than 0")
    elif result < 0:
        raise SystemExit(f"{label} must be non-negative")
    return result


def integer(value: Any, label: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or value is None:
        raise SystemExit(f"{label} must be an integer")
    try:
        as_float = float(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{label} must be an integer") from exc
    try:
        result = int(as_float)
    except (OverflowError, ValueError) as exc:
        raise SystemExit(f"{label} must be an integer") from exc
    if result != as_float:
        raise SystemExit(f"{label} must be an integer")
    if positive and result <= 0:
        raise SystemExit(f"{label} must be greater than 0")
    return result


def fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def validate_profile_name(spec: dict[str, Any], name: str) -> None:
    spec_profiles = spec.get("profiles") or {}
    if name not in DEFAULT_PROFILES and name not in spec_profiles:
        known = sorted(set(DEFAULT_PROFILES) | set(spec_profiles))
        raise SystemExit(f"Unknown profile '{name}'. Known profiles: {', '.join(known)}")


def normalized_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def reject_output_overwriting_inputs(output: Path, inputs: list[tuple[str, Path | None]]) -> None:
    output_path = normalized_path(output)
    for label, input_path in inputs:
        if input_path and output_path == normalized_path(input_path):
            raise SystemExit(f"Output path must not overwrite {label}: {output}")


class RenderBuilder:
    def __init__(self, spec: dict[str, Any], base_dir: Path, profile: dict[str, Any], dry_run: bool):
        self.spec = spec
        self.base_dir = base_dir
        self.profile = profile
        self.dry_run = dry_run
        self.input_args: list[str] = []
        self.filters: list[str] = []
        self.input_count = 0
        self.image_inputs: dict[tuple[str, float | None], int] = {}

    def add_input(self, path: Path, *, loop: bool = False, duration: float | None = None) -> int:
        key = (str(path), duration if loop else None)
        if loop and key in self.image_inputs:
            return self.image_inputs[key]
        if loop:
            self.input_args.extend(["-loop", "1"])
            if duration is not None:
                self.input_args.extend(["-t", fmt(duration)])
        self.input_args.extend(["-i", str(path)])
        index = self.input_count
        self.input_count += 1
        if loop:
            self.image_inputs[key] = index
        return index

    def normalize_video(self, label: str) -> str:
        timeline = self.spec.get("timeline", {})
        width = timeline.get("width")
        height = timeline.get("height")
        if width is not None or height is not None:
            if width is None or height is None:
                raise SystemExit("timeline.width and timeline.height must be provided together")
            w = integer(width, "timeline.width", positive=True)
            h = integer(height, "timeline.height", positive=True)
            return (
                f"{label}scale={w}:{h}:"
                "force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
            )
        return label

    def make_body(self, video_index: int) -> tuple[str, float]:
        timeline = self.spec.get("timeline", {})
        fps = seconds(timeline.get("fps", 60), "timeline.fps", positive=True)
        segments = timeline.get("segments") or []
        if not segments:
            raise SystemExit("timeline.segments must contain at least one segment")

        labels: list[str] = []
        total_duration = 0.0
        for index, segment in enumerate(segments):
            kind = segment.get("type", "video")
            out_label = f"vseg{index}"
            if kind == "video":
                start = seconds(segment.get("start"), f"segments[{index}].start")
                end = seconds(segment.get("end"), f"segments[{index}].end")
                if end <= start:
                    raise SystemExit(f"segments[{index}].end must be greater than start")
                multiplier = segment.get("setpts_multiplier")
                speed_value = segment.get("speed")
                if multiplier is not None and speed_value is not None:
                    raise SystemExit(
                        f"segments[{index}] must provide either 'speed' or 'setpts_multiplier', not both"
                    )
                if multiplier is None:
                    speed = seconds(speed_value if speed_value is not None else 1, f"segments[{index}].speed", positive=True)
                    multiplier = 1 / speed
                multiplier = seconds(multiplier, f"segments[{index}].setpts_multiplier", positive=True)
                pad_after = seconds(segment.get("clone_pad_after", 0), f"segments[{index}].clone_pad_after")
                chain = (
                    f"[{video_index}:v]"
                    f"trim=start={fmt(start)}:end={fmt(end)},"
                    f"setpts=(PTS-STARTPTS)*{fmt(multiplier)},"
                    f"fps={fmt(fps)},settb=AVTB,format=rgba,"
                )
                chain = self.normalize_video(chain)
                if pad_after:
                    chain += f"tpad=stop_mode=clone:stop_duration={fmt(pad_after)},"
                chain = chain.rstrip(",") + f"[{out_label}]"
                self.filters.append(chain)
                total_duration += (end - start) * multiplier + pad_after
            elif kind == "freeze":
                path = resolve_path(segment.get("path"), self.base_dir, f"segments[{index}].path")
                duration = seconds(segment.get("duration"), f"segments[{index}].duration", positive=True)
                require_file(path, f"segments[{index}].path", self.dry_run)
                image_index = self.add_input(path, loop=True, duration=duration)
                chain = (
                    f"[{image_index}:v]"
                    f"trim=duration={fmt(duration)},setpts=PTS-STARTPTS,"
                    f"fps={fmt(fps)},settb=AVTB,format=rgba,"
                )
                chain = self.normalize_video(chain).rstrip(",") + f"[{out_label}]"
                self.filters.append(chain)
                total_duration += duration
            else:
                raise SystemExit(f"Unsupported segment type: {kind}")
            labels.append(f"[{out_label}]")

        body_label = "vbody"
        self.filters.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[{body_label}]")
        return body_label, total_duration

    def make_card(self, card: dict[str, Any], name: str) -> tuple[str, float, float]:
        timeline = self.spec.get("timeline", {})
        fps = seconds(timeline.get("fps", 60), "timeline.fps", positive=True)
        path = resolve_path(card.get("path"), self.base_dir, f"{name}.path")
        duration = seconds(card.get("duration"), f"{name}.duration", positive=True)
        fade = seconds(card.get("fade_duration", 1), f"{name}.fade_duration")
        if fade > duration:
            raise SystemExit(
                f"{name}.fade_duration ({fmt(fade)}) must be <= {name}.duration ({fmt(duration)})"
            )
        require_file(path, f"{name}.path", self.dry_run)
        image_index = self.add_input(path, loop=True, duration=duration)
        label = f"v{name}"
        chain = (
            f"[{image_index}:v]"
            f"trim=duration={fmt(duration)},setpts=PTS-STARTPTS,"
            f"fps={fmt(fps)},settb=AVTB,format=rgba,"
        )
        chain = self.normalize_video(chain).rstrip(",") + f"[{label}]"
        self.filters.append(chain)
        return label, duration, fade

    def add_intro_outro(self, body_label: str, body_duration: float) -> tuple[str, float]:
        timeline = self.spec.get("timeline", {})
        current_label = body_label
        current_duration = body_duration

        intro = timeline.get("intro")
        if intro:
            intro_label, intro_duration, intro_fade = self.make_card(intro, "intro")
            offset = seconds(intro.get("offset", intro_duration - intro_fade), "intro.offset")
            max_offset = intro_duration - intro_fade
            if offset - max_offset > TIMING_TOLERANCE:
                raise SystemExit(
                    f"intro.offset ({fmt(offset)}) must be <= intro.duration - intro.fade_duration ({fmt(max_offset)})"
                )
            next_label = "vafterintro"
            self.filters.append(
                f"[{intro_label}][{current_label}]"
                f"xfade=transition={intro.get('transition', 'fade')}:"
                f"duration={fmt(intro_fade)}:offset={fmt(offset)}[{next_label}]"
            )
            current_label = next_label
            # xfade output length = offset + input2_duration (input2 is the body)
            current_duration = offset + current_duration

        outro = timeline.get("outro")
        if outro:
            outro_label, outro_duration, outro_fade = self.make_card(outro, "outro")
            offset = seconds(outro.get("offset", current_duration - outro_fade), "outro.offset")
            max_offset = current_duration - outro_fade
            if offset - max_offset > TIMING_TOLERANCE:
                raise SystemExit(
                    f"outro.offset ({fmt(offset)}) must be <= preceding-content duration - outro.fade_duration ({fmt(max_offset)})"
                )
            next_label = "vafteroutro"
            self.filters.append(
                f"[{current_label}][{outro_label}]"
                f"xfade=transition={outro.get('transition', 'fade')}:"
                f"duration={fmt(outro_fade)}:offset={fmt(offset)}[{next_label}]"
            )
            current_label = next_label
            current_duration = offset + outro_duration

        return current_label, current_duration

    def add_overlays(self, input_label: str) -> str:
        label = input_label
        overlays = self.spec.get("timeline", {}).get("overlays") or []
        for index, overlay in enumerate(overlays):
            path = resolve_path(overlay.get("path"), self.base_dir, f"overlays[{index}].path")
            require_file(path, f"overlays[{index}].path", self.dry_run)
            image_index = self.add_input(path, loop=True)
            overlay_label = f"overlay{index}"
            self.filters.append(f"[{image_index}:v]setpts=PTS-STARTPTS,format=rgba[{overlay_label}]")
            next_label = f"voverlay{index}"
            x = integer(overlay.get("x", 0), f"overlays[{index}].x")
            y = integer(overlay.get("y", 0), f"overlays[{index}].y")
            start = seconds(overlay.get("start", 0), f"overlays[{index}].start")
            end = seconds(overlay.get("end"), f"overlays[{index}].end")
            if end <= start:
                raise SystemExit(f"overlays[{index}].end must be greater than start")
            self.filters.append(
                f"[{label}][{overlay_label}]"
                f"overlay={x}:{y}:enable='between(t,{fmt(start)},{fmt(end)})':"
                f"eof_action=pass[{next_label}]"
            )
            label = next_label
        return label

    def finalize_video(self, input_label: str) -> str:
        label = input_label
        filters: list[str] = []
        scale_width = self.profile.get("scale_width")
        if scale_width is not None:
            filters.append(f"scale={integer(scale_width, 'profile.scale_width', positive=True)}:-2")
        filters.append("format=yuv420p")
        output_label = "vfinal"
        self.filters.append(f"[{label}]{','.join(filters)}[{output_label}]")
        return output_label


def merged_profile(spec: dict[str, Any], name: str) -> dict[str, Any]:
    validate_profile_name(spec, name)
    spec_profiles = spec.get("profiles") or {}
    profile = dict(DEFAULT_PROFILES.get(name, {}))
    profile.update(spec_profiles.get(name, {}))
    return profile


def build_command(spec: dict[str, Any], base_dir: Path, profile_name: str, output_override: Path | None, dry_run: bool) -> list[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        if not dry_run:
            raise SystemExit("ffmpeg was not found. Install ffmpeg first.")
        ffmpeg = "ffmpeg"

    profile = merged_profile(spec, profile_name)
    builder = RenderBuilder(spec, base_dir, profile, dry_run)

    inputs = spec.get("inputs", {})
    source_video = resolve_path(inputs.get("video"), base_dir, "inputs.video")
    source_audio = resolve_path(inputs.get("audio"), base_dir, "inputs.audio")
    require_file(source_video, "inputs.video", dry_run)
    ensure_timeline_defaults(spec, source_video)
    video_index = builder.add_input(source_video)

    audio_index: int | None = None
    if source_audio:
        require_file(source_audio, "inputs.audio", dry_run)
        audio_index = builder.add_input(source_audio)

    body_label, body_duration = builder.make_body(video_index)
    composite_label, _ = builder.add_intro_outro(body_label, body_duration)
    overlay_label = builder.add_overlays(composite_label)
    final_label = builder.finalize_video(overlay_label)

    output = output_override or resolve_path(spec.get("output"), base_dir, "spec.output")
    if not output:
        raise SystemExit("Provide spec.output or --output")
    reject_output_overwriting_inputs(output, [("inputs.video", source_video), ("inputs.audio", source_audio)])
    if not dry_run and has_unexpanded_env_var(output):
        raise SystemExit(f"Output path contains an unset environment variable: {output}")
    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [ffmpeg, "-y", *builder.input_args, "-filter_complex", ";".join(builder.filters)]
    cmd.extend(["-map", f"[{final_label}]"])
    if audio_index is not None:
        cmd.extend(["-map", f"{audio_index}:a:0"])

    cmd.extend(["-c:v", str(profile.get("video_codec", "libx264"))])
    if profile.get("preset"):
        cmd.extend(["-preset", str(profile["preset"])])
    if profile.get("crf") is not None:
        cmd.extend(["-crf", str(profile["crf"])])
    fps = spec.get("timeline", {}).get("fps")
    if fps:
        cmd.extend(["-r", fmt(seconds(fps, "timeline.fps"))])

    if audio_index is not None:
        audio_codec = str(profile.get("audio_codec", "copy"))
        audio_bitrate = profile.get("audio_bitrate")
        if audio_codec == "copy" and source_audio and source_audio.exists():
            detected = detect_audio_codec(source_audio)
            if detected and detected != "aac":
                print(
                    f"# Audio is {detected}, not AAC; switching from copy to aac for MP4 compatibility.",
                    file=sys.stderr,
                )
                audio_codec = "aac"
                if not audio_bitrate:
                    audio_bitrate = "192k"
        cmd.extend(["-c:a", audio_codec])
        if audio_codec != "copy" and audio_bitrate:
            cmd.extend(["-b:a", str(audio_bitrate)])

    if profile.get("movflags_faststart", True):
        cmd.extend(["-movflags", "+faststart"])
    if profile.get("shortest", True):
        cmd.append("-shortest")
    if profile.get("limit_duration"):
        cmd.extend(["-t", fmt(seconds(profile["limit_duration"], "profile.limit_duration"))])

    cmd.append(str(output))
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="JSON edit spec")
    parser.add_argument("--profile", default="preview", help="Render profile from built-ins or spec.profiles")
    parser.add_argument("--output", type=Path, help="Override output path")
    parser.add_argument("--limit-duration", type=float, help="Temporary output duration cap")
    parser.add_argument("--dry-run", action="store_true", help="Print command without running ffmpeg")
    args = parser.parse_args()

    spec_path = args.spec.expanduser()
    try:
        spec_text = spec_path.read_text()
    except OSError as exc:
        raise SystemExit(f"Could not read spec {spec_path}: {exc}") from exc
    try:
        spec = json.loads(spec_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Invalid JSON in spec {spec_path} (line {exc.lineno}, col {exc.colno}): {exc.msg}"
        ) from exc
    if args.limit_duration is not None:
        validate_profile_name(spec, args.profile)
        spec.setdefault("profiles", {}).setdefault(args.profile, {})["limit_duration"] = args.limit_duration

    output = resolve_path(str(args.output), spec_path.parent) if args.output else None
    cmd = build_command(spec, spec_path.parent, args.profile, output, args.dry_run)
    print(shlex.join(cmd), flush=True)
    if args.dry_run:
        return 0
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ffmpeg failed with exit code {exc.returncode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
