# Paperless NGX Case Study

This case study records the workflow used for a Paperless NGX narrated
screencast. It is a worked example, not a runnable tutorial: it
references local media that lives on the original author's machine. The
example spec under `assets/examples/paperless-ngx/` substitutes environment
variables for the absolute paths so it can be inspected (and `--dry-run`'d)
without those files.

## Source Media (placeholder env vars)

The example spec uses these environment variables. Set them to your own files
to run the spec end-to-end:

| Env var | Original role |
| --- | --- |
| `$PAPERLESS_SOURCE_VIDEO` | Source screencast (3600x2160, 60 fps, ~48.7s). |
| `$PAPERLESS_NARRATION` | Narration m4a (~92.18s). |
| `$PAPERLESS_FREEZE_DOC_LIST` | Clean document-list freeze frame, 4K. |
| `$PAPERLESS_INTRO_CARD` | Rendered intro PNG (4K). |
| `$PAPERLESS_OUTRO_CARD` | Rendered outro PNG (4K). |
| `$PAPERLESS_TOOLTIP_PATCH` | Transparent overlay PNG hiding the tooltip and green artifact. |
| `$PAPERLESS_OUTPUT` | Output path for the rendered MP4. |

Observed source facts:

- Source screencast: 3600x2160, 60 fps, about 48.7 seconds.
- Narration: about 92.18 seconds.
- Final accepted render: about 92.14 seconds.

## Edit Strategy

- Added a 4 second custom intro card.
- Crossfaded intro to video over 1 second.
- Retimed the source screen recording into several segments with `setpts`.
- Inserted a clean freeze frame for the document list while narration caught up.
- Used a transparent overlay patch from 35.7s to 55.8s to hide the persistent
  "Toggle tag filter" hover title and a small green artifact.
- Crossfaded to the custom outro right after the narration phrase "makes
  searching even smarter."
- Used a 3.871552 second outro still with the final text:
  `Thanks for watching!` and `https://fullstack.ag`.

## Timing Recipe

The body timeline used these operations:

| Operation | Source Time | Multiplier / Duration |
| --- | ---: | ---: |
| Clone first frame | 0.000-0.016667 | hold 0.983333s |
| Video | 0.000-8.000 | setpts 2.46 |
| Video | 8.000-10.000 | setpts 2.02 |
| Video | 10.000-13.200 | setpts 1.025 |
| Video | 13.200-17.000 | setpts 1.126315789 |
| Video | 17.000-28.500 | setpts 0.765217391 |
| Freeze frame | clean document list | 11.88s |
| Video | 28.500-39.600 | setpts 1.214414414 |
| Video | 39.600-48.716667 | setpts 2.070018333, then hold 1s |

Title card fade settings:

- Intro duration: 4s.
- Intro fade: 1s, offset 3s.
- Outro duration: 3.871552s.
- Outro fade: 1s, offset 88.311668s.

## Reusable Lessons

- A freeze frame is often better than showing a long upload or indexing wait.
- Transparent patches work well when the background underneath is static.
- Always inspect a patch at the start, middle, and end of its enabled range.
- Generate preview renders before HQ; still-card contrast and timing are easier
  to iterate at preview quality.
- A final HQ file can be much smaller than the capture source when encoded with
  H.264 CRF 18 and a slow preset.

## Example Spec

See:

```text
assets/examples/paperless-ngx/paperless-ngx-edit-spec.json
```

Dry-run it with:

```bash
python3 "$SKILL_DIR/scripts/render_screencast.py" \
  "$SKILL_DIR/assets/examples/paperless-ngx/paperless-ngx-edit-spec.json" \
  --profile hq \
  --dry-run
```

Set the `$PAPERLESS_*` env vars (see the table above) before running the
spec without `--dry-run`.
