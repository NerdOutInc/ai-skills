#!/usr/bin/env python3
"""Analyze macOS screencast frames with Apple Vision and write screen events."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import platform
import re
import shlex
import shutil
import statistics
import subprocess
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


SCHEMA = "nerdout.screen_events.v1"
END_FRAME_MARGIN_SECONDS = 0.25


@dataclass
class Frame:
    id: str
    time: float
    path: Path
    role: str = "anchor"


@dataclass
class DiffPoint:
    time: float
    score: float
    previous_time: float


@dataclass
class HoldSpan:
    start: float
    end: float
    mean_score: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def mid(self) -> float:
        return self.start + self.duration / 2.0


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def format_cmd(cmd: list[str | Path]) -> str:
    return shlex.join(str(part) for part in cmd)


def run(cmd: list[str | Path], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    eprint(f"+ {format_cmd(cmd)}")
    try:
        return subprocess.run(
            [str(part) for part in cmd],
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        detail = ""
        if exc.stderr:
            detail = exc.stderr.strip()
        elif exc.stdout:
            detail = exc.stdout.strip()
        raise SystemExit(detail or f"Command failed: {format_cmd(cmd)}") from exc


def pip_install_command() -> list[str]:
    cmd = [sys.executable, "-m", "pip", "install"]
    if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
        cmd.append("--user")
    cmd.append("pillow")
    return cmd


def pillow_install_hint() -> str:
    return shlex.join(pip_install_command())


def install_pillow(no_install: bool) -> None:
    if no_install:
        raise SystemExit(
            "Pillow is required for screen-event analysis. Install it with:\n"
            f"  {pillow_install_hint()}"
        )
    cmd = pip_install_command()
    eprint(format_cmd(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Automatic Pillow install failed. Install it with:\n"
            f"  {pillow_install_hint()}"
        ) from exc


def load_pillow(no_install: bool):
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat
    except ImportError:
        install_pillow(no_install)
        importlib.invalidate_caches()
        try:
            from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat
        except ImportError as exc:
            raise SystemExit(
                "Pillow was installed, but this Python process still cannot import PIL. "
                "Try rerunning the command."
            ) from exc
    return Image, ImageChops, ImageDraw, ImageFont, ImageStat


def positive_float(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than 0")
    return result


def positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return result


def ensure_macos() -> None:
    if platform.system() != "Darwin":
        raise SystemExit(
            "Screen-event analysis requires macOS because it uses Apple Vision. "
            "Run this helper on macOS with the Command Line Tools installed."
        )


def ensure_command(name: str, install_hint: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(f"{name} was not found. Install it with:\n  {install_hint}")


def ffprobe_json(ffprobe: str, path: Path) -> dict[str, Any]:
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ],
        capture_output=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse ffprobe JSON for {path}: {exc}") from exc


def parse_fraction(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text == "0/0":
        return None
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            denom = float(denominator)
            if denom == 0:
                return None
            return float(numerator) / denom
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def media_summary(ffprobe: str, video: Path) -> dict[str, Any]:
    data = ffprobe_json(ffprobe, video)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    try:
        duration = float(fmt.get("duration"))
    except (TypeError, ValueError):
        duration = None
    if not duration or duration <= 0:
        raise SystemExit(f"Could not determine a positive video duration for {video}")
    return {
        "duration": duration,
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": parse_fraction(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
        "codec": video_stream.get("codec_name"),
    }


def timestamp_label(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:
        whole += 1
        millis = 0
    minutes, sec = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}-{minutes:02d}-{sec:02d}-{millis:03d}"
    return f"{minutes:02d}-{sec:02d}-{millis:03d}"


def scale_filter(width: int | None) -> str | None:
    if not width:
        return None
    return f"scale={width}:-2:flags=fast_bilinear"


def extract_scan_frames(ffmpeg: str, video: Path, output_dir: Path, interval: float, width: int) -> list[Frame]:
    clean_generated_dir(output_dir)
    fps = 1.0 / interval
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        video,
        "-vf",
        f"fps={fps:.6f},scale={width}:-2:flags=fast_bilinear",
        "-q:v",
        "4",
        str(output_dir / "scan_%06d.jpg"),
    ]
    run(cmd)
    frames = []
    for index, path in enumerate(sorted(output_dir.glob("scan_*.jpg")), start=1):
        frames.append(Frame(id=f"s{index:04d}", time=(index - 1) * interval, path=path, role="scan"))
    if len(frames) < 2:
        raise SystemExit("ffmpeg produced fewer than two scan frames; cannot analyze screen events.")
    return frames


def clean_generated_dir(output_dir: Path) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise SystemExit(f"Generated artifact path is not a directory: {output_dir}")
    if output_dir.exists():
        for child in output_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)


def remove_generated_files(paths: list[Path]) -> None:
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            raise SystemExit(f"Generated artifact path is a directory, not a file: {path}")
        path.unlink()


def extract_frame(ffmpeg: str, video: Path, output: Path, time: float, width: int | None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    coarse = max(0.0, time - 5.0)
    fine = time - coarse
    vf = scale_filter(width)
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{coarse:.3f}",
        "-i",
        video,
        "-ss",
        f"{fine:.3f}",
        "-frames:v",
        "1",
    ]
    if vf:
        cmd.extend(["-vf", vf])
    cmd.extend(["-q:v", "2", "-update", "1", output])
    run(cmd)


def frame_diff(frame_a: Path, frame_b: Path, Image, ImageChops, ImageStat) -> float:
    with Image.open(frame_a) as opened_a:
        image_a = opened_a.convert("RGB")
    with Image.open(frame_b) as opened_b:
        image_b = opened_b.convert("RGB")
    if image_a.size != image_b.size:
        image_b = image_b.resize(image_a.size)
    diff = ImageChops.difference(image_a, image_b)
    stat = ImageStat.Stat(diff)
    return float(sum(stat.mean[:3]) / (3.0 * 255.0))


def median_mad(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    median = statistics.median(values)
    deviations = [abs(value - median) for value in values]
    return float(median), float(statistics.median(deviations))


def consecutive_diffs(frames: list[Frame], Image, ImageChops, ImageStat) -> list[DiffPoint]:
    points = []
    for previous, current in zip(frames, frames[1:]):
        points.append(
            DiffPoint(
                time=current.time,
                previous_time=previous.time,
                score=frame_diff(previous.path, current.path, Image, ImageChops, ImageStat),
            )
        )
    return points


def group_by_gap(points: list[DiffPoint], min_gap: float) -> list[DiffPoint]:
    if not points:
        return []
    groups: list[list[DiffPoint]] = []
    current = [points[0]]
    for point in points[1:]:
        if point.time - current[-1].time <= min_gap:
            current.append(point)
        else:
            groups.append(current)
            current = [point]
    groups.append(current)
    return [max(group, key=lambda item: item.score) for group in groups]


def detect_scene_candidates(diffs: list[DiffPoint], min_gap: float) -> tuple[list[DiffPoint], float]:
    scores = [point.score for point in diffs]
    median, mad = median_mad(scores)
    threshold = max(0.04, median + 3 * mad)
    peaks = []
    for index, point in enumerate(diffs):
        previous_score = diffs[index - 1].score if index > 0 else -1.0
        next_score = diffs[index + 1].score if index + 1 < len(diffs) else -1.0
        if point.score >= threshold and point.score >= previous_score and point.score >= next_score:
            peaks.append(point)
    return group_by_gap(peaks, min_gap), threshold


def detect_stable_holds(diffs: list[DiffPoint], min_duration: float) -> tuple[list[HoldSpan], float]:
    scores = [point.score for point in diffs]
    median, mad = median_mad(scores)
    threshold = max(0.015, median + mad)
    holds = []
    current: list[DiffPoint] = []
    for point in diffs:
        if point.score <= threshold:
            current.append(point)
            continue
        if current:
            append_hold(holds, current, min_duration)
            current = []
    if current:
        append_hold(holds, current, min_duration)
    return holds, threshold


def append_hold(holds: list[HoldSpan], points: list[DiffPoint], min_duration: float) -> None:
    start = points[0].previous_time
    end = points[-1].time
    duration = end - start
    if duration >= min_duration:
        holds.append(
            HoldSpan(
                start=start,
                end=end,
                mean_score=sum(point.score for point in points) / len(points),
            )
        )


def refine_scene_candidate(
    ffmpeg: str,
    video: Path,
    candidate: DiffPoint,
    output_dir: Path,
    duration: float,
    args: argparse.Namespace,
    Image,
    ImageChops,
    ImageStat,
) -> DiffPoint:
    start = max(0.0, candidate.time - args.refine_window)
    end = min(duration, candidate.time + args.refine_window)
    times = []
    value = start
    while value <= end + 0.0001:
        times.append(round(value, 3))
        value += args.refine_step
    frames = []
    for index, time in enumerate(times, start=1):
        frame = output_dir / f"refine_{timestamp_label(candidate.time)}_{index:03d}_{timestamp_label(time)}.jpg"
        extract_frame(ffmpeg, video, frame, time, args.scan_width)
        frames.append(Frame(id=f"r{index:04d}", time=time, path=frame, role="refine"))
    diffs = consecutive_diffs(frames, Image, ImageChops, ImageStat)
    if not diffs:
        return candidate
    best = max(diffs, key=lambda point: point.score)
    return DiffPoint(time=best.time, previous_time=best.previous_time, score=max(candidate.score, best.score))


def time_range(start: float, end: float, step: float) -> list[float]:
    values = []
    value = start
    while value <= end + 0.0001:
        values.append(round(value, 3))
        value += step
    return values


def add_time(times: dict[float, str], time: float, role: str, duration: float) -> None:
    # Avoid the exact container end, where ffmpeg can seek past the last
    # decodable frame.
    max_time = max(0.0, duration - END_FRAME_MARGIN_SECONDS)
    clamped = round(min(max(0.0, time), max_time), 3)
    existing = times.get(clamped)
    if existing and existing != "anchor":
        return
    times[clamped] = role


def required_vision_times(
    duration: float,
    scenes: list[DiffPoint],
    holds: list[HoldSpan],
    args: argparse.Namespace,
) -> dict[float, str]:
    mandatory: dict[float, str] = {}
    for scene in scenes:
        add_time(mandatory, scene.previous_time, "scene_pre", duration)
        add_time(mandatory, scene.time, "scene_change", duration)
        add_time(mandatory, scene.time + args.refine_step, "scene_post", duration)
    for hold in holds:
        add_time(mandatory, hold.start, "hold_start", duration)
        add_time(mandatory, hold.mid, "stable_hold", duration)
        add_time(mandatory, hold.end, "hold_end", duration)
    if len(mandatory) > args.max_vision_frames:
        raise SystemExit(
            f"Selected {len(mandatory)} required Apple Vision frames, which exceeds "
            f"--max-vision-frames={args.max_vision_frames}. Increase --max-vision-frames, "
            "increase --min-event-gap, or increase --min-hold-duration."
        )
    return mandatory


def selected_vision_times(
    duration: float,
    scenes: list[DiffPoint],
    holds: list[HoldSpan],
    args: argparse.Namespace,
) -> dict[float, str]:
    mandatory = required_vision_times(duration, scenes, holds, args)

    anchors: dict[float, str] = {}
    for time in time_range(0.0, duration, args.vision_interval):
        add_time(anchors, time, "anchor", duration)
    anchors = {time: role for time, role in anchors.items() if time not in mandatory}

    slots_left = max(0, args.max_vision_frames - len(mandatory))
    if len(anchors) > slots_left:
        anchor_items = sorted(anchors.items())
        if slots_left <= 0:
            anchors = {}
        else:
            stride = max(1, math.ceil(len(anchor_items) / slots_left))
            anchors = dict(anchor_items[::stride][:slots_left])

    selected = dict(anchors)
    selected.update(mandatory)
    return dict(sorted(selected.items()))


def write_manifest(frames: list[Frame], manifest: Path) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w") as handle:
        for frame in frames:
            handle.write(
                json.dumps(
                    {
                        "id": frame.id,
                        "time": frame.time,
                        "path": str(frame.path),
                        "role": frame.role,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def run_vision(swift: str, helper: Path, manifest: Path, output: Path, ocr_level: str) -> None:
    if not helper.exists():
        raise SystemExit(f"Apple Vision helper not found: {helper}")
    run(
        [
            swift,
            helper,
            "--manifest",
            manifest,
            "--out",
            output,
            "--ocr-level",
            ocr_level,
        ]
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, raw in enumerate(path.read_text().splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            records.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Could not parse JSONL at {path}:{line_number}: {exc}") from exc
    return records


def nearest_record(records: list[dict[str, Any]], time: float) -> dict[str, Any] | None:
    if not records:
        return None
    return min(records, key=lambda record: abs(float(record.get("time", 0.0)) - time))


def text_similarity(left: str, right: str) -> float:
    left = re.sub(r"\s+", " ", left.strip().lower())
    right = re.sub(r"\s+", " ", right.strip().lower())
    if not left and not right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def event_from_record(
    kind: str,
    time: float,
    record: dict[str, Any] | None,
    score: float,
    notes: list[str],
    *,
    end: float | None = None,
    duration: float | None = None,
) -> dict[str, Any]:
    event = {
        "kind": kind,
        "time": round(time, 3),
        "score": round(float(score), 4),
        "frame": record.get("path") if record else None,
        "ocr_text": record.get("ocr_text", "") if record else "",
        "notes": notes,
    }
    if record and record.get("feature_distance_from_previous") is not None:
        event["feature_distance_from_previous"] = record.get("feature_distance_from_previous")
    if end is not None:
        event["end"] = round(end, 3)
    if duration is not None:
        event["duration"] = round(duration, 3)
    return event


def build_events(
    scenes: list[DiffPoint],
    holds: list[HoldSpan],
    records: list[dict[str, Any]],
    args: argparse.Namespace,
    stable_threshold_hint: float,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    usable_records = [record for record in records if not record.get("error")]
    for scene in scenes:
        record = nearest_record(usable_records, scene.time)
        score = scene.score
        feature_distance = record.get("feature_distance_from_previous") if record else None
        if isinstance(feature_distance, (int, float)):
            score = max(score, min(float(feature_distance) / 20.0, 1.0))
        events.append(
            event_from_record(
                "scene_change",
                scene.time,
                record,
                score,
                ["visual change peak", "Apple Vision feature-print analyzed"],
            )
        )

    for hold in holds:
        record = nearest_record(usable_records, hold.mid)
        score = max(
            0.0,
            min(1.0, 1.0 - hold.mean_score / max(stable_threshold_hint, 0.001)),
        )
        events.append(
            event_from_record(
                "stable_hold",
                hold.mid,
                record,
                score,
                ["low visual change span", "candidate loading/wait/freeze-frame region"],
                end=hold.end,
                duration=hold.duration,
            )
        )
        events[-1]["start"] = round(hold.start, 3)

    for previous, current in zip(usable_records, usable_records[1:]):
        previous_text = str(previous.get("ocr_text") or "")
        current_text = str(current.get("ocr_text") or "")
        if not previous_text and not current_text:
            continue
        ratio = text_similarity(previous_text, current_text)
        if ratio < args.ocr_change_threshold:
            events.append(
                event_from_record(
                    "ocr_change",
                    float(current["time"]),
                    current,
                    1.0 - ratio,
                    ["visible text changed between Apple Vision OCR samples"],
                )
            )

    for record in usable_records:
        role = str(record.get("role") or "")
        if role == "anchor":
            events.append(
                event_from_record(
                    "anchor",
                    float(record["time"]),
                    record,
                    0.0,
                    ["regular Apple Vision sample for agent review"],
                )
            )

    events.sort(key=lambda item: (float(item["time"]), item["kind"]))
    for index, event in enumerate(events, start=1):
        event["id"] = f"e{index:03d}"
    return events


def make_contact_sheet(events: list[dict[str, Any]], output: Path, width: int, cols: int, Image, ImageDraw, ImageFont) -> None:
    frame_events = [event for event in events if event.get("frame") and Path(str(event["frame"])).exists()]
    if not frame_events:
        return
    frame_events = frame_events[:120]
    images = []
    for event in frame_events:
        with Image.open(str(event["frame"])) as source:
            image = source.convert("RGB")
        ratio = width / image.width
        images.append((image.resize((width, int(image.height * ratio))), event))

    label_height = 46
    rows = math.ceil(len(images) / cols)
    cell_height = max(image.height for image, _ in images) + label_height
    sheet = Image.new("RGB", (cols * width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, (image, event) in enumerate(images):
        col = index % cols
        row = index // cols
        x = col * width
        y = row * cell_height
        sheet.paste(image, (x, y + label_height))
        label = f"{event['id']} {event['kind']} {float(event['time']):.3f}s"
        draw.text((x + 8, y + 8), label, fill=(32, 32, 32), font=font)
        text = str(event.get("ocr_text") or "")[:70]
        if text:
            draw.text((x + 8, y + 25), text, fill=(80, 80, 80), font=font)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True, help="Source screencast video")
    parser.add_argument("--out", type=Path, required=True, help="Output directory for screen analysis artifacts")
    parser.add_argument("--scan-interval", type=positive_float, default=1.0)
    parser.add_argument("--vision-interval", type=positive_float, default=5.0)
    parser.add_argument("--refine-window", type=positive_float, default=1.5)
    parser.add_argument("--refine-step", type=positive_float, default=0.5)
    parser.add_argument("--min-hold-duration", type=positive_float, default=4.0)
    parser.add_argument("--min-event-gap", type=positive_float, default=1.5)
    parser.add_argument("--max-vision-frames", type=positive_int, default=180)
    parser.add_argument("--ocr-level", choices=("fast", "accurate"), default="fast")
    parser.add_argument("--scan-width", type=positive_int, default=320)
    parser.add_argument("--vision-width", type=positive_int, default=1920)
    parser.add_argument("--sheet-width", type=positive_int, default=480)
    parser.add_argument("--cols", type=positive_int, default=3)
    parser.add_argument("--ocr-change-threshold", type=positive_float, default=0.70)
    parser.add_argument("--no-install", action="store_true", help="Do not install Pillow automatically")
    args = parser.parse_args()

    ensure_macos()
    video = args.video.expanduser()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")

    out_dir = args.out.expanduser()
    if out_dir.exists() and not out_dir.is_dir():
        raise SystemExit(f"--out must be a directory path, not a file: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg = ensure_command("ffmpeg", "brew install ffmpeg")
    ffprobe = ensure_command("ffprobe", "brew install ffmpeg")
    swift = ensure_command("swift", "xcode-select --install")
    Image, ImageChops, ImageDraw, ImageFont, ImageStat = load_pillow(args.no_install)

    summary = media_summary(ffprobe, video)
    duration = float(summary["duration"])
    scan_dir = out_dir / "scan-frames"
    refine_dir = out_dir / "refine-frames"
    frame_dir = out_dir / "frames"
    remove_generated_files(
        [
            out_dir / "frames.jsonl",
            out_dir / "vision-frames.jsonl",
            out_dir / "screen-events.json",
            out_dir / "screen-events-contact-sheet.jpg",
        ]
    )
    clean_generated_dir(refine_dir)
    clean_generated_dir(frame_dir)
    scan_frames = extract_scan_frames(ffmpeg, video, scan_dir, args.scan_interval, args.scan_width)
    diffs = consecutive_diffs(scan_frames, Image, ImageChops, ImageStat)
    scene_candidates, scene_threshold = detect_scene_candidates(diffs, args.min_event_gap)
    holds, stable_threshold = detect_stable_holds(diffs, args.min_hold_duration)
    # Fail before costly refinement if required event/hold samples already exceed the cap.
    required_vision_times(duration, scene_candidates, holds, args)

    refined_scenes = [
        refine_scene_candidate(
            ffmpeg,
            video,
            candidate,
            refine_dir,
            duration,
            args,
            Image,
            ImageChops,
            ImageStat,
        )
        for candidate in scene_candidates
    ]
    refined_scenes = group_by_gap(sorted(refined_scenes, key=lambda item: item.time), args.min_event_gap)

    selected_times = selected_vision_times(duration, refined_scenes, holds, args)
    frames: list[Frame] = []
    for index, (time, role) in enumerate(selected_times.items(), start=1):
        frame = frame_dir / f"frame_{index:04d}_{timestamp_label(time)}_{role}.jpg"
        extract_frame(ffmpeg, video, frame, time, args.vision_width)
        frames.append(Frame(id=f"f{index:04d}", time=time, path=frame, role=role))

    manifest = out_dir / "frames.jsonl"
    vision_output = out_dir / "vision-frames.jsonl"
    write_manifest(frames, manifest)
    helper = Path(__file__).with_name("vision_frame_analysis.swift")
    run_vision(swift, helper, manifest, vision_output, args.ocr_level)
    records = read_jsonl(vision_output)
    by_id = {frame.id: frame.role for frame in frames}
    for record in records:
        record["role"] = by_id.get(str(record.get("id")), "anchor")

    events = build_events(refined_scenes, holds, records, args, stable_threshold)
    contact_sheet = out_dir / "screen-events-contact-sheet.jpg"
    make_contact_sheet(events, contact_sheet, args.sheet_width, args.cols, Image, ImageDraw, ImageFont)

    payload = {
        "schema": SCHEMA,
        "source_video": str(video),
        "duration": duration,
        "media": summary,
        "analysis": {
            "platform": "macOS",
            "engine": "Apple Vision",
            "ocr_level": args.ocr_level,
            "scan_interval": args.scan_interval,
            "vision_interval": args.vision_interval,
            "scene_threshold": scene_threshold,
            "stable_threshold": stable_threshold,
            "max_vision_frames": args.max_vision_frames,
            "scan_frame_count": len(scan_frames),
            "vision_frame_count": len(frames),
        },
        "artifacts": {
            "frames_manifest": str(manifest),
            "vision_frames_jsonl": str(vision_output),
            "contact_sheet": str(contact_sheet) if contact_sheet.exists() else None,
            "scan_frames_dir": str(scan_dir),
            "frames_dir": str(frame_dir),
        },
        "events": events,
        "warnings": [],
    }
    output = out_dir / "screen-events.json"
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote screen events: {output}")
    print(f"Wrote Vision frame observations: {vision_output}")
    if contact_sheet.exists():
        print(f"Wrote contact sheet: {contact_sheet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
