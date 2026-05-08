# Narrated Screencast Editing Workflow

This workflow is for an existing screen recording plus separately recorded
narration. The goal is to make the visual action match the voiceover without
requiring a new recording.

## 1. Inspect the Media

Run:

```bash
python3 "$SKILL_DIR/scripts/probe_media.py" source.mp4 narration.m4a
```

Record:

- Source video duration, resolution, frame rate, codec, and bitrate.
- Narration duration and codec.
- Whether the video has embedded audio that should be ignored.
- The target output resolution and frame rate.

Keep the original source files untouched.

## 2. Build a Timing Map

Create a simple table with these columns:

- Narration cue or phrase.
- Desired output time.
- Matching source-video action.
- Source time range.
- Edit operation.

Common operations:

- Slow a clip down when the narration needs more time.
- Speed a clip up when the UI is waiting, uploading, indexing, or loading.
- Insert a freeze frame when the screen should hold while narration continues.
- Cut to the outro as soon as the narration finishes the last idea.
- Patch a hover title, tooltip, toast, or one-frame artifact with a transparent
  overlay made from a clean frame.

## 3. Generate or Collect Still Assets

Title cards:

```bash
python3 "$SKILL_DIR/scripts/render_title_cards.py" \
  --config style.json \
  --output-dir /tmp/my-edit/cards
```

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

- Intro text and brand treatment.
- Fade duration between intro, video, and outro.
- Narration/action timing.
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
