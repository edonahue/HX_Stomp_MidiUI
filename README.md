# HX Stomp Soundboard

A dark-themed Python desktop soundboard for the **Line 6 HX Stomp** (and other
Helix-family processors). Click a tone card to instantly switch presets, bank-select,
and load a snapshot — all via MIDI. Describe a tone in plain English and let an AI
suggest the name, color, and category.

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-macOS%20%C2%B7%20Linux%20%C2%B7%20Windows-lightgrey)

**Features**

- One-click preset + snapshot switching via USB MIDI
- Responsive card grid with custom colors and categories
- Collapsible Live Controls panel — tap tempo, snapshot nav, looper transport
- AI tone generation from plain-English descriptions (Anthropic, OpenAI, Ollama, Gemini)
- Fully usable without hardware via `--mock-midi` mode

---

## Requirements

**Hardware**
- Line 6 HX Stomp, HX Stomp XL, or any Helix-family device connected via USB

**Software**
- Python 3.9 or newer
- pip

**Linux system libraries** (required by the `python-rtmidi` MIDI backend)

```bash
# Debian / Ubuntu
sudo apt install libasound2-dev libjack-dev

# Fedora / RHEL
sudo dnf install alsa-lib-devel jack-audio-connection-kit-devel
```

**Optional — AI tone generation**

