---
name: screen-studio
description: Record repeatable macOS screencasts with Screen Studio. Use when Codex is asked to capture a screen recording, record a web app or product demo, rehearse a Screen Studio take, start or stop Screen Studio recording, choose full-display versus window capture, use Helium browser for clean web recordings, run test takes to clear first-time prompts, or document exact click/interaction locations before a final recording.
---

# Record Screen Studio Screencasts

## Overview

Use Screen Studio for recording. Optimize for a clean capture and a predictable final take; do not export or edit the video unless the user explicitly asks.

When asked to operate the Mac directly, use available desktop automation or Computer Use capabilities to control Screen Studio, Helium, and the target app. Use browser automation only for setup or verification inside a web page; the actual screencast should be captured from the visible Helium/browser window.

## Hard Gates

These requirements are not optional for keeper takes:

- Do not start a keeper until the full scripted interaction sequence has passed
  at least two dry runs without manual correction.
- If the Screen Studio start/stop path has not been proven in the current app
  state, run a short smoke capture first and verify it creates a fresh
  `.screenstudio` project with a readable display track.
- Do not proceed if Codex or unrelated workbench apps are visible in the capture
  area. Hide them before opening or starting Screen Studio capture.
- Do not proceed if old Screen Studio project/recording windows are visible.
  Minimize them first. The active "Start Recording" picker is allowed because
  it hides itself when capture starts.
- Do not resize or reposition target windows as part of recording setup. The
  user is responsible for approving window sizes and positions before recording;
  verify they are stable and work with the scripted coordinates.
- For logged-in browser flows, verify the signed-in destination immediately
  before recording. If the take redirects to a login page or exposes the wrong
  account state, reject it. Ask the user to verify the signed-in state before recording.
- Do not call a take a keeper until duration has been measured with `ffprobe`
  and a timestamp-based contact sheet has been inspected.

## Script and Audio Preparation

If the user provides an audio narration file and no complete screencast script, transcribe the audio before planning the recording. Use the transcript to create the original screencast script file or notes file that will drive the dry runs and keeper take.

- Identify the audio file path, measure its duration with `ffprobe`, and transcribe it with an available local transcription tool. If no transcription tool is available, tell the user what is missing and ask how they want to proceed.
- To discover local transcription tooling on this Mac, check the usual CLIs and
  Python packages before giving up:

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

  A known-good local path is `/opt/homebrew/bin/whisper-cli`, from
  `whisper.cpp`. If `whisper-cli` exists, find its cached model before running:

  ```bash
  find "$HOME/.cache/whisper.cpp" /opt/homebrew -maxdepth 5 \
    -name 'ggml-*.bin' 2>/dev/null
  ```

  The known-good model path on this Mac is
  `$HOME/.cache/whisper.cpp/ggml-base.en.bin`. Convert m4a files to wav because
  this `whisper-cli` build advertises wav/flac/mp3/ogg input:

  ```bash
  ffmpeg -y -i video.m4a -ar 16000 -ac 1 -c:a pcm_s16le /tmp/video.wav
  whisper-cli \
    -m "$HOME/.cache/whisper.cpp/ggml-base.en.bin" \
    -f /tmp/video.wav \
    -l en \
    -otxt -osrt -oj \
    -of /tmp/video-transcript
  ```

- Build a script file from the transcript with the audio source, duration, transcript notes, timeline cues, planned screen actions, setup/reset instructions, dry-run command sequence, state checks, and keeper notes.
- If the narration does not make the intended on-screen action clear, ask clarifying questions before writing or finalizing the script file. Examples: what app/page should be shown, what data should be searched, which filters should be used, whether to log in on camera, or where the take should end.
- Do not guess risky screen actions from vague narration. Make a conservative draft only after the user answers or the local context clearly establishes the intended product flow.
- Treat the script file as the living source of truth. After the first dry run, update it with the discovered `cliclick` commands, coordinates, waits, and expected visible states. After the second dry run, update it again with any corrections needed to make the command sequence pass.
- When the user asks for changes after a rehearsal or keeper take, update the script file with the new instructions and command changes before recording again.
- If a dry-run or keeper flow grows helper scripts, save those scripts beside the script/notes file in the local project rather than leaving them in `/tmp`. Temporary copies are fine while experimenting, but the reproducible command sequence must be versioned with the project before finishing.

## Human Cursor Control

Use `cliclick` for visible cursor movement during recorded interactions. Computer Use clicks are acceptable for setup and rehearsal, but they can look abrupt on camera; keeper takes should move the actual macOS pointer with human-paced motion.

