# Title Cards

Title and outro cards are the branded still images that bookend the screencast.
The renderer (`scripts/render_screencast.py`) does not care how they were made
— it just consumes PNGs via `intro.path` / `outro.path`. Anything that
produces a PNG at the timeline canvas size is fair game: Figma export,
Keynote slide, Photoshop, Pillow, etc.

## Bundled Brand Renderer

`scripts/render_fullstack_ag_cards.py` is the **Fullstack AG** title-card
renderer, kept in the skill as a worked example. It produces the
gradient + wave-texture + wheat decoration look used in the Paperless NGX
case study. It is not a generic card renderer — the colors, layout
proportions, and decorative elements all encode that one brand.

Use it directly when generating Fullstack AG cards; treat it as a starting
template for any other brand.

### macOS dependency

`render_fullstack_ag_cards.py` looks for fonts at:

- `/System/Library/Fonts/Supplemental/Arial.ttf`
- `/System/Library/Fonts/Supplemental/Arial Bold.ttf`
- `/System/Library/Fonts/Supplemental/Helvetica.ttc`
- `/Library/Fonts/Arial.ttf`
- `/System/Library/Fonts/SFNS.ttf`

If none of those exist (Linux, Windows, or a stripped-down macOS image),
Pillow falls back to its built-in bitmap font, which renders text far too
small for a 4K card. On non-macOS systems either:

1. Edit the script to point at a TrueType font you actually have, or
2. Skip the script and supply pre-made PNGs for `intro.path` / `outro.path`.

## Authoring A New Brand Renderer

If the user has a different brand, **copy** the Fullstack AG script and
adapt it rather than parameterizing the existing one — the design choices
are tightly coupled enough that a brand-specific copy is cleaner than a
mega-config:

1. Copy `scripts/render_fullstack_ag_cards.py` to
   `scripts/render_<brand>_cards.py`.
2. Replace the `make_background` palette and decoration calls
   (`draw_wave_texture`, `draw_wheat`) with calls that match the new
   brand. Drop the wheat helper if the brand doesn't use one.
3. Adjust `find_font` to point at the brand's preferred typeface.
4. Update `layout` defaults (logo position, title size, subtitle size) to
   match the new brand's title-card proportions.
5. Update the example style JSON under `assets/examples/<brand>/` so the
   renderer has a runnable config to consume.

The script CLI surface (`--config`, `--output-dir`, `--title`, `--subtitle`,
`--logo`, `--output`, `--dry-run`) is worth preserving so editors can swap
renderers without rewriting their orchestration.

## Bypassing The Bundled Renderer

For one-off cards, just author the PNG by hand at the timeline canvas size
(`width × height` from the spec) and reference it directly:

```json
"intro": {
  "path": "/path/to/hand-authored-intro.png",
  "duration": 4,
  "fade_duration": 1
}
```

The renderer normalizes intro/outro images to the timeline canvas with
letterboxing if the aspect ratio doesn't match, so the PNG dimensions don't
have to be exact — but matching the canvas avoids any padding bars.
