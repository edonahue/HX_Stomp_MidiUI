# Changelog

All notable changes to HLX Generator are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-04-04

### Added

- **MIDI Soundboard** — one-click tone activation via MIDI Program Change + Bank Select; snapshot, tuner, tap tempo, looper, and expression pedal controls
- **AI Preset Builder** — full `.hlx` signal chain generation (amp, cab, effects, snapshots) from a plain-English description
- **Provider support** — Anthropic Claude, OpenAI GPT, Google Gemini, and Ollama (local)
- **Manual Mode** — copy the system prompt to any AI chatbot and paste the response back
- **Preset Catalog** — browse, export, and manage generated presets from `~/.hxstomp/presets/`
- **12 included tones** — Clean, Overdrive, High Gain, and Ambient categories ready to assign
- **3 example presets** — `AFD_Appetite.hlx`, `Slash's_Brit_Ple.hlx`, `Slash_Tone.hlx` in `saved_presets/`
- **Keyboard shortcuts** — `1`–`9` for direct tone activation, `↑`/`↓` to navigate, `Enter` to activate
- **Cross-platform installers** — `.deb` (Linux), `.dmg` × 2 (macOS Intel + Apple Silicon), NSIS `.exe` (Windows)
- **84 verified HX Stomp models** across 8 categories (Amp, Cab, Distortion, Dynamics, EQ, Modulation, Delay, Reverb)