- Check for `cliclick` before recording with `command -v cliclick`.
- If `cliclick` is missing, ask for action-time confirmation before installing it, for example with `brew install cliclick`.
- `cliclick` uses global macOS display coordinates, not Computer Use screenshot coordinates or browser/window-local coordinates. Do not pass a visible screenshot coordinate directly to `cliclick`.
- Retina screenshots from `screencapture` are usually physical pixels, while `cliclick` uses logical macOS points. On a 2x Retina display, a screenshot point must usually be divided by 2 before it can become a `cliclick` coordinate. Prefer recording coordinates from the live pointer or from window-origin math instead of copying screenshot pixels.
- Before using `cliclick`, activate the target app and get the front window's global position. Convert with `globalX = windowX + localX` and `globalY = windowY + localY`.
- Use this AppleScript pattern to read the front window origin and size:

  ```bash
  osascript \
    -e 'tell application "System Events" to tell process "Helium" to set {x, y} to position of front window' \
    -e 'tell application "System Events" to tell process "Helium" to set {w, h} to size of front window' \
    -e 'return (x as text) & "," & (y as text) & "," & (w as text) & "," & (h as text)'
  ```

- During rehearsals, capture the real global screen coordinates for each target and convert them into a `cliclick` script. Example: if Helium is at `184,50` and a target is around local `76,216`, click global `260,266`.
- Use `-e 300` as the current baseline for human-looking cursor speed in keeper takes. Keep pauses around the move so the viewer can see intent, for example `cliclick -e 300 -w 380 m:700,420 w:1000 m:260,266 w:750 c:.`.
- When calibrating cursor speed, keep the same start point, target point, and waits while changing only `-e`; this makes each test comparable.
- Prefer smooth movement commands before clicks, short waits before and after clicks, and don't move the cursor while narration is speaking.
- Use visible cursor movement for clicks and focus changes. Use AppleScript, keyboard shortcuts, or app-native typing only when they look natural and avoid brittle pointer work.
- For keeper-take typing that is visible on camera, type a little slower than
  normal automation. Prefer paced keystrokes with short per-character delays
  over instant paste or `cliclick t:` for long visible text. Clipboard paste is
  still fine for off-camera setup, config blocks, or flows where the typing
  itself is not part of the demo.
- Do not rely on browser automation, DOM clicks, or invisible app scripting for keeper-take interactions unless the user explicitly wants an automated-looking capture.

## Smooth List Scrolling

When a screencast should show a list, grid, or search result set being browsed,
add a human-looking scroll after the list first appears and after filters
or searches settle. Validate the scroll during dry runs before carrying it into a
keeper take.

- Focus the scrollable page or list first with a visible `cliclick` move/click.
  Choose a blank area inside the browser or app window that does not open an
  item, toggle a filter, or land outside the target window.
- Avoid edge coordinates near the desktop, browser border, widgets, or app
  chrome. Re-check the coordinate whenever the window is resized.
- Prefer small, repeated scroll increments with short delays over one large jump.
  The result should feel like a trackpad browse, not a page teleport.
- If wheel events or Swift/CGEvent scrolling do not reliably affect the target
  app, use repeated arrow-key events after focusing the scrollable area. This
  proved reliable in Helium for Paperless-style document grids.
- Return the list to a useful position before the next scripted click if the next
  target assumes the top of the results.

Use this helper in rehearsal scripts when arrow-key scrolling is the reliable
path:

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

Example sequence:

```bash
cliclick -e 300 m:1200,390 c:.
sleep 0.2
smooth_scroll_down_and_back 18 18 0.025
```

Record the working focus coordinate and tuned step counts in the script or notes
file. If the scroll opens a document, changes filters, summons macOS UI, or does
not move the intended list, fix the focus target and repeat the dry run before
recording.

## Coordinate Calibration and State Checks

Treat dry runs as data-gathering runs, not just timing runs. Every click target that will appear in the keeper take needs a recorded coordinate or a stable target description before the final recording starts.

- Use the first dry run as the discovery run. As soon as a click or typed interaction works, write the exact `cliclick` command, coordinate, wait, and expected visible result into the script or screencast notes file.
- Use the second dry run as the command-validation run. Execute the recorded `cliclick` commands from the script file, update any wrong coordinates or waits, and repeat until the script drives the app correctly.
- Only record the Screen Studio keeper after the recorded `cliclick` command sequence has passed a dry run without manual correction.
- Keep updating the script file after every dry run, failed take, user-requested change, or calibration fix so the next agent can reproduce the current best-known flow.
- During dry runs, perform each click, field focus, form submit, dropdown selection, and search exactly as planned, then record the actual `cliclick` coordinate that worked.
- After each click or form submission in a dry run, inspect the visible screen before continuing. Use `screencapture -x /tmp/name.png` plus image inspection, Computer Use state inspection, or a browser/app-specific check.
- Do not advance to the next scripted task until the app has visibly responded: the page navigated, the URL changed, the active page title changed, a result count updated, a filter chip appeared, a modal opened, or the expected element became visible.
- Required when switching between apps: after activating the next app, confirm
  the intended window is visible and frontmost before performing the next click,
  keystroke, paste, or menu action. Use Computer Use state inspection,
  `screencapture`, or a small AppleScript/window-title check. Do not rely on a
  fixed sleep alone after an app switch.
