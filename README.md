# HX Stomp Soundboard

A dark-themed Python desktop app for the **Line 6 HX Stomp** and Helix-family
processors. It has two distinct capabilities that work independently or together:

**MIDI Soundboard** — click a tone card to instantly switch preset, bank, and
snapshot on your device via USB MIDI.

**AI Preset Tools** — describe a tone in plain English. Get a suggested card
name, color, and category (labeling), or generate a complete `.hlx` preset file
with real amp, cab, and effect models ready to import into HX Edit (generation).

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-macOS%20%C2%B7%20Linux%20%C2%B7%20Windows-lightgrey)

---

## Requirements

**Hardware (optional — see `--mock-midi`)**
- Line 6 HX Stomp, HX Stomp XL, or any Helix-family device connected via USB

**Software**
- Python 3.9 or newer

**Linux system libraries** (required by the `python-rtmidi` MIDI backend)

```bash
# Debian / Ubuntu
sudo apt install libasound2-dev libjack-dev

# Fedora / RHEL
sudo dnf install alsa-lib-devel jack-audio-connection-kit-devel
```

**AI features** (optional — labeling and preset generation)

One of: an Anthropic, OpenAI, or Google API key, or
[Ollama](https://ollama.com) running locally (free, no account needed).
See [AI Providers](#ai-providers) for setup.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/edonahue/hx_stomp_midiui.git
cd hx_stomp_midiui

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows

# Install core dependencies (includes Anthropic Claude, the default AI provider)
pip install -r requirements.txt

# Optional: install an alternative AI provider
# pip install openai                # OpenAI GPT
# pip install google-generativeai   # Google Gemini
# Ollama requires no Python package — see docs/LLM_PROVIDERS.md
```

---

## Quick Start

```bash
# Connected HX Stomp
python main.py

# No hardware — MIDI printed to stdout
python main.py --mock-midi

# Check available MIDI ports
python main.py --list-ports
```

After launch the app opens to the **🎸 HLX Generator** tab — describe a tone,
configure your AI provider once, and generate a ready-to-import `.hlx` preset.
Click the **🎵 Soundboard** tab to manage tone cards and connect to your HX Stomp via MIDI
(**MIDI → Connect…** to select your port).

---

## Part 1 — MIDI Soundboard

### Connecting to Your HX Stomp

1. Plug the HX Stomp in via USB and power it on
2. Click **MIDI → Connect…** in the menu bar
3. The port named "HX Stomp" is detected and pre-selected
4. Set the **MIDI channel** to match the device:
   *Menu → Global Settings → MIDI/Tempo → MIDI Channel* (default: 1)
5. Click **Connect** — the status bar shows a green **●** and port name

> **Tip:** If the port is missing, click **↺ Refresh** in the connect dialog.
> On Linux, ensure your user is in the `audio` group:
> `sudo usermod -aG audio $USER` (then log out and back in).

---

### Tone Grid

The main window is a responsive grid of **tone cards**, each representing one
saved preset configuration.

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Blues Crunch│  │  Warm Lead   │  │  Shimmer Pad │
│  PC 10 · S1  │  │  PC 22 · S2  │  │  PC 45 · S1  │
└──────────────┘  └──────────────┘  └──────────────┘
```

- **Click** a card → sends Bank Select + Program Change + Snapshot CC
- **Right-click** a card → Edit or Remove
- The active card gets a blue accent border
- Cards reflow when you resize the window

#### Tone Fields

| Field | Description | Range |
|---|---|---|
| Name | Label on the card | Any text |
| Preset | Program Change number | 0–127 |
| Snapshot | Snapshot index | 0–7 (0 = snapshot 1) |
| Bank MSB | Bank Select coarse (CC0) | 0–127 |
| Bank LSB | Bank Select fine / setlist (CC32) | 0–127 |
| Color | Card background hex color | e.g. `#E67E22` |
| Category | Grouping separator label | Any text |

> **Preset numbering:** HX Stomp counts from 1 on its display
> (e.g. "1A" = PC 0, "64A" = PC 63, "128D" = PC 127).
> Subtract 1 from the display number to get the PC value.

#### Managing Tones

| Action | How |
|---|---|
| Add | **⊕ Add** button or **Tones → ⊕ Add Tone** |
| Edit | Select a card → **✏ Edit** or right-click → Edit |
| Remove | Select a card → **🗑 Remove** or right-click → Remove |
| Reload from disk | **↺ Reload** or **Ctrl+R** |
| Save to disk | **💾 Save** or **Ctrl+S** |

#### presets.json Format

Tones are stored as a JSON array and can be edited directly.

```json
[
  {
    "name":     "Blues Crunch",
    "preset":   10,
    "snapshot": 0,
    "bank_msb": 0,
    "bank_lsb": 0,
    "color":    "#E67E22",
    "category": "Overdrive"
  },
  {
    "name": "Jazz Box",
    "preset": 1
  }
]
```

`snapshot`, `bank_msb`, `bank_lsb`, `color`, and `category` are optional
(defaults: `0`, `0`, `0`, `#4A90D9`, none).

---

### Live Controls

Toggle with **⚡ Live** in the toolbar or **View → ⚡ Live Controls**.

#### Snapshot Navigation

Sends CC69 to jump between snapshots within the active preset.

| Button | Action |
|---|---|
| ◀ Prev | Go to previous snapshot (CC69, value 9) |
| Next ▶ | Go to next snapshot (CC69, value 8) |

#### Tap Tempo

Each press sends CC64 and records the interval. BPM updates after 2+ taps
using the mean of the last 8 intervals. Intervals longer than 4 s auto-reset.

#### Looper Transport

| Button | CC | Action |
|---|---|---|
| ⏺ Rec | CC60, 127 | Start recording |
| ▶ Play | CC61, 127 | Start playback |
| ⏹ Stop | CC61, 0 | Stop playback |
| ↩ Undo | — | Undo / redo last overdub |
| ⟳ OD | — | Overdub |
| ⊙ Once | — | Play once then stop |
| ↔ Rev | — | Toggle reverse |
| ½ ½Spd | — | Toggle half speed |

> Button highlight states are tracked by the app only. Operating the looper
> from the physical footswitches will put the UI out of sync until you use
> the app controls again.

---

### Tuner

Toggle via **MIDI → 🎵 Toggle Tuner**.

The HX Stomp tuner is a hardware toggle — CC68 flips its state regardless of
value. The app tracks state internally and shows "Tuner ON" / "Tuner OFF" in
the status bar. Hardware footswitch toggles will diverge until the next in-app
toggle.

---

### MIDI Reference

| Action | Messages sent |
|---|---|
| Select a tone | CC0 (bank MSB) → CC32 (bank LSB) → Program Change |
| Select snapshot | CC69, value 0–7 (direct), 8 (next), 9 (prev) |
| Tap tempo | CC64, any value |
| Toggle tuner | CC68, any value |
| Looper record | CC60, value 127 |
| Looper play / stop | CC61, value 127 / 0 |
| Footswitch emulate | CC49–58, value 127 (press) / 0 (release) |
| Expression pedal | CC1 (EXP1) or CC2 (EXP2), value 0–127 |

Full CC map, bank/setlist addressing, footswitch numbering →
**[docs/MIDI_REFERENCE.md](docs/MIDI_REFERENCE.md)**

---

## Part 2 — AI Preset Tools

The AI features require an API key or a running Ollama server.
See [AI Providers](#ai-providers) below. AI features work independently of
MIDI — no device connection required.

---

### ✨ AI Tone Labeling

**What it does:** Takes a plain-English description and suggests a tone card
**name**, **color**, **category**, and **snapshot index** — purely as display
metadata for the soundboard grid.

**What it does not do:** It cannot touch amp models, effects, or any signal-chain
parameter. MIDI is output-only; the app has no visibility into what sound is in
any slot on your HX Stomp. Use
[AI Preset Generation](#-ai-preset-generation) to build actual .hlx presets.

#### How to Use

1. Click **✨ Label Tone** in the toolbar or **Tones → ✨ Generate Tone…**
2. Select a provider and configure your API key if needed
3. Describe your tone, e.g. *"dark ambient shimmer with long reverb"*
4. Click **✨ Generate** — the result fills the Add Tone form
5. Enter the correct preset number from your HX Stomp, then click **OK**

---

### 📦 AI Preset Generation

**What it does:** Takes a tone description or artist name and produces a
complete `.hlx` preset file with real HX Stomp amp, cab, and effect models —
with starting parameters, per-block explanations, and three distinct snapshots.
The file is imported into HX Edit offline; no device connection needed.

#### How to Use

1. Open the **🎸 HLX Generator** tab — it is the default tab on launch.
   From the Soundboard tab: **Tones → 🎸 Open HLX Generator**.
2. Configure your provider if not already set
3. Describe the tone, e.g.:
   - *"bluesy SRV crunch with tape delay and spring reverb"*
   - *"tight metal rhythm tone, Mesa-style, no reverb"*
   - *"clean Vox AC30 jangle like The Edge"*
   - *"dark ambient shoegaze with shimmer and chorus"*
4. Click **📦 Generate Preset** — result panel appears with:
   - Signal chain strip — each block in order with category color
   - Per-block explanation of why each model was chosen
   - Three named snapshots (e.g. Rhythm / Lead / Clean)
   - Overall design rationale
5. Click **💾 Save .hlx…** to write the file
6. In **HX Edit**: drag onto an empty preset slot or
   **File → Import Preset…**, then sync to device

Click **🔄 Regenerate** to try a fresh take on the same description.

#### What Gets Generated

| Element | Detail |
|---|---|
| Amp + matched cab | One amp block with best-match default cab |
| Effect chain | Up to 5 blocks: distortion, dynamics, EQ, modulation, delay, reverb |
| Signal chain order | Dynamics → Drive → Amp → EQ → Mod → Delay → Reverb |
| Starting parameters | Sensible defaults; tune further in HX Edit |
| Three snapshots | Distinct named states, e.g. Rhythm / Lead / Clean — per-block bypass states set |
| Explanations | Per-block and overall rationale shown in the UI |

Full guide, tips, and troubleshooting →
**[docs/HLX_GENERATION.md](docs/HLX_GENERATION.md)**

---

### 📋 Preset Catalog

All generated presets are saved to `~/.hxstomp/presets/` and tracked in
`catalog.json`. The **Preset Catalog** panel sits in the lower half of the
**🎸 HLX Generator** tab, below the generation workspace. It updates automatically
after each save.

Each catalog entry shows the preset name, date, description, signal chain
strip, snapshot names, and design rationale. From there you can:

- **📂 Show** — reveal the `.hlx` file in your system file manager
- **💾 Export…** — copy the file to a custom location
- **🗑** — remove the entry from the catalog (file is not deleted)

---

### AI Providers

| Provider | Default model | Requires | Sign-up |
|---|---|---|---|
| Anthropic (Claude) | `claude-haiku-4-5` | API key | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | `gpt-4o-mini` | API key | [platform.openai.com](https://platform.openai.com) |
| Google Gemini | `gemini-1.5-flash` | API key | [aistudio.google.com](https://aistudio.google.com) |
| Ollama (local) | `llama3.2` | Ollama server | `ollama pull llama3.2 && ollama serve` |

Configure via the **⚙ Configure…** button in either AI dialog. API keys are
saved to `~/.hxstomp/config.json` and reused across sessions.

**Environment variable shortcut:**

```bash
ANTHROPIC_API_KEY=sk-ant-...  python main.py
OPENAI_API_KEY=sk-...         python main.py
GOOGLE_API_KEY=AIza...        python main.py
```

Full per-provider setup → **[docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md)**

---

## Reference

### Configuration File

`~/.hxstomp/config.json` is created automatically on first AI provider
configuration. Edit directly or use the in-app **⚙ Configure…** dialog.

```json
{
  "provider":          "anthropic",
  "anthropic_api_key": "sk-ant-...",
  "anthropic_model":   "claude-haiku-4-5",
  "openai_api_key":    "sk-...",
  "openai_model":      "gpt-4o-mini",
  "ollama_base_url":   "http://localhost:11434",
  "ollama_model":      "llama3.2",
  "gemini_api_key":    "AIza...",
  "gemini_model":      "gemini-1.5-flash"
}
```

All keys are optional; missing values use the defaults shown.

---

### CLI Options

```
python main.py [OPTIONS]

Options:
  --presets PATH        Tone data file  (default: presets.json)
  --list-ports          Print available MIDI ports and exit
  --mock-midi           Software mock; no hardware required
  --no-llm              Disable AI features entirely
  --api-key KEY         Set API key for the active provider and save to config
  --llm-provider NAME   Override the provider  [anthropic | openai | ollama | gemini]
```

**Examples**

```bash
# Load a custom tone file
python main.py --presets ~/gig.json

# First-run Anthropic setup
python main.py --api-key sk-ant-...

# Local Ollama, no cloud account needed
python main.py --llm-provider ollama

# Stage/live use — disable AI dialogs
python main.py --no-llm
```

---

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| **Ctrl+S** | Save tones to disk |
| **Ctrl+R** | Reload tones from disk |

---

### Project Structure

```
hx_stomp_midiui/
├── main.py              Entry point, CLI flags, MockHXStompMidi
├── midi_interface.py    HXStompMidi — all CC constants and MIDI send methods
├── tone_manager.py      Tone dataclass, JSON persistence, CRUD
├── soundboard_ui.py     Full UI — SoundboardApp, dialogs, LiveControlPanel
├── llm_generator.py     AI providers, GenerateToneDialog, GeneratePresetDialog,
│                          PresetCatalogDialog
├── hx_models.py         HX Stomp amp/cab/effect model catalog (84 models)
├── hlx_builder.py       .hlx file construction, PresetCatalog,
│                          generate_hlx_preset()
├── presets.json         Default tone library (edit freely)
├── requirements.txt     Python dependencies
└── docs/
    ├── MIDI_REFERENCE.md   Complete CC map and bank/preset addressing
    ├── LLM_PROVIDERS.md    Step-by-step setup for each AI provider
    └── HLX_GENERATION.md   .hlx preset generation guide
```

---

## Roadmap

- **Direct device loading** — send `.hlx` presets to the HX Stomp without
  HX Edit as an intermediary (requires research into Line 6 SysEx or USB HID)
- **Model catalog expansion** — add more amp and effect models as community
  documentation grows (now 84 models across 8 categories; newer IDs marked VERIFY
  pending hardware confirmation)
- **Snapshot parameter control** — expose per-snapshot CC value overrides
  within generated presets (e.g. drive level, reverb mix per snapshot)

---

## License

MIT — see [LICENSE](LICENSE)
