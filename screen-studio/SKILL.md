---
name: screen-studio
description: >
  Record repeatable macOS full-display screencasts with Screen Studio. Use when
  Codex is asked to capture a full-display screen recording, record a web app or
  product demo, rehearse a Screen Studio take, start or stop Screen Studio
  recording, use Helium for clean web recordings, run test takes, or document
  exact click locations before a final recording. This skill does not support
  window or selected-area capture.
---

# Record Screen Studio Screencasts

## Scope

Use Screen Studio for recording. This skill records the full display only. Do
not offer or use window capture or selected-area capture. Do not export, trim,
upload, or edit the video unless the user explicitly asks.

Use desktop automation for Screen Studio, Helium, and the target app. Computer
Use is acceptable for inspection and off-camera setup, but do not use Computer
Use to start or stop Screen Studio for a keeper take. Its cursor overlay can
appear in the captured screen.

Use browser automation only for setup or verification inside a page. The actual
screencast should be captured from the visible app or Helium window.

Audio timing is not required. Treat audio duration as a guide to the expected
story beats. The recording just needs to capture each required action clearly.
If the UI needs time to load, index, upload, or respond, wait. The user can
trim or retime the footage to match narration after recording.

## Hard Gates

These requirements are not optional for keeper takes:

- Validate the full interaction sequence with at least two dry runs without recording.
- Do not resize or reposition the target window during recording setup.
- Verify logged-in browser flows immediately before recording.
- Hide Codex and unrelated workbench apps from the capture area.
- Minimize old Screen Studio project and recording windows.
- Start and stop Screen Studio with keyboard shortcuts, not Computer Use.
- If the keyboard recording path is untested, prove it with a smoke capture.
- Do not call a take a keeper until the display track has been checked with
  `ffprobe` and a timestamp contact sheet has been inspected.
- Reject takes that miss required actions or show the wrong state. Do not reject
  a complete take only because it is longer than the audio.

## Actions File And Audio Prep

The "actions file" is a human-readable planning document (markdown or notes)
for a single screencast. It is not a bash script. It captures the take's
story, on-camera steps, and dry-run findings, and may reference small bash or
AppleScript helpers that live as separate files beside it.

If the user provides audio and no complete actions file, transcribe the audio
before planning the recording. Use the transcript to identify the expected
on-screen actions.

Check local transcription tooling before giving up:

```bash
command -v whisper || true
command -v mlx_whisper || true
command -v whisper-cli || true
command -v whisperx || true

python3 - <<'PY'
for mod in ("whisper", "faster_whisper", "mlx_whisper", "torch", "openai"):
    try:
        __import__(mod)
        print(mod, "OK")
    except Exception as exc:
        print(mod, "NO", type(exc).__name__)
PY
```

If no transcription tool is installed, ask the user before installing one.
The preferred local path is `whisper.cpp` via Homebrew because it is fast on
Apple Silicon and runs offline:

```bash
brew install whisper-cpp
```

After install, download a model (the known-good model on this Mac is
`ggml-base.en.bin`). Place it under `$HOME/.cache/whisper.cpp/`:

```bash
mkdir -p "$HOME/.cache/whisper.cpp"
curl -L \
  -o "$HOME/.cache/whisper.cpp/ggml-base.en.bin" \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```

`ffmpeg` and `ffprobe` are required for audio conversion, duration checks, and
the contact sheet. `ffprobe` ships with `ffmpeg`. If either is missing
(`command -v ffmpeg` or `command -v ffprobe` returns nothing), ask the user
before installing:

```bash
brew install ffmpeg
```

The known-good local path is `/opt/homebrew/bin/whisper-cli`, from
`whisper.cpp`. If it exists, find the cached model:

```bash
find "$HOME/.cache/whisper.cpp" /opt/homebrew -maxdepth 5 \
  -name 'ggml-*.bin' 2>/dev/null
```

The known-good model path on this Mac is:

```text
$HOME/.cache/whisper.cpp/ggml-base.en.bin
```

Convert m4a files to wav for this `whisper-cli` build:

```bash
ffmpeg -y -i video.m4a \
  -ar 16000 \
  -ac 1 \
  -c:a pcm_s16le \
  /tmp/video.wav

whisper-cli \
  -m "$HOME/.cache/whisper.cpp/ggml-base.en.bin" \
  -f /tmp/video.wav \
  -l en \
  -otxt \
  -osrt \
  -oj \
  -of /tmp/video-transcript
```

Create or update the actions file with:

- Audio path, duration, and transcript cues.
- Planned screen actions and expected visible states.
- Setup and reset steps.
- Coordinates, helper commands, waits, and state checks.
- Dry-run notes, recording result, project path, and frame-review result.

