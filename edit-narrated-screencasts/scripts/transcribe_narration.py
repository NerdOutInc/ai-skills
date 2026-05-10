#!/usr/bin/env python3
"""Transcribe narration audio with whisper.cpp and normalize the output."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

# Mirrored helper: keep this file in sync with:
# - edit-narrated-screencasts/scripts/transcribe_narration.py
# - screen-studio/scripts/transcribe_narration.py

MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"
MODEL_SHA256 = "a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002"
DOWNLOAD_TIMEOUT_SECONDS = 120
DEFAULT_MODEL = Path.home() / ".cache" / "whisper.cpp" / "ggml-base.en.bin"
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


def find_executable(name: str, extras: list[Path] | None = None) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in extras or []:
        expanded = candidate.expanduser()
        if expanded.exists() and expanded.is_file():
            return str(expanded)
    return None


def homebrew_executables(name: str) -> list[Path]:
    return [directory / name for directory in HOMEBREW_BIN_DIRS]


def find_brew() -> str | None:
    found = shutil.which("brew")
    if found:
        return found
    for candidate in homebrew_executables("brew"):
        if candidate.exists():
            return str(candidate)
    return None


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
    raise SystemExit("ffmpeg install completed, but ffmpeg/ffprobe still were not found on PATH.")


def ensure_whisper_cli(no_install: bool, override: str | None) -> str:
    if override:
        override_path = Path(override).expanduser()
        if override_path.exists():
            return str(override_path)
        found = shutil.which(override)
        if found:
            return found
        raise SystemExit(f"Configured whisper-cli was not found: {override}")

    whisper_cli = find_executable(
        "whisper-cli",
        homebrew_executables("whisper-cli"),
    )
    if whisper_cli:
        return whisper_cli

    if no_install or not can_auto_install():
        raise missing_dependency("whisper-cli", "brew install whisper-cpp", no_install)

    brew = find_brew()
    if not brew:
        raise missing_dependency("whisper-cli", "brew install whisper-cpp", no_install)
    run([brew, "install", "whisper-cpp"])

    whisper_cli = find_executable(
        "whisper-cli",
        homebrew_executables("whisper-cli"),
    )
    if whisper_cli:
        return whisper_cli
    raise SystemExit("whisper-cpp install completed, but whisper-cli still was not found on PATH.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_model(tmp: Path) -> None:
    with urllib.request.urlopen(MODEL_URL, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        with tmp.open("wb") as output:
            shutil.copyfileobj(response, output)


def ensure_model(model: Path, no_install: bool) -> Path:
    model = model.expanduser()
    if model.exists():
        return model
    if model != DEFAULT_MODEL.expanduser():
        raise SystemExit(
            f"Model not found: {model}\n"
            f"Only the default model path is downloaded automatically: {DEFAULT_MODEL}\n"
            "Provide an existing model path with --model, or omit --model to use the default."
        )
    if no_install:
        raise SystemExit(
            f"Missing Whisper model: {model}\n"
            "Install it with:\n"
            f"  mkdir -p {shlex.quote(str(model.parent))}\n"
            f"  curl -L -o {shlex.quote(str(model))} {shlex.quote(MODEL_URL)}"
        )

    model.parent.mkdir(parents=True, exist_ok=True)
    tmp = model.with_name(f"{model.name}.download")
    if tmp.exists():
        tmp.unlink()
    eprint(f"Downloading Whisper model to {model}")
    try:
        download_model(tmp)
        actual_sha256 = sha256_file(tmp)
        if actual_sha256 != MODEL_SHA256:
            tmp.unlink(missing_ok=True)
            raise SystemExit(
                "Downloaded Whisper model checksum mismatch:\n"
                f"  expected: {MODEL_SHA256}\n"
                f"  actual:   {actual_sha256}"
            )
        tmp.replace(model)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink()
        raise SystemExit(f"Could not download Whisper model from {MODEL_URL}: {exc}") from exc
    return model


def probe_duration(ffprobe: str, audio: Path) -> float | None:
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            audio,
        ],
        capture_output=True,
    )
    try:
        data = json.loads(result.stdout)
        duration = data.get("format", {}).get("duration")
        return float(duration)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def parse_timecode(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if text.replace(".", "", 1).isdigit():
        return float(text)
    parts = text.replace(",", ".").split(":")
    try:
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
    except ValueError:
        return None
    return None


def parse_offset_ms(value: Any) -> float | None:
    try:
        return float(value) / 1000.0
    except (TypeError, ValueError):
        return None


def segment_times(entry: dict[str, Any]) -> tuple[float | None, float | None]:
    offsets = entry.get("offsets")
    if isinstance(offsets, dict):
        start = parse_offset_ms(offsets.get("from"))
        end = parse_offset_ms(offsets.get("to"))
        if start is not None or end is not None:
            return start, end

    timestamps = entry.get("timestamps")
    if isinstance(timestamps, dict):
        start = parse_timecode(timestamps.get("from"))
        end = parse_timecode(timestamps.get("to"))
        if start is not None or end is not None:
            return start, end

    return parse_timecode(entry.get("start")), parse_timecode(entry.get("end"))


def parse_whisper_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Whisper JSON output was not created: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse Whisper JSON at {path}: {exc}") from exc

    raw_segments: list[Any]
    if isinstance(data, dict) and isinstance(data.get("transcription"), list):
        raw_segments = data["transcription"]
    elif isinstance(data, dict) and isinstance(data.get("segments"), list):
        raw_segments = data["segments"]
    elif isinstance(data, list):
        raw_segments = data
    else:
        raw_segments = []

    segments: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_segments, start=1):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        start, end = segment_times(raw)
        segments.append(
            {
                "id": f"n{index:03d}",
                "start": start,
                "end": end,
                "text": text,
            }
        )
    return segments


def normalize_transcript(
    *,
    audio: Path,
    duration: float | None,
    language: str,
    model: Path,
    raw_prefix: Path,
    normalized_path: Path,
) -> dict[str, Any]:
    raw_txt = raw_prefix.with_suffix(".txt")
    raw_srt = raw_prefix.with_suffix(".srt")
    raw_json = raw_prefix.with_suffix(".json")
    segments = parse_whisper_json(raw_json)

    if not segments and raw_txt.exists():
        text = raw_txt.read_text().strip()
        if text:
            segments = [{"id": "n001", "start": 0.0, "end": duration, "text": text}]

    payload = {
        "schema": "nerdout.transcript.v1",
        "source_audio": str(audio),
        "duration": duration,
        "language": language,
        "engine": "whisper.cpp",
        "model": str(model),
        "raw_outputs": {
            "text": str(raw_txt),
            "srt": str(raw_srt),
            "json": str(raw_json),
        },
        "segments": segments,
        "text": "\n".join(segment["text"] for segment in segments),
    }
    normalized_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def transcribe(args: argparse.Namespace) -> Path:
    audio = args.audio.expanduser()
    if not audio.exists():
        raise SystemExit(f"Audio file not found: {audio}")

    out_dir = args.out.expanduser()
    if out_dir.exists() and not out_dir.is_dir():
        raise SystemExit(f"--out must be a directory path, not a file: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg, ffprobe = ensure_ffmpeg(args.no_install)
    whisper_cli = ensure_whisper_cli(args.no_install, args.whisper_cli)
    model = ensure_model(args.model, args.no_install)
    duration = probe_duration(ffprobe, audio)

    raw_prefix = out_dir / "whisper"
    normalized_path = out_dir / "transcript.json"

    with tempfile.TemporaryDirectory(prefix="transcribe-narration-") as tmp_dir:
        wav = Path(tmp_dir) / "narration.wav"
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                audio,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                wav,
            ]
        )
        run(
            [
                whisper_cli,
                "-m",
                model,
                "-f",
                wav,
                "-l",
                args.language,
                "-otxt",
                "-osrt",
                "-oj",
                "-of",
                raw_prefix,
            ]
        )

    normalize_transcript(
        audio=audio,
        duration=duration,
        language=args.language,
        model=model,
        raw_prefix=raw_prefix,
        normalized_path=normalized_path,
    )
    return normalized_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="Narration audio file to transcribe")
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for transcript.json and raw Whisper outputs",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL,
        help=f"Whisper model path (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Whisper language code to pass to whisper-cli (default: en)",
    )
    parser.add_argument("--whisper-cli", help="Path or command name for whisper-cli")
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Do not install Homebrew packages or download the default Whisper model",
    )
    args = parser.parse_args()

    normalized_path = transcribe(args)
    print(f"Wrote normalized transcript: {normalized_path}")
    print(f"Wrote raw text: {normalized_path.parent / 'whisper.txt'}")
    print(f"Wrote raw SRT: {normalized_path.parent / 'whisper.srt'}")
    print(f"Wrote raw Whisper JSON: {normalized_path.parent / 'whisper.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