- When editing a config file on camera, verify the save reached disk before
  continuing. Use a structured check such as `jq -e` for JSON files, and reject
  the take if the editor reports a stale-file or save-conflict warning.
- When a recorded flow depends on a local connector, MCP server, extension, or
  background bridge process, verify it is actually loaded after app relaunch
  before submitting the on-camera query. Prefer a visible connector/tool state
  plus a process or API check over a fixed sleep.
- If the app does not respond, stop and fix the coordinate, focus target, wait time, or state reset in rehearsal. Do not carry an unverified click into a keeper take.
- For browser form flows, prefer explicit clicks on each field and submit button when focus is fragile. Use Tab only after a rehearsal proves it reliably focuses the next field.
- For pages with sticky footers, price summaries, final submit bars, or
  destructive/provisioning controls, focus and scroll from a safe blank/body
  area above the sticky control. Do not click the sticky footer just to focus
  the page.
- For dropdowns and autocomplete panels, capture coordinates for both the control and the selected option after the list is open. Re-check those coordinates if the window size, zoom, or data set changes.
- Add waits after navigation and search/filter actions, but verify with a screenshot or visible-state check during rehearsal rather than guessing a sleep duration.
- If keyboard shortcuts or special keys summon unexpected macOS UI during rehearsal, replace them with visible mouse movement, explicit clicks, or a safer app-native action before recording again.

## Screen Studio Shortcuts

Use these user-provided Screen Studio shortcuts unless the user says they changed:

- Start new recording picker / finish recording: Command + Control + Return.
- Resume or pause recording in progress: Command + Option + P.
- Restart recording in progress: Command + Option + Delete.
- Create recording flag: Command + Option + Control + F.
- Select/configure entire display: Command + Option + 3.
- Select/configure single window: Command + Option + 4.
- Select/configure area: Command + Option + 5.
- Show speaker notes: Command + Option + /.
- Start or stop prompter in speaker notes: Command + Option + Period.
- Show or hide recording controls: Command + Option + Apostrophe.

## Workflow

1. Confirm the capture scope.
   - If not provided with an audio file or a complete script, ask the user to describe the intended screen content and flow in detail before writing the script or planning the recording. Examples: what app/page should be shown, what data should be searched, which filters should be used, whether to log in on camera, or where the take should end.
   - Before starting Screen Studio recording, ask whether to record the full display or a specific window unless the user already said so.
   - If the user asks to record the entire screen, use full-display capture. Do not use Screen Studio's window picker for that take.
   - If recording a window, identify the exact app/window title to capture.
   - Confirm any requested microphone, system audio, or camera settings; otherwise leave recording inputs unchanged.