Do not force a full screencast into one brittle automation script. Prefer
small helper commands for visible actions, then run them manually when the UI
is ready. Save helpers beside the actions file, not only in `/tmp`.

Ask clarifying questions if the narration does not make the on-screen action
clear. Do not guess risky actions such as logins, destructive changes, account
switches, final submissions, purchases, or provisioning steps.

## Window Setup

For web recordings, use Helium by default if installed because its chrome is
clean. Use the default browser if Helium is not installed, or use the browser
requested by the user.

Before rehearsals and keeper takes:

- Put the target app or Helium window in the desired starting state.
- Keep the user-approved display, window size, position, profile, and zoom.
- Do not resize or reposition the target window yourself.
- If browser state is noisy, reopen Helium to the target URL off camera.
- Avoid visible address-bar focus unless it is part of the demo.
- For clean page loads, set the URL off camera and click safely in the page.
- Verify signed-in pages immediately before recording.
- If the user is already logged in, do not quit Helium unless a dry run proves
  the session survives.

Minimize old Screen Studio project or recording windows before opening the
picker. The active "Start Recording" picker may appear in accessibility as
windows named `Screen Studio`, `Start Recording`, an empty dialog, or
`recording-manager-widget`. Do not count that active picker as a stale project
window because it hides itself when recording starts.

Hide Codex and unrelated workbench apps before the final take. Keep
Finder/Desktop visible when the demo needs a Desktop file, a drag/drop source,
or a Finder window on camera. On macOS, verify process names when hiding apps;
for example, VS Code may appear as `Code`.

Restore Codex after recording stops so the user can see verification work.

## Cursor And Coordinates

Use `cliclick` for visible cursor movement during recorded interactions.
Keeper takes should move the actual macOS pointer at a human pace.

- Check for `cliclick` with `command -v cliclick`.
- If missing, ask before installing it.
- `cliclick` uses global macOS display coordinates.
- Do not pass Computer Use or screenshot coordinates directly to `cliclick`.
- Retina screenshots are usually physical pixels; `cliclick` uses logical
  points. On a 2x Retina display, divide screenshot coordinates by 2.
- Prefer coordinates from the live pointer or window-origin math.

Read the front Helium window origin and size with:

```bash
osascript <<'APPLESCRIPT'
tell application "System Events" to tell process "Helium"
  set {x, y} to position of front window
  set {w, h} to size of front window
end tell
return (x as text) & "," & (y as text) & "," & (w as text) & "," & (h as text)
APPLESCRIPT
```

Use `-e 300` as a baseline for human-looking cursor speed. Keep pauses around
movement so the viewer can see intent. Don't move the cursor while narration
is speaking unless the cursor movement is the story.

Prefer visible cursor movement for clicks and focus changes. Use AppleScript,
keyboard shortcuts, or app-native typing when they look natural and avoid
brittle pointer work. Do not rely on browser automation, DOM clicks, or
invisible scripting for keeper interactions unless the user explicitly wants an
automated-looking capture.

For visible typing, type a little slower than normal automation. Prefer paced
keystrokes over instant paste unless typing is not part of the demo.

## Scrolling

When showing a list, grid, or search result set, add a human-looking scroll.
Validate the scroll during dry runs.

- Focus a safe blank area inside the scrollable app first.
- Avoid browser borders, desktop edges, sticky footers, and app chrome.
- Prefer small repeated scroll increments over one large jump.
- If wheel events are unreliable, use repeated arrow-key events.
- Return the list to a useful position before the next scripted click.

Reusable helper:

```bash
smooth_scroll_down_and_back() {
  local down_steps="${1:-24}"
  local up_steps="${2:-18}"
  local delay="${3:-0.025}"

  osascript <<APPLESCRIPT
tell application "System Events"
  repeat ${down_steps} times
    key code 125
    delay ${delay}
  end repeat
  delay 0.30
  repeat ${up_steps} times
    key code 126
    delay ${delay}
  end repeat
end tell
APPLESCRIPT
}
```

Example:

```bash
cliclick -e 300 m:1200,390 c:.
sleep 0.2
smooth_scroll_down_and_back 18 18 0.025
```

If scrolling opens a document, changes filters, summons macOS UI, or does not
move the intended list, fix the focus target and repeat the dry run.

## Dry Runs

Treat dry runs as data gathering. Do not start a keeper until the visible action
sequence works without manual correction.

1. Discovery run: find coordinates, waits, typed text, reset steps, and state
   checks.
2. Validation run: execute the recorded commands and update them until every
   expected state is reached.

During dry runs:

- Trigger the same clicks, typing, navigation, and pauses planned for the take.
- Inspect the visible screen after each click, field edit, form submit, and
  navigation.
- Do not continue until the app has visibly changed state.
- Dismiss first-time prompts, permission dialogs, cookie banners, update
  notices, focus warnings, and one-off UI.
