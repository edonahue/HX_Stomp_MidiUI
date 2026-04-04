"""
midi_interface.py

Low-level MIDI interface for the Line 6 HX Stomp.

The HX Stomp responds to standard MIDI messages on a configurable channel
(factory default: channel 1, i.e. channel index 0).

Complete reserved MIDI CC map (from Line 6 official documentation and
community research — firmware 2.65+):

  CC  0   Bank Select MSB (usually 0)
  CC  1   EXP 1 expression pedal position (0–127)
  CC  2   EXP 2 expression pedal position (0–127)
  CC  32  Bank Select LSB / setlist selector (0 = setlist 1)
  CC  49  Stomp FS1 emulation  (0–63 = release, 64–127 = press → toggles block)
  CC  50  Stomp FS2
  CC  51  Stomp FS3
  CC  52  Stomp FS4
  CC  53  Stomp FS5
  CC  54  Stomp FS7  ← FS6 does not exist in Helix/HX numbering
  CC  55  Stomp FS8
  CC  56  Stomp FS9
  CC  57  Stomp FS10
  CC  58  Stomp FS11
  CC  59  EXP Toe Switch (0–63 = off, 64–127 = on)
  CC  60  Looper Record/Overdub  (0–63 = Overdub, 64–127 = Record)
  CC  61  Looper Play/Stop       (0–63 = Stop,    64–127 = Play)
  CC  62  Looper Play Once       (64–127 = trigger)
  CC  63  Looper Undo/Redo       (64–127 = trigger)
  CC  64  Tap Tempo              (any value = one tap)
  CC  65  Looper Forward/Reverse (0–63 = Forward,    64–127 = Reverse)
  CC  66  Looper Full/Half Speed (0–63 = Full Speed, 64–127 = Half Speed)
  CC  67  Looper On/Off          (0–63 = Off,        64–127 = On)
  CC  68  Tuner toggle           (any value toggles on/off)
  CC  69  Snapshot select        (0–7 = snap 1–8, 8 = next, 9 = previous)
  CC  71  Reserved (future use)

IMPORTANT notes:
  - Footswitch CCs (49–58) EMULATE a button press/release. They TOGGLE the
    assigned block — they do not set an absolute on/off state. To control
    absolute bypass state, assign a custom CC in HX Edit (Global Settings →
    MIDI/Tempo → MIDI CC).
  - Tuner (CC 68) is always a TOGGLE — any value flips the current state.
    This class tracks tuner state internally, but that state can become
    out of sync if the tuner is toggled directly on the hardware.
  - Looper CCs have defined on/off semantics (0–63 vs 64–127), not toggle.
"""

from __future__ import annotations

import mido


# ---------------------------------------------------------------------------
# CC number constants
# ---------------------------------------------------------------------------

CC_BANK_MSB     = 0    # Bank Select coarse (usually 0)
CC_EXP1         = 1    # Expression pedal 1 position
CC_EXP2         = 2    # Expression pedal 2 position
CC_BANK_LSB     = 32   # Bank Select fine / setlist

# Stomp footswitch emulation — emulates pressing the physical footswitch.
# Note: Helix/HX family numbering skips FS6; CC54 = FS7.
CC_FS1          = 49
CC_FS2          = 50
CC_FS3          = 51
CC_FS4          = 52
CC_FS5          = 53
CC_FS7          = 54   # FS6 does not exist in Line 6 Helix numbering
CC_FS8          = 55
CC_FS9          = 56
CC_FS10         = 57
CC_FS11         = 58
CC_EXP_TOE      = 59   # EXP Toe Switch

# Looper transport controls
CC_LOOP_REC     = 60   # 0–63 = Overdub,  64–127 = Record
CC_LOOP_PLAY    = 61   # 0–63 = Stop,     64–127 = Play
CC_LOOP_ONCE    = 62   # 64–127 = Play Once (trigger)
CC_LOOP_UNDO    = 63   # 64–127 = Undo/Redo (trigger)
CC_TAP_TEMPO    = 64   # any value = one tap
CC_LOOP_REV     = 65   # 0–63 = Forward,  64–127 = Reverse
CC_LOOP_HALF    = 66   # 0–63 = Full Speed, 64–127 = Half Speed
CC_LOOP_ONOFF   = 67   # 0–63 = Off,      64–127 = On

