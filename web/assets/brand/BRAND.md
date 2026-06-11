# saakshe brand assets

## Wordmark — locked 2026-06-11

**SΛΛKSHE** · Syncopate · weight **900** · letter-spacing **.295em** · line-height 1 · CAPS ONLY.

```css
font-family:'Syncopate',sans-serif; font-weight:900; font-size:38px;
line-height:1; letter-spacing:.295em; padding-left:.295em;
```

- `padding-left:.295em` re-centers the wordmark (CSS letter-spacing adds a
  trailing space after the last glyph).
- Syncopate ships only 400/700 — `font-weight:900` resolves to the Bold cut
  today; keep 900 in CSS so a heavier cut is adopted automatically if one
  ever ships.
- **Λ = U+039B.** Syncopate has no Λ glyph; in live text browsers substitute
  a fallback Λ. In the vector/raster assets the two Λ's are drawn as the
  brand **witness wedge** (the same polygon as the witness-mark eyes,
  `M50 0 L100 88 L72 88 L50 36 L28 88 L0 88 Z`, scaled to cap height) — the
  two Λ's stand in the wordmark and fall over to become the witness eyes.

### Sizes by position

| position            | size                          | notes                      |
|---------------------|-------------------------------|----------------------------|
| navbar / topbar     | **38px** desktop              | `clamp(22px, 5.5vw, 38px)` |
| cockpit topbar      | 38px (24px ≤760px)            | 52px bar, line-height 1    |
| footer lockup       | 20px                          |                            |
| sign-in gate plate  | 16px                          |                            |
| mobile floor        | 22px                          | tracking stays .295em      |

## Files

- `saakshe-wordmark.svg` — outline vector, `fill="currentColor"`, transparent.
  True Syncopate Bold glyph outlines + witness-wedge Λ's, .295em tracking baked in.
- `saakshe-wordmark-on-paper.svg` / `-on-obsidian.svg` — on BRUT paper
  `#F4EEE2` (ink `#161410`) / on OBSIDIAN `#0A0D0A` (phosphor `#D4F5DE`).
- `saakshe-wordmark-on-paper@4x.png` / `-on-obsidian@4x.png` — 3840px rasters.
- `wordmark.css` — canonical `.sk-wordmark` classes (nav / foot / card sizes).
- `fonts/Syncopate-Bold.ttf` + `fonts/LICENSE.txt` (Apache 2.0).

Served live at `/assets/brand/<file>` (svg/png/css ride the asset safelist).

Regenerate vectors: `/tmp/fontenv/bin/python /tmp/gen_wordmark.py` pattern —
fontTools SVGPathPen over the TTF, wedge polygon for Λ, tracking
`0.295 × unitsPerEm` between glyphs (none trailing), PNGs via headless Chrome
at the SVG's exact aspect.

## Witness mark / logo

Next round — the lockup (witness bot + divider + wordmark) and og.png refresh
land with the logo decision.