- Replace brittle shortcuts with visible mouse movement or safer app-native
  actions if they summon unexpected macOS UI.
- Reset the app to the desired starting state after each run.
- Update the actions file while the discoveries are fresh.

When audio exists, rehearse for complete screen coverage, not exact duration.
Capture each expected action clearly. Long waits are acceptable.

## Screen Studio Keyboard Flow

Use this full-display recording flow for keeper takes:

1. Activate Screen Studio.
2. Press `Esc` once to clear stale picker state.
3. Press `Command-Control-Return` to toggle the recording picker.
4. Press `Command-Option-3` to choose Display recording.
5. Activate Screen Studio again.
6. Press `Return` to start recording.
7. Press `Command-Control-Return` to stop recording.

The second activation matters. The picker can be visible while another app is
frontmost. If Screen Studio is not frontmost, the final `Return` can go to
Codex, Terminal, or another app instead of starting recording.

If this path has not been proven in the current app state, run a 3-5 second
smoke capture. Verify that Screen Studio created a fresh `.screenstudio`
project with a readable display track before using the path for a keeper.

## Final Take

Before starting:

- Confirm the target app is in the correct starting state.
- Confirm the target window and Desktop state match the rehearsed coordinates.
- Minimize old Screen Studio project windows.
- Hide Codex and unrelated workbench apps.
- Keep intentional on-camera sources, such as Desktop files, visible.

During the take:

- Start Screen Studio with the keyboard flow.
- Wait a short beat.
- Run the rehearsed helper commands or manual steps when the UI is ready.
- Wait as long as needed for uploads, processing, search, loading, or responses.
- Capture every expected action and final state clearly.
- Wait a short beat at the end.
- Stop Screen Studio with `Command-Control-Return`.

After stopping:

- Restore Codex.
- Verify a fresh project exists in `~/Screen Studio Projects`.
- Verify the display track exists, usually at:

  ```text
  recording/channel-1-display-0.mp4
  ```

- Measure duration with `ffprobe`. Treat duration as informational unless the
  user explicitly asked for live sync.
- Generate and inspect a timestamp-based contact sheet.
- Reject the take if sampled frames show missing actions, wrong state, Codex,
  stale Screen Studio windows, wrong query text, address-bar suggestions,
  failed saves, missing connectors, or an incorrect final hold.
- Do not reject a complete take just because waits make it longer than the
  audio.
- Leave Screen Studio at the saved project state. Minimize the resulting project
  window before any additional recording.

Reusable frame-check pattern:

```bash
PROJECT="$HOME/Screen Studio Projects/name.screenstudio"
TRACK="$PROJECT/recording/channel-1-display-0.mp4"
OUT="/tmp/screencast-contact-sheet.jpg"
FRAME_DIR="/tmp/screencast-contact-frames"

rm -rf "$FRAME_DIR"
mkdir -p "$FRAME_DIR"

ffprobe \
  -v error \
  -show_entries format=duration \
  -of default=nk=1:nw=1 \
  "$TRACK"

for t in 0 15 30 60 90 120 150 180 210; do
  ffmpeg \
    -y \
    -ss "$t" \
    -i "$TRACK" \
    -frames:v 1 \
    -q:v 2 \
    "$FRAME_DIR/frame-$t.jpg" >/dev/null 2>&1
done

FILTER='scale=302:196:force_original_aspect_ratio=decrease'
FILTER="${FILTER},pad=302:196:(ow-iw)/2:(oh-ih)/2,tile=4x3"

ffmpeg \
  -y \
  -framerate 1 \
  -pattern_type glob \
  -i "$FRAME_DIR/frame-*.jpg" \
  -vf "$FILTER" \
  -frames:v 1 \
  "$OUT"
```

## Interaction Log

Keep a compact log while rehearsing and recording:

- Capture scope: full display.
- Window state: display, size, position, and coordinate validation.
- Starting state: app, URL or file, selected data, and visible panel.
- Rehearsal issues found and cleared.
- Final action sequence: coordinates, helper commands, typed text, and waits.
- Screen Studio project path and display-track duration.
- Contact sheet path, sampled timestamps, and keeper or rejection result.
- Screen Studio project windows minimized before subsequent recording.

## Recovery

- If Screen Studio or macOS asks for recording, microphone, camera, or
  accessibility permission, stop and ask the user to grant it.
- If the wrong display is selected, cancel before recording and reselect the
  correct display.
- If the picker is on window or selected-area capture, press
  `Command-Option-3` to switch back to full-display capture.
- If an unexpected modal appears during the final take, stop recording, clear
  the modal, reset the starting state, run another test pass, and record again.
- If the target window is the wrong size or position, ask the user to adjust it,
  then re-run coordinate calibration and dry rehearsal.
