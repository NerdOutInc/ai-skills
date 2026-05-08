# Quality And Compression

The final video can be much smaller than the original while still looking good.
That is normal when the source is a high-bitrate screen recording and the final
render uses modern constant-quality encoding.

## Recommended Defaults

HQ render:

```text
H.264 / libx264
preset slow
CRF 18
original resolution
original frame rate
pix_fmt yuv420p
audio copy when possible
movflags +faststart
```

Preview render:

```text
H.264 / libx264
preset veryfast
CRF 28
scale to about 1280px wide
AAC audio around 128k
```

## Why A Smaller File Can Still Be HQ

Screen recordings often come from capture tools at very high bitrates to avoid
dropped detail during recording. After editing, `libx264` can encode the same
mostly-static UI frames much more efficiently.

CRF encoding targets perceptual quality instead of a fixed bitrate:

- Lower CRF means higher quality and larger files.
- Higher CRF means lower quality and smaller files.
- CRF 18 is a strong default for final screencast output.
- CRF 28 is useful for previews where speed and small file size matter.

The `slow` preset does not mean lower quality. It means the encoder spends more
time finding efficient compression, usually producing a smaller file than
`veryfast` at the same CRF.

## When To Increase Quality

Use a lower CRF such as 16 if:

- Small text looks smeared.
- Cursor movement or UI animation leaves artifacts.
- The video will be uploaded to a platform that re-encodes aggressively.

Use ProRes or another mezzanine format only when another editor needs to keep
editing the result. For final web delivery, H.264 MP4 is usually the right
answer.
