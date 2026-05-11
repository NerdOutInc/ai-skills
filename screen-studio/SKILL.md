---
name: screen-studio
disable-model-invocation: true
description: >
  Record repeatable macOS full-display screencasts with Screen Studio. Covers
  the full workflow: setup, dry runs, keeper recording, and post-take
  verification. Use when asked to capture a screen recording, record a product
  demo, or run Screen Studio takes. Does not support window or selected-area
  capture.
---

# Record Screen Studio Screencasts

## Scope

**Recording tool and capture mode.** Use Screen Studio for recording. This skill records the full display only. Do
not offer or use window capture or selected-area capture. Do not export, trim,
upload, or edit the video yourself unless the user explicitly asks. (The user
may trim or retime footage in post-production on their own.)

**Automation boundaries.** Use desktop automation for Screen Studio, Helium, and the target app. Computer
Use is acceptable for inspection and off-camera setup, but do not use Computer
Use to start or stop Screen Studio for a keeper take. Its cursor overlay can
appear in the captured screen.

Browser automation (DOM clicks, invisible scripting) is acceptable for
off-camera setup or verification inside a page, but must not be used for
keeper-take interactions unless the user explicitly wants an automated-looking
capture. The actual screencast should be captured from the visible app or
Helium window.

**Timing.** Audio timing is not required. Treat audio duration as a guide to the expected
story beats. The recording just needs to capture each required action clearly.
If the UI needs time to load, index, upload, or respond, wait. Post-production
timing adjustments are the user's responsibility.

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
binds `0.0.0.0` by default). **Always pass `--agent` with your own name** so
the page UI says "Send a note to Codex" / "queued for Claude" instead of the
generic fallback "the agent":

```bash
"$SKILL_DIR/server/status-server" --port 8765 --agent Codex &
```

Use the name of the chat agent you are running as: `Codex` for Codex,
`Claude` for Claude Code, etc. The `--agent` flag accepts spaces if quoted
(e.g. `--agent "Claude Code"`).

`$SKILL_DIR` is the path to this skill's directory. The default port is `8765`;
pass `--port N` to change it. If `--agent` is omitted, the page falls back to
the literal string "the agent" — this is the giveaway that the flag was
forgotten on startup.

On startup the server prints a banner block to stdout containing:

- A randomly-generated **4-digit PIN** (different every run; required to
  access the page from a non-localhost device).
- The Bonjour URL with `?pin=XXXX` embedded (e.g. `http://Brians-Mac-mini.local:8765/?pin=4827`).
- The LAN IP URL with `?pin=XXXX` embedded.
- A **unique QR PNG file path** (e.g.
  `/var/folders/.../T/screen-studio-status-qr-8765-4827-*.png`) written to disk
  at startup so chat clients can render a real PNG. The path changes on every
  server start; always use the newest banner's path.
- An ASCII QR code (terminal use only — see the next paragraph).

**Sharing the page in chat:**

1. Read the banner from the server's stdout.
2. Reply with the URLs and PIN, then embed the QR PNG inline after a short
   `Scan:` label. In Codex chat this renders larger inline than a standalone
   markdown image, while HTML image tags render as literal text. Use the file
   path from the current banner. Example:

   ```markdown
   Recording status page is live. **PIN: 4827.**

   - Scan: ![Screen Studio QR](/var/folders/xx/T/screen-studio-status-qr-8765-4827-abc.png)
   - Bonjour: http://Brians-Mac-mini.local:8765/?pin=4827
   - LAN IP: http://192.168.68.201:8765/?pin=4827
   ```

3. If the QR still appears too small inline, use the local image viewer tool on
   the QR PNG path with original detail; that renders the QR large in the
   thread. Keep the URLs and PIN in the assistant message because tool-rendered
   images may not be visible in every client.

4. If a larger click-to-open image is useful, create a wide "QR card" PNG and
   embed that card with the same `Scan:` markdown pattern. Preserve sharp
   edges by scaling the QR with nearest-neighbor filtering:

   ```bash
   ffmpeg -y \
     -i "$QR_PATH" \
     -filter_complex "[0:v]scale=840:840:flags=neighbor[qr];color=white:s=1600x900[bg];[bg][qr]overlay=(W-w)/2:(H-h)/2" \
     -frames:v 1 \
     /tmp/screen-studio-status-qr-card.png
   ```

   Then embed:

   ```markdown
   Scan: ![Screen Studio QR](/tmp/screen-studio-status-qr-card.png)
   ```