2. Prepare the target window.
   - For web recordings, use the Helium browser by default because its clean chrome looks better on camera. Use another browser only when the user asks or the workflow depends on a specific browser profile, extension, developer tool, or login state.
   - If the browser start state has become noisy, quit Helium completely and reopen it from scratch to the target URL during preflight. Avoid starting a keeper from an old Helium session with stale address-bar focus, selected URL text, selected page text, or leftover navigation state.
   - If the workflow depends on a signed-in web session, do not quit Helium
     after the user has logged in unless a dry run proves the session survives.
     Prefer keeping Helium open, closing extra tabs, setting the active tab URL
     directly, and verifying the signed-in destination just before recording.
   - Bring the app or Helium browser window to the foreground and put it in the state the demo should start from.
   - Open the target URL in Helium before rehearsals, then keep the same window, profile, zoom level, size, and position through the final take.
   - Do not use `Command+L` as the first visible browser action unless selecting the address bar is part of the intended demo. For clean openings, load the target URL off camera, then click safely in the page body before starting so the address bar is not focused or selected. For mid-recording site switches where the address bar is not part of the story, prefer opening the target URL through the app or automation path that does not visibly select the URL or show browser suggestions.
   - Do not resize or reposition the target window during setup. If the window
     size or position looks wrong for the recording, pause and ask the user to
     adjust it before continuing. After any user adjustment, re-run coordinate
     calibration and dry runs.
   - Required before every new recording: minimize any open Screen Studio
     recording/project windows before opening the picker, using a recording
     shortcut, or starting capture from a Screen Studio menu. Verify Screen
     Studio has zero non-minimized project/recording windows. The active
     Screen Studio "Start Recording" picker/window does not need to be hidden
     before recording; it hides itself when the recording starts. The active
     picker may appear to accessibility as windows named `Screen Studio`,
     `Start Recording`, an empty dialog, or `recording-manager-widget`; do not
     count those as stale project windows. If any old Screen Studio project
     window remains visible, stop and fix the window state before recording.
   - Required before every new recording: hide the Codex app and verify no Codex window is visible in the capture area or behind the target app. Do this before opening the Screen Studio picker and before the final take so Screen Studio does not highlight, preview, or capture Codex instead of the target app.
   - Hide non-target workbench apps such as VS Code, Finder, Safari, or old setup windows unless the current on-camera step intentionally uses them. On macOS, verify the visible process name when hiding apps; for example VS Code may appear as `Code`.
   - Required when not recording: restore the Codex window so the user can see what you are doing and thinking about. Only keep Codex hidden during the narrow pre-recording setup window and while the take is running.
   - Keep the user-approved window size, display, and position stable across
     rehearsals and the final take.

3. Run dry rehearsals before the keeper take.
   - Do at least two dry test runs before recording with Screen Studio. Use more runs if the app changes state, prompts appear, timing is uncertain, or the flow involves several interactions.
   - The first dry run is for discovery: find the working coordinates, waits, typed text, reset steps, and state checks. Write the resulting `cliclick` commands into the script or notes file while the discoveries are fresh.
   - The second dry run is for validation: run the recorded commands from the script or notes file and update them until the app reaches every expected state without manual correction.
   - Start Screen Studio only after the recorded command sequence has been validated in a dry run.
   - If the Screen Studio capture path itself is untested, run one very short Screen Studio capture test after the dry command sequence passes. Verify that the start path creates a saved project before using it for the keeper.
   - During rehearsals, intentionally trigger the same clicks, typing, navigation, and pauses planned for the final take.
   - After each click, field edit, form submit, and navigation during dry runs, inspect the screen and confirm the app actually changed state before continuing to the next task.
   - Dismiss first-time prompts, permission dialogs, cookie banners, update notices, focus warnings, or other one-off UI before the final take.
   - Record the exact click targets and interaction sequence as coordinates or stable UI descriptions. Prefer coordinates when using desktop automation; include enough context to reproduce each click and the visible state that proves it worked.
   - Build or update a `cliclick` rehearsal script for the visible cursor path. Include waits, typed text, and reset steps so the final take feels hand-driven instead of machine-driven.
   - If matching an audio track or narration script, measure the rehearsal recording duration and adjust the opening, per-section, and ending pauses before recording the keeper take. The raw recording should try to land close to the audio length, but it does not have to be perfect because editing can speed up or slow down specific sections later. Long waits such as a Claude query or page load can be accelerated in the edit if the screen content is otherwise correct.
   - Reset the app to the desired starting state after each rehearsal.

4. Configure Screen Studio.
   - Required pre-recording gate: minimize all existing Screen Studio
     recording/project windows before starting a new recording. Do this even
     when using keyboard shortcuts or the Record menu, because an old Screen
     Studio project window can otherwise become the first visible thing in the
     new capture. Count or inspect Screen Studio windows after minimizing; zero
     non-minimized Screen Studio project/recording windows is required. Do not
     count the active "Start Recording" picker/window as a stale project
     window; it may remain visible while configuring the take because it hides
     itself when recording starts.
   - Required pre-recording gate: hide Codex and confirm it is not visible anywhere in the recording view. If Codex remains visible behind the target app, stop and clean up the window state before recording.
   - Open or foreground Screen Studio, or use Command + Control + Return to open the new recording picker.
   - Choose full display or window capture based on the confirmed scope. Prefer Command + Option + 3 to select/configure entire-display capture and Command + Option + 4 to select/configure single-window capture.
   - Use Command + Option + 5 only if the user explicitly asks to record a selected area.
   - Verify the selected display/window is the intended one before starting.
   - The Screen Studio menu path and capture shortcuts may only configure the
     picker; they are not proof that recording has started. Click the visible
     purple "Start recording" button in the picker and verify a short smoke
     capture creates a fresh project before using that start path for a keeper.
     On the built-in Retina display, the latest working full-display start
     coordinate was `m:757,547 c:.`, after selecting display capture at
     `m:420,905 c:.`.
   - It is acceptable to start recording with the Screen Studio UI after the picker is configured.
   - The Screen Studio recording widget is configured to stay hidden during recording, so do not rely on the widget for stopping a take.
   - Start recording only after the target window is user-approved, rehearsals
     have cleared unexpected UI, existing Screen Studio project windows are
     minimized, and Codex is hidden from the recording view.

