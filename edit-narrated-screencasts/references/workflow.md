# Narrated Screencast Editing Workflow

This workflow is for an existing screen recording plus separately recorded
narration. The goal is to make the visual action match the voiceover without
requiring a new recording.

## 0. Check Dependencies

The rendering and frame-review scripts depend on `ffmpeg` (with `ffprobe`) and
Python's Pillow library. Screen analysis requires macOS, Swift from the macOS
Command Line Tools, and Apple Vision. The timing-analysis helper can
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

## 1. Prepare Timing Analysis

In the examples below, `$SKILL_DIR` means the path to the installed
`edit-narrated-screencasts` skill directory.

Run the orchestrator before building the edit map:

```bash
python3 "$SKILL_DIR/scripts/prepare_timing_analysis.py" \
  --video source.mp4 \
  --audio narration.m4a \
  --out /tmp/my-edit/analysis
```

Use `--force` to regenerate `transcript.json` and `screen-events.json` in an
existing analysis directory. Use `--no-install` in locked-down environments. On
macOS with Homebrew, the helper may install `ffmpeg` and `whisper-cpp` and
download `$HOME/.cache/whisper.cpp/ggml-base.en.bin`.

The analysis directory should contain these required artifacts:

- `media-summary.json`
- `transcript.json`
- `screen-events.json`
- `timing-map.md`
- `timing-map.json`

It may also contain `screen-events-contact-sheet.jpg`. The contact sheet is a
best-effort review aid generated when screen analysis has usable frame-backed
events; `prepare_timing_analysis.py` warns when it is absent, and the agent must
then verify screen events from the frame paths in `screen-events.json`.

Use lower-level helpers such as `transcribe_narration.py` and
`analyze_screen_events.py` directly only when you need to debug or regenerate
one artifact family. The normal path is `prepare_timing_analysis.py`.

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

Keep the original source files untouched.

## 2. Review the Timing Map

Start with `timing-map.md` for human review and use `timing-map.json` when a
structured source is easier for the agent to inspect. These files are evidence,
not a render spec and not final alignment.

Review each generated row:

- Compare the narration segment with the suggested source range.
- Open the referenced frame or contact sheet when confidence is low or the OCR
  text is ambiguous.
- Treat proposed operations as prompts: `align_to_event`, `review_hold`,
  `review_freeze`, `review_speed_change`, and `needs_manual_match`.
- Verify important timestamps visually before rendering.

Use the analysis artifacts this way:

- Transcript segments identify narration beats.
- `scene_change` marks likely action/page/modal boundaries.
- `ocr_change` marks visible text or state changes that can confirm the screen
  now matches a narration phrase.
- `stable_hold` marks waits that may be sped up, trimmed, or replaced with a
  freeze frame while narration continues.
- `anchor` frames are regular reference samples for visual review.

## 3. Build a Checked Edit Map

Create a simple table with these columns:

- Narration cue or phrase.
- Desired output time.
- Matching source-video action.
- Source time range.
- Edit operation.

### Action/Narration Anchoring

When mapping a source-video action to a narration cue, anchor to the exact
spoken phrase that introduces the action. Do not use the transcript segment
start as the cue when the phrase appears later in the segment; Whisper segment
boundaries are only rough narration spans and can be several seconds early for a
specific click, scroll, or typing run.

Treat the first meaningful click or keystroke as the calibration anchor for the
whole edit. If the first action is early, fix that before judging later actions.
A bad first anchor can make the whole preview feel slightly ahead of the audio,
even when later mismatches are smaller.

The phrase onset is the earliest acceptable time for visible motion. A click,
scroll, typing run, app switch, or page transition that appears before the
phrase that introduces it will usually feel like the video is ahead of the
audio. By default, start visible action about 0.3-0.8 seconds after the phrase
begins, then verify with real playback.

Use freeze frames to create that delay. Hold the stable frame immediately before
the cursor moves, the page scrolls, or typing begins, then let the recorded
action play at normal speed. If the narration still needs more room after the
action completes, hold a stable frame after the action. Do not slow cursor
movement, scrolling, or typing to fill time; slowed input motion looks wrong
even when the endpoint lands near the narration.

Pick freeze frames that look intentional. Avoid frames with the cursor
mid-motion, a page mid-scroll, a transient hover state, or a distracting cursor
over the content unless that cursor position is part of the demonstration. When
the whole preview feels slightly ahead of the audio, first add or extend a
freeze before the first meaningful action, then re-audit representative later
actions against their exact phrase onsets. Do not shift narration or stretch
visible motion to compensate.

Before each preview, build an action/cue ledger for at least the first
meaningful action and several later representative actions:

- Cue phrase.
- Verified phrase onset in the output audio.
- Matching visual action start in the output video.
- Lead/lag, with negative values meaning the video is early.
- Edit operation that creates any needed delay.

If transcript timing is uncertain, verify the phrase onset from the audio by
playback, waveform inspection, or short audio snippets before rendering. For
review contact sheets, include frames around important cue onsets, such as
`cue - 0.5s`, `cue`, `cue + 0.5s`, and `cue + 1.0s`, so early actions are easy
to spot.

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

## 4. Generate or Collect Still Assets

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

## 5. Render Preview First

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

## 6. Render HQ

After the user accepts the preview:

```bash
python3 "$SKILL_DIR/scripts/render_screencast.py" edit-spec.json \
  --profile hq \
  --output /tmp/my-edit/final-hq.mp4
```

Inspect the final with `probe_media.py` and a timestamp contact sheet before
calling the edit complete.