5. After sending the status server info with the URLs, PIN, and QR code, pause
   for **20 seconds** before starting the first dry run or any recording setup.
   This gives the user time to scan the code and open the status page on a
   second device.
6. **Do NOT reuse a QR PNG path from a previous server run.** The PIN changes
   on restart, and a stale QR image sends the user to an old `?pin=` URL.
7. **Chat clients vs. terminal clients — pick the right QR format.**
   - **Chat clients (Codex Desktop, web UIs, etc.):** always embed the PNG
     via the `Scan: ![...](path)` markdown above. Do **not** paste the
     half-block ASCII QR from the banner — most chat clients use a
     proportional or differently-spaced monospace font and the blocks
     rearrange so the code stops scanning.
   - **Terminal clients (Claude Code in Terminal.app/iTerm2, SSH sessions,
     anything where the markdown image embed renders as a literal path
     instead of an actual image):** the half-block ASCII QR from the banner
     *is* the right answer. Paste it verbatim inside a fenced code block so
     the renderer keeps it monospace and doesn't re-wrap it. Example:

     ````markdown
     Recording status page is live. **PIN: 4827.**

     - Bonjour: http://Brians-Mac-mini.local:8765/?pin=4827
     - LAN IP:  http://192.168.68.201:8765/?pin=4827

     Scan with your phone:

     ```
     <paste the half-block ASCII QR block from the banner here, exactly as
     printed — preserve leading spaces and line breaks>
     ```
     ````

     The half-block format (▀▄█) renders square-ish in any standard
     monospace font and scans well from a few feet away. If the user reports
     the code won't scan, the next fallback is `open <qr-png-path>` (macOS
     only) which launches Preview with the actual image — this always works
     when a GUI is available.

The PIN auto-applies on first load via the URL query, then the page stores it
as a cookie and strips it from the address bar. Localhost requests from the
agent's own CLI calls (update / status / notes) bypass auth automatically.
If the server restarts with a new PIN, the fresh `?pin=...` link replaces any
stale `ss_pin` cookie from an older run.

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

