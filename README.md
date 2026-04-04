<p align="center">
  <img src="assets/icons/app-icon.png" width="96" alt="HLX Generator">
</p>

<h1 align="center">HLX Generator</h1>

<p align="center">
  AI-powered <code>.hlx</code> preset builder and MIDI soundboard for the Line 6 HX Stomp.
</p>

<p align="center">
  <a href="https://github.com/edonahue/hlx-generator/actions/workflows/test.yml">
    <img src="https://github.com/edonahue/hlx-generator/actions/workflows/test.yml/badge.svg" alt="CI">
  </a>
  <img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <a href="https://github.com/edonahue/hlx-generator/releases/latest">
    <img src="https://img.shields.io/github/v/release/edonahue/hlx-generator?color=blue" alt="Latest Release">
  </a>
</p>

---

<!--
  Hero screenshot — Soundboard tab with tone cards.
  Once captured, save as docs/screenshots/soundboard.png and replace this comment with:
  <p align="center">
    <img src="docs/screenshots/soundboard.png" alt="HLX Generator Soundboard" width="700">
  </p>
  See docs/screenshots/README.md for capture instructions.
-->

## Why HLX Generator?

Scrolling through the HX Stomp's menus mid-performance is a distraction. Building a new signal chain from scratch — choosing amps, cabs, and effects, then dialling in parameters — takes hours. HLX Generator solves both problems: your tones are one click away, and AI can draft a complete `.hlx` signal chain from a plain-English description.

## Features

| 🎵 MIDI Soundboard | ✨ AI Preset Builder |
|---|---|
| One-click tone activation (MIDI PC + Bank Select) | Describe a tone → full `.hlx` signal chain |
| Snapshot, tuner, tap tempo, looper controls | Anthropic · OpenAI · Gemini · Ollama |
| Expression pedal control | Manual Mode — paste prompt to any AI chatbot |
| 12 tones included (Clean / Overdrive / High Gain / Ambient) | Preset catalog with browse & export |

## Install

### Download (no Python required)

Get the latest installer from the [**Releases page**](https://github.com/edonahue/hlx-generator/releases/latest).

| Platform | File |
|---|---|
| macOS Apple Silicon | `HLXGenerator-*-arm64.dmg` |
| macOS Intel (10.15+) | `HLXGenerator-*-x86_64.dmg` |
| Linux (Ubuntu 22.04+) | `hlx-generator_*_amd64.deb` — `sudo dpkg -i hlx-generator_*.deb` |
| Windows 10/11 | `HLXGenerator-*-Setup.exe` |

<details>
<summary>⚠️ Unsigned app — first-launch instructions</summary>

These binaries are not code-signed.

**macOS:** Right-click the app → **Open** → **Open anyway**.  
Or via Terminal:
```bash
xattr -d com.apple.quarantine /Applications/HLXGenerator.app
```

**Windows:** When SmartScreen appears, click **More info** → **Run anyway**.

</details>

### Run from source

```bash
git clone https://github.com/edonahue/hlx-generator
cd hlx-generator
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

No HX Stomp? `python main.py --mock-midi` runs the full UI without hardware.

## Quick Start

1. Launch the app — the **HLX Generator** tab opens by default
2. Switch to the **Soundboard** tab → click **Connect** → select your USB MIDI port
3. Click any tone card to send it to the pedal instantly
4. Back on the **HLX Generator** tab, click **✨ Generate Preset**, describe a tone, and save the resulting `.hlx` to load in HX Edit

> **Keyboard shortcuts:** `1`–`9` activate tones directly · `↑`/`↓` navigate · `Enter` activates

<!--
  AI Builder screenshot — HLX Generator tab with a generated signal chain.
  Save as docs/screenshots/ai-builder.png and replace this comment with:
  <p align="center">
    <img src="docs/screenshots/ai-builder.png" alt="AI Preset Builder" width="700">
  </p>
-->

## Configuration

| Flag | Purpose |
|---|---|
| `--mock-midi` | Run without hardware |
| `--no-llm` | Disable AI features |
| `--presets PATH` | Use a custom presets file (default: `presets.json`) |
| `--llm-provider NAME` | Set AI provider: `anthropic` · `openai` · `gemini` · `ollama` |
| `--api-key KEY` | Set API key for the active provider |

## Documentation

- [AI Preset Generation](docs/HLX_GENERATION.md) — how `.hlx` files are built, tips, model catalog
- [LLM Provider Setup](docs/LLM_PROVIDERS.md) — step-by-step API key setup for each provider
- [MIDI Reference](docs/MIDI_REFERENCE.md) — complete CC map and MIDI addressing guide
- [Changelog](CHANGELOG.md)

## Requirements

- **Python 3.9+** — or use an installer (no Python needed)
- **Line 6 HX Stomp** via USB — optional; `--mock-midi` works without hardware
- **AI features** — API key for Anthropic, OpenAI, or Gemini; [Ollama](https://ollama.com) is free and local
- **Linux only** — `sudo apt install libasound2` (MIDI runtime library)

## License

MIT — see [LICENSE](LICENSE).
