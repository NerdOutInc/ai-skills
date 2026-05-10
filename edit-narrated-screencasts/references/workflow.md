# Narrated Screencast Editing Workflow

This workflow is for an existing screen recording plus separately recorded
narration. The goal is to make the visual action match the voiceover without
requiring a new recording.

## 0. Check Dependencies

The rendering and frame-review scripts depend on `ffmpeg` (with `ffprobe`) and
Python's Pillow library. Screen analysis requires macOS, Swift from the macOS
Command Line Tools, and Apple Vision. The transcription helper can
automatically install `ffmpeg`, `whisper-cpp`, and the default Whisper model
when needed on macOS with Homebrew. Pillow-using helpers can automatically
install Pillow with the active Python when needed. Use `--no-install` in
locked-down environments.

```bash
command -v ffmpeg
command -v ffprobe
command -v swift
python3 -c "import PIL" 2>/dev/null && echo "Pillow OK" || echo "Pillow missing"
```

## 1. Inspect the Media

In the examples below, `$SKILL_DIR` means the path to the installed
`edit-narrated-screencasts` skill directory.

Run:

```bash
python3 "$SKILL_DIR/scripts/probe_media.py" source.mp4 narration.m4a
```

Then transcribe the narration:

```bash
python3 "$SKILL_DIR/scripts/transcribe_narration.py" \
  narration.m4a \
  --out /tmp/my-edit/transcript
```

Use `--no-install` in locked-down environments. On macOS with Homebrew, the
helper may install `ffmpeg` and `whisper-cpp` and download
`$HOME/.cache/whisper.cpp/ggml-base.en.bin`. It writes
`/tmp/my-edit/transcript/transcript.json` plus raw `whisper.txt`,
`whisper.srt`, and `whisper.json` files.

Record:

- Source video duration, resolution, frame rate, codec, and bitrate.
- Narration duration and codec. **If the narration is not AAC** (`m4a` /
  MP4-compatible), the renderer will auto-fall back from
  `audio_codec: copy` to `aac` re-encoding with a printed warning. To skip
  the warning, set `audio_codec: aac` explicitly in the HQ profile.
- Whether the video has embedded audio that should be ignored. The renderer
  does not map embedded source-video audio; provide narration or replacement
  audio with `inputs.audio` when the output should include audio.
- The target output resolution and frame rate.
- Transcript cues and timestamps from `transcript.json`.

Then analyze the source video:

```bash
python3 "$SKILL_DIR/scripts/analyze_screen_events.py" \
  --video source.mp4 \
  --out /tmp/my-edit/screen-analysis
```

Use `/tmp/my-edit/screen-analysis/screen-events.json` and the contact sheet to
review likely scene changes, stable holds/load waits, OCR text changes, and
representative frames. This output is evidence for the timing map, not the final
edit decision.

Keep the original source files untouched.

## 2. Build a Timing Map

Create a simple table with these columns:

- Narration cue or phrase.
- Desired output time.
- Matching source-video action.
- Source time range.
- Edit operation.

Use `screen-events.json` to choose candidate source ranges:

- `scene_change` marks likely action/page/modal boundaries.
- `stable_hold` marks waits that may be sped up, trimmed, or replaced with a
  freeze frame while narration continues.
- `ocr_change` marks visible text or state changes that can confirm the screen
  now matches a narration phrase.
- `anchor` frames are regular reference samples for visual review.

Common operations:

- Slow a clip down when the narration needs more time.
- Speed a clip up when the UI is waiting, uploading, indexing, or loading.
- Insert a freeze frame when the screen should hold while narration continues.
- Cut to the outro as soon as the narration finishes the last idea.
- Patch a hover title, tooltip, toast, or one-frame artifact with a transparent
  overlay made from a clean frame.

**Narration leading silence.** Narration plays from output time `0`, under
the intro card. Make sure the m4a starts with silence equal to
`intro.duration - intro.fade_duration` (e.g. ~3s of silence for a 4s intro
with a 1s fade). See `edit-spec.md` for the full constraint.

## 3. Generate or Collect Still Assets

If the edit needs intro or outro stills, create them as one-off project assets
using the user's supplied brand files, screenshots, or generated artwork. Keep
those images in the edit output directory, not inside the skill repo. Match the
source video resolution unless the user asks otherwise, and show the stills or
a preview render before making an HQ video.

Review frames:

```bash
python3 "$SKILL_DIR/scripts/extract_review_frames.py" \
  output-preview.mp4 /tmp/my-edit/review \
  --timestamps 3.2 3.8 35 40 55.7 88.5 91.5
```

Overlay patch:

```bash
python3 "$SKILL_DIR/scripts/make_overlay_patch.py" \
  clean.png dirty.png patch.png \
  --bbox 1800,900,420,180
```

## 4. Render Preview First

Render the low-quality version:

```bash
python3 "$SKILL_DIR/scripts/render_screencast.py" edit-spec.json \
  --profile preview \
  --output /tmp/my-edit/preview.mp4
```

Use the preview to check:

- Any intro/outro stills the user requested.
- Fade duration between intro, video, and outro.
- Narration/action timing.
- Leading-silence alignment (first narration word should land at the body
  cut, not under the intro card).
- Freeze frame placement.
- Overlay patch alignment.
- Whether the outro starts at the right narration phrase.

## 5. Render HQ

After the user accepts the preview:

```bash
python3 "$SKILL_DIR/scripts/render_screencast.py" edit-spec.json \
  --profile hq \
  --output /tmp/my-edit/final-hq.mp4
```

Inspect the final with `probe_media.py` and a timestamp contact sheet before
calling the edit complete.
