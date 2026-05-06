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
- Start the status server before any dry runs and share the Bonjour and LAN
  URLs in chat. See [Recording Status Server](#recording-status-server).

## Recording Status Server

This skill ships a tiny self-contained status server so the user can monitor a
take live from a phone, tablet, or another computer on the same network.

The server is a precompiled universal macOS binary at:

```text
screen-studio/server/status-server
```

It has zero runtime dependencies (no Python, Node, Go, or Homebrew needed).

### Starting the server

Run the binary in the background and bind to all interfaces (the binary already
binds `0.0.0.0` by default):

```bash
"$SKILL_DIR/server/status-server" --port 8765 &
```

`$SKILL_DIR` is the path to this skill's directory. The default port is `8765`;
pass `--port N` to change it.

On startup the server prints a banner block to stdout containing:

- A randomly-generated **4-digit PIN** (different every run; required to
  access the page from a non-localhost device).
- The Bonjour URL with `?pin=XXXX` embedded (e.g. `http://Brians-Mac-mini.local:8765/?pin=4827`).
- The LAN IP URL with `?pin=XXXX` embedded.
- A **QR PNG file path** (e.g. `/var/folders/.../T/screen-studio-status-qr.png`)
  written to disk at startup so chat clients can render a real PNG.
- An ASCII QR code (terminal use only — see the next paragraph).

**Sharing the page in chat:**

1. Read the banner from the server's stdout.
2. Reply with the URLs and PIN, then embed the QR PNG using a markdown image
   link pointing at the file path from the banner. Example:

   ```markdown
   Recording status page is live. **PIN: 4827.**
   - Scan: ![Screen Studio QR](/var/folders/xx/T/screen-studio-status-qr.png)
   - Bonjour: http://Brians-Mac-mini.local:8765/?pin=4827
   - LAN IP:  http://192.168.68.201:8765/?pin=4827
   ```

3. **Do NOT try to repeat the ASCII QR from the banner in chat.** Most chat
   clients use a different font and line width than the terminal, so the
   blocks rearrange and the code stops scanning. Always embed the PNG file
   from the banner instead.

The PIN auto-applies on first load via the URL query, then the page stores it
as a cookie and strips it from the address bar. Localhost requests from the
agent's own CLI calls (update / status / notes) bypass auth automatically.

Detect the values programmatically when needed:

```bash
curl -s http://127.0.0.1:8765/api/lan
# {"agent":"Codex","bonjour":"Brians-Mac-mini.local",
#  "ips":["192.168.68.201"],"preferred":"192.168.68.201","port":8765}
```

If `preferred` is empty (no usable LAN IPv4), still share the Bonjour URL and
PIN, but the QR will not be useful from outside the host machine.

### Pushing status updates

Update status at every meaningful transition. The same binary doubles as a
client:

```bash
# Mark prep, set the project name, and clear any stale log:
"$SKILL_DIR/server/status-server" update \
  --phase preparing \
  --project "checkout-demo" \
  --action "Helium opened to /cart" \
  --reset-log

# Mark the actual recording start (sets started_at and elapsed clock):
"$SKILL_DIR/server/status-server" update \
  --phase recording \
  --action "Pressed Return to start"

# Append actions during the take:
"$SKILL_DIR/server/status-server" update --action "Clicked Submit"
"$SKILL_DIR/server/status-server" update --action "Waiting for upload"

# Mark stop:
"$SKILL_DIR/server/status-server" update \
  --phase stopped \
  --action "Stop hotkey pressed" \
  --clear-started-at

# Free-form note (e.g. for the user to see from across the room):
"$SKILL_DIR/server/status-server" update --note "Hands off the keyboard"
```

Phases: `idle`, `preparing`, `recording`, `stopped`, `error`. The page color
codes the badge: red pulse for `recording`, amber for `preparing`, green for
`stopped`, gray for `idle`, red for `error`. The elapsed clock starts when the
phase first transitions to `recording` and freezes when it leaves `recording`
or `preparing`.

### When to update during the workflow

The user is watching the page from another device. **Silence on the page reads
as "stalled" or "broken"**, even when the agent is busy thinking. Push action
updates often enough that the page never goes more than ~30 seconds without a
new line during active work. The exception is the final take itself, where
updates correspond to scripted steps (one update per step, no thinking-out-loud
narration that doesn't match a visible event).

- **Server start:** push `phase=preparing` with the project name. Push
  `action="Reset stale state"` or similar so the first line on the page
  isn't the placeholder.
- **During dry runs and discovery — push frequently.** This is investigative
  work; the user benefits from seeing what you're poking at. Aim for an
  update every meaningful step: each app you activate, each coordinate you
  measure, each helper you build, each thing you click to verify. Use
  present-continuous descriptions in the `--action` text so the page reads
  like a live status feed, e.g.:

  ```bash
  status-server update --action "Locating Document link in left nav"
  status-server update --action "Reading window origin via osascript"
  status-server update --action "Confirming button coordinates with cliclick"
  status-server update --action "Discovering how to upload document"
  status-server update --action "Drafting smooth-scroll helper"
  status-server update --action "Verifying Helium session is logged in"
  status-server update --action "Dismissing first-time prompt"
  ```

  Don't narrate every individual thought — group small steps into the action
  they belong to. A good rhythm is one update per investigation finding, app
  switch, coordinate set, or helper script written. If the agent has been
  silent on the page for 30+ seconds and is still working, push something.

- **Hard gates check:** push `action="Hard gates verified"` once gates pass.
- **Final take start:** push `phase=recording` immediately after pressing
  `Return` to start Screen Studio. The pulse on the page is the user's
  confirmation the take actually began.
- **Each scripted action during the take:** push one update per scripted
  helper command — that's it. The take itself should NOT have the same
  density of updates as dry runs; one entry per visible on-camera step
  keeps the keeper-take log clean for the post-take debrief.
- **Long waits:** push `action="Waiting for upload (N seconds)"` so the user
  on the other device understands the apparent pause.
- **Stop:** push `phase=stopped` immediately after `Command-Control-Return`.
- **Errors / takes rejected after frame review:** push `phase=error` with a
  short reason (e.g. `action="Rejected: Codex visible in frame 90"`).

Never block on the update call. If the server is down for any reason, log it
locally and continue the take — the recording is the source of truth.

### Notes from the user

The status page has a "Send a note to {{Agent}}" form. The user types
observations or questions while watching the take from a phone or another
device, and each note arrives at the server stamped with both wall-clock time
and a **take-relative offset** (milliseconds since `started_at`). Notes are
queued; the recording is **not** interrupted to acknowledge them.

Each note has two server-tracked states:

- **queued** — user sent it, agent has not acknowledged it yet. Page shows
  a green "queued for {{Agent}}" badge.
- **consumed** (a.k.a. seen) — agent has fetched it and confirmed it. Page
  shows a blue ✓ "seen by {{Agent}}" badge with the timestamp.

The CLI verb that flips queued → consumed is `notes --clear` — despite the
name, this **does not delete** the notes; it just stamps `consumed_at` so
the page can keep showing the user that {{Agent}} has seen them. Use
`notes --purge` only when you want to truly wipe history. The default
`notes` (no flags) lists only queued notes; pass `--all` to include
already-consumed ones.

**When to poll for notes:**

The agent must check for queued notes — and surface them in chat — at every
natural pause in the workflow. Polling at these points reassures the user
that their input was received, and gives the agent a chance to act on
feedback before doing more work.

- **Between dry runs.** Before starting dry run N+1, run
  `status-server notes --clear`, surface any new notes in chat, and decide
  whether they affect the rehearsal plan (e.g. "you forgot to hide Codex" →
  fix the window setup before the next dry run).
- **Between attempted recordings.** After a take is stopped (whether kept,
  rejected, or aborted) and before starting the next take, run
  `status-server notes --clear` and address each note. A common case: the
  user noticed a problem during the take that you should fix before the next
  attempt.
- **During a take, between scripted actions.** Poll with
  `status-server notes --since-id <last_seen_id>` (no `--clear`) and silently
  log them. **Do not type a chat reply mid-take** — keystrokes can corrupt
  the recording (focus changes, audible noise, broken cursor scripts). The
  page already shows the user a "📨 Queued for {{Agent}}" receipt; that is
  the acknowledgement.
- **Post-take debrief.** Run `status-server notes --clear --all`. The
  `--all` includes notes already consumed earlier in the take cycle so the
  debrief covers the whole take. Surface every note with:
  - The note text in a quote.
  - The take-relative offset formatted as `mm:ss`.
  - A direct response: answer questions by inspecting the relevant frames in
    the contact sheet at the matching timestamp; treat feedback as a request
    that may justify a re-take.

Always `--clear` (mark consumed) when surfacing notes in chat — that flips
the page badge from "queued" to "seen", letting the user know {{Agent}} got
them.

Sample post-take note debrief in chat:

> You sent two notes during the take:
>
> 1. **+0:27** — "The cursor moved too fast across the search box."
>    Looking at the contact sheet at 0:27, the cursor crosses the search box
>    in ~150ms. I can drop that to ~400ms by raising the `cliclick -e` value
>    on the search-box helper. Want me to retake?
> 2. **+1:12** — "Did the email confirmation render before I clicked Next?"
>    Yes — at 1:12 the green "Email sent" toast is fully on-screen for
>    ~600ms before the click on Next. Take is good on that point.

### Stopping the server

Leave the server running across multiple takes in a session. Stop it at the
end of the session with `kill %1` (or whatever job control matches how it was
started). The state is in-memory only; a restart resets the page to `idle`
with an empty log.

### Hard gate addition

Announcing the Bonjour / LAN URL is a hard gate: do not start dry runs until
the URL has been shared in chat. The point of the server is the second screen,
and the user can't open it if they don't know where to go.

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

**Pace.** Scrolls should feel like a person reading, not a machine skimming.
Aim for a single down-burst that lasts roughly **1.2–1.6 seconds** (long enough
that a viewer can register what's on screen as it passes), with at least
**0.4–0.6 seconds** of pause at the bottom before scrolling back. Avoid many
short, quick bursts — one slower, longer burst reads as deliberate; several
quick bursts read as nervous or stalled.

The helper defaults below produce ~1.4s down-bursts; tune `delay` (per-key
pause) up rather than adding more bursts if a take feels rushed.

Reusable helper:

```bash
smooth_scroll_down_and_back() {
  local down_steps="${1:-32}"
  local up_steps="${2:-24}"
  local delay="${3:-0.045}"
  local pause="${4:-0.45}"

  osascript <<APPLESCRIPT
tell application "System Events"
  repeat ${down_steps} times
    key code 125
    delay ${delay}
  end repeat
  delay ${pause}
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
smooth_scroll_down_and_back 32 24 0.045 0.45
```

For a slower, more documentary pace (e.g. for a long settings page where
the user needs to read each row), try `smooth_scroll_down_and_back 40 30 0.06 0.6`.

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
- Push `phase=recording` to the status server immediately after pressing
  `Return`, then push one `--action` line per scripted step.
- Run the rehearsed helper commands or manual steps when the UI is ready.
- Wait as long as needed for uploads, processing, search, loading, or responses.
- Capture every expected action and final state clearly.
- Wait a short beat at the end.
- Stop Screen Studio with `Command-Control-Return`.
- Push `phase=stopped` to the status server right after the stop hotkey.

After stopping:

- Restore Codex.
- Run `status-server notes --clear` and surface every note in chat with its
  take-relative offset, answering questions and reacting to feedback. See
  [Notes from the user](#notes-from-the-user).
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

- If a take is rejected after frame review, push `phase=error` to the status
  server with a short reason
  (`status-server update --phase error --action "Rejected: Codex visible in frame 90"`).
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
