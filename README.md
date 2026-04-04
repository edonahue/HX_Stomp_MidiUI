# HX Stomp MIDI Soundboard

A modern dark-theme desktop soundboard for the **Line 6 HX Stomp** multi-effects processor. Switch presets and snapshots with one click, manage your tone library, and toggle the tuner — all from a responsive card-grid UI.

---

## Features

- Visual grid of tone cards grouped by category, color-coded per tone
- One-click preset + snapshot switching via MIDI
- Add, edit, duplicate, and remove tones with an in-app dialog
- Manual tone reordering within categories (Up / Down buttons)
- Keyboard shortcuts: `1`–`9` activate the first 9 visible tones; `↑`/`↓` navigate, `Enter` activates
- Tuner toggle via MIDI menu
- Effect bypass panel for footswitches FS1–FS6
- Auto-detect HX Stomp USB MIDI port
- `--mock-midi` mode — full UI without any hardware attached

---

## Requirements

- Python 3.10+
- Linux: `libasound2-dev` and `libjack-dev` for rtmidi

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
# Normal launch (requires HX Stomp connected via USB)
python main.py

# Launch without hardware (mock MIDI — all messages printed to log)
python main.py --mock-midi

# Use a custom presets file
python main.py --presets my_tones.json

# List available MIDI output ports and exit
python main.py --list-ports

# Control log verbosity (DEBUG, INFO, WARNING, ERROR)
python main.py --log-level DEBUG
```

---

## Connecting to the HX Stomp

1. Connect the HX Stomp via USB.
2. Launch the app.
3. Open **MIDI → Connect…**, select the HX Stomp port, choose your MIDI channel (default: 1), and click **Connect**.
4. The status bar turns green when connected.

---

## Managing Tones

Tones are stored in `presets.json` (or the file passed via `--presets`).

### Tone fields

| Field | Description | Range |
|-------|-------------|-------|
| `name` | Display label on the card | Any string |
| `preset` | MIDI Program Change number | 0–127 |
| `snapshot` | Snapshot index within preset | 0–2 (HX Stomp supports 3 per preset) |
| `bank_msb` | Bank Select MSB | 0–127 (usually 0) |
| `bank_lsb` | Bank Select LSB (setlist 1–4 → 0–3) | 0–127 |
| `color` | Card background color | Hex string e.g. `"#4A90D9"` |
| `category` | Grouping label | Any string or omit |

### Example `presets.json` entry

```json
[
  {
    "name": "Clean Surf",
    "preset": 3,
    "snapshot": 0,
    "bank_msb": 0,
    "bank_lsb": 0,
    "color": "#4A90D9",
    "category": "Clean"
  }
]
```

### Toolbar actions

| Button | Action |
|--------|--------|
| ⊕ Add | Create a new tone |
| ✏ Edit | Edit the selected tone (click a card first) |
| ⧉ Duplicate | Clone the selected tone as a starting point |
| ↑ / ↓ | Move the selected tone up or down in its category |
| 🗑 Remove | Delete the selected tone (with confirmation) |
| ↺ Reload | Reload `presets.json` from disk |

Right-click any card for the same options via context menu.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1` – `9` | Activate tone at that position (in display order) |
| `↑` / `↓` | Move card focus up / down |
| `Enter` | Activate focused tone |
| `Ctrl+S` | Save current tones to file |
| `Ctrl+R` | Reload tones from file |

---

## Architecture

```
main.py              CLI entry point, --mock-midi injection, logging setup
midi_interface.py    HXStompMidi class — MIDI port management & HX Stomp protocol
tone_manager.py      Tone dataclass + ToneManager CRUD + JSON persistence
soundboard_ui.py     customtkinter UI — SoundboardApp, ConnectDialog, ToneDialog
presets.json         Tone library (default path)
```
