"""
midi_interface.py

Low-level MIDI interface for the Line 6 HX Stomp.

The HX Stomp responds to standard MIDI messages on a configurable channel
(factory default: channel 1, i.e. channel index 0).

Key MIDI messages used:
  - Bank Select MSB  : CC 0,  value = bank high byte  (usually 0)
  - Bank Select LSB  : CC 32, value = bank low byte   (0-3 for setlists 1-4)
  - Program Change   : PC 0-127 selects the preset within the current bank
  - Snapshot Select  : CC 69, value 0-7 selects snapshot 1-8 within the preset
  - Tuner Toggle     : CC 68, value 0 = off, 127 = on
  - Effect Bypass    : CC 49-54 (FS1-FS6), value 0 = bypass, 127 = engage
"""

import mido


# HX Stomp MIDI CC numbers
CC_BANK_MSB       = 0    # Bank Select (coarse)
CC_BANK_LSB       = 32   # Bank Select (fine / setlist)
CC_TUNER          = 68   # Tuner on/off
CC_SNAPSHOT       = 69   # Snapshot select (value 0-7)
CC_FS1_BYPASS     = 49   # Footswitch 1 effect block bypass
CC_FS2_BYPASS     = 50
CC_FS3_BYPASS     = 51
CC_FS4_BYPASS     = 52
CC_FS5_BYPASS     = 53
CC_FS6_BYPASS     = 54

BYPASS_OFF    = 0
BYPASS_ON     = 127
TUNER_OFF     = 0
TUNER_ON      = 127


class HXStompMidi:
    """
    Manages a MIDI output connection to the HX Stomp and provides
    high-level helpers for preset and snapshot switching.
    """

    def __init__(self, port_name: str = None, channel: int = 0):
        """
        Parameters
        ----------
        port_name : str, optional
            Substring of the MIDI port name to connect to.  If None, the
            first available output port is used.
        channel : int
            MIDI channel index (0-based, so channel 1 = 0).
        """
        self.channel   = channel
        self._port     = None
        self._port_name: str = ""

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
        """
        Try to auto-detect the HX Stomp port by looking for common
        substrings in the port names.
        """
        keywords = ("hx stomp", "hx-stomp", "line 6", "line6")
        for name in mido.get_output_names():
            if any(k in name.lower() for k in keywords):
                return name
        return None

    def connect(self, port_name: str) -> None:
        """
        Open a MIDI output port whose name contains `port_name` (case-insensitive).
        Raises ValueError if no matching port is found.
        """
        self.disconnect()
        available = mido.get_output_names()
        match = next(
            (p for p in available if port_name.lower() in p.lower()),
            None,
        )
        if match is None:
            raise ValueError(
                f"No MIDI output port matching '{port_name}' found.\n"
                f"Available ports: {available}"
            )
        self._port = mido.open_output(match)
        self._port_name = match
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
    # Low-level send
    # ------------------------------------------------------------------

    def _require_connection(self) -> None:
        if not self.is_connected:
            raise RuntimeError("Not connected to a MIDI port. Call connect() first.")

    def send_cc(self, control: int, value: int) -> None:
        """Send a Control Change message."""
        self._require_connection()
        msg = mido.Message("control_change", channel=self.channel,
                           control=control, value=value)
        self._port.send(msg)

    def send_program_change(self, program: int) -> None:
        """Send a Program Change message (0-127)."""
        self._require_connection()
        msg = mido.Message("program_change", channel=self.channel, program=program)
        self._port.send(msg)

    # ------------------------------------------------------------------
    # High-level HX Stomp helpers
    # ------------------------------------------------------------------

    def select_preset(self, preset: int, bank_msb: int = 0, bank_lsb: int = 0) -> None:
        """
        Switch to a preset on the HX Stomp.

        Parameters
        ----------
        preset   : int  Program number 0-127.
        bank_msb : int  Bank Select MSB (usually 0).
        bank_lsb : int  Bank Select LSB — corresponds to the setlist (0=setlist 1).
        """
        self._require_connection()
        self.send_cc(CC_BANK_MSB, bank_msb)
        self.send_cc(CC_BANK_LSB, bank_lsb)
        self.send_program_change(preset)
        print(f"[HXStomp] Preset → bank({bank_msb},{bank_lsb}) PC {preset}")

    def select_snapshot(self, snapshot: int) -> None:
        """
        Select a snapshot (0-7) within the current preset.
        The HX Stomp supports up to 3 snapshots per preset (0, 1, 2).
        """
        if not 0 <= snapshot <= 7:
            raise ValueError(f"Snapshot must be 0-7, got {snapshot}")
        self.send_cc(CC_SNAPSHOT, snapshot)
        print(f"[HXStomp] Snapshot → {snapshot + 1}")

    def select_preset_and_snapshot(
        self,
        preset: int,
        snapshot: int = 0,
        bank_msb: int = 0,
        bank_lsb: int = 0,
    ) -> None:
        """Convenience: switch preset then select snapshot."""
        self.select_preset(preset, bank_msb, bank_lsb)
        self.select_snapshot(snapshot)

    def set_tuner(self, on: bool) -> None:
        self.send_cc(CC_TUNER, TUNER_ON if on else TUNER_OFF)

    def set_effect_bypass(self, footswitch: int, bypassed: bool) -> None:
        """
        Toggle an effect block bypass via footswitch CC.
        footswitch: 1-6 → CC 49-54
        """
        if not 1 <= footswitch <= 6:
            raise ValueError("Footswitch must be 1-6")
        cc = CC_FS1_BYPASS + (footswitch - 1)
        self.send_cc(cc, BYPASS_ON if not bypassed else BYPASS_OFF)

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.disconnect()