CC_TUNER        = 68   # any value toggles the tuner screen
CC_SNAPSHOT     = 69   # 0–7 = snapshot 1–8; 8 = next; 9 = previous

# Snapshot navigation special values
SNAPSHOT_NEXT = 8
SNAPSHOT_PREV = 9

# Footswitch number → CC number mapping (FS6 intentionally absent)
_FS_CC: dict[int, int] = {
    1: CC_FS1, 2: CC_FS2,  3: CC_FS3, 4: CC_FS4,  5: CC_FS5,
    7: CC_FS7, 8: CC_FS8,  9: CC_FS9, 10: CC_FS10, 11: CC_FS11,
}

# Generic "pressed" / "released" values
_PRESS   = 127
_RELEASE = 0


# ---------------------------------------------------------------------------
# HXStompMidi
# ---------------------------------------------------------------------------

class HXStompMidi:
    """
    Manages a MIDI output connection to the HX Stomp and provides
    high-level helpers for all reserved MIDI CC functions.
    """

    def __init__(self, port_name: str = None, channel: int = 0):
        """
        Parameters
        ----------
        port_name : str, optional
            Substring of the MIDI output port name to connect to.
            If None, no connection is made at construction time.
        channel : int
            MIDI channel index (0-based; channel 1 on device = 0 here).
        """
        self.channel = channel
        self._port: mido.ports.BaseOutput | None = None
        self._port_name: str = ""
        self._tuner_active: bool = False  # internal tuner state tracker

        if port_name is not None:
            self.connect(port_name)

    # ------------------------------------------------------------------
    # Port management
    # ------------------------------------------------------------------

    @staticmethod
    def list_output_ports() -> list[str]:
        """Return all available MIDI output port names."""
        return mido.get_output_names()

    @staticmethod
    def find_hx_port() -> str | None:
        """Auto-detect the HX Stomp MIDI port by name substrings."""
        keywords = ("hx stomp", "hx-stomp", "line 6", "line6", "helix")
        for name in mido.get_output_names():
            if any(k in name.lower() for k in keywords):
                return name
        return None

    def connect(self, port_name: str) -> None:
        """
        Open the MIDI output port whose name contains `port_name`
        (case-insensitive substring match).
        Raises ValueError if no matching port is found.
        """
        self.disconnect()
        available = mido.get_output_names()
        match = next(
            (p for p in available if port_name.lower() in p.lower()), None)
        if match is None:
            raise ValueError(
                f"No MIDI output port matching '{port_name}' found.\n"
                f"Available ports: {available}")
        self._port = mido.open_output(match)
        self._port_name = match
        self._tuner_active = False  # reset tracked state on new connection
        print(f"[HXStomp] Connected to: {match}")

    def connect_first_available(self) -> str:
        """Connect to the first available MIDI output port. Returns port name."""
        ports = mido.get_output_names()
        if not ports:
            raise RuntimeError("No MIDI output ports available.")
        self.connect(ports[0])
        return self._port_name

    def disconnect(self) -> None:
        if self._port and not self._port.closed:
            self._port.close()
        self._port = None
        self._port_name = ""

    @property
    def is_connected(self) -> bool:
        return self._port is not None and not self._port.closed

    @property
    def port_name(self) -> str:
        return self._port_name

    # ------------------------------------------------------------------
    # Low-level send primitives
    # ------------------------------------------------------------------

    def _require_connection(self) -> None:
        if not self.is_connected:
            raise RuntimeError(
                "Not connected to a MIDI port. Call connect() first.")

    def send_cc(self, control: int, value: int) -> None:
        """Send a raw Control Change message."""
        self._require_connection()
        self._port.send(mido.Message(
            "control_change", channel=self.channel,
            control=control, value=value))

    def send_program_change(self, program: int) -> None:
        """Send a Program Change message (0–127)."""
        self._require_connection()
        self._port.send(mido.Message(
            "program_change", channel=self.channel, program=program))

    # ------------------------------------------------------------------
    # Preset / bank navigation
    # ------------------------------------------------------------------

    def select_preset(self, preset: int,
                      bank_msb: int = 0, bank_lsb: int = 0) -> None:
        """
        Switch to a preset.

        Sends Bank Select MSB (CC0), Bank Select LSB (CC32), then PC.

        Parameters
        ----------
        preset   : Program Change number (0–127).
        bank_msb : Bank Select MSB — almost always 0.
        bank_lsb : Bank Select LSB — selects setlist (0 = setlist 1).
        """
        self._require_connection()
        self.send_cc(CC_BANK_MSB, bank_msb)
        self.send_cc(CC_BANK_LSB, bank_lsb)
        self.send_program_change(preset)
        print(f"[HXStomp] Preset → bank({bank_msb},{bank_lsb}) PC {preset}")

    def select_preset_and_snapshot(
            self, preset: int, snapshot: int = 0,
            bank_msb: int = 0, bank_lsb: int = 0) -> None:
        """Convenience: switch preset then select a snapshot."""
        self.select_preset(preset, bank_msb, bank_lsb)
        self.select_snapshot(snapshot)

    # ------------------------------------------------------------------
    # Snapshot navigation
    # ------------------------------------------------------------------

    def select_snapshot(self, snapshot: int) -> None:
        """
        Select a snapshot within the current preset.

        Parameters
        ----------
        snapshot : 0–7 selects snapshots 1–8 directly.
                   Use SNAPSHOT_NEXT (8) or SNAPSHOT_PREV (9) to step
                   relative to the current snapshot.
        """
        if snapshot not in range(10):
            raise ValueError(f"Snapshot must be 0–9 (got {snapshot})")
        self.send_cc(CC_SNAPSHOT, snapshot)
        if snapshot == SNAPSHOT_NEXT:
            print("[HXStomp] Snapshot → next")
        elif snapshot == SNAPSHOT_PREV:
            print("[HXStomp] Snapshot → previous")
        else:
            print(f"[HXStomp] Snapshot → {snapshot + 1}")

    def next_snapshot(self) -> None:
        """Step to the next snapshot within the current preset."""
        self.select_snapshot(SNAPSHOT_NEXT)

    def prev_snapshot(self) -> None:
        """Step to the previous snapshot within the current preset."""
        self.select_snapshot(SNAPSHOT_PREV)

    # ------------------------------------------------------------------
    # Footswitch emulation
    # ------------------------------------------------------------------

    def press_footswitch(self, fs: int) -> None:
        """
        Emulate pressing a stomp footswitch (CC value 127).

        This TOGGLES the block assigned to that footswitch on the device —
        it does not set an absolute bypass state. To set absolute state,
        assign a custom CC in HX Edit (Global Settings → MIDI/Tempo).

        Parameters
        ----------
        fs : Footswitch number. Valid values: 1–5, 7–11.
             (FS6 does not exist in Line 6 Helix/HX numbering.)
        """
        cc = _FS_CC.get(fs)
        if cc is None:
            valid = sorted(_FS_CC)
            raise ValueError(
                f"Invalid footswitch {fs}. Valid: {valid} (FS6 does not exist)")
        self.send_cc(cc, _PRESS)

    def release_footswitch(self, fs: int) -> None:
        """
        Emulate releasing a stomp footswitch (CC value 0).
        Sending release alone has no effect on the device; it is provided
        for completeness when simulating full press/release cycles.
        """
        cc = _FS_CC.get(fs)
        if cc is None:
            raise ValueError(f"Invalid footswitch {fs}.")
        self.send_cc(cc, _RELEASE)

    # ------------------------------------------------------------------
    # Expression pedals
    # ------------------------------------------------------------------

    def set_exp1(self, value: int) -> None:
        """Set EXP 1 pedal position (CC 1, 0–127)."""
        if not 0 <= value <= 127:
            raise ValueError(f"EXP value must be 0–127 (got {value})")
        self.send_cc(CC_EXP1, value)

    def set_exp2(self, value: int) -> None:
        """Set EXP 2 pedal position (CC 2, 0–127)."""
        if not 0 <= value <= 127:
            raise ValueError(f"EXP value must be 0–127 (got {value})")
        self.send_cc(CC_EXP2, value)

    def set_exp_toe(self, engaged: bool) -> None:
        """
        Engage or release the EXP toe switch (CC 59).
        engaged=True sends 127; engaged=False sends 0.
        """
        self.send_cc(CC_EXP_TOE, _PRESS if engaged else _RELEASE)

    # ------------------------------------------------------------------
    # Tap Tempo
    # ------------------------------------------------------------------

    def tap_tempo(self) -> None:
        """
        Send one tap tempo pulse (CC 64, value 127).
        Call repeatedly at the desired tempo interval to set BPM.
        """
        self.send_cc(CC_TAP_TEMPO, _PRESS)

    # ------------------------------------------------------------------
    # Tuner
    # ------------------------------------------------------------------

    def toggle_tuner(self) -> bool:
        """
        Toggle the tuner screen (CC 68, any value).

        The HX Stomp tuner is always a toggle — any CC 68 message flips
        the current state regardless of value. This method tracks state
        internally and returns the new state (True = tuner now active).

        Note: internal state may become out of sync if the tuner button
        is pressed directly on the hardware.
        """
        self.send_cc(CC_TUNER, _PRESS)
        self._tuner_active = not self._tuner_active
        print(f"[HXStomp] Tuner {'ON' if self._tuner_active else 'OFF'}")
        return self._tuner_active

    def set_tuner(self, on: bool) -> None:
        """
        Set tuner to a known state.

        Sends CC 68 only if the tracked internal state differs from `on`.
        Because the tuner is a hardware toggle, internal state can become
        out of sync if the hardware tuner button is used directly.
        """
        if self._tuner_active != on:
            self.toggle_tuner()

    @property
    def tuner_active(self) -> bool:
        """Tracked tuner state (may be out of sync if hardware was used)."""
        return self._tuner_active

    # ------------------------------------------------------------------
    # Looper controls
    # ------------------------------------------------------------------

    def looper_record(self) -> None:
        """Start recording (CC 60, value 127)."""
        self.send_cc(CC_LOOP_REC, _PRESS)

    def looper_overdub(self) -> None:
        """Switch to overdub mode (CC 60, value 0)."""
        self.send_cc(CC_LOOP_REC, _RELEASE)

    def looper_play(self) -> None:
        """Start playback (CC 61, value 127)."""
        self.send_cc(CC_LOOP_PLAY, _PRESS)

    def looper_stop(self) -> None:
        """Stop playback (CC 61, value 0)."""
        self.send_cc(CC_LOOP_PLAY, _RELEASE)

    def looper_play_once(self) -> None:
        """Play loop once then stop (CC 62, value 127)."""
        self.send_cc(CC_LOOP_ONCE, _PRESS)

    def looper_undo_redo(self) -> None:
        """Undo or redo last looper action (CC 63, value 127)."""
        self.send_cc(CC_LOOP_UNDO, _PRESS)

    def looper_reverse(self, on: bool) -> None:
        """Enable (True) or disable (False) reverse playback (CC 65)."""
        self.send_cc(CC_LOOP_REV, _PRESS if on else _RELEASE)

    def looper_half_speed(self, on: bool) -> None:
        """Enable (True) or disable (False) half-speed mode (CC 66)."""
        self.send_cc(CC_LOOP_HALF, _PRESS if on else _RELEASE)

    def looper_enabled(self, on: bool) -> None:
        """Turn the looper block on (True) or off (False) (CC 67)."""
        self.send_cc(CC_LOOP_ONOFF, _PRESS if on else _RELEASE)

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.disconnect()
