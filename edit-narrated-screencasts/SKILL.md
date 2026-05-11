---
name: edit-narrated-screencasts
disable-model-invocation: true
description: >
  Edit narrated screencasts by syncing existing narration to screen actions,
  analyzing screen events with Apple Vision, retiming footage, inserting freeze
  frames, patching visual artifacts such as hover tooltips, optionally adding
  user-supplied intro/outro stills, and rendering preview or high-quality MP4
  outputs. Use when asked to combine a voiceover with existing screen recording
  footage or polish a screencast edit.
---

# Edit Narrated Screencasts

Use this skill when the user has an existing screencast and narration audio and
wants them turned into a cohesive edited video. The default workflow is
iterative: inspect first, generate a low-quality preview for timing review, then
render the high-quality final only after the user accepts the edit.

This skill is macOS-only because screen analysis uses Apple Vision through a
bundled Swift helper.

## Workflow

The workflow has three phases: **Inspect**, **Edit**, and **Render**.
Follow each phase in order.

### Phase 1 — Inspect

1. Run the timing-analysis package before building the edit plan.
   - Run:

     ```bash
     python3 "$SKILL_DIR/scripts/prepare_timing_analysis.py" \
       --video source.mp4 \
       --audio narration.m4a \
       --out /tmp/my-edit/analysis
     ```

   - Use `--force` to rebuild transcript and screen-analysis artifacts when
     rerunning against the same output directory.
   - Pass `--no-install` in locked-down environments or when dependencies must
     be preinstalled manually.
   - The helper writes `media-summary.json`, `transcript.json`,
     `screen-events.json`, `timing-map.md`, and `timing-map.json` in the output
     directory. It also writes `screen-events-contact-sheet.jpg` when usable
     frame-backed screen events are available; if the sheet is absent, the
     orchestrator warns and you must verify screen events from the frame paths.
   - Treat `timing-map.md` and `timing-map.json` as evidence scaffolds, not a
     render spec and not final alignment.

2. Review the analysis artifacts.
   - Use `media-summary.json` to capture source duration, resolution, frame
     rate, codec, bitrate, audio duration, and whether the source has embedded
     audio.
   - Use `transcript.json` segments as narration beats.
   - Use `screen-events.json` and the contact sheet, when present, as screen
     evidence:
     `scene_change` marks action/page/modal boundaries, `ocr_change` confirms
     visible text or state changes, `stable_hold` suggests waits/trims/speed-up
     or freeze-frame candidates, and `anchor` frames provide regular visual
     review points.
   - Use confidence and proposed operations in the timing map as review
     prompts. Verify important timestamps visually before rendering.
   - Preserve the source resolution and frame rate for HQ unless the user
     explicitly requests downscaling or upscaling. The renderer auto-detects
     resolution and frame rate when the source file is available; set
     `timeline.fps` explicitly for placeholder-only dry runs.

### Phase 2 — Edit

3. Turn the generated timing map into a checked edit map.
   - Start from `timing-map.md` or `timing-map.json`; do not treat it as a
     finished edit decision.
   - Mark narration beats and the matching screen actions.
   - Use screen-event candidates to identify likely source-video action
     boundaries, loading waits, state changes, and freeze-frame candidates.
   - If narration and screen actions do not align, notify the user and suggest
     adjustments to either the narration or the video.
   - Identify long waits that can be sped up, actions that need more breathing
     room, and places where a freeze frame communicates better than raw waiting.
   - Keep a simple table of source time, output time, action, narration cue,
     and edit operation.

4. Create supporting stills.
   - If the user asks for intro/outro stills, treat them as project-specific
     still assets. Use supplied artwork, inspect the user's actual brand/source
     files, or create one-off images in the requested output directory. Do not
     rely on bundled brand templates.
   - Extract clean freeze frames with `ffmpeg` or `scripts/extract_review_frames.py`.
   - When a hover title, cursor artifact, toast, or other blemish persists, use
     `scripts/make_overlay_patch.py` to build a transparent patch from a clean
     frame.

### Phase 3 — Render

5. Render a preview first.
   - Use `scripts/render_screencast.py --profile preview`.
   - Share the preview path and ask the user to review timing, text, fades, and
     patched areas.
   - Expect several rounds of small timing/design adjustments.

6. Render HQ after approval.
   - Use `scripts/render_screencast.py --profile hq`.
   - Prefer H.264, `-preset slow`, `-crf 18`, original FPS, `yuv420p`, and audio
     stream copy when the audio is already AAC (m4a/MP4-compatible).
   - Use `-movflags +faststart` for shareable MP4 output.

7. Verify the final.
   - Probe the final file.
   - Generate a contact sheet around intros, fades, patches, important actions,
     and the outro.
   - Inspect visually before calling the render finished.

## Hard Rules

- Never overwrite the user's original video or audio.
- Run this skill on macOS. Screen analysis requires Apple Vision and the Swift
  runtime from macOS Command Line Tools.
- Keep large generated media out of the skill repository.
- Put preview renders, final renders, extracted frames, generated stills, and
  temporary stills in a user-specified output directory.
- Before rendering HQ, show or describe the preview result and confirm the user
  likes the timing and any generated still-card design.
- Print generated `ffmpeg` commands before running them so the edit is
  explainable and recoverable.
- If replacing a visual artifact with a static patch, verify alignment at the
  first, middle, and last affected timestamps.
- Confirm the narration's leading silence matches `intro.duration -
  intro.fade_duration`. The narration plays from output time `0`, so if the
  intro card is 4s with a 1s fade, the m4a should start with ~3s of silence.
  See `references/edit-spec.md` for details.
- Do not run unrelated dependency installs without user approval. Bundled
  helpers may automatically install their own direct runtime dependencies:
  on macOS with Homebrew, `prepare_timing_analysis.py` and
  `transcribe_narration.py` may install `ffmpeg`/`ffprobe` or `whisper-cpp` and
  download the default Whisper model; Pillow-using helpers may install Pillow
  with the active Python, using `--user` only for non-virtualenv Python
  installs. Pass `--no-install` in locked-down environments.

## Bundled Helpers

- `scripts/probe_media.py`: summarize source video/audio metadata.
- `scripts/prepare_timing_analysis.py`: run media probing, narration
  transcription, Apple Vision screen analysis, and timing-map scaffolding in one
  analysis package.
- `scripts/transcribe_narration.py`: transcribe narration with local
  whisper.cpp and write normalized `transcript.json`. Normally invoked by
  `prepare_timing_analysis.py`.
- `scripts/analyze_screen_events.py`: sample the source video, run Apple Vision
  screen analysis, write `screen-events.json`, and write a best-effort contact
  sheet when frame-backed events are available.
  Normally invoked by `prepare_timing_analysis.py`.
- `scripts/vision_frame_analysis.swift`: Apple Vision OCR and feature-print
  analysis for sampled frames.
- `scripts/extract_review_frames.py`: extract timestamped frames and contact
  sheets for review. Automatically installs Pillow when a contact sheet is
  requested and Pillow is missing.
- `scripts/make_overlay_patch.py`: create transparent PNG overlays from clean
  and dirty frames. Automatically installs Pillow when missing.
- `scripts/render_screencast.py`: render preview/HQ MP4 files from an edit spec.

Read the references when needed:

- `references/workflow.md` for the full editing process.
- `references/edit-spec.md` for the JSON render-spec schema.
- `references/quality-and-compression.md` for encode choices and file size
  tradeoffs.
- `references/paperless-ngx-case-study.md` for the worked Paperless NGX
  example.