**Every `update` response carries any unread notes from the page.** The JSON
returned by `status-server update` looks like the regular status snapshot
plus a top-level `notes` array of any notes the user has sent that the agent
has not yet seen. Those notes are marked consumed server-side as part of the
same call — the page badges flip from "queued for {{Agent}}" to "seen by
{{Agent}}" on its next poll. **The agent must read the output of every
`update` call and act on any notes it returns** before continuing. Do not
redirect the output to `/dev/null`, swallow it with `2>&1 || true`, or
otherwise drop it; if you do, the page will show "seen" while the agent has
not actually seen the note. See [Notes from the user](#notes-from-the-user)
for what "act on" means at each phase.

### When to update during the workflow

The user is watching the page from another device. **Silence on the page reads
as "stalled" or "broken"**, even when the agent is busy thinking. Push action
updates often enough that the page never goes more than ~30 seconds without a
new line during active work. The exception is the final take itself, where
updates correspond to scripted steps (one update per step, no thinking-out-loud
narration that doesn't match a visible event).

The same cadence also bounds how quickly the agent picks up notes the user
sent from the page. Notes only surface in the response of an `update` call —
this is **not** an async interrupt. If you don't push an update, the agent
won't see the note. Treat the ~30-second silence rule as a hard ceiling on
note latency too: any stretch of work longer than that needs at least one
heartbeat update to flush the note channel.

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
- **Each scripted action during the take:** push one update **before** the
  scripted helper command runs — that's the natural interrupt point. If the
  user has just sent a note ("stop, the cursor is in the wrong spot") it
  comes back in that response and the agent can abort or adjust before the
  on-camera action fires. One update per visible on-camera step is still
  enough density; the take log stays clean for the post-take debrief.
- **Long waits:** push `action="Waiting for upload (N seconds)"` so the user
  on the other device understands the apparent pause. Long waits are also
  the highest-risk window for missed notes (no scripted action is firing,
  so no update is naturally scheduled). If a wait is going to exceed ~30s,
  push at least one mid-wait update so any note like "this is hung, stop"
  reaches the agent.
- **Stop:** push `phase=stopped` immediately after `Command-Control-Return`.
- **Post-take verification and contact-sheet review:** keep updating the
  status server while verifying the recording. Contact-sheet analysis can take
  long enough to look stalled from the second screen, so push one action before
  each meaningful verification step and each finding, e.g.:

  ```bash
  status-server update --phase stopped --action "Measuring display-track duration"
  status-server update --phase stopped --action "Generating timestamp contact sheet"
  status-server update --phase stopped --action "Inspecting frame 0:45 for search result state"
  status-server update --phase stopped --action "Checking final frame for expected hold"
  status-server update --phase stopped --action "Frame review passed; take looks like a keeper"
  ```

  The final status update before stopping the server must be the verdict:
  whether the recording looks like a keeper or must be rejected/retaken.

- **Errors / takes rejected after frame review:** push `phase=error` with a
  short reason (e.g. `action="Rejected: Codex visible in frame 90"`).

Never block on the update call. If the server is down for any reason, log it
locally and continue the take — the recording is the source of truth.

### Notes from the user

The status page has a "Send a note to {{Agent}}" form. The user types
observations or questions while watching the take from a phone or another
device, and each note arrives at the server stamped with both wall-clock time
and a **take-relative offset** (milliseconds since `started_at`). Notes ride
back to the agent on the next `update` response (see
[Pushing status updates](#pushing-status-updates)) — there is no separate
poll.

Each note has two server-tracked states the page renders as a badge:

- **queued** — user sent it, agent has not run an `update` yet. Page shows
  a green "queued for {{Agent}}" badge.
- **consumed** (a.k.a. seen) — the agent ran an `update` that returned the
  note. Page shows a blue ✓ "seen by {{Agent}}" badge with the timestamp.

The flip from queued → consumed happens automatically when the next
`update` returns the note in its `notes` array. There is no separate
"clear" step in the normal workflow.

**Reading update output is mandatory.** Because `update` is what consumes
notes, dropping its stdout is the same as ignoring the user. Capture and
inspect the response on every call. The agent has not "seen" a note until
it has actually parsed the JSON and read the `text` field.

**Responding by phase:**

- **Before a take (server start, dry runs, between rehearsals, between
  takes).** Surface every note returned by the update in chat. Quote the
  text and act on it: fix the rehearsal plan, adjust window setup, answer
  the question before the next dry run, etc. This is also where most notes
  arrive in practice — the user is watching the prep and flagging things to
  fix before recording.
- **During a take (`phase=recording`).** Notes still come back on every
  update. Act on directives immediately:
  - "stop, this is broken" / "abort" → press `Command-Control-Return`,
    push `phase=stopped --action "Aborted on user note"`, then surface the
    note text in chat after the take has stopped.
  - "skip this step" / "wait longer" → adjust the next scripted action.
  - Questions or observations that don't require action → log silently and
    answer in the post-take debrief.

  **Do not type long chat replies while the take is still rolling** —
  verbose narration adds focus changes and noise that can land in the
  recording. Take the requested action, keep chat output to the minimum
  needed to confirm it, and save the full response for after stop.
- **Post-take debrief.** By the time the take has stopped, every note from
  the run has already been delivered via update responses; the agent
  already has them in conversation context. Surface each one in chat with:
  - The note text in a quote.
  - The take-relative offset formatted as `mm:ss`.
  - A direct response: answer questions by inspecting the relevant frames
    in the contact sheet at the matching timestamp; treat feedback as a
    request that may justify a re-take.

If the agent suspects an update response was lost (server was down, network
hiccup, output got dropped), `status-server notes --all` is a manual
fallback that re-lists every note on record (consumed and unconsumed). It
does not change state. The primary path is still the `update` response.

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

Leave the server running across multiple takes in a session. Before stopping it
at the end of the session, push a final verdict update that says whether the
latest recording is a keeper or why it is rejected. Then stop the server with
`kill %1` (or whatever job control matches how it was started). The state is
in-memory only; a restart resets the page to `idle` with an empty log.

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

Run the bundled helper:

```bash
python3 "$SKILL_DIR/scripts/transcribe_narration.py" \
  narration.m4a \
  --out /tmp/screen-studio-transcript
```

The helper uses local whisper.cpp. On macOS with Homebrew, it can automatically
install `ffmpeg` and `whisper-cpp` when missing. It downloads
`$HOME/.cache/whisper.cpp/ggml-base.en.bin`, converts the audio to 16 kHz mono
WAV, and writes `/tmp/screen-studio-transcript/transcript.json` plus raw
`whisper.txt`, `whisper.srt`, and `whisper.json` files. Pass `--no-install`
in locked-down environments or when dependencies must be preinstalled manually.

Create or update the actions file with:

- Audio path, duration, and transcript cues from `transcript.json`.
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

- Before first use, ensure `cliclick` is available:

  ```bash
  CLICLICK="$(python3 "$SKILL_DIR/scripts/ensure_cliclick.py")"
  ```

  On macOS with Homebrew, the helper can automatically install `cliclick` when
  missing. Pass `--no-install` in locked-down environments.
- `cliclick` uses global macOS display coordinates.
- Do not pass Computer Use or screenshot coordinates directly to `cliclick`.
- Prefer live pointer coordinates when possible. Put the pointer over the
  target, then read the exact `cliclick` coordinate with:

  ```bash
  "$CLICLICK" p:.
  ```

- If using a screenshot, convert from screenshot pixels to global logical
  display coordinates before calling `cliclick`. Retina screenshots are usually
  physical pixels; `cliclick` uses logical points. On a 2x Retina display,
  divide screenshot coordinates by 2.
- For text targets visible in a screenshot, use Apple Vision instead of
  eyeballing coordinates. The helper script prints the recognized screenshot
  pixel bounds and the converted `cliclick` coordinate:

  ```bash
  screencapture -x /tmp/screen.png
  "$SKILL_DIR/scripts/vision-find-text.swift" /tmp/screen.png "Workflows"
  ```

  Example output:

  ```text
  text        screenshot_x  screenshot_y  screenshot_w  screenshot_h  center_x  center_y  cliclick_x  cliclick_y  confidence
  Workflows   448           1213          149           26            523       1226      261         613         1.000
  ```

  Click the `cliclick_x,cliclick_y` value, then take another screenshot to
  verify the expected UI state.

- Apple Vision finds visible text, not arbitrary UI structure:
  - For links, sidebar items, menu items, buttons with text, labels, and
    placeholder text, use Apple Vision directly on the visible text.
  - For a text input with a visible label but no placeholder, find the label
    text with Apple Vision, then click the input area next to or below that
    label. Verify focus with a screenshot before typing.
  - For a text input with no visible label and no placeholder, Apple Vision
    cannot identify the input by itself. Use a live pointer read, accessibility
    metadata, or screenshot geometry, then verify focus with a screenshot.
  - For icon-only buttons without visible text or accessible labels, Apple
    Vision cannot identify the button semantically. Use nearby text as an
    anchor if available, otherwise use a live pointer read, accessibility
    metadata, or screenshot geometry. Always verify the click with a screenshot.
- Only use window-relative math as a rare fallback when the target point was
  intentionally measured relative to a window, or when coordinates must survive
  the window moving. In that case, document both the window origin and the
  relative point, then add them to get the global `cliclick` coordinate.

For the rare window-relative fallback, read the front Helium window origin and
size with:

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
brittle pointer work. For keeper interactions, follow the browser-automation
rule in the Scope section above.

For visible typing, type a little slower than normal automation. Prefer paced
keystrokes over instant paste unless typing is not part of the demo.

## Scrolling

When showing a list, grid, or search result set, add a human-looking scroll.
Validate the scroll during dry runs.

- Focus a safe blank area inside the scrollable app first.
- Avoid browser borders, desktop edges, sticky footers, and app chrome.
- Prefer real scroll-wheel/trackpad-style events over keyboard scrolling.
- Prefer small repeated scroll increments over one large jump.
- Use repeated arrow-key events only as a fallback after wheel events are
  proven unreliable. Arrow keys often look jumpy and may not move far enough.
- Return the list to a useful position before the next scripted click.

**Pace.** Scrolls should feel like a person reading, not a machine skimming.
Aim for a single down-burst that lasts roughly **1.2–1.6 seconds** (long enough
that a viewer can register what's on screen as it passes), with at least
**0.4–0.6 seconds** of pause at the bottom before scrolling back. Avoid many
short, quick bursts — one slower, longer burst reads as deliberate; several
quick bursts read as nervous or stalled.

The helper defaults below produce visible wheel-based motion. Tune `delay`
or `delta` rather than switching to Page Down or arrow keys if a take feels
rushed. If the story needs a full browse of a page, scroll down slowly and
then scroll back up slowly; do not use Home/End/Page Down during the visible
scroll beat unless the user explicitly asks for a jump.
To make a wheel scroll about 50% faster, multiply `delay` by roughly `0.67`.
To cover more of the page per swipe burst, increase the numbers in the
acceleration curve rather than adding more bursts.
For the most human-looking motion, prefer several trackpad-like swipe bursts
instead of one long constant wheel stream. Each burst should accelerate,
decelerate, then pause briefly before the next swipe.

This skill includes a reusable scroll-wheel helper at:

```text
scripts/scroll-wheel.swift
```

Resolve it relative to this `SKILL.md` file. Reusable shell wrapper:

```bash
SCROLL_WHEEL="$SKILL_DIR/scripts/scroll-wheel.swift"
smooth_scroll_down_and_back() {
  local down_bursts="${1:-5}"
  local up_bursts="${2:-5}"
  local delay="${3:-0.034}"
  local burst_pause="${4:-0.18}"
  local curve="${5:-21,42,75,117,162,117,75,42,21}"
  local bottom_pause="${6:-0.80}"

  "$SCROLL_WHEEL" trackpad "$down_bursts" down "$delay" "$burst_pause" "$curve"
  sleep "$bottom_pause"
  "$SCROLL_WHEEL" trackpad "$up_bursts" up "$delay" "$burst_pause" "$curve"
}
```

Example:

```bash
"$CLICLICK" -e 300 m:1200,390 c:.
sleep 0.2
smooth_scroll_down_and_back 5 5 0.034 0.18 "21,42,75,117,162,117,75,42,21" 0.8
```

For a slower, more documentary pace (e.g. for a long settings page where
the user needs to read each row), try
`smooth_scroll_down_and_back 5 5 0.04 0.28 "4,8,14,22,30,22,14,8,4" 1.2`.

If scrolling opens a document, changes filters, summons macOS UI, or does not
move the intended list, fix the focus target and repeat the dry run.

Before typing into controls near notification toasts or banners, wait for the
transient UI to clear. A toast can steal attention, occlude a target, or make
the next action look rushed. For upload-complete toasts, a 8-10 second wait is
usually enough unless the app shows a visible close animation or progress state.

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
- Hold on the final frame just long enough to confirm it. **Cap a still
  final shot at ~10 seconds.** Anything beyond that is dead air — the editor
  can freeze the last frame and extend it for as long as needed in post.
  Only keep rolling past 10 seconds if something on screen is still
  animating, loading, or visibly changing (a fade-in, a spinner, an
  incoming notification, a typing indicator). Once the screen is truly
  static, stop.
- Stop Screen Studio with `Command-Control-Return`.
- Push `phase=stopped` to the status server right after the stop hotkey.

After stopping:

- Restore Codex.
- Surface every note received during the take in chat, with its
  take-relative offset, answering questions and reacting to feedback. The
  notes have already arrived via update responses — no separate fetch is
  needed. See [Notes from the user](#notes-from-the-user).
- Push `phase=stopped` with `action="Starting post-take verification"` before
  inspecting files or frames.
- Verify a fresh project exists in `~/Screen Studio Projects`, and push an
  update naming the project found.
- Verify the display track exists, usually at:

  ```text
  recording/channel-1-display-0.mp4
  ```

- Measure duration with `ffprobe`. Push an update before measuring and another
  update with the measured duration. Treat duration as informational unless the
  user explicitly asked for live sync.
- Generate and inspect a timestamp-based contact sheet. Push an update before
  generation, after the sheet path is known, and while inspecting frames. If
  you open or extract focused frames from a timestamp, push an update with the
  timestamp and what you are checking.
- Reject the take if sampled frames show missing actions, wrong state, Codex,
  stale Screen Studio windows, wrong query text, address-bar suggestions,
  failed saves, missing connectors, or an incorrect final hold.
- Do not reject a complete take just because waits make it longer than the
  audio.
- Before stopping the status server, push one final verdict update. Use
  `phase=stopped` for a keeper verdict, e.g.
  `action="Frame review passed; take looks like a keeper"`, or `phase=error`
  for a rejected take, e.g.
  `action="Rejected: missing final confirmation frame"`.
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
