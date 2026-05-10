#!/usr/bin/env python3
"""Prepare transcript, screen-event, and timing-map artifacts for a narrated screencast."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


SCHEMA = "nerdout.timing_map.v1"
MEDIA_SCHEMA = "nerdout.media_summary.v1"
TRANSCRIPT_SCHEMA = "nerdout.transcript.v1"
SCREEN_EVENTS_SCHEMA = "nerdout.screen_events.v1"
NEARBY_EVENT_WINDOW_SECONDS = 6.0
LIKELY_RANGE_PADDING_SECONDS = 2.0
MAX_CANDIDATES_PER_ROW = 4
EVENT_PRIORITY = {
    "ocr_change": 0,
    "scene_change": 1,
    "stable_hold": 2,
    "anchor": 3,
}
STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "been",
    "but",
    "can",
    "for",
    "from",
    "have",
    "here",
    "into",
    "now",
    "our",
    "that",
    "the",
    "then",
    "there",
    "this",
    "through",
    "with",
    "you",
    "your",
}
HOMEBREW_BIN_DIRS = (Path("/opt/homebrew/bin"), Path("/usr/local/bin"))


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


def homebrew_executables(name: str) -> list[Path]:
    return [directory / name for directory in HOMEBREW_BIN_DIRS]


def include_homebrew_bin_dirs() -> None:
    path_parts = [part for part in os.environ.get("PATH", "").split(os.pathsep) if part]
    for directory in reversed(HOMEBREW_BIN_DIRS):
        directory_text = str(directory)
        if directory.exists() and directory_text not in path_parts:
            path_parts.insert(0, directory_text)
    os.environ["PATH"] = os.pathsep.join(path_parts)


def find_executable(name: str, extras: list[Path] | None = None) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in extras or []:
        expanded = candidate.expanduser()
        if expanded.exists() and expanded.is_file():
            return str(expanded)
    return None


def find_brew() -> str | None:
    return find_executable("brew", homebrew_executables("brew"))


def can_auto_install() -> bool:
    return platform.system() == "Darwin" and find_brew() is not None


def missing_dependency(name: str, install_cmd: str, no_install: bool) -> SystemExit:
    if no_install:
        return SystemExit(
            f"Missing {name}. Install it with:\n  {install_cmd}\n"
            "Then rerun this command, or rerun without --no-install on macOS with Homebrew."
        )
    return SystemExit(
        f"Missing {name}. Automatic install is only supported on macOS with Homebrew.\n"
        f"Install it with:\n  {install_cmd}"
    )


def ensure_ffmpeg(no_install: bool) -> tuple[str, str]:
    include_homebrew_bin_dirs()
    ffmpeg = find_executable("ffmpeg", homebrew_executables("ffmpeg"))
    ffprobe = find_executable("ffprobe", homebrew_executables("ffprobe"))
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe

    if no_install or not can_auto_install():
        raise missing_dependency("ffmpeg/ffprobe", "brew install ffmpeg", no_install)

    brew = find_brew()
    if not brew:
        raise missing_dependency("ffmpeg/ffprobe", "brew install ffmpeg", no_install)
    run([brew, "install", "ffmpeg"])

    ffmpeg = find_executable("ffmpeg", homebrew_executables("ffmpeg"))
    ffprobe = find_executable("ffprobe", homebrew_executables("ffprobe"))
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe
    raise SystemExit(
        "ffmpeg install completed, but ffmpeg/ffprobe still were not found on PATH "
        "or in common Homebrew bin directories."
    )


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError(f"{value!r} must be greater than 0")
    return parsed


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"{value!r} must be greater than 0")
    return parsed


def resolve_existing_file(path: Path, label: str) -> Path:
    expanded = path.expanduser()
    if not expanded.exists():
        raise SystemExit(f"{label} not found: {expanded}")
    if not expanded.is_file():
        raise SystemExit(f"{label} must be a file: {expanded}")
    return expanded.resolve()


def prepare_output_dir(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.exists() and not expanded.is_dir():
        raise SystemExit(f"--out must be a directory path, not a file: {expanded}")
    expanded.mkdir(parents=True, exist_ok=True)
    return expanded.resolve()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SystemExit(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Could not parse {label} at {path} (line {exc.lineno}, col {exc.colno}): {exc.msg}"
        ) from exc
    except UnicodeDecodeError as exc:
        raise SystemExit(f"Could not decode {label} at {path}: {exc}") from exc
    except OSError as exc:
        raise SystemExit(f"Could not read {label} at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{label} must be a JSON object: {path}")
    return data


def paths_match(actual: Any, expected: Path) -> bool:
    if not isinstance(actual, str) or not actual:
        return False
    try:
        return Path(actual).expanduser().resolve() == expected
    except OSError:
        return str(actual) == str(expected)


def validate_artifact_data(
    *,
    data: dict[str, Any],
    label: str,
    schema: str,
    source_key: str,
    expected_source: Path,
) -> None:
    actual_schema = data.get("schema")
    if actual_schema != schema:
        raise SystemExit(f"{label} has schema {actual_schema!r}, expected {schema!r}.")
    if not paths_match(data.get(source_key), expected_source):
        raise SystemExit(f"{label} was created for {data.get(source_key)!r}, not {str(expected_source)!r}.")


def cached_artifact(
    *,
    path: Path,
    label: str,
    schema: str,
    source_key: str,
    expected_source: Path,
    force: bool,
) -> dict[str, Any] | None:
    if force or not path.exists():
        return None
    try:
        data = load_json(path, label)
    except SystemExit as exc:
        raise SystemExit(f"Existing {label} is malformed. Rerun with --force to regenerate it.\n{exc}") from exc
    try:
        validate_artifact_data(
            data=data,
            label=label,
            schema=schema,
            source_key=source_key,
            expected_source=expected_source,
        )
    except SystemExit as exc:
        raise SystemExit(
            f"Existing {label} does not match this run. Rerun with --force to regenerate it.\n{exc}"
        ) from exc
    eprint(f"Reusing existing {label}: {path}")
    return data


def parse_fraction(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value)
    if "/" in text:
        try:
            fraction = Fraction(text)
        except (ValueError, ZeroDivisionError):
            return None
        if fraction.denominator == 0:
            return None
        return float(fraction)
    try:
        return float(text)
    except ValueError:
        return None


def maybe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_stream(streams: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return next((stream for stream in streams if stream.get("codec_type") == kind), {})


def summarize_video(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    fmt = data.get("format", {}) if isinstance(data.get("format"), dict) else {}
    streams = data.get("streams", []) if isinstance(data.get("streams"), list) else []
    video_stream = first_stream(streams, "video")
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    return {
        "path": str(path),
        "duration": maybe_float(fmt.get("duration")),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": parse_fraction(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
        "codec": video_stream.get("codec_name"),
        "pixel_format": video_stream.get("pix_fmt"),
        "bit_rate": maybe_float(video_stream.get("bit_rate") or fmt.get("bit_rate")),
        "has_embedded_audio": bool(audio_streams),
        "embedded_audio_codecs": [stream.get("codec_name") for stream in audio_streams if stream.get("codec_name")],
    }


def summarize_audio(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    fmt = data.get("format", {}) if isinstance(data.get("format"), dict) else {}
    streams = data.get("streams", []) if isinstance(data.get("streams"), list) else []
    audio_stream = first_stream(streams, "audio")
    return {
        "path": str(path),
        "duration": maybe_float(fmt.get("duration")),
        "codec": audio_stream.get("codec_name"),
        "channels": audio_stream.get("channels"),
        "sample_rate": maybe_float(audio_stream.get("sample_rate")),
        "bit_rate": maybe_float(audio_stream.get("bit_rate") or fmt.get("bit_rate")),
    }


def probe_media(script: Path, video: Path, audio: Path) -> dict[str, Any]:
    result = run([sys.executable, script, "--json", video, audio], capture_output=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse probe_media.py JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("probe_media.py --json did not return a JSON object")
    return payload


def probe_entry(raw: dict[str, Any], expected: Path, label: str) -> dict[str, Any]:
    direct = raw.get(str(expected))
    if isinstance(direct, dict):
        return direct
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        try:
            if Path(key).expanduser().resolve() == expected:
                return value
        except OSError:
            continue
    raise SystemExit(f"probe_media.py did not return metadata for {label}: {expected}")


def write_media_summary(script: Path, video: Path, audio: Path, output: Path) -> dict[str, Any]:
    raw = probe_media(script, video, audio)
    video_data = probe_entry(raw, video, "video")
    audio_data = probe_entry(raw, audio, "audio")

    video_summary = summarize_video(video, video_data)
    audio_summary = summarize_audio(audio, audio_data)
    video_duration = video_summary.get("duration")
    audio_duration = audio_summary.get("duration")
    duration_delta = None
    if isinstance(video_duration, (int, float)) and isinstance(audio_duration, (int, float)):
        duration_delta = float(audio_duration) - float(video_duration)

    summary = {
        "schema": MEDIA_SCHEMA,
        "source_video": str(video),
        "source_audio": str(audio),
        "video": video_summary,
        "audio": audio_summary,
        "duration_delta": duration_delta,
    }
    output.write_text(json.dumps(summary, indent=2) + "\n")
    eprint(f"Wrote media summary: {output}")
    return summary


def transcribe(args: argparse.Namespace, script: Path, audio: Path, out_dir: Path) -> dict[str, Any]:
    transcript_path = out_dir / "transcript.json"
    cached = cached_artifact(
        path=transcript_path,
        label="transcript.json",
        schema=TRANSCRIPT_SCHEMA,
        source_key="source_audio",
        expected_source=audio,
        force=args.force,
    )
    if cached is not None:
        return cached

    cmd: list[str | Path] = [sys.executable, script, audio, "--out", out_dir, "--language", args.language]
    if args.model:
        cmd.extend(["--model", args.model.expanduser()])
    if args.whisper_cli:
        cmd.extend(["--whisper-cli", args.whisper_cli])
    if args.no_install:
        cmd.append("--no-install")
    run(cmd)
    data = load_json(transcript_path, "transcript.json")
    validate_artifact_data(
        data=data,
        label="transcript.json",
        schema=TRANSCRIPT_SCHEMA,
        source_key="source_audio",
        expected_source=audio,
    )
    return data


def analyze_screen(args: argparse.Namespace, script: Path, video: Path, out_dir: Path) -> dict[str, Any]:
    screen_events_path = out_dir / "screen-events.json"
    cached = cached_artifact(
        path=screen_events_path,
        label="screen-events.json",
        schema=SCREEN_EVENTS_SCHEMA,
        source_key="source_video",
        expected_source=video,
        force=args.force,
    )
    if cached is not None:
        return cached

    cmd: list[str | Path] = [sys.executable, script, "--video", video, "--out", out_dir]
    passthrough = [
        ("--scan-interval", args.scan_interval),
        ("--vision-interval", args.vision_interval),
        ("--refine-window", args.refine_window),
        ("--refine-step", args.refine_step),
        ("--min-hold-duration", args.min_hold_duration),
        ("--min-event-gap", args.min_event_gap),
        ("--max-vision-frames", args.max_vision_frames),
        ("--ocr-level", args.ocr_level),
    ]
    for flag, value in passthrough:
        if value is not None:
            cmd.extend([flag, str(value)])
    if args.no_install:
        cmd.append("--no-install")
    run(cmd)
    data = load_json(screen_events_path, "screen-events.json")
    validate_artifact_data(
        data=data,
        label="screen-events.json",
        schema=SCREEN_EVENTS_SCHEMA,
        source_key="source_video",
        expected_source=video,
    )
    return data


def segment_midpoint(segment: dict[str, Any], index: int, count: int, audio_duration: float | None) -> tuple[float | None, bool]:
    start = maybe_float(segment.get("start"))
    end = maybe_float(segment.get("end"))
    if start is not None and end is not None:
        return (start + end) / 2.0, False
    if start is not None:
        return start, True
    if end is not None:
        return end, True
    if audio_duration and count > 0:
        return audio_duration * ((index - 0.5) / count), True
    return None, True


def segment_duration(segment: dict[str, Any]) -> float | None:
    start = maybe_float(segment.get("start"))
    end = maybe_float(segment.get("end"))
    if start is None or end is None:
        return None
    return max(0.0, end - start)


def source_time_from_narration(
    narration_time: float | None,
    audio_duration: float | None,
    video_duration: float | None,
) -> float | None:
    if narration_time is None or not audio_duration or not video_duration:
        return None
    if audio_duration <= 0 or video_duration <= 0:
        return None
    return max(0.0, min(video_duration, narration_time / audio_duration * video_duration))


def clean_text(value: Any, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def event_time(event: dict[str, Any]) -> float | None:
    return maybe_float(event.get("time"))


def event_end(event: dict[str, Any]) -> float | None:
    end = maybe_float(event.get("end"))
    if end is not None:
        return end
    time = event_time(event)
    duration = maybe_float(event.get("duration"))
    if time is not None and duration is not None:
        return time + duration / 2.0
    return time


def candidate_event(event: dict[str, Any], anchor: float | None) -> dict[str, Any]:
    time = event_time(event)
    distance = abs(time - anchor) if time is not None and anchor is not None else None
    payload = {
        "id": event.get("id"),
        "kind": event.get("kind"),
        "time": time,
        "start": maybe_float(event.get("start")),
        "end": event_end(event),
        "duration": maybe_float(event.get("duration")),
        "score": maybe_float(event.get("score")),
        "distance_from_expected": distance,
        "ocr_text": clean_text(event.get("ocr_text")),
        "frame": event.get("frame"),
        "notes": event.get("notes") if isinstance(event.get("notes"), list) else [],
    }
    return payload


def select_candidates(events: list[dict[str, Any]], anchor: float | None) -> list[dict[str, Any]]:
    if anchor is None:
        return []
    timed_events = [event for event in events if event_time(event) is not None]
    nearby = [
        event
        for event in timed_events
        if abs(float(event_time(event)) - anchor) <= NEARBY_EVENT_WINDOW_SECONDS
    ]
    source = nearby or sorted(timed_events, key=lambda event: abs(float(event_time(event)) - anchor))[:MAX_CANDIDATES_PER_ROW]
    ordered = sorted(
        source,
        key=lambda event: (
            EVENT_PRIORITY.get(str(event.get("kind")), 99),
            abs(float(event_time(event)) - anchor),
        ),
    )
    return [candidate_event(event, anchor) for event in ordered[:MAX_CANDIDATES_PER_ROW]]


def rank_candidates_for_segment(segment_text: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cue_tokens = tokens(segment_text)
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        overlap = sorted(cue_tokens & tokens(str(candidate.get("ocr_text") or "")))
        score = len(overlap) / len(cue_tokens) if cue_tokens else 0.0
        updated = dict(candidate)
        updated["text_overlap"] = {"score": round(score, 3), "terms": overlap}
        ranked.append(updated)
    return sorted(
        ranked,
        key=lambda candidate: (
            -maybe_float(candidate.get("text_overlap", {}).get("score") or 0.0),
            EVENT_PRIORITY.get(str(candidate.get("kind")), 99),
            maybe_float(candidate.get("distance_from_expected")) or float("inf"),
        ),
    )


def overlap_score(candidates: list[dict[str, Any]]) -> tuple[float, list[str]]:
    scores = [maybe_float(candidate.get("text_overlap", {}).get("score")) or 0.0 for candidate in candidates]
    terms = sorted(
        {
            term
            for candidate in candidates
            for term in candidate.get("text_overlap", {}).get("terms", [])
            if isinstance(term, str)
        }
    )
    return (max(scores) if scores else 0.0), terms


def proposed_operation(
    candidates: list[dict[str, Any]],
    cue_duration: float | None,
) -> str:
    if not candidates:
        return "needs_manual_match"
    candidate = candidates[0]
    kind = candidate.get("kind")
    event_duration = maybe_float(candidate.get("duration"))
    if kind in {"ocr_change", "scene_change"}:
        return "align_to_event"
    if kind == "stable_hold":
        if cue_duration and event_duration:
            if cue_duration > event_duration * 1.25:
                return "review_freeze"
            if event_duration > cue_duration * 1.5:
                return "review_speed_change"
        return "review_hold"
    return "needs_manual_match"


def confidence(
    *,
    candidates: list[dict[str, Any]],
    estimated_source_time: float | None,
    inferred_time: bool,
    overlap: float,
) -> str:
    if estimated_source_time is None or inferred_time or not candidates:
        return "low"
    first = candidates[0]
    distance = maybe_float(first.get("distance_from_expected"))
    kind = first.get("kind")
    if kind == "ocr_change" and overlap >= 0.25:
        return "high"
    if kind == "scene_change" and distance is not None and distance <= 1.5:
        return "high"
    if kind in {"ocr_change", "scene_change", "stable_hold"} and distance is not None and distance <= NEARBY_EVENT_WINDOW_SECONDS:
        return "medium"
    return "low"


def likely_source_range(
    estimated_source_time: float | None,
    candidates: list[dict[str, Any]],
    video_duration: float | None,
) -> dict[str, float | None]:
    values: list[float] = []
    if estimated_source_time is not None:
        values.append(estimated_source_time)
    for candidate in candidates:
        for key in ("start", "time", "end"):
            value = maybe_float(candidate.get(key))
            if value is not None:
                values.append(value)
    if not values:
        return {"start": None, "end": None}
    start = min(values) - LIKELY_RANGE_PADDING_SECONDS
    end = max(values) + LIKELY_RANGE_PADDING_SECONDS
    if video_duration is not None:
        start = max(0.0, min(video_duration, start))
        end = max(0.0, min(video_duration, end))
    else:
        start = max(0.0, start)
    return {"start": round(start, 3), "end": round(max(start, end), 3)}


def row_notes(
    *,
    inferred_time: bool,
    candidates: list[dict[str, Any]],
    overlap: float,
    duration_delta: float | None,
) -> list[str]:
    notes: list[str] = []
    if inferred_time:
        notes.append("Transcript segment timing is partial or missing; source estimate is approximate.")
    if not candidates:
        notes.append("No nearby screen-event evidence found; review manually.")
    elif candidates[0].get("kind") == "stable_hold":
        notes.append("Stable hold may indicate a wait/load span that can be trimmed, sped up, or frozen.")
    if overlap >= 0.25:
        notes.append("OCR text overlaps the narration cue.")
    if duration_delta is not None and abs(duration_delta) > 5:
        relation = "longer" if duration_delta > 0 else "shorter"
        notes.append(f"Narration is {abs(duration_delta):.1f}s {relation} than the source video overall.")
    return notes


def build_rows(
    transcript: dict[str, Any],
    screen_events: dict[str, Any],
    media_summary: dict[str, Any],
    warnings: list[str],
) -> list[dict[str, Any]]:
    raw_segments = transcript.get("segments")
    if not isinstance(raw_segments, list):
        warnings.append("transcript.json has no segments array; timing map has no narration rows.")
        return []
    segments = [segment for segment in raw_segments if isinstance(segment, dict)]
    if not segments:
        warnings.append("transcript.json contains no usable transcript segments.")
        return []

    raw_events = screen_events.get("events")
    events = [event for event in raw_events if isinstance(event, dict)] if isinstance(raw_events, list) else []
    if not events:
        warnings.append("screen-events.json contains no usable screen events.")

    audio_duration = maybe_float(transcript.get("duration")) or maybe_float(media_summary.get("audio", {}).get("duration"))
    video_duration = maybe_float(screen_events.get("duration")) or maybe_float(media_summary.get("video", {}).get("duration"))
    duration_delta = maybe_float(media_summary.get("duration_delta"))

    rows: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        mid, inferred_time = segment_midpoint(segment, index, len(segments), audio_duration)
        source_estimate = source_time_from_narration(mid, audio_duration, video_duration)
        candidates = rank_candidates_for_segment(
            str(segment.get("text") or ""),
            select_candidates(events, source_estimate),
        )
        overlap, terms = overlap_score(candidates)
        cue_duration = segment_duration(segment)
        operation = proposed_operation(candidates, cue_duration)
        row_confidence = confidence(
            candidates=candidates,
            estimated_source_time=source_estimate,
            inferred_time=inferred_time,
            overlap=overlap,
        )
        rows.append(
            {
                "id": f"tm{index:03d}",
                "transcript_segment": {
                    "id": segment.get("id") or f"n{index:03d}",
                    "start": maybe_float(segment.get("start")),
                    "end": maybe_float(segment.get("end")),
                    "text": clean_text(segment.get("text"), limit=500),
                },
                "narration_time": {
                    "start": maybe_float(segment.get("start")),
                    "end": maybe_float(segment.get("end")),
                    "mid": round(mid, 3) if mid is not None else None,
                    "inferred": inferred_time,
                },
                "expected_source_time": round(source_estimate, 3) if source_estimate is not None else None,
                "likely_source_range": likely_source_range(source_estimate, candidates, video_duration),
                "candidate_events": candidates,
                "text_overlap": {
                    "score": round(overlap, 3),
                    "terms": terms,
                },
                "proposed_operation": operation,
                "confidence": row_confidence,
                "notes": row_notes(
                    inferred_time=inferred_time,
                    candidates=candidates,
                    overlap=overlap,
                    duration_delta=duration_delta,
                ),
            }
        )
    return rows


def seconds(value: Any) -> str:
    numeric = maybe_float(value)
    if numeric is None:
        return "unknown"
    return f"{numeric:.3f}s"


def time_range_text(value: dict[str, Any]) -> str:
    return f"{seconds(value.get('start'))} - {seconds(value.get('end'))}"


def escape_md(value: Any) -> str:
    text = clean_text(value, limit=160)
    return text.replace("|", "\\|").replace("\n", " ")


def evidence_text(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "No nearby evidence"
    parts = []
    for candidate in candidates:
        label = f"{candidate.get('kind')} {candidate.get('id') or ''}".strip()
        time = seconds(candidate.get("time"))
        ocr = clean_text(candidate.get("ocr_text"), limit=80)
        if ocr:
            parts.append(f"{label} @ {time}: {ocr}")
        else:
            parts.append(f"{label} @ {time}")
    return "; ".join(parts)


def write_markdown(
    *,
    path: Path,
    video: Path,
    audio: Path,
    artifacts: dict[str, str | None],
    media_summary: dict[str, Any],
    rows: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    video_duration = media_summary.get("video", {}).get("duration")
    audio_duration = media_summary.get("audio", {}).get("duration")
    duration_delta = media_summary.get("duration_delta")
    lines = [
        "# Timing Map",
        "",
        "This is an evidence scaffold for review. It is not a render spec.",
        "",
        "## Summary",
        "",
        f"- Source video: `{video}`",
        f"- Narration audio: `{audio}`",
        f"- Video duration: {seconds(video_duration)}",
        f"- Narration duration: {seconds(audio_duration)}",
        f"- Duration delta: {seconds(duration_delta)}",
        "",
        "## Artifacts",
        "",
    ]
    for label, artifact_path in artifacts.items():
        if artifact_path:
            lines.append(f"- {label}: `{artifact_path}`")
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "",
            "## Review Checklist",
            "",
            "- Confirm high-confidence narration/screen matches visually.",
            "- Review low-confidence rows before building an edit spec.",
            "- Treat stable holds as candidates for trims, speed changes, or freeze frames.",
            "- Use OCR text as supporting evidence, not proof of final alignment.",
            "",
            "## Timing Rows",
            "",
            "| Narration | Narration Time | Likely Source Range | Nearby Evidence | Proposed Operation | Confidence | Notes / Questions |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        segment = row["transcript_segment"]
        notes = "; ".join(row.get("notes") or [])
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(segment.get("text")),
                    escape_md(time_range_text(row["narration_time"])),
                    escape_md(time_range_text(row["likely_source_range"])),
                    escape_md(evidence_text(row.get("candidate_events") or [])),
                    escape_md(row.get("proposed_operation")),
                    escape_md(row.get("confidence")),
                    escape_md(notes),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n")
    eprint(f"Wrote timing map: {path}")


def write_timing_json(
    *,
    path: Path,
    video: Path,
    audio: Path,
    artifacts: dict[str, str | None],
    media_summary: dict[str, Any],
    rows: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "source_video": str(video),
        "source_audio": str(audio),
        "artifacts": artifacts,
        "media_summary": media_summary,
        "warnings": warnings,
        "rows": rows,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    eprint(f"Wrote timing map JSON: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True, help="Source screencast video")
    parser.add_argument("--audio", type=Path, required=True, help="Narration audio")
    parser.add_argument("--out", type=Path, required=True, help="Output directory for analysis artifacts")
    parser.add_argument("--force", action="store_true", help="Regenerate transcript and screen analysis artifacts")
    parser.add_argument("--no-install", action="store_true", help="Pass --no-install to bundled helpers")
    parser.add_argument("--language", default="en", help="Whisper language code to pass to transcription")
    parser.add_argument("--model", type=Path, help="Whisper model path to pass to transcription")
    parser.add_argument("--whisper-cli", help="Path or command name for whisper-cli")
    parser.add_argument("--scan-interval", type=positive_float)
    parser.add_argument("--vision-interval", type=positive_float)
    parser.add_argument("--refine-window", type=positive_float)
    parser.add_argument("--refine-step", type=positive_float)
    parser.add_argument("--min-hold-duration", type=positive_float)
    parser.add_argument("--min-event-gap", type=positive_float)
    parser.add_argument("--max-vision-frames", type=positive_int)
    parser.add_argument("--ocr-level", choices=("fast", "accurate"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    video = resolve_existing_file(args.video, "--video")
    audio = resolve_existing_file(args.audio, "--audio")
    out_dir = prepare_output_dir(args.out)
    script_dir = Path(__file__).resolve().parent

    media_summary_path = out_dir / "media-summary.json"
    transcript_path = out_dir / "transcript.json"
    screen_events_path = out_dir / "screen-events.json"
    timing_md_path = out_dir / "timing-map.md"
    timing_json_path = out_dir / "timing-map.json"
    contact_sheet = out_dir / "screen-events-contact-sheet.jpg"

    ensure_ffmpeg(args.no_install)
    media_summary = write_media_summary(script_dir / "probe_media.py", video, audio, media_summary_path)
    transcript = transcribe(args, script_dir / "transcribe_narration.py", audio, out_dir)
    screen_events = analyze_screen(args, script_dir / "analyze_screen_events.py", video, out_dir)

    warnings: list[str] = []
    duration_delta = maybe_float(media_summary.get("duration_delta"))
    if duration_delta is not None and abs(duration_delta) > 5:
        relation = "longer" if duration_delta > 0 else "shorter"
        warnings.append(f"Narration is {abs(duration_delta):.1f}s {relation} than the source video.")
    if not contact_sheet.exists():
        warnings.append("screen-events-contact-sheet.jpg was not found; verify screen events manually.")

    artifacts = {
        "media_summary": str(media_summary_path),
        "transcript": str(transcript_path),
        "screen_events": str(screen_events_path),
        "screen_events_contact_sheet": str(contact_sheet) if contact_sheet.exists() else None,
        "timing_map_markdown": str(timing_md_path),
        "timing_map_json": str(timing_json_path),
    }
    rows = build_rows(transcript, screen_events, media_summary, warnings)
    write_timing_json(
        path=timing_json_path,
        video=video,
        audio=audio,
        artifacts=artifacts,
        media_summary=media_summary,
        rows=rows,
        warnings=warnings,
    )
    write_markdown(
        path=timing_md_path,
        video=video,
        audio=audio,
        artifacts=artifacts,
        media_summary=media_summary,
        rows=rows,
        warnings=warnings,
    )
    print(f"Wrote media summary: {media_summary_path}")
    print(f"Wrote timing map: {timing_md_path}")
    print(f"Wrote timing map JSON: {timing_json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
