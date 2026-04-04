# Screenshot Guide

Screenshots referenced in the main README. Capture these locally and save them here, then uncomment the `<img>` tags in `README.md`.

---

## 1. `soundboard.png` — Hero image (Soundboard tab)

**What to show:**
- Full app window, **Soundboard** tab active
- Tone card grid with all four categories visible (Clean, Overdrive, High Gain, Ambient)
- One card highlighted as active (just clicked)
- Live Controls panel visible on the right
- Status bar showing a connected MIDI port

**Tips:**
- Use `python main.py --mock-midi` so no hardware is needed
- Click a tone card before capturing so the active state is visible
- Suggested size: ~1400 × 900 px at native resolution (no scaling)

**How to enable in README.md** — replace this comment block:
```
<!--
  Hero screenshot — Soundboard tab with tone cards.
  ...
-->
```

with:
```html
<p align="center">
  <img src="docs/screenshots/soundboard.png" alt="HLX Generator Soundboard" width="700">
</p>
```

---

## 2. `ai-builder.png` — AI Preset Builder tab

**What to show:**
- Full app window, **HLX Generator** tab active
- A generated preset with colored signal-chain block cards visible (amp, reverb, delay, etc.)
- The description input field containing something like "warm jazz clean with plate reverb"

**Tips:**
- Generate a preset with `--mock-midi` and no real API key by using Manual Mode, or with a real Anthropic/OpenAI/Gemini key
- Capture after generation so the block cards are populated
- Suggested size: ~1400 × 900 px

**How to enable in README.md** — replace this comment block:
```
<!--
  AI Builder screenshot — HLX Generator tab with a generated signal chain.
  ...
-->
```

with:
```html
<p align="center">
  <img src="docs/screenshots/ai-builder.png" alt="AI Preset Builder" width="700">
</p>
```

---

## Format notes

- PNG preferred (lossless, good for UI screenshots)
- Dark theme (the app's default) reads well on both GitHub light and dark modes
- Width 700px in the `<img>` tag keeps it readable without dominating the page
