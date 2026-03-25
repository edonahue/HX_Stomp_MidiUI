# MIDI Reference — HX Stomp Soundboard

Complete MIDI control change (CC) map and addressing guide for the Line 6 HX Stomp,
as implemented in this application.

All information applies to HX Stomp, HX Stomp XL, and other Helix-family devices.

---

## MIDI Channel

All messages are sent on the channel you select at connect time (displayed as 1–16).

The app uses 0-based channel numbers internally (channel 1 = index 0), but the
connect dialog always shows 1-based values.

**Match this to the device:**
*Menu → Global Settings → MIDI/Tempo → MIDI Channel*

The HX Stomp factory default is channel **1**.

---

## Preset Selection

Selecting a preset sends three messages in sequence:

```
CC0  (Bank Select MSB)  → value = bank_msb  (usually 0)
CC32 (Bank Select LSB)  → value = bank_lsb  (setlist index)
PC   (Program Change)   → value = preset    (0–127)
```

### Setlist / Bank LSB Mapping

| Bank LSB | HX Stomp Setlist |
|---|---|
| 0 | Setlist 1 (128 presets, PC 0–127) |
| 1 | Setlist 2 |
| 2 | Setlist 3 |
| 3 | Setlist 4 |

### Preset Number Conversion

The HX Stomp display uses a 1-based label with a letter suffix (A–D):

| Display | PC value |
|---|---|
| 1A | 0 |
| 1B | 1 |
| 1C | 2 |
| 1D | 3 |
| 2A | 4 |
| … | … |
| 32D | 127 |

**Formula:** `PC = (row - 1) × 4 + (letter_index)`
Where letter_index: A=0, B=1, C=2, D=3

**Example:** Preset "17B" = (17-1) × 4 + 1 = **65**

If you send a Program Change without first sending CC0/CC32, the device stays in
the current setlist and bank.

---

## Snapshot Selection — CC69

| Value | Action |
|---|---|
| 0 | Snapshot 1 |
| 1 | Snapshot 2 |
| 2 | Snapshot 3 |
| 3 | Snapshot 4 |
| 4 | Snapshot 5 |
| 5 | Snapshot 6 |
| 6 | Snapshot 7 |
| 7 | Snapshot 8 |
| 8 | **Next** snapshot (relative) |
| 9 | **Previous** snapshot (relative) |

The HX Stomp supports up to 4 snapshots per preset (indices 0–3) in standard mode,
or up to 8 in extended snapshot mode.

---

## Tuner — CC68

**Any value** toggles the tuner screen.

CC68 is a **toggle only** — there is no "force on" value or "force off" value.
The app tracks the state it believes the tuner to be in and uses this to implement
`set_tuner(on: bool)` (only sends CC68 if the current tracked state differs from
the requested state).

If you toggle the tuner from the physical footswitch, the app's tracked state will
be out of sync until the next in-app toggle.

---

## Tap Tempo — CC64

**Any value** registers as one tap.

Send CC64 repeatedly to set tempo. The HX Stomp calculates BPM from the interval
between the last two taps. The app's Live Controls panel tracks its own interval
history (mean of last 8 taps) for BPM display, and sends CC64 on every tap.

---

## Footswitch Emulation — CC49–58

Each footswitch CC **emulates pressing the physical footswitch** — it toggles the
bypass state of whatever block is assigned to that footswitch in the current preset.

| CC | Footswitch |
|---|---|
| 49 | FS1 |
| 50 | FS2 |
| 51 | FS3 |
| 52 | FS4 |
| 53 | FS5 |
| 54 | FS7 |
| 55 | FS8 |
| 56 | FS9 |
| 57 | FS10 |
| 58 | FS11 |

> **Note:** FS6 does not exist in Line 6 / Helix numbering. CC54 maps to FS7.

**Values:**
- `127` — press (toggles bypass state)
- `0` — release (no effect in most configurations)

There is no "force bypass on" or "force bypass off" — these CCs mirror the physical
footswitch behavior exactly.

---

## Expression Pedals — CC1, CC2, CC59

| CC | Control | Value range |
|---|---|---|
| 1 | EXP 1 position | 0 (heel) – 127 (toe) |
| 2 | EXP 2 position | 0 (heel) – 127 (toe) |
| 59 | EXP Toe Switch | 0–63 = released, 64–127 = engaged |

