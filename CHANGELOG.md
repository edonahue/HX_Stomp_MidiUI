# Changelog

All notable changes to HLX Generator are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added

- **Tone search / filter bar** — real-time filtering of tone cards by name or category; `Escape` or ✕ clears the search
- **Generate Variants** — fire 3 parallel LLM calls for the same description with different interpretive hints (default / brighter / warmer); results appear in Option A / B / C tabs so you can compare and pick one
- **Two-way device sync** — MIDI input listener detects program changes and snapshot selects sent by the HX Stomp hardware and highlights the matching tone card (green ring); auto-reconnects after USB disconnect
- **Draft release workflow** — `.github/workflows/draft-release.yml` creates/updates a draft GitHub Release on every push to `main`

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