5. Perform the final take.
   - Start recording in Screen Studio, either from the configured Screen Studio UI or with the appropriate shortcut.
   - Wait a short beat before interacting with the target app.
   - Follow the rehearsed click/typing/navigation sequence exactly, using `cliclick` for visible pointer movement wherever practical.
   - Wait a short beat at the end, then stop the recording with Command + Control + Return. The recording widget is hidden, so do not expect a visible stop control.
   - After recording stops, restore Codex so the user can see verification work, notes, and any recovery steps.
   - After stopping, verify Screen Studio created a fresh project in `~/Screen Studio Projects` and that the recording folder contains a display track such as `recording/channel-1-display-0.mp4`.
   - When matching narration, use `ffprobe` or Screen Studio's project metadata to compare the raw display-track duration with the target script/audio length. Re-record if the timing is materially short, rushed, or missing required screen beats. If the recording is a little long because one section waited on a response or page load, note that the section can be sped up in editing instead of automatically discarding the take.
   - Required post-take review: generate a timestamp-based contact sheet from the saved display track and inspect it before calling the take a keeper. Sample by elapsed time, not by raw frame number, so the review covers the beginning, middle, end, and scripted transitions.
   - For repo-managed screencasts, add a helper script for the frame review alongside the actions file, for example `video-scripts/<nn>-<slug>-check-frames.sh`, and record the command plus contact sheet path in the notes file.
   - Zoom or open individual sampled frames around risky transitions such as app switches, settings/config edits, browser URL changes, Claude/tool responses, response scrolling, and ending holds. Reject the take if the samples show Screen Studio/Codex in the capture, stale windows, address-bar suggestions, selected URL/page text, failed saves, missing connectors, wrong query text, or an incorrect final state.
   - A reusable frame-check command pattern is:

     ```bash
     PROJECT="$HOME/Screen Studio Projects/Built-in Retina Display YYYY-MM-DD HH:MM:SS.screenstudio"
     TRACK="$PROJECT/recording/channel-1-display-0.mp4"
     OUT="/tmp/screencast-contact-sheet.jpg"
     FRAME_DIR="/tmp/screencast-contact-frames"

     rm -rf "$FRAME_DIR"
     mkdir -p "$FRAME_DIR"
     ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 "$TRACK"
     for t in 0 15 30 60 90 120 150 180 210; do
       ffmpeg -y -ss "$t" -i "$TRACK" -frames:v 1 -q:v 2 \
         "$FRAME_DIR/frame-$t.jpg" >/dev/null 2>&1
     done
     ffmpeg -y -framerate 1 -pattern_type glob -i "$FRAME_DIR/frame-*.jpg" \
       -vf "scale=302:196:force_original_aspect_ratio=decrease,pad=302:196:(ow-iw)/2:(oh-ih)/2,tile=4x3" \
       -frames:v 1 "$OUT"
     ```

   - Leave Screen Studio at the saved recording state. Minimize the resulting Screen Studio project window before any additional recording. Do not export, trim, upload, or share unless the user asks.

## Interaction Log

Keep a compact log while rehearsing and recording:

- Capture scope: full display or specific window.
- Window state: user-approved size/position, display, and whether coordinates
  were revalidated after any change.
- Starting state: app, URL/file, selected data, and visible panel/tab.
- Rehearsal issues found and cleared.
- Final interaction sequence: click coordinates or stable UI targets, pointer movement notes, typed text, waits, and stop action.
- Recording result: whether the final take completed, the saved project path, the measured duration when relevant, and where Screen Studio left it.
- Frame review result: contact sheet path, sampled timestamps, issues found, and whether the take is keeper or rejected.
- Screen Studio project windows minimized before any subsequent recording.

## Recovery

- If Screen Studio or macOS asks for screen recording, microphone, camera, or accessibility permission, stop and ask the user to grant it if automation cannot proceed.
- If the wrong display/window is selected, cancel before recording and reselect the correct target.
- If an unexpected modal appears during the final take, stop the recording, clear the modal, reset the starting state, run another test pass, and then record again.
- If the target window is the wrong size or position, do not improvise the
  final take. Ask the user to adjust it, then re-run coordinate calibration and
  dry rehearsal.