EXP pedal CCs control whatever parameters are assigned to EXP 1 and EXP 2 in the
current preset's block assignments.

---

## Looper Transport — CC60–67

The looper CCs use a threshold-based on/off semantic rather than toggle:
- Values **0–63** = "off" state
- Values **64–127** = "on" state

| CC | Function | Off (0–63) | On (64–127) |
|---|---|---|---|
| 60 | Record / Overdub | Overdub | Record |
| 61 | Play / Stop | Stop | Play |
| 62 | Play Once | — | Trigger (send 127) |
| 63 | Undo / Redo | — | Trigger (send 127) |
| 65 | Reverse | Forward | Reverse |
| 66 | Half Speed | Full speed | Half speed |
| 67 | Looper block on/off | Off | On |

### Recommended Sequences

**Start a loop from scratch:**
```
CC60 val 127   → Record
CC61 val 127   → Play (ends recording, starts playback)
```

**Overdub onto existing loop:**
```
CC60 val 0     → Overdub
```

**Stop and undo:**
```
CC61 val 0     → Stop
CC63 val 127   → Undo
```

---

## Complete CC Map Reference

| CC | Name | Values / Behavior |
|---|---|---|
| 0 | Bank Select MSB | 0–127; send before PC |
| 1 | EXP 1 | 0–127 position |
| 2 | EXP 2 | 0–127 position |
| 32 | Bank Select LSB | 0–3 for setlists 1–4 |
| 49 | FS1 emulate | 127=press, 0=release |
| 50 | FS2 emulate | 127=press, 0=release |
| 51 | FS3 emulate | 127=press, 0=release |
| 52 | FS4 emulate | 127=press, 0=release |
| 53 | FS5 emulate | 127=press, 0=release |
| 54 | FS7 emulate | 127=press, 0=release |
| 55 | FS8 emulate | 127=press, 0=release |
| 56 | FS9 emulate | 127=press, 0=release |
| 57 | FS10 emulate | 127=press, 0=release |
| 58 | FS11 emulate | 127=press, 0=release |
| 59 | EXP Toe Switch | 0–63=off, 64–127=on |
| 60 | Looper Record/Overdub | 0–63=overdub, 64–127=record |
| 61 | Looper Play/Stop | 0–63=stop, 64–127=play |
| 62 | Looper Play Once | 64–127=trigger |
| 63 | Looper Undo/Redo | 64–127=trigger |
| 64 | Tap Tempo | any value = one tap |
| 65 | Looper Reverse | 0–63=forward, 64–127=reverse |
| 66 | Looper Half Speed | 0–63=full, 64–127=half |
| 67 | Looper On/Off | 0–63=off, 64–127=on |
| 68 | Tuner | any value = toggle |
| 69 | Snapshot | 0–7=direct, 8=next, 9=prev |

---

## Python API Reference

The `HXStompMidi` class in `midi_interface.py` wraps all of the above:

```python
from midi_interface import HXStompMidi

midi = HXStompMidi()
midi.connect("HX Stomp")        # or midi.connect_first_available()

# Preset selection
midi.select_preset(preset=10, bank_lsb=0)
midi.select_preset_and_snapshot(preset=10, snapshot=1)

# Snapshots
midi.select_snapshot(2)         # snapshot index 0–9
midi.next_snapshot()
midi.prev_snapshot()

# Tap tempo
midi.tap_tempo()                # call once per tap

# Tuner
midi.toggle_tuner()             # returns new bool state
midi.set_tuner(True)            # smart: only sends if state differs

# Footswitches
midi.press_footswitch(3)        # valid: 1–5, 7–11
midi.release_footswitch(3)

# Expression pedals
midi.set_exp1(64)               # 0–127
midi.set_exp2(0)
midi.set_exp_toe(True)

# Looper
midi.looper_record()
midi.looper_play()
midi.looper_stop()
midi.looper_overdub()
midi.looper_play_once()
midi.looper_undo_redo()
midi.looper_reverse(True)       # bool
midi.looper_half_speed(True)    # bool
midi.looper_enabled(True)       # turn looper block on/off

midi.disconnect()
```
