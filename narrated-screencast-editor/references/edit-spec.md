# Edit Spec

`scripts/render_screencast.py` reads a JSON edit spec and turns it into an
`ffmpeg` command. Paths can be absolute, relative to the spec file, or use
environment variables.

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

## Timeline Fields

- `width` and `height`: normalize all video and still assets to this canvas.
- `fps`: output frame rate and filter graph frame rate.
- `segments`: body timeline before intro/outro fades are applied.
- `intro`: optional still image that crossfades into the body timeline.
- `outro`: optional still image that crossfades from the body timeline.
- `overlays`: optional transparent PNG overlays applied after intro/body/outro
  composition.

## Segment Types

`video` segments:

- `start`: source-video start time in seconds.
- `end`: source-video end time in seconds.
- `setpts_multiplier`: direct ffmpeg `setpts` multiplier. Values above `1`
  slow the clip down; values below `1` speed it up.
- `speed`: alternative to `setpts_multiplier`. Values above `1` speed the clip
  up; values below `1` slow it down.
- `clone_pad_after`: optional freeze on the last frame of the segment.

`freeze` segments:

- `path`: still image path.
- `duration`: hold duration in seconds.

## Profiles

Profiles merge with built-in defaults. Use `preview` for review renders and
`hq` for final renders.

Useful overrides:

- `scale_width`: downscale preview video after all overlays.
- `crf`: lower means higher quality and larger file.
- `preset`: slower means better compression at the same quality.
- `audio_codec`: use `copy` when the narration audio can be copied into MP4.
- `limit_duration`: temporary cap for short proof renders.

Run a dry run to inspect the generated command:

```bash
python3 "$SKILL_DIR/scripts/render_screencast.py" edit-spec.json --profile hq --dry-run
```
