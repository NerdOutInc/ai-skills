# Edit Spec

`scripts/render_screencast.py` reads a JSON edit spec and turns it into an
`ffmpeg` command. Paths can be absolute or relative to the spec file (a
leading `~` is also expanded).

## Minimal Shape

```json
{
  "output": "/tmp/my-edit/final.mp4",
  "inputs": {
    "video": "/path/to/source.mp4",
    "audio": "/path/to/narration.m4a"
  },
  "timeline": {
    "width": 3600,
    "height": 2160,
    "fps": 60,
    "segments": [
      { "type": "video", "start": 0, "end": 8, "setpts_multiplier": 2.46 },
      { "type": "freeze", "path": "/path/to/freeze.png", "duration": 4.2 },
      { "type": "video", "start": 8, "end": 12, "speed": 1.5 }
    ],
    "intro": {
      "path": "/path/to/intro.png",
      "duration": 4,
      "fade_duration": 1
    },
    "outro": {
      "path": "/path/to/outro.png",
      "duration": 3.8,
      "fade_duration": 1,
      "offset": 88.3
    },
    "overlays": [
      {
        "path": "/path/to/transparent-patch.png",
        "start": 35.7,
        "end": 55.8,
        "x": 0,
        "y": 0
      }
    ]
  },
  "profiles": {
    "preview": {
      "preset": "veryfast",
      "crf": 28,
      "scale_width": 1280,
      "audio_codec": "aac",
      "audio_bitrate": "128k"
    },
    "hq": {
      "preset": "slow",
      "crf": 18,
      "audio_codec": "copy"
    }
  }
}
```

## Top-Level Fields

| Field | Required | Description |
| --- | --- | --- |
| `output` | Yes¹ | Default output path. May be overridden with `--output`. |
| `inputs.video` | Yes | Source screencast path. |
| `inputs.audio` | No | Narration audio path. If omitted, the rendered file has no audio. Embedded audio in the source video is **not** carried over. |
| `timeline` | Yes | See "Timeline Fields" below. |
| `profiles` | No | Per-profile overrides keyed by profile name (`preview`, `hq`, …). Merged on top of the script defaults. |

¹ Either `output` in the spec or `--output` on the command line is required.

## Timeline Fields

| Field | Required | Description |
| --- | --- | --- |
| `width`, `height` | No (pair) | Canvas size. All segments and stills are scaled to fit (preserve aspect, pad with letterboxing). Set **both** for an explicit canvas or omit **both** to auto-detect from the first source video's resolution via `ffprobe`. Setting only one is rejected. Set both explicitly for placeholder-only dry runs. |
| `fps` | No | Output frame rate. Defaults to the source video's frame rate when that file is available to `ffprobe`, otherwise `60`. All filter graphs run at this rate. |
| `segments` | Yes | Body timeline before intro/outro fades are applied. Must contain at least one segment. |
| `intro` | No | Optional still image that crossfades into the body timeline. |
| `outro` | No | Optional still image that crossfades from the body timeline. |
| `overlays` | No | Transparent PNG overlays applied after intro/body/outro composition. |

## Segment Types

### `video` segments

| Field | Required | Description |
| --- | --- | --- |
| `start` | Yes | Source-video start time in seconds. |
| `end` | Yes | Source-video end time in seconds. Must be greater than `start`. |
| `setpts_multiplier` | One-of² | Direct ffmpeg `setpts` multiplier. Values **above** `1` slow the clip down (output is longer); values **below** `1` speed it up. |
| `speed` | One-of² | Alternative to `setpts_multiplier`. Values **above** `1` speed the clip up; values **below** `1` slow it down. Internally converted to `1/speed`. |
| `clone_pad_after` | No | Hold the last frame of this segment for N seconds (uses `tpad=stop_mode=clone`). Useful for the "first-frame freeze" idiom (see below). |

² Provide either `setpts_multiplier` or `speed`. If both are omitted the segment plays at native rate (`speed=1`).

### `freeze` segments

| Field | Required | Description |
| --- | --- | --- |
| `path` | Yes | Still image path (PNG/JPEG). |
| `duration` | Yes | Hold duration in seconds. |

