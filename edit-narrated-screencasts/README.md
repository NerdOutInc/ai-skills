# edit-narrated-screencasts

A skill that helps AI agents turn an existing screen recording and separately
recorded narration into a polished screencast edit. It guides media inspection,
narration/action timing maps, clip retiming, freeze frames, optional
project-specific intro/outro stills, transparent artifact patches, preview
renders, HQ renders, and timestamp contact-sheet verification.

The full agent instructions live in [`SKILL.md`](SKILL.md).

## Install

```bash
npx skills add https://github.com/NerdOutInc/ai-skills --skill edit-narrated-screencasts
```

## Usage

Invoke the skill explicitly when you want to edit an existing screencast with
narration; it does not auto-load on intent:

- **Claude Code:** type `/edit-narrated-screencasts` and then describe the edit.
- **Codex:** type `$edit-narrated-screencasts` and then describe the edit.

Example: `$edit-narrated-screencasts` then "sync this product walkthrough video
to my recorded voiceover and render a preview first."

Attach or point the agent to the source screen recording, narration audio, and
the output directory where generated previews, frames, patches, stills, and
final renders should go. The skill keeps the original media untouched.

A typical session:

1. **Media inspection.** The agent probes the source video and narration audio
   for duration, resolution, frame rate, codecs, bitrate, and embedded audio.
2. **Timing map.** The agent builds a simple source-time to output-time map so
   narration beats line up with visible screen actions.
3. **Edit assets.** The agent extracts freeze frames, creates transparent
   overlay patches for artifacts such as hover tooltips, and prepares any
   project-specific intro/outro stills you requested.
4. **Preview render.** The agent renders a low-quality preview first and shares
   the file path so you can review timing, text, fades, and patched areas.
5. **HQ render.** After you approve the preview, the agent renders the
   high-quality MP4 and verifies it with media probing and timestamp review
   frames.

For the full agent-facing protocol, including edit specs, profile options,
audio timing constraints, and helper script usage, see [`SKILL.md`](SKILL.md).

## Dependencies

The agent checks for these at the point in the workflow where they're needed
and will ask before running `brew install` or `pip install`. They're listed
here so you can pre-install them once and skip the prompt on every session.

### Required

- **Python 3.10 or newer** - the bundled scripts use modern type-hint syntax.
  Install it with Homebrew or from python.org if `python3` is not already
  available on your system.

- **[ffmpeg](https://www.ffmpeg.org)** (provides `ffprobe`) - media inspection,
  frame extraction, contact sheets, timeline rendering, and MP4 output:

  ```bash
  brew install ffmpeg
  ```

- **[Pillow](https://python-pillow.org)** - contact sheet generation and
  transparent overlay patch creation:

  ```bash
  python3 -m pip install pillow
  ```

### Bundled (no install needed)

These ship inside the skill directory and don't require a separate install:

- `scripts/probe_media.py` - summarizes source video/audio metadata with
  `ffprobe`.
- `scripts/extract_review_frames.py` - extracts timestamped frames and optional
  contact sheets for visual review.
- `scripts/make_overlay_patch.py` - creates transparent PNG overlays from clean
  and dirty frames.
- `scripts/render_screencast.py` - renders preview and HQ MP4 files from a JSON
  edit spec.
