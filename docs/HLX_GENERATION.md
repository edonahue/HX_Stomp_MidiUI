# HX Stomp Preset Generation (.hlx)

Generate complete Line 6 HX Stomp preset files using an AI language model.
The AI selects amp and effect models from the HX Stomp catalog, sets starting
parameters, and explains every choice.  The result is a `.hlx` file you import
directly into **HX Edit** and push to your device.

---

## How It Works

```
You describe a tone or artist
        ↓
AI selects models from the HX Stomp catalog
(amp + cab + effects, signal chain order)
        ↓
App constructs a valid .hlx file
        ↓
You save and import into HX Edit
        ↓
Load onto your HX Stomp
```

The AI does **not** invent model names.  It chooses from a curated catalog of
real HX Stomp model IDs (community-documented from `hx_models.py`) and
explains why each was selected.

---

## Step-by-Step Usage

### 1. Open the HLX Generator

The **🎸 HLX Generator** tab is the default view — it opens automatically on launch.

From the **🎵 Soundboard** tab you can also switch via **Tones → 🎸 Open HLX Generator**.

### 2. Configure your AI provider (first time only)

Select a provider from the dropdown, click **⚙ Configure…**, and enter your
API key (or set it as an environment variable — see `docs/LLM_PROVIDERS.md`).

Ollama (local) works without an API key.

### 3. Describe your tone

Type a description or artist name in the text box. Examples:

- `"bluesy SRV crunch with tape delay and spring reverb"`
- `"dark ambient shoegaze with shimmer reverb and chorus"`
- `"tight metal rhythm, Mesa high-gain, no reverb"`
- `"clean Vox AC30 jangle like The Edge"`

### 4. Click Generate Preset

The AI calls the provider in the background (takes 5–20 seconds depending on
provider and model).  A progress bar is shown while waiting.

### 5. Review the result

After generation, a result panel appears showing:

- **Preset name and description**
- **Signal chain strip** — coloured cards for each block in chain order
- **Block notes** — one sentence per block explaining why it was chosen
- **Design rationale** — overall signal chain explanation

### 6. Save the .hlx file

Click **💾 Save .hlx…** to open a save dialog.  Choose a location (e.g. your
Desktop) and confirm.  The file is also recorded in `~/.hxstomp/presets/catalog.json`
with the full block list and explanations for reference.

### 7. Import into HX Edit

1. Open **HX Edit** on your computer
2. Drag the `.hlx` file onto an empty preset slot in the HX Edit preset list
   — or use **File → Import Preset…**
3. Click **Send to Device** (or double-click the preset in HX Edit)
4. The preset loads onto your HX Stomp

### 8. Regenerate if needed

Click **🔄 Regenerate** to run a new generation with the same description.
Each run is independent — the AI may make different choices.

---

## What the AI Generates

| Generated | Notes |
|-----------|-------|
| Amp model | One per preset; chosen from catalog based on tonal description |
| Cab model | Paired automatically with the amp (best-match default) |
| Effect blocks | Up to 5 additional blocks: distortion, dynamics, EQ, modulation, delay, reverb |
| Signal chain order | Follows convention: dynamics → drive → amp → EQ → mod → delay → reverb |
| Three named snapshots | Distinct bypass states per snapshot (e.g. Rhythm / Lead / Clean) |
| Parameter values | Starting values; tweak further in HX Edit |
| Per-block explanations | Why each model was chosen |
| Design rationale | Overall chain philosophy |

## What It Does NOT Generate

| Not Generated | Reason |
|---------------|--------|
| Snapshot parameter values | Block bypass states are set per snapshot; knob/parameter value overrides require HX Edit |
| Footswitch assignments | Assign FS1–FS3 in HX Edit as desired |
| Controller (MIDI CC) mappings | Set up in HX Edit |
| IR loader blocks | Requires an IR file on your device; not generated |
| Exact artist tones | AI approximates based on known gear/style; adjust to taste |

---

## Available Models

The catalog (`hx_models.py`) includes 84 models across categories:

| Category | Count | Examples |
|----------|-------|---------|
| Amp | 26 | US Double Nrm, A30 Fawn Nrm, Brit Plexi Nrm, Cali Rectifire, Hiway 100, Das Benzin |
| Cab | 11 | 2x12 Blue Bell, 4x12 Greenback 25, 4x12 Cali V30, 4x12 Brit Basket |
| Distortion | 13 | Scream 808, Minotaur, Vermin Dist, Arbitrator Fuzz, Pillars OD |
| Delay | 8 | Simple Delay, Transistor Tape, Elephant Man, Cosmos Echo, Reverse Delay |
| Reverb | 9 | Plate, 63 Spring, Hall, Ganymede, Octo, Cave, Plateaux |
| Modulation | 9 | Chorus, Tremolo, Harmonic Tremolo, Pattern Tremolo, Gray Flanger, UniVibe |
| Dynamics | 5 | Red Squeeze, Deluxe Comp, LA Studio Comp, Kinky Comp, Noise Gate |
| EQ | 3 | Parametric, Low/High Cut, 10 Band |

Newer entries are marked `# VERIFY` in the source — test against a physical device
or HX Edit before relying on them. The catalog can be expanded by adding entries to
`hx_models.py`.

---

## Tips

- **Be specific about genre/artist** — "Hendrix fuzz" or "modern metal" gives
  better results than "good tone"
- **Mention preferred effects** — "with chorus and delay" guides the chain
- **Say what to omit** — "no reverb" or "dry tone only" works well
- **Start simple** — 3–4 blocks is usually plenty; you can add more in HX Edit
- **Use a capable model** — Claude Sonnet or GPT-4o produces better explanations
  and more accurate parameter choices than the default haiku/mini models

---

## Files Created

| Path | Contents |
|------|---------|
| `<chosen path>/<preset>.hlx` | The preset file for HX Edit import |
| `~/.hxstomp/presets/catalog.json` | Index of all generated presets with block metadata |

---

## Technical Notes

- `.hlx` files are plain JSON understood by HX Edit.  The format is
  community-reverse-engineered (not officially documented by Line 6).
- Model IDs follow the `HD2_<Category><Name>` pattern.
- Parameter ranges: most knobs `0.0–1.0`; Level/Gain in real dB; High/LowCut
  in Hz; Threshold in negative dB.
- Presets use `device: 2162694` (HX Stomp) and `"schema": "L6Preset"`,
  `"version": 6`.
- If HX Edit shows a compatibility warning, check that your firmware matches the
  `device_version` or simply accept the import — HX Edit will adapt as needed.

---

## Troubleshooting

**"No valid amp block in response"**
The LLM did not include an amp from the catalog.  Try regenerating or adding
"with amp" to your description.

**"Could not parse .hlx generation response"**
The LLM returned malformed JSON.  This can happen with smaller local models
(Ollama).  Try regenerating or switch to a cloud provider.

**HX Edit shows "Unknown model" on some blocks**
A model ID in the catalog may not match your firmware version.  Remove that
block in HX Edit and substitute manually.  You can also report the mismatch
as an issue so the catalog can be corrected.

**Preset sounds very different from the description**
AI parameter choices are approximations.  Use the block names and explanations
as a starting point, then dial in the sound in HX Edit or on the device itself.