### First-frame freeze idiom

A common opening trick is to hold the first frame of the source video for ~1
second before the action starts. Express it as a tiny `video` segment with
`clone_pad_after`:

```json
{
  "type": "video",
  "start": 0,
  "end": 0.016667,
  "setpts_multiplier": 1,
  "clone_pad_after": 0.983333
}
```

`end - start` is one frame at 60 fps; `clone_pad_after` extends that frame to a
total of 1 second. Adjust `clone_pad_after` to taste.

## Intro / Outro Cards

| Field | Required | Description |
| --- | --- | --- |
| `path` | Yes | Still PNG/JPEG path. |
| `duration` | Yes | Card duration in seconds. |
| `fade_duration` | No | Crossfade duration in seconds (default `1`). |
| `offset` | No | Output time at which the crossfade begins. **Auto-computed when omitted** (see below). |
| `transition` | No | Any [`xfade` transition](https://ffmpeg.org/ffmpeg-filters.html#xfade) name (default `fade`). |

### Auto-computed offsets

- **Intro `offset`** defaults to `intro.duration - intro.fade_duration`. With
  `duration=4, fade_duration=1`, the fade starts at output time `3s` and ends
  at `4s`.
- **Outro `offset`** defaults to `current_duration - outro.fade_duration`,
  where `current_duration` is the body duration after the intro fade has been
  composed in. In practice that means "fade out one second before the body
  ends." When narration timing dictates the outro start, set `offset`
  explicitly to the desired output time.

### Audio timing constraint

Narration audio is mapped raw from input — it plays from output time `0`.
That means the narration starts under the intro card. Make sure the m4a has
leading silence equal to the visible intro time:

```text
intro_visible = intro.duration - intro.fade_duration
```

For a 4s intro with a 1s fade, the narration should begin with ~3 seconds of
silence so the first word lands as the body video appears.

## Overlays

Overlays are transparent PNGs composited after intro/body/outro:

| Field | Required | Description |
| --- | --- | --- |
| `path` | Yes | Transparent PNG path. |
| `start` | No | Output time at which the overlay becomes visible (default `0`). |
| `end` | Yes | Output time at which the overlay disappears. |
| `x`, `y` | No | Top-left position on the canvas (default `0, 0`). |

Verify alignment at the first, middle, and last affected timestamps before
calling the patch good.

## Profiles

Profiles merge with built-in defaults. The script ships `preview` and `hq`;
spec `profiles.<name>` keys override those defaults field-by-field.

| Field | Default (preview / hq) | Description |
| --- | --- | --- |
| `video_codec` | `libx264` / `libx264` | Output video codec. |
| `preset` | `veryfast` / `slow` | x264 preset. Slower means better compression at the same CRF. |
| `crf` | `28` / `18` | Constant Rate Factor. Lower = higher quality, larger file. |
| `scale_width` | `1280` / *(unset)* | If set, downscale to this width (height auto). |
| `audio_codec` | `aac` / `copy` | `copy` is fast and lossless but **requires the input audio to already be AAC/m4a**. The renderer auto-detects non-AAC inputs and falls back to `aac` with a printed warning. |
| `audio_bitrate` | `128k` / *(unset)* | Used only when `audio_codec` is not `copy`. |
| `movflags_faststart` | `true` / `true` | Adds `-movflags +faststart` (better web-shareable MP4 layout). |
| `shortest` | `true` / `true` | Adds `-shortest`, capping output duration at the shortest input. With narration as a separate input this typically truncates output to narration length. Set `false` if the body plus intro/outro stills are intentionally longer than the narration. |
| `limit_duration` | *(unset)* / *(unset)* | Cap output duration in seconds. Useful for short proof renders; overridden by `--limit-duration` on the command line. |

Run a dry run to inspect the generated command:

```bash
python3 "$SKILL_DIR/scripts/render_screencast.py" edit-spec.json --profile hq --dry-run
```

Dry runs skip file existence checks, so specs with placeholder paths still
print a useful command for inspection.