One of: an Anthropic, OpenAI, or Google API key, or
[Ollama](https://ollama.com) running locally (free, no account needed).

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/edonahue/hx_stomp_midiui.git
cd hx_stomp_midiui

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows

# 3. Install core dependencies
pip install -r requirements.txt

# 4. Optional: install an AI provider package
pip install anthropic              # Anthropic Claude (default provider)
# pip install openai               # OpenAI GPT
# pip install google-generativeai  # Google Gemini
# Ollama requires no Python package — see docs/LLM_PROVIDERS.md
```

---

## Quick Start

```bash
# With an HX Stomp connected via USB
python main.py

# No hardware? Use the mock backend (all MIDI printed to stdout)
python main.py --mock-midi

# Check which MIDI ports are available
python main.py --list-ports
```

After launch, open **MIDI → Connect…** to connect to your device.

---

## Connecting to the HX Stomp

1. Plug the HX Stomp into your computer via USB and power it on
2. Click **MIDI → Connect…** in the menu bar
3. The port named "HX Stomp" is detected and pre-selected automatically
4. Set the **MIDI channel** — must match the device setting at
   *Menu → Global Settings → MIDI/Tempo → MIDI Channel* (default: 1)
5. Click **Connect**
6. The status bar shows a green **●** and the port name

> **Tip:** If the port is not listed, click the **↺** refresh button in the connect
> dialog. On Linux, make sure your user is in the `audio` group:
> `sudo usermod -aG audio $USER` (then log out and back in).

---

## Tone Grid

The main window is a responsive grid of **tone cards**, each representing one saved
preset configuration.

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Blues Crunch│  │  Warm Lead   │  │  Shimmer Pad │
│  PC 10 · S1  │  │  PC 22 · S2  │  │  PC 45 · S1  │
└──────────────┘  └──────────────┘  └──────────────┘
```

- **Click** a card → sends Bank Select + Program Change + Snapshot to the HX Stomp
- **Right-click** a card → Edit or Remove
- The active card gets a blue accent border; the status bar shows preset details
- Cards reflow automatically when you resize the window

### Tone Fields

| Field | Description | Valid range |
|---|---|---|
| Name | Display label on the card | Any text |
| Preset | Program Change number | 0–127 |
| Snapshot | Snapshot index on the device | 0–7 (0 = snapshot 1) |
| Bank MSB | Bank Select coarse (CC0) | 0–127 (almost always 0) |
| Bank LSB | Bank Select fine / setlist (CC32) | 0–127 (0 = setlist 1) |
| Color | Card background hex color | e.g. `#E67E22` |
| Category | Grouping label shown as a separator | Any text |

> **Preset numbering:** The HX Stomp display counts from 1 (e.g. "1A" = PC 0,
> "64A" = PC 63, "128D" = PC 127). Subtract 1 from the display number for PC.

### Managing Tones

| Action | How |
|---|---|
| Add | **⊕ Add** button or **Tones → ⊕ Add Tone** |
| Edit | Select a card, then **✏ Edit** or right-click → Edit |
| Remove | Select a card, then **🗑 Remove** or right-click → Remove |
| Reload from disk | **↺ Reload** button or **Ctrl+R** |
| Save to disk | **💾 Save** or **Ctrl+S** |

### presets.json Format

Tones are stored as a JSON array. You can edit the file directly in any text editor.

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

`snapshot`, `bank_msb`, `bank_lsb`, `color`, and `category` are **optional** and
default to `0`, `0`, `0`, `#4A90D9`, and no category respectively.

---

## AI Tone Generation

The **✨ Generate** feature lets you describe a tone in plain English and have an
AI suggest the name, card color, category, and snapshot index.

> **Important:** The AI generates *metadata only* — it does not assign a preset
> number. Preset slots are specific to your rig (preset 10 on your HX Stomp is a
> completely different sound from preset 10 on someone else's). You enter the
> correct preset number yourself in the confirmation form.

### How to Use

1. Click **✨ Generate** in the toolbar or **Tones → ✨ Generate Tone…**
2. Select a provider (default: Anthropic Claude)
3. Click **⚙ Configure…** to add your API key — required once; saved to
   `~/.hxstomp/config.json`
4. Type a description, e.g. *"dark ambient shimmer with long reverb"*
5. Click **✨ Generate** — the API call runs in the background
6. The **Add Tone** form opens pre-filled with the AI's suggestions
7. Enter the correct preset number from your HX Stomp, then click **OK**
8. The new card appears in the grid

### Providers

| Provider | Default model | Requires | Sign-up |
|---|---|---|---|
| Anthropic (Claude) | `claude-haiku-4-5` | API key | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | `gpt-4o-mini` | API key | [platform.openai.com](https://platform.openai.com) |
| Google Gemini | `gemini-1.5-flash` | API key | [aistudio.google.com](https://aistudio.google.com) |
| Ollama (local) | `llama3.2` | Ollama server | `ollama pull llama3.2 && ollama serve` |

For full per-provider setup instructions → **[docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md)**

### API Key via Environment Variable

```bash
ANTHROPIC_API_KEY=sk-ant-...  python main.py
OPENAI_API_KEY=sk-...         python main.py
GOOGLE_API_KEY=AIza...        python main.py
```

When the key is set in the environment, no dialog configuration is needed.

---

## Live Controls

The **Live Controls** panel provides real-time performance controls without leaving
the tone grid.

**Toggle:** Click **⚡ Live** in the toolbar, or **View → ⚡ Live Controls**.

### Snapshot Navigation

| Button | Action |
|---|---|
| ◀ Prev | Go to previous snapshot |
| Next ▶ | Go to next snapshot |

The HX Stomp supports up to 4 snapshots per preset (indices 0–3). Each snapshot
stores independent block bypass states and parameter values within one preset.

### Tap Tempo

| Control | Description |
|---|---|
| **⏱ Tap** | Each press sends a tap to the device and records the interval |
| BPM display | Updates after 2+ taps; uses the mean of the last 8 intervals |
| **Reset** | Clears tap history; intervals longer than 4 s auto-reset |

### Looper Transport

| Button | Action | Visual state |
|---|---|---|
| ⏺ Rec | Start recording | Red |
| ▶ Play | Start playback | Green |
| ⏹ Stop | Stop playback | — |
| ↩ Undo | Undo / redo last overdub | — |
| ⟳ OD | Overdub | Orange |
| ⊙ Once | Play once then stop | — |
| ↔ Rev | Toggle reverse | Blue when active |
| ½ ½Spd | Toggle half speed | Blue when active |

> **Note:** Button highlight states are tracked by the app only. If you operate the
> looper from the physical footswitches, the UI state will be out of sync until you
> use the app controls again.

---

## Tuner

Toggle the tuner via **MIDI → 🎵 Toggle Tuner**.

The HX Stomp's tuner is a **hardware toggle** — CC68 flips the state regardless of
the value sent. The app tracks the state internally and shows "Tuner ON" or
"Tuner OFF" in the status bar. If you use the hardware footswitch to toggle the
tuner, the app's tracked state will diverge until the next in-app toggle.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| **Ctrl+S** | Save tones to disk |
| **Ctrl+R** | Reload tones from disk |

---

## CLI Reference

```
python main.py [OPTIONS]

Options:
  --presets PATH        Tone data file  (default: presets.json)
  --list-ports          Print available MIDI output ports and exit
  --mock-midi           Software mock — no hardware required; all MIDI
                        messages printed to stdout
  --no-llm              Disable AI generation entirely (✨ Generate shows
                        an info dialog instead of opening the generator)
  --api-key KEY         Set API key for the active LLM provider and save
                        to ~/.hxstomp/config.json
  --llm-provider NAME   Override the provider from config
                        Choices: anthropic | openai | ollama | gemini
```

**Examples**

```bash
# Load a custom tone file
python main.py --presets ~/my_gig_tones.json

# Set API key for Anthropic on first run
python main.py --api-key sk-ant-...

# Switch to Ollama and launch
python main.py --llm-provider ollama

# Stage setup (disable AI to prevent accidental dialogs)
python main.py --no-llm
```

---

## Configuration File

`~/.hxstomp/config.json` is created automatically the first time you configure an
AI provider. Edit it directly or use the in-app **⚙ Configure…** dialog.

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

All keys are optional; missing values use the defaults shown above.

---

## MIDI Overview

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

Complete CC map, bank/setlist addressing, and footswitch numbering →
**[docs/MIDI_REFERENCE.md](docs/MIDI_REFERENCE.md)**

---

## Project Structure

```
hx_stomp_midiui/
├── main.py              Entry point, CLI flags, MockHXStompMidi
├── midi_interface.py    HXStompMidi — all CC constants and MIDI methods
├── tone_manager.py      Tone dataclass, JSON persistence, CRUD
├── soundboard_ui.py     Full UI — SoundboardApp, dialogs, LiveControlPanel
├── llm_generator.py     AI providers, GenerateToneDialog, config helpers
├── presets.json         Default tone library (edit freely)
├── requirements.txt     Python dependencies
└── docs/
    ├── MIDI_REFERENCE.md   Complete CC map and bank/preset addressing
    └── LLM_PROVIDERS.md    Step-by-step setup for each AI provider
```

---

## License

MIT — see [LICENSE](LICENSE)
