"""
main.py

Entry point for the HX Stomp Soundboard.

Usage
-----
    python main.py [--presets presets.json] [--mock-midi] [--list-ports]

Optional flags
--------------
    --presets     Path to the JSON file containing tone definitions.
                  Defaults to presets.json in the current directory.
    --list-ports  Print available MIDI output ports and exit.
    --mock-midi   Use a mock MIDI backend — no HX Stomp hardware needed.
                  All MIDI messages are printed to stdout instead of sent.
                  Useful for UI development and testing.
"""

import argparse
import sys

import soundboard_ui
from midi_interface import HXStompMidi
from soundboard_ui import SoundboardApp


# ---------------------------------------------------------------------------
# Mock MIDI backend (no hardware required)
# ---------------------------------------------------------------------------

class MockHXStompMidi:
    """
    Drop-in replacement for HXStompMidi that prints MIDI messages to stdout
    instead of sending them to a real device.  Injected via --mock-midi.
    """

    def __init__(self, port_name: str = None, channel: int = 0):
        self.channel = channel
        self._connected = False
        self._port_name = ""
        if port_name:
            self.connect(port_name)

    # Port management --------------------------------------------------

    @staticmethod
    def list_output_ports() -> list[str]:
        return ["Mock HX Stomp [USB]", "Mock Virtual Port 1"]

    @staticmethod
    def find_hx_port() -> str | None:
        return "Mock HX Stomp [USB]"

    def connect(self, port_name: str) -> None:
        self._connected = True
        self._port_name = port_name
        print(f"[MockMIDI] Connected → {port_name}")

    def connect_first_available(self) -> str:
        ports = self.list_output_ports()
        self.connect(ports[0])
        return self._port_name

    def disconnect(self) -> None:
        if self._connected:
            print("[MockMIDI] Disconnected")
        self._connected = False
        self._port_name = ""

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def port_name(self) -> str:
        return self._port_name

    # MIDI output ------------------------------------------------------

    def send_cc(self, control: int, value: int) -> None:
        print(f"[MockMIDI] CC  ch={self.channel + 1}  cc={control}  val={value}")

    def send_program_change(self, program: int) -> None:
        print(f"[MockMIDI] PC  ch={self.channel + 1}  program={program}")

    def select_preset(self, preset: int, bank_msb: int = 0,
                      bank_lsb: int = 0) -> None:
        print(f"[MockMIDI] Preset → bank({bank_msb},{bank_lsb})  PC {preset}")

    def select_snapshot(self, snapshot: int) -> None:
        print(f"[MockMIDI] Snapshot → {snapshot + 1}")

    def select_preset_and_snapshot(self, preset: int, snapshot: int = 0,
                                    bank_msb: int = 0, bank_lsb: int = 0) -> None:
        self.select_preset(preset, bank_msb, bank_lsb)
        self.select_snapshot(snapshot)

    def set_tuner(self, on: bool) -> None:
        print(f"[MockMIDI] Tuner {'ON' if on else 'OFF'}")

    def set_effect_bypass(self, footswitch: int, bypassed: bool) -> None:
        state = "bypass" if bypassed else "engage"
        print(f"[MockMIDI] FS{footswitch} → {state}")

    def __enter__(self):  return self
    def __exit__(self, *_): self.disconnect()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="HX Stomp MIDI Soundboard")
    parser.add_argument(
        "--presets", default="presets.json",
        help="Path to tone definitions JSON file (default: presets.json)",
    )
    parser.add_argument(
        "--list-ports", action="store_true",
        help="Print available MIDI output ports and exit",
    )
    parser.add_argument(
        "--mock-midi", action="store_true",
        help="Use mock MIDI backend (no hardware needed; messages printed to stdout)",
    )
    args = parser.parse_args()

    if args.list_ports:
        ports = HXStompMidi.list_output_ports()
        if ports:
            print("Available MIDI output ports:")
            for i, p in enumerate(ports):
                print(f"  [{i}] {p}")
        else:
            print("No MIDI output ports found.")
        sys.exit(0)

    if args.mock_midi:
        # Patch the HXStompMidi class used inside soundboard_ui at import time
        soundboard_ui.HXStompMidi = MockHXStompMidi
        print("[MockMIDI] Mock MIDI backend active — no hardware required.")

    app = SoundboardApp(presets_file=args.presets)
    app.mainloop()


if __name__ == "__main__":
    main()
