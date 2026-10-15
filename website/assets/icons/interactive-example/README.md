# QuasiLeak-Bench — Interactive Example Icon Bundle

23 original vector icons, each delivered as:
- `illustrated/<name>.svg`: 64×64 viewBox with a soft duotone tile for cards and section headers
- `glyphs/<name>.svg`: transparent 24×24 viewBox, no background, for inline fields/actions
- `glyphs/currentcolor/<name>.svg`: theme-color SVG to embed inline so CSS `color` controls stroke
- `png/<name>_illustrated.png`: transparent 256×256 export
- `png/<name>_glyph.png`: transparent 96×96 export

All files are separate. No raster atlas cropping is needed. Icons contain no words or embedded fonts.

## Suggested placement

- Scenario banner: `illustrated/movie.svg` at 56–64px; `glyphs/download.svg` at 18px.
- Profile heading: `illustrated/profile.svg` at 40–44px. Attribute rows: `glyphs/{age,gender,nationality,relationship,education,occupation,income,health}.svg` at 20–22px.
- Policy heading: `illustrated/policy.svg` at 40–44px. Policy rows: `glyphs/{hide,keep,neutral}.svg` at 22px.
- Interactive evidence: `illustrated/evidence.svg` at 36–44px; `glyphs/cue_group.svg` and `glyphs/gold.svg` at 20–22px.
- Restore/source actions: `glyphs/reset.svg`, `glyphs/download.svg` at 18px.

## Installation

Copy `illustrated/` and `glyphs/` to `public/icons/interactive-example/`.

```jsx
<img src="/icons/interactive-example/illustrated/movie.svg" alt="" width="56" height="56" />
<img src="/icons/interactive-example/glyphs/occupation.svg" alt="" width="20" height="20" />
```

Decorative icons use `alt=""`; visible text should carry the meaning. For standalone icon buttons add `aria-label` to the button.

`integration/example.html` and `integration/example.css` demonstrate the intended visual hierarchy, spacing, and use of the icons. Links in the sample page are illustrative placeholders, not implemented controls.

## Design constraints

- Keep existing QuasiLeak-Bench brand blue and muted off-white backgrounds.
- Standardize headings at 18/24/30px, body/control text 16px, secondary 14px minimum.
- Avoid category cards nested inside attribute cards; simple field rows with small glyphs read better.
- Treat author-profile attributes as **reference only**. Never style them like detected evidence spans.
- HIDE/KEEP/NEUTRAL have different policy meanings, not truth labels for inferred attributes.
- Leave HTML text and interaction state editable; icons are separate decorative visual assets.

## Verification

- All SVGs rasterized successfully for corresponding PNG exports.
- Integration screenshot supplied at `preview/integration_preview.png`.
- `manifest.json` lists every available icon.

## Dark mode guidance

For dark mode or hover-state recoloring, import `glyphs/currentcolor/<name>.svg` as **inline SVG** through your application's SVG component pipeline and set CSS `color`. `currentColor` does not inherit the page's `color` when an SVG is loaded as an external `<img>`; use the static colored glyphs with `<img>` instead.

The SVGs are visual assets only. They do not implement state or click behavior; connect them to your existing React/Vue controls.
